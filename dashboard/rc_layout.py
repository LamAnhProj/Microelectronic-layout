"""Map Magic's extracted R-C nodes onto the saved inverter GDS coordinate frame.

The overlay joins extracted node anchors. It does not reconstruct the physical
route or identify which conductor layer supplied each resistor value.
"""

from __future__ import annotations

import math
import re
import shlex


PORTS = ("IN", "OUT", "VSS", "VDD")
MODELS = {
    "sky130": {
        "sky130_fd_pr__nfet_01v8": ("NMOS", ("source", "gate", "drain", "bulk")),
        "sky130_fd_pr__pfet_01v8": ("PMOS", ("source", "gate", "drain", "bulk")),
    },
    "gf180": {
        "nfet_03v3": ("NMOS", ("drain", "gate", "source", "bulk")),
        "pfet_03v3": ("PMOS", ("drain", "gate", "source", "bulk")),
    },
}
BOX_LABEL = re.compile(
    r"box values\s+([+-]?\d+(?:\.\d+)?)um\s+([+-]?\d+(?:\.\d+)?)um\s+"
    r"([+-]?\d+(?:\.\d+)?)um\s+([+-]?\d+(?:\.\d+)?)um\s*\n"
    r"label\s+(IN|OUT|VSS|VDD)\s+", re.I)


def _fields(line: str) -> list[str]:
    return shlex.split(line, comments=False, posix=True)


def _gaussian_solve(matrix: list[list[float]], rhs: list[float]) -> list[float]:
    size = len(rhs)
    a = [row[:] + [rhs[i]] for i, row in enumerate(matrix)]
    for col in range(size):
        pivot = max(range(col, size), key=lambda i: abs(a[i][col]))
        if abs(a[pivot][col]) < 1e-14:
            raise ValueError("Extracted resistor network is disconnected")
        a[col], a[pivot] = a[pivot], a[col]
        factor = a[col][col]
        for j in range(col, size + 1):
            a[col][j] /= factor
        for i in range(size):
            if i == col:
                continue
            factor = a[i][col]
            for j in range(col, size + 1):
                a[i][j] -= factor * a[col][j]
    return [a[i][size] for i in range(size)]


def effective_ohms(port: str, target: str, edges: list[dict]) -> float:
    """DC effective resistance of a branched R network between two anchors."""
    if port == target:
        return 0.0
    nodes = sorted({port, target, *(node for edge in edges for node in (edge["a"], edge["b"]))})
    unknown = [node for node in nodes if node != port]
    index = {node: i for i, node in enumerate(unknown)}
    matrix = [[0.0] * len(unknown) for _ in unknown]
    for edge in edges:
        a, b, conductance = edge["a"], edge["b"], 1.0 / edge["ohm"]
        if a != port:
            matrix[index[a]][index[a]] += conductance
        if b != port:
            matrix[index[b]][index[b]] += conductance
        if a != port and b != port:
            matrix[index[a]][index[b]] -= conductance
            matrix[index[b]][index[a]] -= conductance
    rhs = [float(node == target) for node in unknown]
    result = _gaussian_solve(matrix, rhs)[index[target]]
    if not math.isfinite(result) or result < 0:
        raise ValueError("Invalid effective resistance")
    return result


