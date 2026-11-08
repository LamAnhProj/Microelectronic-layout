"""Compare saved GDS polygons by exact layer and canonicalized geometry."""

from __future__ import annotations

from collections import defaultdict


def ring_key(points: list[list[float]]) -> tuple[tuple[float, float], ...]:
    ring = tuple((float(x), float(y)) for x, y in points)
    if len(ring) > 1 and ring[0] == ring[-1]:
        ring = ring[:-1]
    if len(ring) < 3:
        raise ValueError("Degenerate GDS polygon ring")
    turns = [ring[i:] + ring[:i] for i in range(len(ring))]
    backward = ring[::-1]
    turns += [backward[i:] + backward[:i] for i in range(len(backward))]
    return min(turns)


def polygon_key(polygon: dict) -> tuple:
    return (ring_key(polygon["hull"]),
            tuple(sorted(ring_key(hole) for hole in polygon["holes"])))


def compare_layouts(old: dict, new: dict) -> dict:
    """Return shape indexes only in one layout, preserving duplicate polygons."""
    if old.get("top") != "inverter" or new.get("top") != "inverter":
        raise ValueError("Comparison requires two inverter top cells")
    old_layers = {layer["key"]: layer for layer in old["layers"]}
    new_layers = {layer["key"]: layer for layer in new["layers"]}
    old_only, new_only, per_layer = {}, {}, []
    for key in sorted(old_layers.keys() | new_layers.keys()):
        before = old_layers.get(key, {}).get("polygons", [])
        after = new_layers.get(key, {}).get("polygons", [])
        before_groups, after_groups = defaultdict(list), defaultdict(list)
        for index, polygon in enumerate(before):
            before_groups[polygon_key(polygon)].append(index)
        for index, polygon in enumerate(after):
            after_groups[polygon_key(polygon)].append(index)
        removed, added, common = [], [], 0
        for shape in before_groups.keys() | after_groups.keys():
            left, right = before_groups[shape], after_groups[shape]
            shared = min(len(left), len(right))
            common += shared
            removed.extend(left[shared:])
            added.extend(right[shared:])
        old_only[key], new_only[key] = sorted(removed), sorted(added)
        per_layer.append({"key": key,
                          "name": new_layers.get(key, old_layers.get(key))["name"],
                          "old": len(before), "new": len(after),
                          "old_only": len(removed), "new_only": len(added),
                          "shared": common})
    return {"old_only": old_only, "new_only": new_only,
            "removed_polygons": sum(len(items) for items in old_only.values()),
            "added_polygons": sum(len(items) for items in new_only.values()),
            "layers": per_layer}
