import unittest
from readout_comparison_pool_20260919 import pairs_summary

def rows(values,selected=(0,1)):
    return [dict(slot=i,original_selected=i in selected,valid=v is not None,score=v) for i,v in enumerate(values)]

class Tests(unittest.TestCase):
    def test_all_bad(self):
        out=pairs_summary(rows([None]*6));self.assertEqual(out['selected_vs_all_uniform_pairs'],dict(wins=0,ties=15,losses=0,pairs=15))
    def test_one_valid_selected(self):
        out=pairs_summary(rows([1,None,None,None,None,None]));self.assertEqual(out['selected_valid'],1)
        self.assertAlmostEqual(out['uniform_probability_any_valid'],1/3);self.assertEqual(out['selected_vs_all_uniform_pairs']['wins'],10)
    def test_one_valid_unselected(self):
        out=pairs_summary(rows([None,None,1,None,None,None]));self.assertEqual(out['selected_vs_all_uniform_pairs']['losses'],5)
    def test_quality_minimizes(self):
        out=pairs_summary(rows([1,2,3,4,5,6]));self.assertEqual(out['selected_vs_all_uniform_pairs']['wins'],10)
    def test_unknown_not_failure(self):
        rs=rows([1]*6);rs[3]['valid']=None;self.assertEqual(pairs_summary(rs)['status'],'UNKNOWN_NO_EFFECT_CLAIM')
    def test_duplicate_rejected(self):
        rs=rows([1]*6);rs[2]['slot']=0
        with self.assertRaises(ValueError):pairs_summary(rs)
    def test_missing_candidate_rejected(self):
        with self.assertRaises(ValueError):pairs_summary(rows([1]*5))
    def test_nan_rejected(self):
        with self.assertRaises(ValueError):pairs_summary(rows([float('nan')]*6))

if __name__=='__main__':unittest.main()
