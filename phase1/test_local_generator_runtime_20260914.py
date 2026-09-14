import ast,importlib.util,os,unittest
from pathlib import Path
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('runtime',Path(__file__).with_name('local_generator_runtime_20260914.py'))
runtime=importlib.util.module_from_spec(spec);spec.loader.exec_module(runtime)

class WiringTests(unittest.TestCase):
    def test_roles_share_allocation_and_disjoint_requests(self):
        with patch.dict(os.environ,{'SLURM_JOB_ID':'12345'}):
            for role,gpus in (('server',2),('worker',1)):
                cmd=runtime.step_command(role,gpus)
                self.assertIn('--jobid=12345',cmd)
                self.assertIn('--exclusive',cmd)
                self.assertNotIn('--exact',cmd)
                self.assertIn('--cpus-per-task=6',cmd)
                self.assertIn('--gres=gpu:'+str(gpus),cmd)
            with self.assertRaises(ValueError):runtime.step_command('server',8)

    def test_image_separation_readonly_weights_no_auth_in_arguments(self):
        cmd=runtime.service_command()
        self.assertIn(str(runtime.ASSETS/'model')+':/model:ro',cmd)
        self.assertIn(str(runtime.ASSETS/'vllm.sif'),cmd)
        self.assertNotIn('superimage',' '.join(cmd))
        self.assertNotIn('LD_LIBRARY_PATH',' '.join(cmd))
        self.assertNotIn('--api-key',cmd)
        self.assertIn('--no-home',cmd)

    def test_service_entry_parses_and_pins_caps(self):
        tree=ast.parse(runtime.SERVICE_ENTRY)
        assignment=next(n for n in tree.body if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Attribute) and n.targets[0].attr=='argv')
        args=ast.literal_eval(assignment.value)
        for name,value in (('--tensor-parallel-size','2'),('--max-model-len','131072'),('--max-num-seqs','6'),('--host','127.0.0.1'),('--seed','49')):
            self.assertEqual(args[args.index(name)+1],value)
        self.assertNotIn('--api-key',args)
        self.assertNotIn('--enforce-eager',args)

    def test_mle_binding_must_belong_to_current_allocation(self):
        env={'FORETS_CURRENT_POOL_ROOT':str(runtime.ROOT),'DOJO_WORKER_IDENTITY_PATH':str(runtime.ROOT/'identity-2.json'),'SLURM_JOB_ID':'123'}
        with patch.object(runtime,'read',return_value={'job':'123'}):
            self.assertEqual(runtime.binding_context(env),runtime.ROOT/'identity-2.native-binding.json')
        with patch.object(runtime,'read',return_value={'job':'456'}):
            with self.assertRaises(ValueError):runtime.binding_context(env)
        env['DOJO_WORKER_IDENTITY_PATH']=str(runtime.ROOT.parent/'identity-2.json')
        with self.assertRaises(ValueError):runtime.binding_context(env)

if __name__=='__main__':unittest.main()
