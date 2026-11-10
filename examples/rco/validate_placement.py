"""Generate an unrouted RCO placement and run both PDK DRC engines.

Usage: python3 -m examples.rco.validate_placement gf180
       python3 -m examples.rco.validate_placement sky130
"""

from __future__ import annotations

import json
import platform
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

import klayout.db as db

from examples.rco.place import write
from examples.rco.run import CONFIG, PDK_ROOT, PIN, ROOT, sha256


sys.path.insert(0, str(__file__).rsplit("/", 1)[0])
from validate_passives import KLAYOUT, gf_deck  # noqa: E402


def execute(args: list[str], *, cwd, input_text: str | None, log, timeout: int = 900) -> str:
    result = subprocess.run(args, cwd=cwd, input=input_text, text=True,
                            capture_output=True, timeout=timeout)
    output = result.stdout + result.stderr
    log.write_text(output)
    if result.returncode:
        raise RuntimeError(f"{args[0]} exited {result.returncode}; inspect {log}")
    return output


def validate(process: str) -> dict:
    if process not in CONFIG:
        raise ValueError("Choose sky130 or gf180")
    if (platform.system(), platform.machine()) != ("Darwin", "arm64"):
        raise RuntimeError("This checkpoint runs on the native arm64 Mac")
    pdk = PDK_ROOT / CONFIG[process]["pdk"]
    if PIN not in str(pdk.resolve()) or not KLAYOUT.is_file():
        raise RuntimeError("Pinned PDK or native KLayout is unavailable")
    folder = write(process)
    manifest = json.loads((folder / "placement.json").read_text())
    expected = sum(manifest["counts"].values())
    source = folder / "placement.tcl"
    rcfile = f"/pdk/{pdk.name}/libs.tech/magic/{pdk.name}.magicrc"
    magic = execute(["docker", "compose", "run", "--rm", "-v",
                     f"{PDK_ROOT}:/pdk:ro", "-e", "PDK_ROOT=/pdk",
                     "--workdir", f"/results/rco/placement/{process}/{folder.name}",
                     "--entrypoint", "magic", "worker", "-dnull", "-noconsole",
                     "-rcfile", rcfile], cwd=ROOT, input_text=source.read_text(),
                    log=folder / "magic.log")
    counts = re.findall(r"Total DRC errors found: (\d+)", magic)
    children = re.findall(r"MAGIC_CHILD_CELL_COUNT=(\d+)", magic)
    if (len(counts) != 1 or len(children) != 1 or
            f'Using technology "{pdk.name}"' not in magic):
        raise RuntimeError(f"Magic placement population or DRC parsing failed: {folder}")
    gds = folder / "rco_placement.gds"
    if not gds.is_file() or "GDS_FEEDBACK_COUNT=0" not in magic:
        raise RuntimeError(f"Placement GDS export failed: {folder}")
    layout = db.Layout()
    layout.read(str(gds))
    top = layout.top_cell()
    if top is None or top.name != "rco_placement":
        raise RuntimeError("Placement GDS top cell is missing")
    gds_instances = sum(1 for _ in top.each_inst())
    if gds_instances != expected:
        raise RuntimeError(f"GDS has {gds_instances} instances; expected {expected}")
    if process == "sky130":
        deck = pdk / "libs.tech" / "klayout" / "drc" / "sky130A_mr.drc"
        marker = folder / "klayout_drc.xml"
        args = [str(KLAYOUT), "-b", "-r", str(deck), "-rd", f"input={gds}",
                "-rd", "top_cell=rco_placement", "-rd", f"report={marker}",
                "-rd", "feol=true", "-rd", "beol=true", "-rd", "offgrid=true",
                "-rd", "seal=false", "-rd", "thr=2"]
    else:
        deck = gf_deck(folder)
        marker = folder / "full.lyrdb"
        args = [str(KLAYOUT), "-b", "-r", str(deck), "-rd", "thr=1",
                "-rd", "metal_top=11K", "-rd", "mim_option=B", "-rd",
                "metal_level=5LM", "-rd", "feol=true", "-rd", "beol=true",
                "-rd", "offgrid=true", "-rd", "conn_drc=true", "-rd",
                "density=false", "-rd", "topcell=rco_placement", "-rd",
                f"input={gds}", "-rd", f"report={marker}", "-rd",
                "run_mode=flat", "-rd", "table_name=main"]
    execute(args, cwd=ROOT, input_text=None, log=folder / "klayout.log")
    items = ET.parse(marker).getroot().findall(".//item")
    report = {"status": "placement_drc_clear" if counts[0] == "0" and not items else "placement_drc_findings",
              "process": process, "bank_style": manifest["bank_style"],
              "scope": "Unrouted PDK PCell placement only; no nets, taps/routing qualification, LVS, PEX, or full RCO verification",
              "host": manifest["host"], "pdk_pin": PIN,
              "instances": expected, "counts": manifest["counts"],
              "magic_unique_child_cells": int(children[0]),
              "gds_instances": gds_instances,
              "gds_bbox_um": [value * layout.dbu for value in
                              (top.bbox().left, top.bbox().bottom,
                               top.bbox().right, top.bbox().top)],
              "magic_drc_errors": int(counts[0]), "klayout_drc_items": len(items),
              "placement_manifest_sha256": sha256(folder / "placement.json"),
              "placement_tcl_sha256": sha256(source), "gds_sha256": sha256(gds),
              "drc_deck_sha256": sha256(deck), "marker_sha256": sha256(marker),
              "commands": {"magic": ["docker", "compose", "run", "worker", "magic"],
                           "klayout": args},
              "run": str(folder)}
    (folder / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("process", choices=CONFIG)
    args = parser.parse_args()
    print(json.dumps(validate(args.process), indent=2))
