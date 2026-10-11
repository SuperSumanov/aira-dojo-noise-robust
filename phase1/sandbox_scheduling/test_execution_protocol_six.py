import ast,os
from pathlib import Path
import unittest
from unittest.mock import patch
import execution_protocol_six_20261011 as m

class Tests(unittest.TestCase):
    def test_observer_does_not_clear_allocated_device_before_probe(self):
        for value in (None,'0','GPU-test'):
            with patch.dict(os.environ,{},clear=True),patch.object(m.e.r.s.d,'configure',side_effect=lambda:os.environ.update(CUDA_VISIBLE_DEVICES='')):
                if value is not None:os.environ['CUDA_VISIBLE_DEVICES']=value
                m.configure_preserving_device()
                self.assertEqual(os.environ.get('CUDA_VISIBLE_DEVICES'),value)
    def test_original_matrix_and_shared_roots(self):
        self.assertEqual(len(m.e.schedule()),14)
        self.assertEqual([sum(x['block']==b for x in m.e.schedule()) for b in range(4)],[1,1,6,6])
        self.assertEqual({x['program'] for x in m.e.schedule()},{1})
        self.assertTrue(all(x.ROOT==m.ROOT and x.NAME==m.NAME for x in (m.e,m.e.r,m.e.r.s,m.e.r.s.d)))
    def test_only_observers_not_runtime_retry(self):
        source=Path(m.__file__).read_text();tree=ast.parse(source)
        install=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='install')
        text=ast.unparse(install)
        self.assertNotIn('_JUPYTER_BOOTSTRAP',text)
        self.assertNotIn('sleep(',text)
        self.assertIn('original(proxy, timeout_seconds)',text)
        self.assertIn("env['PYTHONPATH'] = '/workspace/observer'",text)
        worker=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='worker')
        self.assertIn('return e.worker(index)',ast.unparse(worker))

if __name__=='__main__':unittest.main()
