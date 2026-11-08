"""Check that a flattened Magic R-C inverter preserves port connectivity.

Netgen correctly counts the added R network as extra devices, so the ordinary
schematic-vs-layout LVS is performed on the separate resistor-free extraction.
This check collapses only explicit positive R edges and verifies every MOS
terminal against the expected port; capacitors never imply connectivity.
"""

from __future__ import annotations

import math
import re


def validate_rcx(text: str, ports: tuple[str, ...],
                 devices: dict[str, tuple[str, ...]]) -> dict[str, int]:
    top = re.search(r"(?ims)^\.subckt\s+inverter\s+([^\n]+)\n(.*?)^\.ends", text)
    if not top or tuple(top.group(1).split()) != ports:
        raise ValueError("R-C inverter ports are absent or reordered")

    parent: dict[str, str] = {}

    def root(node: str) -> str:
        parent.setdefault(node, node)
        if parent[node] != node:
            parent[node] = root(parent[node])
        return parent[node]

    def union(a: str, b: str) -> None:
        parent[root(a)] = root(b)

    resistors: list[list[str]] = []
    capacitors: list[list[str]] = []
    actual_devices: dict[str, tuple[str, ...]] = {}
    for line in top.group(2).splitlines():
        fields = line.split()
        if not fields:
            continue
        element = fields[0].upper()
        if element.startswith("R"):
            if len(fields) != 4 or not math.isfinite(float(fields[3])) or float(fields[3]) <= 0:
                raise ValueError("R-C netlist contains an invalid resistor")
            resistors.append(fields)
            union(fields[1], fields[2])
        elif element.startswith("C"):
            if len(fields) != 4 or not fields[3].lower().endswith("f"):
                raise ValueError("R-C netlist contains an invalid capacitor")
            value = float(fields[3][:-1])
            if not math.isfinite(value) or value <= 0:
                raise ValueError("R-C netlist contains a nonpositive capacitor")
            capacitors.append(fields)
        elif element.startswith("X"):
            if len(fields) < 6:
                raise ValueError("R-C device has too few terminals")
            model = fields[5]
            if model in actual_devices:
                raise ValueError("R-C netlist contains a duplicate device model")
            actual_devices[model] = tuple(fields[1:5])

    if not resistors or not capacitors or set(actual_devices) != set(devices):
        raise ValueError("R-C inverter devices or parasitics are incomplete")
    if len({root(port) for port in ports}) != len(ports):
        raise ValueError("R-C resistors short two distinct inverter ports")
    port_by_root = {root(port): port for port in ports}
    for model, expected in devices.items():
        actual = actual_devices[model]
        resolved = tuple(port_by_root.get(root(node)) for node in actual)
        if resolved != expected:
            raise ValueError(f"R-C {model} terminals do not match ports: {resolved}")
    for fields in resistors + capacitors:
        for node in fields[1:3]:
            if node != "0" and root(node) not in port_by_root:
                raise ValueError(f"R-C parasitic node {node} is floating")
    return {"resistor_count": len(resistors), "capacitor_count": len(capacitors)}
