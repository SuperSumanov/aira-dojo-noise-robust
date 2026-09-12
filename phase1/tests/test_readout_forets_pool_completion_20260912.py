import importlib.util
from pathlib import Path
import unittest

PHASE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('poolread',PHASE/'readout_forets_pool_completion_20260912.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)

def rows(values):return [dict(slot=i,valid=v,score=float(i+1) if v is True else None) for i,v in enumerate(values)]

class ReadoutTests(unittest.TestCase):
    def test_complete_pool_known_gain(self):
        result=r.finite_pool(rows([True,True,False,False]),[[0,1,2,3]]*2)
        self.assertEqual(result['validity_gain_bounds'],[.5,.5])
        self.assertEqual(result['policies']['frozen_borda_top2']['conditional_mean_score'],1.5)
    def test_same_unknown_is_coupled_not_independent_bounds(self):
        result=r.finite_pool(rows([True,None,False,False]),[[0,1,2,3]]*2)
        self.assertEqual(result['validity_gain_bounds'],[.25,.5])
        self.assertIsNone(result['policies']['frozen_borda_top2']['conditional_mean_score'])
    def test_all_unknown_no_quality_imputation(self):
        result=r.finite_pool(rows([None]*4),[[0,1,2,3]]*2)
        self.assertEqual(result['validity_gain_bounds'],[-.5,.5])
    def test_negative_result_and_missing_score_retained(self):
        self.assertEqual(r.finite_pool(rows([False,False,True,True]),[[0,1,2,3]]*2)['validity_gain_bounds'],[-.5,-.5])
        invalid=rows([True,False,False,False]);invalid[0]['score']=None
        with self.assertRaises(ValueError):r.finite_pool(invalid,[[0,1,2,3]]*2)
    def test_archive_not_joined_on_score_alone(self):
        report={'score':.7,'valid_submission':True,'created_at':'a'}
        metric={**report,'validity_feedback':'Submission is valid.'}
        self.assertEqual(r.match_archive(metric,[('right',report),('wrong',{**report,'created_at':'b'})])[0],'right')
        with self.assertRaises(ValueError):r.match_archive(metric,[('duplicate1',report),('duplicate2',report)])

if __name__=='__main__':unittest.main()