def analyze_rc_layout(process: str, layout_tcl: str, flat_ext: str,
                      resist_ext: str, spice: str, bbox_um: list[float]) -> dict:
    """Return coordinate-anchored elements and port-to-device R measurements."""
    if process not in MODELS:
        raise ValueError("Unknown process")
    source_ports = {match[5].upper(): tuple(float(match[i]) for i in range(1, 5))
                    for match in BOX_LABEL.finditer(layout_tcl)}
    ext_ports: dict[str, tuple[int, int, int, int]] = {}
    for line in flat_ext.splitlines():
        if line.startswith("port "):
            f = _fields(line)
            if len(f) >= 7 and f[1] in PORTS:
                ext_ports[f[1]] = tuple(int(v) for v in f[3:7])
    if set(source_ports) != set(PORTS) or set(ext_ports) != set(PORTS):
        raise ValueError("Cannot align the four Magic and source-layout ports")
    scale_a = next((line for line in flat_ext.splitlines() if line.startswith("scale ")), None)
    scale_b = next((line for line in resist_ext.splitlines() if line.startswith("scale ")), None)
    if not scale_a or scale_a != scale_b:
        raise ValueError("Magic R-C coordinate scales differ")
    first = PORTS[0]
    x0, y0, x1, y1 = ext_ports[first]
    sx0, sy0, sx1, sy1 = source_ports[first]
    factor_x = (sx1 - sx0) / (x1 - x0)
    factor_y = (sy1 - sy0) / (y1 - y0)
    offset_x = sx0 - factor_x * x0
    offset_y = sy0 - factor_y * y0
    if factor_x <= 0 or abs(factor_x - factor_y) > 1e-7:
        raise ValueError("Magic-to-GDS coordinate conversion is inconsistent")
    for name in PORTS:
        for raw, expected, factor, offset in zip(ext_ports[name], source_ports[name],
                                                  (factor_x, factor_y, factor_x, factor_y),
                                                  (offset_x, offset_y, offset_x, offset_y)):
            if abs(raw * factor + offset - expected) > 0.011:
                raise ValueError(f"Magic port {name} does not align with layout")

    nodes: dict[str, list[float]] = {}
    resist_annotations: dict[tuple[str, str], float] = {}
    for line in resist_ext.splitlines():
        if line.startswith("rnode "):
            f = _fields(line)
            if len(f) < 7 or f[1] in nodes:
                raise ValueError("Invalid or duplicate Magic R-C node")
            point = [round(int(f[4]) * factor_x + offset_x, 5),
                     round(int(f[5]) * factor_y + offset_y, 5)]
            if not (bbox_um[0] - 0.2 <= point[0] <= bbox_um[2] + 0.2 and
                    bbox_um[1] - 0.2 <= point[1] <= bbox_um[3] + 0.2):
                raise ValueError(f"R-C node {f[1]} falls outside connected GDS")
            nodes[f[1]] = point
        elif line.startswith("resist "):
            f = _fields(line)
            if len(f) != 4:
                raise ValueError("Invalid Magic resistance annotation")
            key = tuple(sorted(f[1:3]))
            if key in resist_annotations:
                raise ValueError("Ambiguous parallel Magic resistance annotation")
            resist_annotations[key] = float(f[3])

    top = re.search(r"(?ims)^\.subckt\s+inverter\s+([^\n]+)\n(.*?)^\.ends", spice)
    if not top or set(top.group(1).split()) != set(PORTS):
        raise ValueError("R-C inverter subcircuit is missing its four ports")
    parent = {node: node for node in nodes}

    def find(node: str) -> str:
        if node not in parent:
            raise ValueError(f"R-C node {node} has no coordinate annotation")
        if parent[node] != node:
            parent[node] = find(parent[node])
        return parent[node]

    def union(a: str, b: str) -> None:
        parent[find(a)] = find(b)

    segments, capacitors, devices = [], [], {}
    for line in top.group(2).splitlines():
        f = line.split()
        if not f:
            continue
        label = f[0].upper()
        if label.startswith("R"):
            if len(f) != 4 or len(segments) >= 1000:
                raise ValueError("R-C resistor list is invalid or too large")
            value = float(f[3])
            key = tuple(sorted(f[1:3]))
            if (not math.isfinite(value) or value <= 0 or key not in resist_annotations
                    or abs(value - resist_annotations[key]) > max(0.02, value * 0.001)):
                raise ValueError(f"R-C resistor {f[0]} disagrees with Magic annotation")
            find(f[1]);find(f[2]);union(f[1], f[2])
            segments.append({"id": f[0], "a": f[1], "b": f[2], "ohm": value,
                             "a_xy": nodes[f[1]], "b_xy": nodes[f[2]]})
        elif label.startswith("C"):
            if len(f) != 4 or len(capacitors) >= 1000 or not f[3].lower().endswith("f"):
                raise ValueError("R-C capacitor list is invalid or too large")
            ff = float(f[3][:-1])
            if not math.isfinite(ff) or ff <= 0:
                raise ValueError("R-C capacitor value is invalid")
            find(f[1]);find(f[2])
            capacitors.append({"id": f[0], "a": f[1], "b": f[2], "ff": ff,
                               "a_xy": nodes[f[1]], "b_xy": nodes[f[2]]})
        elif label.startswith("X"):
            if len(f) < 6 or f[5] in devices:
                raise ValueError("R-C MOS list is invalid")
            devices[f[5]] = f[1:5]
    if not segments or not capacitors or set(devices) != set(MODELS[process]):
        raise ValueError("R-C parasitic network or MOS devices are incomplete")
    if len({find(port) for port in PORTS}) != len(PORTS):
        raise ValueError("R-C segments short external ports")
    net_of_root = {find(port): port for port in PORTS}
    for segment in segments:
        segment["net"] = net_of_root.get(find(segment["a"]))
        if not segment["net"]:
            raise ValueError("Floating resistor network")
    for capacitor in capacitors:
        capacitor["net_a"] = net_of_root.get(find(capacitor["a"]))
        capacitor["net_b"] = net_of_root.get(find(capacitor["b"]))
        if not capacitor["net_a"] or not capacitor["net_b"]:
            raise ValueError("Floating capacitor anchor")

    terminals = []
    for model, (device, roles) in MODELS[process].items():
        for node, role in zip(devices[model], roles):
            net = net_of_root.get(find(node))
            if not net:
                raise ValueError("Floating MOS terminal")
            edges = [segment for segment in segments if segment["net"] == net]
            terminals.append({"device": device, "terminal": role, "net": net,
                              "node": node, "xy": nodes[node],
                              "effective_ohm": round(effective_ohms(net, node, edges), 4)})
    nets = [{"name": port,
             "resistors": sum(segment["net"] == port for segment in segments),
             "largest_ohm": max((segment["ohm"] for segment in segments
                                 if segment["net"] == port), default=0.0)} for port in PORTS]
    return {"segments": segments, "capacitors": capacitors, "terminals": terminals,
            "nets": nets, "total_ff": round(sum(c["ff"] for c in capacitors), 5),
            "coordinate_um_per_magic_unit": factor_x,
            "geometry_note": "Node anchors from Magic .res.ext over the saved GDS. "
                             "Straight links show electrical connections, not exact "
                             "route shapes or conductor layers. Effective R is a DC "
                             "port-to-terminal calculation from the extracted network."}
