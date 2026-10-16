import unittest
from closed_clock_granularity_20261016 import classify

class ScopeTests(unittest.TestCase):
    def scopes(self,code):return classify(code)['exit_scope_counts']
    def test_fold(self):
        self.assertEqual(self.scopes('import time\nfor fold_idx in range(5):\n if time.time()>201.6: break'),{'break:fold_named':1})
    def test_inner_epoch(self):
        self.assertEqual(self.scopes('import time\nfor fold in range(5):\n for epoch in range(12):\n  if time.time()>10: break'),{'break:epoch_named':1})
    def test_batch_alias(self):
        self.assertEqual(self.scopes('from time import monotonic as now\nstart=now()\nfor batch in loader:\n elapsed=now()-start\n if elapsed>10: break'),{'break:batch_or_loader_named':1})
    def test_nested_function_not_inherited(self):
        code='import time\nif time.time()>1:\n def f():\n  for fold in range(5):\n   break'
        self.assertEqual(self.scopes(code),{})
    def test_return_not_fold_break(self):
        self.assertEqual(self.scopes('import time\ndef f():\n for fold in range(5):\n  if time.time()>1: return'),{'function_return':1})
    def test_nonclock(self):
        self.assertEqual(self.scopes('for fold in range(5):\n if fold>2: break'),{})
    def test_while(self):
        self.assertEqual(self.scopes('import time as t\nwhile t.monotonic()<10: pass'),{'while_clock_test':1})
    def test_ast_normalization(self):
        a=classify('for x in range(5):\n pass')['ast_sha256']
        b=classify('#comment\nfor x in range(5):\n    pass')['ast_sha256']
        self.assertEqual(a,b)

if __name__=='__main__':unittest.main()
