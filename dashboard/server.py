"""Loopback-only dashboard for the local semiconductor lab.

Launch with: uv run --frozen --extra layout python dashboard/server.py
"""

from __future__ import annotations

import hashlib
import json
import math
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import threading
import uuid
from urllib.parse import parse_qs, urlsplit
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
STATIC = Path(__file__).resolve().parent / "static"
RUNS = ROOT / "runs"
PDK_ROOT = ROOT / "pdks" / "volare"
TOKEN = secrets.token_urlsafe(32)
UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
PROCESSES = {
    "sky130": {"title": "SKY130A", "folder": "sky130_inverter", "pdk": "sky130A",
               "voltage": 1.8, "channel": "0.15 µm", "n_width": "1 µm",
               "p_width": "2 µm", "corner": "tt", "min_v": 0.9},
    "gf180": {"title": "GF180MCU D", "folder": "gf180_inverter", "pdk": "gf180mcuD",
              "voltage": 3.3, "channel": "0.28 µm", "n_width": "1 µm",
              "p_width": "2 µm", "corner": "typical", "min_v": 1.65},
}
DOCS = [
    "README.md", "dashboard/README.md", "docs/validation.md",
    "docs/setup-macos.md", "docs/pdks-and-data.md",
    "docs/architecture.md", "docs/bridge.md", "docs/agent-workflow.md",
    "docs/learning-plan.md", "docs/storage-r2.md",
    "docs/CONTINUE-SETUP.md", "docs/publish-from-mac.md",
    "knowledge/circuit-reasoning.md", "knowledge/layout-judgment.md",
    "knowledge/debug-and-evidence.md", "examples/sky130_inverter/README.md",
    "examples/gf180_inverter/README.md",
]
JOBS: dict[str, dict] = {}
JOB_LOCK = threading.Lock()
TRACE_LOCK = threading.Lock()


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run_path(process: str, run_id: str) -> Path:
    if process not in PROCESSES or not UUID.fullmatch(run_id):
        raise ValueError("Unknown process or run ID")
    path = RUNS / PROCESSES[process]["folder"] / run_id
    if not (path / "report.json").is_file():
        raise ValueError("Run report not found")
    return path


def run_list(process: str) -> list[dict]:
    folder = RUNS / PROCESSES[process]["folder"]
    results = []
    if folder.is_dir():
        for path in folder.iterdir():
            if not path.is_dir() or not UUID.fullmatch(path.name):
                continue
            report_file = path / "report.json"
            if not report_file.is_file():
                continue
            try:
                report = json.loads(report_file.read_text())
                results.append({"id": path.name, "status": report.get("status", "unknown"),
                                "modified": report_file.stat().st_mtime})
            except (OSError, json.JSONDecodeError):
                continue
    return sorted(results, key=lambda item: item["modified"], reverse=True)


def report_data(process: str, run_id: str) -> dict:
    path = run_path(process, run_id)
    report = json.loads((path / "report.json").read_text())
    artifacts = []
    for name in report.get("evidence_sha256", {}):
        if name.endswith((".spice", ".tcl", ".log", ".txt", ".xml", ".lyrdb")):
            artifacts.append(name)
    report["artifacts"] = sorted(artifacts)
    return report


def artifact_text(process: str, run_id: str, name: str) -> str:
    base = run_path(process, run_id)
    report = json.loads((base / "report.json").read_text())
    if name not in report.get("evidence_sha256", {}):
        raise ValueError("Artifact is not in the run manifest")
    path = (base / name).resolve()
    if not path.is_relative_to(base.resolve()) or not path.is_file():
        raise ValueError("Artifact path is invalid")
    if path.stat().st_size > 2_000_000 or not name.endswith(
            (".spice", ".tcl", ".log", ".txt", ".xml", ".lyrdb")):
        raise ValueError("Artifact is not a small text file")
    return path.read_text(errors="replace")


