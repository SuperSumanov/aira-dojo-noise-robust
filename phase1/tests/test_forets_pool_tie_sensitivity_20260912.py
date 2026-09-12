import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location('ties',Path(__file__).resolve().parents[1]/'forets_pool_tie_sensitivity_20260912.py')
t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)

class TieTests(unittest.TestCase):
    def test_favorable_frozen_tie_can_disappear(self):
        r=t.one([{'valid':v} for v in [True,False,False,False]],[2.5,1,4,2.5])
        self.assertEqual(r['uniformly_randomized_cutoff_tie_gain_bounds'],[0,0])
        self.assertEqual(r['arbitrary_admissible_tie_gain_bounds'],[-.25,.25])
    def test_no_boundary_tie_keeps_gain(self):
        r=t.one([{'valid':v} for v in [False,False,True,False]],[1,2,4,3])
        self.assertEqual(r['arbitrary_admissible_tie_gain_bounds'],[.25,.25])
    def test_all_scores_tied_is_uniform_in_expectation(self):
        for values in ([True,False,False,False],[True,None,False,None]):
            r=t.one([{'valid':v} for v in values],[1]*4)
            self.assertEqual(r['uniformly_randomized_cutoff_tie_gain_bounds'],[0,0])
if __name__=='__main__':unittest.main()
