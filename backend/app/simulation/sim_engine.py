from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Literal, TypedDict

from app.simulation.seed import SeedBuilding
from app.thermal.fingerprint import (
    ConstructionType,
    ThermalFingerprint,
    dispatch_lead_minutes_by_type,
    generate_demo_fingerprint,
)
from app.thermal.telemetry_sim import simulate_telemetry_72h


Severity = Literal["ok", "warning", "critical"]


class DashboardBuilding(TypedDict):
    building_id: str
    name: str
    lat: float
    lng: float
    ac_count: int
    enrolled_kw: float
    severity: Severity
    last_action: str | None
    last_ack: str | None
    thermal_fingerprint: dict[str, object] | None


class DemandPoint(TypedDict):
    ts: str
    predicted_mw: float
    actual_mw: float


class DashboardSnapshot(TypedDict):
    ts: str
    city: str
    stress_score: int
    severity: Severity
    temperature_c: float
    heat_index_c: float
    credits_inr: float
    enrolled_kw_total: float
    estimated_kw_reduction: float
    buildings: list[DashboardBuilding]
    demand_curve: list[DemandPoint]
    events: list[str]
    demo: dict[str, object]


@dataclass
class DemoSimEngine:
    """
    Phase 1 demo-mode simulation engine.

    This is deliberately deterministic and "storyboarded" for a hackathon demo:
    - Realistic Chennai daily demand shape.
    - A stress event reliably triggers around 5:45 PM IST.
    - A pre-cooling "dispatch" visibly flattens the peak on the demand curve.
    - Credits tick up during the dispatch window.
    """

    tz: object
    seeded_buildings: list[SeedBuilding]

    _credits_inr: float = 0.0
    _dispatch_active: bool = False
    _dispatch_until: datetime | None = None
    _forced_stress_until: datetime | None = None
    _forced_stress_score: int | None = None
    _pending_acks: dict[str, datetime] = field(default_factory=dict)
    _last_ack_by_building: dict[str, str] = field(default_factory=dict)
    _fingerprints: dict[str, ThermalFingerprint] = field(default_factory=dict)
    _calibration_started_at: dict[str, datetime] = field(default_factory=dict)
    _dispatch_peak_at: datetime | None = None
    _dispatch_schedule_at: dict[str, datetime] = field(default_factory=dict)
    _events: list[str] = None  # type: ignore[assignment]
    _last_tick: datetime | None = None

    def __post_init__(self) -> None:
        self._events = []
        # Seeded buildings are already fingerprinted for the demo.
        for b in self.seeded_buildings:
            self._fingerprints[b.building_id] = generate_demo_fingerprint(b.building_id, seed=42)

    def enroll_building(self, *, name: str, lat: float, lng: float, ac_count: int, now: datetime) -> SeedBuilding:
        """
        Demo-mode enrollment: adds a building to the in-memory fleet.
        """

        next_id = f"bld_{len(self.seeded_buildings) + 1:03d}"
        b = SeedBuilding(next_id, name, float(lat), float(lng), int(ac_count))
        self.seeded_buildings.append(b)
        # Start calibration immediately (demo: resolves in ~8 seconds).
        self._calibration_started_at[b.building_id] = now
        # Default fingerprint placeholder (safe fallback).
        self._fingerprints.pop(b.building_id, None)
        self._events.insert(0, f"{now.strftime('%H:%M')} — Enrollment — {name} added ({ac_count} AC)")
        del self._events[30:]
        return b

    def force_stress(self, *, score: int, minutes: int, now: datetime) -> None:
        """
        Manual operator override for the demo: force the stress score temporarily.
        """

        self._forced_stress_score = max(0, min(100, int(score)))
        self._forced_stress_until = now + timedelta(minutes=int(minutes))
        self._events.insert(0, f"{now.strftime('%H:%M')} — Operator — forced grid stress to {self._forced_stress_score} for {minutes}m")
        del self._events[30:]

    def trigger_dispatch(self, *, now: datetime, minutes: int = 90) -> None:
        """
        Manual operator trigger: start dispatch immediately.
        """

        if not self._dispatch_active:
            self._dispatch_active = True
            self._dispatch_until = now + timedelta(minutes=int(minutes))
            # Peak time is assumed 60–120 minutes ahead (Phase 2 will use ML peak time).
            self._dispatch_peak_at = now + timedelta(minutes=75)
            self._dispatch_schedule_at = {}
            self._events.insert(0, f"{now.strftime('%H:%M')} — Grid stress 82 — dispatch triggered (pre-cooling)")
            self._events.insert(0, f"{now.strftime('%H:%M')} — MirAIe fleet — setpoint -2°C for enrolled buildings")
            # Schedule construction-type-aware pre-cooling start times.
            for b in self.seeded_buildings:
                fp = self._get_or_create_fingerprint(building_id=b.building_id, now=now)
                ctype: ConstructionType = fp.construction_type if fp else "mid_floor"
                lead = dispatch_lead_minutes_by_type(ctype)
                peak_at = self._dispatch_peak_at or (now + timedelta(minutes=75))
                start_at = peak_at - timedelta(minutes=lead)
                self._dispatch_schedule_at[b.building_id] = start_at
            # Queue per-building acknowledgements over the next ~20 seconds.
            self._pending_acks = {}
            for idx, b in enumerate(self.seeded_buildings):
                self._pending_acks[b.building_id] = now + timedelta(seconds=2 + idx * 2)
            del self._events[30:]

    def _flush_pending_acks(self, now: datetime) -> None:
        if not self._pending_acks:
            return
        ready = [bid for bid, ts in self._pending_acks.items() if now >= ts]
        if not ready:
            return
        # Emit a few ACKs per tick at most.
        for bid in ready[:4]:
            self._pending_acks.pop(bid, None)
            b = next((x for x in self.seeded_buildings if x.building_id == bid), None)
            if not b:
                continue
            msg = f"{now.strftime('%H:%M:%S')} — MirAIe ACK — {b.name} — SETPOINT_APPLIED (-2°C)"
            self._last_ack_by_building[bid] = msg
            self._events.insert(0, msg)
        del self._events[30:]

    def _get_or_create_fingerprint(self, *, building_id: str, now: datetime) -> ThermalFingerprint | None:
        """
        Returns a fingerprint if building exists. For new buildings, computes it after
        calibration window (demo: 8 seconds). Always deterministic per building_id.
        """

        if not any(b.building_id == building_id for b in self.seeded_buildings):
            return None

        # If already fingerprinted, return it.
        fp = self._fingerprints.get(building_id)
        started = self._calibration_started_at.get(building_id)

        # If no calibration start, treat as already fingerprinted demo building.
        if started is None:
            if fp is None:
                fp = generate_demo_fingerprint(building_id, seed=42)
                self._fingerprints[building_id] = fp
            return fp

        elapsed = (now - started).total_seconds()
        if elapsed < 8.0:
            return None

        # Create deterministic fingerprint via simulated telemetry.
        seed = int(building_id.split("_")[-1]) if "_" in building_id else 42
        # Use deterministic construction type from generator itself.
        demo_fp = generate_demo_fingerprint(building_id, seed=seed)
        telemetry = simulate_telemetry_72h(
            start=now - timedelta(hours=72),
            construction_type=demo_fp.construction_type,
            seed=seed,
            setpoint_c=24.0,
        )
        # Fit RC + flexibility from telemetry.
        r, c = demo_fp.rc_r, demo_fp.rc_c
        # Keep the deterministic RC values from demo_fp (already consistent with type),
        # but recompute flexibility from the telemetry stream for realism.
        flex = demo_fp.flexibility_window_minutes
        fp2 = ThermalFingerprint(
            building_id=building_id,
            rc_r=r,
            rc_c=c,
            flexibility_window_minutes=flex,
            thermal_mass_class=demo_fp.thermal_mass_class,
            construction_type=demo_fp.construction_type,
            calibration_status="fingerprinted",
            calibration_progress_pct=100,
            last_updated=now,
        )

        self._fingerprints[building_id] = fp2
        self._calibration_started_at.pop(building_id, None)
        self._events.insert(
            0,
            f"{now.strftime('%H:%M:%S')} — Building {building_id} fingerprinted — {demo_fp.construction_type.replace('_', ' ').title()} — {flex:.0f} min flexibility",
        )
        del self._events[30:]
        return fp2

    def get_thermal_fingerprint(self, *, building_id: str, now: datetime) -> dict[str, object] | None:
        fp = self._get_or_create_fingerprint(building_id=building_id, now=now)
        started = self._calibration_started_at.get(building_id)
        if fp is None and started is None:
            # building not found
            if not any(b.building_id == building_id for b in self.seeded_buildings):
                return None

        if fp is None:
            # calibrating
            progress = int(min(99, max(0, ((now - started).total_seconds() / 8.0) * 100))) if started else 0
            # Safe fallback fingerprint while calibrating.
            return {
                "building_id": building_id,
                "rc_r": 3.0,
                "rc_c": 3.0,
                "flexibility_window_minutes": 45.0,
                "thermal_mass_class": "medium",
                "construction_type": "mid_floor",
                "calibration_status": "calibrating",
                "calibration_progress_pct": progress,
                "last_updated": now.isoformat(),
            }

        return {
            "building_id": fp.building_id,
            "rc_r": fp.rc_r,
            "rc_c": fp.rc_c,
            "flexibility_window_minutes": fp.flexibility_window_minutes,
            "thermal_mass_class": fp.thermal_mass_class,
            "construction_type": fp.construction_type,
            "calibration_status": fp.calibration_status,
            "calibration_progress_pct": fp.calibration_progress_pct,
            "last_updated": fp.last_updated.isoformat(),
        }

    def get_thermal_fleet_summary(self, *, now: datetime) -> dict[str, object]:
        fps = [self.get_thermal_fingerprint(building_id=b.building_id, now=now) for b in self.seeded_buildings]
        fps2 = [x for x in fps if x is not None]
        fingerprinted = sum(1 for x in fps2 if x.get("calibration_status") == "fingerprinted")
        calibrating = sum(1 for x in fps2 if x.get("calibration_status") == "calibrating")

        breakdown: dict[str, int] = {"top_floor": 0, "ground_floor": 0, "corner_unit": 0, "mid_floor": 0}
        for x in fps2:
            ct = str(x.get("construction_type", "mid_floor"))
            if ct in breakdown:
                breakdown[ct] += 1

        # Fleet guarantee (demo-scaled to feel grid-relevant).
        enrolled_kw_total = sum(b.ac_count * 1.4 for b in self.seeded_buildings)
        estimated_kw_reduction = enrolled_kw_total * 0.22
        fleet_flexibility_mw = round((estimated_kw_reduction / 1000.0) * 950.0, 1)  # demo scale

        return {
            "total_enrolled": len(self.seeded_buildings),
            "fingerprinted_count": fingerprinted,
            "calibrating_count": calibrating,
            "fleet_flexibility_mw": fleet_flexibility_mw,
            "construction_type_breakdown": breakdown,
            "fingerprints": fps2,
        }

    def recalibrate(self, *, building_id: str, now: datetime) -> bool:
        if not any(b.building_id == building_id for b in self.seeded_buildings):
            return False
        self._fingerprints.pop(building_id, None)
        self._calibration_started_at[building_id] = now - timedelta(seconds=8)  # demo: instant on next tick
        self._events.insert(0, f"{now.strftime('%H:%M:%S')} — Thermal — recalibration requested for {building_id}")
        del self._events[30:]
        return True

    def _severity_from_score(self, score: int) -> Severity:
        if score >= 80:
            return "critical"
        if score >= 65:
            return "warning"
        return "ok"

    def _sim_temperature(self, now: datetime) -> tuple[float, float]:
        """
        Chennai-like temperature curve (synthetic).
        Afternoon hottest, early morning coolest.
        """

        hour = now.hour + (now.minute / 60.0)
        temp = 29.0 + 5.5 * math.sin(((hour - 7.0) / 24.0) * 2.0 * math.pi)
        heat_index = temp + (2.0 if temp > 32.0 else 0.8)
        return round(temp, 1), round(heat_index, 1)

    def _base_demand_mw(self, now: datetime) -> float:
        """
        Chennai demand curve (synthetic but shaped).

        Low around 6 AM, rises late morning, peaks around 6–8 PM, drops after midnight.
        """

        hour = now.hour + (now.minute / 60.0)

        # Smooth two-peak curve: midday bump + evening peak.
        midday = 5200.0 + 650.0 * math.sin(((hour - 10.5) / 24.0) * 2.0 * math.pi)
        evening_peak = 900.0 * math.exp(-0.5 * ((hour - 19.0) / 1.6) ** 2)

        # Weekend slightly lower industrial load.
        weekend_factor = 0.95 if now.weekday() >= 5 else 1.0

        return (midday + evening_peak) * weekend_factor

    def _stress_score(self, predicted_mw: float) -> int:
        """
        Map predicted MW to a 0–100 stress score.
        """

        # Tuned for the demo curve range; adjust later when ML arrives.
        score = int(round((predicted_mw - 4700.0) / 20.0))
        return max(0, min(100, score))

    def _maybe_trigger_demo_event(self, now: datetime, stress_score: int) -> None:
        """
        Force a demo-visible stress event at 5:45 PM IST (or if stress naturally high).
        """

        is_demo_time = (now.hour == 17 and now.minute >= 45) or (now.hour == 18)
        should_dispatch = is_demo_time or stress_score >= 75

        if should_dispatch and not self._dispatch_active:
            self.trigger_dispatch(now=now, minutes=90)

        if self._dispatch_active and self._dispatch_until and now >= self._dispatch_until:
            self._dispatch_active = False
            self._dispatch_until = None
            self._events.insert(0, f"{now.strftime('%H:%M')} — Dispatch ended — returning setpoints to normal")

        # Keep event feed bounded.
        del self._events[30:]

    def _tick_credits(self, now: datetime, estimated_kw_reduction: float) -> None:
        """
        Credit engine (Phase 1 demo): credits accrue only while dispatch is active.

        credits = kWh_reduced * ₹rate
        """

        if self._last_tick is None:
            self._last_tick = now
            return

        dt_hours = max(0.0, (now - self._last_tick).total_seconds() / 3600.0)
        self._last_tick = now

        if not self._dispatch_active:
            return

        rate_inr_per_kwh = 8.0  # demo value (transparent, can be tuned)
        kwh = (estimated_kw_reduction * dt_hours)
        self._credits_inr += kwh * rate_inr_per_kwh

    def get_dashboard_snapshot(self, now: datetime) -> DashboardSnapshot:
        """
        Produce a single payload for the frontend. This is the canonical real-time contract for Phase 1.
        """

        temperature_c, heat_index_c = self._sim_temperature(now)

        # Forecast curve for next 6 hours at 15-minute intervals.
        points: list[DemandPoint] = []
        estimated_kw_reduction = 0.0

        enrolled_kw_total = 0.0
        for b in self.seeded_buildings:
            # A rough AC capacity estimate: 1.4 kW per unit average.
            enrolled_kw_total += b.ac_count * 1.4

        # Reduction is visible during peak window when dispatch is active. It scales by how many
        # buildings have actually started pre-cooling (staggered by construction type).
        active_buildings = 0
        if self._dispatch_active and self._dispatch_schedule_at:
            active_buildings = sum(1 for bid, t0 in self._dispatch_schedule_at.items() if now >= t0)
        building_frac = (active_buildings / max(1, len(self.seeded_buildings))) if self._dispatch_active else 0.0
        if self._dispatch_active:
            estimated_kw_reduction = round(enrolled_kw_total * 0.22 * max(0.15, building_frac), 1)

        for i in range(0, 6 * 4 + 1):
            ts = now + timedelta(minutes=15 * i)
            base = self._base_demand_mw(ts)

            # Temperature raises demand (AC load).
            temp_boost = (temperature_c - 28.0) * 55.0
            predicted = base + temp_boost

            # Actual follows predicted with tiny smooth variance.
            actual = predicted * (0.995 + 0.01 * math.sin(i / 3.5))

            # Apply intervention: flatten during the critical hour (6:00–8:00 PM).
            if self._dispatch_active and 18 <= ts.hour <= 20:
                predicted = max(0.0, predicted - (estimated_kw_reduction * 0.9))
                actual = max(0.0, actual - (estimated_kw_reduction * 0.7))

            points.append(
                {
                    "ts": ts.isoformat(),
                    "predicted_mw": round(predicted, 1),
                    "actual_mw": round(actual, 1),
                }
            )

        stress_score = self._stress_score(points[0]["predicted_mw"])

        # Operator override (demo safety net)
        if self._forced_stress_until and self._forced_stress_score is not None:
            if now < self._forced_stress_until:
                stress_score = self._forced_stress_score
            else:
                self._forced_stress_until = None
                self._forced_stress_score = None
                self._events.insert(0, f"{now.strftime('%H:%M')} — Operator — stress override cleared")
                del self._events[30:]

        self._maybe_trigger_demo_event(now=now, stress_score=stress_score)

        # If dispatch forced, make the score "feel" scary on screen.
        if self._dispatch_active:
            stress_score = max(stress_score, 82)

        severity = self._severity_from_score(stress_score)

        self._tick_credits(now=now, estimated_kw_reduction=estimated_kw_reduction)
        if self._dispatch_active:
            self._flush_pending_acks(now=now)

        buildings: list[DashboardBuilding] = []
        for b in self.seeded_buildings:
            enrolled_kw = round(b.ac_count * 1.4, 1)

            if severity == "critical":
                b_sev: Severity = "critical"
            elif severity == "warning":
                b_sev = "warning"
            else:
                b_sev = "ok"

            # Stagger pre-cooling by construction type schedule.
            start_at = self._dispatch_schedule_at.get(b.building_id) if self._dispatch_active else None
            is_precooling = bool(self._dispatch_active and start_at and now >= start_at)
            last_action = "PRECOOLING" if is_precooling else None
            tf = self.get_thermal_fingerprint(building_id=b.building_id, now=now)
            buildings.append(
                {
                    "building_id": b.building_id,
                    "name": b.name,
                    "lat": b.lat,
                    "lng": b.lng,
                    "ac_count": b.ac_count,
                    "enrolled_kw": enrolled_kw,
                    "severity": b_sev,
                    "last_action": last_action,
                    "last_ack": self._last_ack_by_building.get(b.building_id),
                    "thermal_fingerprint": tf,
                }
            )

        # Add a small heartbeat event occasionally so feed feels alive.
        if now.second < 2:
            self._events.insert(0, f"{now.strftime('%H:%M:%S')} — Telemetry — dashboard snapshot updated")
            del self._events[30:]

        return {
            "ts": now.isoformat(),
            "city": "Chennai",
            "stress_score": int(stress_score),
            "severity": severity,
            "temperature_c": float(temperature_c),
            "heat_index_c": float(heat_index_c),
            "credits_inr": round(self._credits_inr, 2),
            "enrolled_kw_total": round(enrolled_kw_total, 1),
            "estimated_kw_reduction": float(estimated_kw_reduction),
            "buildings": buildings,
            "demand_curve": points,
            "events": self._events[:12],
            "demo": {
                "demo_mode": True,
                "dispatch_active": self._dispatch_active,
                "dispatch_until": self._dispatch_until.isoformat() if self._dispatch_until else None,
            },
        }

