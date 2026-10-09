import copy
import json
import contextlib
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from live_identity import verify


class IdentityTests(unittest.TestCase):
    def fixture(self):
        execution=dict(job='1',step='2',gpu_uuid='a',affinity=list(range(6))+list(range(32,38)),
            cpu_topology=[dict(logical_cpu=i,socket=0,core=i%32) for i in list(range(6))+list(range(32,38))])
        service=dict(job='1',step='1',gpu_uuids=['b','c'],
            cpu_topology=[dict(logical_cpu=i+16,socket=1,core=i) for i in range(12)])
        workers=[dict(job='1',step='2',gpu_uuids=['a']) for _ in range(4)]
        return execution,service,workers

    def test_six_physical_cores_twelve_threads_and_distinct_steps_pass(self):
        self.assertTrue(verify(*self.fixture()))

    def test_same_service_step_fails(self):
        e,s,w=self.fixture();s['step']=e['step'];self.assertFalse(verify(e,s,w))

    def test_inconsistent_logical_id_or_nine_service_cores_fails(self):
        e,s,w=self.fixture();s['cpu_topology'][0]['logical_cpu']=0
        self.assertFalse(verify(e,s,w))
        e,s,w=self.fixture();s['cpu_topology']=s['cpu_topology'][:9]
        self.assertFalse(verify(e,s,w))

    def test_same_cpu_core_or_gpu_fails(self):
        e,s,w=self.fixture();s['cpu_topology'][0]=dict(logical_cpu=5,socket=0,core=5)
        self.assertFalse(verify(e,s,w))
        e,s,w=self.fixture();s['gpu_uuids'][0]='a';self.assertFalse(verify(e,s,w))

    def test_wrong_worker_or_missing_topology_fails(self):
        e,s,w=self.fixture();w[0]['step']='3';self.assertFalse(verify(e,s,w))
        e,s,w=self.fixture();del e['cpu_topology'];self.assertFalse(verify(e,s,w))


