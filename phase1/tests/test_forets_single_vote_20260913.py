import importlib.util
from pathlib import Path
import sys
import unittest
P=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(P))
from forets_parallel_scope_gate_20260913 import validate
import build_forets_single_vote_20260913 as build

class SingleVoteTests(unittest.TestCase):
    def test_fixed_balanced_matrix(self):
        rows=build.order();self.assertEqual(len(rows),8)
        self.assertEqual(len(set(rows)),8)
        for block,seed in enumerate((26,27),1):
            rs=[r for r in rows if r[0]==block]
            self.assertEqual(len(rs),4);self.assertEqual({r[2] for r in rs},{seed})
            self.assertEqual({r[3] for r in rs},{'uniform_random','critic_topk_random'})
        self.assertNotEqual(rows[0][3],rows[4][3])
    def test_budget_includes_prior_liability_and_concurrent_reserve(self):
        self.assertEqual(build.NEW_CAP+build.PRIOR_HELD,10**10)
        self.assertLess(build.PRIOR_HELD+8*700000000,10**10)
    def test_unknown_gate_distinguishes_owned_inflight_from_finished_failure(self):
        old=[('old1','old',700000000,None,'unresolved',0),('old2','old',700000000,None,'unresolved',0)]
        live=('new','run',700000000,None,'unresolved',900)
        validate({'stopped':False},old+[live],{'run'},{'run'},now=1000)
        for active,now in [(set(),1000),({'run'},1035),({'run'},899)]:
            with self.assertRaises(RuntimeError):validate({'stopped':False},old+[live],{'run'},active,now=now)
        with self.assertRaises(RuntimeError):validate({'stopped':True},old,{'run'},set(),now=1000)
        with self.assertRaises(RuntimeError):validate({'stopped':False},old[:1],{'run'},set(),now=1000)
    def test_common_defaults_retained(self):
        import inspect
        self.assertEqual(inspect.signature(build.common.build).parameters['block_minutes'].default,180)
        self.assertEqual(inspect.signature(build.common.build).parameters['block_ids'].default,(1,))

if __name__=='__main__':unittest.main()
