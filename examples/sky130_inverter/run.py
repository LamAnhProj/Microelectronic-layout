"""Run the SKY130A inverter checks on this Mac and keep a hashed run record.

Usage: python3 examples/sky130_inverter/run.py
Requires the pinned Volare PDK at pdks/volare/sky130A, the built worker, and
the native KLayout application. Reports and geometry stay under ignored runs/.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET


PIN = "c6d73a35f524070e85faff4a6a9eef49553ebc2b"
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "examples"))
from rcx_validate import validate_rcx
SOURCE = Path(__file__).resolve().parent
PDK_MOUNT = ROOT / "pdks" / "volare"
PDK = PDK_MOUNT / "sky130A"
KLAYOUT = Path("/Applications/klayout.app/Contents/MacOS/klayout")
RUN_ID = str(uuid.uuid4())
RUN = ROOT / "runs" / "sky130_inverter" / RUN_ID
CONTAINER_RUN = f"/results/sky130_inverter/{RUN_ID}"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def tree_hash(path: Path) -> str:
    """Hash names and contents, including every nested model include."""
    digest = hashlib.sha256()
    for item in sorted(p for p in path.rglob("*") if p.is_file()):
        digest.update(str(item.relative_to(path)).encode())
        digest.update(bytes.fromhex(sha256(item)))
    return digest.hexdigest()


def command(name: str, args: list[str], *, stdin: str | None = None) -> str:
    result = subprocess.run(args, cwd=ROOT, input=stdin, text=True,
                            capture_output=True, check=False)
    output = result.stdout + result.stderr
    (RUN / f"{name}.log").write_text(output)
    if result.returncode:
        raise RuntimeError(f"{name} exited {result.returncode}; see {RUN / (name + '.log')}")
    return output


def worker(name: str, program: str, *args: str, stdin: str | None = None,
           workdir: str = "") -> str:
    call = ["docker", "compose", "run", "--rm", "-v", f"{PDK_MOUNT}:/pdk:ro",
            "-e", "PDK_ROOT=/pdk", "--workdir", f"{CONTAINER_RUN}/{workdir}" if workdir else CONTAINER_RUN,
            "--entrypoint", program, "worker", *args]
    return command(name, call, stdin=stdin)


def measure(log: str) -> dict[str, float]:
    values = {}
    for name in ("vout_high", "vout_low", "tphl", "tplh"):
        matches = re.findall(rf"^\s*{name}\s*=\s*([+\-\d.eE]+)", log,
                             re.MULTILINE | re.IGNORECASE)
        if len(matches) != 1:
            raise RuntimeError(f"Missing or ambiguous {name} measurement")
        values[name] = float(matches[0])
    if not (1.7 <= values["vout_high"] <= 1.9
            and 0 <= values["vout_low"] < 0.1
            and 0 < values["tphl"] < 100e-12
            and 0 < values["tplh"] < 100e-12):
        raise RuntimeError(f"Circuit acceptance limits failed: {values}")
    return values


def require(pattern: str, output: str, name: str) -> None:
    if not re.search(pattern, output):
        raise RuntimeError(f"{name} evidence missing or failed")


def main() -> None:
    variant = sys.argv[1] if len(sys.argv) == 2 else "standard"
    if variant not in {"standard", "fast"}:
        raise ValueError("Usage: run.py [standard|fast]")
    layout_source = "layout_fast.tcl" if variant == "fast" else "layout.tcl"
    if (platform.system(), platform.machine()) != ("Darwin", "arm64"):
        raise RuntimeError("This run requires the user's native arm64 Mac")
    if PIN not in str(PDK.resolve()) or not PDK.is_dir():
        raise RuntimeError(f"Enable the pinned SKY130A Volare revision {PIN}")
    if not KLAYOUT.is_file():
        raise RuntimeError("Native KLayout app is missing")
    RUN.mkdir(parents=True, mode=0o700)
    os.chmod(RUN, 0o700)
    report: dict = {"status": "failed", "run": str(RUN),
                    "layout_variant": variant,
                    "layout_source_name": layout_source,
                    "comparison_run_id": ("a48fd805-e40e-467e-8076-395e6b3caaae"
                                          if variant == "fast" else None),
                    "host": {"system": platform.system(), "arch": platform.machine()},
                    "pdk_pin": PIN,
                    "scope": "open-PDK lab check; capacitance-only and distributed wire R-C extraction; no foundry signoff",
                    "checks": {}}
    try:
        for name in ("inverter.spice", "schematic.spice",
                     "design.json", "run.py"):
            shutil.copyfile(SOURCE / name, RUN / name)
        shutil.copyfile(SOURCE / layout_source, RUN / "layout.tcl")
        shutil.copyfile(ROOT / "examples" / "rcx.tcl", RUN / "rcx.tcl")
        shutil.copyfile(ROOT / "examples" / "rcx_validate.py", RUN / "rcx_validate.py")
        report["source_sha256"] = {name: sha256(RUN / name) for name in
                                   ("inverter.spice", "schematic.spice", "layout.tcl",
                                    "design.json", "run.py", "rcx.tcl", "rcx_validate.py")}
        report["pdk_sha256"] = {
            "magic": tree_hash(PDK / "libs.tech" / "magic"),
            "netgen": tree_hash(PDK / "libs.tech" / "netgen"),
            "ngspice": tree_hash(PDK / "libs.tech" / "ngspice"),
            "primitive_models": tree_hash(PDK / "libs.ref" / "sky130_fd_pr" / "spice"),
            "klayout_drc": sha256(PDK / "libs.tech" / "klayout" / "drc" / "sky130A_mr.drc"),
        }
        report["worker_image"] = command("image", ["docker", "image", "inspect",
            "semiconductor-lab-worker:local", "--format", "{{.Id}}"]).strip()

        baseline = worker("baseline", "ngspice", "-b", "inverter.spice")
        report["checks"]["baseline"] = measure(baseline)

        magic = worker("magic", "magic", "-dnull", "-noconsole", "-rcfile",
                       "/pdk/sky130A/libs.tech/magic/sky130A.magicrc",
                       stdin=(RUN / "layout.tcl").read_text())
        require(r"Magic 8\.3 revision 686", magic, "Magic version")
        require(r"Using technology \"sky130A\"", magic, "PDK load")
        require(r"Total DRC errors found: 0", magic, "full Magic DRC")
        require(r"GDS_FEEDBACK_COUNT=0", magic, "GDS export")
        for name in ("inverter.mag", "inverter.gds", "inverter_lvs.spice",
                     "inverter_pex.spice"):
            if not (RUN / name).is_file() or (RUN / name).stat().st_size == 0:
                raise RuntimeError(f"Missing generated artifact {name}")
        report["checks"]["magic_full_drc_errors"] = 0
        report["checks"]["gds_export_feedback"] = 0

        netgen = worker("lvs", "netgen", "-batch", "lvs",
                        "schematic.spice inverter", "inverter_lvs.spice inverter",
                        "/pdk/sky130A/libs.tech/netgen/sky130A_setup.tcl", "lvs_report.txt")
        require(r"Final result:\s*Circuits match uniquely\.", netgen, "LVS")
        report["checks"]["lvs"] = "unique match, 2 devices, 4 nets"

        post = (RUN / "inverter.spice").read_text()
        post = post.replace("XMN out in 0 0 sky130_fd_pr__nfet_01v8 w=1 l=0.15\n"
                            "XMP out in vdd vdd sky130_fd_pr__pfet_01v8 w=2 l=0.15",
                            "XINV out in 0 vdd inverter")
        if "XINV out in 0 vdd inverter" not in post:
            raise RuntimeError("Post-layout testbench substitution failed")
        post = post.replace(".temp 25", f".include {CONTAINER_RUN}/inverter_pex.spice\n.temp 25")
        (RUN / "postlayout.spice").write_text(post)
        extracted = worker("postlayout", "ngspice", "-b", "postlayout.spice")
        report["checks"]["capacitance_extracted"] = measure(extracted)

        # Flatten only a private copy of the saved cell. Keep the original
        # capacitance-only and LVS extraction outputs intact for comparison.
        rcx_dir = RUN / "rcx"
        rcx_dir.mkdir()
        for cell in RUN.glob("*.mag"):
            shutil.copyfile(cell, rcx_dir / cell.name)
        shutil.copyfile(RUN / "rcx.tcl", rcx_dir / "rcx.tcl")
        rcx_log = worker("magic_rcx", "magic", "-dnull", "-noconsole",
                         "-rcfile", "/pdk/sky130A/libs.tech/magic/sky130A.magicrc",
                         stdin=(rcx_dir / "rcx.tcl").read_text(), workdir="rcx")
        require(r"Total Nets: 4\s+Nets extracted: 4 .*?\s+Nets output: 4", rcx_log,
                "distributed R-C extraction")
        rcx_netlist = rcx_dir / "inverter_rcx.spice"
        if not (rcx_dir / "inverter.res.ext").is_file() or not rcx_netlist.is_file():
            raise RuntimeError("Magic did not produce the R-C annotation and SPICE netlist")
        rcx_text = rcx_netlist.read_text()
        topology = validate_rcx(rcx_text, ("OUT", "IN", "VSS", "VDD"), {
            "sky130_fd_pr__nfet_01v8": ("VSS", "IN", "OUT", "VSS"),
            "sky130_fd_pr__pfet_01v8": ("VDD", "IN", "OUT", "VDD"),
        })
        report["checks"]["rc_network"] = {
            **topology, "port_topology": "two MOS devices match four external nets",
            "threshold_milliohm": 0, "mindelay_ps": 0, "minres_milliohm": 1,
        }
        rc_post = (RUN / "inverter.spice").read_text()
        if rc_post.count("XMN out in 0 0 sky130_fd_pr__nfet_01v8 w=1 l=0.15\n"
                         "XMP out in vdd vdd sky130_fd_pr__pfet_01v8 w=2 l=0.15") != 1:
            raise RuntimeError("R-C testbench device substitution failed")
        rc_post = rc_post.replace(
            "XMN out in 0 0 sky130_fd_pr__nfet_01v8 w=1 l=0.15\n"
            "XMP out in vdd vdd sky130_fd_pr__pfet_01v8 w=2 l=0.15",
            "XINV out in 0 vdd inverter")
        rc_post = rc_post.replace(".temp 25", ".include inverter_rcx.spice\n.temp 25")
        (rcx_dir / "postlayout_rcx.spice").write_text(rc_post)
        rc_sim = worker("postlayout_rcx", "ngspice", "-b", "postlayout_rcx.spice",
                        workdir="rcx")
        report["checks"]["rc_extracted"] = measure(rc_sim)

        deck = PDK / "libs.tech" / "klayout" / "drc" / "sky130A_mr.drc"
        command("klayout", [str(KLAYOUT), "-b", "-r", str(deck),
                 "-rd", f"input={RUN / 'inverter.gds'}", "-rd", "top_cell=inverter",
                 "-rd", f"report={RUN / 'klayout_drc.xml'}", "-rd", "feol=true",
                 "-rd", "beol=true", "-rd", "offgrid=true", "-rd", "seal=false",
                 "-rd", "thr=2"])
        items = ET.parse(RUN / "klayout_drc.xml").getroot().findall(".//item")
        if items:
            raise RuntimeError(f"Native KLayout DRC found {len(items)} violations")
        report["checks"]["native_klayout_drc_items"] = 0
        readback_code = (
            "import json,sys,klayout.db as db; "
            "ly=db.Layout(); ly.read(sys.argv[1]); "
            "tops=[c.name for c in ly.top_cells()]; "
            "print(json.dumps({'tops':tops,'cells':ly.cells(),'layers':ly.layers(),"
            "'dbu_um':ly.dbu,'version':db.__version__}))"
        )
        readback = command("klayout_readback", ["uv", "run", "--frozen", "--extra",
                            "layout", "python", "-c", readback_code,
                            str(RUN / "inverter.gds")])
        geometry = json.loads(readback.strip())
        if geometry["tops"] != ["inverter"] or geometry["cells"] < 3 or geometry["layers"] < 1:
            raise RuntimeError(f"Native KLayout GDS readback failed: {geometry}")
        report["checks"]["native_klayout_readback"] = geometry

        negative_drc = """load inverter
