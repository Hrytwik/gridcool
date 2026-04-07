from __future__ import annotations

"""
Thermal Fingerprinting (Phase 1).

This module infers per-building thermal characteristics passively from MirAIe AC telemetry.
No surveys. No manual building configuration.

--------------------------------------------------------------------------
PHASE 2 HANDOFF (do not delete)

Current thermal fingerprinting state summary:
- Demo-mode fingerprints are deterministic per `building_id` via a stable seed.
- New enrollments enter a short "calibrating" window (demo: 8 seconds) and then
  transition to "fingerprinted".
- Rule-based construction-type classifier outputs one of:
  top_floor, ground_floor, corner_unit, mid_floor
- Flexibility window is computed from an RC model fit (first-order thermal model).

Exact snapshot contract additions made:
- Each building in the websocket `snapshot.buildings[]` includes an additional nested object:
  `thermal_fingerprint` with fields:
    flexibility_window_minutes: float
    construction_type: 'top_floor' | 'ground_floor' | 'corner_unit' | 'mid_floor'
    thermal_mass_class: 'low' | 'medium' | 'high'
    calibration_status: 'calibrating' | 'fingerprinted'
    calibration_progress_pct: int
  All existing snapshot fields remain intact.

What Phase 2 ML should replace:
- Replace `classify_construction_type(...)` (rule-based) with a trained model using
  real MirAIe telemetry (XGBoost classifier is a good baseline).
- Replace `fit_rc_model(...)` (heuristics) with a more robust estimator and uncertainty bounds.

Confirmed Phase 2 decisions:
- Stress threshold: ≥80, peak 60–120 min ahead
- Credits rate: ₹8/kWh
- Forecast granularity: hourly predicted, interpolated to 15-min for chart
- Model target: load_mw → calibrated stress score (Option B)
- Manual stress trigger must work independently of real clock
--------------------------------------------------------------------------
"""

import hashlib
import math
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Sequence


CalibrationStatus = Literal["calibrating", "fingerprinted"]
ThermalMassClass = Literal["low", "medium", "high"]
ConstructionType = Literal["top_floor", "ground_floor", "corner_unit", "mid_floor"]


@dataclass(frozen=True)
class ThermalFingerprint:
    building_id: str
    rc_r: float
    rc_c: float
    flexibility_window_minutes: float
    thermal_mass_class: ThermalMassClass
    construction_type: ConstructionType
    calibration_status: CalibrationStatus
    calibration_progress_pct: int
    last_updated: datetime


@dataclass(frozen=True)
class TelemetryPoint:
    ts: datetime
    compressor_on: bool
    setpoint_c: float
    ambient_c: float
    runtime_minutes: float


def _stable_int_seed(s: str) -> int:
    # stable across processes/runs (unlike Python's hash()).
    h = hashlib.sha256(s.encode("utf-8")).hexdigest()[:8]
    return int(h, 16)


def fit_rc_model(telemetry_stream: Sequence[TelemetryPoint]) -> tuple[float, float]:
    """
    Fit a first-order RC thermal model using simple heuristics.

    Model intuition:
    - R (thermal resistance) is inferred from steady-state delta between ambient and setpoint.
      Better insulation => higher R.
    - C (thermal capacitance) is inferred from time-to-target and rebound rate.
      Higher thermal mass => higher C.
    """

    if not telemetry_stream:
        return 1.0, 1.0

    # Steady-state delta proxy (ambient - setpoint) during compressor on windows.
    deltas: list[float] = []
    runtimes: list[float] = []
    for p in telemetry_stream:
        if p.compressor_on:
            deltas.append(max(0.1, p.ambient_c - p.setpoint_c))
            runtimes.append(max(0.1, p.runtime_minutes))

    avg_delta = sum(deltas) / len(deltas) if deltas else 3.5
    avg_runtime = sum(runtimes) / len(runtimes) if runtimes else 18.0

    # Heuristic scaling chosen to produce plausible demo ranges.
    r = min(6.0, max(0.8, 2.2 + (avg_delta - 3.0) * 0.35))
    c = min(6.5, max(0.8, 1.4 + (avg_runtime - 12.0) * 0.12))
    return round(r, 3), round(c, 3)


