import copy
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from readout_forets_generation_capacity_20260912 import TASKS,MODELS,MATRIX,summarize,numerical

def rows():
    return [dict(task=TASKS[t],replicate=s,model=MODELS[m],status='valid',valid=True,
        score=.5 if m==0 else .4,execution_seconds=1.,api_cost_usd=.01) for t,s,m in MATRIX]

class ReadoutTests(unittest.TestCase):
    def test_direction(self):
        report=summarize(rows())
        for pair in report['pairs']:
            self.assertAlmostEqual(pair['plus_oriented_score_gain'],.1 if pair['task']==TASKS[0] else -.1)
    def test_no_imputation(self):
        data=rows();data[0].update(valid=False,status='program_error',score=None)
        report=summarize(data)
        self.assertIsNone(report['pairs'][0]['plus_oriented_score_gain'])
        data[0]['score']=0
        with self.assertRaises(ValueError):summarize(data)
    def test_no_partial_or_duplicate(self):
        data=rows()
        with self.assertRaises(ValueError):summarize(data[:-1])
        data[-1]=copy.copy(data[0])
        with self.assertRaises(ValueError):summarize(data)
    def test_infrastructure_not_quality(self):
        data=rows();data[0].update(valid=False,status='infrastructure_error',score=None)
        with self.assertRaises(ValueError):summarize(data)
    def test_independent_numeric_alignment(self):
        import pandas as pd
        import math
        truth=pd.DataFrame(dict(id=[1,2],a=[1,0],b=[0,1]))
        pred=pd.DataFrame(dict(id=[2,1],a=[.1,.8],b=[.9,.2]))
        self.assertAlmostEqual(numerical(TASKS[0],pred,truth),-(math.log(.8)+math.log(.9))/2)
        truth=pd.DataFrame(dict(PassengerId=['a','b'],Transported=[True,False],HomePlanet=['Earth','Mars']))
        pred=pd.DataFrame(dict(PassengerId=['b','a'],Transported=['true','true']))
        self.assertEqual(numerical(TASKS[1],pred,truth),.5)
    def test_independent_numeric_rejects_bad_ids(self):
        import pandas as pd
        truth=pd.DataFrame(dict(PassengerId=['a','b'],Transported=[True,False]))
        pred=pd.DataFrame(dict(PassengerId=['a','a'],Transported=[True,False]))
        with self.assertRaises(ValueError):numerical(TASKS[1],pred,truth)

if __name__=='__main__':unittest.main()
