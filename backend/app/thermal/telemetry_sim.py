from __future__ import annotations

"""
Telemetry simulation (Phase 1 demo).

Simulates 72 hours of MirAIe AC telemetry per building. For demo onboarding we
compress the 72h observation window to ~8 seconds, but the underlying generator
still produces a realistic sequence for RC fitting.
"""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Sequence

from app.thermal.fingerprint import ConstructionType, TelemetryPoint


def _daily_temp(hour: float) -> float:
    # Chennai-like diurnal cycle.
    return 29.0 + 4.5 * math.sin(((hour - 8.0) / 24.0) * 2.0 * math.pi)


def _solar_gain(hour: float) -> float:
    # Solar bump around midday; used for corner units.
    return 1.8 * math.exp(-0.5 * ((hour - 13.0) / 2.3) ** 2)


def simulate_telemetry_72h(
    *,
    start: datetime,
    construction_type: ConstructionType,
    seed: int,
    setpoint_c: float = 24.0,
) -> list[TelemetryPoint]:
    """
    Output points at 10-minute intervals for 72 hours.
    """

    points: list[TelemetryPoint] = []
    dt = timedelta(minutes=10)

    # Construction-type parameters.
    if construction_type == "top_floor":
        rebound_per_hour = 3.3
        cycle_on_min = 12
        cycle_off_min = 18
    elif construction_type == "ground_floor":
        rebound_per_hour = 1.6
        cycle_on_min = 20
        cycle_off_min = 28
    elif construction_type == "corner_unit":
        rebound_per_hour = 2.4
        cycle_on_min = 16
        cycle_off_min = 22
    else:  # mid_floor
        rebound_per_hour = 1.3
        cycle_on_min = 22
        cycle_off_min = 30

    # Slight deterministic variation by seed.
    rebound_per_hour *= 0.92 + ((seed % 17) / 100.0)

    t = start
    compressor_on = True
    cycle_elapsed = 0
    cycle_len = cycle_on_min
    ambient = _daily_temp(t.hour)

    for i in range(int((72 * 60) / 10)):
        hour_f = t.hour + t.minute / 60.0

        ambient = _daily_temp(hour_f)
        if construction_type == "corner_unit":
            ambient += _solar_gain(hour_f)

        # Simulated compressor cycling.
        cycle_elapsed += 10
        if compressor_on and cycle_elapsed >= cycle_on_min:
            compressor_on = False
            cycle_elapsed = 0
            cycle_len = cycle_off_min
        elif (not compressor_on) and cycle_elapsed >= cycle_off_min:
            compressor_on = True
            cycle_elapsed = 0
            cycle_len = cycle_on_min

        # Runtime proxy: minutes the compressor has run in this 10-min slice.
        runtime = 10.0 if compressor_on else 0.0

        points.append(
            TelemetryPoint(
                ts=t,
                compressor_on=compressor_on,
                setpoint_c=setpoint_c,
                ambient_c=float(round(ambient, 2)),
                runtime_minutes=runtime,
            )
        )
        t = t + dt

    return points

