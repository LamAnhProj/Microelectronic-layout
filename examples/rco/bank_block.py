"""Standalone hierarchical RCO capacitor-bank schematic and isolated bench.

The fan and centroid floorplans share this exact circuit. Until their routed
netlists are extracted, both placements have the same schematic response.
Run on the Mac: .venv/bin/python -m examples.rco.bank_block sky130 146
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import platform
import shutil
import subprocess
import uuid

from examples.rco.run import CONFIG, GF_BALANCED_MIM_WIDTH_UM, PDK_ROOT, PIN, ROOT, model_hash, passive_lines, sha256


SOURCE = Path(__file__).resolve()
AC_HZ = 512_000
PINS = ["rc", "vdd", "main", "mainb"] + [pin for bit in range(9)
                                                for pin in (f"s{bit}", f"s{bit}b")]


def bank_subckt(process: str, bank_style: str) -> str:
    """One stage's base MIM, master gate, nine bit gates, and MIM networks."""
    if process not in CONFIG or bank_style != ("balanced" if process == "gf180" else "binary"):
        raise ValueError("Use SKY binary or GF balanced bank topology")
    c = CONFIG[process]
    if process == "sky130":
        base = "XCBASE rc 0 sky130_fd_pr__cap_mim_m3_2 w=15.7 l=15.7"
    else:
        base = "XCBASE rc 0 cap_mim_2f0_m4m5_noshield c_width=15.6u c_length=15.6u"
    lines = ["* Physical device hierarchy; Rbleed elements below are simulation aids",
             ".subckt BANK_TG a b ctrl ctrlb supply ground wn=1 wp=2",
             f"XN a ctrl b ground {c['nmos']} w={{wn}} l={c['l']}",
             f"XP a ctrlb b supply {c['pmos']} w={{wp}} l={c['l']}",
             ".ends BANK_TG",
             ".subckt RCO_BANK " + " ".join(PINS),
             base,
             f"XMAIN rc bank main mainb vdd 0 BANK_TG wn={c['wmainn']} wp={c['wmainp']}",
             "RBLEED_BANK bank 0 1g"]
    for bit in range(9):
        lines.append(f"XSW{bit} bank cap{bit} s{bit} s{bit}b vdd 0 BANK_TG wn={c['wn']} wp={c['wp']}")
        lines.extend(passive_lines(process, 0, bit, f"cap{bit}", bank_style))
        lines.append(f"RBLEED{bit} cap{bit} 0 1g")
    lines.append(".ends RCO_BANK")
    return "\n".join(lines) + "\n"


def testbench(process: str, code: int, analysis: str, main: bool = True) -> str:
    """Isolate bank/switch behavior with static high-domain controls."""
    if process not in CONFIG or not 0 <= code <= 511 or analysis not in ("ac", "transient"):
        raise ValueError("Choose a PDK, code 0–511, and ac or transient")
    c = CONFIG[process]
    pdk = PDK_ROOT / c["pdk"]
    style = "balanced" if process == "gf180" else "binary"
    library = c["library"].format(pdk=pdk)
    if process == "gf180":
        library += (f"\n.lib {pdk}/libs.tech/ngspice/sm141064.ngspice res_typical"
                    f"\n.lib {pdk}/libs.tech/ngspice/sm141064.ngspice mimcap_typical")
    vdd = c["supply"]
    lines = [f"* Isolated RCO bank; {process}; code={code}; MAIN={int(main)}; {analysis}",
             library, ".temp 25", ".option reltol=1e-4",
             bank_subckt(process, style), f"VDD vdd 0 {vdd}",
             f"VMAIN main 0 {vdd if main else 0}",
             f"VMAINB mainb 0 {0 if main else vdd}"]
    for bit in range(9):
        high = vdd if code & (1 << bit) else 0
        lines.extend((f"VS{bit} s{bit} 0 {high}",
                      f"VS{bit}B s{bit}b 0 {vdd - high}"))
    lines.append("XBANK " + " ".join(PINS) + " RCO_BANK")
    if analysis == "ac":
        lines.extend((f"VTEST rc 0 DC {vdd / 2} AC 1",
                      f".ac lin 1 {AC_HZ} {AC_HZ}",
                      ".control", "run", "set wr_singlescale", "set wr_vecnames",
                      "wrdata admittance.dat i(VTEST)", "quit", ".endc", ".end"))
    else:
        lines.extend((f"VSTEP drive 0 PULSE(0 {vdd} 1u 1n 1n 20u 40u)",
                      "RDRIVE drive rc 470k", ".tran 2n 12u",
                      ".control", "run", "set wr_singlescale", "set wr_vecnames",
                      "wrdata waveform.dat v(drive) v(rc)", "quit", ".endc", ".end"))
    return "\n".join(lines) + "\n"


