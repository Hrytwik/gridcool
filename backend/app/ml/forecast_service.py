from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd

from app.core.config import Settings
from app.ml.model_io import (
    load_artifacts,
    load_to_stress_score,
    resolve_backend_root,
    stress_context_from_metadata,
)

ArtifactStatus = Literal["loaded", "missing", "error"]
ForecastSource = Literal["ml", "sim_fallback"]


def _season_from_month(month: int) -> str:
    if month in (4, 5, 6):
        return "summer"
    if month in (7, 8, 9):
        return "monsoon"
    if month in (12, 1, 2):
        return "winter"
    return "shoulder"


def _indian_holiday_dates(year: int) -> set[date]:
    fixed = {
        date(year, 1, 26),
        date(year, 8, 15),
        date(year, 10, 2),
        date(year, 12, 25),
    }
    approx = {
        date(year, 3, 14),
        date(year, 10, 21),
        date(year, 4, 14),
        date(year, 5, 1),
    }
    return fixed | approx


def resolve_data_csv(settings: Settings) -> Path:
    p = Path(settings.ML_DATA_CSV)
    if p.is_absolute():
        return p
    root = resolve_backend_root()
    parts = p.parts
    if len(parts) >= 2 and parts[0] == "backend":
        return root / Path(*parts[1:])
    return root / p


def month_hour_weather_means(df: pd.DataFrame) -> pd.DataFrame:
    cols = ["temp_c", "feels_like_c", "humidity", "wind_speed", "cloud_cover"]
    g = df.groupby(["month", "hour_of_day"], as_index=False)[cols].mean()
    return g


def _row_weather(means: pd.DataFrame, month: int, hour: int, fallback: pd.Series) -> dict[str, float]:
    sub = means[(means["month"] == month) & (means["hour_of_day"] == hour)]
    if sub.empty:
        return {c: float(fallback[c]) for c in ["temp_c", "feels_like_c", "humidity", "wind_speed", "cloud_cover"]}
    row = sub.iloc[0]
    return {c: float(row[c]) for c in ["temp_c", "feels_like_c", "humidity", "wind_speed", "cloud_cover"]}


def _feature_vector_order(
    *,
    ts_utc: pd.Timestamp,
    w: dict[str, float],
    lag_24: float,
    lag_1: float,
    roll3: float,
    roll24: float,
    feature_names: list[str],
) -> np.ndarray:
    ts_ist = ts_utc.tz_convert("Asia/Kolkata")
    month = int(ts_ist.month)
    hod = int(ts_ist.hour)
    dow = int(ts_ist.weekday())
    season = _season_from_month(month)
    is_weekend = 1 if dow >= 5 else 0
    is_holiday = 1 if ts_ist.date() in _indian_holiday_dates(ts_ist.year) else 0
    temp = w["temp_c"]
    hw = 1 if temp >= 35.0 else 0
    ev = 1 if (hw == 1 or temp >= 38.0 or (temp >= 36.0 and w["humidity"] < 38.0)) else 0

    season_cols = {
        "season_summer": 1 if season == "summer" else 0,
        "season_monsoon": 1 if season == "monsoon" else 0,
        "season_winter": 1 if season == "winter" else 0,
        "season_shoulder": 1 if season == "shoulder" else 0,
    }

    values: dict[str, float] = {
        "hour_of_day": float(hod),
        "day_of_week": float(dow),
        "month": float(month),
        "is_weekend": float(is_weekend),
        "is_holiday": float(is_holiday),
        "season_summer": float(season_cols["season_summer"]),
        "season_monsoon": float(season_cols["season_monsoon"]),
        "season_winter": float(season_cols["season_winter"]),
        "season_shoulder": float(season_cols["season_shoulder"]),
        "temp_c": w["temp_c"],
        "feels_like_c": w["feels_like_c"],
        "humidity": w["humidity"],
        "wind_speed": w["wind_speed"],
        "cloud_cover": w["cloud_cover"],
        "heatwave_flag": float(hw),
        "event_flag": float(ev),
        "load_mw_lag_24h": float(lag_24),
        "lag_1h": float(lag_1),
        "roll_mean_3h": float(roll3),
        "roll_mean_24h": float(roll24),
    }
    arr = np.array([[values[name] for name in feature_names]], dtype=np.float64)
    return arr


def _multi_step_forecast(
    model: object,
    feature_names: list[str],
    df: pd.DataFrame,
    means: pd.DataFrame,
    horizon: int,
) -> list[float]:
    df = df.sort_values("timestamp").reset_index(drop=True)
    last = df.iloc[-1]
    last_ts = pd.to_datetime(last["timestamp"], utc=True)
    tail: list[float] = df["load_mw"].astype(float).iloc[-168:].tolist()

    preds: list[float] = []
    for h in range(1, horizon + 1):
        ts = last_ts + timedelta(hours=h)
        ts_ist = ts.tz_convert("Asia/Kolkata")
        month = int(ts_ist.month)
        hod = int(ts_ist.hour)
        w = _row_weather(means, month, hod, last)

        lag_1 = tail[-1]
        lag_24 = tail[-24] if len(tail) >= 24 else float(last["load_mw_lag_24h"])
        if math.isnan(lag_24):
            lag_24 = lag_1
        win3 = tail[-3:] if len(tail) >= 3 else tail
        win24 = tail[-24:] if len(tail) >= 24 else tail
        roll3 = float(np.mean(win3))
        roll24 = float(np.mean(win24))

        X = _feature_vector_order(
            ts_utc=ts,
            w=w,
            lag_24=lag_24,
            lag_1=lag_1,
            roll3=roll3,
            roll24=roll24,
            feature_names=feature_names,
        )
        p = float(model.predict(X)[0])
        preds.append(p)
        tail.append(p)
    return preds


