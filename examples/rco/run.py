"""Build and simulate the nine-bit RCO on the native Mac with pinned PDK models.

Usage: python3 examples/rco/run.py sky130 100
       python3 examples/rco/run.py gf180 100
The generated netlist, waveform, log, and hashed report stay in ignored runs/.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import statistics
import time
import uuid


ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path(__file__).resolve()
PIN = "c6d73a35f524070e85faff4a6a9eef49553ebc2b"
PDK_ROOT = ROOT / "pdks" / "volare"
CONFIG = {
    "sky130": {
        "pdk": "sky130A", "supply": 1.8,
        "library": ".lib {pdk}/libs.tech/ngspice/sky130.lib.spice tt",
        "nmos": "sky130_fd_pr__nfet_01v8", "pmos": "sky130_fd_pr__pfet_01v8",
        "l": "0.15", "wn": "1", "wp": "2", "wmainn": "8", "wmainp": "16",
        "wlsn": "4", "wlsp": "2", "wbuf1n": "2", "wbuf1p": "4",
        "wbuf2n": "8", "wbuf2p": "16",
    },
    "gf180": {
        "pdk": "gf180mcuD", "supply": 3.3,
        "library": ".include {pdk}/libs.tech/ngspice/design.ngspice\n"
                   ".lib {pdk}/libs.tech/ngspice/sm141064.ngspice typical",
        "nmos": "nfet_03v3", "pmos": "pfet_03v3",
        "l": "0.28u", "wn": "1u", "wp": "2u", "wmainn": "8u", "wmainp": "16u",
        "wlsn": "4u", "wlsp": "2u", "wbuf1n": "2u", "wbuf1p": "4u",
        "wbuf2n": "8u", "wbuf2p": "16u",
    },
}


def sha256(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def model_hash(path: Path) -> str:
    result = hashlib.sha256()
    for file in sorted(path.rglob("*")):
        if file.is_file():
            result.update(str(file.relative_to(path)).encode())
            result.update(bytes.fromhex(sha256(file)))
    return result.hexdigest()


def passive_lines(process: str, stage: int, bit: int, node: str,
                  bank_style: str) -> list[str]:
    """Build one binary weight from legal-size MIM unit cells.

    SKY uses an eight-unit series base; GF's extractable 2 fF/µm²
    M4/M5 unit uses sixteen. Higher bits use parallel cells.
    """
    if process == "sky130":
        unit = "sky130_fd_pr__cap_mim_m3_2 w=4.5 l=4.5"
    else:
        width = (f"{5 * math.sqrt(1.10 ** bit):.4f}u"
                 if bank_style == "guarded" else "5u")
        unit = ("cap_mim_2f0_m4m5_noshield "
                f"c_width={width} c_length={width}")
    anchor = 3 if process == "sky130" else 4
    series = 1 << (anchor - bit) if bit < anchor else 1
    parallel = 1 << (bit - anchor) if bit >= anchor else 1
    lines = []
    for parallel_index in range(parallel):
        previous = node
        for series_index in range(series):
            following = ("0" if series_index == series - 1 else
                         f"mid{stage}_{bit}_{parallel_index}_{series_index}")
            lines.append(f"XC{stage}_{bit}_{parallel_index}_{series_index} "
                         f"{previous} {following} {unit}")
            previous = following
    return lines


def build_netlist(process: str, code: int, main: bool = True,
                  passives: str = "ideal", bank_style: str = "binary") -> str:
    if process not in CONFIG or not 0 <= code <= 511:
        raise ValueError("Choose sky130 or gf180 and a nine-bit code from 0 to 511")
    if passives not in ("ideal", "pdk"):
        raise ValueError("Choose ideal or pdk passives")
    if bank_style not in ("binary", "guarded"):
        raise ValueError("Choose binary or guarded bank")
    c = CONFIG[process]
    pdk = PDK_ROOT / c["pdk"]
    stop_us = simulation_stop_us(code, main, passives)
    library = c["library"].format(pdk=pdk)
    if passives == "pdk" and process == "gf180":
        library += (f"\n.lib {pdk}/libs.tech/ngspice/sm141064.ngspice res_typical"
                    f"\n.lib {pdk}/libs.tech/ngspice/sm141064.ngspice mimcap_typical")
    lines = [
        f"* Nine-bit RC ring oscillator; {process}; code {code}; MAIN={int(main)}; passives={passives}; bank={bank_style}",
        library, ".temp 25", ".option reltol=1e-4",
        f"VDD vdd 0 {c['supply']}", "VCTRL vctrl 0 1.8",
        "* CMOS inverter and low-domain control inverter",
        ".subckt INV in out supply ground wn=1 wp=2",
        f"XN out in ground ground {c['nmos']} w={{wn}} l={c['l']}",
        f"XP out in supply supply {c['pmos']} w={{wp}} l={c['l']}",
        ".ends INV",
        "* PMOS and NMOS in parallel; CTRL=1 connects A to B",
        ".subckt TG a b ctrl ctrlb supply ground wn=1 wp=2",
        f"XN a ctrl b ground {c['nmos']} w={{wn}} l={c['l']}",
        f"XP a ctrlb b supply {c['pmos']} w={{wp}} l={c['l']}",
        ".ends TG",
        "* Cross-coupled high-domain PMOS latch, driven by 1.8 V NMOS controls",
        ".subckt LS in inb out outb high",
        f"XN0 outb in 0 0 {c['nmos']} w={c['wlsn']} l={c['l']}",
        f"XN1 out inb 0 0 {c['nmos']} w={c['wlsn']} l={c['l']}",
        f"XP0 outb out high high {c['pmos']} w={c['wlsp']} l={c['l']}",
        f"XP1 out outb high high {c['pmos']} w={c['wlsp']} l={c['l']}",
        ".ends LS",
        "* Static 1.8 V code; shared by all three banks",
    ]
    for bit in range(9):
        level = 1.8 if code & (1 << bit) else 0
        lines += [f"VB{bit} b{bit} 0 {level}",
                  f"XLB{bit} b{bit} b{bit}bar vctrl 0 INV wn={c['wn']} wp={c['wp']}",
                  f"XLS{bit} b{bit} b{bit}bar s{bit} s{bit}bar vdd LS"]
    lines += [f"VMAIN main 0 {1.8 if main else 0}",
              f"XLMAIN main mainbar vctrl 0 INV wn={c['wn']} wp={c['wp']}",
              "XLSMAIN main mainbar smain smainbar vdd LS",
              "* Three inverters, each followed by a series resistor",
              "* before the next gate. Capacitor banks terminate at RC nodes."]
    for stage in range(3):
        source = f"n{(stage - 1) % 3}"
        if passives == "ideal":
            resistor = f"RDELAY{stage} d{stage} n{stage} 470k"
            base = f"CBASE{stage} n{stage} 0 0.5p"
        elif process == "sky130":
            resistor = (f"XRDELAY{stage} d{stage} n{stage} 0 "
                        "sky130_fd_pr__res_xhigh_po_1p41 w=1.41 l=330")
            base = (f"XCBASE{stage} n{stage} 0 "
                    "sky130_fd_pr__cap_mim_m3_2 w=15.7 l=15.7")
        else:
            resistor = (f"XRDELAY{stage} d{stage} n{stage} 0 "
                        "ppolyf_u_1k r_width=1u r_length=440u")
            base = (f"XCBASE{stage} n{stage} 0 "
                    "cap_mim_2f0_m4m5_noshield c_width=15.6u c_length=15.6u")
        lines += [f"XINV{stage} {source} d{stage} vdd 0 INV wn={c['wn']} wp={c['wp']}",
                  resistor, base,
                  f"XMAIN{stage} n{stage} bank{stage} smain smainbar vdd 0 TG "
                  f"wn={c['wmainn']} wp={c['wmainp']}",
                  f"RBANK{stage} bank{stage} 0 1g"]
        for bit in range(9):
            lines += [f"XSW{stage}_{bit} bank{stage} cap{stage}_{bit} s{bit} s{bit}bar "
                      f"vdd 0 TG wn={c['wn']} wp={c['wp']}"]
            if passives == "ideal":
                lines += [f"CB{stage}_{bit} cap{stage}_{bit} 0 {(1 << bit) * 5}f"]
            else:
                lines += passive_lines(process, stage, bit, f"cap{stage}_{bit}", bank_style)
            lines += [f"RB{stage}_{bit} cap{stage}_{bit} 0 1g"]
    lines += [
        "* Two output buffers isolate the oscillator from the external load",
        f"XBUF0 d2 buf vdd 0 INV wn={c['wbuf1n']} wp={c['wbuf1p']}",
        f"XBUF1 buf clk vdd 0 INV wn={c['wbuf2n']} wp={c['wbuf2p']}",
        "CLOAD clk 0 1p",
        f".ic V(n0)=0 V(n1)={c['supply']} V(n2)=0",
        f".tran 5n {stop_us:.3f}u 0 5n uic",
        f".meas tran period TRIG v(clk) VAL={c['supply']/2} RISE=6 "
        f"TARG v(clk) VAL={c['supply']/2} RISE=7",
        f".meas tran vhigh MAX v(clk) FROM={stop_us/2:.3f}u TO={stop_us:.3f}u",
        f".meas tran vlow MIN v(clk) FROM={stop_us/2:.3f}u TO={stop_us:.3f}u",
        f".meas tran idd_avg AVG i(VDD) FROM={stop_us/2:.3f}u TO={stop_us:.3f}u",
        ".control", "run", "set wr_singlescale", "set wr_vecnames",
        "wrdata waveform.dat v(n0) v(n1) v(n2) v(clk)", "quit", ".endc", ".end",
    ]
    return "\n".join(lines) + "\n"


def xschem_testbench(process: str, code: int, main: bool) -> tuple[str, Path, Path]:
    """Use the current editable source for devices and the generated stimulus."""
    import sys
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from examples.rco.generate_xschem import verify_export

    source = ROOT / "examples" / "rco" / process / "rco.sch"
    if not source.is_file():
        raise ValueError("Editable RCO schematic is missing")
    exported = verify_export(process, source)
    instances = []
    for line in exported.read_text().splitlines():
        if line.startswith("X"):
            instances.append(line)
        elif line.startswith("+"):
            instances[-1] += " " + line[1:].strip()
    if len(instances) != (367 if process == "sky130" else 319):
        raise ValueError("Xschem export has an unexpected device count")
    generated = build_netlist(process, code, main, "pdk", "binary").splitlines()
    bench = []
    in_subckt = False
    for line in generated:
        if line.startswith(".subckt"):
            in_subckt = True
            continue
        if line.startswith(".ends"):
            in_subckt = False
            continue
        if not in_subckt and not line.startswith("X"):
            bench.append(line)
    index = next(i for i, line in enumerate(bench) if line.startswith(".ic"))
    bench[index:index] = instances
    bench[0] += "; editable Xschem devices"
    return "\n".join(bench) + "\n", source, exported


def simulation_stop_us(code: int, main: bool, passives: str = "ideal") -> float:
    """Leave at least fourteen estimated cycles in the late half of the trace."""
    cap_pf = 0.5 + ((0.0055 if passives == "pdk" else 0.005) * code if main else 0)
    estimated_period_us = 6 * 470_000 * cap_pf * 1e-6 * math.log(2)
    return max(60.0, 28 * estimated_period_us)


def late_cycle_metrics(waveform: Path, supply: float, start_us: float) -> dict:
    """Interpolate clock crossings and check stable oscillation after settling."""
    rising, falling = [], []
    previous = None
    threshold = supply / 2
    for line in waveform.read_text().splitlines()[1:]:
        parts = line.split()
        if len(parts) != 5:
            continue
        now = (float(parts[0]), float(parts[4]))
        if previous and now[0] >= start_us * 1e-6:
            for crossings, upward in ((rising, True), (falling, False)):
                crossed = (previous[1] < threshold <= now[1] if upward else
                           previous[1] > threshold >= now[1])
                if crossed:
                    fraction = (threshold - previous[1]) / (now[1] - previous[1])
                    crossings.append(previous[0] + fraction * (now[0] - previous[0]))
        previous = now
    if len(rising) < 10 or len(falling) < 10:
        raise ValueError("Fewer than ten complete late-cycle clock edges")
    periods = [b - a for a, b in zip(rising[-10:-1], rising[-9:])]
    period = statistics.mean(periods)
    spread = (max(periods) - min(periods)) / period * 100
    if not (period > 0 and spread < 2):
        raise ValueError("Late oscillator period is unstable")
    high_fractions = []
    for start, end in zip(rising[-10:-1], rising[-9:]):
        edge = next((crossing for crossing in falling if start < crossing < end), None)
        if edge is not None:
            high_fractions.append((edge - start) / (end - start))
    if len(high_fractions) < 8:
        raise ValueError("Late clock duty cycle could not be measured")
    return {"period_s": period, "frequency_hz": 1 / period,
            "late_rising_edges": len(rising), "late_falling_edges": len(falling),
            "period_spread_pct": spread,
            "duty_cycle_pct": 100 * statistics.mean(high_fractions)}


def measured(log: str, name: str) -> float:
    hits = re.findall(rf"^\s*{name}\s*=\s*([+\-\d.eE]+)", log, re.I | re.M)
    if len(hits) != 1:
        raise ValueError(f"Missing or ambiguous {name} measurement")
    return float(hits[0])


def run(process: str, code: int, main: bool = True,
        passives: str = "ideal", schematic: str = "generated",
        bank_style: str = "binary") -> dict:
    if (platform.system(), platform.machine()) != ("Darwin", "arm64"):
        raise RuntimeError("This entry point records native arm64 Mac simulations only")
    ngspice = shutil.which("ngspice")
    if not ngspice:
        raise RuntimeError("Native ngspice is unavailable")
    c = CONFIG[process]
    pdk = PDK_ROOT / c["pdk"]
    if PIN not in str(pdk.resolve()) or not pdk.is_dir():
        raise RuntimeError(f"Pinned {c['pdk']} PDK is unavailable")
    if (schematic not in ("generated", "xschem") or
            (schematic == "xschem" and (passives != "pdk" or bank_style != "binary"))):
        raise ValueError("Editable Xschem runs require binary PDK passives")
    folder = ROOT / "runs" / "rco" / str(uuid.uuid4())
    folder.mkdir(parents=True, mode=0o700)
    os.chmod(folder, 0o700)
    deck = folder / "rco.spice"
    if schematic == "xschem":
        netlist_text, schematic_source, schematic_export = xschem_testbench(process, code, main)
    else:
        netlist_text, schematic_source, schematic_export = (
            build_netlist(process, code, main, passives, bank_style), None, None)
    deck.write_text(netlist_text)
    deck.chmod(0o600)
    report = {"status": "failed", "process": process, "code": code, "main": main,
              "passives": passives,
              "bank_style": bank_style,
              "schematic": schematic,
              "target_hz": 512000, "control_v": 1.8, "supply_v": c["supply"],
              "host": {"system": platform.system(), "arch": platform.machine()},
              "pdk_pin": PIN, "pdk_name": c["pdk"],
              "model_tree_sha256": model_hash(pdk / "libs.tech" / "ngspice"),
              "source_sha256": sha256(SOURCE), "netlist_sha256": sha256(deck),
              "ngspice_version": subprocess.run([ngspice, "--version"], text=True,
                                               capture_output=True, timeout=10).stdout.strip(),
              "run": str(folder), "command": [ngspice, "-b", str(deck)]}
    if schematic_source is not None and schematic_export is not None:
        report["schematic_source"] = str(schematic_source)
        report["schematic_sha256"] = sha256(schematic_source)
        report["xschem_export_sha256"] = sha256(schematic_export)
    started = time.time()
    try:
        result = subprocess.run(report["command"], cwd=folder, text=True,
                                capture_output=True, timeout=180)
        log = result.stdout + result.stderr
        (folder / "ngspice.log").write_text(log)
        report["exit_code"] = result.returncode
        if result.returncode:
            raise ValueError("ngspice failed; inspect ngspice.log")
        ngspice_period = measured(log, "period")
        high, low = measured(log, "vhigh"), measured(log, "vlow")
        supply_current = measured(log, "idd_avg")
        cycles = late_cycle_metrics(folder / "waveform.dat", c["supply"],
                                     simulation_stop_us(code, main, passives) / 2)
        period, frequency = cycles["period_s"], cycles["frequency_hz"]
        report["measurements"] = {**cycles, "ngspice_period_s": ngspice_period,
                                   "vhigh_v": high, "vlow_v": low,
                                   "core_supply_current_a": -supply_current,
                                   "core_supply_power_w": -c["supply"] * supply_current,
                                   "frequency_error_pct": 100 * (frequency / 512000 - 1)}
        report["waveform_sha256"] = sha256(folder / "waveform.dat")
        report["log_sha256"] = sha256(folder / "ngspice.log")
        if not (abs(ngspice_period / period - 1) < 0.05 and
                high > 0.9 * c["supply"] and low < 0.1 * c["supply"]):
            raise ValueError("Oscillation period or output swing failed acceptance")
        report["status"] = "simulated"
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        report["error"] = str(exc)
    report["elapsed_s"] = round(time.time() - started, 3)
    (folder / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    os.chmod(folder / "report.json", 0o600)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("process", choices=CONFIG)
    parser.add_argument("code", type=int, help="nine-bit code, 0 to 511")
    parser.add_argument("--main-off", action="store_true")
    parser.add_argument("--passives", choices=("ideal", "pdk"), default="ideal")
    parser.add_argument("--bank-style", choices=("binary", "guarded"), default="binary")
    parser.add_argument("--xschem", action="store_true", help="simulate current editable Xschem circuit")
    args = parser.parse_args()
    if not 0 <= args.code <= 511:
        parser.error("code must be between 0 and 511")
    print(json.dumps(run(args.process, args.code, not args.main_off,
                         args.passives, "xschem" if args.xschem else "generated",
                         args.bank_style), indent=2))
