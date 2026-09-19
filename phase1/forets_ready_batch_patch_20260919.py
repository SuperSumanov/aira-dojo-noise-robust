"""Undeployed, default-off selected-batch ordering on exact production source.

No new generation, selection, reward, operator, or task-budget rule. This is a
mechanism ablation, not a novelty claim. Returns bytes; never edits a source tree.
"""
import ast,hashlib,textwrap

SOLVER_SHA='7e4bb110eae6ab86007975bc167a218402c83d1d373aeff1e9a298af14c3a00a'
CONFIG_SHA='6189e87b9734e7a10bd6ceb76719314f4eb392d84f5d617431d90adef40aa63e'

READY_METHOD='''
def _execute_ready_chosen_batch(self, path, state, task, chosen_child_nodes):
    pending_debug = []
    for child_node in chosen_child_nodes:
        self.logger.debug(f"Step {self.state.current_step}: Executing generated code")
        state, eval_result = task.step_task(state, extract_code(child_node.code))
        self.parse_eval_result(node=child_node, eval_result=eval_result)
        self.journal.append(child_node)
        self.log_journal()
        self.state.current_step += 1
        if not child_node.is_buggy:
            self._backprop_step(path=path + [child_node], value_estimate=child_node.metric.value)
            self.set_global_q_values(child_node.metric.value)
        else:
            pending_debug.append(child_node)
        # Preserve the original > comparison, not an unrelated step-limit fix.
        if self.state.current_step > self.cfg.step_limit:
            self.logger.info(f"Step limit reached: {self.state.current_step} steps")
            break
    for child_node in pending_debug:
        if self.state.current_step > self.cfg.step_limit:
            break
        state, debug_path, fixed_metric = self.debug_cycle(state, task, child_node)
        if fixed_metric is not None:
            self._backprop_step(path=path + debug_path, value_estimate=fixed_metric)
            self.set_global_q_values(fixed_metric)
    return state
'''

def once(text,old,new):
    if text.count(old)!=1:raise ValueError('exact source anchor drift')
    return text.replace(old,new,1)

def patched_sources(config,solver):
    config=config.replace('\r\n','\n');solver=solver.replace('\r\n','\n')
    for text,expected in ((config,CONFIG_SHA),(solver,SOLVER_SHA)):
        if hashlib.sha256(text.encode()).hexdigest()!=expected:raise ValueError('unreviewed production source')
    config=once(config,'    def validate(self) -> None:\n',
        '    chosen_batch_order: str = "native"\n\n    def validate(self) -> None:\n')
    config=once(config,'        super().validate()\n',
        '        super().validate()\n        if self.chosen_batch_order not in ("native", "ready_first"):\n            raise ValueError("chosen batch order")\n')
    solver=once(solver,'        async def _gather():\n',
        '        batch_order = getattr(self.cfg, "chosen_batch_order", "native")\n'
        '        if batch_order not in ("native", "ready_first"):\n'
        '            raise ValueError("chosen batch order")\n'
        '        async def _gather():\n')
    solver=once(solver,'        for i in range(self.num_children_to_choose):\n',
        '        if batch_order == "ready_first":\n'
        '            return self._execute_ready_chosen_batch(path, state, task, chosen_child_nodes)\n\n'
        '        for i in range(self.num_children_to_choose):\n')
    solver=once(solver,'    async def _query_critic(',
        textwrap.indent(READY_METHOD.strip()+'\n\n','    ')+'    async def _query_critic(')
    for text in (config,solver):ast.parse(text)
    return {'src/dojo/config_dataclasses/solver/fore_ts.py':config.encode(),
            'src/dojo/solvers/fore_ts/fore_ts.py':solver.encode()}
