import ast
import copy
from pathlib import Path
import unittest
from live_identity import cores


def functions():
    p=Path(__file__).with_name('six_gpu_capacity_20261011.py')
    nodes=[n for n in ast.parse(p.read_text()).body if isinstance(n,ast.FunctionDef) and n.name in ('schedule','validate_block')]
    scope=dict(cores=cores);exec(compile(ast.Module(body=nodes,type_ignores=[]),str(p),'exec'),scope);return scope


def topology(start,count):return [dict(socket=0,core=i,logical_cpu=i) for i in range(start,start+count)]


class CapacityTests(unittest.TestCase):
    def test_matrix(self):
        rows=functions()['schedule']()
        self.assertEqual(len(rows),14)
        self.assertEqual([sum(r['block']==b for r in rows) for b in range(4)],[1,1,6,6])
        self.assertEqual([sum(r['program']==p for r in rows) for p in (0,1)],[7,7])

    def test_isolation_and_resource_count(self):
        service=dict(uuids=['s0','s1'],step='0')
        workers=[dict(gpu_uuids=[f'w{i}'],cpu_topology=topology(8+4*i,4),job='99',step=str(i+1)) for i in range(6)]
        check=functions()['validate_block']
        self.assertEqual(check(service,topology(0,8),workers,'99'),dict(gpu_count=8,physical_cores=32))
        for field,value in [('gpu_uuids',['s0']),('cpu_topology',topology(0,4)),('job','wrong'),('step','0')]:
            bad=copy.deepcopy(workers);bad[0][field]=value
            with self.assertRaises(AssertionError):check(service,topology(0,8),bad,'99')


if __name__=='__main__':unittest.main()
