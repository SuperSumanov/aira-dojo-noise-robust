from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from verify_delivery_width_exports_20260913 import task_arm_statistics


class StatisticsTests(unittest.TestCase):
    def test_missing_does_not_become_zero_and_cost_retained(self):
        rows=[dict(task='fixture',arm='control',technical_eligible=True,action_valid=True,
            action_score=.5,iteration_valid=False,iteration_score=None,api_cost_usd=.1),
            dict(task='fixture',arm='control',technical_eligible=False,action_valid=True,
                action_score=.9,iteration_valid=True,iteration_score=.9,api_cost_usd=.2)]
        action,iteration=task_arm_statistics(rows)
        self.assertEqual(action['median'],.5)
        self.assertIsNone(action['sample_std'])
        self.assertEqual(action['valid_scores'],1)
        self.assertAlmostEqual(action['summed_api_usd'],.3)
        self.assertIsNone(iteration['median'])

    def test_sample_not_population_sd(self):
        rows=[dict(task='fixture',arm='control',technical_eligible=True,action_valid=True,
            action_score=v,iteration_valid=True,iteration_score=v,api_cost_usd=.1) for v in (1,3)]
        for row in task_arm_statistics(rows):
            self.assertEqual(row['median'],2)
            self.assertAlmostEqual(row['sample_std'],2**.5)


if __name__=='__main__':unittest.main()
