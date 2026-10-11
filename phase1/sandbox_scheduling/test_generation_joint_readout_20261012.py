import copy
import unittest
from generation_joint_readout_20261012 import ARMS,TASKS,summarize,generation_audit,independent_rank
from test_joint_generation_20261012 import fixture
from joint_generation_policy_20261012 import rank_request


def rows():
    order=('continuation','cost','joint','joint','cost','continuation')
    return [dict(index=8*b+2*l+k,block=b,repeat=b//3,arm=a,task=t,lane=l,
        seed=100*(b//3)+2*l+k,started=True,cleanup=True,complete=True,valid=True,
        score=.5 if k==0 else .1) for b,a in enumerate(order) for l in range(4) for k,t in enumerate(TASKS)]


class ReadoutTests(unittest.TestCase):
    def test_null_no_gain(self):
        s=summarize(rows(),dict(zip(TASKS,(.5,.1))))
        self.assertFalse(s['quality_signal_before_structure']);self.assertEqual(len(s['pool_task_contrasts']),8)

    def test_one_repeat_not_success(self):
        r=rows()
        for x in r:
            if x['arm']=='joint' and x['repeat']==0 and x['task']==TASKS[1]:x['score']=.09
        self.assertFalse(summarize(r,dict(zip(TASKS,(.5,.1))))['quality_signal_before_structure'])

    def test_both_repeats_both_references(self):
        r=rows()
        for x in r:
            if x['arm']=='joint' and x['task']==TASKS[1]:x['score']=.09
        self.assertTrue(summarize(r,dict(zip(TASKS,(.5,.1))))['quality_signal_before_structure'])

    def test_strong_reference_win_blocks_gate(self):
        r=rows()
        for x in r:
            if x['task']==TASKS[1] and x['arm']=='joint':x['score']=.09
            if x['task']==TASKS[1] and x['arm']=='cost':x['score']=.08
        self.assertFalse(summarize(r,dict(zip(TASKS,(.5,.1))))['quality_signal_before_structure'])

    def test_missing_run_not_zero(self):
        r=rows();r[0].update(started=False,valid=False,score=None,cleanup=False,complete=False)
        s=summarize(r,dict(zip(TASKS,(.5,.1))))
        self.assertEqual(s['assigned'],48);self.assertTrue(any(x['oriented_delta'] is None for x in s['run_pairs']))
        self.assertTrue(any(not x['all_assigned_started'] for x in s['pool_task_contrasts']))

    def test_assignment_denominator(self):
        with self.assertRaises(AssertionError):summarize(rows()[:-1],dict(zip(TASKS,(.5,.1))))

    def test_seeds_must_match(self):
        r=rows();r[0]['seed']=999
        with self.assertRaises(AssertionError):summarize(r,dict(zip(TASKS,(.5,.1))))

    def test_recomputed_rank(self):
        s=fixture();busy={'0':dict(start=0.,expected_seconds=300.)}
        for arm in ARMS:
            for r in s['waiting']:
                self.assertEqual(independent_rank(r,s,10.,arm,busy),rank_request(r,s,10.,arm,busy))

    def test_independent_event_replay(self):
        s=fixture();es=[dict(event='queued',request=r) for r in s['waiting']]
        es.append(dict(event='admitted',key='0',snapshot=copy.deepcopy(s),decision_time=10.,
            occupancy={},alternatives={a:'0' for a in ARMS},scarce=True))
        es.append(dict(event='released',key='0'))
        es.extend(dict(event='cancelled',key=str(i)) for i in (1,2,3))
        got=generation_audit(es,'joint');self.assertTrue(got['all_released']);self.assertEqual(got['scarce_choices'],1)
        es[4]['alternatives']['joint']='1'
        with self.assertRaises(AssertionError):generation_audit(es,'joint')


if __name__=='__main__':unittest.main()