@lru_cache(maxsize=12)
def layout_data(process: str, run_id: str) -> dict:
    import klayout.db as db

    base = run_path(process, run_id)
    gds = (base / "connected" / "inverter.gds") if process == "gf180" else (base / "inverter.gds")
    if not gds.is_file():
        raise ValueError("This run has no connected GDS layout")
    layout = db.Layout()
    layout.read(str(gds))
    tops = list(layout.top_cells())
    if len(tops) != 1 or tops[0].name != "inverter":
        raise ValueError("Unexpected GDS top cell")
    box = tops[0].bbox()
    scale = layout.dbu
    lyp = PDK_ROOT / PROCESSES[process]["pdk"] / "libs.tech" / "klayout" / "tech"
    lyp = lyp / ("sky130A.lyp" if process == "sky130" else "gf180mcu.lyp")
    names = {}
    if lyp.is_file():
        tree = ET.parse(lyp)
        for prop in tree.findall(".//properties"):
            source = prop.findtext("source") or ""
            match = re.search(r"(?:(.*?)\s+)?(\d+/\d+)@", source)
            if match:
                label = prop.findtext("name") or match[1] or match[2]
                names[match[2]] = (label, prop.findtext("fill-color") or "#60baca")
    layers = []
    shape_count = 0
    for index in layout.layer_indices():
        info = layout.get_info(index)
        key = f"{info.layer}/{info.datatype}"
        region = db.Region(tops[0].begin_shapes_rec(index))
        polygons = []
        for poly in region.each():
            hull = [[round(pt.x * scale, 4), round(pt.y * scale, 4)]
                    for pt in poly.each_point_hull()]
            holes = [[[round(pt.x * scale, 4), round(pt.y * scale, 4)]
                      for pt in poly.each_point_hole(i)] for i in range(poly.holes())]
            polygons.append({"hull": hull, "holes": holes})
            shape_count += 1
            if shape_count > 20_000:
                raise ValueError("Layout exceeds dashboard geometry limit")
        if polygons:
            label, color = names.get(key, (f"Layer {key}", "#60baca"))
            layers.append({"key": key, "name": label, "color": color,
                           "polygons": polygons, "count": len(polygons)})
    return {"top": "inverter", "bbox": [round(box.left * scale, 4),
            round(box.bottom * scale, 4), round(box.right * scale, 4),
            round(box.top * scale, 4)], "layers": layers,
            "shape_count": shape_count, "gds_sha256": digest(gds)}


def trace_netlist(process: str, run_id: str, kind: str, target: Path) -> str:
    if kind not in {"schematic", "postlayout"}:
        raise ValueError("Unknown waveform kind")
    base = run_path(process, run_id)
    source = (base / "inverter.spice").read_text()
    lines = [line for line in source.splitlines()
             if not line.lower().startswith((".tran", ".meas", ".end"))]
    if kind == "postlayout":
        pex = (base / "connected" / "inverter_pex.spice") if process == "gf180" else (base / "inverter_pex.spice")
        if not pex.is_file():
            raise ValueError("No extracted netlist for this run")
        shutil.copyfile(pex, target / "inverter_pex.spice")
        if process == "gf180":
            prefixes = ("XMN out", "XMP out")
            replacement = "XINV in out 0 vdd inverter"
        else:
            prefixes = ("XMN out", "XMP out")
            replacement = "XINV out in 0 vdd inverter"
        found = [line for line in lines if line.startswith(prefixes)]
        if len(found) != 2:
            raise ValueError("Cannot identify the two inverter devices")
        lines = [line for line in lines if not line.startswith(prefixes)]
        lines.extend([".include inverter_pex.spice", replacement])
    lines.extend([".control", "set wr_singlescale", "set wr_vecnames",
                  "tran 2p 12n", "wrdata waveform.txt v(in) v(out)",
                  ".endc", ".end"])
    return "\n".join(lines) + "\n"


def read_waveform(path: Path) -> list[list[float]]:
    rows = []
    with path.open() as stream:
        next(stream)
        for line in stream:
            values = line.split()
            if len(values) != 3:
                continue
            rows.append([round(float(values[0]) * 1e9, 6),
                         round(float(values[1]), 7), round(float(values[2]), 7)])
    if len(rows) < 100:
        raise ValueError("Waveform export is incomplete")
    return rows


def waveform_data(process: str, run_id: str, kind: str) -> dict:
    base = RUNS / "dashboard" / "traces" / process / run_id / kind
    with TRACE_LOCK:
        base.mkdir(parents=True, exist_ok=True)
        netlist = trace_netlist(process, run_id, kind, base)
        pex = base / "inverter_pex.spice"
        fingerprint = hashlib.sha256((netlist + (digest(pex) if pex.is_file() else "")).encode()).hexdigest()
        metadata = base / "manifest.json"
        wave = base / "waveform.txt"
        existing = json.loads(metadata.read_text()) if metadata.is_file() else {}
        if not wave.is_file() or existing.get("input_sha256") != fingerprint:
            (base / "trace.spice").write_text(netlist)
            args = ["docker", "compose", "run", "--rm", "-v",
                    f"{PDK_ROOT}:/pdk:ro", "-e", "PDK_ROOT=/pdk",
                    "--workdir", f"/results/dashboard/traces/{process}/{run_id}/{kind}",
                    "--entrypoint", "ngspice", "worker", "-b", "trace.spice"]
            result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True,
                                    timeout=90, check=False)
            (base / "ngspice.log").write_text(result.stdout + result.stderr)
            if result.returncode or not wave.is_file():
                raise ValueError("Waveform simulation failed; see dashboard trace log")
            metadata.write_text(json.dumps({"input_sha256": fingerprint,
                                            "wave_sha256": digest(wave),
                                            "kind": kind, "process": process,
                                            "source_run": run_id}, indent=2) + "\n")
    return {"kind": kind, "process": process, "run_id": run_id,
            "source": "ngspice on the Mac arm64 Docker worker",
            "samples": read_waveform(wave), "manifest": json.loads(metadata.read_text())}


