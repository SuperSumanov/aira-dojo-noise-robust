import copy
import unittest

from audit_homogeneous_result import validate_matrix, paired_latencies, descriptive
from homogeneous_trial import schedule


class AuditTests(unittest.TestCase):
    def test_matrix(self):
        validate_matrix(schedule())

    def test_missing_slot(self):
        with self.assertRaises(ValueError):
            validate_matrix(schedule()[:-1])

    def test_replica_duplicate(self):
        rows = copy.deepcopy(schedule())
        rows[1]['replica'] = 0
        with self.assertRaises(ValueError):
            validate_matrix(rows)

    def test_seed_mismatch(self):
        rows = copy.deepcopy(schedule())
        rows[0]['source_seed'] = 99
        with self.assertRaises(ValueError):
            validate_matrix(rows)

    def test_latency_tradeoff_not_hidden(self):
        serial = {0:dict(candidate_seconds=10, response_seconds=12),
                  1:dict(candidate_seconds=10, response_seconds=24)}
        share = {0:dict(candidate_seconds=15, response_seconds=17),
                 1:dict(candidate_seconds=15, response_seconds=17)}
        rows = paired_latencies(serial, share)
        self.assertEqual([r['candidate_slowdown'] for r in rows], [1.5, 1.5])
        self.assertGreater(rows[0]['response_ratio'], 1)
        self.assertLess(rows[1]['response_ratio'], 1)

    def test_nonpositive_duration_rejected(self):
        block = {r:dict(candidate_seconds=0, response_seconds=1) for r in (0,1)}
        with self.assertRaises(ValueError):
            paired_latencies(block, block)

    def test_no_single_sample_variance(self):
        self.assertIsNone(descriptive([1.2])['sample_std'])
        self.assertIsNone(descriptive([])['median'])


if __name__ == '__main__':
    unittest.main()