def compute_flexibility_window(telemetry_stream: Sequence[TelemetryPoint]) -> float:
    """
    Computes flexibility window in minutes.

    Formula (from brief):
      flexibility_minutes = R * C * ln((T_comfort_limit - T_ambient) / (T_setpoint - T_ambient))

    Notes:
    - We choose a comfort limit based on a ±1.5°C comfort band around the typical setpoint.
    - The log term is clamped to avoid math domain errors in demo.
    """

    if not telemetry_stream:
        return 45.0

    r, c = fit_rc_model(telemetry_stream)

    # Use the most recent point as "current conditions".
    last = telemetry_stream[-1]
    t_ambient = float(last.ambient_c)
    t_set = float(last.setpoint_c)

    # Comfort band: allow indoor to drift +1.5°C above setpoint.
    t_comfort_limit = t_set + 1.5

    num = (t_comfort_limit - t_ambient)
    den = (t_set - t_ambient)

    # Ensure positive ratio for ln().
    ratio = (num / den) if den != 0 else 1.2
    ratio = max(1.05, min(8.0, ratio))

    minutes = (r * c) * math.log(ratio) * 22.0
    return float(round(max(10.0, min(90.0, minutes)), 1))


def classify_construction_type(
    rebound_rate: float, time_to_target: float, tod_variance: float
) -> ConstructionType:
    """
    Rule-based classifier (Phase 1) for Indian construction typologies.

    Inputs:
    - rebound_rate: °C/hour after compressor off (higher => heats faster)
    - time_to_target: minutes to reach setpoint from higher ambient (higher => more mass / worse cooling)
    - tod_variance: variability in rebound by time of day (solar gain proxy)
    """

    # Top floor: highest rebound, lowest mass.
    if rebound_rate >= 3.2 and time_to_target <= 18:
        return "top_floor"

    # Corner unit: rebound varies significantly (solar gain + exposed walls).
    if tod_variance >= 1.2 and rebound_rate >= 2.2:
        return "corner_unit"

    # Ground floor: moderate rebound but longer time-to-target (more mass).
    if rebound_rate <= 2.0 and time_to_target >= 24:
        return "ground_floor"

    # Default: mid-floor (best insulated, stable).
    return "mid_floor"


def _thermal_mass_class_from_c(c: float) -> ThermalMassClass:
    if c >= 4.6:
        return "high"
    if c >= 2.8:
        return "medium"
    return "low"


def generate_demo_fingerprint(building_id: str, seed: int) -> ThermalFingerprint:
    """
    Deterministic fingerprint generator for demo mode.
    Same building_id -> same construction type + RC values + flexibility window.
    """

    # Create a stable seed from building_id + seed.
    s = _stable_int_seed(f"{building_id}:{seed}")
    # Map to pseudo "telemetry-derived" features.
    rebound_rate = 1.6 + (s % 170) / 100.0  # 1.6 .. 3.29
    time_to_target = 14.0 + ((s // 7) % 220) / 10.0  # 14 .. 36
    tod_variance = 0.4 + ((s // 17) % 160) / 100.0  # 0.4 .. 1.99

    ctype = classify_construction_type(rebound_rate, time_to_target, tod_variance)

    # Construction-type biased RC values (plausible ranges).
    if ctype == "top_floor":
        r = 1.4 + ((s // 3) % 30) / 100.0  # ~1.4..1.69
        c = 1.3 + ((s // 5) % 40) / 100.0  # ~1.3..1.69
        flex = 18.0 + ((s // 11) % 70) / 10.0  # 18..24.9
    elif ctype == "corner_unit":
        r = 1.8 + ((s // 3) % 50) / 100.0
        c = 2.0 + ((s // 5) % 70) / 100.0
        flex = 22.0 + ((s // 11) % 140) / 10.0  # 22..35.9
    elif ctype == "ground_floor":
        r = 2.6 + ((s // 3) % 80) / 100.0
        c = 3.4 + ((s // 5) % 90) / 100.0
        flex = 35.0 + ((s // 11) % 160) / 10.0  # 35..50.9
    else:  # mid_floor
        r = 3.2 + ((s // 3) % 110) / 100.0
        c = 4.2 + ((s // 5) % 120) / 100.0
        flex = 50.0 + ((s // 11) % 260) / 10.0  # 50..75.9

    mass = _thermal_mass_class_from_c(c)
    now = datetime.now()

    return ThermalFingerprint(
        building_id=building_id,
        rc_r=round(float(r), 3),
        rc_c=round(float(c), 3),
        flexibility_window_minutes=round(float(flex), 1),
        thermal_mass_class=mass,
        construction_type=ctype,
        calibration_status="fingerprinted",
        calibration_progress_pct=100,
        last_updated=now,
    )


def dispatch_lead_minutes_by_type(construction_type: ConstructionType) -> int:
    """
    Phase 1 dispatch timing by construction type (brief requirement).
    """

    return {
        "top_floor": 35,
        "corner_unit": 50,
        "ground_floor": 85,
        "mid_floor": 90,
    }[construction_type]

