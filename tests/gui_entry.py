"""Surface GUI-macro exceptions on stderr instead of an unattended modal dialog."""
import os
from pathlib import Path
import runpy
import sys
import traceback

os.write(2, b'CHIP_LAB_GUI_START\n')
try:
    macro_state = runpy.run_path(str(Path(__file__).with_name('gui_bootstrap.py')), run_name='__main__')
except BaseException:
    os.write(2, traceback.format_exc().encode())
    os._exit(2)
