"""Build a routed four-MIM series coupon from one RCO trim branch.

SKY bit 1 and GF bit 2 each contain four series MIM units. This isolated
coupon tests that electrical chain before adding the transmission gate and
the remaining bank. It does not claim complete RCO connectivity.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
import platform
import re
import shutil
import subprocess
import uuid
import xml.etree.ElementTree as ET

import klayout.db as db

from examples.rco.bank_placement import _mim_plate_size
from examples.rco.run import CONFIG, PDK_ROOT, PIN, ROOT, sha256


SOURCE = Path(__file__).resolve()
CELL = "rco_four_mim"
PITCH_UM = 14.0
AC_HZ = 512_000
X_UM = 50.0
Y_UM = 50.0
SPEC = {"sky130": {"bit": 1, "width": 4.5, "model": "sky130_fd_pr__cap_mim_m3_2",
                    "params": "w=4.5 l=4.5"},
        "gf180": {"bit": 2, "width": 6.0, "model": "cap_mim_2f0_m4m5_noshield",
                  "params": "c_width=6u c_length=6u"}}


def reference(process: str) -> str:
    spec = SPEC[process]
    lines = [f"* Four series units from RCO {process} bit {spec['bit']}",
             f".subckt {CELL} IN GND"]
    nodes = ("IN", "N1", "N2", "N3", "GND")
    lines.extend(f"XC{i} {nodes[i]} {nodes[i+1]} {spec['model']} {spec['params']}"
                 for i in range(4))
    lines.append(f".ends {CELL}")
    return "\n".join(lines) + "\n"


def magic_script(process: str) -> str:
    spec = SPEC[process]
    lines = ["# Isolated four-unit series branch. M5 joins alternating MIM terminals.",
             "proc rect {layer x1 y1 x2 y2} {",
             "  box values ${x1}um ${y1}um ${x2}um ${y2}um",
             "  paint $layer", "}", f"load {CELL}"]
    for index in range(4):
        y = Y_UM + index * PITCH_UM
        plate_w, plate_h = _mim_plate_size(process, spec["width"])
        origin_x, origin_y = X_UM - plate_w / 2, y - plate_h / 2
        if process == "sky130":
            command = (f"magic::gencell sky130::sky130_fd_pr__cap_mim_m3_2 "
                       f"PC{index} w {spec['width']:g} l {spec['width']:g}")
        else:
            command = (f"magic::gencell gf180mcu::cap_mim_2p0fF "
                       f"PC{index} w {spec['width']:g} l {spec['width']:g}")
        lines += [f"box values {origin_x}um {origin_y}um {origin_x}um {origin_y}um", command]
    # The left M5 island contacts top plate C1; the right M5 strip contacts
    # bottom plate C2 via the PCell's own Via4. Keep the three series links
    # outside the capacitor footprints in each 14 um inter-row gap.
    left, right, half_width = X_UM - 1.2, X_UM + 3.5, 0.8
    for index in range(3):
        low = Y_UM + index * PITCH_UM
        high = low + PITCH_UM
        mid = low + PITCH_UM / 2
        lines += [f"rect metal5 {right-half_width} {low} {right+half_width} {mid+half_width}",
                  f"rect metal5 {left-half_width} {mid-half_width} {right+half_width} {mid+half_width}",
                  f"rect metal5 {left-half_width} {mid-half_width} {left+half_width} {high}"]
    lines += [f"rect metal5 {X_UM-10} {Y_UM-half_width} {left+half_width} {Y_UM+half_width}",
              f"rect metal5 {right-half_width} {Y_UM+3*PITCH_UM-half_width} {X_UM+11} {Y_UM+3*PITCH_UM+half_width}",
              f"box values {X_UM-10}um {Y_UM-half_width}um {X_UM-8}um {Y_UM+half_width}um",
              "label IN c metal5", "port make 1",
              f"box values {X_UM+9}um {Y_UM+3*PITCH_UM-half_width}um {X_UM+11}um {Y_UM+3*PITCH_UM+half_width}um",
              "label GND c metal5", "port make 2",
              "select top cell", "drc style drc(full)", "drc check", "drc catchup",
              "drc count total", f"foreach cell [cellname list children {CELL}] {{",
              "  pushstack $cell", "  save $cell", "  popstack", "}",
              f"save {CELL}", f"gds write {CELL}.gds",
              'puts "GDS_FEEDBACK_COUNT=[feedback count]"',
              "extract all", "ext2spice lvs", f"ext2spice -o {CELL}_lvs.spice",
              "ext2spice default", "ext2spice subcircuits top on",
              "ext2spice cthresh 0", "ext2spice rthresh 0",
              f"ext2spice -o {CELL}_pex.spice", "quit -noprompt"]
    return "\n".join(lines) + "\n"


def rcx_script() -> str:
    return f"""# Resistance extraction on a private flattened copy; original GDS stays saved.
