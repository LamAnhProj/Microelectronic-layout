"""Local, bounded KLayout commands. No eval, arbitrary shell, or remote code API."""
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import queue
import secrets
import shutil
import socket
import socketserver
import tempfile
import threading
import time
import uuid

MAX_MESSAGE = 1024 * 1024
OPERATIONS = ('inspect', 'index', 'add-rectangle', 'save', 'stop')


def encoded(value):
    return json.dumps(value, sort_keys=True, allow_nan=False).encode()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_private(path, value):
    with open(path, 'x', opener=lambda p, f: os.open(p, f, 0o600)) as stream:
        json.dump(value, stream, indent=2, allow_nan=False)


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('Expected a finite number, not a string, boolean or nonfinite value.')
    return value


class LayoutSession:
    """All methods must run on the editor's owning thread."""

    def __init__(self, db, active, source, cell, technology, output, library='lab', view='layout', editor=None):
        self.db, self.active, self.editor = db, active, editor
        self.source, self.cell = Path(source).resolve(strict=True), cell
        self.library, self.view = library, view
        self.source_hash = digest(self.source)
        self.technology = json.loads(Path(technology).read_text())
        self.technology_hash = digest(technology)
        grid = number(self.technology['grid_um'])
        if grid <= 0 or not self.technology.get('layers'):
            raise ValueError('Technology needs a positive grid and explicit layer mappings.')
        self.output = Path(output).resolve()
        self.output.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.owner_thread = threading.get_ident()
        self.session_id = str(uuid.uuid4())
        self.revision = 0
        self.seen = {}

    def current(self):
        if threading.get_ident() != self.owner_thread:
            raise ValueError('Layout access must run on the editor main thread.')
        layout, cell, filename = self.active()
        if Path(filename).resolve() != self.source or cell is None or cell.name != self.cell:
            raise ValueError('Active editor target changed; start a bridge for the intended cell.')
        if digest(self.source) != self.source_hash:
            raise ValueError('Source file changed on disk; reopen it and start a new session.')
        return layout, cell

    def target(self):
        layout, cell = self.current()
        # Deterministic hierarchy fingerprint includes geometry, instance transforms,
        # object properties and layout units. Remote handles never escape the editor.
        content = [str(layout.dbu), repr(sorted(layout.properties().items(), key=repr))]
        for c in sorted(layout.each_cell(), key=lambda c: c.name):
            content.append(c.name)
            content.append(repr(sorted(c.properties().items(), key=repr)))
            for layer in sorted(layout.layer_indexes()):
                info = layout.get_info(layer)
                shapes = sorted((s.to_s(), repr(sorted(s.properties().items(), key=repr))) for s in c.shapes(layer).each())
                content.append(repr((info.to_s(), shapes)))
            content.append(repr(sorted((i.to_s(), repr(sorted(i.properties().items(), key=repr))) for i in c.each_inst())))
        return {'session_id': self.session_id, 'file': str(self.source), 'library': self.library, 'cell': cell.name,
                'view': self.view, 'source_sha256': self.source_hash,
                'technology': self.technology['id'], 'technology_sha256': self.technology_hash,
                'dbu_um': layout.dbu, 'revision': self.revision,
                'layout_sha256': hashlib.sha256(encoded(content)).hexdigest()}

    def agentBridgeCheckTarget(self, expected):
        if expected != self.target():
            raise ValueError('Target mismatch or stale layout fingerprint. Inspect again; do not replay the edit.')

    def agentBridgeIndex(self):
        layout, cell = self.current()
        return {'target': self.target(), 'cells': layout.cells(),
                'top_cells': [c.name for c in layout.top_cells()],
                'layers': [{'layer': layout.get_info(i).layer, 'datatype': layout.get_info(i).datatype,
                            'shapes_in_cell': cell.shapes(i).size()} for i in layout.layer_indexes()],
                'pdk_verified': False}

    def agentBridgeAddRectangle(self, params):
        if params.get('approve_edit') is not True:
            raise ValueError('Editing requires --approve-edit.')
        mapping = self.technology['layers'].get(params.get('layer'))
        if not isinstance(mapping, list) or len(mapping) != 2 or any(type(v) is not int or v < 0 for v in mapping):
            raise ValueError('Layer is not explicitly mapped by this technology profile.')
        box = params.get('box_um')
        if not isinstance(box, list) or len(box) != 4:
            raise ValueError('Rectangle needs four coordinates in micrometers.')
        box = [number(v) for v in box]
        if box[0] >= box[2] or box[1] >= box[3]:
            raise ValueError('Rectangle must have positive width and height.')
        layout, cell = self.current()
        grid = self.technology['grid_um']
        if not math.isclose(grid / layout.dbu, round(grid / layout.dbu), abs_tol=1e-8):
            raise ValueError('Technology grid is not representable in layout database units.')
        coords = []
        for value in box:
            units = value / layout.dbu
            if not math.isclose(value / grid, round(value / grid), rel_tol=0, abs_tol=1e-7):
                raise ValueError('Off-grid coordinate refused.')
            if abs(units) > 2**31 - 1:
                raise ValueError('Coordinate exceeds GDS integer range.')
            coords.append(round(units))
        if self.editor:
            self.editor.transaction('agentBridgeAddRectangle')
        try:
            cell.shapes(layout.layer(*mapping)).insert(self.db.Box(*coords))
        finally:
            if self.editor:
                self.editor.commit()
        self.revision += 1
        return {'target': self.target(), 'changed': True, 'saved': False,
                'layer': params['layer'], 'box_um': box}

    def agentBridgeSaveSnapshot(self, params):
        if params.get('confirm_save') is not True:
            raise ValueError('Saving requires --confirm-save, separately from editing.')
        layout, _ = self.current()
        descriptor, path = tempfile.mkstemp(prefix='snapshot-', suffix='.gds', dir=self.output)
        os.close(descriptor)
        try:
            layout.write(path)
            reread = self.db.Layout()
            reread.read(path)
            if reread.cell(self.cell) is None:
                raise ValueError('Saved snapshot did not preserve the target cell.')
            os.chmod(path, 0o600)
        except Exception:
            Path(path).unlink(missing_ok=True)
            raise
        return {'target': self.target(), 'snapshot': path, 'sha256': digest(path),
                'saved': True, 'original_file_saved': False, 'pdk_verified': False}

    def dispatch(self, request):
        request_id = request.get('id', '')
        if str(uuid.UUID(request_id)) != request_id:
            raise ValueError('Request id must be a canonical UUID.')
        signature = hashlib.sha256(encoded(request)).hexdigest()
        if request_id in self.seen:
            old_signature, result = self.seen[request_id]
            if old_signature != signature:
                raise ValueError('Job UUID reused with different content.')
            return result
        write_private(self.output / (request_id + '.job.json'), request)
        operation, params = request.get('operation'), request.get('params', {})
        try:
            if operation not in OPERATIONS or not isinstance(params, dict):
                raise ValueError('Unsupported operation or invalid parameters.')
            if operation not in ('inspect', 'stop'):
                self.agentBridgeCheckTarget(request.get('target'))
            if operation in ('inspect', 'index'):
                value = self.agentBridgeIndex()
            elif operation == 'add-rectangle':
                value = self.agentBridgeAddRectangle(params)
            elif operation == 'save':
                value = self.agentBridgeSaveSnapshot(params)
            else:
                value = {'stopping': True}
            result = {'status': 'passed', 'job_id': request_id, **value}
        except Exception as exc:
            result = {'status': 'failed', 'job_id': request_id, 'error': str(exc)}
        # Cache before reporting: a report IO failure must never cause an edit replay.
        self.seen[request_id] = (signature, result)
        write_private(self.output / (request_id + '.report.json'), result)
        return result


