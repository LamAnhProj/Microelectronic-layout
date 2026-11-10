"""Place every RCO PDK device as a spaced, unrouted Magic PCell.

This is a physical placement checkpoint, not a connected circuit layout.
Usage: python3 -m examples.rco.place gf180
       python3 -m examples.rco.place sky130
"""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import platform
import uuid

from examples.rco.generate_xschem import devices
from examples.rco.run import CONFIG, GF_BALANCED_MIM_WIDTH_UM, PIN, ROOT


SOURCE = Path(__file__).resolve()


def number(value: str) -> float:
    return float(value.removesuffix("u"))


def placement(process: str) -> tuple[list[dict], str]:
    if process not in CONFIG:
        raise ValueError("Choose sky130 or gf180")
    style = "balanced" if process == "gf180" else "binary"
    entries = []
    cap_index = [0, 0, 0]
    mos_index = 0
    lines = ["# Unrouted RCO device placement; no electrical connectivity is asserted.",
             "proc rect {layer x1 y1 x2 y2} {",
             "    box values ${x1}um ${y1}um ${x2}um ${y2}um",
             "    paint $layer", "}", "load rco_placement"]
    for name, kind, nets, params in devices(process, style):
        if kind == "res":
            stage = int(name[-1])
            x, y = 35 + stage * 340, 25
            if process == "gf180":
                command = f"magic::gencell gf180mcu::ppolyf_u_1k P{name} w 1 l 440"
            else:
                command = f"magic::gencell sky130::sky130_fd_pr__res_xhigh_po_1p41 P{name} w 1.41 l 330"
        elif kind == "cap":
            stage = int(name[5] if name.startswith("CBASE") else name[1])
            index = cap_index[stage]
            cap_index[stage] += 1
            x, y = 105 + stage * 340 + (index % 9) * 31, 25 + (index // 9) * 31
            if process == "gf180":
                width = 15.6 if name.startswith("CBASE") else number(params["c_width"])
                command = f"magic::gencell gf180mcu::cap_mim_2p0fF P{name} w {width:g} l {width:g}"
            else:
                width = 15.7 if name.startswith("CBASE") else number(params["w"])
                command = f"magic::gencell sky130::sky130_fd_pr__cap_mim_m3_2 P{name} w {width:g} l {width:g}"
        else:
            index = mos_index
            mos_index += 1
            x, y = 35 + (index % 18) * 57, 560 + (index // 18) * 65
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
            # Nearby body contacts are needed even at the placement stage.
            # Shapes follow the already DRC-checked GF inverter tap geometry.
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
        entries.append({"name": name, "kind": kind, "nets_from_schematic": nets,
                        "parameters": params, "origin_um": [x, y]})
    counts = Counter(entry["kind"] for entry in entries)
    expected = Counter({"nmos": 65, "pmos": 65,
                        "cap": 234 if process == "sky130" else 186, "res": 3})
    if counts != expected or cap_index != ([78] * 3 if process == "sky130" else [62] * 3):
        raise RuntimeError(f"Unexpected placement population: {counts}, {cap_index}")
    lines += ["select top cell", "drc style drc(full)", "drc check", "drc catchup",
              "drc count total", "puts \"EXPECTED_INSTANCE_COUNT=%d\"" % len(entries),
              "puts \"MAGIC_CHILD_CELL_COUNT=[llength [cellname list children rco_placement]]\"",
              "foreach cell [cellname list children rco_placement] {",
              "    pushstack $cell", "    save $cell", "    popstack", "}",
              "save rco_placement", "gds write rco_placement.gds",
              "puts \"GDS_FEEDBACK_COUNT=[feedback count]\"",
              "feedback save gds_feedback.txt", "quit -noprompt"]
    return entries, "\n".join(lines) + "\n"


def write(process: str) -> Path:
    if (platform.system(), platform.machine()) != ("Darwin", "arm64"):
        raise RuntimeError("The placement checkpoint runs on the native arm64 Mac")
    entries, script = placement(process)
    folder = ROOT / "runs" / "rco" / "placement" / process / str(uuid.uuid4())
    folder.mkdir(parents=True, mode=0o700)
    source = folder / "placement.tcl"
    source.write_text(script)
    manifest = {"status": "generated", "process": process,
                "bank_style": "balanced" if process == "gf180" else "binary",
                "pdk_pin": PIN, "host": {"system": "Darwin", "arch": "arm64"},
                "scope": "Unrouted PDK device placement; no connectivity, LVS, PEX, or full circuit DRC claim",
                "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                "placement_tcl_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "counts": dict(Counter(entry["kind"] for entry in entries)),
                "gf_balanced_widths_um": list(GF_BALANCED_MIM_WIDTH_UM) if process == "gf180" else None,
                "instances": entries, "run": str(folder)}
    (folder / "placement.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return folder


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("process", choices=CONFIG)
    args = parser.parse_args()
    print(write(args.process))
