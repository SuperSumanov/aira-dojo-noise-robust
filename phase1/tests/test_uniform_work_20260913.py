from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_closed_uniform_work_20260913 import journal_counts


class WorkTests(unittest.TestCase):
    def test_root_unexecuted_and_unknown(self):
        rows = [dict(step=0, exec_time=1), dict(step=1, exec_time=None),
            dict(step=2, exec_time=1, exit_code=1, term_out='unrecognized', metric_info={})]
        counts = journal_counts(rows)
        self.assertEqual(counts['saved_executed_nodes'], 1)
        self.assertEqual(counts['nonzero_nodes'], 1)
        self.assertEqual(counts['unclassified_nonzero_nodes'], 1)
        self.assertEqual(counts['valid_submission_nodes'], 0)

    def test_success_is_not_failure_from_text(self):
        counts = journal_counts([dict(step=1, exec_time=1, exit_code=0,
            term_out='Cannot setitem on a Categorical with a new category', metric_info={'valid_submission': 1})])
        self.assertNotIn('error_family:categorical_new_fill_value', counts)
        self.assertEqual(counts['valid_submission_nodes'], 1)

    def test_failure_family(self):
        counts = journal_counts([dict(step=1, exec_time=1, exit_code=1,
            term_out=['Cannot setitem on a Categorical with a new category'], metric_info={})])
        self.assertEqual(counts['error_family:categorical_new_fill_value'], 1)


if __name__ == '__main__': unittest.main()
