from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Query

from app.core.config import get_settings
from app.ml.forecast_cache import get_cached_forecast
from app.ml.forecast_service import forecast_to_dict, run_forecast
from app.state import demo_engine


router = APIRouter(prefix="/ml", tags=["ml"])


@router.get("/predict")
def ml_predict(
    horizon_hours: int | None = Query(default=None, ge=1, le=48),
) -> dict[str, object]:
    """
    Next-hour load forecast (ML when artifacts exist; otherwise sim fallback). Never raises on ML failure.
    """

    settings = get_settings()
    now = datetime.now(tz=ZoneInfo("Asia/Kolkata"))
    h = horizon_hours if horizon_hours is not None else settings.ML_FORECAST_HORIZON_HOURS
    if settings.USE_ML_FORECAST and h == settings.ML_FORECAST_HORIZON_HOURS:
        cached = get_cached_forecast()
        if cached is not None:
            return forecast_to_dict(cached)
    fr = run_forecast(settings=settings, now=now, horizon=h, engine=demo_engine)
    return forecast_to_dict(fr)
