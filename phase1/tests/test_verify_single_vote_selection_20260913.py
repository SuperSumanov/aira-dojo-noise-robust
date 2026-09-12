import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from verify_single_vote_selection_20260913 import verify_pool,sha,replay

class ReplayTests(unittest.TestCase):
    def fixture(self):
        row=dict(task='leaf-classification',seed=26,arm='critic_topk_random')
        cfg=dict(critic_top_k=2,num_children_to_choose=1,selector_seed=26,skip_redundant_critic=True)
        codes=['a=1','a=2','a=3','a=4'];scores=[4.,3.,2.,1.]
        chosen=replay(4,scores,row['arm'],'common_priority_v1',26,row['task'],1)
        value=dict(binding=dict(task=row['task'],selection_policy=row['arm'],selection_coupling='common_priority_v1',step=1),
            candidates=[dict(node=dict(code=c),score=s) for c,s in zip(codes,scores)],selected=chosen,phase='complete',
            task_calls=[dict(slot=chosen[0],state='returned',intent=dict(role='candidate'))])
        inp=dict(codes_sha256=[sha(c.encode()) for c in codes],aggregation='single_order_rank_v1')
        return value,cfg,row,inp,dict(borda=scores)
    def test_real_intervention_and_changed_code_guard(self):
        args=self.fixture();self.assertTrue(verify_pool(*args)['replay_matches'])
        bad=copy.deepcopy(args);bad[0]['candidates'][0]['node']['code']='different'
        with self.assertRaises(ValueError):verify_pool(*bad)
    def test_wrong_selection_execution_or_scores_rejected(self):
        for mutation in ('selection','call','scores'):
            args=copy.deepcopy(self.fixture())
            if mutation=='selection':args[0]['selected']=[3]
            elif mutation=='call':args[0]['task_calls'][0]['slot']=3
            else:args[4]['borda']=[1.,2.,3.,4.]
            with self.assertRaises(ValueError):verify_pool(*args)
    def test_partial_pool_preserved_not_fake_completed(self):
        args=self.fixture();args[0].update(selected=None,phase='collecting',task_calls=[])
        self.assertFalse(verify_pool(*args)['selected'])
        args[0]['task_calls']=[dict(slot=0,state='returned',intent=dict(role='candidate'))]
        with self.assertRaises(ValueError):verify_pool(*args)

if __name__=='__main__':unittest.main()
