import tempfile
import unittest
from pathlib import Path
from chip_lab.cli import build_index, check_rc, private_json, search


class LabTests(unittest.TestCase):
    def test_reports_are_private_and_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'result.json'
            private_json(path, {'status': 'passed'})
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(FileExistsError):
                private_json(path, {'status': 'changed'})

    def test_rc_measurement_is_checked_against_physics(self):
        self.assertAlmostEqual(check_rc('f_3db = 1.59155e5')['cutoff_hz'], 159155)
        for bad in ('', 'f_3db = 200', 'f_3db = 1e999', 'f_3db = 159155\nf_3db = 159155'):
            with self.subTest(log=bad), self.assertRaises(ValueError):
                check_rc(bad)

    def test_reference_search_handles_fts_punctuation(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / 'knowledge.sqlite'
            self.assertGreater(build_index(db)['indexed_documents'], 0)
            result = search(db, '"matching" OR gm/Id; DROP TABLE notes; --')
            self.assertTrue(result['matches'])
            self.assertTrue(search(db, 'matching')['matches'])


if __name__ == '__main__':
    unittest.main()
