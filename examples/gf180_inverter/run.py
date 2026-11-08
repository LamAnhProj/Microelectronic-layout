"""Run the GF180MCU D inverter checks on the native Mac.

Usage: python3 examples/gf180_inverter/run.py
Reports and geometry remain under ignored runs/.
"""

from __future__ import annotations

import hashlib
import glob
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
PDK = PDK_MOUNT / "gf180mcuD"
KLAYOUT = Path("/Applications/klayout.app/Contents/MacOS/klayout")
RUN_ID = str(uuid.uuid4())
RUN = ROOT / "runs" / "gf180_inverter" / RUN_ID


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def tree_hash(path: Path) -> str:
    digest = hashlib.sha256()
    for item in sorted(p for p in path.rglob("*") if p.is_file()):
        digest.update(str(item.relative_to(path)).encode())
        digest.update(bytes.fromhex(sha256(item)))
    return digest.hexdigest()


def command(name: str, args: list[str], *, stdin: str | None = None,
            cwd: Path = ROOT) -> str:
    result = subprocess.run(args, cwd=cwd, input=stdin, text=True,
                            capture_output=True, check=False)
    output = result.stdout + result.stderr
    (RUN / f"{name}.log").write_text(output)
    if result.returncode:
        raise RuntimeError(f"{name} exited {result.returncode}; see {RUN / (name + '.log')}")
    return output


def worker(name: str, program: str, workdir: str, *args: str,
           stdin: str | None = None) -> str:
    return command(name, ["docker", "compose", "run", "--rm", "-v",
        f"{PDK_MOUNT}:/pdk:ro", "-e", "PDK_ROOT=/pdk", "--workdir",
        f"/results/gf180_inverter/{RUN_ID}/{workdir}", "--entrypoint",
        program, "worker", *args], stdin=stdin)


def drc_count(output: str) -> int:
    found = re.findall(r"Total DRC errors found: (\d+)", output)
    if len(found) != 1 or "GDS_FEEDBACK_COUNT=0" not in output:
        raise RuntimeError("Magic DRC or GDS export evidence is incomplete")
    return int(found[0])


def klayout_drc(fixture: str, deck: Path, table: str) -> int:
    gds = RUN / fixture / "inverter.gds"
    report = RUN / fixture / f"{table}.lyrdb"
    command(f"klayout_{fixture}_{table}", [str(KLAYOUT), "-b", "-r", str(deck),
        "-rd", "thr=1", "-rd", "metal_top=11K", "-rd", "mim_option=B",
        "-rd", "metal_level=5LM", "-rd", "feol=true", "-rd", "beol=true",
        "-rd", "offgrid=true", "-rd", "conn_drc=true", "-rd",
        "density=false", "-rd", "topcell=inverter", "-rd",
        f"input={gds}", "-rd", f"report={report}", "-rd", "run_mode=flat",
        "-rd", f"table_name={table}"])
    return len(ET.parse(report).getroot().findall(".//item"))


def measure(output: str) -> dict[str, float]:
    values = {}
    for key in ("vout_high", "vout_low", "tphl", "tplh"):
        matches = re.findall(rf"^\s*{key}\s*=\s*([+\-\d.eE]+)", output,
                             re.MULTILINE | re.IGNORECASE)
        if len(matches) != 1:
            raise RuntimeError(f"Missing or ambiguous ngspice {key} measurement")
        values[key] = float(matches[0])
    if not (3.2 < values["vout_high"] <= 3.3 and
            0 <= values["vout_low"] < 0.1 and
            0 < values["tphl"] < 1e-9 and
            0 < values["tplh"] < 1e-9):
        raise RuntimeError(f"GF180 inverter simulation failed: {values}")
    return values


