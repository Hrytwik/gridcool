from __future__ import annotations

"""
Pydantic models for buildings.

In Phase 1 we store a minimal building record. Devices are mocked until the MirAIe
integration is enabled (Phase 2/3).
"""

from pydantic import BaseModel, Field


class BuildingBase(BaseModel):
    name: str = Field(..., min_length=3, max_length=80)
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)
    ac_count: int = Field(..., ge=1, le=250)


class Building(BuildingBase):
    building_id: str

