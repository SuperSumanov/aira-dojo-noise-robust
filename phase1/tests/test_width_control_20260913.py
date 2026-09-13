import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import build_forets_width_control_20260913 as b
import readout_forets_width_control_20260913 as r
from forets_single_proposal_control_20260913 import difference_paths

class WidthTests(unittest.TestCase):
    def test_exact_paired_matrix_and_counterorder(self):
        rows=b.order();self.assertEqual(len(rows),8);self.assertEqual(len(set(rows)),8)
        self.assertEqual(rows[0],(1,'leaf-classification',38,'batch_four'))
        self.assertEqual(rows[4],(2,'leaf-classification',39,'direct_two'))
        for i in range(0,8,2):
            self.assertEqual(rows[i][:3],rows[i+1][:3]);self.assertEqual({rows[i][3],rows[i+1][3]},set(b.WIDTHS))
    def test_only_fanout_changes(self):
        cfg={'solver':dict(num_children=4,num_children_to_choose=2,critic_top_k=2,time_limit_secs=600,
            execution_timeout=300,selection_policy='uniform_random',use_test_score=False,
            action_delivery_protocol='original_search_visible_action_delivery_v1')}
        a=b.config_transform(copy.deepcopy(cfg),'batch_four');c=b.config_transform(copy.deepcopy(cfg),'direct_two')
        self.assertEqual(difference_paths(a,c),{('solver','num_children')})
        cfg['solver']['selection_policy']='critic_topk_random'
        with self.assertRaises(ValueError):b.config_transform(cfg,'direct_two')
    def test_matrix_controller_replacement(self):
        text='def expected_order():\n    return ()\n\ndef untouched():\n    return 9\n'
        ns={};exec(b.derive('forets_block_controller_20260911.py',text),ns)
        self.assertEqual(ns['expected_order'](),tuple(b.order()));self.assertEqual(ns['untouched'](),9)
    def test_no_algorithm_source_changes(self):
        with patch.object(b,'FACTS',dict(billing_counts=[1,2_000_000_000,600_000_000,2])):
            out=b.changed_sources()
        self.assertEqual(list(out),[b.PREFIX+'paid_budget.py'])
        for name,raw in out.items():compile(raw,name,'exec')
    def rows(self):
        return [dict(task=t,seed=s,arm=a,technical_eligible=True,action_valid=True,iteration_valid=True,
            action_score=.6 if a=='batch_four' else .5,iteration_score=.6,api_cost_usd=.1 if a=='batch_four' else .05)
            for t in r.TASKS for s in r.SEEDS for a in r.ARMS]
    def test_positive_and_negative_task_directions(self):
        result=r.paired_effects(self.rows())
        groups=result['groups'];self.assertEqual(groups[0]['wins'],2);self.assertEqual(groups[1]['losses'],2)
        self.assertEqual(groups[2]['ties'],2);self.assertEqual(groups[3]['ties'],2)
    def test_technical_failure_not_quality_win(self):
        rows=self.rows();rows[0]['technical_eligible']=False;result=r.paired_effects(rows)
        self.assertIsNone(result['pairs'][0]['direct_oriented_gain']);self.assertEqual(result['groups'][0]['quality_comparable'],1)
    def test_missing_and_duplicates_rejected(self):
        rows=self.rows();rows[0]['action_valid']=False
        with self.assertRaises(ValueError):r.paired_effects(rows)
        rows[0]['action_score']=None;self.assertFalse(r.paired_effects(rows)['pairs'][0]['quality_comparable'])
        rows[-1]=rows[0]
        with self.assertRaises(ValueError):r.paired_effects(rows)

if __name__=='__main__':unittest.main()
