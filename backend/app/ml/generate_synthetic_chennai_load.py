"""
Generate `backend/data/chennai_hourly_load.csv` with real Chennai-area weather
(OpenWeatherMap One Call 3.0 timemachine when `OPENWEATHER_API_KEY` is set) and
deterministic synthetic grid load (MW) calibrated to Tamil Nadu / Chennai-style
daily and seasonal shapes (public TNEB-style hourly studies as qualitative reference).

Without an API key, weather is synthesized deterministically from the seed so CI
and local workflows still produce a valid training CSV.
"""

from __future__ import annotations

import argparse
import math
import os
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import numpy as np
import pandas as pd

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_OUT = BACKEND_ROOT / "data" / "chennai_hourly_load.csv"

CHENNAI_LAT = 13.0827
CHENNAI_LON = 80.2707
IST = ZoneInfo("Asia/Kolkata")

OWM_TIMEMACHINE_URL = "https://api.openweathermap.org/data/3.0/onecall/timemachine"


def _backend_env_api_key() -> str | None:
    k = os.environ.get("OPENWEATHER_API_KEY", "").strip()
    return k or None


def _season_from_month(month: int) -> str:
    if month in (4, 5, 6):
        return "summer"
    if month in (7, 8, 9):
        return "monsoon"
    if month in (12, 1, 2):
        return "winter"
    return "shoulder"


def _indian_holiday_dates(year: int) -> set[date]:
    """
    Synthetic but plausible fixed-date public holidays (IST calendar dates).
    Variable festivals use approximate 2025-style anchors; deterministic per year.
    """

    fixed = {
        date(year, 1, 26),
        date(year, 8, 15),
        date(year, 10, 2),
        date(year, 12, 25),
    }
    # Approximate movable / lunar (rough placeholders for synthetic is_holiday signal)
    approx = {
        date(year, 3, 14),  # Holi (approx)
        date(year, 10, 21),  # Diwali (approx; varies)
        date(year, 4, 14),  # Tamil New Year (approx)
        date(year, 5, 1),
    }
    return fixed | approx


def _synthetic_hourly_weather(ts_ist: datetime, rng: np.random.Generator) -> dict[str, float]:
    """Deterministic Chennai-like weather when OWM is unavailable."""
    doy = ts_ist.timetuple().tm_yday
    h = ts_ist.hour + ts_ist.minute / 60.0
    seasonal = 2.8 * math.sin((doy - 120) / 365.25 * 2 * math.pi)
    diurnal = 4.2 * math.sin((h - 8.0) / 24.0 * 2 * math.pi)
    base_temp = 29.5 + seasonal + diurnal
    noise = rng.normal(0, 0.35)
    temp_c = float(base_temp + noise)
    feels = temp_c + (1.2 if temp_c > 33 else 0.4) + rng.normal(0, 0.2)
    humidity = float(np.clip(55 + 25 * math.sin((doy + 40) / 365 * 2 * math.pi) - (temp_c - 28) * 1.1 + rng.normal(0, 3), 25, 98))
    wind = float(np.clip(2.5 + rng.normal(0, 1.2), 0.3, 14.0))
    cloud = float(np.clip(40 + 30 * math.sin(doy / 45.0) + rng.normal(0, 8), 0, 100))
    return {
        "temp_c": temp_c,
        "feels_like_c": float(feels),
        "humidity": humidity,
        "wind_speed": wind,
        "cloud_cover": cloud,
    }


def _parse_owm_hourly_payload(data: object) -> list[dict[str, object]]:
    if not isinstance(data, dict):
        return []
    hourly = data.get("hourly")
    if isinstance(hourly, list) and hourly:
        return hourly  # type: ignore[return-value]
    inner = data.get("data")
    if isinstance(inner, list) and inner:
        return inner  # type: ignore[return-value]
    return []


