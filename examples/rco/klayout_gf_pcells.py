"""Register the installed GF180MCU KLayout API PCell library for a lab session.

Pass this file to native KLayout with ``-rm``. It registers *new* editable
PCell generators; it does not convert Magic-exported GDS cells into PCells.
"""

from pathlib import Path
import os
import sys

import pya


ROOT = Path(__file__).resolve().parents[2]
MACROS = ROOT / "pdks" / "volare" / "gf180mcuD" / "libs.tech" / "klayout" / "tech" / "pymacros"
os.environ.setdefault("GF_PDK_OPTION", "D")
if str(MACROS) not in sys.path:
    sys.path.insert(0, str(MACROS))

if pya.Library.library_by_name("gf180mcu_klayoutapi") is None:
    from klayout_api_cells import gf180mcu_klayoutapi
    gf180mcu_klayoutapi()

library = pya.Library.library_by_name("gf180mcu_klayoutapi")
if library is None or not {"nfet", "pfet", "cap_mim", "ppolyf_u_resistor"}.issubset(
        set(library.layout().pcell_names())):
    raise RuntimeError("GF180MCU KLayout API PCells did not register")
print("Chip Lab: GF180MCU editable KLayout API PCell library registered")
