import unittest
from unittest.mock import patch

import neural_node_replication as r
from neural_full_input_trial import set_scope


class FullInputTests(unittest.TestCase):
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
