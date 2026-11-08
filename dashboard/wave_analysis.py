"""Measure inverter transitions from the actual ngspice traces, in ns and V."""

from __future__ import annotations

import math


def crossing(samples: list[list[float]], column: int, level: float,
             direction: str, after_ns: float, before_ns: float = 4.0) -> float:
    """Interpolate the first threshold crossing in the requested time window."""
    for previous, current in zip(samples, samples[1:]):
        t0, v0 = previous[0], previous[column]
        t1, v1 = current[0], current[column]
        if t1 < after_ns or t0 > before_ns:
            continue
        crossed = v0 < level <= v1 if direction == "rise" else v0 > level >= v1
        if crossed and v1 != v0:
            time = t0 + (level - v0) * (t1 - t0) / (v1 - v0)
            if after_ns <= time <= before_ns:
                return time
    raise ValueError(f"Missing {direction} crossing at {level:g} V")


def analyze_trace(samples: list[list[float]], supply_v: float) -> dict[str, float]:
    """Measure first complete rising/falling input pulse and output response."""
    if len(samples) < 3 or not math.isfinite(supply_v) or supply_v <= 0:
        raise ValueError("Waveform or supply is invalid")
    if any(len(row) != 3 or any(not math.isfinite(value) for value in row)
           for row in samples):
        raise ValueError("Waveform samples are invalid")
    if any(a[0] >= b[0] for a, b in zip(samples, samples[1:])):
        raise ValueError("Waveform time is not increasing")
    half = supply_v / 2
    input_rise = crossing(samples, 1, half, "rise", 0.5)
    input_fall = crossing(samples, 1, half, "fall", input_rise + 0.1)
    output_fall = crossing(samples, 2, half, "fall", input_rise)
    output_rise = crossing(samples, 2, half, "rise", input_fall)
    output_fall_90 = crossing(samples, 2, supply_v * .9, "fall", input_rise)
    output_fall_10 = crossing(samples, 2, supply_v * .1, "fall", output_fall_90)
    output_rise_10 = crossing(samples, 2, supply_v * .1, "rise", input_fall)
    output_rise_90 = crossing(samples, 2, supply_v * .9, "rise", output_rise_10)
    return {
        "tphl_ps": round((output_fall - input_rise) * 1000, 4),
        "tplh_ps": round((output_rise - input_fall) * 1000, 4),
        "fall_90_10_ps": round((output_fall_10 - output_fall_90) * 1000, 4),
        "rise_10_90_ps": round((output_rise_90 - output_rise_10) * 1000, 4),
        "input_rise_ns": round(input_rise, 6),
        "input_fall_ns": round(input_fall, 6),
    }
