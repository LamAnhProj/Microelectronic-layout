"""RCO trim-bank placement proposals with PDK unit counts.

The fan uses one connected block per bit and places the MSB on its outer edge.
The centered grouped map keeps every bit connected; the exact centroid is a
separate interdigitated teaching reference because two-unit groups cannot
both edge-touch and share the singleton's centroid on this grid.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from examples.rco.run import passive_lines


GRID = {"sky130": (5, 17), "gf180": (5, 17)}  # core; row 0 faces switches
FAN_GRID = {"sky130": (4, 21), "gf180": (4, 17)}
FAN_ORDER = {"sky130": (3, 2, 4, 1, 0, 5, 6, 7, 8),
             "gf180": (4, 3, 5, 2, 1, 0, 6, 7, 8)}
CLUSTER_ORDER = {"sky130": (3, 0, 1, 6, 8, 7, 5, 4, 2),
                 "gf180": (4, 0, 1, 8, 6, 7, 2, 3, 5)}
NARROW_SPAN = {"sky130": (1, 15), "gf180": (3, 13)}
STYLE = {"sky130": "binary", "gf180": "balanced"}
COLORS = ("#16a6a4", "#57a5db", "#8b75d6", "#cc6ec3", "#e67b9b",
          "#f3956b", "#ddb64d", "#a6ba46", "#477e47")


def units(process: str) -> dict[int, list[str]]:
    if process not in GRID:
        raise ValueError("Choose sky130 or gf180")
    return {bit: [line.split()[0][1:] for line in passive_lines(
        process, 0, bit, f"cap0_{bit}", STYLE[process])]
        for bit in range(9)}


def singleton_bit(process: str) -> int:
    odd = [bit for bit, names in units(process).items() if len(names) % 2]
    if len(odd) != 1:
        raise RuntimeError("This grid requires exactly one odd population")
    return odd[0]


def entry_columns(process: str) -> dict[int, tuple[int, ...]]:
    return {bit: (start,) for bit, (start, _) in fan_stripes(process).items()}


def _stripes(process: str, order: tuple[int, ...]) -> dict[int, tuple[int, int]]:
    if process not in FAN_GRID:
        raise ValueError("Choose sky130 or gf180")
    counts = {bit: len(names) for bit, names in units(process).items()}
    start = 0
    result = {}
    for bit in order:
        width = (counts[bit] + 3) // 4
        result[bit] = (start, width)
        start += width
    if start != FAN_GRID[process][1]:
        raise RuntimeError("Fan stripe widths do not fit the core")
    return result


def fan_stripes(process: str) -> dict[int, tuple[int, int]]:
    return _stripes(process, FAN_ORDER[process])


def clustered_stripes(process: str) -> dict[int, tuple[int, int]]:
    return _stripes(process, CLUSTER_ORDER[process])


def active_sites(process: str, variant: str) -> set[tuple[int, int]]:
    if process not in GRID or variant not in ("fan", "clustered", "centroid"):
        raise ValueError("Choose a PDK and fan, clustered, or centroid")
    if variant in ("fan", "clustered"):
        result = set()
        stripes = fan_stripes(process) if variant == "fan" else clustered_stripes(process)
        for bit, (start, width) in stripes.items():
            count = len(units(process)[bit])
            if count < 4:
                start_row = 0 if variant == "fan" else 1
                result.update((row, start) for row in range(start_row, start_row + count))
            else:
                result.update((row, col) for row in range(4)
                              for col in range(start, start + width))
        return result
    rows, cols = GRID[process]
    left, right = NARROW_SPAN[process]
    full_row = 0 if variant == "fan" else rows // 2
    return {(row, col) for row in range(rows)
            for col in (range(cols) if row == full_row else
                        range(left, right + 1))}


def fan_map(process: str) -> dict[str, tuple[int, int]]:
    names = units(process)
    placed: dict[str, tuple[int, int]] = {}
    for bit, (start, width) in fan_stripes(process).items():
        count = len(names[bit])
        if count < 4:
            sites = [(row, start) for row in range(count)]
        else:
            # A serpentine walk keeps successive series elements adjacent.
            sites = [(row, col) for row in range(4)
                     for col in (range(start, start + width) if row % 2 == 0
                                 else range(start + width - 1, start - 1, -1))]
        if len(sites) != count:
            raise RuntimeError(f"Bit {bit} does not fill its fan stripe")
        placed.update(zip(names[bit], sites))
    _check_map(process, placed, require_entry=True)
    return placed


def clustered_map(process: str) -> dict[str, tuple[int, int]]:
    """Connected-bit reference, with the MSB near the center; not exact CC."""
    names = units(process)
    placed: dict[str, tuple[int, int]] = {}
    for bit, (start, width) in clustered_stripes(process).items():
        count = len(names[bit])
        if count < 4:
            sites = [(row, start) for row in range(1, 1 + count)]
        else:
            sites = [(row, col) for row in range(4)
                     for col in (range(start, start + width) if row % 2 == 0
                                 else range(start + width - 1, start - 1, -1))]
        if len(sites) != count:
            raise RuntimeError(f"Bit {bit} does not fill its clustered stripe")
        placed.update(zip(names[bit], sites))
    _check_map(process, placed, clustered=True)
    return placed


def centroid_map(process: str) -> dict[str, tuple[int, int]]:
    names = units(process)
    placed: dict[str, tuple[int, int]] = {}
    single = singleton_bit(process)
    placed[names[single].pop(0)] = (2, 8)
    for row in (0, 1, 3, 4):
        placed[names[8].pop(0)] = (row, 8)
    center_pairs = [(2, col, 16 - col) for col in (7, 5, 3, 1, 6, 4, 2, 0)]
    # Two-unit groups and two four-unit groups fit the middle row.
    small = [bit for bit in range(9) if len(names[bit]) == 2]
    four = [bit for bit in range(9) if len(names[bit]) == 4]
    if len(small) != 2 or len(four) != 2:
        raise RuntimeError("Centroid middle-row packing changed")
    for bit, pair_count in [(b, 1) for b in small] + [(b, 2) for b in four]:
        for _ in range(pair_count):
            row, left, right = center_pairs.pop(0)
            placed[names[bit].pop(0)] = (row, left)
            placed[names[bit].pop(0)] = (row, right)
    for row, left, right in center_pairs:
        placed[names[8].pop(0)] = (row, left)
        placed[names[8].pop(0)] = (row, right)
    # A quartet is mirrored in x and y; every bit centroid is (2, 8).
    left_edge, _ = NARROW_SPAN[process]
    quartets = [(row, left) for row in (0, 1)
                for left in range(left_edge, 8)]
    quartets.sort(key=lambda site: ((site[0] - 2) ** 2 +
                                    (site[1] - 8) ** 2, site))
    for bit in sorted(names, reverse=True):
        while names[bit]:
            if len(names[bit]) < 4 or not quartets:
                raise RuntimeError("Centroid quartet allocation failed")
            row, col = quartets.pop(0)
            for site in ((row, col), (row, 16 - col),
                         (4 - row, col), (4 - row, 16 - col)):
                placed[names[bit].pop(0)] = site
    _check_map(process, placed)
    for bit in range(9):
        points = [pos for name, pos in placed.items()
                  if int(name.split("_")[1]) == bit]
        if sum(row for row, _ in points) != 2 * len(points) or \
                sum(col for _, col in points) != 8 * len(points):
            raise RuntimeError(f"Bit {bit} is not centroid-balanced")
    return placed


def _check_map(process: str, placed: dict[str, tuple[int, int]],
               require_entry: bool = False, clustered: bool = False) -> None:
    if require_entry and clustered:
        raise ValueError("Choose one placement style")
    expected = {name for group in units(process).values() for name in group}
    rows, cols = (FAN_GRID if require_entry or clustered else GRID)[process]
    if set(placed) != expected or len(set(placed.values())) != len(placed):
        raise RuntimeError("Missing or overlapping capacitor positions")
    if any(not (0 <= row < rows and 0 <= col < cols)
           for row, col in placed.values()):
        raise RuntimeError("Capacitor outside the core")
    for bit in range(9):
        positions = {pos for name, pos in placed.items()
                     if int(name.split("_")[1]) == bit}
        if require_entry or clustered:
            start = entry_columns(process)[bit][0]
            if require_entry and placed[units(process)[bit][0]] != (0, start):
                raise RuntimeError(f"Bit {bit} lacks its switch-facing entry")
            unseen = set(positions)
            stack = [unseen.pop()]
            while stack:
                row, col = stack.pop()
                for neighbor in ((row-1, col), (row+1, col),
                                 (row, col-1), (row, col+1)):
                    if neighbor in unseen:
                        unseen.remove(neighbor)
                        stack.append(neighbor)
            if unseen:
                raise RuntimeError(f"Bit {bit} is not one connected cluster")
        elif {(row, cols - 1 - col) for row, col in positions} != positions:
            raise RuntimeError(f"Bit {bit} lacks left-right symmetry")
    variant = "fan" if require_entry else "clustered" if clustered else "centroid"
    if set(placed.values()) != active_sites(process, variant):
        raise RuntimeError(f"{variant} has a gap in its active row span")


def dummy_sites(process: str, variant: str) -> set[tuple[int, int]]:
    if variant not in ("fan", "clustered", "centroid"):
        raise ValueError("Choose fan, clustered, or centroid")
    placed = (fan_map(process) if variant == "fan" else
              clustered_map(process) if variant == "clustered" else centroid_map(process))
    rows, cols = (FAN_GRID if variant in ("fan", "clustered") else GRID)[process]
    return {(row, col) for row in range(-1, rows + 1)
            for col in range(-1, cols + 1)} - set(placed.values())


def site_x(process: str, variant: str, row: int, col: int,
           pitch: float, origin: float = 0.0) -> float:
    """Every MIM site uses the same column lattice; no row staggering."""
    if process not in GRID or variant not in ("fan", "clustered", "centroid"):
        raise ValueError("Choose a PDK and fan, clustered, or centroid")
    return origin + col * pitch


def text_map(process: str, variant: str) -> str:
    placed = (fan_map(process) if variant == "fan" else
              clustered_map(process) if variant == "clustered" else centroid_map(process))
    cells = {pos: int(name.split("_")[1]) for name, pos in placed.items()}
    rows, cols = (FAN_GRID if variant in ("fan", "clustered") else GRID)[process]
    return "\n".join(" ".join(str(cells.get((row, col), "D"))
                               for col in range(-1, cols + 1))
                     for row in reversed(range(-1, rows + 1)))


def svg(variants: tuple[str, ...] = ("fan", "clustered")) -> str:
    width, height = 40 + 900 * len(variants), 730
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
             '<rect width="100%" height="100%" fill="#101827"/>',
             '<style>text{font-family:Arial,sans-serif;fill:#e9f0fb}.title{font-size:17px;font-weight:bold}.small{font-size:12px}.bit{font-size:11px;font-weight:bold;text-anchor:middle;dominant-baseline:middle}</style>',
             '<text x="28" y="30" class="title">RCO one-stage capacitor-bank placement proposals</text>',
             '<text x="28" y="50" class="small">Numbers are trim bits. D = intended grounded dummy, including full perimeter. MIM centers share one grid; routes and ground ties are not drawn.</text>']
    for process_index, process in enumerate(("sky130", "gf180")):
        for variant_index, variant in enumerate(variants):
            x0, y0 = 30 + variant_index * 900, 80 + process_index * 330
            rows, cols = (FAN_GRID if variant in ("fan", "clustered") else GRID)[process]
            mapping = (fan_map(process) if variant == "fan" else
                       clustered_map(process) if variant == "clustered" else centroid_map(process))
            cells = {pos: int(name.split("_")[1]) for name, pos in mapping.items()}
            style = {"fan": "outer-edge grouped fan", "clustered": "centered grouped reference",
                     "centroid": "exact common centroid"}[variant]
            label = f'{"SKY130A" if process == "sky130" else "GF180MCU D"} · {style} · {rows}×{cols} core'
            parts.append(f'<text x="{x0}" y="{y0}" class="title">{label}</text>')
            for row in range(-1, rows + 1):
                for col in range(-1, cols + 1):
                    bit = cells.get((row, col))
                    x = site_x(process, variant, row, col, 37, x0 + 37)
                    y = y0 + 18 + (rows - row) * 31
                    fill = COLORS[bit] if bit is not None else "#394357"
                    parts.append(f'<rect x="{x}" y="{y}" width="34" height="28" rx="3" fill="{fill}"/>')
                    parts.append(f'<text x="{x+17}" y="{y+14}" class="bit">{bit if bit is not None else "D"}</text>')
            if variant == "fan":
                parts.append(f'<text x="{x0}" y="{y0+225}" class="small">bit 8 at outer edge; each bit has a bottom-row switch entry</text>')
            elif variant == "clustered":
                parts.append(f'<text x="{x0}" y="{y0+225}" class="small">all bit groups connected; MSB near center; not exact common centroid</text>')
            else:
                parts.append(f'<text x="{x0}" y="{y0+245}" class="small">exact centroids require separated small-bit cells</text>')
    parts.append('<text x="30" y="720" class="small">Each active bit group is edge-connected in the two main proposals. Dummies occupy outer edges and the ring; ground routes, LVS, and PEX remain open.</text>')
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


if __name__ == "__main__":
    path = Path(__file__).with_name("bank-floorplans.svg")
    path.write_text(svg())
    print(path)
    reference = Path(__file__).with_name("bank-centroid-reference.svg")
    reference.write_text(svg(("centroid",)))
    print(reference)
    for process in GRID:
        for variant in ("fan", "clustered", "centroid"):
            placed = (fan_map(process) if variant == "fan" else
                      clustered_map(process) if variant == "clustered" else centroid_map(process))
            print(process, variant, "active", len(placed), "dummies", len(dummy_sites(process, variant)),
                  "bits", dict(Counter(int(name.split("_")[1]) for name in placed)))
