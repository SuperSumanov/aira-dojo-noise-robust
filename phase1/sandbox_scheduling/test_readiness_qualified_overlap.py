from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import readiness_qualified_overlap as q
from lifecycle_pilot import write


class EveningTests(unittest.TestCase):
    def test_three_qualification_restarts_no_data_or_candidate(self):
        self.assertEqual([r['index'] for r in q.q_schedule()], [0,1,2])
        self.assertEqual({r['arm'] for r in q.q_schedule()}, {'close_now'})

    def test_formal_plan_preserves_matrix_and_limits(self):
        plan = {}
        with patch.object(q, 'qualification_gate', return_value={'job':'1'}):
            q.mutate_plan(plan)
        self.assertEqual(len(plan['schedule']), 12)
        self.assertEqual(plan['interpreter_deadline_seconds'], 525)
        self.assertEqual(plan['worker_hard_seconds'], 550)
        self.assertTrue(plan['no_candidate_or_training_changes'])
        self.assertEqual(plan['infrastructure_retry_of_jobs'], ['17014','17021'])
        self.assertEqual(plan['common_handshake_sha256'], q.HELPER_SHA)
        self.assertEqual(plan['new_evening_window_gpu_seconds_cap'], 2400)

    def test_no_failed_qualification_can_open_comparison(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp, patch.object(q, 'Q', Path(tmp)), patch.object(q, 'q_check'):
            write(q.Q/'closed.json', {'complete':False})
            with self.assertRaisesRegex(ValueError, 'did not pass'):
                q.qualification_gate()

    def test_roots_are_new_and_distinct(self):
        self.assertNotEqual(q.Q, q.QD)
        self.assertNotEqual(q.Q, q.R)
        self.assertIn('evening', str(q.R))

    def test_comparison_scope_has_same_runtime_but_explicit_helper(self):
        r = q.control.r
        fields = ('R','NAME','NODE','CAP','JOBNAME','FIXTURE_BUILDER','PLAN_MUTATOR','EXTRA_FILES','QUESTION')
        saved = {k:getattr(r,k) for k in fields}
        oldroot = q.control.R
        oldschedule, oldwrite = q.control.n.schedule, q.control.n.write
        try:
            with patch.object(r, 'configure', return_value=None):
                q.configure()
            self.assertEqual(r.CAP, 1800)
            self.assertEqual(r.NODE, 'gpu27')
            self.assertIn('bounded_readiness.py', r.EXTRA_FILES)
            batch = r.batch_script(f'#SBATCH --time=01:30:00\n#SBATCH --nodelist=gpu27\ncd {r.D}\ntimeout 5350s srun neural_pool_trial.py controller\n')
            self.assertIn('--time=00:30:00', batch)
            self.assertIn('1760s srun readiness_qualified_overlap.py controller', batch)
        finally:
            for k,v in saved.items():
                setattr(r,k,v)
            q.control.R = oldroot
            q.control.n.schedule, q.control.n.write = oldschedule, oldwrite

    def test_prepare_does_not_load_runtime_before_materialization(self):
        with patch.object(q.sys,'argv',[q.NAME,'prepare','--commit','a'*40]), \
             patch.object(q,'set_scope') as scope, \
             patch.object(q,'configure',side_effect=AssertionError('premature runtime')), \
             patch.object(q.control.r,'prepare',return_value='prepared') as prepare:
            self.assertEqual(q.main(),'prepared')
            scope.assert_called_once_with()
            prepare.assert_called_once_with('a'*40)


if __name__ == '__main__':
    unittest.main()
