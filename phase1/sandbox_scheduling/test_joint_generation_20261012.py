import copy
import json
from pathlib import Path
import tempfile
import unittest

import joint_generation_policy_20261012 as p


def fixture():
    stats=dict(completed=0,improvements=0,generation_mean=120.,generation_n=0,
        execution_mean=100.,execution_n=0,analysis_mean=30.,analysis_n=0,best=.5)
    waiting=[dict(key=str(i),run=i,lane=i,task='A',role='improve',requested=0.,deadline=1000.) for i in range(4)]
    return dict(stats={str(i):copy.deepcopy(stats) for i in range(4)},waiting=waiting,active=[])


class PolicyTests(unittest.TestCase):
    def test_deterministic_tie(self):
        for arm in p.ARMS:self.assertEqual(p.choose(fixture(),'A',10.,arm,{}),'0')

    def test_no_cross_task_permit(self):
        s=fixture();s['active']=[dict(task='B'),dict(task='B')]
        self.assertEqual(p.choose(s,'A',10.,'joint',{}),'0')

    def test_cap_two(self):
        s=fixture();s['active']=[dict(task='A'),dict(task='A')]
        for arm in p.ARMS:self.assertIsNone(p.choose(s,'A',10.,arm,{}))

    def test_analyze_common_priority(self):
        s=fixture();s['waiting'][3]['role']='analyze'
        for arm in p.ARMS:self.assertEqual(p.choose(s,'A',10.,arm,{}),'3')

    def test_continuation(self):
        s=fixture();s['stats']['2']['completed']=1
        self.assertEqual(p.choose(s,'A',10.,'continuation',{}),'2')

    def test_cost_learns_only_past(self):
        s=fixture();s['stats']['2'].update(completed=1,improvements=1)
        self.assertEqual(p.choose(s,'A',10.,'cost',{}),'2')

    def test_joint_only_resource_difference(self):
        s=fixture();busy={'0':dict(start=0.,expected_seconds=300.)}
        self.assertEqual(p.choose(s,'A',10.,'cost',busy),'0')
        self.assertEqual(p.choose(s,'A',10.,'joint',busy),'1')
        self.assertEqual(p.choose(s,'A',10.,'continuation',busy),'0')

    def test_overlap_not_double_charged(self):
        s=fixture();busy={'0':dict(start=0.,expected_seconds=100.)}
        self.assertEqual(p.choose(s,'A',10.,'joint',busy),'0')

    def test_finished_occupancy_zero(self):
        s=fixture();busy={'0':dict(start=0.,expected_seconds=1.)}
        self.assertEqual(p.choose(s,'A',100.,'joint',busy),'0')

    def test_no_future_metadata_used(self):
        s=fixture();s['future_final_best']={'0':999.};s['waiting'][3]['future_score']=99.
        for arm in p.ARMS:self.assertEqual(p.choose(s,'A',10.,arm,{}),'0')

    def test_no_state_mutation_from_rank(self):
        s=fixture();old=copy.deepcopy(s)
        for arm in p.ARMS:p.choose(s,'A',10.,arm,{})
        self.assertEqual(s,old)

    def test_fit_changes_selection(self):
        s=fixture();s['waiting'][0]['deadline']=100.
        for arm in ('cost','joint'):self.assertEqual(p.choose(s,'A',10.,arm,{}),'1')

    def test_mean_observed_not_prior_fit(self):
        s=fixture()['stats']['0'];p.mean_update(s,'generation',60.);p.mean_update(s,'generation',100.)
        self.assertEqual(s['generation_mean'],80.)
        with self.assertRaises(ValueError):p.mean_update(s,'generation',float('nan'))

    def test_locked_and_initialization(self):
        with tempfile.TemporaryDirectory() as td:
            d=Path(td)/'q';p.initialize(d,[dict(index=0,task='A')],{'A':dict(metric=.5,exec_time=10.)})
            with p.locked(d) as state:state['stats']['0']['completed']=1
            self.assertEqual(json.loads((d/'state.json').read_text())['stats']['0']['completed'],1)

    def test_invalid_policy(self):
        with self.assertRaises(ValueError):p.choose(fixture(),'A',10.,'not-a-policy',{})


if __name__=='__main__':unittest.main()
