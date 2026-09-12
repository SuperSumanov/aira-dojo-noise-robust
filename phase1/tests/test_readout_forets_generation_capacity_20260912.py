import copy
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from readout_forets_generation_capacity_20260912 import TASKS,MODELS,MATRIX,summarize

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

if __name__=='__main__':unittest.main()
