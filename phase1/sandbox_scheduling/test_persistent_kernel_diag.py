import ast
from pathlib import Path
import unittest
from persistent_kernel_diag_20261011 import schedule, premature_exit


class PersistentPlan(unittest.TestCase):
    def test_fast_final_host_is_not_failure(self):
        self.assertFalse(premature_exit([0,None], [True,False]))
        self.assertTrue(premature_exit([0,None], [False,False]))
        self.assertTrue(premature_exit([1,None], [True,False]))

    def test_full_denominator_and_fixed_hosts(self):
        rows=schedule();self.assertEqual(len(rows),192)
        for slot in range(6):self.assertEqual([r['round'] for r in rows if r['slot']==slot],list(range(32)))

    def test_restore_shim_and_no_forced_gc(self):
        text=Path(__file__).with_name('persistent_kernel_diag_20261011.py').read_text()
        tree=ast.parse(text)
        slot=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='slot')
        guarded=[n for n in ast.walk(slot) if isinstance(n,ast.Try)]
        self.assertTrue(any('_build_singularity_command = build' in ast.unparse(n) for t in guarded for n in t.finalbody))
        self.assertNotIn('gc.collect()',text)


if __name__=='__main__':unittest.main()
