import unittest
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path
import execution_six_20261011 as e

class ExecutionTests(unittest.TestCase):
    def test_fixed_denominator(self):
        rows=e.schedule();self.assertEqual([sum(r['block']==b for r in rows) for b in range(4)],[1,1,6,6]);self.assertEqual({r['program'] for r in rows},{1})

    def test_all_call_flags_without_mutating_result(self):
        result=SimpleNamespace(term_out=['OpenBLAS pthread_create failed'],exit_code=0,timed_out=False)
        class Base:
            def execute_code(self,code):return result
        values=[]
        with patch.object(e,'write',side_effect=lambda p,v:values.append(v)):
            obj=e.observe_executor(Base,Path('/tmp'))();actual=obj.execute_code('fixed source')
        self.assertIs(actual,result);self.assertTrue(values[0]['flags']['pthread_create']);self.assertEqual(values[0]['exit_code'],0)

    def test_distinct_cpu_gpu_required(self):
        a=dict(job='1',step='0',gpu_uuids=['g1'],cpu_topology=[dict(logical_cpu=i,socket=0,core=i) for i in range(4)])
        self.assertEqual(e.placement([a],'1'),dict(gpu_count=1,physical_cores=4))
        with self.assertRaises(AssertionError):e.placement([a,dict(a,step='1')],'1')

if __name__=='__main__':unittest.main()