def _crossing(rows: list[list[float]], col: int, threshold: float) -> float:
    for a, b in zip(rows, rows[1:]):
        if a[col] < threshold <= b[col]:
            return a[0] + (threshold - a[col]) * (b[0] - a[0]) / (b[col] - a[col])
    raise ValueError("Testbench waveform did not cross the half-supply threshold")


def run(process: str, code: int, main: bool = True) -> dict:
    if (platform.system(), platform.machine()) != ("Darwin", "arm64"):
        raise RuntimeError("This report requires native arm64 Mac execution")
    ngspice = shutil.which("ngspice")
    pdk = PDK_ROOT / CONFIG[process]["pdk"]
    if not ngspice or PIN not in str(pdk.resolve()):
        raise RuntimeError("Pinned PDK or native ngspice is missing")
    folder = ROOT / "runs" / "rco" / "bank_bench" / process / str(uuid.uuid4())
    folder.mkdir(parents=True, mode=0o700)
    results = {}
    for analysis in ("ac", "transient"):
        deck = folder / f"{analysis}.spice"
        deck.write_text(testbench(process, code, analysis, main))
        result = subprocess.run([ngspice, "-b", deck.name], cwd=folder,
                                capture_output=True, text=True, timeout=90)
        log = folder / f"{analysis}.log"
        log.write_text(result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError(f"{analysis} bank bench failed: {log}")
        output = folder / ("admittance.dat" if analysis == "ac" else "waveform.dat")
        rows = [[float(value) for value in line.split()]
                for line in output.read_text().splitlines()[1:]]
        if analysis == "ac":
            if len(rows) != 1 or len(rows[0]) != 3:
                raise ValueError("Ambiguous bank AC output")
            conductance = -rows[0][1]
            capacitance = -rows[0][2] / (2 * math.pi * AC_HZ)
            results["ac"] = {"effective_cap_f": capacitance,
                             "conductance_s": conductance,
                             "bias_v": CONFIG[process]["supply"] / 2,
                             "frequency_hz": AC_HZ}
        else:
            if len(rows) < 100 or any(len(row) != 3 for row in rows):
                raise ValueError("Incomplete bank transient waveform")
            threshold = CONFIG[process]["supply"] / 2
            tdrive = _crossing(rows, 1, threshold)
            trc = _crossing(rows, 2, threshold)
            results["transient"] = {"half_supply_delay_s": trc - tdrive,
                                    "drive_crossing_s": tdrive,
                                    "rc_crossing_s": trc,
                                    "samples": len(rows)}
        results[analysis]["deck_sha256"] = sha256(deck)
        results[analysis]["output_sha256"] = sha256(output)
        results[analysis]["log_sha256"] = sha256(log)
    report = {"status": "simulated", "process": process, "code": code,
              "main": main, "bank_style": "balanced" if process == "gf180" else "binary",
              "scope": "One hierarchical bank and switches with ideal static high-domain controls; no control level shifters, layout, PEX, or oscillator",
              "host": {"system": platform.system(), "arch": platform.machine()},
              "pdk_pin": PIN, "model_tree_sha256": model_hash(pdk / "libs.tech" / "ngspice"),
              "source_sha256": sha256(SOURCE),
              "ngspice": ngspice, "results": results, "run": str(folder)}
    (folder / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("process", choices=CONFIG)
    parser.add_argument("code", type=int)
    parser.add_argument("--main-off", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(args.process, args.code, not args.main_off), indent=2))
