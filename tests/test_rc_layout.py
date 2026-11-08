"""Coordinate and network checks for the read-only R-C layout overlay."""

import unittest

from dashboard.rc_layout import analyze_rc_layout, effective_ohms


LAYOUT = """box values 0um 0um 1um 1um
label IN c metal2
box values 2um 0um 3um 1um
label OUT c metal2
box values 0um 2um 1um 3um
label VSS c metal2
box values 2um 2um 3um 3um
label VDD c metal2
"""
FLAT = """scale 1000 1 0.5
port "IN" 1 0 0 200 200 m2
port "OUT" 2 400 0 600 200 m2
port "VSS" 3 0 400 200 600 m2
port "VDD" 4 400 400 600 600 m2
"""
RESIST = """scale 1000 1 0.5
rnode "IN" 0 0 0 0 0
rnode "IN.t0" 0 0 100 0 0
rnode "OUT" 0 0 400 0 0
rnode "VSS" 0 0 0 400 0
rnode "VDD" 0 0 400 400 0
resist "IN" "IN.t0" 10
"""
SPICE = """.subckt inverter IN OUT VSS VDD
X0 OUT IN.t0 VSS VSS nfet_03v3
X1 OUT IN.t0 VDD VDD pfet_03v3
R0 IN IN.t0 10
C0 IN.t0 VSS 0.1f
.ends
"""


class RcLayoutTests(unittest.TestCase):
    def test_aligns_nodes_and_solves_terminal_resistance(self):
        result = analyze_rc_layout("gf180", LAYOUT, FLAT, RESIST, SPICE,
                                   [0, 0, 3, 3])
        self.assertAlmostEqual(result["coordinate_um_per_magic_unit"], 0.005)
        self.assertEqual(result["segments"][0]["b_xy"], [0.5, 0.0])
        gates = [item for item in result["terminals"] if item["terminal"] == "gate"]
        self.assertEqual([item["effective_ohm"] for item in gates], [10, 10])

    def test_rejects_misaligned_port_geometry(self):
        with self.assertRaisesRegex(ValueError, "does not align"):
            analyze_rc_layout("gf180", LAYOUT.replace("2um 0um 3um 1um",
                                                       "2.1um 0um 3.1um 1um"),
                              FLAT, RESIST, SPICE, [0, 0, 3.1, 3])

    def test_parallel_effective_resistance(self):
        edges = [{"a": "A", "b": "B", "ohm": 10},
                 {"a": "B", "b": "C", "ohm": 10},
                 {"a": "A", "b": "C", "ohm": 20}]
        self.assertAlmostEqual(effective_ohms("A", "C", edges), 10)


if __name__ == "__main__":
    unittest.main()