class BridgeRuntime:
    """Socket thread handles transport; pump() alone touches layout objects."""

    def __init__(self, session):
        self.session = session
        self.pending = queue.Queue(maxsize=16)
        self.stop_event = threading.Event()
        self.temp = Path(tempfile.mkdtemp(prefix='chip-lab-'))
        self.token = secrets.token_hex(32)
        self.socket = str(self.temp / 'bridge.sock')
        self.token_file = self.temp / 'auth.json'
        write_private(self.token_file, {'token': self.token})
        runtime = self

        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                self.connection.settimeout(5)
                try:
                    line = self.rfile.readline(MAX_MESSAGE + 1)
                    if len(line) > MAX_MESSAGE or not line.endswith(b'\n'):
                        raise ValueError('Request too large or incomplete.')
                    request = json.loads(line)
                    token = request.pop('token', '')
                    if not isinstance(token, str) or not hmac.compare_digest(token, runtime.token):
                        raise ValueError('Authentication failed.')
                    item = {'request': request, 'event': threading.Event(), 'deadline': time.monotonic() + 20}
                    runtime.pending.put_nowait(item)
                    if not item['event'].wait(25):
                        raise ValueError('Timeout: outcome unknown; inspect state before retrying.')
                    result = item['result']
                except Exception as exc:
                    result = {'status': 'failed', 'error': str(exc)}
                try:
                    self.wfile.write(encoded(result) + b'\n')
                except OSError:
                    pass

        self.server = socketserver.UnixStreamServer(self.socket, Handler)
        os.chmod(self.socket, 0o600)
        self.descriptor = session.output / 'session.json'
        write_private(self.descriptor, {'socket': self.socket, 'auth_file': str(self.token_file),
                                      'mode': 'gui' if session.editor else 'headless',
                                      'operations': OPERATIONS, 'reports': str(session.output)})
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': 0.05}, daemon=True)
        self.thread.start()

    def pump(self):
        try:
            item = self.pending.get_nowait()
        except queue.Empty:
            return
        try:
            if time.monotonic() > item['deadline']:
                raise ValueError('Request expired before execution; no change applied.')
            result = self.session.dispatch(item['request'])
        except Exception as exc:
            result = {'status': 'failed', 'error': str(exc)}
        item['result'] = result
        item['event'].set()
        if result.get('stopping'):
            self.stop_event.set()

    def close(self):
        self.stop_event.set()
        self.server.shutdown()
        self.server.server_close()
        shutil.rmtree(self.temp)


def call(descriptor, operation, target=None, params=None, request_id=None):
    meta = json.loads(Path(descriptor).read_text())
    auth = json.loads(Path(meta['auth_file']).read_text())
    request = {'id': request_id or str(uuid.uuid4()), 'operation': operation,
               'target': target, 'params': params or {}, 'token': auth['token']}
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(30)
        sock.connect(meta['socket'])
        sock.sendall(encoded(request) + b'\n')
        with sock.makefile('rb') as stream:
            line = stream.readline(MAX_MESSAGE + 1)
    if len(line) > MAX_MESSAGE:
        raise ValueError('Bridge response too large.')
    return json.loads(line)


def serve(layout_file, cell_name, technology, output):
    import klayout.db as db
    layout = db.Layout()
    layout.read(str(layout_file))
    session = LayoutSession(db, lambda: (layout, layout.cell(cell_name), layout_file),
                            layout_file, cell_name, technology, output)
    runtime = BridgeRuntime(session)
    print(json.dumps({'session': str(runtime.descriptor), 'mode': 'headless'}), flush=True)
    try:
        while not runtime.stop_event.is_set():
            runtime.pump()
            time.sleep(0.01)
    finally:
        runtime.close()
