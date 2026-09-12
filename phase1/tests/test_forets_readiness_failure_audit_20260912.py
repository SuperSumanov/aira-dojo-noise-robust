import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('audit',Path(__file__).parents[1]/'forets_readiness_failure_audit_20260912.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)


class FailureStageTests(unittest.TestCase):
    def test_ready_failure_takes_precedence(self):
        lines=['ERROR:','Kernel did not become ready in time.',
               'TimeoutError: Execution exceeded the time limit of 5 minutes']
        self.assertEqual(audit.classification(lines,1),'kernel_readiness_failure_before_candidate_dispatch')

    def test_actual_reported_timeout(self):
        self.assertEqual(audit.classification(['ERROR: Timeout waiting for output from code block.',
            'TimeoutError: Execution exceeded the time limit of 5 minutes'],1),'reported_execution_timeout_after_readiness')

    def test_success_and_other(self):
        self.assertEqual(audit.classification([],0),'exit_zero')
        self.assertEqual(audit.classification(['ImportError: something'],1),'candidate_code_error')
        with self.assertRaises(ValueError):audit.classification(['Kernel did not become ready in time.'],0)


if __name__=='__main__':unittest.main()
