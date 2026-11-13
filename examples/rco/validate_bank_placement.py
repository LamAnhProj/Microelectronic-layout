"""Validate an isolated, unrouted bank PCell placement in Magic and KLayout.

Usage: .venv/bin/python -m examples.rco.validate_bank_placement sky130 fan
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

from examples.rco.bank_placement import (PITCH_UM, SIDE_CLEARANCE_UM,
                                         WIRE_WIDTH_UM, X0_UM, Y0_UM, write)
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


def validate(process: str, variant: str, corridor_probe: bool = False) -> dict:
    if process not in CONFIG:
        raise ValueError("Choose sky130 or gf180")
    if (platform.system(), platform.machine()) != ("Darwin", "arm64"):
        raise RuntimeError("This checkpoint runs on the native arm64 Mac")
    pdk = PDK_ROOT / CONFIG[process]["pdk"]
    if PIN not in str(pdk.resolve()) or not KLAYOUT.is_file():
        raise RuntimeError("Pinned PDK or native KLayout is unavailable")
    folder = write(process, variant, corridor_probe)
    manifest = json.loads((folder / "placement.json").read_text())
    expected = sum(manifest["counts"].values())
    source = folder / "placement.tcl"
    rcfile = f"/pdk/{pdk.name}/libs.tech/magic/{pdk.name}.magicrc"
    magic = execute(["docker", "compose", "run", "--rm", "-v",
                     f"{PDK_ROOT}:/pdk:ro", "-e", "PDK_ROOT=/pdk",
                     "--workdir", f"/results/rco/bank_placement/{process}/{variant}/{folder.name}",
                     "--entrypoint", "magic", "worker", "-dnull", "-noconsole",
                     "-rcfile", rcfile], cwd=ROOT, input_text=source.read_text(),
                    log=folder / "magic.log")
    counts = re.findall(r"Total DRC errors found: (\d+)", magic)
    children = re.findall(r"MAGIC_CHILD_CELL_COUNT=(\d+)", magic)
    if (len(counts) != 1 or len(children) != 1 or
            f'Using technology "{pdk.name}"' not in magic):
        raise RuntimeError(f"Magic placement population or DRC parsing failed: {folder}")
    gds = folder / "rco_bank_placement.gds"
    if not gds.is_file() or "GDS_FEEDBACK_COUNT=0" not in magic:
        raise RuntimeError(f"Placement GDS export failed: {folder}")
    layout = db.Layout()
    layout.read(str(gds))
    top = layout.top_cell()
    if top is None or top.name != "rco_bank_placement":
        raise RuntimeError("Placement GDS top cell is missing")
    gds_instances = sum(1 for _ in top.each_inst())
    if gds_instances != expected:
        raise RuntimeError(f"GDS has {gds_instances} instances; expected {expected}")
    m4_gds = "71/20" if process == "sky130" else "46/0"
    layer = next(i for i in layout.layer_indices()
                 if layout.get_info(i).to_s() == m4_gds)
    unit_plate_boxes = [shape.bbox().transformed(inst.trans)
                        for inst in top.each_inst()
                        if "cap_mim" in inst.cell.name.lower()
                        for shape in inst.cell.shapes(layer).each()
                        if shape.bbox().width() * layout.dbu < 12.0]
    expected_units = manifest["counts"]["cap"] - 1 + manifest["counts"]["dummy_cap"]
    if len(unit_plate_boxes) != expected_units:
        raise RuntimeError("MIM unit plate population does not match the manifest")
    center_errors = []
    for box in unit_plate_boxes:
        x, y = box.center().x * layout.dbu, box.center().y * layout.dbu
        center_errors.extend((abs(x - X0_UM - round((x - X0_UM) / PITCH_UM) * PITCH_UM),
                              abs(y - Y0_UM - round((y - Y0_UM) / PITCH_UM) * PITCH_UM)))
    max_center_error = max(center_errors)
    if max_center_error > 0.01:
        raise RuntimeError("MIM plate centers are staggered off the uniform grid")
    probe_geometry = None
    if corridor_probe:
        wires = [shape.bbox() for shape in top.shapes(layer).each()]
        if len(wires) != 1:
            raise RuntimeError("Corridor probe is missing or on the wrong GDS layer")
        wire = wires[0]
        if abs(wire.width() * layout.dbu - WIRE_WIDTH_UM) > 0.001 or \
                abs(wire.height() * layout.dbu - 3.0) > 0.001:
            raise RuntimeError("Corridor probe has unexpected geometry")
        plate_boxes = [shape.bbox().transformed(inst.trans)
                       for inst in top.each_inst()
                       if "cap_mim" in inst.cell.name.lower()
                       for shape in inst.cell.shapes(layer).each()]
        same_row = [box for box in plate_boxes
                    if box.bottom < wire.top and box.top > wire.bottom]
        if any(box.left < wire.right and wire.left < box.right
               for box in same_row):
            raise RuntimeError("Corridor probe overlaps a MIM bottom plate")
        left = max((box for box in same_row if box.right <= wire.left),
                   key=lambda box: box.right, default=None)
        right = min((box for box in same_row if box.left >= wire.right),
                    key=lambda box: box.left, default=None)
        if left is None or right is None:
            raise RuntimeError("Corridor probe lacks two flanking MIM plates")
        clear_left = (wire.left - left.right) * layout.dbu
        clear_right = (right.left - wire.right) * layout.dbu
        if min(clear_left, clear_right) + 1e-6 < SIDE_CLEARANCE_UM:
            raise RuntimeError("Measured GDS corridor clearance is below target")
        probe_geometry = {"gds_layer": m4_gds,
                          "wire_bbox_um": [v * layout.dbu for v in
                                           (wire.left, wire.bottom,
                                            wire.right, wire.top)],
                          "left_clearance_um": clear_left,
                          "right_clearance_um": clear_right}
    if process == "sky130":
        deck = pdk / "libs.tech" / "klayout" / "drc" / "sky130A_mr.drc"
        marker = folder / "klayout_drc.xml"
        args = [str(KLAYOUT), "-b", "-r", str(deck), "-rd", f"input={gds}",
                "-rd", "top_cell=rco_bank_placement", "-rd", f"report={marker}",
                "-rd", "feol=true", "-rd", "beol=true", "-rd", "offgrid=true",
                "-rd", "seal=false", "-rd", "thr=2"]
    else:
        deck = gf_deck(folder)
        marker = folder / "full.lyrdb"
        args = [str(KLAYOUT), "-b", "-r", str(deck), "-rd", "thr=1",
                "-rd", "metal_top=11K", "-rd", "mim_option=B", "-rd",
                "metal_level=5LM", "-rd", "feol=true", "-rd", "beol=true",
                "-rd", "offgrid=true", "-rd", "conn_drc=true", "-rd",
                "density=false", "-rd", "topcell=rco_bank_placement", "-rd",
                f"input={gds}", "-rd", f"report={marker}", "-rd",
                "run_mode=flat", "-rd", "table_name=main"]
    execute(args, cwd=ROOT, input_text=None, log=folder / "klayout.log")
    items = ET.parse(marker).getroot().findall(".//item")
    report = {"status": "placement_drc_clear" if counts[0] == "0" and not items else "placement_drc_findings",
              "process": process, "variant": variant,
              "corridor_probe": corridor_probe,
              "bank_style": manifest["bank_style"],
              "scope": "Unrouted PDK PCell placement only; dummies are not grounded; no nets, LVS, PEX, or full RCO verification",
              "host": manifest["host"], "pdk_pin": PIN,
              "instances": expected, "counts": manifest["counts"],
              "magic_unique_child_cells": int(children[0]),
              "gds_instances": gds_instances,
              "gds_bbox_um": [value * layout.dbu for value in
                              (top.bbox().left, top.bbox().bottom,
                               top.bbox().right, top.bbox().top)],
              "magic_drc_errors": int(counts[0]), "klayout_drc_items": len(items),
              "mim_grid_max_center_error_um": max_center_error,
              "corridor_probe_geometry": probe_geometry,
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
    parser.add_argument("variant", choices=("fan", "centroid"))
    parser.add_argument("--corridor-probe", action="store_true")
    args = parser.parse_args()
    print(json.dumps(validate(args.process, args.variant, args.corridor_probe), indent=2))
