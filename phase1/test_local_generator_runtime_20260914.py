import ast,importlib.util,os,unittest
import io,urllib.error,json,copy,types
from pathlib import Path
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('runtime',Path(__file__).with_name('local_generator_runtime_20260914.py'))
runtime=importlib.util.module_from_spec(spec);spec.loader.exec_module(runtime)

class WiringTests(unittest.TestCase):
    def test_server_uses_writable_cache_and_retry_keeps_total_budget(self):
        with patch.object(runtime,'check_files'),patch.object(runtime,'native_service_devices',return_value=['GPU-fixture-a','GPU-fixture-b']),\
             patch.object(runtime,'write'),patch.object(runtime,'local_key',return_value='synthetic-fixture'),\
             patch.dict(os.environ,{'SLURM_JOB_ID':'123','SLURM_STEP_ID':'0'}),patch.object(runtime.os,'execve') as execute:
            runtime.server()
        env=execute.call_args.args[2]
        self.assertEqual(env['SINGULARITYENV_FLASHINFER_WORKSPACE_BASE'],'/cache/flashinfer')
        self.assertEqual(env['SINGULARITYENV_XDG_CACHE_HOME'],'/cache/xdg')
        self.assertNotIn('SINGULARITYENV_LD_LIBRARY_PATH',env)
        self.assertLessEqual((80+runtime.ATTEMPT_SECONDS)*3,3*3600)

    def test_fixed_plan_accepts_all_files_and_rejects_duplicate_or_missing(self):
        plan=json.loads((Path(__file__).parent/'results/local_generator_integration_20260914/assets/plan.json').read_text())
        self.assertEqual(len(plan['files']),18)
        rows=[dict(path=e['path'],bytes=e['size'],digest=e['expected'] or
              '495ca35a3fa7fc534bbd855829af1b86ce75ab9a5675b3b1ab7dba58ca74b7fa') for e in plan['files']]
        complete=dict(model_ready=True,model=plan['model'],revision=plan['revision'],plan_sha256=runtime.PLAN_SHA,files=rows)
        sizes={str(runtime.ASSETS/e['path']):e['size'] for e in plan['files']}
        def fake_read(p):return plan if p.name=='plan.json' else complete
        def fake_sha(p):return runtime.PLAN_SHA if p.name=='plan.json' else 'receipt-fixture'
        def fake_stat(p):return types.SimpleNamespace(st_size=sizes[str(p)])
        with patch.object(runtime,'read',side_effect=fake_read),patch.object(runtime,'sha',side_effect=fake_sha),\
             patch.object(Path,'is_symlink',return_value=False),patch.object(Path,'stat',fake_stat):
            self.assertEqual(runtime.asset_check(plan),'receipt-fixture')
            complete['files']=rows+[copy.deepcopy(rows[0])]
            with self.assertRaises(ValueError):runtime.asset_check(plan)
            complete['files']=rows[:-1]
            with self.assertRaises(ValueError):runtime.asset_check(plan)

    def test_unauthenticated_other_service_never_receives_our_token(self):
        from unittest.mock import Mock
        opener=Mock();opener.open.return_value=io.BytesIO(b'{"data":[]}')
        with patch.object(runtime.urllib.request,'build_opener',return_value=opener),patch.object(runtime,'local_key') as key:
            self.assertFalse(runtime.own_health());key.assert_not_called()

    def test_authenticated_own_model_is_required(self):
        from unittest.mock import Mock
        opener=Mock()
        opener.open.side_effect=[urllib.error.HTTPError('http://127.0.0.1:8000/v1/models',401,'Unauthorized',{},None),
                                 io.BytesIO(b'{"data":[{"id":"qwen3.8-27b"}]}')]
        with patch.object(runtime.urllib.request,'build_opener',return_value=opener),patch.object(runtime,'local_key',return_value='synthetic-fixture'):
            self.assertTrue(runtime.own_health())
        self.assertEqual(opener.open.call_count,2)

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
