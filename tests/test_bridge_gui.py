import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest

from chip_lab.bridge import call, digest
from chip_lab.cli import ROOT


@unittest.skipUnless(shutil.which('klayout'), 'KLayout GUI executable not installed')
class GuiBridgeTests(unittest.TestCase):
    def test_real_editor_inspect_edit_snapshot_and_wrong_cell(self):
        with tempfile.TemporaryDirectory(prefix='chip-gui-') as tmp:
            root = Path(tmp)
            env = dict(os.environ, LAB_GUI_TEST_OUTPUT=tmp, QT_QPA_PLATFORM='offscreen')
            with (root / 'gui.log').open('w+') as log:
                process = subprocess.Popen(['klayout', '-z', '-nc', '-rx', '-e', '-rr', str(ROOT / 'tests/gui_entry.py')],
                                           env=env, stdout=log, stderr=log)
                try:
                    descriptor = root / 'session/session.json'
                    deadline = time.monotonic() + 30
                    while not descriptor.exists() and process.poll() is None and time.monotonic() < deadline:
                        time.sleep(0.05)
                    log.flush()
                    self.assertTrue(descriptor.exists(), (root / 'gui.log').read_text())
                    initial_hash = digest(root / 'input.gds')
                    before = call(descriptor, 'inspect')
                    self.assertEqual(before['status'], 'passed', before)
                    edit = call(descriptor, 'add-rectangle', before['target'],
                                {'approve_edit': True, 'layer': 'M1/drawing', 'box_um': [2, 0, 3, 2]})
                    self.assertEqual(edit['status'], 'passed', edit)
                    self.assertFalse(edit['saved'])
                    self.assertEqual(digest(root / 'input.gds'), initial_hash)
                    indexed = call(descriptor, 'index', edit['target'])
                    self.assertEqual(indexed['layers'][0]['shapes_in_cell'], 2)
                    save = call(descriptor, 'save', edit['target'], {'confirm_save': True})
                    self.assertEqual(save['status'], 'passed', save)
                    self.assertTrue(Path(save['snapshot']).exists())
                    self.assertEqual(digest(root / 'input.gds'), initial_hash)
                    (root / 'switch-cell').touch()
                    deadline = time.monotonic() + 5
                    while not (root / 'switched').exists() and time.monotonic() < deadline:
                        time.sleep(0.025)
                    rejected = call(descriptor, 'inspect')
                    self.assertEqual(rejected['status'], 'failed', rejected)
                    self.assertIn('target changed', rejected['error'])
                    self.assertEqual(call(descriptor, 'stop')['status'], 'passed')
                    process.wait(timeout=10)
                    self.assertEqual(process.returncode, 0, (root / 'gui.log').read_text())
                finally:
                    if process.poll() is None:
                        process.terminate()
                    try:
                        process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
