"""KLayout batch fixture generator; synthetic layers only."""
from pathlib import Path
import pya

root = Path(globals()['output'])
root.mkdir(parents=True, exist_ok=True)
for name, width in [('good', 1000), ('bad', 100)]:
    layout = pya.Layout()
    layout.dbu = 0.001
    cell = layout.create_cell('SCRATCH')
    cell.shapes(layout.layer(1, 0)).insert(pya.Box(0, 0, width, 2000))
    layout.write(str(root / (name + '.gds')))
