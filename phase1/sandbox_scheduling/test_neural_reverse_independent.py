import datetime
import unittest
from unittest.mock import patch
import neural_reverse_independent_20261010 as r


class IndependentReverseTests(unittest.TestCase):
    def valid_result(self):
        return dict(plan_sha256=r.old.LIVE_PLAN,assigned=16,observed_pool_pairs=2,
                    structural_audit=True,controller_error=None,complete=15,
                    exploratory_go=False)

    def run_prerequisite(self,result,duplicate=False):
        def exists(path):
            if path.parent==r.ABANDONED_ROOT:return duplicate
            return True
        with patch.object(r,'sha',side_effect=[r.old.PREVIOUS_PLAN,r.old.PREVIOUS_RESULT,r.old.LIVE_PLAN]), \
             patch.object(r.old.Path,'exists',exists),patch.object(r,'read',return_value=result):
            return r.prerequisites(r.old.WINDOW_END-datetime.timedelta(hours=3))

    def test_model_failure_does_not_decide_independent_program_eligibility(self):
        self.assertEqual(self.run_prerequisite(self.valid_result())['complete'],15)

    def test_does_not_read_quality(self):
        result=self.valid_result();result.pop('complete');result.pop('exploratory_go')
        self.assertEqual(self.run_prerequisite(result),result)

    def test_infrastructure_and_incomplete_matrix_block(self):
        for key,value in (('assigned',8),('observed_pool_pairs',1),('structural_audit',False),('controller_error','ValueError')):
            result=self.valid_result();result[key]=value
            with self.assertRaises(ValueError):self.run_prerequisite(result)

    def test_never_double_submits_predecessor(self):
        with self.assertRaises(ValueError):self.run_prerequisite(self.valid_result(),True)

    def test_same_twelve_sources_and_gate(self):
        plan={'programs':[{},{}],'preflight_items':{}}
        r.mutate(plan)
        self.assertEqual(plan['schedule'],r.old.reverse_schedule())
        self.assertEqual(len(plan['schedule']),12)
        self.assertIn('median pipeline/share2>=1.05',plan['decision'])
        self.assertTrue(plan['original_frozen_gate_unchanged'])
        self.assertEqual(plan['reverse_order_batch_cap_gpu_hours'],1.25)
        r.scope()
        self.assertIn('neural_reverse_order_20261010.py',r.old.e.c.r.EXTRA_FILES)
        self.assertIn('test_neural_reverse_independent.py',r.old.e.c.r.EXTRA_FILES)

    def test_window_deadline_not_relaxed(self):
        with self.assertRaises(ValueError):r.prerequisites(r.old.WINDOW_END)


if __name__=='__main__':unittest.main()
