from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import build_forets_action_prospective_20260913 as m

class MatrixTests(unittest.TestCase):
    def test_eight_distinct_uniform_runs(self):
        rows=m.order();self.assertEqual(len(rows),8);self.assertEqual(len(set(rows)),8)
        self.assertEqual({r[2] for r in rows},{34,35,36,37})
        self.assertEqual({r[3] for r in rows},{'uniform_random'})
        for b in (1,2):self.assertEqual(sum(r[0]==b for r in rows),4)
    def test_controller_exact_function_replacement(self):
        text='def expected_order():\n    return ()\n\ndef untouched():\n    return 19\n'
        changed=m.derive('forets_block_controller_20260911.py',text);ns={};exec(changed,ns)
        self.assertEqual(ns['expected_order'](),tuple(m.order()));self.assertEqual(ns['untouched'](),19)
    def test_wrong_policy_rejected(self):
        cfg={'solver':dict(num_children=4,num_children_to_choose=2,time_limit_secs=600,execution_timeout=300,use_test_score=False,selection_policy='critic_topk_random')}
        with self.assertRaises(ValueError):m.config_transform(cfg)
        cfg['solver']['selection_policy']='uniform_random';out=m.config_transform(cfg)
        self.assertEqual(out['solver']['action_delivery_protocol'],m.PROTOCOL)
    def test_real_source_artifact_changes_only_documented_files(self):
        m.configure(Path(__file__).resolve().parents[1]/'results/forets_reference_s32_s33_20260913/action-parent-facts.json')
        sources=m.changed_sources();self.assertEqual(len(sources),4)
        self.assertFalse(any('interpreter' in p or 'batch_runtime' in p or 'mcts.py' in p for p in sources))
        for p,s in sources.items():compile(s,p,'exec')

if __name__=='__main__':unittest.main()
