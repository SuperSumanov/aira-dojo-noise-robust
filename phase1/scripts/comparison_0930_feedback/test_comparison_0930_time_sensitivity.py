import unittest
from comparison_0930_time_sensitivity import endpoint,trace,CONTRASTS
class Tests(unittest.TestCase):
    def test_no_survivor_carry_after_last_record(self):
        x=[{'elapsed':0,'score':None,'selected_step':0},{'elapsed':10,'score':.8,'selected_step':1}]
        self.assertFalse(endpoint(x,11)['observed']);self.assertIsNone(endpoint(x,11)['score'])
    def test_no_lookahead(self):
        x=[{'elapsed':0,'score':None,'selected_step':0},{'elapsed':10,'score':.8,'selected_step':1}]
        self.assertIsNone(endpoint(x,9)['score']);self.assertEqual(endpoint(x,10)['score'],.8)
    def test_restart_resets_incumbent(self):
        ns=[{'timestamp':f'2026-09-01T00:00:0{i}+00:00',**n} for i,n in enumerate([
            {'step':0,'pointer':0,'score':None},{'step':1,'pointer':1,'score':.9},
            {'step':0,'pointer':0,'score':None},{'step':1,'pointer':1,'score':.2}])]
        x=trace(ns);self.assertIsNone(endpoint(x,2)['score']);self.assertEqual(endpoint(x,3)['score'],.2)
    def test_actual_arm_names(self):
        self.assertEqual({x for pair in CONTRASTS for x in pair},{'forets-selected','short','random'})
if __name__=='__main__':unittest.main()
