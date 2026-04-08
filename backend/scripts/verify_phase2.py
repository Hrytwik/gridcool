#!/usr/bin/env python3
"""
Phase 2 verification helper (safe if Mongo is down). Run from `backend/`:

  python scripts/verify_phase2.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


REQUIRED_SNAPSHOT_KEYS = {
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


def main() -> None:
    from datetime import datetime

    from app.core.config import get_settings
    from app.db.mongo import connect_mongo, ping_mongo
    from app.ml.forecast_cache import get_cached_forecast
    from app.ml.forecast_service import forecast_to_dict, run_forecast
    from app.state import demo_engine

    settings = get_settings()
    print("=== GridCool Phase 2 verify ===\n")

    now = datetime.now(tz=demo_engine.tz)
    fr = run_forecast(settings=settings, now=now, horizon=settings.ML_FORECAST_HORIZON_HOURS, engine=demo_engine)
    fd = forecast_to_dict(fr)
    print("Forecast (live run_forecast):")
    print(f"  source: {fd['source']}")
    print(f"  artifact_status: {fd['artifact_status']}")
    print(f"  horizon steps: {len(fd['forecast_load_mw'])}")

    cached = get_cached_forecast()
    print("\nForecast cache (in-memory):")
    print(f"  populated: {cached is not None}")
    if cached:
        print(f"  source: {cached.source}  artifact_status: {cached.artifact_status}")

    snap = demo_engine.get_dashboard_snapshot(now=now)
    keys_ok = REQUIRED_SNAPSHOT_KEYS <= set(snap.keys())
    print("\nSnapshot contract:")
    print(f"  v1 keys present: {'PASS' if keys_ok else 'FAIL'}")

    print("\nAuto-dispatch state:")
    print(f"  last_auto_dispatch_at: {demo_engine._last_auto_dispatch_at}")
    print(f"  cooldown_minutes (config): {settings.AUTO_DISPATCH_COOLDOWN_MINUTES}")

    async def _mongo() -> None:
        connect_mongo()
        ok = await ping_mongo()
        print("\nMongo:")
        print(f"  ping: {'ok' if ok else 'unreachable'}")
        if ok:
            try:
                from app.db.mongo import mongo_db

                db = mongo_db()
                n1 = await db["credits_ledger"].estimated_document_count()
                n2 = await db["dispatch_events"].estimated_document_count()
                print(f"  credits_ledger docs (est.): {n1}")
                print(f"  dispatch_events docs (est.): {n2}")
            except Exception as e:
                print(f"  collection check failed: {e}")

    try:
        asyncio.run(_mongo())
    except Exception as e:
        print("\nMongo:")
        print(f"  error: {e}")

    print("\nDone.")


if __name__ == "__main__":
    main()
