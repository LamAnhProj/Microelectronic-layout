"""Locate an RCO trim code at two educational PVT stress points.

The search samples endpoints and a binary-search path plus nearby codes. It
does not prove full-code monotonicity or a qualified operating envelope.
Usage: python3 -m examples.rco.corner_trim gf180
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import platform
import re
import shutil
import subprocess
import uuid

from examples.rco.run import (CONFIG, PDK_ROOT, PIN, ROOT, build_netlist,
                              late_cycle_metrics, model_hash, sha256,
                              simulation_stop_us)


SOURCE = Path(__file__).resolve()
TARGET = 512_000
STRESS = {"fast_cold_high_v": {"temperature_c": 0, "supply_scale": 1.05},
          "slow_hot_low_v": {"temperature_c": 85, "supply_scale": 0.95}}


def corner_deck(process: str, code: int, name: str) -> tuple[str, float, str]:
    if process not in CONFIG or name not in STRESS or not 0 <= code <= 511:
        raise ValueError("Unknown process, corner, or trim code")
    settings = STRESS[name]
    nominal = CONFIG[process]["supply"]
    supply = round(nominal * settings["supply_scale"], 6)
    style = "balanced" if process == "gf180" else "binary"
    deck = build_netlist(process, code, True, "pdk", style)
    pdk = PDK_ROOT / CONFIG[process]["pdk"]
    corner = ("ff_ll" if name.startswith("fast") else "ss_hh") if process == "sky130" else ("ff" if name.startswith("fast") else "ss")
    replacements = [(".temp 25", f".temp {settings['temperature_c']}"),
                    (f"VDD vdd 0 {nominal}", f"VDD vdd 0 {supply}"),
                    (f"V(n1)={nominal}", f"V(n1)={supply}"),
                    (f"VAL={nominal/2}", f"VAL={supply/2}")]
    if process == "sky130":
        replacements.append((f"sky130.lib.spice tt", f"sky130.lib.spice {corner}"))
    else:
        for kind in ("typical", "res_typical", "mimcap_typical"):
            target = corner if kind == "typical" else kind.replace("typical", corner)
            replacements.append((f"sm141064.ngspice {kind}",
                                 f"sm141064.ngspice {target}"))
    for before, after in replacements:
        if before not in deck:
            raise RuntimeError(f"Expected netlist setting is missing: {before}")
        deck = deck.replace(before, after)
    return deck, supply, corner


def simulate(process: str, code: int, name: str, folder: Path,
             model_digest: str) -> dict:
    deck_text, supply, model_corner = corner_deck(process, code, name)
    subdir = folder / name / f"code_{code:03d}"
    subdir.mkdir(parents=True, exist_ok=True)
    deck = subdir / "rco.spice"
    deck.write_text(deck_text)
    command = [shutil.which("ngspice") or "ngspice", "-b", str(deck)]
    result = subprocess.run(command, cwd=subdir, text=True, capture_output=True,
                            timeout=240)
    log = subdir / "ngspice.log"
    log.write_text(result.stdout + result.stderr)
    trace = subdir / "waveform.dat"
    if result.returncode or not trace.is_file():
        raise RuntimeError(f"ngspice failed for {process} {name} code {code}: {log}")
    metrics = late_cycle_metrics(trace, supply,
                                 simulation_stop_us(code, True, "pdk") / 2)
    row = {"code": code, "frequency_hz": metrics["frequency_hz"],
           "frequency_error_pct": 100 * (metrics["frequency_hz"] / TARGET - 1),
           "duty_cycle_pct": metrics["duty_cycle_pct"],
           "period_spread_pct": metrics["period_spread_pct"],
           "supply_v": supply, "temperature_c": STRESS[name]["temperature_c"],
           "model_corner": model_corner, "host": {"system": "Darwin", "arch": "arm64"},
           "pdk_pin": PIN, "model_tree_sha256": model_digest,
           "source_sha256": sha256(SOURCE), "netlist_sha256": sha256(deck),
           "waveform_sha256": sha256(trace), "log_sha256": sha256(log),
           "run": str(subdir)}
    (subdir / "report.json").write_text(json.dumps(row, indent=2) + "\n")
    return row


def search(process: str) -> dict:
    if process not in CONFIG:
        raise ValueError("Choose sky130 or gf180")
    if (platform.system(), platform.machine()) != ("Darwin", "arm64"):
        raise RuntimeError("Corner trim checks must run on the native arm64 Mac")
    folder = ROOT / "runs" / "rco" / "corner_trim" / process / str(uuid.uuid4())
    folder.mkdir(parents=True, mode=0o700)
    model_digest = model_hash(PDK_ROOT / CONFIG[process]["pdk"] / "libs.tech" / "ngspice")
    scenarios = {}
    for name in STRESS:
        measured = {}
        def at(code: int) -> dict:
            if code not in measured:
                measured[code] = simulate(process, code, name, folder, model_digest)
            return measured[code]
        low, high = 0, 511
        at(low); at(high)
        while high - low > 1:
            middle = (low + high) // 2
            if at(middle)["frequency_hz"] > TARGET:
                low = middle
            else:
                high = middle
        for code in range(max(0, low-2), min(511, high+2)+1):
            at(code)
        best = min(measured.values(), key=lambda row: abs(row["frequency_error_pct"]))
        scenarios[name] = {"best_sampled": best, "sampled": [measured[k] for k in sorted(measured)],
                           "endpoint_bracketed": ((measured[0]["frequency_hz"]-TARGET) *
                                                  (measured[511]["frequency_hz"]-TARGET) <= 0)}
        (folder / "report.json").write_text(json.dumps({"process": process,
            "status": "partial", "scenarios": scenarios,
            "scope": "Native Mac PDK schematic PVT search; binary-search path and neighboring codes only, no full-corner monotonicity or layout PEX."}, indent=2) + "\n")
    result = {"process": process, "status": "measured", "scenarios": scenarios,
              "target_hz": TARGET, "host": {"system": "Darwin", "arch": "arm64"},
              "pdk_pin": PIN, "source_sha256": sha256(SOURCE), "model_tree_sha256": model_digest,
              "scope": "Educational fast/cold/+5%V and slow/hot/-5%V open-PDK schematic tests; sampled trim path, no full-corner monotonicity, mismatch, RCO PEX, or foundry qualification.",
              "run": str(folder)}
    (folder / "report.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("process", choices=CONFIG)
    args = parser.parse_args()
    report = search(args.process)
    print(json.dumps({name: {"best_sampled": value["best_sampled"],
                             "endpoint_bracketed": value["endpoint_bracketed"],
                             "sampled_codes": [row["code"] for row in value["sampled"]]}
                      for name, value in report["scenarios"].items()}, indent=2))
