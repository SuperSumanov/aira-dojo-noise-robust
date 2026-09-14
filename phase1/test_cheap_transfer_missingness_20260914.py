import itertools,unittest
from cheap_transfer_missingness_20260914 import bounds
class Tests(unittest.TestCase):
    def test_all_label_policy_combinations(self):
        for a,b in itertools.product(([0.,1.],[1.,0.],[.5,.5]),repeat=2):
            for labels in itertools.product((0,1,None),repeat=2):
                lower,upper=bounds(a,b,labels)
                self.assertLessEqual(lower,upper);self.assertGreaterEqual(lower,-1);self.assertLessEqual(upper,1)
    def test_unknowns_cancel_for_identical_policy(self):
        self.assertEqual(bounds([1.,0.],[1.,0.],[None,None]),(0,0))
        self.assertEqual(bounds([1.,0.],[0.,1.],[None,None]),(-1,1))
        self.assertEqual(bounds([1.,0.],[0.,1.],[1,None]),(0,1))
    def test_ties_and_known_points(self):
        self.assertEqual(bounds([1.,0.],[.5,.5],[1,0]),(.5,.5))
        self.assertEqual(bounds([.5,.5],[1.,0.],[None,0]),(-.5,0))
    def test_bad_input(self):
        with self.assertRaises(ValueError):bounds([float('nan'),0.],[1.,0.],[0,1])
        with self.assertRaises(ValueError):bounds([1.,0.],[1.,0.],[False,None])
if __name__=='__main__':unittest.main()
