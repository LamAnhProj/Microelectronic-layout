"""Checks that R-C topology validation sees shorts and wrong MOS terminals."""

import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "examples"))
from rcx_validate import validate_rcx


PORTS = ("IN", "OUT", "VSS", "VDD")
DEVICES = {"nfet": ("OUT", "IN", "VSS", "VSS"),
           "pfet": ("OUT", "IN", "VDD", "VDD")}
NETLIST = """.subckt inverter IN OUT VSS VDD
X0 OUT.n IN.n VSS.n VSS nfet
X1 OUT.p IN.p VDD.p VDD pfet
R0 OUT OUT.n 1.2
R1 OUT OUT.p 1.4
R2 IN IN.n 2.0
R3 IN IN.p 2.1
R4 VSS VSS.n 0.3
R5 VDD VDD.p 0.4
C0 OUT VSS 0.1f
.ends
"""


class RcxTopologyTests(unittest.TestCase):
    def test_valid_resistor_network(self):
        self.assertEqual(validate_rcx(NETLIST, PORTS, DEVICES),
                         {"resistor_count": 6, "capacitor_count": 1})

    def test_rejects_cross_net_short(self):
        with self.assertRaisesRegex(ValueError, "short"):
            validate_rcx(NETLIST.replace("R0 OUT OUT.n", "R0 IN OUT"),
                         PORTS, DEVICES)

    def test_rejects_wrong_device_terminal(self):
        with self.assertRaisesRegex(ValueError, "terminals"):
            validate_rcx(NETLIST.replace("X0 OUT.n IN.n", "X0 OUT.n VDD.p"),
                         PORTS, DEVICES)


if __name__ == "__main__":
    unittest.main()
