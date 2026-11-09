"""Run a bounded native transient sweep of the RCO's trim word.

Usage: python3 examples/rco/sweep_trim.py gf180 195 225 --workers 2
The per-code waveform/log/netlist reports remain under ignored runs/rco/.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import uuid

from run import BANK_STYLES, CONFIG, ROOT, run, sha256


def sweep(process: str, first: int, last: int, *, workers: int = 2,
          bank_style: str = "binary") -> dict:
    if process not in CONFIG or not (0 <= first <= last <= 511):
        raise ValueError("Choose a PDK and a bounded code interval within 0–511")
    if bank_style not in BANK_STYLES:
        raise ValueError("Unknown bank style")
    with ThreadPoolExecutor(max_workers=workers) as pool:
        reports = list(pool.map(lambda code: run(process, code, True, "pdk",
                                                 "generated", bank_style),
                                range(first, last + 1)))
    failures = [{"code": r["code"], "error": r.get("error", "unknown")}
                for r in reports if r["status"] != "simulated"]
    points = [{"code": r["code"], "frequency_hz": r["measurements"]["frequency_hz"],
               "period_spread_pct": r["measurements"]["period_spread_pct"],
               "duty_cycle_pct": r["measurements"]["duty_cycle_pct"],
               "core_supply_power_w": r["measurements"]["core_supply_power_w"],
               "run_id": Path(r["run"]).name,
               "report_sha256": sha256(Path(r["run"]) / "report.json")}
              for r in reports if r["status"] == "simulated"]
    reversed_steps = [{"from": a["code"], "to": b["code"],
                       "frequency_increase_hz": b["frequency_hz"] - a["frequency_hz"]}
                      for a, b in zip(points, points[1:])
                      if b["code"] == a["code"] + 1 and
                      b["frequency_hz"] >= a["frequency_hz"]]
    best = min(points, key=lambda x: abs(x["frequency_hz"] - 512000)) if points else None
    folder = ROOT / "runs" / "rco" / "sweeps" / str(uuid.uuid4())
    folder.mkdir(parents=True, mode=0o700)
    result = {"status": "measured" if not failures else "partial",
              "process": process, "bank_style": bank_style,
              "first_code": first, "last_code": last,
              "target_hz": 512000, "points": points,
              "reversed_steps": reversed_steps, "failures": failures,
              "best": best,
              "scope": "Native Mac nominal transient sweep, 25 °C, PDK MOS/MIM/resistor models; no layout, LVS, PEX, or PVT guarantee.",
              "run": str(folder)}
    (folder / "report.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("process", choices=CONFIG)
    parser.add_argument("first", type=int)
    parser.add_argument("last", type=int)
    parser.add_argument("--workers", type=int, choices=(1, 2, 3), default=2)
    parser.add_argument("--bank-style", choices=BANK_STYLES, default="binary")
    args = parser.parse_args()
    result = sweep(args.process, args.first, args.last, workers=args.workers,
                   bank_style=args.bank_style)
    print(json.dumps({key: value for key, value in result.items() if key != "points"}, indent=2))
