"""Run as a KLayout macro: klayout -e -rr /path/to/this/file.py.

Open a saved design and select its cell first. Configure LAB_BRIDGE_* environment
variables when launching KLayout. No shell execution is exposed by the bridge.
"""
import os
from pathlib import Path
import sys
import uuid
import pya

LAB_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB_ROOT / 'src'))
from chip_lab.bridge import BridgeRuntime, LayoutSession


def start_bridge():
    if os.environ.get('LAB_BRIDGE_LAYOUT'):
        cv = pya.Application.instance().main_window().load_layout(os.environ['LAB_BRIDGE_LAYOUT'], 1)
        if os.environ.get('LAB_BRIDGE_CELL'):
            selected = cv.layout().cell(os.environ['LAB_BRIDGE_CELL'])
            if selected is None:
                raise ValueError('Requested cell is not present in the layout.')
            cv.cell = selected
    view = pya.LayoutView.current()
    if view is None or not view.active_cellview().is_valid():
        raise ValueError('Open a saved GDS/OAS and select a cell before starting the bridge.')
    cv = view.active_cellview()
    source, cell = cv.filename(), cv.cell.name

    def active():
        current = pya.LayoutView.current()
        if current is None or not current.active_cellview().is_valid():
            raise ValueError('No active editor cellview.')
        cv = current.active_cellview()
        if current != view:
            raise ValueError('Active layout view changed.')
        return cv.layout(), cv.cell, cv.filename()

    profile = Path(os.environ.get('LAB_BRIDGE_TECH', LAB_ROOT / 'config/technology-scratch.json'))
    output = Path(os.environ.get('LAB_BRIDGE_OUTPUT', LAB_ROOT / 'runs/bridge' / str(uuid.uuid4())))
    session = LayoutSession(pya, active, source, cell, profile, output, editor=view)
    runtime = BridgeRuntime(session)
    timer = pya.QTimer()

    def pump():
        runtime.pump()
        if runtime.stop_event.is_set():
            timer.stop()
            runtime.close()

    timer.timeout = pump
    timer.start(25)
    # Keep Python objects alive after macro evaluation.
    global _chip_lab_runtime, _chip_lab_timer
    _chip_lab_runtime, _chip_lab_timer = runtime, timer
    print('chip-lab bridge session: ' + str(runtime.descriptor), flush=True)
    return runtime


if __name__ == '__main__':
    start_bridge()
