import unittest
from read_comparison_qwen_20260919 import solver_choice,plot_choice,stats,number

def node(i,m,maximize=True,score=0.0,lower=False,buggy=False):
    return dict(id=i,metric=m,metric_maximize=maximize,is_buggy=buggy,metric_info=dict(score=score,is_lower_better=lower))

class Tests(unittest.TestCase):
    def test_excludes_buggy(self):
        ns=[node('bad',9,buggy=True),node('ok',1)]
        self.assertEqual(solver_choice(ns)['id'],'ok');self.assertEqual(plot_choice(ns)['id'],'bad')
    def test_internal_direction_not_official(self):
        ns=[node('a',.9,score=.1,lower=True),node('b',.8,score=.2,lower=True)]
        self.assertEqual(solver_choice(ns)['id'],'a');self.assertEqual(plot_choice(ns)['id'],'b')
    def test_minimize(self):self.assertEqual(solver_choice([node('a',2,False),node('b',1,False)])['id'],'b')
    def test_tie_first(self):self.assertEqual(solver_choice([node('a',1),node('b',1)])['id'],'a')
    def test_no_outcome_selection(self):
        self.assertEqual(solver_choice([node('a',.9,score=-100),node('b',.8,score=100)])['id'],'a')
    def test_mixed_directions_stop(self):
        with self.assertRaises(ValueError):solver_choice([node('a',1),node('b',2,False)])
    def test_finite_and_small_sample(self):
        self.assertIsNone(number(float('nan')));self.assertIsNone(stats([1])['sd'])
    def test_empty(self):self.assertIsNone(solver_choice([]))

if __name__=='__main__':unittest.main()
