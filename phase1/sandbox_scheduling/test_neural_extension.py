import ast
import unittest
import neural_extension_20261010 as e


class ExtensionTests(unittest.TestCase):
    def test_worker_changes_are_declared(self):
        source=e.rewritten_worker()
        self.assertIn('else 1080',source);self.assertIn('else 450',source)
        self.assertIn('ji._gateway_port=',source)
        recovered=source.replace('else 1080','else 525').replace('ji._gateway_port=','ji._slurm_gateway_port=')
        self.assertEqual(ast.dump(ast.parse(recovered)),ast.dump(ast.parse(e.ORIGINAL_WORKER)))
    def test_matrix(self):
        rows=e.c.schedule();self.assertEqual(len(rows),12)
        self.assertEqual({r['arm'] for r in rows},{'pipeline','share2'})
        for program in (0,1):
            for arm in ('pipeline','share2'):
                self.assertEqual(sum(r['program']==program and r['arm']==arm for r in rows),3)
    def test_new_sources_but_same_two_tasks(self):
        self.assertEqual(len(set(p for t,p in e.PINS)),2)
        self.assertNotIn('c0888120b84c72f433712fb1c103f9e10e6ff18d84f5a15198d34b1159991369',dict(e.PINS).values())
        self.assertNotIn('0d7b2d191f2dd2e4dd7b28a6c3d678eb321eb3f008abdefab538703a71bbc3f9',dict(e.PINS).values())
    def test_batch(self):
        s=e.batch_script(f'#SBATCH --time=00:45:00\ncd {e.D}\ntimeout 2660s srun neural_full_confirmation.py controller')
        self.assertIn('01:30:00',s);self.assertIn('5350s',s);self.assertNotIn(str(e.D),s)
    def test_scope_overwrites_old_budget_gate(self):
        e.scope();self.assertEqual(e.c.r.CAP,5400);self.assertEqual(e.c.r.D,e.D)
        self.assertEqual(e.c.r.NAME,e.NAME)


if __name__=='__main__':unittest.main()