drc style drc(full)
box values 10um 10um 10.1um 11um
paint metal1
box values -10um -10um 15um 20um
drc check
drc catchup
drc count total
quit -noprompt
"""
        drc_log = worker("negative_drc", "magic", "-dnull", "-noconsole",
                         "-rcfile", "/pdk/sky130A/libs.tech/magic/sky130A.magicrc",
                         stdin=negative_drc)
        counts = re.findall(r"Total DRC errors found: (\d+)", drc_log)
        if len(counts) != 1 or int(counts[0]) < 1:
            raise RuntimeError("Negative DRC control failed to detect narrow metal")
        report["checks"]["negative_drc_errors"] = int(counts[0])

        bad = (RUN / "schematic.spice").read_text().replace(
            "XMP OUT IN VDD VDD", "XMP OUT IN VDD VSS")
        if bad == (RUN / "schematic.spice").read_text():
            raise RuntimeError("Negative LVS control substitution failed")
        (RUN / "schematic_bad.spice").write_text(bad)
        bad_lvs = worker("negative_lvs", "netgen", "-batch", "lvs",
                         "schematic_bad.spice inverter", "inverter_lvs.spice inverter",
                         "/pdk/sky130A/libs.tech/netgen/sky130A_setup.tcl",
                         "lvs_negative_report.txt")
        require(r"Netlists do not match\.|Top level cell failed pin matching|MISMATCH", bad_lvs,
                "negative LVS control")
        report["checks"]["negative_lvs"] = "mismatch detected"

        report["evidence_sha256"] = {str(p.relative_to(RUN)): sha256(p)
                                     for p in RUN.rglob("*")
                                     if p.is_file() and p.name != "report.json"}
        report["status"] = "passed"
    except Exception as exc:
        report["error"] = str(exc)
        raise
    finally:
        (RUN / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        print(RUN / "report.json")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(error, file=sys.stderr)
        sys.exit(1)
