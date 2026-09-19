"""Actual native debug-loop body plus actual ForeTS expansion; no model calls."""
import ast,copy,subprocess,sys,unittest
from types import ModuleType
from unittest.mock import patch
from test_forets_cached_continuation_20260919 import FakeBase,Node,Task,load_pinned_expansion
from forets_common_admission_20260919 import make_comparable_continuation
from verify_comparison_native_acceptance_20260919 import COMMIT,SOURCE,SECRET

def native_loop():
    raw=subprocess.check_output(['git','show',COMMIT+':'+SOURCE],timeout=30)
    if SECRET.search(raw):raise ValueError('source credential shape')
    cls=next(n for n in ast.parse(raw).body if isinstance(n,ast.ClassDef) and n.name=='MCTS')
    fn=copy.deepcopy(next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='debug_cycle'))
    fn.returns=None
    for arg in fn.args.args:arg.annotation=None
    namespace=dict(extract_code=lambda code:code)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fn],type_ignores=[])),COMMIT+':debug_cycle','exec'),namespace)
    return namespace['debug_cycle']

class NativeDebugTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):load_pinned_expansion();cls.native_loop=staticmethod(native_loop())
    def setUp(self):
        response=ModuleType('dojo.core.solvers.utils.response');response.extract_code=lambda x:x
        temporary=patch.dict(sys.modules,{'dojo.core.solvers.utils.response':response});temporary.start();self.addCleanup(temporary.stop)
    def make(self,enabled,cache_valid=True,clock=lambda:0):
        native=self.native_loop
        class ActualDebugBase(FakeBase):
            debug_cycle=native
            def __init__(self):
                super().__init__(cache_valid)
                self.cfg.max_debug_depth=2;self.cfg.max_debug_time=100
                for node in self.pool+[self.root]:node.exec_time=0;node.debug_depth=0
            def _debug(self,parent):
                self.debugged.append(parent.id)
                child=Node('debug-'+parent.id,parent);child.exec_time=0;child.debug_depth=parent.debug_depth+1
                return child
            def parse_eval_result(self,node,eval_result):
                super().parse_eval_result(node,eval_result)
                if node.operators_used==['draft'] and node.id.startswith('debug-') and node.debug_depth==1:
                    node.is_buggy=True;node.metric.value=None
        return make_comparable_continuation(ActualDebugBase,cache_enabled=enabled,seed=7,clock=clock)()
    def test_baseline_really_runs_two_native_repairs_per_failure(self):
        solver=self.make(False);task=Task();solver._expand_leaf_and_backprop([solver.root],0,task)
        self.assertEqual(task.executed,['n0','debug-n0','debug-debug-n0','n1','debug-n1','debug-debug-n1'])
        self.assertEqual(solver.backprops[0],['root','n0','debug-n0','debug-debug-n0'])
    def test_cache_success_skips_first_native_chain_and_credits_sibling(self):
        solver=self.make(True);task=Task();solver._expand_leaf_and_backprop([solver.root],0,task)
        cached=task.executed[1]
        self.assertEqual(solver.backprops[0],['root',cached]);self.assertEqual(solver.debugged,['n1','debug-n1'])
    def test_cache_failure_retains_full_native_chain(self):
        solver=self.make(True,False);task=Task();solver._expand_leaf_and_backprop([solver.root],0,task)
        self.assertEqual(task.executed[2:4],['debug-n0','debug-debug-n0'])
        self.assertEqual(solver.backprops[0],['root','n0','debug-n0','debug-debug-n0'])
    def test_native_chain_honors_common_step_cap(self):
        for enabled in (False,True):
            for limit in range(2,9):
                solver=self.make(enabled,False);solver.cfg.step_limit=limit;task=Task()
                solver._expand_leaf_and_backprop([solver.root],0,task)
                self.assertEqual(solver.state.current_step,1+len(task.executed))
                self.assertLessEqual(solver.state.current_step,limit)
    def test_deadline_blocks_second_real_native_debug_call(self):
        ticks=[0];solver=self.make(False,clock=lambda:ticks[0]);solver.cfg.time_limit_secs=5
        task=Task();original=task.step_task
        def execute(state,code):
            result=original(state,code)
            if len(task.executed)==2:ticks[0]=6
            return result
        task.step_task=execute
        self.assertEqual(solver._expand_leaf_and_backprop([solver.root],0,task),2)
        self.assertEqual(solver.debugged,['n0']);self.assertEqual(task.executed,['n0','debug-n0'])

if __name__=='__main__':unittest.main()
