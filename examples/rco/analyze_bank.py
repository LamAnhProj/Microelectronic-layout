"""Measure the RCO bank's mid-bias small-signal capacitance at every trim code.

This is an AC diagnostic of one disconnected bank, not a transient oscillator
measurement or a post-layout extraction. Usage:
    python3 examples/rco/analyze_bank.py gf180 --bank-style binary
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import math
from pathlib import Path
import platform
import shutil
import subprocess
import uuid

from run import CONFIG, PIN, PDK_ROOT, ROOT, build_netlist, model_hash, sha256


SOURCE = Path(__file__).resolve()
FREQUENCY_HZ = 512_000


def bank_deck(process: str, code: int, bank_style: str) -> str:
    lines = build_netlist(process, code, passives="pdk", bank_style=bank_style).splitlines()
    control_start = next(i for i, line in enumerate(lines) if line.startswith("* Static"))
    stage_start = next(i for i, line in enumerate(lines) if line.startswith("* Three inverters"))
    header = lines[:control_start]
    controls = lines[control_start:stage_start]
    bank = [line for line in lines[stage_start:]
            if line.startswith(("XCBASE0 ", "XMAIN0 ", "RBANK0 ",
                                "XSW0_", "XC0_", "RB0_"))]
    if not bank or not any(line.startswith("XCBASE0 ") for line in bank):
        raise ValueError("Stage-zero capacitor bank is missing")
    half_supply = CONFIG[process]["supply"] / 2
    tail = [f"VTEST n0 0 DC {half_supply} AC 1", *bank,
            f".ac lin 1 {FREQUENCY_HZ} {FREQUENCY_HZ}",
            ".control", "run", "set wr_singlescale", "set wr_vecnames",
            "wrdata admittance.dat i(vtest)", "quit", ".endc", ".end"]
    return "\n".join(header + controls + tail) + "\n"


def one_code(process: str, code: int, bank_style: str, folder: Path,
             ngspice: str) -> dict:
    cell = folder / f"code_{code:03d}"
    cell.mkdir()
    deck = cell / "bank.spice"
    deck.write_text(bank_deck(process, code, bank_style))
    result = subprocess.run([ngspice, "-b", str(deck)], cwd=cell,
                            text=True, capture_output=True, timeout=45)
    log = cell / "ngspice.log"
    log.write_text(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError(f"AC code {code} failed; inspect {log}")
    data = cell / "admittance.dat"
    rows = data.read_text().splitlines()
    if len(rows) != 2:
        raise RuntimeError(f"AC code {code} has an ambiguous output")
    fields = rows[1].split()
    if len(fields) != 3 or abs(float(fields[0]) - FREQUENCY_HZ) > 1:
        raise RuntimeError(f"AC code {code} has an invalid frequency row")
    conductance = -float(fields[1])
    capacitance = -float(fields[2]) / (2 * math.pi * FREQUENCY_HZ)
    if not (math.isfinite(capacitance) and capacitance > 0):
        raise RuntimeError(f"AC code {code} has invalid capacitance")
    return {"code": code, "effective_cap_f": capacitance,
            "conductance_s": conductance,
            "netlist_sha256": sha256(deck), "log_sha256": sha256(log),
            "ac_sha256": sha256(data)}


def analyze(process: str, bank_style: str, workers: int = 2) -> dict:
    if process not in CONFIG or bank_style not in ("binary", "guarded"):
        raise ValueError("Choose a process and bank style")
    if (platform.system(), platform.machine()) != ("Darwin", "arm64"):
        raise RuntimeError("This check records native arm64 Mac execution only")
    ngspice = shutil.which("ngspice")
    pdk = PDK_ROOT / CONFIG[process]["pdk"]
    if not ngspice or PIN not in str(pdk.resolve()):
        raise RuntimeError("Pinned PDK or native ngspice is missing")
    folder = ROOT / "runs" / "rco" / "bank_ac" / process / str(uuid.uuid4())
    folder.mkdir(parents=True, mode=0o700)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        points = list(pool.map(lambda code: one_code(process, code, bank_style,
                                                    folder, ngspice), range(512)))
    reversed_steps = [
        {"from": a["code"], "to": b["code"],
         "cap_delta_f": b["effective_cap_f"] - a["effective_cap_f"]}
        for a, b in zip(points, points[1:])
        if b["effective_cap_f"] <= a["effective_cap_f"]]
    report = {"status": "measured", "process": process,
              "bank_style": bank_style, "sample_count": len(points),
              "ac_frequency_hz": FREQUENCY_HZ,
              "bias_v": CONFIG[process]["supply"] / 2,
              "host": {"system": platform.system(), "arch": platform.machine()},
              "pdk_pin": PIN, "model_tree_sha256": model_hash(pdk / "libs.tech" / "ngspice"),
              "source_sha256": sha256(SOURCE),
              "ngspice_version": subprocess.run([ngspice, "--version"],
                                               capture_output=True, text=True).stdout.splitlines()[1].strip(),
              "reversed_cap_steps": reversed_steps,
              "scope": "One stage's mid-supply AC capacitance at 512 kHz; excludes the oscillator, its resistor, charge history, layout, DRC/LVS, and PEX.",
              "points": points, "run": str(folder)}
    (folder / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("process", choices=CONFIG)
    parser.add_argument("--bank-style", choices=("binary", "guarded"), default="binary")
    parser.add_argument("--workers", type=int, choices=(1, 2, 3), default=2)
    args = parser.parse_args()
    result = analyze(args.process, args.bank_style, args.workers)
    print(json.dumps({key: value for key, value in result.items() if key != "points"}, indent=2))
