"""
In-memory forecast cache refreshed by APScheduler. Snapshot and `/ml/predict` read here
when `USE_ML_FORECAST` is enabled so the UI matches the scheduled refresh cadence.
"""

from __future__ import annotations

import logging
from threading import Lock
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.ml.forecast_service import ForecastResult

logger = logging.getLogger(__name__)

_lock = Lock()
_cached: ForecastResult | None = None


def get_cached_forecast() -> ForecastResult | None:
    with _lock:
        return _cached


def set_cached_forecast(fr: ForecastResult) -> None:
    with _lock:
        global _cached
        _cached = fr


def clear_cache() -> None:
    with _lock:
        global _cached
        _cached = None
