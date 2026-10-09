import hashlib
import unittest
from exposure_opportunity_readout import summarize


def fixture(role, step, value, parents=(), maximize=True, code=None):
    code = str(step) if code is None else code
    node = dict(operators_used=[role], step=step, metric=value, metric_maximize=maximize,
                code=code, parents=list(parents))
    candidate = dict(valid=value is not None, score=value, elapsed_seconds=10+step,
                     code_sha256=hashlib.sha256(code.encode()).hexdigest())
    return node, candidate


class OpportunityTests(unittest.TestCase):
    def test_parent_gain_is_not_record_gain(self):
        pairs = [fixture('draft', 1, .8), fixture('draft', 2, .5), fixture('improve', 3, .6, [2])]
        result = summarize(*zip(*pairs), 1)
        self.assertEqual(result['better_than_parent'], 1)
        self.assertEqual(result['strict_incumbent_improvements'], 0)
    def test_minimize(self):
        pairs = [fixture('draft', 1, .8, maximize=False), fixture('improve', 2, .7, [1], maximize=False)]
        result = summarize(*zip(*pairs), -1)
        self.assertEqual(result['strict_incumbent_improvements'], 1)
        self.assertEqual(result['improve_rows'][0]['parent_oriented_delta'], '0.1')
    def test_invalid_and_missing_parent_retained(self):
        pairs = [fixture('draft', 1, None), fixture('improve', 2, .8, [1]), fixture('improve', 3, None, [2])]
        result = summarize(*zip(*pairs), 1)
        self.assertEqual(result['completed_improve_attempts'], 2)
        self.assertEqual(result['valid_improve_returns'], 1)
        self.assertEqual(result['paired_valid_parent_edges'], 0)
    def test_same_code_uses_chronological_receipts(self):
        pairs = [fixture('draft', 1, .5, code='pass'), fixture('improve', 2, .6, [1], code='pass')]
        result = summarize(*zip(*pairs), 1)
        self.assertEqual(result['improve_rows'][0]['parent_oriented_delta'], '0.1')
    def test_metric_mismatch_refused(self):
        node, candidate = fixture('draft', 1, .5)
        node['metric'] = .6
        with self.assertRaises(ValueError):
            summarize([node], [candidate], 1)
    def test_direction_mismatch_refused(self):
        node, candidate = fixture('draft', 1, .5)
        with self.assertRaises(ValueError):
            summarize([node], [candidate], -1)
    def test_empty_stays_empty(self):
        self.assertEqual(summarize([], [], 1)['strict_incumbent_improvements'], 0)
    def test_missing_code_match_not_imputed(self):
        node, _ = fixture('improve', 1, .5, [0])
        result = summarize([node], [], 1)
        self.assertEqual(result['unmatched_recorded_nodes'], 1)
        self.assertEqual(result['completed_improve_attempts'], 0)


if __name__ == '__main__':
    unittest.main()
