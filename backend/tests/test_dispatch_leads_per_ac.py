from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.simulation.seed import seeded_buildings_chennai
from app.simulation.sim_engine import DemoSimEngine
from app.thermal.fingerprint import ConstructionType, dispatch_lead_minutes_by_type


def test_dispatch_lead_mapping() -> None:
    assert dispatch_lead_minutes_by_type("top_floor") == 35
    assert dispatch_lead_minutes_by_type("corner_unit") == 50
    assert dispatch_lead_minutes_by_type("ground_floor") == 85
    assert dispatch_lead_minutes_by_type("mid_floor") == 90


def test_trigger_dispatch_sets_per_ac_schedule_from_construction_type() -> None:
    tz = ZoneInfo("Asia/Kolkata")
    now = datetime(2026, 6, 15, 12, 0, tzinfo=tz)
    engine = DemoSimEngine(tz=tz, seeded_buildings=seeded_buildings_chennai())
    engine.trigger_dispatch(now=now, minutes=90, trigger_type="manual")
    peak = engine._dispatch_peak_at
    assert peak is not None
    for b in engine.seeded_buildings:
        for ac in engine._acs_by_building.get(b.building_id, []):
            fp = engine._fingerprints_by_ac.get(ac["ac_id"])
            assert fp is not None
            ctype: ConstructionType = fp.construction_type
            lead = dispatch_lead_minutes_by_type(ctype)
            start = engine._dispatch_schedule_at_by_ac.get(ac["ac_id"])
            assert start is not None
            delta_min = (peak - start).total_seconds() / 60.0
            assert abs(delta_min - lead) < 0.5, f"{ac['ac_id']} {ctype} expected {lead} got {delta_min}"
