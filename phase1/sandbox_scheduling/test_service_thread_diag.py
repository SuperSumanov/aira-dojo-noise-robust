"""CPU-only state-machine tests extracted from the actual diagnostic driver."""
import ast
import concurrent.futures
from pathlib import Path
import types
import unittest


def run_control(kernel_failure=None, request_failure=None):
    source=Path(__file__).with_name('service_thread_diag_20261011.py')
    tree=ast.parse(source.read_text(encoding='utf-8'))
    fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='controller')
    written={}
    d=types.SimpleNamespace(resource_pressure=types.SimpleNamespace(snapshot=lambda:{}),
        write=lambda path,value:written.__setitem__(path.name,value),
        run_one=lambda b,i:dict(block=b,index=i,returncode=int((b,i)==kernel_failure)))
    scope=dict(d=d,ROOT=Path('/synthetic'),concurrent=concurrent,
        time=types.SimpleNamespace(sleep=lambda _:None),
        request_one=lambda b,i:dict(block=b,index=i,complete=(b,i)!=request_failure))
    exec(compile(ast.Module(body=[fn],type_ignores=[]),str(source),'exec'),scope)
    code=scope['controller']()
    return code,written['closed.json']


class ServiceDiagnosticTests(unittest.TestCase):
    def test_complete_matrix_preserved(self):
        code,receipt=run_control()
        self.assertEqual(code,0)
        self.assertEqual((receipt['planned'],receipt['attempted'],receipt['complete'],receipt['requests_complete']),(14,14,14,14))

    def test_first_six_way_failure_does_not_replace(self):
        code,receipt=run_control(kernel_failure=(1,3))
        self.assertEqual(code,1)
        self.assertEqual((receipt['planned'],receipt['attempted'],receipt['complete']),(14,7,6))

    def test_request_failure_also_closes_remaining_blocks(self):
        code,receipt=run_control(request_failure=(0,0))
        self.assertEqual(code,1)
        self.assertEqual((receipt['planned'],receipt['attempted'],receipt['requests_complete']),(14,1,0))


if __name__=='__main__':unittest.main()
