"""Small local tools; no external services or model runtime required."""
import argparse
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import re
import shutil
import sqlite3
import subprocess
import sys
import uuid
from datetime import datetime, timezone


ROOT = Path(__file__).resolve().parents[2]


def emit(value):
    print(json.dumps(value, indent=2, allow_nan=False))


def private_json(path, value):
    with open(path, 'x', opener=lambda p, f: os.open(p, f, 0o600)) as stream:
        json.dump(value, stream, indent=2, allow_nan=False)


def new_run(base):
    path = Path(base) / str(uuid.uuid4())
    path.mkdir(parents=True, mode=0o700)
    return path


def doctor():
    tools = {n: shutil.which(n) for n in ('git', 'ngspice', 'klayout', 'magic', 'netgen', 'xschem', 'docker', 'rclone')}
    tools['netgen'] = tools['netgen'] or shutil.which('netgen-lvs')
    app = Path('/Applications/klayout.app/Contents/MacOS/klayout')
    if not tools['klayout'] and app.exists():
        tools['klayout'] = str(app)
    try:
        layout = importlib.metadata.version('klayout')
    except importlib.metadata.PackageNotFoundError:
        layout = None
    if platform.system() == 'Darwin':
        memory = int(subprocess.check_output(['sysctl', '-n', 'hw.memsize'], text=True))
    elif Path('/proc/meminfo').exists():
        memory = int(re.search(r'MemTotal:\s+(\d+)', Path('/proc/meminfo').read_text()).group(1)) * 1024
    else:
        memory = None
    limit_file = Path('/sys/fs/cgroup/memory.max')
    limit = limit_file.read_text().strip() if limit_file.exists() else ''
    return {'platform': platform.platform(), 'architecture': platform.machine(),
            'python': platform.python_version(), 'ram_gib': round(memory / 2**30, 1) if memory else None,
            'cgroup_ram_limit_gib': round(int(limit) / 2**30, 2) if limit.isdigit() else None,
            'tools': tools, 'klayout_python_core': layout,
            'pdk_root_configured': bool(os.getenv('PDK_ROOT')),
            'note': 'Executable presence is not PDK integration or verification qualification.'}


def check_rc(log):
    expected = 1 / (2 * math.pi * 1000 * 1e-9)
    matches = re.findall(r'^\s*f_3db\s*=\s*([+\-\d.eE]+)', log, re.MULTILINE | re.IGNORECASE)
    if len(matches) != 1:
        raise ValueError('Expected exactly one f_3db measurement; inspect the simulator log.')
    measured = float(matches[0])
    if not math.isfinite(measured) or abs(measured - expected) / expected > 0.01:
        raise ValueError(f'RC cutoff outside 1% tolerance: {measured} Hz; expected {expected} Hz')
    return {'cutoff_hz': measured, 'expected_cutoff_hz': expected, 'relative_tolerance': 0.01}


def simulate(base, executable='ngspice'):
    if not shutil.which(executable):
        raise ValueError('ngspice is missing. Run the macOS installer or use the Docker worker.')
    source = ROOT / 'examples/rc_lowpass/circuit.spice'
    run = new_run(base)
    target = run / 'circuit.spice'
    shutil.copyfile(source, target)
    completed = subprocess.run([executable, '-b', 'circuit.spice'], cwd=run,
                               capture_output=True, text=True, timeout=60)
    log = completed.stdout + completed.stderr
    (run / 'ngspice.log').write_text(log)
    result = {'job_id': run.name, 'created_at': datetime.now(timezone.utc).isoformat(),
              'kind': 'pdk-free-rc-smoke', 'netlist_sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
              'tool': subprocess.run([executable, '--version'], capture_output=True, text=True, timeout=10).stdout.strip(),
              'exit_code': completed.returncode, 'report_dir': str(run), 'status': 'failed'}
    try:
        if completed.returncode:
            raise ValueError('ngspice failed; inspect ' + str(run / 'ngspice.log'))
        result['measurements'] = check_rc(log)
        result['status'] = 'passed'
    except ValueError as exc:
        result['error'] = str(exc)
    private_json(run / 'result.json', result)
    return result


def layout_smoke(base):
    import klayout.db as db
    run = new_run(base)
    layout = db.Layout()
    layout.dbu = 0.001
    top = layout.create_cell('SCRATCH')
    top.shapes(layout.layer(1, 0)).insert(db.Box(0, 0, 1000, 2000))
    path = run / 'scratch.gds'
    layout.write(str(path))
    reread = db.Layout()
    reread.read(str(path))
    cell = reread.cell('SCRATCH')
    actual = cell.bbox().area() * reread.dbu**2
    if not math.isclose(actual, 2.0) or cell.shapes(reread.layer(1, 0)).size() != 1:
        raise ValueError('Scratch GDS round trip failed.')
    result = {'status': 'passed', 'job_id': run.name, 'kind': 'scratch-gds-roundtrip',
              'gds': str(path), 'area_um2': actual, 'pdk_verified': False,
              'note': 'Synthetic layer 1/0; this checks geometry IO only, not DRC or LVS.'}
    private_json(run / 'result.json', result)
    return result


