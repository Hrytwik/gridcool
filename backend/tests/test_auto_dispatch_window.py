from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from app.core.config import get_settings
from app.jobs import forecast_scheduler as fs
from app.ml.forecast_cache import clear_cache, set_cached_forecast
from app.ml.forecast_service import ForecastResult
from app.state import demo_engine


def _freeze_scheduler_now(monkeypatch: pytest.MonkeyPatch, ts: datetime) -> None:
    def _now(tz=None):
        if tz is not None:
            return ts if ts.tzinfo == tz else ts.astimezone(tz)
        return ts

    monkeypatch.setattr(fs, "datetime", SimpleNamespace(now=_now))


@pytest.fixture
def reset_engine_dispatch() -> None:
    demo_engine._dispatch_active = False
    demo_engine._dispatch_until = None
    demo_engine._last_auto_dispatch_at = None
    yield
    demo_engine._finalize_dispatch(now=datetime.now(tz=demo_engine.tz))
    demo_engine._dispatch_active = False
    demo_engine._dispatch_until = None
    demo_engine._last_auto_dispatch_at = None


def test_peak_outside_60_120_window_no_trigger(monkeypatch: pytest.MonkeyPatch, reset_engine_dispatch: None) -> None:
    monkeypatch.setenv("USE_ML_FORECAST", "true")
    monkeypatch.setenv("AUTO_DISPATCH_ENABLED", "true")
    get_settings.cache_clear()

    now_ist = datetime(2026, 6, 15, 12, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    _freeze_scheduler_now(monkeypatch, now_ist)

    clear_cache()
    fr = ForecastResult(
        generated_at="2026-01-01T00:00:00Z",
        horizon_hours=[1, 2, 3, 4],
        forecast_load_mw=[5000.0, 5000.0, 5000.0, 5000.0],
        forecast_stress_score=[40.0, 40.0, 90.0, 90.0],
        peak_hour_index=2,
        peak_in_minutes=180,
        artifact_status="loaded",
        source="ml",
    )
    set_cached_forecast(fr)

    fs.auto_dispatch_trigger_job_sync()
    assert demo_engine._dispatch_active is False


def test_peak_in_60_120_triggers_once_and_cooldown(monkeypatch: pytest.MonkeyPatch, reset_engine_dispatch: None) -> None:
    monkeypatch.setenv("USE_ML_FORECAST", "true")
    monkeypatch.setenv("AUTO_DISPATCH_ENABLED", "true")
    get_settings.cache_clear()

    now_ist = datetime(2026, 6, 15, 12, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    _freeze_scheduler_now(monkeypatch, now_ist)

    clear_cache()
    fr = ForecastResult(
        generated_at="2026-01-01T00:00:00Z",
        horizon_hours=[1, 2, 3],
        forecast_load_mw=[8000.0, 8000.0, 8000.0],
        forecast_stress_score=[82.0, 81.0, 50.0],
        peak_hour_index=0,
        peak_in_minutes=60,
        artifact_status="loaded",
        source="ml",
    )
    set_cached_forecast(fr)

    fs.auto_dispatch_trigger_job_sync()
    assert demo_engine._dispatch_active is True

    fs.auto_dispatch_trigger_job_sync()
    assert demo_engine._dispatch_active is True

    demo_engine._finalize_dispatch(now=now_ist)
    assert demo_engine._dispatch_active is False

    fs.auto_dispatch_trigger_job_sync()
    assert demo_engine._dispatch_active is False
