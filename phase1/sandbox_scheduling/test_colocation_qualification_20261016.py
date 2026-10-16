"""Run the COMPLETE qualification function with inert OS/GPU boundaries.

This reproduces18468 from its exact committed source and rejects the bad
release/admit sequence. Passing this is NOT real CUDA or container validation.
"""
import ast
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
from types import SimpleNamespace
import unittest

import colocation_pool_20261016 as pool

SOURCE=Path(__file__).with_name('colocation_trial_20261016.py')
FAILED_COMMIT='2ec2903f746e5368025a26a75d1c20cf3ebb9c3c'


def function(source,namespace):
    tree=ast.parse(source)
    node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='qualification')
    exec(compile(ast.Module(body=[node],type_ignores=[]),'<exact qualification fixture>','exec'),namespace)
    return namespace['qualification']


class QualificationTests(unittest.TestCase):
    def exercise(self,source,fail_at=None,bad_receipt=False):
        # All external boundaries, including filesystem creation, are inert.
        # This tests the real control flow, not CUDA or a real namespace.
        class InertPath(PurePosixPath):
            def mkdir(self,*a,**kw):pass
        root=InertPath('inert-root');writes={};devices=[];states=[]
        class State(pool.State):
            def __init__(self,*a,**kw):super().__init__(*a,**kw);states.append(self)
        def write(path,value):writes[path.name]=value
        def command(args,uid):
            devices.append(uid)
            return ['inert-boundary',uid],{},dict(gpu_uuid=uid,namespace={'exact_device_namespace':True})
        def run(cmd,**kw):
            i=int(cmd[-1].split('-')[-1])
            if i==fail_at:return SimpleNamespace(returncode=1,stdout='',stderr='fixture failure')
            record=dict(passed=not bad_receipt,device_count=1,cap_eff=0,result=4096)
            return SimpleNamespace(returncode=0,stdout='POOL_CUDA_GATE '+json.dumps(record)+'\n',stderr='')
        ns=dict(R=root,pool=SimpleNamespace(State=State),host=lambda:SimpleNamespace(TASK_IMAGE='inert-image'),
            namespace_command=command,subprocess=SimpleNamespace(run=run),write=write,json=json,
            read=lambda _:dict(source_commit=FAILED_COMMIT))
        try:function(source,ns)(dict(gpu_uuids=[f'GPU-fixture-{i}' for i in range(4)]))
        finally:self.last=(devices,writes,states)
        return devices,writes,states

    def test_corrected_complete_qualification(self):
        devices,writes,states=self.exercise(SOURCE.read_text(encoding='utf-8'))
        self.assertEqual(devices,[f'GPU-fixture-{i}' for i in range(4)])
        result=writes['dispatch-qualification.json']
        self.assertTrue(result['passed'])
        self.assertEqual([r['device'] for r in result['rows']],list(range(4)))
        self.assertEqual([r['home'] for r in result['rows']],[3]*4)
        self.assertEqual(states[0].active,{})
        self.assertEqual(states[0].queue,[])

    def test_exact_failed_source_reproduces_after_first_device(self):
        frozen=Path('/research/d7/spc/yzyang4/scheduling-pooling-20261015-v1/pooling_trial_20261015.py')
        if frozen.exists():
            raw=frozen.read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(),'3fde212f692e6a8cfc84761a96248e224cb488f8ff4e9abd2f60843dfbc33fbe')
            old=raw.decode('utf-8')
        else:
            old=subprocess.check_output(['git','show',FAILED_COMMIT+':phase1/sandbox_scheduling/pooling_trial_20261015.py'],cwd=SOURCE.parent,text=True,encoding='utf-8')
        with self.assertRaises(AssertionError):self.exercise(old)
        devices,writes,states=self.last
        self.assertEqual(devices,['GPU-fixture-0'])
        self.assertNotIn('dispatch-qualification.json',writes)
        self.assertEqual(states[0].active['1']['device'],0)

    def test_cuda_failure_never_passes(self):
        with self.assertRaisesRegex(RuntimeError,'qualification failed'):
            self.exercise(SOURCE.read_text(encoding='utf-8'),fail_at=2)
        self.assertNotIn('dispatch-qualification.json',self.last[1])
        self.assertIn('failed-2.safe.json',self.last[1])

    def test_false_receipt_never_passes(self):
        with self.assertRaisesRegex(RuntimeError,'qualification failed'):
            self.exercise(SOURCE.read_text(encoding='utf-8'),bad_receipt=True)
        self.assertNotIn('dispatch-qualification.json',self.last[1])


if __name__=='__main__':unittest.main()
