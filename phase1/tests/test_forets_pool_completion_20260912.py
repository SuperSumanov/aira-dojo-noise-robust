import ast
import importlib.util
from pathlib import Path
import unittest

PHASE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('completion',PHASE/'forets_pool_completion_20260912.py')
worker=importlib.util.module_from_spec(spec);spec.loader.exec_module(worker)

class CompletionTests(unittest.TestCase):
    def test_only_unattempted_slots_and_no_code_edits(self):
        codes=['print('+str(i)+')\n' for i in range(4)];saved=list(codes)
        self.assertEqual(worker.unattempted_slots(codes,{worker.sha(codes[1].encode())},[1]),[0,2,3])
        self.assertEqual(codes,saved)
    def test_failed_or_other_run_attempt_is_also_excluded(self):
        codes=['code'+str(i) for i in range(4)]
        with self.assertRaises(ValueError):
            worker.unattempted_slots(codes,{worker.sha(codes[i].encode()) for i in [0,1]},[1])
    def test_unexpected_duplicate_or_missing_original_is_rejected(self):
        with self.assertRaises(ValueError):worker.unattempted_slots(['x']*4,{worker.sha(b'x')},[0])
        with self.assertRaises(ValueError):worker.unattempted_slots(['a','b','c','d'],set(),[0])
    def test_existing_executor_default_is_unchanged(self):
        tree=ast.parse((PHASE/'forets_closed_pool_20260911.py').read_text())
        f=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='execute_one')
        defaults=dict(zip([a.arg for a in f.args.kwonlyargs],f.args.kw_defaults))
        self.assertEqual(ast.literal_eval(defaults['ready_timeout']),10)
        self.assertIn('ready_timeout=120',(PHASE/'forets_pool_completion_20260912.py').read_text())

if __name__=='__main__':unittest.main()
