from __future__ import annotations

import hashlib
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class MiraieAdapter(Protocol):
    def send_precool(self, ac_id: str, setpoint_delta_c: float) -> dict[str, Any]: ...

    def restore_setpoint(self, ac_id: str) -> dict[str, Any]: ...

    def health(self) -> dict[str, Any]: ...


class DemoMiraieAdapter:
    """
    Deterministic demo MirAIe: no network; simulates command acceptance latency.
    """

    def send_precool(self, ac_id: str, setpoint_delta_c: float) -> dict[str, Any]:
        seed = int(hashlib.sha256(ac_id.encode()).hexdigest()[:8], 16)
        latency_ms = 80 + (seed % 120)
        return {
            "ok": True,
            "latency_ms": latency_ms,
            "ac_id": ac_id,
            "setpoint_delta_c": setpoint_delta_c,
            "mode": "demo",
        }

    def restore_setpoint(self, ac_id: str) -> dict[str, Any]:
        seed = int(hashlib.sha256((ac_id + "restore").encode()).hexdigest()[:8], 16)
        latency_ms = 70 + (seed % 90)
        return {
            "ok": True,
            "latency_ms": latency_ms,
            "ac_id": ac_id,
            "mode": "demo",
        }

    def health(self) -> dict[str, Any]:
        return {"ok": True, "mode": "demo", "adapter": "DemoMiraieAdapter"}


class RealMiraieAdapterStub:
    """
    Production MirAIe seam — inert stub.

    TODO: Configure Panasonic MirAIe API base URL and OAuth / API key from env
    (e.g. `MIRAIE_API_BASE`, `MIRAIE_CLIENT_ID`, `MIRAIE_CLIENT_SECRET`).

    TODO: Implement `send_precool` as authenticated POST to fleet setpoint endpoint
    with body like `{"device_id": ac_id, "delta_c": setpoint_delta_c}`; map response
    to `{"ok": bool, "latency_ms": int, ...}`.

    TODO: Implement `restore_setpoint` to clear temporary offset for `ac_id`.

    No live HTTP calls in hackathon mode — always return a safe placeholder.
    """

    def send_precool(self, ac_id: str, setpoint_delta_c: float) -> dict[str, Any]:
        return {
            "ok": False,
            "latency_ms": 0,
            "ac_id": ac_id,
            "setpoint_delta_c": setpoint_delta_c,
            "mode": "stub",
            "error": "RealMiraieAdapterStub: not wired to Panasonic API",
        }

    def restore_setpoint(self, ac_id: str) -> dict[str, Any]:
        return {
            "ok": False,
            "latency_ms": 0,
            "ac_id": ac_id,
            "mode": "stub",
            "error": "RealMiraieAdapterStub: not wired to Panasonic API",
        }

    def health(self) -> dict[str, Any]:
        return {"ok": False, "mode": "stub", "adapter": "RealMiraieAdapterStub"}
