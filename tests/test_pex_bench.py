import unittest

from dashboard.pex_bench import build_deck, dc_trip_v, parse_table


SOURCE = """.lib /pdk/model.lib tt
.temp 25
VDD vdd 0 1.8
VIN in 0 PULSE(0 1.8 1n 20p 20p 2n 4n)
CLOAD out 0 5f
.include inverter_rcx.spice
XINV out in 0 vdd inverter
.control
tran 2p 12n
wrdata waveform.txt v(in) v(out)
.endc
.end
"""


class PexBenchTests(unittest.TestCase):
    def test_dc_and_ac_keep_extraction_and_load(self):
        dc, dc_settings = build_deck(SOURCE, "dc", 1.8)
        ac, ac_settings = build_deck(SOURCE, "ac", 1.8, 0.86)
        for deck in (dc, ac):
            self.assertIn(".include inverter_rcx.spice", deck)
            self.assertIn("CLOAD out 0 5f", deck)
            self.assertIn(".lib /pdk/model.lib tt", deck)
            self.assertNotIn("PULSE", deck)
        self.assertIn("dc VIN 0 1.8 0.01", dc)
        self.assertIn("VIN in 0 DC 0.860000 AC 1", ac)
        self.assertIn("ac dec 40 1k 100G", ac)
        self.assertEqual(dc_settings["output_load_ff"], 5)
        self.assertEqual(ac_settings["input_bias_v"], 0.86)

    def test_interpolates_dc_trip_and_rejects_bad_bias(self):
        rows = [[0, 0, 1.8], [0.8, 0.8, 1.0], [1.0, 1.0, 0.7]]
        self.assertAlmostEqual(dc_trip_v(rows), 0.88)
        with self.assertRaisesRegex(ValueError, "AC bias"):
            build_deck(SOURCE, "ac", 1.8, 2.0)

    def test_table_requires_ordered_finite_data(self):
        data = "frequency gain phase\n" + "\n".join(f"{i} {i/2} 0" for i in range(1, 22))
        self.assertEqual(len(parse_table(data)), 21)
        with self.assertRaisesRegex(ValueError, "unordered"):
            parse_table(data.replace("20 10.0 0", "10 10.0 0"))


if __name__ == "__main__":
    unittest.main()
