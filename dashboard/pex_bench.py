"""Reproducible small-signal and DC benches for a selected extracted inverter."""

from __future__ import annotations

import math
import re


def build_deck(transient_deck: str, analysis: str, supply_v: float,
               bias_v: float | None = None) -> tuple[str, dict]:
    """Retain the selected PDK, extracted inverter and 5 fF load."""
    if analysis not in {"dc", "ac"} or not math.isfinite(supply_v) or supply_v <= 0:
        raise ValueError("Unknown or invalid PEX bench")
    prefix = transient_deck.split(".control\n", 1)[0]
    if prefix == transient_deck:
        raise ValueError("Transient testbench has no control block")
    step_v = 0.01 if supply_v < 2 else 0.02
    if analysis == "dc":
        source = "VIN in 0 DC 0"
        command = f"dc VIN 0 {supply_v:g} {step_v:g}"
        vectors = "v(in) v(out)"
        settings = {"input_start_v": 0, "input_stop_v": supply_v,
                    "input_step_v": step_v, "temperature_c": 25,
                    "output_load_ff": 5}
    else:
        if bias_v is None or not math.isfinite(bias_v) or not 0 < bias_v < supply_v:
            raise ValueError("AC bias must be inside the supply range")
        source = f"VIN in 0 DC {bias_v:.6f} AC 1"
        command = "ac dec 40 1k 100G"
        vectors = "vdb(out) vp(out)"
        settings = {"input_bias_v": round(bias_v, 6), "ac_amplitude_v": 1,
                    "start_hz": 1e3, "stop_hz": 1e11, "points_per_decade": 40,
                    "temperature_c": 25, "output_load_ff": 5}
    prefix, count = re.subn(r"(?m)^VIN in 0 PULSE\([^\n]+$", source, prefix)
    if count != 1:
        raise ValueError("Cannot identify the transient input source")
    deck = (prefix + ".control\nset wr_singlescale\nset wr_vecnames\n"
            + command + "\nwrdata result.txt " + vectors + "\n.endc\n.end\n")
    return deck, settings


def parse_table(content: str) -> list[list[float]]:
    rows = []
    for line in content.splitlines()[1:]:
        fields = line.split()
        if len(fields) != 3:
            continue
        row = [float(field) for field in fields]
        if not all(math.isfinite(value) for value in row):
            raise ValueError("PEX bench produced nonfinite samples")
        rows.append(row)
    if len(rows) < 20 or any(a[0] >= b[0] for a, b in zip(rows, rows[1:])):
        raise ValueError("PEX bench samples are incomplete or unordered")
    return rows


def dc_trip_v(rows: list[list[float]]) -> float:
    """Input voltage where the DC transfer curve crosses VOUT=VIN."""
    for a, b in zip(rows, rows[1:]):
        da, db = a[2] - a[1], b[2] - b[1]
        if da >= 0 >= db and da != db:
            return round(a[1] + (-da) * (b[1] - a[1]) / (db - da), 6)
    raise ValueError("DC transfer curve has no inverter trip point")
