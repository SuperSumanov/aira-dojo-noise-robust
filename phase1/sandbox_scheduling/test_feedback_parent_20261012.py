import copy
import json
from pathlib import Path
import tempfile
import unittest
import feedback_parent_policy_20261012 as p


def fixture():
    return dict(archive={'A':{'a':dict(metric=.8,visits=1,total=.8,order=0),
                              'b':dict(metric=.7,visits=1,total=.7,order=1)}},
                sign={'A':1},pending={},waiting=[],active=[])


class ParentTests(unittest.TestCase):
    def test_greedy_best(self):
        self.assertEqual(p.parent_choice(fixture(),'A','greedy'),'a')

    def test_single_parent_pending_baseline_does_not_wait(self):
        s=fixture();s['archive']['A'].pop('b');s['pending']['x']=dict(task='A',parent='a')
        self.assertEqual(p.parent_choice(s,'A','pending_ucb'),'a')
        self.assertIsNone(p.parent_choice(s,'A','feedback_gate'))

    def test_gate_chooses_different_available_parent(self):
        s=fixture();s['pending']['x']=dict(task='A',parent='a')
        self.assertEqual(p.parent_choice(s,'A','feedback_gate'),'b')

    def test_same_as_pending_without_pending(self):
        s=fixture()
        self.assertEqual(p.parent_choice(s,'A','feedback_gate'),p.parent_choice(s,'A','pending_ucb'))

    def test_lower_is_better(self):
        s=fixture();s['sign']['A']=-1
        for v in s['archive']['A'].values():v['total']=-v['metric']
        self.assertEqual(p.parent_choice(s,'A','greedy'),'b')
        self.assertEqual(p.parent_choice(s,'A','pending_ucb'),'b')

    def test_ucb_not_greedy(self):
        s=fixture();s['archive']['A']['a'].update(visits=1000,total=800.)
        self.assertEqual(p.parent_choice(s,'A','pending_ucb'),'b')
        self.assertEqual(p.parent_choice(s,'A','greedy'),'a')

    def test_no_future_access(self):
        s=fixture();original=copy.deepcopy(s);s['future_best']=1000
        for arm in p.ARMS:self.assertEqual(p.parent_choice(s,'A',arm),p.parent_choice(original,'A',arm))

    def test_no_mutation(self):
        s=fixture();old=copy.deepcopy(s)
        for arm in p.ARMS:p.parent_choice(s,'A',arm)
        self.assertEqual(s,old)

    def test_bad_arm(self):
        with self.assertRaises(ValueError):p.parent_choice(fixture(),'A','old_joint')

    def test_analysis_can_finish_when_all_parents_busy(self):
        s=fixture();s['pending']={k:dict(task='A',parent=k) for k in ('a','b')}
        s['waiting']=[dict(key='i',run=0,task='A',role='improve',requested=0),
                      dict(key='a',run=1,task='A',role='analyze',requested=1)]
        self.assertEqual(p.select_request(s,'A','feedback_gate'),('a',None))

    def test_debug_not_suppressed(self):
        s=fixture();s['pending']={k:dict(task='A',parent=k) for k in ('a','b')}
        s['waiting']=[dict(key='d',run=0,task='A',role='debug',requested=0)]
        self.assertEqual(p.select_request(s,'A','feedback_gate'),('d',None))

    def test_no_cross_task_capacity(self):
        s=fixture();s['active']=[dict(task='B')]*2
        s['waiting']=[dict(key='i',run=0,task='A',role='improve',requested=0)]
        self.assertEqual(p.select_request(s,'A','greedy'),('i','a'))
        s['active']=[dict(task='A')]*2
        self.assertEqual(p.select_request(s,'A','greedy'),(None,None))

    def test_fifo_common(self):
        s=fixture();s['waiting']=[dict(key=str(i),run=i,task='A',role='improve',requested=i) for i in (3,1)]
        for arm in p.ARMS:self.assertEqual(p.select_request(s,'A',arm)[0],'1')

    def test_initialize_unique_code_and_isolated_tasks(self):
        warm=dict(code='print(1)',plan='',analysis='',_term_out=[],exec_time=1.,metric=.5,metric_maximize=True)
        with tempfile.TemporaryDirectory() as d:
            q=Path(d)/'q';p.initialize(q,[dict(task='A'),dict(task='B')],{'A':warm,'B':warm})
            with p.locked(q) as s:
                self.assertEqual(set(s['archive']),{'A','B'})
                self.assertEqual(len(s['archive']['A']),1)
                self.assertEqual(s['pending'],{})

    def test_readout_summary_positive_and_negative(self):
        from feedback_parent_readout_20261012 import quality_summary
        scores={}
        for b,arm in enumerate(p.ARMS+tuple(reversed(p.ARMS))):
            for task in ('aerial-cactus-identification','denoising-dirty-documents'):
                scores[b,task]=.99 if task.startswith('aerial') else (.02 if arm=='feedback_gate' else .03)
        self.assertTrue(quality_summary(scores)['quality_gate'])
        scores[2,'denoising-dirty-documents']=.04
        self.assertFalse(quality_summary(scores)['quality_gate'])


if __name__=='__main__':unittest.main()