def main() -> None:
    variant = sys.argv[1] if len(sys.argv) == 2 else "standard"
    if variant not in {"standard", "fast"}:
        raise ValueError("Usage: run.py [standard|fast]")
    layout_source = "layout_fast.tcl" if variant == "fast" else "layout.tcl"
    if (platform.system(), platform.machine()) != ("Darwin", "arm64"):
        raise RuntimeError("This diagnostic requires the native arm64 Mac")
    if PIN not in str(PDK.resolve()) or not KLAYOUT.is_file():
        raise RuntimeError("Pinned GF180MCU D PDK or native KLayout is missing")
    RUN.mkdir(parents=True, mode=0o700)
    os.chmod(RUN, 0o700)
    report: dict = {
        "status": "failed", "run": str(RUN), "pdk": "gf180mcuD",
        "layout_variant": variant, "layout_source_name": layout_source,
        "comparison_run_id": ("53c0cbd1-8b41-4346-a913-2c371ad8726e"
                              if variant == "fast" else None),
        "pdk_pin": PIN, "host": {"system": platform.system(),
                                   "arch": platform.machine()},
        "scope": "open-PDK inverter check; capacitance-only and distributed wire R-C extraction; no foundry signoff",
        "checks": {}, "unresolved": []}
    try:
        for name in ("inverter.spice", "schematic.spice",
                     "disconnected_probe.tcl", "bad_pcell.tcl", "run.py"):
            shutil.copyfile(SOURCE / name, RUN / name)
        shutil.copyfile(SOURCE / layout_source, RUN / "layout.tcl")
        shutil.copyfile(ROOT / "examples" / "rcx.tcl", RUN / "rcx.tcl")
        shutil.copyfile(ROOT / "examples" / "rcx_validate.py", RUN / "rcx_validate.py")
        report["source_sha256"] = {p.name: sha256(p) for p in RUN.iterdir()
                                   if p.is_file() and p.suffix in {".spice", ".tcl", ".py"}}
        report["pdk_sha256"] = {
            "magic": tree_hash(PDK / "libs.tech" / "magic"),
            "netgen": tree_hash(PDK / "libs.tech" / "netgen"),
            "ngspice": tree_hash(PDK / "libs.tech" / "ngspice"),
            "klayout_drc_rules": tree_hash(PDK / "libs.tech" / "klayout" / "drc" / "rule_decks"),
        }
        report["worker_image"] = command("image", ["docker", "image", "inspect",
            "semiconductor-lab-worker:local", "--format", "{{.Id}}"]).strip()
        report["native_klayout_version"] = command("klayout_version",
            [str(KLAYOUT), "-b", "-v"]).strip()

        baseline = worker("baseline", "ngspice", "", "-b", "inverter.spice")
        report["checks"]["schematic_simulation"] = measure(baseline)

        rc = "/pdk/gf180mcuD/libs.tech/magic/gf180mcuD.magicrc"
        for fixture, script in (("connected", "layout.tcl"),
                                ("probe", "disconnected_probe.tcl"),
                                ("default_pcell", "bad_pcell.tcl")):
            folder = RUN / fixture
            folder.mkdir()
            shutil.copyfile(RUN / "schematic.spice", folder / "schematic.spice")
            magic = worker(f"magic_{fixture}", "magic", fixture, "-dnull",
                "-noconsole", "-rcfile", rc, stdin=(RUN / script).read_text())
            if 'Using technology "gf180mcuD"' not in magic:
                raise RuntimeError("GF180MCU D Magic technology did not load")
            report["checks"][f"magic_{fixture}_drc_errors"] = drc_count(magic)
            unknown = sorted(set(re.findall(r"Unknown cif layer: (\S+)", magic)))
            report["checks"][f"magic_{fixture}_unknown_cif_layers"] = unknown
            for artifact in ("inverter.mag", "inverter.gds"):
                if not (folder / artifact).is_file():
                    raise RuntimeError(f"Missing {fixture}/{artifact}")
        if report["checks"]["magic_connected_drc_errors"] != 0 or \
                report["checks"]["magic_probe_drc_errors"] != 0 or \
                report["checks"]["magic_default_pcell_drc_errors"] <= 0:
            raise RuntimeError("PCell DRC diagnostic no longer matches expectations")

        for artifact in ("inverter_lvs.spice", "inverter_pex.spice"):
            if not (RUN / "connected" / artifact).is_file():
                raise RuntimeError(f"Missing connected/{artifact}")

        lvs = worker("lvs_probe", "netgen", "probe", "-batch", "lvs",
            "schematic.spice inverter", "inverter_lvs.spice inverter",
            "/pdk/gf180mcuD/libs.tech/netgen/gf180mcuD_setup.tcl", "lvs_report.txt")
        if "Top level cell failed pin matching" not in lvs:
            raise RuntimeError("Disconnected physical probe was not rejected by LVS")
        report["checks"]["probe_lvs"] = "mismatch: disconnected ports and nets"

        lvs = worker("lvs_connected", "netgen", "connected", "-batch", "lvs",
            "schematic.spice inverter", "inverter_lvs.spice inverter",
            "/pdk/gf180mcuD/libs.tech/netgen/gf180mcuD_setup.tcl", "lvs_report.txt")
        if not re.search(r"Final result:\s*Circuits match uniquely\.", lvs):
            raise RuntimeError("Connected GF180 inverter LVS did not match uniquely")
        report["checks"]["connected_lvs"] = "unique match, 2 devices, 4 nets"

        baseline_spice = (RUN / "inverter.spice").read_text()
        expected_devices = ("XMN out in 0 0 nfet_03v3 w=1u l=0.28u\n"
                            "XMP out in vdd vdd pfet_03v3 w=2u l=0.28u")
        if baseline_spice.count(expected_devices) != 1:
            raise RuntimeError("Post-layout testbench device substitution failed")
        post = baseline_spice.replace(expected_devices, "XINV in out 0 vdd inverter")
        post = post.replace(".temp 25", ".include inverter_pex.spice\n.temp 25")
        (RUN / "connected" / "postlayout.spice").write_text(post)
        extracted = worker("postlayout", "ngspice", "connected", "-b",
                           "postlayout.spice")
        report["checks"]["capacitance_extracted_simulation"] = measure(extracted)

        # Flatten only a private copy; the connected layout and LVS files stay
        # tied to their original geometry and remain available as evidence.
        rcx_dir = RUN / "connected" / "rcx"
        rcx_dir.mkdir()
        for cell in (RUN / "connected").glob("*.mag"):
            shutil.copyfile(cell, rcx_dir / cell.name)
        shutil.copyfile(RUN / "rcx.tcl", rcx_dir / "rcx.tcl")
        rcx_log = worker("magic_rcx", "magic", "connected/rcx", "-dnull",
                         "-noconsole", "-rcfile", rc,
                         stdin=(rcx_dir / "rcx.tcl").read_text())
        if not re.search(r"Total Nets: 4\s+Nets extracted: 4 .*?\s+Nets output: 4",
                         rcx_log):
            raise RuntimeError("Magic did not extract all four R-C nets")
        rcx_netlist = rcx_dir / "inverter_rcx.spice"
        if not (rcx_dir / "inverter.res.ext").is_file() or not rcx_netlist.is_file():
            raise RuntimeError("Magic did not produce the R-C annotation and SPICE netlist")
        rcx_text = rcx_netlist.read_text()
        topology = validate_rcx(rcx_text, ("IN", "OUT", "VSS", "VDD"), {
            "nfet_03v3": ("OUT", "IN", "VSS", "VSS"),
            "pfet_03v3": ("OUT", "IN", "VDD", "VDD"),
        })
        report["checks"]["rc_network"] = {
            **topology, "port_topology": "two MOS devices match four external nets",
            "threshold_milliohm": 0, "mindelay_ps": 0, "minres_milliohm": 1,
        }
        rc_post = baseline_spice.replace(expected_devices,
                                         "XINV in out 0 vdd inverter")
        rc_post = rc_post.replace(".temp 25", ".include inverter_rcx.spice\n.temp 25")
        (rcx_dir / "postlayout_rcx.spice").write_text(rc_post)
        rc_sim = worker("postlayout_rcx", "ngspice", "connected/rcx", "-b",
                        "postlayout_rcx.spice")
        report["checks"]["rc_extracted_simulation"] = measure(rc_sim)

        bad_schematic = (RUN / "schematic.spice").read_text().replace(
            "XMP OUT IN VDD VDD", "XMP OUT IN VDD VSS")
        if bad_schematic == (RUN / "schematic.spice").read_text():
            raise RuntimeError("Negative LVS fixture substitution failed")
        (RUN / "connected" / "schematic_bad.spice").write_text(bad_schematic)
        bad_lvs = worker("lvs_negative", "netgen", "connected", "-batch", "lvs",
            "schematic_bad.spice inverter", "inverter_lvs.spice inverter",
            "/pdk/gf180mcuD/libs.tech/netgen/gf180mcuD_setup.tcl",
            "lvs_negative_report.txt")
        if "Top level cell failed pin matching" not in bad_lvs and \
                "Netlists do not match" not in bad_lvs:
            raise RuntimeError("Wrong PFET bulk was not rejected by LVS")
        report["checks"]["negative_lvs"] = "wrong PFET bulk rejected"

        # The vendor's Ruby logger calls Linux pmap. Adapt only its logging line
        # in a run-local copy; retain the original rule body and hash both.
        rules = PDK / "libs.tech" / "klayout" / "drc" / "rule_decks"
        deckdir = RUN / "klayout_deck"
        deckdir.mkdir()
        shutil.copyfile(rules / "layers_def.drc", deckdir / "layers_def.drc")
        old = "`pmap #{Process.pid} | tail -1`[10, 40].strip"
        new = "`ps -o rss= -p #{Process.pid}`.strip + ' KiB'"
        report["checks"]["vendor_runset_uses_linux_pmap"] = True
        def prepare_deck(table: str, names: list[str]) -> Path:
            deck = deckdir / f"{table}.drc"
            body = "\n".join((rules / name).read_text() for name in
                             ("main.drc", *names, "tail.drc"))
            if body.count(old) != 1:
                raise RuntimeError("Vendor pmap logger changed; review Mac adapter")
            deck.write_text(body.replace(old, new))
            report.setdefault("mac_deck_adapter_sha256", {})[table] = sha256(deck)
            return deck

        metal1_deck = prepare_deck("metal1", ["metal1.drc"])
        for fixture in ("probe", "default_pcell"):
            report["checks"][f"native_klayout_{fixture}_metal1_items"] = \
                klayout_drc(fixture, metal1_deck, "metal1")
        if report["checks"]["native_klayout_default_pcell_metal1_items"] <= 0:
            raise RuntimeError("Native KLayout failed to detect default PCell metal errors")

        excluded = {"antenna.drc", "density.drc", "main.drc",
                    "layers_def.drc", "tail.drc"}
        full_tables = [Path(p).name for p in glob.glob(str(rules / "*.drc"))
                       if Path(p).name not in excluded]
        full_deck = prepare_deck("main", full_tables)
        report["checks"]["native_klayout_connected_full_drc_items"] = \
            klayout_drc("connected", full_deck, "main")
        if report["checks"]["native_klayout_connected_full_drc_items"] != 0:
            raise RuntimeError("Native GF180 full DRC found violations")

        report["unresolved"] = [
            "Vendor KLayout DRC requires a macOS logger adapter",
            "Antenna and density tables were not run on this small cell",
            "Distributed R-C is Magic open-PDK extraction; not foundry-qualified signoff",
            "No foundry qualification or silicon measurement",
        ]
        if report["checks"]["magic_connected_unknown_cif_layers"]:
            report["unresolved"].append(
                "GF180 Magic DRC deck prints unknown CIF layer diagnostics")
        report["status"] = "passed"
    except Exception as exc:
        report["error"] = str(exc)
        raise
    finally:
        report["evidence_sha256"] = {str(p.relative_to(RUN)): sha256(p)
            for p in RUN.rglob("*") if p.is_file() and p.name != "report.json"}
        (RUN / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        print(RUN / "report.json")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(error, file=sys.stderr)
        sys.exit(1)
