from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.state import demo_engine


REQUIRED_SNAPSHOT_KEYS = frozenset(
    {
        "ts",
        "city",
        "stress_score",
        "severity",
        "temperature_c",
        "heat_index_c",
        "credits_inr",
        "enrolled_kw_total",
        "estimated_kw_reduction",
        "buildings",
        "demand_curve",
        "events",
        "demo",
    }
)


def test_dashboard_snapshot_has_v1_keys() -> None:
    now = datetime.now(tz=ZoneInfo("Asia/Kolkata"))
    snap = demo_engine.get_dashboard_snapshot(now=now)
    keys = set(snap.keys())
    assert REQUIRED_SNAPSHOT_KEYS <= keys
    assert isinstance(snap["buildings"], list)
    assert isinstance(snap["demand_curve"], list)
    assert "demo_mode" in snap["demo"]


def test_ml_key_is_optional() -> None:
    now = datetime.now(tz=ZoneInfo("Asia/Kolkata"))
    snap = demo_engine.get_dashboard_snapshot(now=now)
    assert "ml" not in snap or snap.get("ml") is None or isinstance(snap["ml"], dict)