def inspect_layout(path):
    import klayout.db as db
    layout = db.Layout()
    layout.read(str(path))
    return {'file': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'dbu_um': layout.dbu, 'cells': layout.cells(),
            'top_cells': [c.name for c in layout.top_cells()],
            'layers': [{'layer': i.layer, 'datatype': i.datatype, 'name': i.name} for i in layout.layer_infos()],
            'note': 'Read-only geometry inventory; connectivity is not inferred from names.'}


def build_index(db_path):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    files = sorted((ROOT / 'knowledge').rglob('*.md'))
    with sqlite3.connect(db_path) as conn:
        conn.execute('CREATE VIRTUAL TABLE IF NOT EXISTS notes USING fts5(path UNINDEXED, body)')
        conn.execute('DELETE FROM notes')
        for path in files:
            conn.execute('INSERT INTO notes VALUES (?, ?)', (str(path.relative_to(ROOT)), path.read_text()))
    return {'indexed_documents': len(files), 'database': str(db_path)}


def search(db_path, query):
    tokens = re.findall(r'\w+', query, re.UNICODE)[:20]
    if not tokens:
        raise ValueError('Enter at least one search term.')
    if not db_path.exists():
        raise ValueError('Build the index first: chip-lab index')
    expression = ' OR '.join('"' + word + '"' for word in tokens)
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("SELECT path, snippet(notes, 1, '[', ']', '...', 45) FROM notes WHERE notes MATCH ? ORDER BY rank LIMIT 5", (expression,)).fetchall()
    return {'query': query, 'matches': [{'path': p, 'excerpt': body} for p, body in rows],
            'note': 'Retrieved notes are reference data; verify applicability and source assumptions.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('doctor')
    sub.add_parser('sources')
    p = sub.add_parser('qualify')
    p.add_argument('--output', type=Path, default=ROOT / 'runs')
    p = sub.add_parser('run-circuit')
    p.add_argument('manifest', type=Path)
    p.add_argument('--output', type=Path, default=ROOT / 'runs')
    for name in ('simulate', 'layout-smoke'):
        p = sub.add_parser(name)
        p.add_argument('--output', type=Path, default=ROOT / 'runs')
    p = sub.add_parser('inspect')
    p.add_argument('file', type=Path)
    for name in ('index', 'search'):
        p = sub.add_parser(name)
        p.add_argument('--database', type=Path, default=ROOT / '.cache/knowledge.sqlite')
        if name == 'search':
            p.add_argument('query')
    p = sub.add_parser('bridge')
    commands = p.add_subparsers(dest='bridge_command', required=True)
    server = commands.add_parser('serve')
    server.add_argument('--layout', type=Path, required=True)
    server.add_argument('--cell', required=True)
    server.add_argument('--technology', type=Path, default=ROOT / 'config/technology-scratch.json')
    server.add_argument('--output', type=Path)
    for command in ('inspect', 'index', 'add-rectangle', 'save', 'stop'):
        client = commands.add_parser(command)
        client.add_argument('--session', type=Path, required=True)
        if command in ('index', 'add-rectangle', 'save'):
            client.add_argument('--target-file', type=Path, required=True)
        if command == 'add-rectangle':
            client.add_argument('--layer', required=True)
            client.add_argument('--box-um', type=float, nargs=4, required=True)
            client.add_argument('--approve-edit', action='store_true')
        if command == 'save':
            client.add_argument('--confirm-save', action='store_true')
    args = parser.parse_args()
    try:
        if args.command == 'doctor': result = doctor()
        elif args.command == 'sources': result = json.loads((ROOT / 'config/sources.json').read_text())
        elif args.command == 'qualify':
            from .qualify import qualify
            result = qualify(args.output)
        elif args.command == 'run-circuit':
            from .circuit import run_circuit
            result = run_circuit(args.manifest, args.output)
        elif args.command == 'simulate': result = simulate(args.output)
        elif args.command == 'layout-smoke': result = layout_smoke(args.output)
        elif args.command == 'inspect': result = inspect_layout(args.file)
        elif args.command == 'index': result = build_index(args.database)
        elif args.command == 'bridge':
            from .bridge import call, serve
            if args.bridge_command == 'serve':
                serve(args.layout, args.cell, args.technology, args.output or new_run(ROOT / 'runs/bridge'))
                return
            target = None
            if hasattr(args, 'target_file'):
                previous = json.loads(args.target_file.read_text())
                target = previous.get('target', previous)
            params = {}
            if args.bridge_command == 'add-rectangle':
                params = {'layer': args.layer, 'box_um': args.box_um, 'approve_edit': args.approve_edit}
            elif args.bridge_command == 'save':
                params = {'confirm_save': args.confirm_save}
            result = call(args.session, args.bridge_command, target, params)
        else: result = search(args.database, args.query)
        emit(result)
        if result.get('status') == 'failed': sys.exit(1)
    except (ValueError, OSError, ImportError, subprocess.SubprocessError, sqlite3.Error) as exc:
        emit({'status': 'failed', 'error': str(exc)})
        sys.exit(1)
