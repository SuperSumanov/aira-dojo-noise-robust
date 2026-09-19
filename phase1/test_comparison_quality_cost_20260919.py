import unittest
from analyze_comparison_quality_cost_20260919 import analyze


def rows(values,costs):
    return [dict(slot=i,original_selected=i<2,valid=v is not None,score=v,wall_seconds=c) for i,(v,c) in enumerate(zip(values,costs))]


class QualityCostTests(unittest.TestCase):
    def test_fast_best_is_not_dominated(self):
        r=analyze(rows([1,None,2,3,4,None],[1,1,10,10,10,10]))
        self.assertTrue(r['selected_is_pareto_undominated'])
        self.assertEqual(len(r['pairs_dominated_by_selected']),14)
    def test_expensive_bad_is_dominated(self):
        r=analyze(rows([4,None,1,2,3,None],[100,100,1,1,1,1]))
        self.assertFalse(r['selected_is_pareto_undominated'])
        self.assertIn([2,3],r['pairs_dominating_selected'])
    def test_equal_quality_cost_not_strict(self):
        r=analyze(rows([1]*6,[1]*6))
        self.assertFalse(r['pairs_dominating_selected']);self.assertFalse(r['pairs_dominated_by_selected'])
    def test_unknown_not_imputed(self):
        rr=rows([1]*6,[1]*6);rr[1]['valid']=None
        self.assertEqual(analyze(rr)['status'],'unknown')
    def test_runtime_bad_rejected(self):
        with self.assertRaises(ValueError):analyze(rows([1]*6,[float('nan')]*6))


if __name__=='__main__':unittest.main()
