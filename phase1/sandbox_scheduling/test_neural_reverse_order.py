import ast
import datetime
import unittest
from unittest.mock import patch
import neural_reverse_order_20261010 as r


class ReverseTests(unittest.TestCase):
    def test_exact_opposite_arms_same_programs_and_rng(self):
        original = [dict(x,arm='pipeline' if x['arm']=='serial' else 'share2',position=x['index']%2)
                    for x in r.ORIGINAL_BASE_SCHEDULE()]
        current = r.reverse_schedule()
        self.assertEqual(len(current),12)
        for a,b in zip(original,current):
            self.assertNotEqual(a['arm'],b['arm'])
            self.assertEqual({k:v for k,v in a.items() if k!='arm'},
                             {k:v for k,v in b.items() if k!='arm'})
        self.assertEqual([current[2*b]['arm'] for b in range(6)],
                         ['share2','pipeline','pipeline','share2','share2','pipeline'])

    def test_combined_arm_positions_balanced(self):
        first = r.ORIGINAL_BASE_SCHEDULE(); second = r.reverse_schedule()
        old = ['pipeline' if first[2*b]['arm']=='serial' else 'share2' for b in range(6)]
        new = [second[2*b]['arm'] for b in range(6)]
        self.assertEqual(sum(i for seq in (old,new) for i,a in enumerate(seq) if a=='pipeline'),
                         sum(i for seq in (old,new) for i,a in enumerate(seq) if a=='share2'))

    def test_same_worker_source_and_limits(self):
        recovered = r.e.rewritten_worker().replace('else 1080','else 525').replace(
            'ji._gateway_port=','ji._slurm_gateway_port=')
        self.assertEqual(ast.dump(ast.parse(recovered)),ast.dump(ast.parse(r.e.ORIGINAL_WORKER)))

    def test_allocation_and_scope(self):
        s = r.batch_script(f'#SBATCH --time=00:45:00\n#SBATCH --cpus-per-task=6\ncd {r.e.D}\ntimeout 2660s srun --cpu-bind=cores neural_full_confirmation.py controller')
        self.assertIn('01:15:00',s);self.assertIn('4450s srun',s)
        self.assertEqual(s.count('--hint=nomultithread'),2)
        r.scope();self.assertEqual(r.e.c.r.CAP,4500)
        self.assertIn('test_neural_reverse_order.py',r.e.c.r.EXTRA_FILES)

    def test_accounting_all_jobs_and_failures(self):
        raw='17364|COMPLETED|216|cpu=6,gres/gpu=1\n17366|COMPLETED|1796|cpu=6,gres/gpu=1\n17368|FAILED|100|cpu=18,gres/gpu=3\n'
        self.assertEqual(r.accounted_costs(raw),{'17364':216,'17366':1796,'17368':300})
        for bad in (raw.replace('FAILED','RUNNING'),raw+raw.splitlines()[0]+'\n',raw.replace('17368|FAILED|100','17368|FAILED|12000')):
            with self.assertRaises(ValueError):r.accounted_costs(bad)

    def test_no_late_preparation(self):
        with self.assertRaises(ValueError):r.prerequisites(r.WINDOW_END-datetime.timedelta(minutes=10))

    def test_no_live_outcome_condition(self):
        with patch.object(r,'sha',side_effect=[r.PREVIOUS_PLAN,r.PREVIOUS_RESULT,r.LIVE_PLAN]), \
             patch.object(r.Path,'exists',return_value=True), \
             patch.object(r,'read',return_value={'plan_sha256':r.LIVE_PLAN,'complete':16,'structural_audit':True,'exploratory_go':False}):
            self.assertFalse(r.prerequisites(r.WINDOW_END-datetime.timedelta(hours=3))['exploratory_go'])

    def test_manifest_has_reverse_matrix_and_honest_scope(self):
        plan = {'programs':[{},{}], 'preflight_items':{}}
        r.mutate(plan)
        self.assertEqual(plan['schedule'],r.reverse_schedule())
        self.assertIn('first block is now share2',plan['first_serial_gate'])
        self.assertEqual(plan['reverse_order_batch_cap_gpu_hours'],1.25)
        self.assertEqual(plan['new_window_cost_cap_gpu_hours'],10.25)
        self.assertTrue(plan['original_frozen_gate_unchanged'])


if __name__=='__main__':
    unittest.main()
