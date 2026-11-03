import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from chip_lab.circuit import run_circuit, validate_manifest
from chip_lab.cli import ROOT


class CircuitManifestTests(unittest.TestCase):
    def setUp(self):
        self.source = ROOT / 'examples/rc_lowpass'
        self.manifest = json.loads((self.source / 'design.json').read_text())

    def test_requires_bounded_inputs_and_acceptance_criteria(self):
        validate_manifest(self.manifest, self.source)
        for update in ({'files': ['../outside.spice'], 'netlist': '../outside.spice'},
                       {'measurements': {}}, {'measurements': {'cutoff': {'expected': True, 'relative_tolerance': 0.1}}},
                       {'measurements': {'cutoff': {'expected': 10, 'relative_tolerance': -1}}}):
            manifest = copy.deepcopy(self.manifest)
            manifest.update(update)
            with self.subTest(update=update), self.assertRaises(ValueError):
                validate_manifest(manifest, self.source)

    @unittest.skipUnless(shutil.which('ngspice'), 'ngspice not installed in this interpreter environment')
    def test_actual_simulation_checks_success_and_failed_spec(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copyfile(self.source / 'circuit.spice', root / 'circuit.spice')
            design = root / 'design.json'
            design.write_text(json.dumps(self.manifest))
            passed = run_circuit(design, root / 'runs')
            self.assertEqual(passed['status'], 'passed', passed)
            self.assertAlmostEqual(passed['measurements']['f_3db']['measured'], 159158, delta=10)
            self.manifest['measurements']['f_3db']['expected'] = 100
            design.write_text(json.dumps(self.manifest))
            failed = run_circuit(design, root / 'runs')
            self.assertEqual(failed['status'], 'failed', failed)
            self.assertFalse(failed['measurements']['f_3db']['passed'])