def exploratory_netlist(process: str, voltage: float, load_ff: float, temp_c: float) -> str:
    if process == "sky130":
        library = ".lib /pdk/sky130A/libs.tech/ngspice/sky130.lib.spice tt"
        n, p = "sky130_fd_pr__nfet_01v8", "sky130_fd_pr__pfet_01v8"
        length = "0.15"
        globals_file = ""
    else:
        library = ".lib /pdk/gf180mcuD/libs.tech/ngspice/sm141064.ngspice typical"
        n, p = "nfet_03v3", "pfet_03v3"
        length = "0.28u"
        globals_file = ".include /pdk/gf180mcuD/libs.tech/ngspice/design.ngspice\n"
    width_n = "1" if process == "sky130" else "1u"
    width_p = "2" if process == "sky130" else "2u"
    return (f"* Exploratory {PROCESSES[process]['title']} inverter; not validation\n"
            f"{globals_file}{library}\n.temp {temp_c:g}\n"
            f"VDD vdd 0 {voltage:g}\n"
            f"VIN in 0 PULSE(0 {voltage:g} 1n 20p 20p 2n 4n)\n"
            f"XMN out in 0 0 {n} w={width_n} l={length}\n"
            f"XMP out in vdd vdd {p} w={width_p} l={length}\n"
            f"CLOAD out 0 {load_ff:g}f\n"
            ".control\nset wr_singlescale\nset wr_vecnames\n"
            "tran 2p 12n\nwrdata waveform.txt v(in) v(out)\n.endc\n.end\n")


