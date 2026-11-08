"""Check the RCO control word maps to all three physical bank branches."""

import re
import unittest

from examples.rco.run import build_netlist, simulation_stop_us


class RcoNetlistTests(unittest.TestCase):
    def test_nine_bit_bank_is_shared_across_three_stages(self):
        deck = build_netlist("sky130", 169)
        self.assertIn("VMAIN main 0 1.8", deck)
        for stage in range(3):
            self.assertIn(f"XMAIN{stage} n{stage} bank{stage}", deck)
            self.assertIn(f"RDELAY{stage} d{stage} n{stage} 470k", deck)
            weights = [int(value) for value in re.findall(
                rf"^CB{stage}_\d+ cap{stage}_\d+ 0 (\d+)f$", deck, re.M)]
            self.assertEqual(weights, [5 << bit for bit in range(9)])
            self.assertEqual(sum(weights), 2555)
        levels = [float(value) for value in re.findall(
            r"^VB\d+ b\d+ 0 ([\d.]+)$", deck, re.M)]
        self.assertEqual(levels, [1.8 if 169 & (1 << bit) else 0 for bit in range(9)])

    def test_slow_codes_get_a_longer_transient(self):
        self.assertGreater(simulation_stop_us(511, True), simulation_stop_us(169, True))
        self.assertEqual(simulation_stop_us(169, False), 60)


if __name__ == "__main__":
    unittest.main()
