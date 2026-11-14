"""Compare graph-aware floorplan checks on the saved logical site maps.

The SVG-derived tiles are teaching geometry, not routed GDS. The Manhattan
series-chain lengths are center-to-center lower bounds, not extracted wires.
"""

from __future__ import annotations

from collections import defaultdict
import hashlib
import json
from pathlib import Path
import platform
from statistics import median
from time import perf_counter_ns

from examples.rco.bank_floorplan import centroid_map, clustered_map, fan_map, units


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "dashboard" / "static" / "floorplan-data.json"
PITCH_UM = 14.0
DX, DY = 37.0, 31.0  # Saved teaching SVG site pitches in pixels.


def neighbors(point: tuple[float, float]) -> tuple[tuple[float, float], ...]:
    x, y = point
    return ((x - DX, y), (x + DX, y), (x, y - DY), (x, y + DY))


def components_hash(points: set[tuple[float, float]]) -> int:
    """Four hash probes per site: expected O(n) time and O(n) space."""
    remaining = set(points)
    count = 0
    while remaining:
        count += 1
        stack = [remaining.pop()]
        while stack:
            for neighbor in neighbors(stack.pop()):
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    stack.append(neighbor)
    return count


def components_pairwise(points: set[tuple[float, float]]) -> int:
    """Scan remaining sites for each expansion: O(n²) worst case."""
    remaining = set(points)
    count = 0
    while remaining:
        count += 1
        stack = [remaining.pop()]
        while stack:
            adjacent = set(neighbors(stack.pop()))
            found = {point for point in remaining if point in adjacent}
            remaining.difference_update(found)
            stack.extend(found)
    return count


def panel_points(panel: dict) -> dict[str, set[tuple[float, float]]]:
    points: dict[str, set[tuple[float, float]]] = defaultdict(set)
    for tile in panel["tiles"]:
        if tile["bit"] != "D":
            points[tile["bit"]].add((float(tile["x"]), float(tile["y"])))
    return dict(points)


def score(points: dict[str, set[tuple[float, float]]], method) -> dict:
    counts = {bit: method(sites) for bit, sites in points.items()}
    return {"split_bits": sum(value > 1 for value in counts.values()),
            "extra_components": sum(value - 1 for value in counts.values()),
            "staggered_x": len({round(x % DX, 3)
                                for sites in points.values() for x, _ in sites}) > 1,
            "components_by_bit": dict(sorted(counts.items()))}


def timed(panels: list[dict], method) -> float:
    samples = []
    for _ in range(5):
        start = perf_counter_ns()
        for _ in range(200):
            for panel in panels:
                score(panel, method)
        samples.append((perf_counter_ns() - start) / 200 / len(panels) / 1e6)
    return round(median(samples), 4)  # milliseconds per panel; local microbenchmark


def series_chain(process: str, variant: str, mapping: dict) -> dict:
    bit = 1 if process == "sky130" else 2
    names = units(process)[bit]
    if len(names) != 4:
        raise RuntimeError("The selected branch no longer has four MIM units")
    sites = [mapping[name] for name in names]
    hops = [abs(a[0] - b[0]) + abs(a[1] - b[1])
            for a, b in zip(sites, sites[1:])]
    return {"process": process, "variant": variant, "bit": bit,
            "sites_in_electrical_order": sites,
            "manhattan_hops": sum(hops),
            "center_distance_lower_bound_um": sum(hops) * PITCH_UM}


def run() -> dict:
    saved = json.loads(DATA.read_text())
    panels = []
    history = []
    for revision in saved["revisions"]:
        for panel in revision["panels"]:
            if not panel["id"].endswith("-fan"):
                continue
            points = panel_points(panel)
            hashed, scanned = score(points, components_hash), score(points, components_pairwise)
            if hashed != scanned:
                raise RuntimeError(f"Graph methods disagree on {revision['id']} {panel['id']}")
            history.append({"revision": revision["id"], "process": panel["process"],
                            "active_units": sum(map(len, points.values())), **hashed})
            panels.append(points)
    chains = []
    for process in ("sky130", "gf180"):
        for variant, mapping in (("fan", fan_map(process)),
                                 ("clustered", clustered_map(process)),
                                 ("centroid", centroid_map(process))):
            chains.append(series_chain(process, variant, mapping))
    return {"host": {"system": platform.system(), "machine": platform.machine()},
            "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "floorplan_data_sha256": hashlib.sha256(DATA.read_bytes()).hexdigest(),
            "scope": "Logical SVG site connectivity and Manhattan lower bounds; no routing or PEX",
            "fan_revision_history": history,
            "four_mim_series_chains": chains,
            "connectivity_benchmark": {
                "panels": len(panels), "repetitions_per_sample": 200,
                "median_ms_per_panel_pairwise": timed(panels, components_pairwise),
                "median_ms_per_panel_hash": timed(panels, components_hash),
                "meaning": "Python microbenchmark on small saved panels; not GNN/CNN training or full routing"}}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
