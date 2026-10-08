import unittest
from unittest.mock import patch
import neural_full_confirmation as c


class ConfirmationTests(unittest.TestCase):
    def test_actual_template_and_tighter_cap(self):
        text=f'#SBATCH --time=01:00:00\ncd {c.D}\ntimeout 3560s srun neural_full_input_trial.py controller\n'
        result=c.batch_script(text)
        self.assertIn('--time=00:45:00',result)
        self.assertIn('2660s srun neural_full_confirmation.py controller',result)
        self.assertIn(str(c.R),result)
        for token in ('--time=01:00:00','3560s srun','neural_full_input_trial.py controller',str(c.D)):
            with self.assertRaises(ValueError):c.batch_script(text.replace(token,'wrong'))

    def test_scope_does_not_access_runtime(self):
        fields={k:getattr(c.r,k) for k in ('R','D','DONOR','NAME','NODE','CAP','JOBNAME','FIXTURE_BUILDER','PLAN_MUTATOR','EXTRA_FILES','QUESTION','batch_script')}
        try:
            with patch.object(c.r,'configure',side_effect=AssertionError('runtime')):c.set_scope()
            self.assertEqual(c.r.D,c.D);self.assertEqual(c.r.CAP,2700)
            plan={};c.mutate_plan(plan)
            self.assertTrue(plan['independent_confirmation_not_replacement'])
            self.assertTrue(plan['original_per_candidate_and_worker_limits_unchanged'])
        finally:
            for k,v in fields.items():setattr(c.r,k,v)


if __name__=='__main__':unittest.main()
