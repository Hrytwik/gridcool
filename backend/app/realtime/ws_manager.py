from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from fastapi import WebSocket


@dataclass
class ConnectionManager:
    """
    Tracks active websocket connections and provides fan-out broadcast.
    """

    active_connections: set[WebSocket] = field(default_factory=set)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self.active_connections.add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self.active_connections.discard(websocket)

    async def broadcast_json(self, payload: Any) -> None:
        async with self._lock:
            conns = list(self.active_connections)
        if not conns:
            return

        for ws in conns:
            try:
                await ws.send_json(payload)
            except Exception:
                # best-effort: if a client is gone, drop it
                await self.disconnect(ws)

