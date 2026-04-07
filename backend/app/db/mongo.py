from __future__ import annotations

"""
MongoDB connection utilities (Motor).

We keep the client as a global singleton for hackathon simplicity. In production,
this can be refactored behind a repository layer with dependency injection.
"""

from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import get_settings


_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


def connect_mongo() -> None:
    settings = get_settings()
    global _client, _db
    _client = AsyncIOMotorClient(settings.MONGODB_URI)
    _db = _client[settings.MONGODB_DB]


def close_mongo() -> None:
    global _client, _db
    if _client is not None:
        _client.close()
    _client = None
    _db = None


def mongo_db() -> AsyncIOMotorDatabase:
    if _db is None:
        raise RuntimeError("MongoDB is not connected")
    return _db


async def ping_mongo() -> bool:
    """
    Best-effort connectivity check.
    """

    try:
        db = mongo_db()
        await db.command({"ping": 1})
        return True
    except Exception:
        return False


def building_collection() -> Any:
    """
    Collection accessor (untyped for hackathon speed).
    """

    return mongo_db()["buildings"]

