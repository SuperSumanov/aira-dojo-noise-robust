import ast
from pathlib import Path
import sys
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from forets_common_start_20260913 import initial,code_for,make_node,digest
import build_forets_common_start_20260913 as build


class CommonStartTests(unittest.TestCase):
    def test_only_first_step_and_known_root(self):
        s=NS(cfg=NS(common_start_protocol='rf_common_v1'),state=NS(current_step=1))
        self.assertTrue(initial(s,[NS(parents=[])]))
        s.state.current_step=2;self.assertFalse(initial(s,[NS(parents=[])]))
        s.state.current_step=1
        with self.assertRaises(ValueError):initial(s,[NS(parents=[1])])
        s.cfg.common_start_protocol='none';self.assertFalse(initial(s,[NS(parents=[])]))
    def test_baseline_does_not_call_llm_or_pick_old_winner(self):
        for t in ('leaf-classification','spaceship-titanic'):
            ast.parse(code_for(t))
            with patch('forets_common_start_20260913.canonical',return_value=code_for(t)):
                n=make_node(t,NS)
                self.assertEqual(digest(t),digest(t))
            self.assertEqual(n.parents,[]);self.assertEqual(n.operators_metrics,[])
            self.assertNotIn('readout',n.code)
            self.assertIn('random_state=0',n.code)
        with self.assertRaises(ValueError):code_for('unknown')
    def test_balanced_matrix_and_budget(self):
        rows=build.order();self.assertEqual(len(rows),8);self.assertEqual(len(set(rows)),8)
        for b in (1,2):self.assertEqual(sum(r[0]==b for r in rows),4)
        self.assertEqual({r[2] for r in rows},{28,29})
        self.assertEqual(4097577935+build.NEW_CAP,10**10)
        self.assertLess(4097577935+8*700000000,10**10)
    def test_all_source_changes_compile_and_baseline_branch_exists(self):
        src=build.changed_sources();self.assertEqual(len(src),4)
        for name,raw in src.items():compile(raw,name,'exec')
        batch=src['src/dojo/solvers/fore_ts/batch_runtime.py'].decode()
        self.assertIn('count = 1 if bootstrap',batch)
        self.assertIn('if bootstrap else await',batch)
        self.assertIn('digest as start_digest',batch)


if __name__=='__main__':unittest.main()
