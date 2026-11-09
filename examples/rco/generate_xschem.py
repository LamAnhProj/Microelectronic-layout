"""Generate labeled, editable PDK-symbol RCO schematics from the PDK netlist.

The schematic describes the circuit only. Stimulus, measurement, and the
simulation-only bleed resistors stay in run.py's SPICE testbench.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
import re
import subprocess
import os

from examples.rco.run import CONFIG, PDK_ROOT, build_netlist


HERE = Path(__file__).resolve().parent


def devices(process: str) -> list[tuple[str, str, list[str], dict[str, str]]]:
    """Expand each INV, TG, and LS into physical PDK symbol instances."""
    result = []
    for raw in build_netlist(process, 0, passives="pdk", bank_style="binary").splitlines():
        if not raw.startswith("X"):
            continue
        words = raw.split()
        name = words[0][1:]
        params = dict(part.split("=", 1) for part in words if "=" in part)
        if "INV" in words:
            _, a, b, supply, ground, *_ = words
            result += [(f"{name}_N", "nmos", [b, a, ground, ground],
                        {"W": params["wn"]}),
                       (f"{name}_P", "pmos", [b, a, supply, supply],
                        {"W": params["wp"]})]
        elif "TG" in words:
            _, a, b, ctrl, ctrlb, supply, ground, *_ = words
            result += [(f"{name}_N", "nmos", [a, ctrl, b, ground],
                        {"W": params["wn"]}),
                       (f"{name}_P", "pmos", [a, ctrlb, b, supply],
                        {"W": params["wp"]})]
        elif "LS" in words:
            _, a, abar, out, outbar, supply, *_ = words
            result += [(f"{name}_N0", "nmos", [outbar, a, "0", "0"],
                        {"W": CONFIG[process]["wlsn"]}),
                       (f"{name}_N1", "nmos", [out, abar, "0", "0"],
                        {"W": CONFIG[process]["wlsn"]}),
                       (f"{name}_P0", "pmos", [outbar, out, supply, supply],
                        {"W": CONFIG[process]["wlsp"]}),
                       (f"{name}_P1", "pmos", [out, outbar, supply, supply],
                        {"W": CONFIG[process]["wlsp"]})]
        elif name.startswith("C"):
            result.append((name, "cap", words[1:3], params))
        elif name.startswith("RDELAY"):
            result.append((name, "res", words[1:4], params))
    counts = Counter(kind for _, kind, _, _ in result)
    assert counts == {"nmos": 65, "pmos": 65,
                      "cap": 234 if process == "sky130" else 186, "res": 3}, counts
    return result


def symbol(process: str, kind: str) -> tuple[str, str]:
    c = CONFIG[process]
    if process == "sky130":
        prefix = "sky130_fd_pr/"
        if kind == "nmos":
            return prefix + "nfet_01v8.sym", "model=nfet_01v8"
        if kind == "pmos":
            return prefix + "pfet_01v8.sym", "model=pfet_01v8"
        if kind == "res":
            return prefix + "res_xhigh_po_1p41.sym", "model=res_xhigh_po_1p41 L=330 mult=1"
        return prefix + "cap_mim_m3_2.sym", "model=cap_mim_m3_2"
    prefix = "symbols/"
    if kind in ("nmos", "pmos"):
        return prefix + c[kind] + ".sym", "model=" + c[kind]
    if kind == "res":
        return prefix + "ppolyf_u_1k.sym", "model=ppolyf_u_1k W=1u L=440u m=1"
    return prefix + "cap_mim_analog.sym", "model=cap_mim_2f0_m4m5_noshield m=1"


def generate(process: str) -> Path:
    if process not in CONFIG:
        raise ValueError(process)
    lines = ["v {xschem version=3.4.4 file_version=1.2}", "G {}", "K {}",
             "V {}", "S {}", "E {}"]
    pins = 0
    current_group = ""
    row = 0
    slot = 0
    for name, kind, nets, params in devices(process):
        # Separate the control, ring, switch, and passive rows for inspection.
        group = ("CONTROL" if name.startswith(("LB", "LS", "LMAIN")) else
                 "RING" if name.startswith("INV") else
                 "MASTER" if name.startswith("MAIN") else
                 "BRANCH SWITCH" if name.startswith("SW") else
                 "BUFFER" if name.startswith("BUF") else
                 "PASSIVES")
        if group != current_group:
            row += 1
            lines.append(f"T {{{group} — PDK symbols; nets use named labels}} 80 {-row * 190} 0 0 0.35 0.35 {{}}")
            row += 1
            current_group = group
            slot = 0
        column = slot % 8
        if column == 0:
            row += 1
        slot += 1
        x, y = 120 + column * 280, -row * 190
        path, model = symbol(process, kind)
        if kind in ("nmos", "pmos"):
            properties = (f"name=M{name} L={CONFIG[process]['l']} W={params['W']} "
                          "nf=1 m=1 mult=1 ad=0 as=0 pd=0 ps=0 nrd=0 nrs=0 "
                          f"sa=0 sb=0 sd=0 {model} spiceprefix=X")
            offsets = ([(20, 30), (-20, 0), (20, -30), (20, 0)]
                       if kind == "pmos" else
                       [(20, -30), (-20, 0), (20, 30), (20, 0)])
        elif kind == "res":
            properties = f"name=R{name} {model} spiceprefix=X"
            offsets = [(0, -30), (0, 30), (-20, 0)]
        else:
            width = (("15.7" if name.startswith("CBASE") else params["w"])
                     if process == "sky130" else
                     ("15.6u" if name.startswith("CBASE") else params["c_width"]))
            properties = f"name=C{name} {model} W={width} L={width} MF=1 spiceprefix=X"
            offsets = [(0, -30), (0, 30)]
        lines.append(f"C {{{path}}} {x} {y} 0 0 {{{properties}}}")
        for net, (dx, dy) in zip(nets, offsets):
            pins += 1
            lines.append(f"C {{devices/lab_pin.sym}} {x + dx} {y + dy} 0 0 "
                         f"{{name=p{pins} lab={net}}}")
    path = HERE / process / "rco.sch"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")
    return path


def verify_export(process: str, path: Path) -> Path:
    output = HERE / process / "xschem_export"
    output.mkdir(exist_ok=True)
    pdk = PDK_ROOT / CONFIG[process]["pdk"] / "libs.tech" / "xschem"
    command = ["xschem", "-n", "-x", "-q", "-s", "--rcfile", str(pdk / "xschemrc"),
               "-o", str(output), str(path)]
    result = subprocess.run(command, env={**os.environ, "PDK_ROOT": str(PDK_ROOT)},
                            capture_output=True, text=True, timeout=90)
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    netlist = output / "rco.spice"
    content = netlist.read_text()
    counts = Counter()
    observed = {}
    for line in content.splitlines():
        if not line.startswith("X"):
            continue
        fields = line.split()
        observed[fields[0][2:].upper()] = fields[1:]
        if "cap_mim" in line:
            counts["cap"] += 1
        elif "ppolyf_u_1k" in line or "res_xhigh_po_1p41" in line:
            counts["res"] += 1
        elif "nfet_" in line:
            counts["nmos"] += 1
        elif "pfet_" in line:
            counts["pmos"] += 1
    if counts != {"nmos": 65, "pmos": 65,
                  "cap": 234 if process == "sky130" else 186, "res": 3}:
        raise RuntimeError(f"Xschem export missing devices: {counts}")
    for name, kind, nets, _ in devices(process):
        got = observed.get(name.upper())
        if got is None:
            raise RuntimeError(f"Xschem export missing {name}")
        actual = [node.lower() for node in got[:len(nets)]]
        expected = [node.lower() for node in nets]
        if kind == "res":
            matches = (actual == expected or
                       actual == [expected[1], expected[0], expected[2]])
        else:
            matches = actual == expected
        if not matches:
            raise RuntimeError(f"Xschem connectivity differs for {name}: {actual} != {expected}")
    if re.search(r"IS MISSING|\?\?", content):
        raise RuntimeError("Xschem export has an unresolved symbol or net")
    return netlist


if __name__ == "__main__":
    for choice in CONFIG:
        source = generate(choice)
        exported = verify_export(choice, source)
        print(f"{choice}: {source} -> {exported}")
