import unittest

from dashboard.wave_analysis import analyze_trace, crossing


class WaveAnalysisTests(unittest.TestCase):
    def test_interpolates_circuit_delays_and_output_slew(self):
        # A 1 V inverter: input rises at 1 ns, falls at 3 ns; output lags.
        samples = [
            [0.0, 0.0, 1.0], [0.9, 0.0, 1.0],
            [1.0, 0.5, 1.0], [1.1, 1.0, 0.9],
            [1.2, 1.0, 0.5], [1.3, 1.0, 0.1], [1.4, 1.0, 0.0],
            [2.9, 1.0, 0.0], [3.0, 0.5, 0.0], [3.1, 0.0, 0.1],
            [3.2, 0.0, 0.5], [3.3, 0.0, 0.9], [3.4, 0.0, 1.0],
        ]
        result = analyze_trace(samples, 1.0)
        self.assertAlmostEqual(result["tphl_ps"], 200.0)
        self.assertAlmostEqual(result["tplh_ps"], 200.0)
        self.assertAlmostEqual(result["fall_90_10_ps"], 200.0)
        self.assertAlmostEqual(result["rise_10_90_ps"], 200.0)

    def test_rejects_missing_output_crossing(self):
        samples = [[0.0, 0.0, 1.0], [1.0, 0.5, 1.0],
                   [1.1, 1.0, 1.0], [3.0, 0.5, 1.0], [3.1, 0.0, 1.0]]
        with self.assertRaisesRegex(ValueError, "Missing fall crossing"):
            analyze_trace(samples, 1.0)

    def test_crossing_uses_linear_interpolation(self):
        self.assertAlmostEqual(
            crossing([[0.0, 0.0, 0.0], [2.0, 1.0, 0.0]], 1, 0.25,
                     "rise", 0.0), 0.5)


if __name__ == "__main__":
    unittest.main()
