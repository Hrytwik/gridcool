from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from app.core.config import get_settings
from app.ml.forecast_cache import set_cached_forecast
from app.ml.forecast_service import ForecastResult, run_forecast
from app.state import demo_engine

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")


def refresh_forecast_job_sync() -> None:
    settings = get_settings()
    if not settings.USE_ML_FORECAST:
        return
    try:
        now = datetime.now(tz=IST)
        fr = run_forecast(
            settings=settings,
            now=now,
            horizon=settings.ML_FORECAST_HORIZON_HOURS,
            engine=demo_engine,
        )
        set_cached_forecast(fr)
    except Exception:
        logger.exception("refresh_forecast_job failed; keeping previous cache")


def peak_stress_in_60_120_min(fr: ForecastResult) -> tuple[float, int]:
    """Max stress in forecast hours 1–2 (60–120 min ahead); return (peak, peak_hour_index 0 or 1)."""
    s = fr.forecast_stress_score
    if len(s) >= 2:
        if s[0] >= s[1]:
            return float(s[0]), 0
        return float(s[1]), 1
    if s:
        return float(s[0]), 0
    return 0.0, 0


def auto_dispatch_trigger_job_sync() -> None:
    settings = get_settings()
    if not settings.AUTO_DISPATCH_ENABLED:
        return
    if demo_engine._dispatch_active:
        return
    try:
        now = datetime.now(tz=demo_engine.tz)
        if not settings.USE_ML_FORECAST:
            fr = run_forecast(
                settings=settings,
                now=now,
                horizon=max(12, settings.ML_FORECAST_HORIZON_HOURS),
                engine=demo_engine,
            )
        else:
            from app.ml.forecast_cache import get_cached_forecast

            fr = get_cached_forecast()
            if fr is None:
                fr = run_forecast(
                    settings=settings,
                    now=now,
                    horizon=settings.ML_FORECAST_HORIZON_HOURS,
                    engine=demo_engine,
                )

        peak_stress, peak_idx = peak_stress_in_60_120_min(fr)
        if peak_stress < 80.0:
            return

        if not demo_engine.can_auto_dispatch(now=now, cooldown_minutes=settings.AUTO_DISPATCH_COOLDOWN_MINUTES):
            return

        peak_minutes = int(fr.horizon_hours[peak_idx] * 60) if fr.horizon_hours else 90
        demo_engine.trigger_dispatch(
            now=now,
            minutes=90,
            trigger_type="auto",
            peak_in_minutes=peak_minutes,
            stress_at_trigger=peak_stress,
        )
    except Exception:
        logger.exception("auto_dispatch_trigger_job failed")


async def refresh_forecast_job() -> None:
    await asyncio.to_thread(refresh_forecast_job_sync)


async def auto_dispatch_trigger_job() -> None:
    await asyncio.to_thread(auto_dispatch_trigger_job_sync)
