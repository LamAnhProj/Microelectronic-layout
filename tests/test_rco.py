"""Check the RCO control word maps to all three physical bank branches."""

import re
import unittest

from examples.rco.run import GF_BALANCED_MIM_WIDTH_UM, build_netlist, simulation_stop_us


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

    def test_pdk_bank_uses_mim_series_and_parallel_weights(self):
        for process, unit, resistor in (
            ("sky130", "sky130_fd_pr__cap_mim_m3_2 w=4.5 l=4.5",
             "sky130_fd_pr__res_xhigh_po_1p41 w=1.41 l=330"),
            ("gf180", "cap_mim_2f0_m4m5_noshield c_width=5u c_length=5u",
             "ppolyf_u_1k r_width=1u r_length=440u"),
        ):
            deck = build_netlist(process, 154, passives="pdk", bank_style="binary")
            self.assertEqual(deck.count(unit), 231 if process == "sky130" else 183)
            self.assertEqual(deck.count(resistor), 3)
            self.assertEqual(len(re.findall(r"^XCBASE\d+ ", deck, re.M)), 3)
            for stage in range(3):
                for bit in range(9):
                    count = len(re.findall(rf"^XC{stage}_{bit}_\d+_\d+ ", deck, re.M))
                    self.assertEqual(count, 1 << abs(bit - (3 if process == "sky130" else 4)))
            self.assertNotIn("RDELAY0 d0 n0 470k", deck)

    def test_guarded_gf_bank_enlarges_higher_mim_bits(self):
        deck = build_netlist("gf180", 211, passives="pdk", bank_style="guarded")
        matches = re.findall(
            r"^XC0_(\d+)_0_0 \S+ \S+ cap_mim_2f0_m4m5_noshield c_width=([\d.]+)u",
            deck, re.M)
        widths = [float(width) for _, width in matches]
        self.assertEqual(len(widths), 9)
        self.assertEqual(widths[0], 5.0)
        self.assertTrue(all(b > a for a, b in zip(widths, widths[1:])))

    def test_balanced_gf_bank_applies_each_measured_width_to_all_stages(self):
        deck = build_netlist("gf180", 117, passives="pdk", bank_style="balanced")
        for stage in range(3):
            for bit, width in enumerate(GF_BALANCED_MIM_WIDTH_UM):
                name = rf"^XC{stage}_{bit}_0_0 \S+ \S+ cap_mim_2f0_m4m5_noshield c_width=([\d.]+)u"
                match = re.search(name, deck, re.M)
                self.assertIsNotNone(match)
                self.assertEqual(float(match.group(1)), width)


if __name__ == "__main__":
    unittest.main()
