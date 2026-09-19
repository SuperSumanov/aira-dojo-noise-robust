"""Exercise the exact production expansion body, with task/LLM transports mocked."""
import ast
import asyncio
import copy
import hashlib
import json
import random
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace, ModuleType
from unittest.mock import patch
from forets_cached_continuation_20260919 import make_cached_continuation


class Node:
    def __init__(self,name,parent=None):
        self.id=self.code=name;self.parents=[] if parent is None else [parent]
        self.children=set();self.is_buggy=None;self.metric=SimpleNamespace(value=None)
        self.operators_used=['draft'];self.step=None

class Journal:
    def __init__(self):self.nodes=[]
    def append(self,n):n.step=len(self.nodes);self.nodes.append(n)

class FakeBase:
    def __init__(self,cache_valid=True):
        self.cfg=SimpleNamespace(num_children=6,step_limit=30,time_limit_secs=3600)
        self.state=SimpleNamespace(current_step=1,running_time=0)
        self.critic_top_k=3;self.num_children_to_choose=2
        self.root=Node('root');self.journal=Journal();self.journal.append(self.root)
        self.journal_for_unselected=Journal();self.pool=[Node(f'n{i}',self.root) for i in range(6)]
        self.draft_count=0;self.cache_valid=cache_valid;self.debugged=[];self.backprops=[];self.analyzed=[]
        self.logger=SimpleNamespace(info=lambda *_:None,debug=lambda *_:None)
    @property
    def remaining_steps(self):return self.cfg.step_limit-self.state.current_step
    async def _draft(self,parent):
        i=self.draft_count;self.draft_count+=1;return self.pool[i],6-i
    def parse_eval_result(self,node,eval_result):
        self.analyzed.append(node.id)
        node.is_buggy=not (node.code.startswith('debug') or (node.code in ('n2','n3','n4','n5') and self.cache_valid))
        node.metric.value=None if node.is_buggy else .5
    def debug_cycle(self,state,task,node):
        self.debugged.append(node.id);fixed=Node('debug-'+node.id,node)
        state,result=task.step_task(state,fixed.code);self.parse_eval_result(fixed,result)
        self.journal.append(fixed);self.state.current_step+=1
        return state,[node,fixed],fixed.metric.value
    def log_journal(self):pass
    def _backprop_step(self,path,value_estimate):self.backprops.append([n.id for n in path])
    def set_global_q_values(self,value):pass


def load_pinned_expansion():
    source=Path(__file__).resolve().parent/'fixtures/forets_production_be9335348b.py'
    raw=source.read_bytes().replace(b'\r\n',b'\n')
    # Original file SHA edda5ca65dbe7abebbd7f55d4cc5284c8fc226c929fda08b66fd22ff9aec9bc4;
    # remote credential redaction normalized trailing whitespace/newline only.
    assert hashlib.sha256(raw).hexdigest()=='7e4bb110eae6ab86007975bc167a218402c83d1d373aeff1e9a298af14c3a00a'
    tree=ast.parse(raw);cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='ForeTS')
    fn=copy.deepcopy(next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='_expand_leaf_and_backprop'))
    fn.returns=None
    for arg in fn.args.args:arg.annotation=None
    module=ast.fix_missing_locations(ast.Module(body=[fn],type_ignores=[]))
    namespace=dict(asyncio=asyncio,random=SimpleNamespace(sample=lambda seq,k:list(seq[:k])),extract_code=lambda text:text)
    exec(compile(module,'pinned-production-expansion','exec'),namespace)
    FakeBase._expand_leaf_and_backprop=namespace[fn.name]


class Task:
    def __init__(self):self.executed=[]
    def step_task(self,state,code):self.executed.append(code);return state+1,None


class ContinuationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):load_pinned_expansion()
    def setUp(self):
        response=ModuleType('dojo.core.solvers.utils.response');response.extract_code=lambda x:x
        self.patch=patch.dict(sys.modules,{'dojo.core.solvers.utils.response':response});self.patch.start()
    def tearDown(self):self.patch.stop()
    def run_solver(self,enabled=True,cache_valid=True,seed=7):
        solver=make_cached_continuation(FakeBase,enabled=enabled,seed=seed)(cache_valid)
        task=Task();state=solver._expand_leaf_and_backprop([solver.root],0,task)
        return solver,task,state
    def test_off_is_original_class_and_debugs_both_failures(self):
        self.assertIs(make_cached_continuation(FakeBase,enabled=False,seed=7),FakeBase)
        solver,task,state=self.run_solver(False)
        self.assertEqual(task.executed,['n0','debug-n0','n1','debug-n1']);self.assertEqual(state,4)
    def test_success_returns_sibling_not_failed_node_path(self):
        solver,task,state=self.run_solver()
        cache=task.executed[1];self.assertIn(cache,['n2','n3','n4','n5'])
        self.assertEqual(solver.debugged,['n1']);self.assertEqual(solver.backprops[0],['root',cache])
        self.assertNotIn('n0',solver.backprops[0]);self.assertEqual(state,4)
    def test_failed_cache_falls_back_only_once_per_pool(self):
        solver,task,state=self.run_solver(cache_valid=False)
        self.assertEqual(solver.debugged,['n0','n1']);self.assertEqual(len(task.executed),5)
        self.assertEqual(task.executed[2],'debug-n0');self.assertEqual(state,5)
    def test_no_double_journal_and_normal_analysis(self):
        solver,task,state=self.run_solver();ids={n.id for n in solver.journal.nodes}
        self.assertFalse(ids & {n.id for n in solver.journal_for_unselected.nodes})
        self.assertEqual(len(solver.journal_for_unselected.nodes),3)
        self.assertEqual(solver.analyzed,task.executed);self.assertEqual(solver.state.current_step,len(solver.journal.nodes))
    def test_global_rng_untouched_by_cache_draw(self):
        old=random.getstate();self.run_solver();self.assertEqual(old,random.getstate())
    def test_reproducible_at_expansion_boundary(self):
        a=self.run_solver()[1].executed;b=self.run_solver()[1].executed;self.assertEqual(a,b)
    def test_old_pool_cannot_enter_cache(self):
        solver=make_cached_continuation(FakeBase,enabled=True,seed=7)();solver.journal_for_unselected.append(Node('old',solver.root))
        task=Task();solver._expand_leaf_and_backprop([solver.root],0,task);self.assertNotIn('old',task.executed)
    def test_budget_reserves_fallback_step(self):
        solver=make_cached_continuation(FakeBase,enabled=True,seed=7)();solver.cfg.step_limit=3
        task=Task();solver._expand_leaf_and_backprop([solver.root],0,task)
        self.assertFalse(set(task.executed) & {'n2','n3','n4','n5'})
    def test_wall_clock_not_stale_running_time(self):
        with patch('forets_cached_continuation_20260919.monotonic',side_effect=[0,3601]):
            solver,task,state=self.run_solver()
        self.assertEqual(task.executed,['n0','debug-n0','n1','debug-n1'])
    def test_context_cleared_on_exception(self):
        solver=make_cached_continuation(FakeBase,enabled=True,seed=7)();task=Task()
        task.step_task=lambda *_:(_ for _ in ()).throw(RuntimeError('transport'))
        with self.assertRaises(RuntimeError):solver._expand_leaf_and_backprop([solver.root],0,task)
        self.assertIsNone(solver._cached_continuation_context)

if __name__=='__main__':unittest.main()
