import ast
from pathlib import Path
import unittest
from protocol_capture_20261011 import transform

class CaptureTests(unittest.TestCase):
    def test_runtime_changes_only_scope_and_stop(self):
        source=Path(__file__).with_name('kernel_protocol_trace_20261011.py').read_text();out=transform(source)
        before={x.name:ast.dump(x) for x in ast.parse(source).body if isinstance(x,ast.FunctionDef)}
        after={x.name:ast.dump(x) for x in ast.parse(out).body if isinstance(x,ast.FunctionDef)}
        self.assertEqual(before['slot'],after['slot'])
        self.assertEqual(before['direct_counter'],after['direct_counter'])
        self.assertIn('WIDTH=6;ROUNDS=32;CAP=1200',out)
        self.assertIn('dict(planned=192,attempted=',out)
        self.assertIn("raise RuntimeError('captured readiness failure')",out)

if __name__=='__main__':unittest.main()
