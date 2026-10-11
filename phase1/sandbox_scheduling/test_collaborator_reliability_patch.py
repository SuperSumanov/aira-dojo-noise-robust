import ast,logging,tempfile,types,unittest
from pathlib import Path
import collaborator_reliability_patch as p

REPO=Path(__file__).resolve().parents[2]

def method(text,cls,name):
    tree=ast.parse(text);c=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==cls)
    fn=next(n for n in c.body if isinstance(n,ast.FunctionDef) and n.name==name)
    scope=dict(log=logging.getLogger('patch-test'))
    exec(compile(ast.Module(body=[fn],type_ignores=[]),'exact-f7-patch','exec'),scope)
    return scope[name]

class Tests(unittest.TestCase):
    def test_only_intended_methods_and_drift_rejected(self):
        old,new=p.sources(REPO);self.assertEqual(len(old),4)
        with self.assertRaises(AssertionError):p.once('missing','anchor','replacement')
    def test_interpreter_cleanup_preserves_failure_and_stops_server(self):
        _,new=p.sources(REPO);calls=[]
        def fail():calls.append('kernel');raise RuntimeError('injected')
        obj=types.SimpleNamespace(cleanup_session=fail,jupyter_server=types.SimpleNamespace(stop=lambda:calls.append('server')))
        with self.assertRaises(RuntimeError):method(new[p.FILES[2]],'JupyterInterpreter','close')(obj)
        self.assertEqual(calls,['kernel','server'])
    def test_executor_deletes_after_socket_failure(self):
        _,new=p.sources(REPO);calls=[]
        def fail():calls.append('socket');raise RuntimeError('injected')
        obj=types.SimpleNamespace(_kernel_id='test',_jupyter_kernel_client=types.SimpleNamespace(stop=fail),
            _jupyter_client=types.SimpleNamespace(delete_kernel=lambda k:calls.append('delete')))
        with self.assertRaises(RuntimeError):method(new[p.FILES[1]],'JupyterCodeExecutor','stop')(obj)
        self.assertEqual(calls,['socket','delete'])
if __name__=='__main__':unittest.main()
