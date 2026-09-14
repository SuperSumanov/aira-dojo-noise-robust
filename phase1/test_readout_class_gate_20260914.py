import unittest
from readout_class_gate_20260914 import comparisons,secondary_contrasts
def rows():
    return [dict(task=t,seed=48,arm=a,technical_eligible=True,action_valid=True,action_score=.5,iteration_valid=True,iteration_score=.5)
        for t in ('leaf-classification','spaceship-titanic') for a in ('uniform','short_code','learned_validity','class_gate')]
class TestReadout(unittest.TestCase):
    def test_all_ties_no_gate(self):self.assertFalse(comparisons(rows())['investment_gate'])
    def test_gate_can_tie_short_but_must_beat_other_two(self):
        rr=rows()
        for r in rr:
            if r['arm'] in ('short_code','class_gate'):r['action_score']=.4 if r['task']=='leaf-classification' else .6
        self.assertTrue(comparisons(rr)['investment_gate'])
    def test_technical_unknown_fails(self):
        rr=rows();rr[0]['technical_eligible']=False
        self.assertFalse(comparisons(rr)['investment_gate'])
    def test_secondary_orientation(self):
        rr=rows()
        for r in rr:
            if r['arm']=='short_code':r['action_score']=.4 if r['task']=='leaf-classification' else .6
        self.assertEqual([r['sign'] for r in secondary_contrasts(rr)],[1,1,1,1])
    def test_missing_not_zero(self):
        rr=rows();rr[0]['action_valid']=False
        with self.assertRaises(ValueError):comparisons(rr)
if __name__=='__main__':unittest.main()
