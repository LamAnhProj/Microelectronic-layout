"""Materialize declared circuit inputs and check ngspice measurements."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

from .bridge import number
from .cli import new_run, private_json


def validate_manifest(manifest, root):
    if not isinstance(manifest, dict): raise ValueError('Circuit manifest must be an object.')
    files, netlist, measures = manifest.get('files'), manifest.get('netlist'), manifest.get('measurements')
    if (not isinstance(files, list) or not files or not all(isinstance(f, str) for f in files)
            or len(set(files)) != len(files) or not isinstance(netlist, str) or netlist not in files):
        raise ValueError('Declare unique input files including the netlist.')
    for name in files:
        path = Path(name)
        if name in ('design.json', 'result.json', 'ngspice.log'):
            raise ValueError('Input name conflicts with a reserved result file.')
        if path.is_absolute() or '..' in path.parts or not (root / path).resolve().is_relative_to(root.resolve()):
            raise ValueError('Input files must remain within the circuit project directory.')
        if not (root / path).is_file(): raise ValueError('Missing declared input: ' + name)
    if not isinstance(measures, dict) or not measures:
        raise ValueError('Declare measurable acceptance criteria before simulation.')
    for name, limits in measures.items():
        if not re.fullmatch('[A-Za-z][A-Za-z0-9_]*', name): raise ValueError('Invalid measurement name.')
        if not isinstance(limits, dict) or 'expected' not in limits:
            raise ValueError('Measurement needs an expected value and tolerance.')
        number(limits['expected'])
        relative = number(limits.get('relative_tolerance', 0))
        absolute = number(limits.get('absolute_tolerance', 0))
        if relative < 0 or absolute < 0 or relative + absolute == 0:
            raise ValueError('Specify a positive measurement tolerance.')
    return manifest


def run_circuit(manifest_file, base):
    manifest_file = Path(manifest_file).resolve(strict=True)
    manifest = validate_manifest(json.loads(manifest_file.read_text()), manifest_file.parent)
    executable = shutil.which('ngspice')
    if not executable: raise ValueError('ngspice is missing; use the worker or macOS bootstrap.')
    run = new_run(base)
    hashes = {}
    for name in manifest['files']:
        target = run / name
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        content = (manifest_file.parent / name).read_bytes()
        target.write_bytes(content)
        target.chmod(0o600)
        hashes[name] = hashlib.sha256(content).hexdigest()
    private_json(run / 'design.json', manifest)
    result = {'status': 'failed', 'name': manifest.get('name'), 'run': str(run),
              'input_hashes': hashes, 'measurements': {}, 'pdk_verified': False,
              'dependency_scope': 'declared files only; external model references are not certified'}
    command = [executable, '-b', './' + manifest['netlist']]
    result['command'] = command
    result['tool_version'] = subprocess.run([executable, '--version'], capture_output=True, text=True, timeout=10).stdout.strip()
    try:
        completed = subprocess.run(command, cwd=run, capture_output=True, text=True, timeout=60)
        log = completed.stdout + completed.stderr
        (run / 'ngspice.log').write_text(log)
        result['exit_code'] = completed.returncode
        if completed.returncode: raise ValueError('ngspice failed; see ngspice.log.')
        for name, spec in manifest['measurements'].items():
            matches = re.findall(r'^\s*' + re.escape(name) + r'\s*=\s*([+\-\d.eE]+)', log, re.MULTILINE | re.IGNORECASE)
            if len(matches) != 1: raise ValueError('Missing or ambiguous measurement: ' + name)
            measured = number(float(matches[0]))
            expected = spec['expected']
            tolerance = max(abs(expected) * spec.get('relative_tolerance', 0), spec.get('absolute_tolerance', 0))
            passed = abs(measured - expected) <= tolerance
            result['measurements'][name] = {'measured': measured, 'expected': expected,
                                             'tolerance': tolerance, 'unit': spec.get('unit'), 'passed': passed}
        if not all(v['passed'] for v in result['measurements'].values()):
            raise ValueError('Circuit measurements do not meet declared criteria.')
        result['status'] = 'passed'
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        result['error'] = str(exc)
    private_json(run / 'result.json', result)
    return result