def fetch_owm_timemachine_year(
    *,
    year: int,
    api_key: str,
    lat: float,
    lon: float,
    pause_sec: float = 0.35,
) -> dict[int, dict[str, float]]:
    """
    One request per UTC calendar day; map OpenWeather hourly `dt` (unix, UTC) to features.
    """

    by_dt: dict[int, dict[str, float]] = {}
    start = datetime(year, 1, 1, tzinfo=ZoneInfo("UTC"))
    end = datetime(year, 12, 31, tzinfo=ZoneInfo("UTC"))
    d = start.date()
    end_d = end.date()
    with httpx.Client(timeout=60.0) as client:
        while d <= end_d:
            noon_utc = datetime(d.year, d.month, d.day, 12, 0, tzinfo=ZoneInfo("UTC"))
            dt_unix = int(noon_utc.timestamp())
            try:
                r = client.get(
                    OWM_TIMEMACHINE_URL,
                    params={
                        "lat": lat,
                        "lon": lon,
                        "dt": dt_unix,
                        "appid": api_key,
                        "units": "metric",
                    },
                )
                r.raise_for_status()
                payload = r.json()
                hours = _parse_owm_hourly_payload(payload)
                for h in hours:
                    if not isinstance(h, dict):
                        continue
                    u = int(h.get("dt", 0))
                    if u <= 0:
                        continue
                    temp = h.get("temp")
                    feels = h.get("feels_like", temp)
                    hum = h.get("humidity", 60.0)
                    wind = h.get("wind_speed", 2.0)
                    clouds = h.get("clouds", 40.0)
                    if temp is None:
                        continue
                    by_dt[u] = {
                        "temp_c": float(temp),
                        "feels_like_c": float(feels if feels is not None else temp),
                        "humidity": float(hum),
                        "wind_speed": float(wind),
                        "cloud_cover": float(clouds),
                    }
            except Exception:
                # Skip failed day; caller can fill gaps
                pass
            d = date.fromordinal(d.toordinal() + 1)
            time.sleep(pause_sec)
    return by_dt


def _nearest_weather(by_dt: dict[int, dict[str, float]], unix_ts: int, rng: np.random.Generator, ts_ist: datetime) -> dict[str, float]:
    if not by_dt:
        return _synthetic_hourly_weather(ts_ist, rng)
    # Exact match
    if unix_ts in by_dt:
        return by_dt[unix_ts]
    # Nearest hour bucket
    keys = sorted(by_dt.keys())
    best = min(keys, key=lambda k: abs(k - unix_ts))
    if abs(best - unix_ts) <= 3600 * 3:
        return by_dt[best]
    return _synthetic_hourly_weather(ts_ist, rng)


def _heatwave_by_date(rows_ist: list[datetime], temps: np.ndarray) -> dict[date, bool]:
    by_day: dict[date, list[float]] = {}
    for t, tc in zip(rows_ist, temps):
        d = t.date()
        by_day.setdefault(d, []).append(float(tc))
    out: dict[date, bool] = {}
    for d, arr in by_day.items():
        hot_hours = sum(1 for x in arr if x >= 35.0)
        out[d] = hot_hours >= 4
    return out


def _synthetic_load_mw(
    *,
    hour: float,
    dow: int,
    month: int,
    temp_c: float,
    feels_c: float,
    is_weekend: int,
    is_holiday: int,
    heatwave: int,
    season: str,
    rng: np.random.Generator,
) -> float:
    """
    Qualitative TNEB/Chennai-style curve: evening peak + stronger midday on hot days.
    Scale ~4.8–7.2 GW stylized as city aggregate MW (demo storytelling band).
    """

    # Dual-peak diurnal (IST hour as float)
    midday = 4950.0 + 520.0 * math.sin(((hour - 13.0) / 24.0) * 2.0 * math.pi)
    evening = 980.0 * math.exp(-0.5 * ((hour - 20.0) / 1.85) ** 2)
    noon_ac = 420.0 * math.exp(-0.5 * ((hour - 14.0) / 2.4) ** 2)
    base = midday + evening + noon_ac

    seasonal = 1.0
    if season == "summer":
        seasonal *= 1.12
    elif season == "monsoon":
        seasonal *= 0.98
    elif season == "winter":
        seasonal *= 0.93
    else:
        seasonal *= 1.02

    if is_weekend:
        base *= 0.95
    if is_holiday:
        base *= 0.92

    t_ref = 0.65 * temp_c + 0.35 * feels_c
    temp_excess = max(0.0, t_ref - 30.0)
    ac_factor = 1.0 + 0.022 * (temp_excess**1.38)
    if hour >= 11.0 and hour <= 16.0 and t_ref >= 33.0:
        ac_factor *= 1.0 + 0.06 * min(1.0, (t_ref - 33.0) / 6.0)
    if heatwave:
        ac_factor *= 1.065

    load = base * seasonal * ac_factor
    load *= 1.0 + 0.008 * rng.normal()
    return float(max(3200.0, load))


