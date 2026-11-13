"""Place one isolated RCO bank as fan or centroid PDK-device GDS hierarchy.

This creates unrouted PCells for geometry review and DRC. It does not create
electrical nets or claim a layout-dependent circuit comparison.
"""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import platform
import uuid

from examples.rco.bank_floorplan import (GRID, centroid_map, dummy_sites,
                                         entry_columns, fan_map, site_x)
from examples.rco.generate_xschem import devices
from examples.rco.place import number
from examples.rco.run import CONFIG, PIN, ROOT


SOURCE = Path(__file__).resolve()
PITCH_UM = 14.0  # measured plate gap >=6.01um SKY, >=4.60um GF
WIRE_WIDTH_UM = 0.5  # M4 single-wire corridor proposal, not an actual route
SIDE_CLEARANCE_UM = 2.0
X0_UM, Y0_UM = 35.0, 170.0


def _mim_plate_size(process: str, width: float) -> tuple[float, float]:
    """Pinned PCell M4 bbox dimensions measured from saved native GDS."""
    return ((width + 3.49, width + 0.8) if process == "sky130"
            else (width + 2.4, width + 1.2))


def _body_contacts(lines: list[str], kind: str, x: float, y: float) -> None:
    """Carry over the previously DRC-checked GF placement tap geometry."""
    if kind == "nmos":
        lines += [f"rect pwell {x+5.8} {y} {x+8.5} {y+2.1}",
                  f"rect psubdiff {x+6.4} {y+0.5} {x+7.1} {y+1.2}",
                  f"rect psubdiffcont {x+6.6} {y+0.7} {x+6.9} {y+1.0}",
                  f"rect metal1 {x+6.5} {y+0.6} {x+7.0} {y+1.1}"]
    else:
        lines += [f"rect nwell {x-1.0} {y-1.0} {x+8.5} {y+5.0}",
                  f"rect nsubdiff {x+6.4} {y+1.2} {x+7.2} {y+1.8}",
                  f"rect nsubdiffcont {x+6.65} {y+1.35} {x+6.95} {y+1.65}",
                  f"rect metal1 {x+6.55} {y+1.25} {x+7.05} {y+1.75}"]


