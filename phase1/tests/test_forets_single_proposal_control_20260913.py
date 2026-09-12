import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from forets_single_proposal_control_20260913 import single_proposal,difference_paths,ALLOWED

class SingleProposalTests(unittest.TestCase):
    def source(self):
        return dict(solver=dict(selection_policy='uniform_random',num_children=4,critic_top_k=2,
            num_children_to_choose=1,selection_coupling='common_priority_v1',time_limit_secs=600,
            execution_timeout=300,selector_seed=26,operators={'model':'same'}),task={'data':'same'},metadata={'seed':26})
    def test_only_fanout_and_unused_topk_bound_change(self):
        source=self.source();before=copy.deepcopy(source);cfg=single_proposal(source)
        self.assertEqual(source,before);self.assertEqual(difference_paths(source,cfg),ALLOWED)
        self.assertEqual(cfg['solver']['num_children_to_choose'],1)
        self.assertEqual(cfg['solver']['selection_policy'],'uniform_random')
    def test_unexpected_base_rejected(self):
        for name,value in [('num_children',3),('selection_policy','critic_topk_random'),('execution_timeout',60)]:
            cfg=self.source();cfg['solver'][name]=value
            with self.assertRaises(ValueError):single_proposal(cfg)

if __name__=='__main__':unittest.main()
