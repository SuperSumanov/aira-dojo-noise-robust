import sys,unittest
from types import ModuleType
from unittest.mock import patch
from forets_common_admission_20260919 import make_comparable_continuation
from test_forets_cached_continuation_20260919 import FakeBase,Task,Node,load_pinned_expansion

class AdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):load_pinned_expansion()
    def setUp(self):
        module=ModuleType('dojo.core.solvers.utils.response');module.extract_code=lambda x:x
        self.patch=patch.dict(sys.modules,{'dojo.core.solvers.utils.response':module});self.patch.start()
        self.addCleanup(self.patch.stop)
    def make(self,enabled,limit=30,clock=lambda:0):
        solver=make_comparable_continuation(FakeBase,cache_enabled=enabled,seed=7,clock=clock)()
        solver.cfg.step_limit=limit
        return solver
    def test_both_arms_never_admit_extra_execution_at_step_boundary(self):
        for enabled in (False,True):
            for limit in range(1,11):
                solver=self.make(enabled,limit);task=Task()
                result=solver._expand_leaf_and_backprop([solver.root],0,task)
                self.assertLessEqual(len(task.executed),limit-1)
                self.assertEqual(solver.state.current_step,1+len(task.executed))
                self.assertEqual(result,len(task.executed))
    def test_one_remaining_step_is_one_candidate_not_sample_failure(self):
        for enabled in (False,True):
            solver=self.make(enabled,2);task=Task()
            solver._expand_leaf_and_backprop([solver.root],0,task)
            self.assertEqual(task.executed,['n0']);self.assertEqual(solver.num_children_to_choose,2)
            self.assertEqual(solver.debugged,[])
    def test_deadline_after_first_execution_blocks_debug_and_second_child(self):
        for enabled in (False,True):
            ticks=[0];solver=self.make(enabled,clock=lambda:ticks[0]);solver.cfg.time_limit_secs=5
            task=Task();old=task.step_task
            def execute(state,code):
                result=old(state,code);ticks[0]=6;return result
            task.step_task=execute
            result=solver._expand_leaf_and_backprop([solver.root],0,task)
            self.assertEqual(task.executed,['n0']);self.assertEqual(solver.debugged,[]);self.assertEqual(result,1)
    def test_expired_before_entry_generates_nothing(self):
        for enabled in (False,True):
            solver=self.make(enabled);solver.state.running_time=3600;task=Task()
            self.assertEqual(solver._expand_leaf_and_backprop([solver.root],7,task),7)
            self.assertEqual(solver.draft_count,0);self.assertEqual(task.executed,[])
    def test_successful_cache_keeps_sibling_credit(self):
        solver=self.make(True);task=Task();solver._expand_leaf_and_backprop([solver.root],0,task)
        cache=task.executed[1]
        self.assertEqual(solver.backprops[0],['root',cache]);self.assertNotIn('n0',solver.backprops[0])
    def test_original_nonbudget_error_is_not_swallowed(self):
        solver=self.make(True);task=Task()
        task.step_task=lambda *_:(_ for _ in ()).throw(ValueError('real error'))
        with self.assertRaisesRegex(ValueError,'real error'):solver._expand_leaf_and_backprop([solver.root],0,task)
        self.assertIsNone(solver._common_admission_context);self.assertIsNone(solver._cached_continuation_context)
    def test_failed_cache_cannot_generate_debug_after_deadline(self):
        class GeneratesRepair(FakeBase):
            def _debug(self,node):
                self.debugged.append(node.id);return Node('debug-'+node.id,node)
            def debug_cycle(self,state,task,node):
                fixed=self._debug(node)
                state,result=task.step_task(state,fixed.code);self.parse_eval_result(fixed,result)
                self.journal.append(fixed);self.state.current_step+=1
                return state,[node,fixed],fixed.metric.value
        ticks=[0]
        solver=make_comparable_continuation(GeneratesRepair,cache_enabled=True,seed=7,clock=lambda:ticks[0])(False)
        solver.cfg.time_limit_secs=5
        task=Task();old=task.step_task
        def execute(state,code):
            result=old(state,code)
            if len(task.executed)==2:ticks[0]=6
            return result
        task.step_task=execute
        result=solver._expand_leaf_and_backprop([solver.root],0,task)
        self.assertEqual(len(task.executed),2);self.assertEqual(solver.debugged,[]);self.assertEqual(result,2)

    def outer(self,enabled,limit,clock=lambda:0):
        class OuterBase(FakeBase):
            search_name='ForeTS'
            def create_root_node(self):self.root_calls+=1
            def step(self,task,state):
                self.step_calls+=1
                if self.step_calls>2:raise AssertionError('outer loop did not stop')
                return self._expand_leaf_and_backprop([self.root],state,task)
            def save_checkpoint(self):self.saved+=1
        solver=make_comparable_continuation(OuterBase,cache_enabled=enabled,seed=7,clock=clock)()
        solver.cfg.step_limit=limit;solver.root_calls=solver.step_calls=solver.saved=0
        solver.journal.get_best_node=lambda:next((node for node in solver.journal.nodes if node.metric.value is not None),None)
        module=ModuleType('dojo.core.solvers.utils.search_exporter');module.export_search_results=lambda *args:None
        temporary=patch.dict(sys.modules,{'dojo.core.solvers.utils.search_exporter':module});temporary.start();self.addCleanup(temporary.stop)
        return solver

    def test_whole_search_stops_at_exact_budget_without_busy_loop(self):
        for enabled in (False,True):
            solver=self.outer(enabled,2);task=Task()
            result=solver(task,0)
            self.assertEqual(result,(1,None,None));self.assertEqual(solver.step_calls,1)
            self.assertEqual(solver.saved,1);self.assertEqual(solver.state.current_step,2)

    def test_whole_search_with_no_remaining_actions_never_enters_expansion(self):
        for enabled in (False,True):
            solver=self.outer(enabled,1);task=Task()
            self.assertEqual(solver(task,8),(8,None,None))
            self.assertEqual(solver.step_calls,0);self.assertEqual(task.executed,[])

    def test_whole_search_records_last_state_and_elapsed_cost_at_deadline(self):
        for enabled in (False,True):
            ticks=[0];solver=self.outer(enabled,30,clock=lambda:ticks[0]);solver.cfg.time_limit_secs=5
            task=Task();original=task.step_task
            def run(state,code):
                result=original(state,code);ticks[0]=6;return result
            task.step_task=run
            self.assertEqual(solver(task,0),(1,None,None))
            self.assertEqual(solver.state.running_time,6);self.assertEqual(solver.saved,1)

    def test_whole_search_keeps_original_best_node_contract(self):
        for enabled in (False,True):
            solver=self.outer(enabled,6);task=Task();state,code,node=solver(task,0)
            self.assertEqual(state,len(task.executed));self.assertIs(node,solver.journal.get_best_node())
            self.assertEqual(code,node.code);self.assertLessEqual(solver.state.current_step,6)

    def test_whole_search_no_progress_is_an_error_not_spin(self):
        solver=self.outer(True,6);solver.step=lambda task,state:state
        with self.assertRaisesRegex(RuntimeError,'no progress'):solver(Task(),0)

if __name__=='__main__':unittest.main()
