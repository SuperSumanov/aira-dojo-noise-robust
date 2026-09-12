from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from forets_branching_control_20260913 import execute_two


class BranchingTests(unittest.TestCase):
    def test_only_execution_width_changes_both_arms(self):
        for arm in ('uniform_random', 'critic_topk_random'):
            original = dict(solver=dict(selection_policy=arm, num_children=4,
                critic_top_k=2, num_children_to_choose=1, common_start_protocol='rf_common_v1',
                selection_coupling='common_priority_v1', time_limit_secs=600, execution_timeout=300),
                generator='unchanged', task='unchanged')
            result = execute_two(original)
            self.assertEqual(original['solver']['num_children_to_choose'], 1)
            self.assertEqual(result['solver']['num_children_to_choose'], 2)
            with self.assertRaises(ValueError): execute_two(result)


if __name__ == '__main__': unittest.main()