class ProtocolTests(unittest.TestCase):
    def test_v7_generated_container_shim_imports_real_wrapper_host(self):
        command='''import json
from types import SimpleNamespace
import live_entry_fix_trial as entry
t=entry.trial
assert t.R.name.endswith('-v7') and t.SEED_BASE==142901
assert t.PHYSICAL_CPU_BINDING and not t.GENERATOR_ELIGIBILITY_GATE
assert len(t.FILES)==len(set(t.FILES))
assert t.entry_module() is entry
import sys
del sys.modules['live_entry_fix_trial']
old_main=sys.modules['__main__']
sys.modules['__main__']=entry
assert t.entry_module() is entry
sys.modules['__main__']=old_main
sys.modules['live_entry_fix_trial']=entry
seen=[]
t.host=lambda:SimpleNamespace(task_runtime=lambda:seen.append('called'))
exec('from '+t.NAME[:-3]+' import host; host().task_runtime()')
assert seen==['called']
print(json.dumps(dict(passed=True,entry=t.NAME)))
'''
        r=subprocess.run([sys.executable,'-B','-c',command],cwd=Path(__file__).parent,
                         capture_output=True,text=True,check=True)
        self.assertTrue(json.loads(r.stdout)['passed'])

    def test_v6_common_physical_cpu_fix_and_new_root(self):
        command='''import json
import live_physical_cpu_trial as entry
t=entry.trial
print(json.dumps(dict(root=str(t.R),hint=t.PHYSICAL_CPU_BINDING,seed=t.SEED_BASE,
    fixed=t.FIXED_BLOCK_SECONDS,gate=t.GENERATOR_ELIGIBILITY_GATE,files=t.FILES)))
'''
        r=subprocess.run([sys.executable,'-B','-c',command],cwd=Path(__file__).parent,
                         capture_output=True,text=True,check=True)
        v=json.loads(r.stdout)
        self.assertTrue(v['root'].endswith('-v6'));self.assertTrue(v['hint'])
        self.assertEqual(v['seed'],142901);self.assertEqual(v['fixed'],1320)
        self.assertFalse(v['gate']);self.assertEqual(len(v['files']),len(set(v['files'])))

    def test_full_synthetic_readout_checks_all_sixteen_and_budget(self):
        from live_search_trial_20261009 import schedule
        from live_readout import analyze
        def put(path,value):
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(json.dumps(value))
        with tempfile.TemporaryDirectory(prefix='r14-readout-',dir=Path(__file__).parent) as temp:
            root=Path(temp)
            put(root/'closed.json',dict(attempted_blocks=[0,1,2,3],controller_error=None))
            put(root/'plan.json',dict(schedule=schedule(),gpus=3,allocation_seconds=5400,
                fixed_block_seconds=1320,source_commit='fixture',files={},public_inputs={}))
            for row in schedule():
                ep=root/f'episode-{row["index"]}'
                put(ep/'closed.json',dict(returncode=0,cleanup_verified=True))
                put(ep/'finished.json',dict(status='budget_exhausted',native_selected_valid=True,
                    native_selected_score=.5,native_selected_code_sha256='code'))
                put(ep/'native.json',dict(job='1',step='2',gpu_uuids=['a']))
                for j in range(2 if row['arm']=='share2' else 1):
                    put(ep/f'candidate-{j}.json',dict(valid=True,score=.5,code_sha256='code',
                        elapsed_seconds=100+j,aux=dict(metric_name='metric',submission_sha256='submission')))
                    put(ep/f'scored-{j}.json',dict(receipt=dict(metric=.5,submission_sha256='submission')))
            for b in range(4):
                bd=root/f'block-{b}'
                e,s,_=IdentityTests().fixture()
                put(bd/'execution-native.json',e);put(bd/'service-native.json',s)
                put(bd/'service-cleanup.json',dict(gpu_clean=True))
                put(bd/'closed.json',dict(gpu_clean=True,telemetry_errors=[]))
                put(bd/'cycle-closed.json',dict(start=0,end=900))
                put(bd/'budget-slot.json',dict(reserved_seconds=1320,actual_seconds=1320.1))
            with contextlib.redirect_stdout(io.StringIO()):
                analyze(root,root/'derived-a',allocation_gpu_seconds=15900)
            result=json.loads((root/'derived-a/summary.json').read_text())
            self.assertTrue(result['feedback_throughput_signal']);self.assertTrue(result['exploratory_go'])
            put(root/'block-3/budget-slot.json',dict(reserved_seconds=1320,actual_seconds=1323))
            with contextlib.redirect_stdout(io.StringIO()):
                analyze(root,root/'derived-b',allocation_gpu_seconds=15900)
            result=json.loads((root/'derived-b/summary.json').read_text())
            self.assertFalse(result['feedback_throughput_signal']);self.assertFalse(result['exploratory_go'])

    def test_independent_unfiltered_fixed_budget_contract(self):
        command='''import json
import live_fixed_budget_trial as entry
t=entry.trial
print(json.dumps(dict(root=str(t.R),node=t.NODE,name=t.NAME,profile=t.PROFILE,
    cap=t.CAP,fixed=t.FIXED_BLOCK_SECONDS,gate=t.GENERATOR_ELIGIBILITY_GATE,
    seed_base=t.SEED_BASE,files=t.FILES,rows=t.schedule())))
'''
        r=subprocess.run([sys.executable,'-B','-c',command],cwd=Path(__file__).parent,
                         capture_output=True,text=True,check=True)
        v=json.loads(r.stdout)
        self.assertTrue(v['root'].endswith('-v5'))
        self.assertEqual(v['node'],'gpu27');self.assertEqual(v['profile'],'27b')
        self.assertFalse(v['gate']);self.assertEqual(v['fixed'],1320)
        self.assertEqual(v['cap'],5400);self.assertLess(4*v['fixed']+30,v['cap'])
        self.assertEqual(len(v['rows']),16);self.assertEqual(v['seed_base'],141901)
        self.assertEqual(len(v['files']),len(set(v['files'])))
        self.assertEqual([v['rows'][i]['arm'] for i in (0,4,8,12)],['pipeline','share2','share2','pipeline'])
        for k in range(2):
            for j in range(4):
                a,b=v['rows'][8*k+j],v['rows'][8*k+j+4]
                self.assertEqual((a['seed'],a['task']),(b['seed'],b['task']))


if __name__=='__main__':unittest.main()
