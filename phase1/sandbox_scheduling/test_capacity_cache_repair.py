import ast
from pathlib import Path
import unittest
from capacity_cache_repair_20261011 import patched_driver


class CacheRepairTests(unittest.TestCase):
    def test_only_diagnostic_capture_changes_worker(self):
        text=Path(__file__).with_name('six_gpu_capacity_20261011.py').read_text()
        changed=patched_driver(text,'new-test-root')
        self.assertIn("'new-test-root'",changed)
        before=ast.parse(text);after=ast.parse(changed)
        funcs=lambda t:{n.name:n for n in t.body if isinstance(n,ast.FunctionDef)}
        a,b=funcs(before),funcs(after)
        for name in a:
            if name!='worker':self.assertEqual(ast.dump(a[name]),ast.dump(b[name]))
        calls=lambda t:[ast.dump(n) for n in ast.walk(t) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='execute_code']
        self.assertEqual(calls(a['worker']),calls(b['worker']))


if __name__=='__main__':unittest.main()
