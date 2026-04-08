from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.core.config import get_settings
from app.state import demo_engine


def test_force_stress_overrides_snapshot_score(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("USE_ML_FORECAST", "false")
    get_settings.cache_clear()

    now = datetime(2026, 6, 15, 14, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    try:
        demo_engine.force_stress(score=95, minutes=30, now=now)
        snap = demo_engine.get_dashboard_snapshot(now=now)
        assert snap["stress_score"] == 95

        later = now + timedelta(minutes=31)
        demo_engine.get_dashboard_snapshot(now=later)
        assert demo_engine._forced_stress_until is None
        assert demo_engine._forced_stress_score is None
    finally:
        demo_engine._forced_stress_until = None
        demo_engine._forced_stress_score = None
