from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_closed_error_time_20260913 import accumulate


class ErrorTimeTests(unittest.TestCase):
    def test_counts_do_not_imply_time_share(self):
        nodes=[dict(step=i, exec_time=1, exit_code=1, term_out='unexpected', operators_used=[]) for i in range(1,10)]
        nodes.append(dict(step=10, exec_time=100, exit_code=0, term_out='', operators_used=[]))
        data=accumulate(nodes)
        self.assertEqual(data['nonzero_exit']['nodes'],9)
        self.assertEqual(data['nonzero_exit']['interpreter_seconds'],9)
        self.assertEqual(data['all_saved_executed']['interpreter_seconds'],109)

    def test_invalid_duration_fails(self):
        for duration in (-1, float('nan'), True):
            with self.assertRaises(ValueError): accumulate([dict(step=1, exec_time=duration)])

    def test_unexecuted_does_not_count(self):
        self.assertEqual(accumulate([dict(step=0,exec_time=100),dict(step=1,exec_time=None)]),{})


if __name__=='__main__': unittest.main()
