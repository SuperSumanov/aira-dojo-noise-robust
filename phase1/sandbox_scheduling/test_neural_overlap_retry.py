import unittest
from unittest.mock import patch
import neural_overlap_retry as retry

class RetryTests(unittest.TestCase):
 def test_disclosed_retry_and_unchanged_limits(self):
  plan={};retry.mutate_plan(plan)
  self.assertEqual(plan['infrastructure_retry_of_job'],'17014')
  self.assertEqual(len(plan['schedule']),12)
  self.assertEqual(plan['total_cap_tightened_seconds'],1800)
  self.assertEqual(plan['interpreter_deadline_seconds'],525)
  self.assertEqual(plan['worker_hard_seconds'],550)
  self.assertTrue(plan['no_candidate_or_training_changes'])
 def test_budget_cap_and_script(self):
  r=retry.c.r
  keys=('R','NAME','NODE','CAP','JOBNAME','EXTRA_FILES','PLAN_MUTATOR','FIXTURE_BUILDER','QUESTION')
  old={k:getattr(r,k) for k in keys};oldroot=retry.c.R
  oldschedule=retry.c.n.schedule;oldwrite=retry.c.n.write
  try:
   with patch.object(r,'configure',side_effect=AssertionError('runtime')):retry.set_scope()
   text=f'#SBATCH --time=01:30:00\n#SBATCH --nodelist=gpu27\ncd {r.D}\ntimeout 5350s srun neural_pool_trial.py controller\n'
   batch=r.batch_script(text)
   self.assertIn('--time=00:30:00',batch)
   self.assertIn('1760s srun neural_overlap_retry.py controller',batch)
   self.assertIn(str(retry.R),batch)
  finally:
   for k,v in old.items():setattr(r,k,v)
   retry.c.R=oldroot;retry.c.n.schedule=oldschedule;retry.c.n.write=oldwrite

if __name__=='__main__':unittest.main()
