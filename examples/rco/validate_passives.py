"""Validate isolated RCO passive PCells on the native Mac, not the whole RCO.

Usage: python3 examples/rco/validate_passives.py sky130
       python3 examples/rco/validate_passives.py gf180
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
import uuid

from run import CONFIG, PDK_ROOT, PIN, ROOT


HERE = Path(__file__).resolve().parent
KLAYOUT = Path("/Applications/klayout.app/Contents/MacOS/klayout")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def execute(args: list[str], *, cwd: Path, input_text: str | None,
            log: Path) -> str:
    result = subprocess.run(args, cwd=cwd, input=input_text, text=True,
                            capture_output=True, timeout=180)
    output = result.stdout + result.stderr
    log.write_text(output)
    if result.returncode:
        raise RuntimeError(f"{args[0]} exited {result.returncode}; inspect {log}")
    return output


def gf_deck(folder: Path) -> Path:
    rules = PDK_ROOT / "gf180mcuD" / "libs.tech" / "klayout" / "drc" / "rule_decks"
    deckdir = folder / "klayout_deck"
    deckdir.mkdir(exist_ok=True)
    shutil.copyfile(rules / "layers_def.drc", deckdir / "layers_def.drc")
    excluded = {"antenna.drc", "density.drc", "main.drc", "layers_def.drc", "tail.drc"}
    names = ["main.drc"] + [path.name for path in sorted(rules.glob("*.drc"))
                            if path.name not in excluded] + ["tail.drc"]
    body = "\n".join((rules / name).read_text() for name in names)
    old = "`pmap #{Process.pid} | tail -1`[10, 40].strip"
    new = "`ps -o rss= -p #{Process.pid}`.strip + ' KiB'"
    if body.count(old) != 1:
        raise RuntimeError("GF vendor DRC logger changed; review the Mac adapter")
    deck = deckdir / "main.drc"
    deck.write_text(body.replace(old, new))
    return deck


def validate(process: str) -> dict:
    if process not in CONFIG:
        raise ValueError("Choose sky130 or gf180")
    if (platform.system(), platform.machine()) != ("Darwin", "arm64"):
        raise RuntimeError("This validates native Mac execution only")
    pdk = PDK_ROOT / CONFIG[process]["pdk"]
    if PIN not in str(pdk.resolve()) or not KLAYOUT.is_file():
        raise RuntimeError("Pinned PDK or native KLayout is unavailable")
    run_id = str(uuid.uuid4())
    folder = ROOT / "runs" / "rco" / "passive_probe" / process / run_id
    folder.mkdir(parents=True, exist_ok=True)
    source = HERE / process / "passive_probe.tcl"
    rcfile = f"/pdk/{pdk.name}/libs.tech/magic/{pdk.name}.magicrc"
    magic = execute(["docker", "compose", "run", "--rm", "-v",
                     f"{PDK_ROOT}:/pdk:ro", "-e", "PDK_ROOT=/pdk",
                     "--workdir", f"/results/rco/passive_probe/{process}/{run_id}",
                     "--entrypoint", "magic", "worker", "-dnull", "-noconsole",
                     "-rcfile", rcfile], cwd=ROOT, input_text=source.read_text(),
                    log=folder / "magic.log")
    counts = re.findall(r"Total DRC errors found: (\d+)", magic)
    if (len(counts) != 1 or counts[0] != "0" or
            "GDS_FEEDBACK_COUNT=0" not in magic or
            f'Using technology "{pdk.name}"' not in magic):
        raise RuntimeError("Magic passive PCell DRC or export did not pass")
    gds = folder / "rco_passive_probe.gds"
    extracted = folder / "rco_passive_probe.spice"
    if not gds.is_file() or not extracted.is_file():
        raise RuntimeError("Passive PCell GDS or extracted netlist is missing")
    content = extracted.read_text()
    wanted = (["sky130_fd_pr__cap_mim_m3_2 l=4.5 w=4.5",
               "sky130_fd_pr__res_xhigh_po_1p41 l=330"] if process == "sky130" else
              ["cap_mim_2f0_m4m5_noshield c_width=5u c_length=5u",
               "cap_mim_2f0_m4m5_noshield c_width=7u c_length=7u",
               "ppolyf_u_1k r_width=1u r_length=0.44m"])
    if not all(part in content for part in wanted):
        raise RuntimeError("Magic extracted unexpected passive model or geometry")
    if process == "sky130":
        deck = pdk / "libs.tech" / "klayout" / "drc" / "sky130A_mr.drc"
        marker = folder / "klayout_drc.xml"
        args = [str(KLAYOUT), "-b", "-r", str(deck), "-rd", f"input={gds}",
                "-rd", "top_cell=rco_passive_probe", "-rd", f"report={marker}",
                "-rd", "feol=true", "-rd", "beol=true", "-rd", "offgrid=true",
                "-rd", "seal=false", "-rd", "thr=2"]
    else:
        deck = gf_deck(folder)
        marker = folder / "full.lyrdb"
        args = [str(KLAYOUT), "-b", "-r", str(deck), "-rd", "thr=1",
                "-rd", "metal_top=11K", "-rd", "mim_option=B", "-rd",
                "metal_level=5LM", "-rd", "feol=true", "-rd", "beol=true",
                "-rd", "offgrid=true", "-rd", "conn_drc=true", "-rd",
                "density=false", "-rd", "topcell=rco_passive_probe", "-rd",
                f"input={gds}", "-rd", f"report={marker}", "-rd",
                "run_mode=flat", "-rd", "table_name=main"]
    execute(args, cwd=ROOT, input_text=None, log=folder / "klayout.log")
    markers = ET.parse(marker).getroot().findall(".//item")
    report = {"status": "pass" if not markers else "failed", "process": process,
              "host": {"system": platform.system(), "arch": platform.machine()},
              "pdk_pin": PIN, "scope": "isolated MIM and high-R poly PCells only; no RCO layout, LVS, or PEX",
              "magic_drc_errors": 0, "klayout_drc_items": len(markers),
              "models": wanted, "source_sha256": digest(source),
              "gds_sha256": digest(gds), "extracted_sha256": digest(extracted),
              "drc_deck_sha256": digest(deck), "marker_sha256": digest(marker),
              "report_dir": str(folder)}
    (folder / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("process", choices=CONFIG)
    args = parser.parse_args()
    print(json.dumps(validate(args.process), indent=2))
