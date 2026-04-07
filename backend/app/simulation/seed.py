from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SeedBuilding:
    building_id: str
    name: str
    lat: float
    lng: float
    ac_count: int


def seeded_buildings_chennai() -> list[SeedBuilding]:
    """
    Demo-mode building seed: 10 buildings around Chennai.
    Coordinates are plausible (not exact) and distributed across the city.
    """

    return [
        SeedBuilding("bld_001", "Phoenix Tech Park – Velachery", 12.9815, 80.2180, 22),
        SeedBuilding("bld_002", "Tidel Park Annex – Taramani", 12.9892, 80.2462, 18),
        SeedBuilding("bld_003", "Nungambakkam Residency Cluster", 13.0604, 80.2429, 14),
        SeedBuilding("bld_004", "Guindy Industrial Estate – Block C", 13.0109, 80.2142, 20),
        SeedBuilding("bld_005", "OMR Bayview Apartments – Thoraipakkam", 12.9419, 80.2346, 16),
        SeedBuilding("bld_006", "Adyar Riverside Towers", 13.0067, 80.2574, 12),
        SeedBuilding("bld_007", "Anna Nagar Central Complex", 13.0863, 80.2101, 15),
        SeedBuilding("bld_008", "Perungudi Logistics Hub", 12.9658, 80.2430, 19),
        SeedBuilding("bld_009", "Egmore Heritage Hotels Strip", 13.0721, 80.2618, 11),
        SeedBuilding("bld_010", "Mylapore Mixed-Use Block", 13.0339, 80.2692, 13),
    ]

