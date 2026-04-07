from __future__ import annotations

"""
Shared, in-memory state for the GridCool backend.

Hackathon-friendly: single-process demo mode keeps a simulation engine and websocket manager in memory.
When we deploy, we can swap these for DB-backed state.
"""

from zoneinfo import ZoneInfo

from app.core.config import get_settings
from app.realtime.ws_manager import ConnectionManager
from app.simulation.seed import seeded_buildings_chennai
from app.simulation.sim_engine import DemoSimEngine


settings = get_settings()

ws_manager = ConnectionManager()

# In demo mode we keep all state in-memory (single-process hackathon-safe).
demo_engine = DemoSimEngine(
    tz=ZoneInfo("Asia/Kolkata"),
    seeded_buildings=seeded_buildings_chennai(),
)

