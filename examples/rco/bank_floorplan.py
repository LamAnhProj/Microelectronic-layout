"""Mirrored logical sites for one RCO trim bank; no electrical routing yet.

The fan's 17-site entry row holds eight mirrored pairs and a singleton. Its
upper rows have 16 physically adjacent sites, shifted inward by half a pitch.
Only edge sites remain dummy inside the fan; both styles retain a dummy ring.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from examples.rco.run import passive_lines


GRID = {"sky130": (5, 17), "gf180": (5, 17)}  # core; row 0 faces switches
FAN_GRID = {"sky130": (5, 17), "gf180": (4, 17)}
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
    single = singleton_bit(process)
    order = [bit for bit in range(8, -1, -1) if bit != single]
    result = {single: (8,)}
    for distance, bit in enumerate(order, start=1):
        result[bit] = (8 - distance, 8 + distance)
    return result


def fan_map(process: str) -> dict[str, tuple[int, int]]:
    rows, _ = FAN_GRID[process]
    names = units(process)
    placed: dict[str, tuple[int, int]] = {}
    occupied: set[tuple[int, int]] = set()
    entry = entry_columns(process)
    for bit, columns in entry.items():
        for col in columns:
            name = names[bit].pop(0)
            placed[name] = (0, col)
            occupied.add((0, col))
    # Place remaining units as mirrored pairs, clustered near their entry pair.
    for bit in sorted(names, reverse=True):
        left_anchor = min(entry[bit])
        while names[bit]:
            candidates = [(row, col) for row in range(1, rows)
                          for col in range(8)
                          if not (row == rows - 1 and col in (0, 1))
                          if (row, col) not in occupied and
                          (row, 16 - col) not in occupied]
            if not candidates or len(names[bit]) < 2:
                raise RuntimeError("Fan pair allocation failed")
            row, col = min(candidates, key=lambda pos: (
                abs(pos[1] - left_anchor) + pos[0], pos[0],
                abs(pos[1] - left_anchor), pos[1]))
            for site in ((row, col), (row, 16 - col)):
                placed[names[bit].pop(0)] = site
                occupied.add(site)
    _check_map(process, placed, require_entry=True)
    return placed


def centroid_map(process: str) -> dict[str, tuple[int, int]]:
    names = units(process)
    placed: dict[str, tuple[int, int]] = {}
    single = singleton_bit(process)
    placed[names[single].pop(0)] = (2, 8)
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
    # A quartet is mirrored in x and y; every bit centroid is (2, 8).
    quartets = [(row, left) for row in (1, 3, 0, 4) for left in range(8)
                if row < 2]
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
               require_entry: bool = False) -> None:
    expected = {name for group in units(process).values() for name in group}
    rows, cols = (FAN_GRID if require_entry else GRID)[process]
    if set(placed) != expected or len(set(placed.values())) != len(placed):
        raise RuntimeError("Missing or overlapping capacitor positions")
    if any(not (0 <= row < rows and 0 <= col < cols)
           for row, col in placed.values()):
        raise RuntimeError("Capacitor outside the core")
    for bit in range(9):
        positions = {pos for name, pos in placed.items()
                     if int(name.split("_")[1]) == bit}
        if { (row, cols - 1 - col) for row, col in positions} != positions:
            raise RuntimeError(f"Bit {bit} lacks left-right symmetry")
        if require_entry and set((0, col) for col in entry_columns(process)[bit]) \
                != {pos for pos in positions if pos[0] == 0}:
            raise RuntimeError(f"Bit {bit} lacks the entry-row placement")
    if require_entry:
        empty_core = {(row, col) for row in range(rows)
                      for col in (range(cols) if row == 0 else
                                  tuple(range(8)) + tuple(range(9, cols)))} \
                     - set(placed.values())
        if empty_core != {(rows - 1, col) for col in (0, 1, 15, 16)}:
            raise RuntimeError("Fan has an interior dummy or disconnected row")


def dummy_sites(process: str, variant: str) -> set[tuple[int, int]]:
    if variant not in ("fan", "centroid"):
        raise ValueError("Choose fan or centroid")
    placed = fan_map(process) if variant == "fan" else centroid_map(process)
    rows, cols = (FAN_GRID if variant == "fan" else GRID)[process]
    return {(row, col) for row in range(-1, rows + 1)
            for col in (range(-1, cols + 1) if variant == "centroid" or row <= 0
                        else tuple(range(-1, 8)) + tuple(range(9, cols + 1)))} \
           - set(placed.values())


def site_x(process: str, variant: str, row: int, col: int,
           pitch: float, origin: float = 0.0) -> float:
    """Physical x coordinate; upper fan halves close the vacant center slot."""
    if process not in GRID or variant not in ("fan", "centroid"):
        raise ValueError("Choose a PDK and fan or centroid")
    if variant == "fan" and row > 0:
        if col == 8:
            raise ValueError("Upper fan rows have no center site")
        return origin + (col + 0.5 if col < 8 else col - 0.5) * pitch
    return origin + col * pitch


def text_map(process: str, variant: str) -> str:
    placed = fan_map(process) if variant == "fan" else centroid_map(process)
    cells = {pos: int(name.split("_")[1]) for name, pos in placed.items()}
    rows, cols = (FAN_GRID if variant == "fan" else GRID)[process]
    return "\n".join(" ".join(str(cells.get((row, col), "D"))
                               for col in (range(-1, cols + 1)
                                           if variant == "centroid" or row <= 0 else
                                           tuple(range(-1, 8)) + tuple(range(9, cols + 1))))
                     for row in reversed(range(-1, rows + 1)))


def svg() -> str:
    width, height = 1480, 730
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
             '<rect width="100%" height="100%" fill="#101827"/>',
             '<style>text{font-family:Arial,sans-serif;fill:#e9f0fb}.title{font-size:17px;font-weight:bold}.small{font-size:12px}.bit{font-size:11px;font-weight:bold;text-anchor:middle;dominant-baseline:middle}</style>',
             '<text x="28" y="30" class="title">RCO one-stage capacitor-bank placement proposals</text>',
             '<text x="28" y="50" class="small">Numbers are trim bits. D = intended grounded dummy, including full perimeter. Sites are mirrored; no routes or ground ties drawn.</text>']
    for process_index, process in enumerate(("sky130", "gf180")):
        for variant_index, variant in enumerate(("fan", "centroid")):
            x0, y0 = 30 + variant_index * 730, 80 + process_index * 330
            rows, cols = (FAN_GRID if variant == "fan" else GRID)[process]
            mapping = fan_map(process) if variant == "fan" else centroid_map(process)
            cells = {pos: int(name.split("_")[1]) for name, pos in mapping.items()}
            label = f'{"SKY130A" if process == "sky130" else "GF180MCU D"} · {"edge fan" if variant == "fan" else "common centroid"} · {rows}×{cols} core'
            parts.append(f'<text x="{x0}" y="{y0}" class="title">{label}</text>')
            for row in range(-1, rows + 1):
                columns = (range(-1, cols + 1) if variant == "centroid" or row <= 0
                           else tuple(range(-1, 8)) + tuple(range(9, cols + 1)))
                for col in columns:
                    bit = cells.get((row, col))
                    x = site_x(process, variant, row, col, 37, x0 + 37)
                    y = y0 + 18 + (rows - row) * 31
                    fill = COLORS[bit] if bit is not None else "#394357"
                    parts.append(f'<rect x="{x}" y="{y}" width="34" height="28" rx="3" fill="{fill}"/>')
                    parts.append(f'<text x="{x+17}" y="{y+14}" class="bit">{bit if bit is not None else "D"}</text>')
            if variant == "fan":
                parts.append(f'<text x="{x0}" y="{y0+245}" class="small">bottom active row faces switches; MSB pair straddles center singleton</text>')
    parts.append('<text x="30" y="720" class="small">Fan upper rows close the central slot; centroid retains its regular grid. Base MIM sits outside. Dummy plates require ground routes and LVS.</text>')
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


if __name__ == "__main__":
    path = Path(__file__).with_name("bank-floorplans.svg")
    path.write_text(svg())
    print(path)
    for process in GRID:
        for variant in ("fan", "centroid"):
            placed = fan_map(process) if variant == "fan" else centroid_map(process)
            print(process, variant, "active", len(placed), "dummies", len(dummy_sites(process, variant)),
                  "bits", dict(Counter(int(name.split("_")[1]) for name in placed)))
