"""Exercise installed tools with controlled pass/fail fixtures, without a PDK."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

from .cli import ROOT, new_run, private_json, simulate


def execute(command, directory, logname, stdin=None, timeout=60):
    completed = subprocess.run(command, cwd=directory, input=stdin, text=True,
                               capture_output=True, timeout=timeout)
    text = completed.stdout + completed.stderr
    (directory / logname).write_text(text)
    return completed.returncode, text


def qualify(base):
    run = new_run(base)
    checks = []
    result = {'status': 'failed', 'kind': 'pdk-free-toolchain-qualification', 'run': str(run),
              'checks': checks, 'pdk_qualified': False}
    try:
        for tool in ('ngspice', 'magic', 'xschem', 'klayout'):
            if not shutil.which(tool):
                raise ValueError('Missing ' + tool + '; run qualification inside the complete Docker worker.')
        netgen = shutil.which('netgen') or shutil.which('netgen-lvs')
        if not netgen: raise ValueError('Netgen LVS is missing.')

        rc = simulate(run)
        if rc['status'] != 'passed': raise ValueError('RC simulation failed: ' + str(rc))
        checks.append({'tool': 'ngspice', 'status': 'passed', 'measurements': rc['measurements']})

        code, text = execute(['magic', '-dnull', '-noconsole', '-rcfile', '/dev/null'], run, 'magic.log',
                             'puts "CHIP_LAB_MAGIC_VERSION=[version]"\nquit -noprompt\n')
        if code or 'CHIP_LAB_MAGIC_VERSION=' not in text:
            raise ValueError('Magic failed to initialize; see magic.log.')
        checks.append({'tool': 'magic', 'status': 'passed', 'scope': 'headless initialization', 'version_log': 'magic.log'})

        code, text = execute(['xschem', '--version'], run, 'xschem.log')
        if code or not text.strip(): raise ValueError('Xschem version probe failed.')
        checks.append({'tool': 'xschem', 'status': 'passed', 'scope': 'version probe', 'version': text.strip()})

        (run / 'reference.spice').write_text('.subckt fixture p n\nR1 p n 1000\n.ends fixture\n')
        (run / 'matching.spice').write_text((run / 'reference.spice').read_text())
        (run / 'mismatch.spice').write_text('.subckt fixture p n\nC1 p n 1p\n.ends fixture\n')
        (run / 'setup.tcl').write_text('permute default\nproperty default\n')
        for name, other, should_match in [('match', 'matching.spice', True), ('mismatch', 'mismatch.spice', False)]:
            report = run / (name + '.lvs.log')
            code, text = execute([netgen, '-batch', 'lvs', f'{run / "reference.spice"} fixture',
                                  f'{run / other} fixture', str(run / 'setup.tcl'), str(report)], run, name + '.netgen.log')
            if not report.exists(): raise ValueError('Netgen did not create a report.')
            content = report.read_text().lower()
            accepted = 'circuits match uniquely' in content or 'circuits match correctly' in content
            rejected = 'do not match' in content or 'mismatch' in content
            if (should_match and (code or not accepted)) or (not should_match and not rejected):
                raise ValueError('Netgen controlled comparison produced an unexpected result: ' + name)
        checks.append({'tool': 'netgen', 'status': 'passed', 'scope': 'generic match and intentional mismatch'})

        code, _ = execute(['klayout', '-b', '-r', str(ROOT / 'tests/create_geometry.py'), '-rd', 'output=' + str(run)], run, 'geometry.log')
        if code: raise ValueError('KLayout fixture generation failed.')
        counts = {}
        for name in ('good', 'bad'):
            report = run / (name + '.lyrdb')
            code, _ = execute(['klayout', '-b', '-r', str(ROOT / 'bridge/scratch_width.drc'),
                                '-rd', 'input=' + str(run / (name + '.gds')), '-rd', 'report=' + str(report)], run, name + '.drc.log')
            if code or not report.exists(): raise ValueError('KLayout did not create a DRC report.')
            counts[name] = len(ET.parse(report).findall('.//items/item'))
        if counts['good'] != 0 or counts['bad'] == 0:
            raise ValueError('Synthetic DRC did not distinguish the good and broken fixtures.')
        checks.append({'tool': 'klayout-drc', 'status': 'passed', 'violations': counts,
                       'scope': 'synthetic width rule, not a PDK deck'})

        code, _ = execute([sys.executable, '-m', 'unittest', 'discover', '-s', str(ROOT / 'tests'),
                            '-p', 'test_bridge_gui.py', '-v'], run, 'gui-bridge.log', timeout=60)
        if code: raise ValueError('Live KLayout GUI bridge test failed; see gui-bridge.log.')
        checks.append({'tool': 'klayout-gui-bridge', 'status': 'passed',
                       'scope': 'inspect, edit, separate snapshot save, active-cell refusal, shutdown'})
        result['status'] = 'passed'
    except (ValueError, OSError, subprocess.SubprocessError, ET.ParseError) as exc:
        result['error'] = str(exc)
    private_json(run / 'qualification.json', result)
    return result
