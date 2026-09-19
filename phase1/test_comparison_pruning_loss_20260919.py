import unittest
from analyze_comparison_pruning_loss_20260919 import analyze


def rows(values):
    return [dict(slot=i,original_selected=i<2,valid=v is not None,score=v) for i,v in enumerate(values)]


class PruningTests(unittest.TestCase):
    def test_bad_valid_and_invalid_selected(self):
        r=analyze(rows([4,None,1,2,3,None]))
        self.assertEqual(r['boundary_error_count_range'],[4,9])
        self.assertEqual(r['pruned_better_valid_count_range'],[2,3])
    def test_good_selection_can_have_zero_boundary_errors(self):
        r=analyze(rows([1,2,3,None,None,None]))
        self.assertEqual(r['boundary_error_count_range'],[0,1])
    def test_ties_not_inversions(self):
        self.assertEqual(analyze(rows([1]*6))['boundary_error_count_range'],[0,0])
    def test_unknown(self):
        rr=rows([1]*6);rr[1]['valid']=None
        self.assertEqual(analyze(rr)['status'],'unknown')


if __name__=='__main__':unittest.main()
