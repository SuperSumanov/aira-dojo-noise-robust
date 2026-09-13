import copy
import hashlib
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from verify_branching_selection_20260913 import verify_pool,replay


class ReplayTests(unittest.TestCase):
    def fixture(self):
        row=dict(task='leaf-classification',seed=30,arm='uniform_random')
        cfg=dict(critic_top_k=2,num_children_to_choose=2,selector_seed=30,skip_redundant_critic=True)
        cs=[dict(score=None,node=dict(code=f'print({i})')) for i in range(4)]
        slots=replay(4,None,row['arm'],30,row['task'],2)
        calls=[dict(slot=i,state='returned',intent=dict(role='candidate',code_sha256=hashlib.sha256(cs[i]['node']['code'].encode()).hexdigest())) for i in slots]
        v=dict(binding=dict(task=row['task'],selection_policy=row['arm'],selection_coupling='common_priority_v1',step=2),
            candidates=cs,selected=slots,task_calls=calls,phase='complete')
        return v,cfg,row
    def test_two_and_debug(self):
        v,cfg,row=self.fixture();d=copy.deepcopy(v['task_calls'][0]);d['intent']['role']='debug';v['task_calls'].insert(1,d)
        self.assertEqual(verify_pool(v,cfg,row)['candidate_executions'],2)
    def test_wrong_order(self):
        v,cfg,row=self.fixture();v['task_calls'].reverse()
        with self.assertRaises(ValueError):verify_pool(v,cfg,row)
    def test_wrong_debug(self):
        v,cfg,row=self.fixture();d=copy.deepcopy(v['task_calls'][1]);d['intent']['role']='debug';v['task_calls'].insert(1,d)
        with self.assertRaises(ValueError):verify_pool(v,cfg,row)
    def test_partial_not_complete(self):
        v,cfg,row=self.fixture();v['task_calls'].pop()
        with self.assertRaises(ValueError):verify_pool(v,cfg,row)
        v['phase']='executing';self.assertEqual(verify_pool(v,cfg,row)['candidate_executions'],1)
    def test_wrong_code(self):
        v,cfg,row=self.fixture();v['task_calls'][0]['intent']['code_sha256']='bad'
        with self.assertRaises(ValueError):verify_pool(v,cfg,row)
    def test_critic_top_two(self):
        self.assertEqual(set(replay(4,[1.,2.,3.,4.],'critic_topk_random',30,'leaf-classification',2)),{2,3})


if __name__=='__main__':unittest.main()
