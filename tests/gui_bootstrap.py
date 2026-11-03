"""Runs inside KLayout, only for the controlled GUI integration test."""
import os
from pathlib import Path
import runpy
import pya

root = Path(os.environ['LAB_GUI_TEST_OUTPUT'])
root.mkdir(parents=True, exist_ok=True)
layout = pya.Layout()
layout.dbu = 0.001
cell = layout.create_cell('SCRATCH')
layout.create_cell('OTHER')
cell.shapes(layout.layer(1, 0)).insert(pya.Box(0, 0, 1000, 2000))
layout.write(str(root / 'input.gds'))
os.environ['LAB_BRIDGE_LAYOUT'] = str(root / 'input.gds')
os.environ['LAB_BRIDGE_CELL'] = 'SCRATCH'
os.environ['LAB_BRIDGE_OUTPUT'] = str(root / 'session')
macro = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'bridge/start_klayout_bridge.py'), run_name='__main__')
runtime = macro['_chip_lab_runtime']
exit_timer = pya.QTimer()


def watch():
    if (root / 'switch-cell').exists():
        cv = pya.LayoutView.current().active_cellview()
        cv.cell = cv.layout().cell('OTHER')
        (root / 'switch-cell').unlink()
        (root / 'switched').touch()
    if runtime.stop_event.is_set():
        exit_timer.stop()
        pya.Application.instance().exit(0)


exit_timer.timeout = watch
exit_timer.start(50)
