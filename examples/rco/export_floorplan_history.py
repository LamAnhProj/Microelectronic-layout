"""Export the preserved floorplan SVG tiles for the browser placement sandbox.

The SVGs stay immutable. This file reads their actual colored MIM sites so
the editor starts from each saved revision, including the staggered draft.
"""

from __future__ import annotations

import json
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[2]
HISTORY = ROOT / "examples" / "rco" / "floorplan-history"
OUTPUT = ROOT / "dashboard" / "static" / "floorplan-data.json"
SVG = "{http://www.w3.org/2000/svg}"


def panels_from_svg(path: Path) -> list[dict]:
    root = ET.parse(path).getroot()
    elements = list(root)
    headings = [
        {"x": float(node.attrib["x"]), "y": float(node.attrib["y"]),
         "title": node.text or ""}
        for node in elements if node.tag == SVG + "text"
        and node.attrib.get("class") == "title"
        and ("SKY130A" in (node.text or "") or "GF180MCU" in (node.text or ""))
    ]
    rows = sorted({heading["y"] for heading in headings})
    groups = {heading["title"]: [] for heading in headings}
    for rect, label in zip(elements, elements[1:]):
        if rect.tag != SVG + "rect" or label.tag != SVG + "text":
            continue
        if label.attrib.get("class") != "bit":
            continue
        x, y = float(rect.attrib["x"]), float(rect.attrib["y"])
        row = max((value for value in rows if value < y), default=None)
        if row is None:
            raise ValueError(f"Tile above all headings in {path}")
        candidates = [heading for heading in headings if heading["y"] == row
                      and heading["x"] <= x]
        if not candidates:
            raise ValueError(f"Tile outside heading columns in {path}")
        heading = max(candidates, key=lambda item: item["x"])
        bit = label.text or ""
        if bit not in {"D", *map(str, range(9))}:
            raise ValueError(f"Unexpected bit {bit!r} in {path}")
        groups[heading["title"]].append({"x": x, "y": y, "bit": bit})
    output = []
    for heading in headings:
        tiles = groups[heading["title"]]
        xs, ys = sorted({tile["x"] for tile in tiles}), sorted({tile["y"] for tile in tiles})
        if not xs or not ys:
            raise ValueError(f"Empty panel {heading['title']} in {path}")
        for tile in tiles:
            row_tiles = sorted((other for other in tiles if other["y"] == tile["y"]),
                               key=lambda item: item["x"])
            tile["locked"] = (tile["y"] in (ys[0], ys[-1]) or
                              tile is row_tiles[0] or tile is row_tiles[-1])
            if tile["locked"] and tile["bit"] != "D":
                raise ValueError(f"Active MIM on perimeter in {path}: {heading['title']} {tile}")
        for tile in tiles:
            tile["x"] = round(tile["x"] - xs[0], 3)
            tile["y"] = round(tile["y"] - ys[0], 3)
        counts = {str(bit): sum(tile["bit"] == str(bit) for tile in tiles)
                  for bit in range(9)}
        process = "sky130" if "SKY130A" in heading["title"] else "gf180"
        name = ("fan" if "fan" in heading["title"] else
                "exact-centroid" if "centroid" in heading["title"] else
                "grouped-reference")
        output.append({"id": f"{process}-{name}", "title": heading["title"],
                       "process": process, "counts": counts,
                       "total": sum(counts.values()), "width": round(xs[-1] - xs[0] + 34, 3),
                       "height": round(ys[-1] - ys[0] + 28, 3), "tiles": tiles})
    return output


def main() -> None:
    revisions = []
    for path in sorted(HISTORY.glob("*.svg")):
        revisions.append({"id": path.name, "panels": panels_from_svg(path)})
    OUTPUT.write_text(json.dumps({"revisions": revisions}, separators=(",", ":")) + "\n")
    print(f"Exported {sum(len(item['panels']) for item in revisions)} panels to {OUTPUT}")


if __name__ == "__main__":
    main()