def placement(process: str, variant: str, corridor_probe: bool = False) -> tuple[list[dict], str]:
    if process not in CONFIG or variant not in ("fan", "centroid"):
        raise ValueError("Choose a PDK and fan or centroid")
    if corridor_probe and variant != "fan":
        raise ValueError("The bit-7/8 corridor probe belongs to the fan entry row")
    style = "balanced" if process == "gf180" else "binary"
    grid = fan_map(process) if variant == "fan" else centroid_map(process)
    rows, cols = GRID[process]
    entries = []
    lines = ["# One-stage RCO bank placement only; no electrical connections.",
             "proc rect {layer x1 y1 x2 y2} {",
             "    box values ${x1}um ${y1}um ${x2}um ${y2}um",
             "    paint $layer", "}", "load rco_bank_placement"]
    for name, kind, nets, params in devices(process, style):
        if not (name == "CBASE0" or name.startswith("C0_") or
                name.startswith("MAIN0_") or name.startswith("SW0_")):
            continue
        site_center = None
        if name.startswith("C0_"):
            row, col = grid[name]
            x, y = site_x(process, variant, row, col, PITCH_UM, X0_UM), \
                   Y0_UM + row * PITCH_UM
            site_center = [x, y]
        elif name == "CBASE0":
            x, y = X0_UM + cols * PITCH_UM + 35, Y0_UM
        elif name.startswith("MAIN0_"):
            x = X0_UM + cols * PITCH_UM + 35
            y = 30 if kind == "nmos" else 95
        else:
            bit = int(name.split("_")[1])
            x = X0_UM + min(entry_columns(process)[bit]) * PITCH_UM
            y = 30 if kind == "nmos" else 95
        if kind == "cap":
            if process == "gf180":
                width = 15.6 if name == "CBASE0" else number(params["c_width"])
                command = f"magic::gencell gf180mcu::cap_mim_2p0fF P{name} w {width:g} l {width:g}"
            else:
                width = 15.7 if name == "CBASE0" else number(params["w"])
                command = f"magic::gencell sky130::sky130_fd_pr__cap_mim_m3_2 P{name} w {width:g} l {width:g}"
            if site_center is not None:
                plate_w, plate_h = _mim_plate_size(process, width)
                x -= plate_w / 2
                y -= plate_h / 2
        else:
            width = number(params["W"])
            if process == "gf180":
                pcell = "pfet_03v3" if kind == "pmos" else "nfet_03v3"
                command = (f"magic::gencell gf180mcu::{pcell} P{name} w {width:g} "
                           "l 0.28 topc 0 botc 0 guard 0")
            else:
                pcell = "pfet_01v8" if kind == "pmos" else "nfet_01v8"
                command = (f"magic::gencell sky130::sky130_fd_pr__{pcell} P{name} "
                           f"w {width:g} l 0.15 topc 0 botc 0")
        lines += [f"box values {x}um {y}um {x}um {y}um", command]
        if process == "gf180" and kind in ("nmos", "pmos"):
            _body_contacts(lines, kind, x, y)
        entries.append({"name": name, "kind": kind, "nets_from_schematic": nets,
                        "parameters": params, "origin_um": [x, y],
                        "mim_plate_center_um": site_center,
                        "grid_site": list(grid[name]) if name in grid else None})
    # Each site receives a real MIM PCell. Ground connections remain a routing task.
    for row, col in sorted(dummy_sites(process, variant)):
        name = f"DUMMY_{row+1}_{col+1}"
        site_x_um = site_x(process, variant, row, col, PITCH_UM, X0_UM)
        site_y_um = Y0_UM + row * PITCH_UM
        width = 5.0 if process == "gf180" else 4.5
        plate_w, plate_h = _mim_plate_size(process, width)
        x, y = site_x_um - plate_w / 2, site_y_um - plate_h / 2
        if process == "gf180":
            command = f"magic::gencell gf180mcu::cap_mim_2p0fF P{name} w 5 l 5"
        else:
            command = f"magic::gencell sky130::sky130_fd_pr__cap_mim_m3_2 P{name} w 4.5 l 4.5"
        lines += [f"box values {x}um {y}um {x}um {y}um", command]
        entries.append({"name": name, "kind": "dummy_cap", "nets_from_schematic":
                        ["0", "0"], "ground_connection_status": "not_routed",
                        "parameters": {"unit_pcell": True}, "origin_um": [x, y],
                        "mim_plate_center_um": [site_x_um, site_y_um],
                        "grid_site": [row, col]})
    if corridor_probe:
        # Floating DRC coupon between the active bit-7 and bit-8 entry PCells.
        # It is excluded from the normal bank placement and circuit netlist.
        # Magic puts the PCell's lower-left geometry at its requested origin.
        # The measured M4 plate widths of the bit-7/8 units are below.
        plate_width = 7.99 if process == "sky130" else 9.40
        gap_left = X0_UM + 6 * PITCH_UM + plate_width / 2
        gap_right = X0_UM + 7 * PITCH_UM - plate_width / 2
        center_x = (gap_left + gap_right) / 2
        center_y = Y0_UM
        lines.append(f"rect metal4 {center_x-WIRE_WIDTH_UM/2} "
                     f"{center_y-1.5} {center_x+WIRE_WIDTH_UM/2} {center_y+1.5}")
        if min(center_x - WIRE_WIDTH_UM / 2 - gap_left,
               gap_right - center_x - WIRE_WIDTH_UM / 2) < SIDE_CLEARANCE_UM:
            raise RuntimeError("Corridor probe lacks planned plate clearance")
    expected = Counter({"cap": 78 if process == "sky130" else 62,
                        "nmos": 10, "pmos": 10,
                        "dummy_cap": len(dummy_sites(process, variant))})
    if Counter(entry["kind"] for entry in entries) != expected:
        raise RuntimeError("Unexpected bank placement population")
    lines += ["select top cell", "drc style drc(full)", "drc check", "drc catchup",
              "drc count total", "puts \"EXPECTED_INSTANCE_COUNT=%d\"" % len(entries),
              "puts \"MAGIC_CHILD_CELL_COUNT=[llength [cellname list children rco_bank_placement]]\"",
              "foreach cell [cellname list children rco_bank_placement] {",
              "    pushstack $cell", "    save $cell", "    popstack", "}",
              "save rco_bank_placement", "gds write rco_bank_placement.gds",
              "puts \"GDS_FEEDBACK_COUNT=[feedback count]\"",
              "feedback save gds_feedback.txt", "quit -noprompt"]
    return entries, "\n".join(lines) + "\n"


def write(process: str, variant: str, corridor_probe: bool = False) -> Path:
    if (platform.system(), platform.machine()) != ("Darwin", "arm64"):
        raise RuntimeError("Bank placement runs on the native arm64 Mac")
    entries, script = placement(process, variant, corridor_probe)
    rows, cols = GRID[process]
    folder = ROOT / "runs" / "rco" / "bank_placement" / process / variant / str(uuid.uuid4())
    folder.mkdir(parents=True, mode=0o700)
    source = folder / "placement.tcl"
    source.write_text(script)
    manifest = {"status": "generated", "process": process, "variant": variant,
                "bank_style": "balanced" if process == "gf180" else "binary",
                "grid_rows_cols": [rows, cols], "pitch_um_proposal": PITCH_UM,
                "mim_grid": "M4 plate centers on a uniform 14um lattice; no row staggering",
                "single_m4_wire_corridor_um": {"width": WIRE_WIDTH_UM,
                    "side_clearance_each": SIDE_CLEARANCE_UM,
                    "required_plate_gap": 2 * SIDE_CLEARANCE_UM + WIRE_WIDTH_UM},
                "connection_edge": "row 0 faces bit switches and shared bank routing",
                "corridor_probe": corridor_probe,
                "dummy_ground_status": "intended; neither plate is routed to ground yet",
                "pdk_pin": PIN, "host": {"system": "Darwin", "arch": "arm64"},
                "scope": "Unrouted one-stage bank PDK-device placement; no connectivity, grounded dummies, LVS, PEX or circuit performance claim",
                "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                "placement_tcl_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "counts": dict(Counter(entry["kind"] for entry in entries)),
                "instances": entries, "run": str(folder)}
    (folder / "placement.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return folder


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("process", choices=CONFIG)
    parser.add_argument("variant", choices=("fan", "centroid"))
    parser.add_argument("--corridor-probe", action="store_true")
    args = parser.parse_args()
    print(write(args.process, args.variant, args.corridor_probe))
