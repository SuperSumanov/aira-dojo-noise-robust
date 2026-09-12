import importlib.util
from pathlib import Path
import unittest
import ast

spec=importlib.util.spec_from_file_location('build',Path(__file__).parents[1]/'build_forets_readiness_source_20260912.py')
build=importlib.util.module_from_spec(spec);spec.loader.exec_module(build)


class SourcePatchTests(unittest.TestCase):
    def test_fail_closed_on_anchor_drift(self):
        for func in [build.patch_client,build.patch_executor]:
            with self.assertRaises(ValueError):func('def unexpected(): pass')

    def test_only_expected_files_targeted(self):
        self.assertEqual(set(build.EXPECTED),{'jupyter_client.py','jupyter_code_executor.py'})
        self.assertNotIn('paid_budget.py',build.EXPECTED)


if __name__=='__main__':unittest.main()
