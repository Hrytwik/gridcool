from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import asyncio

from app.db.mongo import mongo_db, ping_mongo

logger = logging.getLogger(__name__)


async def append_credits_ledger_entry(
    *,
    ts: datetime,
    building_id: str | None,
    delta_inr: float,
    cumulative_inr: float,
    dispatch_active: bool,
    source: str,
) -> None:
    if not await ping_mongo():
        return
    try:
        db = mongo_db()
        doc: dict[str, Any] = {
            "ts": ts,
            "building_id": building_id,
            "delta_inr": float(delta_inr),
            "cumulative_inr": float(cumulative_inr),
            "dispatch_active": bool(dispatch_active),
            "source": source,
        }
        await db["credits_ledger"].insert_one(doc)
    except Exception:
        logger.debug("credits_ledger write skipped", exc_info=True)


async def append_dispatch_event(
    *,
    ts: datetime,
    trigger_type: str,
    peak_in_minutes: int,
    stress_score: float,
) -> None:
    if not await ping_mongo():
        return
    try:
        db = mongo_db()
        await db["dispatch_events"].insert_one(
            {
                "ts": ts,
                "trigger_type": trigger_type,
                "peak_in_minutes": int(peak_in_minutes),
                "stress_score": float(stress_score),
            }
        )
    except Exception:
        logger.debug("dispatch_events write skipped", exc_info=True)


def utc_now() -> datetime:
    return datetime.now(tz=timezone.utc)


def schedule_append_credits_ledger_entry(
    *,
    ts: datetime,
    building_id: str | None,
    delta_inr: float,
    cumulative_inr: float,
    dispatch_active: bool,
    source: str,
) -> None:
    async def _go() -> None:
        await append_credits_ledger_entry(
            ts=ts,
            building_id=building_id,
            delta_inr=delta_inr,
            cumulative_inr=cumulative_inr,
            dispatch_active=dispatch_active,
            source=source,
        )

    try:
        asyncio.get_running_loop().create_task(_go())
    except RuntimeError:
        pass


def schedule_dispatch_event(
    *,
    ts: datetime,
    trigger_type: str,
    peak_in_minutes: int,
    stress_score: float,
) -> None:
    async def _go() -> None:
        await append_dispatch_event(
            ts=ts,
            trigger_type=trigger_type,
            peak_in_minutes=peak_in_minutes,
            stress_score=stress_score,
        )

    try:
        asyncio.get_running_loop().create_task(_go())
    except RuntimeError:
        pass
