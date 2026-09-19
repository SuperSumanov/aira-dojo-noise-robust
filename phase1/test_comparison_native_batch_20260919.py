import json,tempfile,unittest
from pathlib import Path
from run_comparison_native_batch_order_20260919 import stages,improves,keep_incumbent

class NativeBatch(unittest.TestCase):
    def test_same_stages_only_order_changes(self):
        self.assertEqual(stages(False),tuple(reversed(stages(True))))
        self.assertEqual(set(stages(False)),{'repair','sibling'})
    def test_internal_metric_ties_keep_first(self):
        self.assertTrue(improves(.8,None));self.assertFalse(improves(.8,.8));self.assertFalse(improves(.7,.8))
        for v in (None,float('nan'),float('inf'),True):self.assertFalse(improves(v,None))
    def test_atomic_best_incumbent_preserves_decisions(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            a=dict(action_index=0,submission_sha256='a'*64,accepted_seconds=4,code_sha256='b'*64)
            b=dict(action_index=1,submission_sha256='c'*64,accepted_seconds=20,code_sha256='d'*64)
            score=keep_incumbent(root,a,.7,None);score=keep_incumbent(root,b,.8,score)
            self.assertEqual(json.loads((root/'incumbent.json').read_text())['action_index'],1)
            self.assertEqual(len(list(root.glob('incumbent-decision-*'))),2)
            self.assertEqual(keep_incumbent(root,a,.6,score),.8)
            self.assertEqual(json.loads((root/'incumbent.json').read_text())['action_index'],1)

if __name__=='__main__':unittest.main()