def generate_dataframe(*, year: int, seed: int, api_key: str | None) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    holidays = _indian_holiday_dates(year)

    ist_start = datetime(year, 1, 1, 0, 0, 0, tzinfo=IST)
    hours_in_year = int((datetime(year + 1, 1, 1, 0, 0, 0, tzinfo=IST) - ist_start).total_seconds() // 3600)

    by_dt: dict[int, dict[str, float]] = {}
    if api_key:
        print("Fetching OpenWeatherMap timemachine data (one call per UTC day)...", file=sys.stderr)
        by_dt = fetch_owm_timemachine_year(year=year, api_key=api_key, lat=CHENNAI_LAT, lon=CHENNAI_LON)
        print(f"OWM hourly samples collected: {len(by_dt)}", file=sys.stderr)
    else:
        print("OPENWEATHER_API_KEY not set; using deterministic synthetic weather.", file=sys.stderr)

    ts_list: list[datetime] = []
    rows: list[dict[str, object]] = []

    for i in range(hours_in_year):
        ts_ist = ist_start + timedelta(hours=i)
        unix_ts = int(ts_ist.astimezone(ZoneInfo("UTC")).timestamp())
        w = _nearest_weather(by_dt, unix_ts, rng, ts_ist)

        hod = ts_ist.hour
        dow = ts_ist.weekday()
        month = ts_ist.month
        is_weekend = 1 if dow >= 5 else 0
        is_holiday = 1 if ts_ist.date() in holidays else 0
        season = _season_from_month(month)

        rows.append(
            {
                "_ts_ist": ts_ist,
                "_unix": unix_ts,
                "hour_of_day": hod,
                "day_of_week": dow,
                "month": month,
                "is_weekend": is_weekend,
                "is_holiday": is_holiday,
                "season": season,
                "temp_c": w["temp_c"],
                "feels_like_c": w["feels_like_c"],
                "humidity": w["humidity"],
                "wind_speed": w["wind_speed"],
                "cloud_cover": w["cloud_cover"],
            }
        )
        ts_list.append(ts_ist)

    temps = np.array([float(r["temp_c"]) for r in rows], dtype=np.float64)
    heatmap = _heatwave_by_date(ts_list, temps)

    loads: list[float] = []
    for r in rows:
        ts_ist = r["_ts_ist"]  # type: ignore[assignment]
        assert isinstance(ts_ist, datetime)
        hw = 1 if heatmap.get(ts_ist.date(), False) else 0
        tref = 0.65 * float(r["temp_c"]) + 0.35 * float(r["feels_like_c"])
        ev = 1 if (hw == 1 or tref >= 38.0 or (tref >= 36.0 and float(r["humidity"]) < 38.0)) else 0
        r["heatwave_flag"] = hw
        r["event_flag"] = ev
        load = _synthetic_load_mw(
            hour=float(r["hour_of_day"]),
            dow=int(r["day_of_week"]),
            month=int(r["month"]),
            temp_c=float(r["temp_c"]),
            feels_c=float(r["feels_like_c"]),
            is_weekend=int(r["is_weekend"]),
            is_holiday=int(r["is_holiday"]),
            heatwave=hw,
            season=str(r["season"]),
            rng=rng,
        )
        loads.append(load)

    load_arr = np.array(loads, dtype=np.float64)
    capacity = float(np.percentile(load_arr, 99.0) * 1.02)
    capacity = max(capacity, 1.0)

    stress_scores = np.clip(100.0 * load_arr / capacity, 0.0, 100.0)
    is_stress = (stress_scores >= 80.0).astype(int)

    out_rows: list[dict[str, object]] = []
    for i, r in enumerate(rows):
        lag = float("nan") if i < 24 else float(loads[i - 24])
        ts_ist = r.pop("_ts_ist")  # type: ignore[misc]
        r.pop("_unix", None)
        ts_iso = ts_ist.astimezone(ZoneInfo("UTC")).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        out_rows.append(
            {
                "timestamp": ts_iso,
                **r,
                "load_mw": float(loads[i]),
                "load_mw_lag_24h": lag,
                "stress_score": float(stress_scores[i]),
                "is_stress_event": int(is_stress[i]),
            }
        )

    df = pd.DataFrame(out_rows)
    df["load_mw_lag_24h"] = pd.to_numeric(df["load_mw_lag_24h"], errors="coerce")
    return df


def main() -> None:
    p = argparse.ArgumentParser(description="Generate chennai_hourly_load.csv")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--year", type=int, default=2025)
    p.add_argument("--out", type=str, default=str(DEFAULT_OUT))
    args = p.parse_args()

    api_key = _backend_env_api_key()
    df = generate_dataframe(year=args.year, seed=args.seed, api_key=api_key)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    print(f"Wrote {out_path} ({len(df)} rows).")


if __name__ == "__main__":
    main()
