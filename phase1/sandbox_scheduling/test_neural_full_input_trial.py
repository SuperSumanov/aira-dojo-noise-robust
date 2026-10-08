import unittest
from unittest.mock import patch

import neural_node_replication as r
from neural_full_input_trial import set_scope, accounted_costs


class FullInputTests(unittest.TestCase):
    def test_zero_allocation_cancelled_queue_job(self):
        raw='1|COMPLETED|20|cpu=6,gres/gpu=1|\n2|CANCELLED by 7542|0||\n'
        self.assertEqual(accounted_costs(raw,['1','2'],'2'),{'1':20,'2':0})

    def test_reject_unclosed_or_ambiguous_accounting(self):
        invalid=('2|PENDING|0||','2|RUNNING|3|gres/gpu=1|',
                 '2|CANCELLED by 7542|1||','2|COMPLETED|0||',
                 '2|COMPLETED|3|gres/gpu=2|','2|COMPLETED|-1|gres/gpu=1|',
                 '2|CANCELLED by 7542|0||\n2.0|COMPLETED|1|gres/gpu=1|')
        for raw in invalid:
            with self.subTest(raw=raw),self.assertRaises(ValueError):
                accounted_costs(raw,['2'],'2')
        with self.assertRaises(ValueError):accounted_costs('2|CANCELLED|0||',['1','2'],'2')
        with self.assertRaises(ValueError):accounted_costs('2|CANCELLED|0||',['2','2'],'2')
        with self.assertRaises(ValueError):accounted_costs('2|CANCELLED|0||\n2|CANCELLED|0||',['2'],'2')

    def test_scope_can_be_selected_without_loading_unbuilt_runtime(self):
        fields={name:getattr(r,name) for name in ('R','NAME','NODE','CAP','JOBNAME','FIXTURE_BUILDER','QUESTION')}
        try:
            with patch.object(r,'configure',side_effect=AssertionError('runtime loaded before prepare')):
                set_scope()
            self.assertEqual(r.CAP,3600)
            self.assertEqual(r.NODE,'gpu27')
            batch=r.batch_script('#SBATCH --time=01:30:00\n#SBATCH --nodelist=gpu27\ntimeout --signal=TERM --kill-after=15s 5350s srun worker')
            self.assertIn('--time=01:00:00',batch)
            self.assertIn('3560s srun',batch)
        finally:
            for name,value in fields.items():setattr(r,name,value)


if __name__=='__main__':unittest.main()
