from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Literal, NotRequired, TypedDict

from app.core.config import get_settings
from app.integrations.miraie_adapter import DemoMiraieAdapter
from app.services.credits_ledger import schedule_append_credits_ledger_entry, schedule_dispatch_event
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
    thermal_summary: dict[str, object]


class ACUnit(TypedDict):
    ac_id: str
    building_id: str
    unit_label: str


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
    ml: NotRequired[dict[str, object] | None]


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
    _acs_by_building: dict[str, list[ACUnit]] = field(default_factory=dict)
    _fingerprints_by_ac: dict[str, ThermalFingerprint] = field(default_factory=dict)
    _calibration_started_at_by_ac: dict[str, datetime] = field(default_factory=dict)
    _dispatch_peak_at: datetime | None = None
    _dispatch_schedule_at: dict[str, datetime] = field(default_factory=dict)
    _dispatch_schedule_at_by_ac: dict[str, datetime] = field(default_factory=dict)
    _events: list[str] = None  # type: ignore[assignment]
    _last_tick: datetime | None = None
    miraie_adapter: Any = field(default_factory=DemoMiraieAdapter)
    _credits_inr_by_building: dict[str, float] = field(default_factory=dict)
    _last_auto_dispatch_at: datetime | None = None

    def __post_init__(self) -> None:
        self._events = []
        for b in self.seeded_buildings:
            self._seed_building_acs(b)

    def can_auto_dispatch(self, *, now: datetime, cooldown_minutes: int) -> bool:
        if self._last_auto_dispatch_at is None:
            return True
        return (now - self._last_auto_dispatch_at).total_seconds() >= float(cooldown_minutes) * 60.0

    def _construction_distribution(self, building: SeedBuilding) -> dict[ConstructionType, int]:
        seed = int(building.building_id.split("_")[-1]) if "_" in building.building_id else 42
        n = max(1, int(building.ac_count))
        # Deterministic archetypes to avoid "everything mid-floor" bias.
        # This creates realistic diversity across a small demo fleet.
        archetypes: list[dict[ConstructionType, float]] = [
            {"mid_floor": 0.30, "top_floor": 0.40, "corner_unit": 0.20, "ground_floor": 0.10},  # top-heavy tower
            {"mid_floor": 0.25, "top_floor": 0.15, "corner_unit": 0.45, "ground_floor": 0.15},  # corner-heavy block
            {"mid_floor": 0.20, "top_floor": 0.10, "corner_unit": 0.20, "ground_floor": 0.50},  # ground-heavy low rise
            {"mid_floor": 0.55, "top_floor": 0.15, "corner_unit": 0.20, "ground_floor": 0.10},  # mixed tower
            {"mid_floor": 0.45, "top_floor": 0.25, "corner_unit": 0.20, "ground_floor": 0.10},  # warm roof load
        ]
        profile = archetypes[seed % len(archetypes)]

        counts: dict[ConstructionType, int] = {
            "top_floor": int(round(n * profile["top_floor"])),
            "ground_floor": int(round(n * profile["ground_floor"])),
            "corner_unit": int(round(n * profile["corner_unit"])),
            "mid_floor": int(round(n * profile["mid_floor"])),
        }

        total = sum(counts.values())
        if total > n:
            # Trim from the most over-represented categories first.
            for ctype in sorted(counts.keys(), key=lambda k: counts[k], reverse=True):
                if total <= n:
                    break
                if counts[ctype] > 0:
                    counts[ctype] -= 1
                    total -= 1
        elif total < n:
            # Fill remaining slots deterministically.
            fill_order: list[ConstructionType] = ["mid_floor", "top_floor", "corner_unit", "ground_floor"]
            i = 0
            while total < n:
                counts[fill_order[i % len(fill_order)]] += 1
                total += 1
                i += 1

        # Ensure each type appears at least once when building size allows.
        if n >= 8:
            for ctype in ("top_floor", "ground_floor", "corner_unit"):
                if counts[ctype] == 0:
                    counts[ctype] = 1
                    donor = max(("mid_floor", "top_floor", "corner_unit", "ground_floor"), key=lambda k: counts[k])
                    if donor != ctype and counts[donor] > 1:
                        counts[donor] -= 1
        return counts

    def _seed_building_acs(self, building: SeedBuilding, *, now: datetime | None = None, calibrating: bool = False) -> None:
        dist = self._construction_distribution(building)
        ctype_order: list[ConstructionType] = []
        for ctype in ("mid_floor", "top_floor", "corner_unit", "ground_floor"):
            ctype_order.extend([ctype] * dist[ctype])
        ctype_order = ctype_order[: building.ac_count]
        if len(ctype_order) < building.ac_count:
            ctype_order.extend(["mid_floor"] * (building.ac_count - len(ctype_order)))

        acs: list[ACUnit] = []
        for i in range(building.ac_count):
            ac_id = f"{building.building_id}_ac_{i + 1:03d}"
            acs.append(
                {
                    "ac_id": ac_id,
                    "building_id": building.building_id,
                    "unit_label": f"Unit {i + 1:02d}",
                }
            )
            if calibrating:
                if now:
                    self._calibration_started_at_by_ac[ac_id] = now
                self._fingerprints_by_ac.pop(ac_id, None)
            else:
                fp = generate_demo_fingerprint(
                    ac_id=ac_id,
                    building_id=building.building_id,
                    seed=42 + i,
                    forced_type=ctype_order[i],
                )
                self._fingerprints_by_ac[ac_id] = fp
                self._calibration_started_at_by_ac.pop(ac_id, None)
        self._acs_by_building[building.building_id] = acs

    def enroll_building(self, *, name: str, lat: float, lng: float, ac_count: int, now: datetime) -> SeedBuilding:
        """
        Demo-mode enrollment: adds a building to the in-memory fleet.
        """

        next_id = f"bld_{len(self.seeded_buildings) + 1:03d}"
        b = SeedBuilding(next_id, name, float(lat), float(lng), int(ac_count))
        self.seeded_buildings.append(b)
        # Start calibration for all AC units immediately (demo: resolves in ~8 seconds).
        self._seed_building_acs(b, now=now, calibrating=True)
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

    def trigger_dispatch(
        self,
        *,
        now: datetime,
        minutes: int = 90,
        trigger_type: Literal["manual", "auto"] = "manual",
        peak_in_minutes: int | None = None,
        stress_at_trigger: float | None = None,
    ) -> None:
        """
        Start dispatch (manual operator or auto-orchestrator). Per-AC pre-cool times use construction type leads.
        """

        if not self._dispatch_active:
            self._dispatch_active = True
            self._dispatch_until = now + timedelta(minutes=int(minutes))
            # Peak time is assumed 60–120 minutes ahead (Phase 2 will use ML peak time).
            self._dispatch_peak_at = now + timedelta(minutes=75)
            self._dispatch_schedule_at = {}
            self._dispatch_schedule_at_by_ac = {}
            label = "Auto" if trigger_type == "auto" else "Grid"
            self._events.insert(0, f"{now.strftime('%H:%M')} — {label} — dispatch triggered (pre-cooling)")
            self._events.insert(0, f"{now.strftime('%H:%M')} — MirAIe fleet — setpoint -2°C for enrolled buildings")
            # Schedule construction-type-aware pre-cooling start times per AC.
            for b in self.seeded_buildings:
                starts: list[datetime] = []
                for ac in self._acs_by_building.get(b.building_id, []):
                    fp = self._get_or_create_fingerprint(ac_id=ac["ac_id"], building_id=b.building_id, now=now)
                    ctype: ConstructionType = fp.construction_type if fp else "mid_floor"
                    lead = dispatch_lead_minutes_by_type(ctype)
                    peak_at = self._dispatch_peak_at or (now + timedelta(minutes=75))
                    start_at = peak_at - timedelta(minutes=lead)
                    starts.append(start_at)
                    self._dispatch_schedule_at_by_ac[ac["ac_id"]] = start_at
                peak_at = self._dispatch_peak_at or (now + timedelta(minutes=75))
                self._dispatch_schedule_at[b.building_id] = min(starts) if starts else (peak_at - timedelta(minutes=90))
            # MirAIe adapter: best-effort precool command per AC (demo: deterministic ack).
            for b in self.seeded_buildings:
                for ac in self._acs_by_building.get(b.building_id, []):
                    try:
                        self.miraie_adapter.send_precool(ac["ac_id"], -2.0)
                    except Exception:
                        pass
            # Queue per-building acknowledgements over the next ~20 seconds.
            self._pending_acks = {}
            for idx, b in enumerate(self.seeded_buildings):
                self._pending_acks[b.building_id] = now + timedelta(seconds=2 + idx * 2)
            del self._events[30:]

            if trigger_type == "auto":
                self._last_auto_dispatch_at = now

            pk = int(peak_in_minutes) if peak_in_minutes is not None else 90
            st = float(stress_at_trigger) if stress_at_trigger is not None else 82.0
            schedule_dispatch_event(
                ts=now,
                trigger_type=trigger_type,
                peak_in_minutes=pk,
                stress_score=st,
            )

    def _finalize_dispatch(self, *, now: datetime) -> None:
        if not self._dispatch_active:
            return
        self._dispatch_active = False
        self._dispatch_until = None
        for b in self.seeded_buildings:
            for ac in self._acs_by_building.get(b.building_id, []):
                try:
                    self.miraie_adapter.restore_setpoint(ac["ac_id"])
                except Exception:
                    pass
        self._events.insert(0, f"{now.strftime('%H:%M')} — Dispatch ended — returning setpoints to normal")
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

    def _get_or_create_fingerprint(self, *, ac_id: str, building_id: str, now: datetime) -> ThermalFingerprint | None:
        """
        Returns a fingerprint if building exists. For new buildings, computes it after
        calibration window (demo: 8 seconds). Always deterministic per building_id.
        """

        if not any(b.building_id == building_id for b in self.seeded_buildings):
            return None
        if not any(ac["ac_id"] == ac_id for ac in self._acs_by_building.get(building_id, [])):
            return None

        fp = self._fingerprints_by_ac.get(ac_id)
        started = self._calibration_started_at_by_ac.get(ac_id)

        # If no calibration start, treat as already fingerprinted demo building.
        if started is None:
            if fp is None:
                fp = generate_demo_fingerprint(ac_id=ac_id, building_id=building_id, seed=42)
                self._fingerprints_by_ac[ac_id] = fp
            return fp

        elapsed = (now - started).total_seconds()
        if elapsed < 8.0:
            return None

        # Create deterministic fingerprint via simulated telemetry.
        seed = int(ac_id.split("_")[-1]) if "_" in ac_id else 42
        # Use deterministic construction type from generator itself.
        demo_fp = generate_demo_fingerprint(ac_id=ac_id, building_id=building_id, seed=seed)
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
            ac_id=ac_id,
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

        self._fingerprints_by_ac[ac_id] = fp2
        self._calibration_started_at_by_ac.pop(ac_id, None)
        self._events.insert(
            0,
            f"{now.strftime('%H:%M:%S')} — AC {ac_id} fingerprinted — {demo_fp.construction_type.replace('_', ' ').title()} — {flex:.0f} min flexibility",
        )
        del self._events[30:]
        return fp2

    def get_ac_fingerprint(self, *, building_id: str, ac_id: str, now: datetime) -> dict[str, object] | None:
        fp = self._get_or_create_fingerprint(ac_id=ac_id, building_id=building_id, now=now)
        started = self._calibration_started_at_by_ac.get(ac_id)

        if fp is None and started is None:
            if not any(b.building_id == building_id for b in self.seeded_buildings):
                return None
            return None

        if fp is None:
            progress = int(min(99, max(0, ((now - started).total_seconds() / 8.0) * 100))) if started else 0
            return {
                "ac_id": ac_id,
                "building_id": building_id,
                "floor_position": "mid_floor",
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
            "ac_id": fp.ac_id,
            "building_id": fp.building_id,
            "floor_position": fp.construction_type,
            "rc_r": fp.rc_r,
            "rc_c": fp.rc_c,
            "flexibility_window_minutes": fp.flexibility_window_minutes,
            "thermal_mass_class": fp.thermal_mass_class,
            "construction_type": fp.construction_type,
            "calibration_status": fp.calibration_status,
            "calibration_progress_pct": fp.calibration_progress_pct,
            "last_updated": fp.last_updated.isoformat(),
        }

    def _building_thermal_summary(self, *, building_id: str, enrolled_kw: float, now: datetime) -> dict[str, object]:
        acs = self._acs_by_building.get(building_id, [])
        fps = [self.get_ac_fingerprint(building_id=building_id, ac_id=ac["ac_id"], now=now) for ac in acs]
        fps2 = [x for x in fps if x is not None]
        if not fps2:
            return {
                "dominant_type": "mid_floor",
                "weighted_flexibility_minutes": 45.0,
                "type_breakdown": {
                    "top_floor": {"count": 0, "avg_flexibility_minutes": 0.0},
                    "ground_floor": {"count": 0, "avg_flexibility_minutes": 0.0},
                    "corner_unit": {"count": 0, "avg_flexibility_minutes": 0.0},
                    "mid_floor": {"count": 0, "avg_flexibility_minutes": 0.0},
                },
                "fingerprinted_ac_count": 0,
                "calibrating_ac_count": 0,
            }

        type_totals: dict[str, tuple[int, float]] = {
            "top_floor": (0, 0.0),
            "ground_floor": (0, 0.0),
            "corner_unit": (0, 0.0),
            "mid_floor": (0, 0.0),
        }
        for x in fps2:
            ct = str(x.get("construction_type", "mid_floor"))
            c, s = type_totals.get(ct, (0, 0.0))
            type_totals[ct] = (c + 1, s + float(x.get("flexibility_window_minutes", 45.0)))

        dominant_type = max(type_totals.items(), key=lambda kv: kv[1][0])[0]
        unit_kw = enrolled_kw / max(1, len(fps2))
        weighted = sum(float(x.get("flexibility_window_minutes", 45.0)) * unit_kw for x in fps2) / max(
            enrolled_kw, 0.0001
        )
        breakdown = {
            k: {
                "count": c,
                "avg_flexibility_minutes": round((s / c), 1) if c > 0 else 0.0,
            }
            for k, (c, s) in type_totals.items()
        }
        fingerprinted = sum(1 for x in fps2 if x.get("calibration_status") == "fingerprinted")
        calibrating = sum(1 for x in fps2 if x.get("calibration_status") == "calibrating")
        return {
            "dominant_type": dominant_type,
            "weighted_flexibility_minutes": round(weighted, 1),
            "type_breakdown": breakdown,
            "fingerprinted_ac_count": fingerprinted,
            "calibrating_ac_count": calibrating,
        }

    def get_thermal_fleet_summary(self, *, now: datetime) -> dict[str, object]:
        fps2 = []
        for b in self.seeded_buildings:
            for ac in self._acs_by_building.get(b.building_id, []):
                fp = self.get_ac_fingerprint(building_id=b.building_id, ac_id=ac["ac_id"], now=now)
                if fp is not None:
                    fps2.append(fp)
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
        for ac in self._acs_by_building.get(building_id, []):
            ac_id = ac["ac_id"]
            self._fingerprints_by_ac.pop(ac_id, None)
            self._calibration_started_at_by_ac[ac_id] = now - timedelta(seconds=8)  # demo: instant on next tick
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

    def hourly_predicted_mw_fallback(self, *, now: datetime, horizon: int) -> list[float]:
        """
        Hour-ahead predicted MW using the same synthetic demand physics as the demo curve
        (used by `/ml/predict` and ML runtime fallback).
        """

        out: list[float] = []
        for h in range(1, max(1, int(horizon)) + 1):
            ts = now + timedelta(hours=h)
            base = self._base_demand_mw(ts)
            temp_c, _ = self._sim_temperature(ts)
            temp_boost = (temp_c - 28.0) * 55.0
            out.append(float(base + temp_boost))
        return out

    def _maybe_trigger_demo_event(self, now: datetime, stress_score: int) -> None:
        """
        Phase 1 storyboard dispatch when ML is off; Phase 2 auto-dispatch uses the scheduler when ML is on.
        """

        settings = get_settings()
        if not settings.USE_ML_FORECAST:
            is_demo_time = (now.hour == 17 and now.minute >= 45) or (now.hour == 18)
            should_dispatch = is_demo_time or stress_score >= 75

            if should_dispatch and not self._dispatch_active:
                self.trigger_dispatch(now=now, minutes=90, trigger_type="manual")

        if self._dispatch_active and self._dispatch_until and now >= self._dispatch_until:
            self._finalize_dispatch(now=now)

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
        delta_inr = kwh * rate_inr_per_kwh
        self._credits_inr += delta_inr

        total_kw = sum(b.ac_count * 1.4 for b in self.seeded_buildings) or 1.0
        schedule_append_credits_ledger_entry(
            ts=now,
            building_id=None,
            delta_inr=delta_inr,
            cumulative_inr=float(self._credits_inr),
            dispatch_active=True,
            source="dispatch_accrual",
        )
        for b in self.seeded_buildings:
            share = (b.ac_count * 1.4) / total_kw
            b_delta = delta_inr * share
            bid = b.building_id
            prev = self._credits_inr_by_building.get(bid, 0.0)
            cum_b = prev + b_delta
            self._credits_inr_by_building[bid] = cum_b
            schedule_append_credits_ledger_entry(
                ts=now,
                building_id=bid,
                delta_inr=b_delta,
                cumulative_inr=cum_b,
                dispatch_active=True,
                source="dispatch_accrual",
            )

    def get_dashboard_snapshot(self, now: datetime) -> DashboardSnapshot:
        """
        Produce a single payload for the frontend. This is the canonical real-time contract for Phase 1.
        """

        settings = get_settings()
        temperature_c, heat_index_c = self._sim_temperature(now)

        # Forecast curve for next 6 hours at 15-minute intervals.
        points: list[DemandPoint] = []
        estimated_kw_reduction = 0.0

        enrolled_kw_total = 0.0
        for b in self.seeded_buildings:
            # A rough AC capacity estimate: 1.4 kW per unit average.
            enrolled_kw_total += b.ac_count * 1.4

        # Reduction is visible during peak window and scales with AC-level pre-cooling activation.
        total_acs = sum(len(self._acs_by_building.get(b.building_id, [])) for b in self.seeded_buildings)
        active_acs = 0
        if self._dispatch_active:
            for b in self.seeded_buildings:
                for ac in self._acs_by_building.get(b.building_id, []):
                    start_at = self._dispatch_schedule_at_by_ac.get(ac["ac_id"])
                    if start_at and now >= start_at:
                        active_acs += 1
        building_frac = (active_acs / max(1, total_acs)) if self._dispatch_active else 0.0
        if self._dispatch_active:
            estimated_kw_reduction = round(enrolled_kw_total * 0.22 * max(0.15, building_frac), 1)

        ml_block: dict[str, object] | None = None
        fr = None
        if settings.USE_ML_FORECAST:
            try:
                from app.ml.forecast_cache import get_cached_forecast, set_cached_forecast
                from app.ml.forecast_service import (
                    interpolate_hourly_to_15min,
                    resolve_data_csv,
                    run_forecast,
                )

                fr = get_cached_forecast()
                if fr is None:
                    fr = run_forecast(
                        settings=settings,
                        now=now,
                        horizon=settings.ML_FORECAST_HORIZON_HOURS,
                        engine=self,
                    )
                    set_cached_forecast(fr)
                load_now: float
                try:
                    import pandas as pd

                    pcsv = resolve_data_csv(settings)
                    if pcsv.is_file():
                        df_tail = pd.read_csv(pcsv)
                        load_now = float(pd.to_numeric(df_tail["load_mw"], errors="coerce").iloc[-1])
                    else:
                        load_now = float(self._base_demand_mw(now) + (temperature_c - 28.0) * 55.0)
                except Exception:
                    load_now = float(self._base_demand_mw(now) + (temperature_c - 28.0) * 55.0)

                hourly_slice = fr.forecast_load_mw[:6] if len(fr.forecast_load_mw) >= 6 else list(fr.forecast_load_mw)
                pairs = interpolate_hourly_to_15min(
                    now=now,
                    hourly_loads=hourly_slice,
                    hours_ahead=6,
                    load_now=load_now,
                )
                for i, (ts, pred) in enumerate(pairs):
                    predicted = float(pred)
                    actual = predicted * (0.995 + 0.01 * math.sin(i / 3.5))
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
                ml_block = {
                    "enabled": True,
                    "source": fr.source,
                    "artifact_status": fr.artifact_status,
                    "last_refresh_ts": fr.generated_at,
                }
            except Exception:
                fr = None
                points = []
                ml_block = {
                    "enabled": True,
                    "source": "sim_fallback",
                    "artifact_status": "error",
                    "last_refresh_ts": now.astimezone().isoformat(),
                }

        if not points:
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

        if fr is not None:
            from app.ml.forecast_service import ml_window_stress_score

            stress_score = int(round(ml_window_stress_score(fr)))
        else:
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
            is_precooling = False
            if self._dispatch_active:
                for ac in self._acs_by_building.get(b.building_id, []):
                    t0 = self._dispatch_schedule_at_by_ac.get(ac["ac_id"])
                    if t0 and now >= t0:
                        is_precooling = True
                        break
            last_action = "PRECOOLING" if is_precooling else None
            summary = self._building_thermal_summary(building_id=b.building_id, enrolled_kw=enrolled_kw, now=now)
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
                    "thermal_summary": summary,
                }
            )

        # Add a small heartbeat event occasionally so feed feels alive.
        if now.second < 2:
            self._events.insert(0, f"{now.strftime('%H:%M:%S')} — Telemetry — dashboard snapshot updated")
            del self._events[30:]

        snap: DashboardSnapshot = {
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
        if ml_block is not None:
            snap["ml"] = ml_block
        return snap

