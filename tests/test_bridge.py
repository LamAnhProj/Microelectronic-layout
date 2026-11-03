import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
import uuid

from chip_lab.bridge import LayoutSession, call, digest
from chip_lab.cli import ROOT


@unittest.skipUnless(importlib.util.find_spec('klayout'), 'KLayout Python core not installed')
class BridgeTests(unittest.TestCase):
    def setUp(self):
        import klayout.db as db
        self.db = db
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.source = self.root / 'input.gds'
        self.layout = db.Layout()
        self.layout.dbu = 0.001
        self.cell = self.layout.create_cell('SCRATCH')
        self.cell.shapes(self.layout.layer(1, 0)).insert(db.Box(0, 0, 1000, 2000))
        self.layout.write(str(self.source))
        self.original = digest(self.source)
        self.session = LayoutSession(db, lambda: (self.layout, self.cell, self.source), self.source,
                                     'SCRATCH', ROOT / 'config/technology-scratch.json', self.root / 'reports')

    def tearDown(self):
        self.tmp.cleanup()

    def request(self, operation, target=None, **params):
        return {'id': str(uuid.uuid4()), 'operation': operation, 'target': target, 'params': params}

    def test_edit_and_save_are_separate_and_idempotent(self):
        target = self.session.target()
        request = self.request('add-rectangle', target, layer='M1/drawing', box_um=[2, 0, 3, 2], approve_edit=True)
        result = self.session.dispatch(request)
        self.assertEqual(result['status'], 'passed', result)
        self.assertFalse(result['saved'])
        self.assertEqual(digest(self.source), self.original)
        self.assertEqual(self.cell.shapes(self.layout.layer(1, 0)).size(), 2)
        self.assertEqual(self.session.dispatch(request), result)
        self.assertEqual(self.cell.shapes(self.layout.layer(1, 0)).size(), 2)
        saved = self.session.dispatch(self.request('save', result['target'], confirm_save=True))
        self.assertEqual(saved['status'], 'passed', saved)
        self.assertEqual(digest(self.source), self.original)
        reread = self.db.Layout()
        reread.read(saved['snapshot'])
        self.assertEqual(reread.cell('SCRATCH').shapes(reread.layer(1, 0)).size(), 2)
        self.assertEqual(Path(saved['snapshot']).stat().st_mode & 0o777, 0o600)

    def test_refuses_unsafe_or_stale_calls_without_changes(self):
        target = self.session.target()
        wrong = copy.deepcopy(target)
        wrong['cell'] = 'OTHER'
        for change in ({'approve_edit': False}, {'box_um': [0.0001, 0, 2, 2]},
                       {'box_um': [float('inf'), 0, 2, 2]}, {'layer': 'unmapped'},
                       {'box_um': [True, 0, 2, 2]}):
            params = dict(layer='M1/drawing', box_um=[2, 0, 3, 2], approve_edit=True)
            params.update(change)
            with self.subTest(change=change):
                if change.get('box_um', [None])[0] == float('inf'):
                    with self.assertRaises(ValueError): self.session.dispatch(self.request('add-rectangle', target, **params))
                else:
                    self.assertEqual(self.session.dispatch(self.request('add-rectangle', target, **params))['status'], 'failed')
        self.assertEqual(self.session.dispatch(self.request('save', target))['status'], 'failed')
        self.assertEqual(self.session.dispatch(self.request('index', wrong))['status'], 'failed')
        self.assertEqual(self.session.target(), target)
        self.cell.shapes(self.layout.layer(1, 0)).insert(self.db.Box(4000, 0, 5000, 1000))
        result = self.session.dispatch(self.request('add-rectangle', target, layer='M1/drawing', box_um=[2, 0, 3, 2], approve_edit=True))
        self.assertEqual(result['status'], 'failed')
        self.assertIn('stale', result['error'])

    def test_external_file_change_is_refused(self):
        self.source.write_bytes(b'changed by another process')
        with self.assertRaisesRegex(ValueError, 'changed on disk'):
            self.session.target()

    def test_property_changes_and_old_session_targets_are_refused(self):
        target = self.session.target()
        other = LayoutSession(self.db, lambda: (self.layout, self.cell, self.source), self.source,
                              'SCRATCH', ROOT / 'config/technology-scratch.json', self.root / 'other')
        with self.assertRaisesRegex(ValueError, 'Target mismatch'):
            other.agentBridgeCheckTarget(target)
        self.cell.set_property(41, 'manual change')
        self.assertNotEqual(self.session.target()['layout_sha256'], target['layout_sha256'])
        with self.assertRaisesRegex(ValueError, 'Target mismatch'):
            self.session.agentBridgeCheckTarget(target)
        self.assertEqual(digest(self.source), self.original)

    def test_socket_transport_and_authentication(self):
        output = self.root / 'server'
        process = subprocess.Popen([sys.executable, '-m', 'chip_lab', 'bridge', 'serve',
                                    '--layout', str(self.source), '--cell', 'SCRATCH', '--output', str(output)],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            deadline = time.monotonic() + 10
            descriptor = output / 'session.json'
            while not descriptor.exists() and process.poll() is None and time.monotonic() < deadline:
                time.sleep(0.025)
            self.assertTrue(descriptor.exists())
            info = call(descriptor, 'inspect')
            self.assertEqual(info['status'], 'passed', info)
            token_file = Path(json.loads(descriptor.read_text())['auth_file'])
            self.assertEqual(token_file.stat().st_mode & 0o777, 0o600)
            self.assertEqual(call(descriptor, 'arbitrary-eval')['status'], 'failed')
            import socket
            meta = json.loads(descriptor.read_text())
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.connect(meta['socket'])
                sock.sendall(b'{"token":"wrong"}\n')
                self.assertIn(b'Authentication failed', sock.recv(4096))
            self.assertEqual(call(descriptor, 'stop')['status'], 'passed')
            process.wait(timeout=5)
            self.assertFalse(Path(meta['socket']).exists())
            self.assertEqual(digest(self.source), self.original)
        finally:
            if process.poll() is None: process.terminate()
            process.communicate(timeout=5)
