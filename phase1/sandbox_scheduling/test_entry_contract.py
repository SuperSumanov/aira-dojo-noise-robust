"""Zero GPU/candidate executions. Reproduce CLI plumbing collision only."""
import argparse
import contextlib
import io
import sys
import unittest
from unittest.mock import patch
from entry_contract import SCRIPT_ENTRY,setup_cell


class EntryContractTests(unittest.TestCase):
    def parser(self):
        parser=argparse.ArgumentParser()
        parser.add_argument('--debug',action='store_true')
        return parser

    def test_kernel_arguments_fail_with_exit_two(self):
        with patch.object(sys,'argv',['ipykernel_launcher.py','-f','connection.json']),contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:self.parser().parse_args()
        self.assertEqual(caught.exception.code,2)

    def test_default_script_contract_no_debug_or_algorithm_change(self):
        with patch.object(sys,'argv',['ipykernel_launcher.py','-f','connection.json']):
            exec(SCRIPT_ENTRY,{})
            self.assertEqual(sys.argv,['candidate.py'])
            self.assertFalse(self.parser().parse_args().debug)

    def test_setup_syntax_and_seed_validation(self):
        compile(setup_cell(130701),'setup','exec')
        for value in (-1,'130701',True):
            with self.assertRaises(ValueError):setup_cell(value)


if __name__=='__main__':unittest.main()
