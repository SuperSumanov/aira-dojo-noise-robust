from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_closed_measurement_gaps_20260913 import accumulate, submission_validity


class MeasurementGapTests(unittest.TestCase):
    def test_zero_is_a_real_metric(self):
        counts, gaps = accumulate([dict(step=1, exec_time=1, exit_code=0,
            metric=0.0, is_buggy=False, metric_info={'valid_submission': 1})])
        self.assertEqual(counts['zero_valid_metric_present'], 1)
        self.assertEqual(gaps, [])

    def test_unknown_not_failed_or_valid(self):
        counts, gaps = accumulate([dict(step=1, exec_time=1, metric=None, is_buggy=True)])
        self.assertEqual(counts['exit_unknown'], 1)
        self.assertNotIn('zero_exit_valid_submission', counts)
        self.assertEqual(gaps, [])

    def test_flat_and_nested_conflict_rejected(self):
        with self.assertRaises(ValueError): submission_validity(dict(
            metric_info={'valid_submission': 1}, **{'metric_info/valid_submission': 0}))

    def test_valid_but_missing_not_automatic_recovery(self):
        counts, gaps = accumulate([dict(step=1, exec_time=1, exit_code=0,
            metric=None, is_buggy=True, **{'metric_info/valid_submission': 1})])
        self.assertEqual(counts['zero_valid_metric_missing'], 1)
        self.assertEqual(gaps[0]['is_buggy'], True)
        self.assertNotIn('recovered', gaps[0])


if __name__ == '__main__': unittest.main()
