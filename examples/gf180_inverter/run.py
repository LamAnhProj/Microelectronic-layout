"""Diagnose the GF180MCU D inverter path on the native Mac.

Usage: python3 examples/gf180_inverter/run.py
The run intentionally ends as partial until a connected, DRC-clean layout
matches the reference schematic. Reports remain under ignored runs/.
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


def metal1_drc(fixture: str, deck: Path) -> int:
    gds = RUN / fixture / "inverter.gds"
    report = RUN / fixture / "metal1.lyrdb"
    command(f"klayout_{fixture}", [str(KLAYOUT), "-b", "-r", str(deck),
        "-rd", "thr=1", "-rd", "metal_top=11K", "-rd", "mim_option=B",
        "-rd", "metal_level=5LM", "-rd", "feol=true", "-rd", "beol=true",
        "-rd", "offgrid=true", "-rd", "topcell=inverter", "-rd",
        f"input={gds}", "-rd", f"report={report}", "-rd", "run_mode=flat",
        "-rd", "table_name=metal1"])
    return len(ET.parse(report).getroot().findall(".//item"))


def main() -> None:
    if (platform.system(), platform.machine()) != ("Darwin", "arm64"):
        raise RuntimeError("This diagnostic requires the native arm64 Mac")
    if PIN not in str(PDK.resolve()) or not KLAYOUT.is_file():
        raise RuntimeError("Pinned GF180MCU D PDK or native KLayout is missing")
    RUN.mkdir(parents=True, mode=0o700)
    os.chmod(RUN, 0o700)
    report: dict = {
        "status": "failed", "run": str(RUN), "pdk": "gf180mcuD",
        "pdk_pin": PIN, "host": {"system": platform.system(),
                                   "arch": platform.machine()},
        "scope": "open-PDK diagnostic; disconnected physical probe is not LVS-clean",
        "checks": {}, "unresolved": []}
    try:
        for name in ("inverter.spice", "schematic.spice", "layout.tcl",
                     "bad_pcell.tcl", "run.py"):
            shutil.copyfile(SOURCE / name, RUN / name)
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

        baseline = worker("baseline", "ngspice", "", "-b", "inverter.spice")
        measures = {}
        for key in ("vout_high", "vout_low", "tphl", "tplh"):
            match = re.search(rf"^\s*{key}\s*=\s*([+\-\d.eE]+)", baseline,
                              re.MULTILINE | re.IGNORECASE)
            if not match:
                raise RuntimeError(f"Missing ngspice {key} measurement")
            measures[key] = float(match[1])
        if not (3.2 < measures["vout_high"] <= 3.3 and
                0 <= measures["vout_low"] < 0.1 and
                0 < measures["tphl"] < 1e-9 and
                0 < measures["tplh"] < 1e-9):
            raise RuntimeError(f"GF180 inverter simulation failed: {measures}")
        report["checks"]["schematic_simulation"] = measures

        rc = "/pdk/gf180mcuD/libs.tech/magic/gf180mcuD.magicrc"
        for fixture, script in (("probe", "layout.tcl"),
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
        if report["checks"]["magic_probe_drc_errors"] != 0 or \
                report["checks"]["magic_default_pcell_drc_errors"] <= 0:
            raise RuntimeError("PCell DRC diagnostic no longer matches expectations")

        lvs = worker("lvs_probe", "netgen", "probe", "-batch", "lvs",
            "schematic.spice inverter", "inverter_lvs.spice inverter",
            "/pdk/gf180mcuD/libs.tech/netgen/gf180mcuD_setup.tcl", "lvs_report.txt")
        if "Top level cell failed pin matching" not in lvs:
            raise RuntimeError("Disconnected physical probe was not rejected by LVS")
        report["checks"]["probe_lvs"] = "mismatch: disconnected ports and nets"

        # The vendor's Ruby logger calls Linux pmap. Adapt only its logging line
        # in a run-local copy; retain the original rule body and hash both.
        rules = PDK / "libs.tech" / "klayout" / "drc" / "rule_decks"
        deckdir = RUN / "klayout_deck"
        deckdir.mkdir()
        shutil.copyfile(rules / "layers_def.drc", deckdir / "layers_def.drc")
        deck = deckdir / "metal1.drc"
        body = "\n".join((rules / name).read_text() for name in
                         ("main.drc", "metal1.drc", "tail.drc"))
        old = "`pmap #{Process.pid} | tail -1`[10, 40].strip"
        if body.count(old) != 1:
            raise RuntimeError("Vendor pmap logger changed; review the Mac adapter")
        report["checks"]["vendor_runset_uses_linux_pmap"] = True
        deck.write_text(body.replace(old,
            "`ps -o rss= -p #{Process.pid}`.strip + ' KiB'"))
        report["mac_deck_adapter_sha256"] = sha256(deck)
        for fixture in ("probe", "default_pcell"):
            report["checks"][f"native_klayout_{fixture}_metal1_items"] = \
                metal1_drc(fixture, deck)
        if report["checks"]["native_klayout_default_pcell_metal1_items"] <= 0:
            raise RuntimeError("Native KLayout failed to detect default PCell metal errors")

        report["unresolved"] = [
            "No connected, DRC-clean inverter layout or matching LVS/PEX",
            "Vendor KLayout DRC requires a macOS logger adapter; only metal1 table was run",
            "No antenna, density, full DRC, or foundry qualification",
        ]
        if report["checks"]["magic_probe_unknown_cif_layers"]:
            report["unresolved"].append(
                "GF180 Magic DRC deck prints unknown CIF layer diagnostics")
        report["status"] = "partial"
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
