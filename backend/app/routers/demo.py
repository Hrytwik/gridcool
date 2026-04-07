from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.models.building import Building
from app.routers.buildings import persist_enrollment_if_possible
from app.state import demo_engine


router = APIRouter(prefix="/demo", tags=["demo"])
settings = get_settings()


class ForceStressRequest(BaseModel):
    score: int = Field(82, ge=0, le=100)
    minutes: int = Field(10, ge=1, le=180)


class TriggerDispatchRequest(BaseModel):
    minutes: int = Field(90, ge=10, le=180)


class EnrollBuildingRequest(BaseModel):
    name: str = Field(..., min_length=3, max_length=80)
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)
    ac_count: int = Field(..., ge=1, le=250)


@router.post("/force-stress")
def force_stress(req: ForceStressRequest) -> dict[str, object]:
    if not settings.DEMO_MODE:
        raise HTTPException(status_code=403, detail="Not available when DEMO_MODE is off")
    now = datetime.now(tz=ZoneInfo("Asia/Kolkata"))
    demo_engine.force_stress(score=req.score, minutes=req.minutes, now=now)
    return {"ok": True, "forced_score": req.score, "until_minutes": req.minutes}


@router.post("/trigger-dispatch")
def trigger_dispatch(req: TriggerDispatchRequest) -> dict[str, object]:
    if not settings.DEMO_MODE:
        raise HTTPException(status_code=403, detail="Not available when DEMO_MODE is off")
    now = datetime.now(tz=ZoneInfo("Asia/Kolkata"))
    demo_engine.trigger_dispatch(now=now, minutes=req.minutes)
    return {"ok": True, "dispatch_active": True, "minutes": req.minutes}


@router.post("/enroll-building")
async def enroll_building(req: EnrollBuildingRequest) -> dict[str, object]:
    if not settings.DEMO_MODE:
        raise HTTPException(status_code=403, detail="Not available when DEMO_MODE is off")
    now = datetime.now(tz=ZoneInfo("Asia/Kolkata"))
    b = demo_engine.enroll_building(
        name=req.name,
        lat=req.lat,
        lng=req.lng,
        ac_count=req.ac_count,
        now=now,
    )
    building = Building(**b.__dict__)
    await persist_enrollment_if_possible(building)
    return {"ok": True, "building": building.model_dump()}

