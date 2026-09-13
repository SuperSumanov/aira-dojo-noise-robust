import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_debug_error_edges_20260913 import edges


class EdgeTests(unittest.TestCase):
    def setUp(self):
        self.a = dict(step=1, parents=[0], operators_used=['draft'], code='one',
            term_out='TypeError: Cannot setitem on a Categorical with a new category',
            exec_time=1, exit_code=1, metric_info={})
        self.b = dict(self.a, step=2, parents=[1], operators_used=['debug', 'analysis'], code='two')

    def test_real_edge(self):
        row = edges([self.a, self.b])[0]
        self.assertEqual(row['same_failed_families'], ['categorical_new_fill_value'])
        self.assertTrue(row['code_bytes_changed'])

    def test_parallel_is_not_debug(self):
        self.b.update(parents=[0], operators_used=['draft'])
        self.assertEqual(edges([self.a, self.b]), [])

    def test_missing_and_bad_parent(self):
        self.assertTrue(edges([self.b])[0]['parent_missing'])
        self.b['parents'] = [2]
        with self.assertRaises(ValueError): edges([self.a, self.b])

    def test_success_not_recurring_failure(self):
        self.b.update(exit_code=0, metric_info={'valid_submission': 1})
        row = edges([self.a, self.b])[0]
        self.assertEqual(row['same_failed_families'], [])
        self.assertTrue(row['child_valid_submission'])


if __name__ == '__main__': unittest.main()
