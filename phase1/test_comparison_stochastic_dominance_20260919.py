import unittest
from verify_comparison_stochastic_dominance_20260919 import diagnose


def rows(values):
    return [dict(slot=i,original_selected=i<2,valid=v is not None,score=v) for i,v in enumerate(values)]


class DominanceTests(unittest.TestCase):
    def test_two_best_selected(self):
        self.assertTrue(diagnose(rows([1,2,3,None,None,None]))['dominates_for_every_possible_third'])
    def test_best_and_failure(self):
        self.assertTrue(diagnose(rows([1,None,2,None,None,None]))['dominates_for_every_possible_third'])
    def test_all_same_is_equal_not_strict(self):
        result=diagnose(rows([1]*6))
        self.assertFalse(result['dominates_for_every_possible_third'])
        self.assertTrue(all(p['equivalent'] for p in result['possibilities']))
    def test_all_failures_is_equal(self):
        result=diagnose(rows([None]*6))
        self.assertTrue(all(p['equivalent'] for p in result['possibilities']))
    def test_unknown_skipped(self):
        rr=rows([1]*6);rr[2]['valid']=None
        self.assertEqual(diagnose(rr)['status'],'unknown')
    def test_validity_and_quality_crossing_is_not_dominance(self):
        result=diagnose(rows([4,None,1,2,3,None]))
        self.assertFalse(result['dominates_for_every_possible_third'])
        self.assertTrue(any(not(p['dominates'] or p['dominated'] or p['equivalent']) for p in result['possibilities']))


if __name__=='__main__':unittest.main()