drc off
locking disable
crashbackups stop
box 0 0 0 0
load {CELL}
select top cell
flatten myflat
load myflat
cellname delete {CELL}
cellname rename myflat {CELL}
select top cell
extract do unique
extract do resistance
extresist threshold 0
extresist mindelay 0
extresist minres 1
extract all
ext2spice lvs
ext2spice cthresh 0
ext2spice extresist on
ext2spice -o {CELL}_rcx.spice
quit -noprompt
"""


def execute(args: list[str], cwd: Path, log: Path, input_text: str | None = None,
            timeout: int = 900) -> str:
    result = subprocess.run(args, cwd=cwd, input=input_text, text=True,
                            capture_output=True, timeout=timeout)
    output = result.stdout + result.stderr
    log.write_text(output)
    if result.returncode:
        raise RuntimeError(f"{args[0]} exited {result.returncode}; inspect {log}")
    return output


def worker(process: str, folder: Path, program: str, args: list[str],
           log: Path, input_text: str | None = None, subdir: str = "") -> str:
    pdk = CONFIG[process]["pdk"]
    container = f"/results/rco/four_mim/{process}/{folder.name}"
    if subdir:
        container += f"/{subdir}"
    command = ["docker", "compose", "run", "--rm", "-v",
               f"{PDK_ROOT}:/pdk:ro", "-e", "PDK_ROOT=/pdk",
               "--workdir", container, "--entrypoint", program, "worker", *args]
    return execute(command, ROOT, log, input_text)


def bench(process: str, variant: str, analysis: str, netlist: Path) -> str:
    if analysis not in ("ac", "transient"):
        raise ValueError("Choose AC or transient")
    pdk = PDK_ROOT / CONFIG[process]["pdk"]
    library = CONFIG[process]["library"].format(pdk=pdk)
    if process == "gf180":
        library += f"\n.lib {pdk}/libs.tech/ngspice/sm141064.ngspice mimcap_typical"
    header = [f"* {process} four-MIM {variant} {analysis} testbench",
              library, ".temp 25", ".option reltol=1e-5",
              f".include {netlist}", f"XU IN 0 {CELL}"]
    if analysis == "ac":
        header += ["VTEST IN 0 DC 0 AC 1", f".ac lin 1 {AC_HZ} {AC_HZ}",
                   ".control", "run", "set wr_singlescale", "set wr_vecnames",
                   "wrdata ac.dat i(VTEST)", "quit", ".endc", ".end"]
    else:
        supply = CONFIG[process]["supply"]
        header += [f"VSTEP DRIVE 0 PULSE(0 {supply} 1n 0.1n 0.1n 100n 200n)",
                   "RDRIVE DRIVE IN 470k", ".tran 0.1n 80n", ".control",
                   "run", "set wr_singlescale", "set wr_vecnames",
                   "wrdata transient.dat v(DRIVE) v(IN)", "quit", ".endc", ".end"]
    return "\n".join(header) + "\n"


def simulate(process: str, variant: str, folder: Path, netlist: Path) -> dict:
    results = {}
    for analysis in ("ac", "transient"):
        deck = folder / f"{variant}_{analysis}.spice"
        deck.write_text(bench(process, variant, analysis, netlist))
        log = folder / f"{variant}_{analysis}.log"
        execute(["ngspice", "-b", deck.name], folder, log, timeout=120)
        data = folder / ("ac.dat" if analysis == "ac" else "transient.dat")
        lines = data.read_text().splitlines()
        points = [[float(value) for value in line.split()] for line in lines[1:]]
        if analysis == "ac":
            if len(points) != 1 or len(points[0]) != 3:
                raise RuntimeError(f"Invalid AC data: {data}")
            cap = -points[0][2] / (2 * math.pi * AC_HZ)
            if not math.isfinite(cap) or cap <= 0:
                raise RuntimeError(f"Nonphysical AC capacitance: {cap}")
            results["ac"] = {"capacitance_f": cap,
                             "conductance_s": -points[0][1], "frequency_hz": AC_HZ}
        else:
            if len(points) < 100 or any(len(row) != 3 for row in points):
                raise RuntimeError(f"Invalid transient data: {data}")
            threshold = CONFIG[process]["supply"] / 2
            crossings = []
            for col in (1, 2):
                crossing = None
                for a, b in zip(points, points[1:]):
                    if a[col] < threshold <= b[col]:
                        crossing = a[0] + (threshold-a[col])*(b[0]-a[0])/(b[col]-a[col])
                        break
                if crossing is None:
                    raise RuntimeError(f"No half-supply crossing in {data}")
                crossings.append(crossing)
            results["transient"] = {"delay_s": crossings[1]-crossings[0],
                                    "drive_crossing_s": crossings[0],
                                    "input_crossing_s": crossings[1],
                                    "samples": len(points)}
        results[analysis]["deck_sha256"] = sha256(deck)
        results[analysis]["data_sha256"] = sha256(data)
        data.rename(folder / f"{variant}_{analysis}.dat")
    return results


def gf_deck(folder: Path) -> Path:
    rules = PDK_ROOT / "gf180mcuD" / "libs.tech" / "klayout" / "drc" / "rule_decks"
    directory = folder / "klayout_deck"
    directory.mkdir()
    shutil.copyfile(rules / "layers_def.drc", directory / "layers_def.drc")
    excluded = {"antenna.drc", "density.drc", "main.drc", "layers_def.drc", "tail.drc"}
    names = ["main.drc"] + [p.name for p in sorted(rules.glob("*.drc"))
                            if p.name not in excluded] + ["tail.drc"]
    body = "\n".join((rules / name).read_text() for name in names)
    old = "`pmap #{Process.pid} | tail -1`[10, 40].strip"
    new = "`ps -o rss= -p #{Process.pid}`.strip + ' KiB'"
    if body.count(old) != 1:
        raise RuntimeError("GF vendor DRC logger changed; review the Mac adapter")
    deck = directory / "main.drc"
    deck.write_text(body.replace(old, new))
    return deck


def run(process: str) -> dict:
    if process not in SPEC:
        raise ValueError("Choose sky130 or gf180")
    if (platform.system(), platform.machine()) != ("Darwin", "arm64"):
        raise RuntimeError("Run the routed coupon on the native arm64 Mac")
    pdk = PDK_ROOT / CONFIG[process]["pdk"]
    if PIN not in str(pdk.resolve()):
        raise RuntimeError("Pinned open PDK is unavailable")
    folder = ROOT / "runs" / "rco" / "four_mim" / process / str(uuid.uuid4())
    folder.mkdir(parents=True, mode=0o700)
    (folder / "layout.tcl").write_text(magic_script(process))
    (folder / "schematic.spice").write_text(reference(process))
    report = {"status": "running", "process": process, "bit": SPEC[process]["bit"],
              "host": {"system": platform.system(), "arch": platform.machine()},
              "pdk_pin": PIN, "source_sha256": sha256(SOURCE),
              "layout_tcl_sha256": sha256(folder / "layout.tcl"),
              "schematic_sha256": sha256(folder / "schematic.spice"),
              "scope": "Four routed series MIM units only; no switch, dummies, resistor, or oscillator",
              "run": str(folder)}
    try:
        magic = worker(process, folder, "magic", ["-dnull", "-noconsole",
            "-rcfile", f"/pdk/{pdk.name}/libs.tech/magic/{pdk.name}.magicrc"],
            folder / "magic.log", (folder / "layout.tcl").read_text())
        drc = [int(item) for item in re.findall(r"Total DRC errors found: (\d+)", magic)]
        gds = folder / f"{CELL}.gds"
        if drc != [0] or "GDS_FEEDBACK_COUNT=0" not in magic or not gds.is_file():
            raise RuntimeError(f"Magic DRC or GDS export failed; see {folder / 'magic.log'}")
        layout = db.Layout()
        layout.read(str(gds))
        top = layout.top_cell()
        instances = list(top.each_inst()) if top else []
        if not top or top.name != CELL or len(instances) != 4 or layout.dbu != 0.001:
            raise RuntimeError("GDS readback has the wrong cell, units, or cap count")
        report["checks"] = {"magic_drc_errors": 0, "gds_feedback": 0,
                            "gds_instances": len(instances), "gds_dbu_um": layout.dbu,
                            "gds_sha256": sha256(gds)}

        klayout = Path("/Applications/klayout.app/Contents/MacOS/klayout")
        if not klayout.is_file():
            raise RuntimeError("Native KLayout is unavailable")
        if process == "sky130":
            deck = pdk / "libs.tech" / "klayout" / "drc" / "sky130A_mr.drc"
            marker = folder / "klayout_drc.xml"
            switches = ["-rd", f"input={gds}", "-rd", f"top_cell={CELL}",
                        "-rd", f"report={marker}", "-rd", "feol=true",
                        "-rd", "beol=true", "-rd", "offgrid=true",
                        "-rd", "seal=false", "-rd", "thr=2"]
        else:
            deck = gf_deck(folder)
            marker = folder / "full.lyrdb"
            switches = ["-rd", "thr=1", "-rd", "metal_top=11K",
                        "-rd", "mim_option=B", "-rd", "metal_level=5LM",
                        "-rd", "feol=true", "-rd", "beol=true", "-rd",
                        "offgrid=true", "-rd", "conn_drc=true", "-rd",
                        "density=false", "-rd", f"topcell={CELL}",
                        "-rd", f"input={gds}", "-rd", f"report={marker}",
                        "-rd", "run_mode=flat", "-rd", "table_name=main"]
        execute([str(klayout), "-b", "-r", str(deck), *switches],
                ROOT, folder / "klayout.log")
        markers = ET.parse(marker).getroot().findall(".//item")
        report["checks"]["klayout_drc_items"] = len(markers)
        report["checks"]["klayout_deck_sha256"] = sha256(deck)
        if markers:
            raise RuntimeError(f"Native KLayout DRC found {len(markers)} items")

        setup = f"/pdk/{pdk.name}/libs.tech/netgen/{pdk.name}_setup.tcl"
        lvs = worker(process, folder, "netgen", ["-batch", "lvs",
            f"schematic.spice {CELL}", f"{CELL}_lvs.spice {CELL}",
            setup, "lvs_report.txt"], folder / "netgen.log")
        if not re.search(r"Final result:\s*Circuits match uniquely\.", lvs):
            raise RuntimeError(f"Four-cap series LVS failed; see {folder / 'netgen.log'}")
        report["checks"]["netgen_lvs"] = "unique match, four MIM devices"

        extracted = folder / f"{CELL}_pex.spice"
        if not extracted.is_file():
            raise RuntimeError("Capacitance PEX netlist is missing")
        rcx = folder / "rcx"
        rcx.mkdir()
        for cell in folder.glob("*.mag"):
            shutil.copyfile(cell, rcx / cell.name)
        (rcx / "rcx.tcl").write_text(rcx_script())
        rcx_log = worker(process, folder, "magic", ["-dnull", "-noconsole",
            "-rcfile", f"/pdk/{pdk.name}/libs.tech/magic/{pdk.name}.magicrc"],
            rcx / "magic.log", (rcx / "rcx.tcl").read_text(), "rcx")
        rcx_netlist = rcx / f"{CELL}_rcx.spice"
        if not rcx_netlist.is_file():
            raise RuntimeError("Distributed R-C netlist is missing")
        rcx_text = rcx_netlist.read_text()
        device_lines = [line for line in rcx_text.splitlines()
                        if line.startswith("X") and "cap_mim" in line]
        resistors = [line for line in rcx_text.splitlines() if line.startswith("R")]
        capacitors = [line for line in rcx_text.splitlines() if line.startswith("C")]
        if len(device_lines) != 4 or not capacitors:
            raise RuntimeError("R-C extraction lost the four-cap topology")
        report["checks"]["rcx"] = {"mim_devices": 4,
            "extracted_resistors": len(resistors),
            "extracted_coupling_capacitors": len(capacitors),
            "extraction_nets": re.findall(r"Total Nets: (\d+)", rcx_log),
            "netlist_sha256": sha256(rcx_netlist),
            "scope": "Magic flattened extract; zero resistors means no resolved wire-R in this small coupon"}
        report["results"] = {
            "schematic": simulate(process, "schematic", folder, folder / "schematic.spice"),
            "capacitance_pex": simulate(process, "pex", folder, extracted),
            "distributed_rcx": simulate(process, "rcx", rcx, rcx_netlist)}
        report["status"] = "passed"
    except Exception as error:
        report["status"] = "failed"
        report["error"] = str(error)
        raise
    finally:
        (folder / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("process", choices=SPEC)
    args = parser.parse_args()
    print(json.dumps(run(args.process), indent=2))
