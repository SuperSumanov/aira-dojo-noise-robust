import importlib.util
from pathlib import Path
import unittest

SOURCE = Path(__file__).parents[1] / 'scripts/task_feedback_rule_harm_20261002.py'
SPEC = importlib.util.spec_from_file_location('rule_harm', SOURCE)
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


class HarmTests(unittest.TestCase):
    def test_positive_mean_can_harm(self):
        d = M.decompose([0, 1, .5], [1, .8, .5], [True, True, False], [True, True, False])
        self.assertEqual((d['improved_rows'], d['harmed_rows'], d['metric_ties']), (1, 1, 1))
        self.assertGreater(d['net_change'], 0)

    def test_perfect_incumbent_attains_floor(self):
        d = M.decompose([1, 1], [.98, 1], [True, False], [True, False])
        self.assertAlmostEqual(d['net_change'], d['finite_set_worst_incumbent_difference'])
        self.assertLess(d['net_change'], 0)

    def test_changed_surface_can_tie(self):
        d = M.decompose([1], [1], [True], [True])
        self.assertEqual(d['changed_text_rows'], 1)
        self.assertEqual(d['metric_ties'], 1)

    def test_reject_non_target_change(self):
        with self.assertRaises(AssertionError):
            M.decompose([.5], [.6], [False], [True])

    def test_reject_nonfinite(self):
        with self.assertRaises(AssertionError):
            M.decompose([float('nan')], [1], [True], [True])

    def test_rule_does_not_apply(self):
        d = M.decompose([.4], [.4], [False], [False])
        self.assertEqual(d['net_change'], 0)
        self.assertIsNone(d['covered_rule_mean'])

    def test_local_auc_is_not_global_guarantee(self):
        from fractions import Fraction
        labels = [1, 0, 1, 0, 0]
        before = [.4, .6, .8, .3, .35]
        after = [.2, .1, .8, .3, .35]
        def auc(indices, predictions):
            pairs = [(i, j) for i in indices for j in indices if labels[i] == 1 and labels[j] == 0]
            return sum(Fraction(int(predictions[i] > predictions[j])) + Fraction(int(predictions[i] == predictions[j]), 2) for i, j in pairs) / len(pairs)
        self.assertEqual(before[2:], after[2:])
        self.assertEqual((auc(range(2), before), auc(range(2), after)), (0, 1))
        self.assertEqual((auc(range(5), before), auc(range(5), after)), (Fraction(5, 6), Fraction(2, 3)))


if __name__ == '__main__':
    unittest.main()
