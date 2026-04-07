from __future__ import annotations

"""
Buildings API (Phase 1).

In DEMO_MODE, source of truth is the in-memory simulation engine, but we also
persist any new enrollments to MongoDB when available so the system feels real.
"""

from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.db.mongo import building_collection, ping_mongo
from app.models.building import Building
from app.state import demo_engine


router = APIRouter(prefix="/buildings", tags=["buildings"])
settings = get_settings()


@router.get("")
async def list_buildings() -> list[Building]:
    # For Phase 1, serve the demo fleet (includes newly enrolled buildings).
    return [
        Building(
            building_id=b.building_id,
            name=b.name,
            lat=b.lat,
            lng=b.lng,
            ac_count=b.ac_count,
        )
        for b in demo_engine.seeded_buildings
    ]


@router.get("/{building_id}")
async def get_building(building_id: str) -> Building:
    b = next((x for x in demo_engine.seeded_buildings if x.building_id == building_id), None)
    if not b:
        raise HTTPException(status_code=404, detail="Building not found")
    return Building(
        building_id=b.building_id,
        name=b.name,
        lat=b.lat,
        lng=b.lng,
        ac_count=b.ac_count,
    )


async def persist_enrollment_if_possible(building: Building) -> None:
    """
    Best-effort: store the enrollment in MongoDB if reachable.
    """

    if not await ping_mongo():
        return
    try:
        col = building_collection()
        await col.update_one(
            {"building_id": building.building_id},
            {"$set": building.model_dump()},
            upsert=True,
        )
    except Exception:
        # best-effort; demo must never crash
        return

