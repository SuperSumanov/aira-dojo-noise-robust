import unittest
from closed_rank_failure_audit_20261016 import classify

READY = '[2026-10-16 15:00:00,000] [jupyter_code_executor.py:112] Ready\n'
FAILED = '[2026-10-16 15:02:00,000] [jupyter_code_executor.py:105] Kernel did not become ready in time.\n'


class FailureAuditTests(unittest.TestCase):
    def test_source_text_not_output(self):
        text = 'print("... Running test inference...")\n' + READY + 'Timeout waiting for output from code block.'
        r = classify(text, dict(valid=False, timed_out=True))
        self.assertEqual(r['category'], 'candidate_execution_timeout')
        self.assertEqual(r['phase_announcements'], [])

    def test_ready_output_phase(self):
        text = READY + '... Running test inference...\nTimeout waiting for output from code block.'
        r = classify(text, dict(valid=False, timed_out=True))
        self.assertEqual(r['last_explicit_phase'], 'inference_announced')

    def test_cv_phase(self):
        text = READY + '... Total CV time: 264.3s\nTimeout waiting for output from code block.'
        r = classify(text, dict(valid=False, timed_out=True))
        self.assertEqual(r['last_explicit_phase'], 'cv_finished_announced')

    def test_infrastructure(self):
        r = classify(FAILED, dict(valid=False, timed_out=True))
        self.assertEqual(r['category'], 'infrastructure_kernel_not_ready')
        self.assertFalse(r['kernel_ready'])

    def test_valid(self):
        self.assertEqual(classify(READY, dict(valid=True, timed_out=False, exit_code=0))['category'], 'valid_output')

    def test_unknown_fails_closed(self):
        self.assertEqual(classify('', dict(valid=False, timed_out=False))['category'], 'unclassified_failure')

    def test_contradiction(self):
        with self.assertRaises(AssertionError):
            classify(READY + FAILED, dict(valid=False, timed_out=True))


if __name__ == '__main__':
    unittest.main()
