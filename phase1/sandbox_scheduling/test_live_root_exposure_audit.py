from pathlib import Path
import unittest
from live_root_exposure_audit import mechanism


class RootExposureTests(unittest.TestCase):
    def source(self):
        return (Path(__file__).parents[2]/'src/dojo/solvers/mcts/mcts.py').read_text(encoding='utf-8')
    def test_current_known_loop(self):
        self.assertTrue(mechanism(self.source())['fixed_root_draft_batch_before_next_selection'])
    def test_changed_root_branch_is_not_accepted(self):
        changed=self.source().replace('if not leaf_node.parents:','if leaf_node.parents:')
        self.assertFalse(mechanism(changed)['fixed_root_draft_batch_before_next_selection'])
    def test_changed_quota_is_not_accepted(self):
        changed=self.source().replace('min(self.cfg.num_children, self.remaining_steps)','1')
        self.assertFalse(mechanism(changed)['fixed_root_draft_batch_before_next_selection'])


if __name__=='__main__':unittest.main()