def experiment_data(payload: dict) -> dict:
    process = payload.get("process")
    if process not in PROCESSES:
        raise ValueError("Select a supported process")
    try:
        voltage = float(payload.get("voltage"))
        load_ff = float(payload.get("load_ff"))
        temp_c = float(payload.get("temp_c"))
    except (TypeError, ValueError):
        raise ValueError("Voltage, load and temperature must be numbers") from None
    if not all(math.isfinite(value) for value in (voltage, load_ff, temp_c)):
        raise ValueError("Parameters must be finite numbers")
    spec = PROCESSES[process]
    if not (spec["min_v"] <= voltage <= spec["voltage"] and
            0.5 <= load_ff <= 100 and -20 <= temp_c <= 100):
        raise ValueError("Parameters are outside this dashboard's exploratory range")
    run_id = str(uuid.uuid4())
    base = RUNS / "dashboard" / "experiments" / run_id
    base.mkdir(parents=True, mode=0o700)
    netlist = exploratory_netlist(process, voltage, load_ff, temp_c)
    (base / "experiment.spice").write_text(netlist)
    args = ["docker", "compose", "run", "--rm", "-v", f"{PDK_ROOT}:/pdk:ro",
            "-e", "PDK_ROOT=/pdk", "--workdir",
            f"/results/dashboard/experiments/{run_id}", "--entrypoint",
            "ngspice", "worker", "-b", "experiment.spice"]
    result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True,
                            timeout=90, check=False)
    (base / "ngspice.log").write_text(result.stdout + result.stderr)
    wave = base / "waveform.txt"
    if result.returncode or not wave.is_file():
        raise ValueError(f"Experiment {run_id} failed; inspect its ngspice log")
    rows = read_waveform(wave)
    # Sample away from switching edges for high/low levels. Crossing delays
    # are measured independently by the validated process runners.
    high = min(rows, key=lambda row: abs(row[0] - 0.5))[2]
    low = min(rows, key=lambda row: abs(row[0] - 2.0))[2]
    manifest = {"id": run_id, "status": "exploratory", "process": process,
                "voltage": voltage, "load_ff": load_ff, "temp_c": temp_c,
                "netlist_sha256": digest(base / "experiment.spice"),
                "wave_sha256": digest(wave), "high_v": high, "low_v": low}
    (base / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return {"manifest": manifest, "samples": rows}


def start_validation(process: str) -> str:
    if process not in PROCESSES:
        raise ValueError("Unknown process")
    with JOB_LOCK:
        if any(job["state"] == "running" for job in JOBS.values()):
            raise ValueError("A validation run is already in progress")
        job_id = str(uuid.uuid4())
        JOBS[job_id] = {"id": job_id, "process": process, "state": "running"}

    def execute() -> None:
        script = ROOT / "examples" / PROCESSES[process]["folder"] / "run.py"
        try:
            result = subprocess.run([sys.executable, str(script)], cwd=ROOT,
                                    capture_output=True, text=True, timeout=300,
                                    check=False)
            lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
            output_path = Path(lines[-1]) if lines else None
            report = None
            if output_path and output_path.is_file() and output_path.name == "report.json":
                report = json.loads(output_path.read_text())
            JOBS[job_id].update({"state": "complete" if result.returncode == 0 else "failed",
                                 "report_status": report.get("status") if report else None,
                                 "run_id": output_path.parent.name if report else None,
                                 "output": (result.stdout + result.stderr)[-6000:]})
        except Exception as exc:
            JOBS[job_id].update({"state": "failed", "output": str(exc)})

    threading.Thread(target=execute, daemon=True).start()
    return job_id


class Handler(BaseHTTPRequestHandler):
    server_version = "ChipLabDashboard/1.0"

    def reply(self, status: int, data: object) -> None:
        body = json.dumps(data, ensure_ascii=False, allow_nan=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def serve_static(self, name: str, content_type: str) -> None:
        body = (STATIC / name).read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; connect-src 'self'; img-src 'self' data:; style-src 'self'")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlsplit(self.path)
        q = {key: values[0] for key, values in parse_qs(parsed.query).items()}
        try:
            if parsed.path in {"/", "/index.html"}:
                return self.serve_static("index.html", "text/html; charset=utf-8")
            if parsed.path == "/app.js":
                return self.serve_static("app.js", "text/javascript; charset=utf-8")
            if parsed.path == "/style.css":
                return self.serve_static("style.css", "text/css; charset=utf-8")
            if parsed.path == "/api/overview":
                return self.reply(200, {"token": TOKEN, "processes": PROCESSES,
                                        "runs": {p: run_list(p) for p in PROCESSES},
                                        "documents": DOCS})
            if parsed.path == "/api/run":
                return self.reply(200, report_data(q["process"], q["run"]))
            if parsed.path == "/api/artifact":
                return self.reply(200, {"name": q["name"], "text":
                    artifact_text(q["process"], q["run"], q["name"])})
            if parsed.path == "/api/document":
                name = q["name"]
                if name not in DOCS:
                    raise ValueError("Unknown document")
                return self.reply(200, {"name": name,
                                        "text": (ROOT / name).read_text()})
            if parsed.path == "/api/layout":
                return self.reply(200, layout_data(q["process"], q["run"]))
            if parsed.path == "/api/waveform":
                return self.reply(200, waveform_data(q["process"], q["run"], q["kind"]))
            if parsed.path == "/api/job":
                return self.reply(200, JOBS.get(q.get("id"), {"state": "unknown"}))
            return self.reply(404, {"error": "Unknown path"})
        except (ValueError, KeyError, OSError, json.JSONDecodeError) as exc:
            return self.reply(400, {"error": str(exc)})
        except subprocess.TimeoutExpired:
            return self.reply(504, {"error": "Tool run timed out"})

    def do_POST(self) -> None:  # noqa: N802
        try:
            origin = self.headers.get("Origin", "")
            if origin and origin != f"http://{self.headers.get('Host')}":
                raise ValueError("Cross-origin request refused")
            if self.headers.get("X-Lab-Token") != TOKEN:
                raise ValueError("Missing dashboard session token")
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                raise ValueError("Expected JSON request")
            length = int(self.headers.get("Content-Length", "0"))
            if length < 1 or length > 16_384:
                raise ValueError("Invalid request length")
            payload = json.loads(self.rfile.read(length))
            if self.path == "/api/simulate":
                return self.reply(200, experiment_data(payload))
            if self.path == "/api/validate":
                return self.reply(202, {"job_id": start_validation(payload.get("process"))})
            return self.reply(404, {"error": "Unknown action"})
        except (ValueError, KeyError, OSError, json.JSONDecodeError) as exc:
            return self.reply(400, {"error": str(exc)})
        except subprocess.TimeoutExpired:
            return self.reply(504, {"error": "Tool run timed out"})


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    if not 1024 <= port <= 65535:
        raise SystemExit("Choose a port from 1024 to 65535")
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Chip Lab dashboard: http://127.0.0.1:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
