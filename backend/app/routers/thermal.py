from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.state import demo_engine


router = APIRouter(prefix="/thermal", tags=["thermal"])
settings = get_settings()


@router.get("/buildings/{building_id}")
def thermal_for_building(building_id: str) -> dict[str, object]:
    building = next((b for b in demo_engine.seeded_buildings if b.building_id == building_id), None)
    if building is None:
        raise HTTPException(status_code=404, detail="Building not found")
    enrolled_kw = round(building.ac_count * 1.4, 1)
    return demo_engine._building_thermal_summary(building_id=building_id, enrolled_kw=enrolled_kw, now=_now_ist())


@router.get("/fleet")
def thermal_for_fleet() -> dict[str, object]:
    return demo_engine.get_thermal_fleet_summary(now=_now_ist())


@router.post("/recalibrate/{building_id}")
def recalibrate(building_id: str) -> dict[str, object]:
    ok = demo_engine.recalibrate(building_id=building_id, now=_now_ist())
    if not ok:
        raise HTTPException(status_code=404, detail="Building not found")
    return {"ok": True}


def _now_ist() -> datetime:
    return datetime.now(tz=ZoneInfo("Asia/Kolkata"))

