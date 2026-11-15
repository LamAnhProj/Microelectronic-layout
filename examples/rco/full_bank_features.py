"""Build terminal-aware, placement-only feature maps for all one-stage bank proposals.

Usage: python3 -m examples.rco.full_bank_features
This is a fast screening pass. It does not route nets or predict DRC/PEX.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import statistics
import time

from examples.rco.run import ROOT


VARIANTS = ("fan", "clustered", "centroid")
PROCESSES = ("sky130", "gf180")
GLOBAL_NETS = {"0", "vdd"}
TERMINALS = {"cap": ("top", "bottom"), "nmos": ("drain", "gate", "source", "body"),
             "pmos": ("drain", "gate", "source", "body")}
OUT = ROOT / "dashboard" / "static" / "full-bank-analysis.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def selected_run(process: str, variant: str) -> tuple[Path, dict, dict]:
    base = ROOT / "runs" / "rco" / "bank_placement" / process / variant
    reports = sorted(base.glob("*/report.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for file in reports:
        report = json.loads(file.read_text())
        folder = file.parent
        manifest_file = folder / "placement.json"
        gds = folder / "rco_bank_placement.gds"
        marker = folder / ("klayout_drc.xml" if process == "sky130" else "full.lyrdb")
        if (report.get("status") == "placement_drc_clear" and
                report.get("host") == {"system": "Darwin", "arch": "arm64"} and
                report.get("process") == process and report.get("variant") == variant and
                not report.get("corridor_probe") and report.get("magic_drc_errors") == 0 and
                report.get("klayout_drc_items") == 0 and
                all(p.is_file() for p in (manifest_file, gds, marker)) and
                digest(manifest_file) == report.get("placement_manifest_sha256") and
                digest(gds) == report.get("gds_sha256") and
                digest(marker) == report.get("marker_sha256")):
            manifest = json.loads(manifest_file.read_text())
            if manifest.get("process") == process and manifest.get("variant") == variant:
                return folder, report, manifest
    raise RuntimeError(f"No hash-verified Mac placement for {process}/{variant}")


def analyze(process: str, variant: str) -> dict:
    start = time.perf_counter_ns()
    folder, report, manifest = selected_run(process, variant)
    validated_ms = (time.perf_counter_ns() - start) / 1e6
    rows, cols = manifest["grid_rows_cols"]
    pitch = manifest["pitch_um_proposal"]
    entries = manifest["instances"]
    devices = [e for e in entries if e["kind"] != "dummy_cap"]
    by_name = {e["name"]: e for e in devices}
    dummies = [e for e in entries if e["kind"] == "dummy_cap"]
    expected_bits = ([8, 4, 2, 1, 2, 4, 8, 16, 32] if process == "sky130"
                     else [16, 8, 4, 2, 1, 2, 4, 8, 16])
    bits = Counter(int(e["name"].split("_")[1]) for e in devices
                   if e["name"].startswith("C0_"))
    kinds = Counter(e["kind"] for e in devices)
    sites = [tuple(e["grid_site"]) for e in entries if e["grid_site"] is not None]
    if (bits != Counter(dict(enumerate(expected_bits))) or
            kinds != {"cap": sum(expected_bits) + 1, "nmos": 10, "pmos": 10} or
            len(sites) != len(set(sites)) or "CBASE0" not in by_name or
            any(e.get("ground_connection_status") != "not_routed" for e in dummies)):
        raise RuntimeError(f"Incomplete or overlapping bank: {process}/{variant}")
    names = {e["name"] for e in devices}
    if len(names) != len(devices):
        raise RuntimeError("Duplicate device names")
    edges = []
    net_pins = defaultdict(list)
    nodes = []
    for e in devices:
        terminals = TERMINALS[e["kind"]]
        nets = e["nets_from_schematic"]
        if len(nets) != len(terminals):
            raise RuntimeError(f"Terminal count changed: {e['name']}")
        point = e["mim_plate_center_um"] or e["origin_um"]
        nodes.append({"id": e["name"], "kind": e["kind"], "bit":
                      int(e["name"].split("_")[1]) if e["name"].startswith("C0_") else None,
                      "site": e["grid_site"], "point_um": point})
        for terminal, net in zip(terminals, nets):
            edges.append({"device": e["name"], "terminal": terminal, "net": net})
            if net not in GLOBAL_NETS:
                net_pins[net].append((e["name"], point))
    graph_ms = (time.perf_counter_ns() - start) / 1e6 - validated_ms
    # Tile the capacitor core. Peripheral MOS pins are projected to the nearest
    # tile at the switch-facing edge. This projection is a location proxy.
    pin_map = [[0 for _ in range(cols)] for _ in range(rows)]
    route_map = [[0.0 for _ in range(cols)] for _ in range(rows)]
    site_by_name = {e["name"]: e["grid_site"] for e in devices}
    origin_x = min(e["mim_plate_center_um"][0] - e["grid_site"][1] * pitch
                   for e in devices if e["grid_site"] is not None)

    def tile(name: str, point: list[float]) -> tuple[int, int]:
        site = site_by_name[name]
        if site is not None:
            return max(0, min(rows - 1, site[0])), max(0, min(cols - 1, site[1]))
        return 0, max(0, min(cols - 1, round((point[0] - origin_x) / pitch)))

    for edge in edges:
        if edge["net"] in GLOBAL_NETS:
            continue
        device = by_name[edge["device"]]
        r, c = tile(device["name"], device["mim_plate_center_um"] or device["origin_um"])
        pin_map[r][c] += 1
    net_metrics = []
    for net, pins in net_pins.items():
        if len(pins) < 2:
            continue
        coords = [tile(name, point) for name, point in pins]
        r0, r1 = min(r for r, _ in coords), max(r for r, _ in coords)
        c0, c1 = min(c for _, c in coords), max(c for _, c in coords)
        hpwl = (r1 - r0 + c1 - c0) * pitch
        area = (r1 - r0 + 1) * (c1 - c0 + 1)
        demand = hpwl / area / pitch
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                route_map[r][c] += demand
        net_metrics.append({"net": net, "terminals": len(pins), "hpwl_um": round(hpwl, 2),
                            "bbox_tiles": [r0, c0, r1, c1]})
    active = {tuple(e["grid_site"]): e["name"] for e in devices if e["grid_site"] is not None}
    adjacency = []
    for (r, c), name in active.items():
        for other in ((r + 1, c), (r, c + 1)):
            if other in active:
                adjacency.append([name, active[other]])
    features_ms = (time.perf_counter_ns() - start) / 1e6 - validated_ms - graph_ms
    all_route = [value for row in route_map for value in row]
    all_pins = [value for row in pin_map for value in row]
    non_global_hpwl = sum(n["hpwl_um"] for n in net_metrics)
    # A screening order, not a physical performance prediction: lower is
    # cheaper by this geometry proxy. Route/DRC labels will test this order.
    score = non_global_hpwl / pitch + 10 * max(all_route) + 2 * max(all_pins)
    return {"process": process, "variant": variant, "run_id": folder.name,
            "gds_sha256": report["gds_sha256"], "placement_drc": "0 Magic / 0 KLayout",
            "rows": rows, "cols": cols, "pitch_um": pitch,
            "graph": {"devices": nodes, "terminals": edges,
                      "net_nodes": sorted(net_pins), "adjacent_cap_pairs": adjacency,
                      "dummy_count": len(dummies), "dummy_connection": "not routed"},
            "maps": {"pin_terminal_count": pin_map,
                     "rudy_proxy": [[round(v, 3) for v in row] for row in route_map]},
            "net_metrics": sorted(net_metrics, key=lambda n: -n["hpwl_um"]),
            "metrics": {"non_global_hpwl_um": round(non_global_hpwl, 2),
                        "max_pin_terminals_per_tile": max(all_pins),
                        "max_rudy_proxy": round(max(all_route), 3),
                        "mean_rudy_proxy": round(statistics.mean(all_route), 3),
                        "screening_score": round(score, 2)},
            "runtime_ms": {"validate_artifacts": round(validated_ms, 3),
                           "build_graph": round(graph_ms, 3),
                           "build_features_and_score": round(features_ms, 3),
                           "total": round((time.perf_counter_ns() - start) / 1e6, 3)}}


def main() -> None:
    if (platform.system(), platform.machine()) != ("Darwin", "arm64"):
        raise RuntimeError("Run this comparison on the native Apple silicon Mac")
    start = time.perf_counter_ns()
    candidates = [analyze(p, v) for p in PROCESSES for v in VARIANTS]
    for process in PROCESSES:
        ranked = sorted((c for c in candidates if c["process"] == process),
                        key=lambda c: c["metrics"]["screening_score"])
        for rank, candidate in enumerate(ranked, 1):
            candidate["screening_rank_within_pdk"] = rank
    payload = {"schema_version": 1, "generated_utc": datetime.now(timezone.utc).isoformat(),
               "builder_sha256": digest(Path(__file__)),
               "host": {"system": platform.system(), "architecture": platform.machine(),
                        "python": platform.python_version()},
               "methods": ["SHA256 verification of Mac placement DRC report, manifest, GDS and marker",
                           "heterogeneous device-net graph with terminal roles; capacitor tile adjacency",
                           "non-global terminal density, projected peripheral MOS terminals",
                           "tile RUDY proxy = net bounding-box HPWL / bounding-box tile area / pitch",
                           "within-PDK screening score = HPWL/pitch + 10×peak RUDY + 2×peak pin count"],
               "limitations": ["No routes, real pin coordinates, metal layer capacities, grounded dummy ties, LVS, PEX or post-layout timing",
                               "Supply and ground nets omitted from demand; switch and base-cap pins projected onto core edge",
                               "RUDY and rank are placement proxies, not RouteNet predictions or physical signoff"],
               "candidates": candidates,
               "runtime_ms": {"batch_total": round((time.perf_counter_ns() - start) / 1e6, 3)}}
    OUT.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"Wrote {OUT}; {len(candidates)} candidates in {payload['runtime_ms']['batch_total']} ms")
    for c in candidates:
        print(c["process"], c["variant"], c["screening_rank_within_pdk"], c["metrics"], c["runtime_ms"]["total"])


if __name__ == "__main__":
    main()
