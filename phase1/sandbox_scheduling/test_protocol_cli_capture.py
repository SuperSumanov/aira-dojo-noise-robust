import ast,builtins,sys,unittest
from pathlib import Path
from unittest.mock import patch
from protocol_cli_capture_20261011 import SITE,transform

class Tests(unittest.TestCase):
    def test_observer_only_in_cli_exec_child(self):
        original=builtins.__import__
        for name,expected in [('-c',0),('ipykernel_launcher.py',0),('/opt/conda/bin/jupyter-kernelgateway',1)]:
            calls=[]
            def importing(name,*a,**kw):
                if name=='gateway_counter':calls.append(name);return object()
                return original(name,*a,**kw)
            with patch.object(sys,'argv',[name]),patch('builtins.__import__',side_effect=importing):exec(SITE,{})
            self.assertEqual(len(calls),expected)
    def test_original_bootstrap_and_client_kept(self):
        source=Path(__file__).with_name('kernel_protocol_trace_20261011.py').read_text();out=transform(source)
        tree=ast.parse(out);slot=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='slot')
        self.assertNotIn('_JUPYTER_BOOTSTRAP',ast.unparse(slot))
        self.assertIn('original(proxy, timeout_seconds)',ast.unparse(slot))
        self.assertIn("env['PYTHONPATH'] = '/workspace/observer'",ast.unparse(slot))
        self.assertIn('CAP=900',out)
        self.assertIn("raise RuntimeError('captured readiness failure')",out)

if __name__=='__main__':unittest.main()