@dataclass
class ForecastResult:
    generated_at: str
    horizon_hours: list[int]
    forecast_load_mw: list[float]
    forecast_stress_score: list[float]
    peak_hour_index: int
    peak_in_minutes: int
    artifact_status: ArtifactStatus
    source: ForecastSource


def _fallback_from_engine(engine: Any, now: datetime, horizon: int) -> tuple[list[float], list[float], dict[str, Any]]:
    loads = engine.hourly_predicted_mw_fallback(now=now, horizon=horizon)
    stresses = [float(engine._stress_score(m)) for m in loads]
    ctx: dict[str, Any] = {}
    return loads, stresses, ctx


def run_forecast(
    *,
    settings: Settings,
    now: datetime,
    horizon: int | None = None,
    engine: Any | None = None,
) -> ForecastResult:
    h = int(horizon if horizon is not None else settings.ML_FORECAST_HORIZON_HOURS)
    h = max(1, min(48, h))
    gen = datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    def _pack(
        loads: list[float],
        stresses: list[float],
        artifact_status: ArtifactStatus,
        source: ForecastSource,
    ) -> ForecastResult:
        peak_idx = int(np.argmax(stresses)) if stresses else 0
        hrs = list(range(1, h + 1))
        return ForecastResult(
            generated_at=gen,
            horizon_hours=hrs,
            forecast_load_mw=loads,
            forecast_stress_score=stresses,
            peak_hour_index=peak_idx,
            peak_in_minutes=int(hrs[peak_idx] * 60) if hrs else 0,
            artifact_status=artifact_status,
            source=source,
        )

    csv_path = resolve_data_csv(settings)
    if engine is not None:
        fb_loads, fb_stress, _ = _fallback_from_engine(engine, now, h)
    else:
        fb_loads = [5000.0 + 50.0 * i for i in range(h)]
        fb_stress = [min(100.0, max(0.0, (x - 4700.0) / 20.0)) for x in fb_loads]

    if not csv_path.is_file():
        return _pack(fb_loads, fb_stress, "missing", "sim_fallback")

    try:
        df = pd.read_csv(csv_path)
        if len(df) < 48:
            return _pack(fb_loads, fb_stress, "error", "sim_fallback")
        model, meta, st = load_artifacts(settings.ML_ARTIFACT_DIR)
        if model is None or meta is None or st != "loaded":
            return _pack(fb_loads, fb_stress, st if st in ("missing", "error") else "error", "sim_fallback")

        fn = meta.get("feature_names")
        if not isinstance(fn, list) or not all(isinstance(x, str) for x in fn):
            return _pack(fb_loads, fb_stress, "error", "sim_fallback")

        means = month_hour_weather_means(df)
        stress_ctx = stress_context_from_metadata(meta)
        preds = _multi_step_forecast(
            model=model,
            feature_names=fn,
            df=df,
            means=means,
            horizon=h,
        )
        stresses = [load_to_stress_score(x, stress_ctx) for x in preds]
        return _pack(preds, stresses, "loaded", "ml")
    except Exception:
        if engine is not None:
            fb_loads, fb_stress, _ = _fallback_from_engine(engine, now, h)
        return _pack(fb_loads, fb_stress, "error", "sim_fallback")


def forecast_to_dict(fr: ForecastResult) -> dict[str, object]:
    return {
        "generated_at": fr.generated_at,
        "horizon_hours": fr.horizon_hours,
        "forecast_load_mw": fr.forecast_load_mw,
        "forecast_stress_score": fr.forecast_stress_score,
        "peak_hour_index": fr.peak_hour_index,
        "peak_in_minutes": fr.peak_in_minutes,
        "artifact_status": fr.artifact_status,
        "source": fr.source,
    }


def interpolate_hourly_to_15min(
    *,
    now: datetime,
    hourly_loads: list[float],
    hours_ahead: int = 6,
    load_now: float | None = None,
) -> list[tuple[datetime, float]]:
    """
    15-minute series for the next `hours_ahead` hours. `hourly_loads[k]` is load at
    now + (k+1)h. `load_now` anchors t=now; if omitted, uses `hourly_loads[0]`.
    """

    steps = int(hours_ahead * 4) + 1
    out: list[tuple[datetime, float]] = []
    if not hourly_loads:
        return out

    ln = float(load_now) if load_now is not None else float(hourly_loads[0])
    use = hourly_loads[: int(max(1, hours_ahead))]
    knots: list[float] = [ln] + [float(x) for x in use]

    def level_at_fh(fh: float) -> float:
        fh = max(0.0, float(fh))
        max_h = float(len(knots) - 1)
        if fh >= max_h:
            return float(knots[-1])
        i = int(math.floor(fh))
        frac = fh - i
        a = knots[i]
        b = knots[i + 1]
        return float(a + (b - a) * frac)

    for j in range(steps):
        minutes = j * 15
        fh = minutes / 60.0
        ts = now + timedelta(minutes=minutes)
        out.append((ts, level_at_fh(fh)))
    return out


def ml_window_stress_score(fr: ForecastResult) -> float:
    """
    Near-term stress for 60–120 min ahead: average of 1h and 2h buckets (indices 0 and 1).
    """

    s = fr.forecast_stress_score
    if len(s) >= 2:
        return float((s[0] + s[1]) / 2.0)
    if s:
        return float(s[0])
    return 0.0
