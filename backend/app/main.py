from __future__ import annotations

import asyncio
import contextlib
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.db.mongo import close_mongo, connect_mongo, ping_mongo
from app.routers.buildings import router as buildings_router
from app.routers.demo import router as demo_router
from app.routers.thermal import router as thermal_router
from app.state import demo_engine, ws_manager


settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    App lifecycle.

    Starts a background broadcaster that pushes a unified "dashboard snapshot"
    to all connected websocket clients every `WS_BROADCAST_INTERVAL_SECONDS`.
    """

    stop_event = asyncio.Event()

    async def _broadcast_loop() -> None:
        while not stop_event.is_set():
            now = datetime.now(tz=demo_engine.tz)
            snapshot = demo_engine.get_dashboard_snapshot(now=now)
            await ws_manager.broadcast_json(snapshot)
            await asyncio.sleep(settings.WS_BROADCAST_INTERVAL_SECONDS)

    # Best-effort DB connection for Phase 1 (works with Atlas or local Mongo).
    connect_mongo()

    task = asyncio.create_task(_broadcast_loop())
    try:
        yield
    finally:
        stop_event.set()
        task.cancel()
        with contextlib.suppress(Exception):
            await task
        close_mongo()


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)
app.include_router(demo_router)
app.include_router(buildings_router)
app.include_router(thermal_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "app": settings.APP_NAME, "mongo_ok": str(await ping_mongo()).lower()}


@app.websocket("/ws/dashboard")
async def ws_dashboard(websocket: WebSocket):
    """
    Real-time dashboard stream.

    The frontend expects a single JSON payload ("snapshot") roughly every 10 seconds:
    stress score, credits, buildings, event feed, and demand curves.
    """

    await ws_manager.connect(websocket)
    try:
        # Immediately push a fresh snapshot on connect for snappy UI.
        now = datetime.now(tz=demo_engine.tz)
        await websocket.send_json(demo_engine.get_dashboard_snapshot(now=now))

        while True:
            # We don't need client messages for Phase 1; keep the socket alive.
            # If a client sends anything, just ignore it.
            await websocket.receive_text()
    except Exception:
        pass
    finally:
        await ws_manager.disconnect(websocket)

