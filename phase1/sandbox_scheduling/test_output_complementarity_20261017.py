import unittest
import numpy as np
from closed_output_complementarity_20261017 import compare, TASKS


class Complementarity(unittest.TestCase):
    def test_opposite_errors_cancel(self):
        y = np.full(8, .5)
        m = np.array([np.full(8, .4), np.full(8, .6)])
        mask = np.array([True]*4 + [False]*4)
        r = compare(m, y, (mask, ~mask), TASKS[1])
        self.assertAlmostEqual(r['full_development']['best_single'], .1)
        self.assertAlmostEqual(r['full_development']['uniform'], 0.)
        self.assertAlmostEqual(r['full_development']['oracle_pair_gain'], .1)
        for fold in r['post_adaptive_resplit_sensitivity']:
            self.assertAlmostEqual(fold['values']['greedy20'], 0.)

    def test_single_library_is_not_missing_or_gain(self):
        y = np.array([0, 1, 0, 1, 0, 1, 0, 1])
        m = np.array([[.2, .8, .3, .7, .6, .4, .1, .9]])
        mask = np.array([True]*4 + [False]*4)
        r = compare(m, y, (mask, ~mask), TASKS[0])
        self.assertEqual(r['full_development']['uniform_gain'], 0.)
        self.assertEqual(r['full_development']['oracle_pair_gain'], 0.)
        for fold in r['post_adaptive_resplit_sensitivity']:
            self.assertTrue(all(abs(v) < 1e-12 for v in fold['gains'].values()))

    def test_duplicate_outputs_give_no_artificial_complementarity(self):
        y = np.array([.4, .6]*4)
        m = np.full((3, 8), .5)
        mask = np.array([True]*4 + [False]*4)
        r = compare(m, y, (mask, ~mask), TASKS[1])
        self.assertAlmostEqual(r['full_development']['uniform_gain'], 0.)
        self.assertAlmostEqual(r['full_development']['oracle_pair_gain'], 0.)


if __name__ == '__main__':
    unittest.main()
