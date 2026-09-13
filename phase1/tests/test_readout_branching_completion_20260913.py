from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from readout_branching_completion_20260913 import compare
def rows(v):return [dict(slot=i,valid=x,score=.7 if x is True else None) for i,x in enumerate(v)]
class Pool(unittest.TestCase):
    def test_all_invalid(self):self.assertEqual(compare(rows([False]*4),[0,1,2,3])['any_valid_gain_bounds'],[0,0])
    def test_valid_kept(self):self.assertEqual(compare(rows([True,False,False,False]),[0,1,2,3])['any_valid_gain_bounds'],[.5,.5])
    def test_valid_removed(self):self.assertEqual(compare(rows([False,False,True,False]),[0,1,2,3])['any_valid_gain_bounds'],[-.5,-.5])
    def test_shared_unknown(self):self.assertEqual(compare(rows([None,False,False,False]),[0,1,2,3])['any_valid_gain_bounds'],[0,.5])
    def test_no_missing_score(self):
        r=rows([None,False,False,False]);r[0]['score']=0
        with self.assertRaises(ValueError):compare(r,[0,1,2,3])
    def test_complete_pool_required(self):
        with self.assertRaises(ValueError):compare(rows([True,False]),[0,1,2,3])
if __name__=='__main__':unittest.main()
