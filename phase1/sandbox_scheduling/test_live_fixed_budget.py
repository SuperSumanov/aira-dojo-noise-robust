import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest
from live_identity import verify


class IdentityTests(unittest.TestCase):
    def fixture(self):
        execution=dict(job='1',step='2',gpu_uuid='a',affinity=list(range(6))+list(range(32,38)),
            cpu_topology=[dict(logical_cpu=i,socket=0,core=i%32) for i in list(range(6))+list(range(32,38))])
        service=dict(job='1',step='1',gpu_uuids=['b','c'],
            cpu_topology=[dict(logical_cpu=i,socket=1,core=i) for i in range(12)])
        workers=[dict(job='1',step='2',gpu_uuids=['a']) for _ in range(4)]
        return execution,service,workers

    def test_six_physical_cores_twelve_threads_and_distinct_steps_pass(self):
        self.assertTrue(verify(*self.fixture()))

    def test_same_service_step_fails(self):
        e,s,w=self.fixture();s['step']=e['step'];self.assertFalse(verify(e,s,w))

    def test_same_cpu_core_or_gpu_fails(self):
        e,s,w=self.fixture();s['cpu_topology'][0]=dict(logical_cpu=5,socket=0,core=5)
        self.assertFalse(verify(e,s,w))
        e,s,w=self.fixture();s['gpu_uuids'][0]='a';self.assertFalse(verify(e,s,w))

    def test_wrong_worker_or_missing_topology_fails(self):
        e,s,w=self.fixture();w[0]['step']='3';self.assertFalse(verify(e,s,w))
        e,s,w=self.fixture();del e['cpu_topology'];self.assertFalse(verify(e,s,w))


class ProtocolTests(unittest.TestCase):
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
