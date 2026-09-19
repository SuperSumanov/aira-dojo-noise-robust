"""Explicit future release: ready-order source + fixed local reward transport.

Replaces the legacy paid/contextual scoring route, not the rank policy or the
model. Does not mutate any source, deploy, submit, or claim full-E2E readiness.
"""
import ast
from pathlib import Path
import forets_action_incumbent_patch_20260919 as base
from forets_ready_batch_patch_20260919 import once

MODULE='src/dojo/solvers/fore_ts/local_reward.py'

def build(sources):
    result=base.build(sources)
    runtime=result[base.RUNTIME].decode()
    runtime=once(runtime,'from dojo.solvers.fore_ts.contextual_rank import rank_pool\n',
        'from dojo.solvers.fore_ts.local_reward import rank_nodes, validate_config as validate_reward_config\n')
    runtime=once(runtime,'    bootstrap = initial(solver, path)\n',
        '    validate_reward_config(solver)  # Before any generation or external call.\n    bootstrap = initial(solver, path)\n')
    old='''                if solver.cfg.cheap_ranker != 'none':
                    from dojo.solvers.fore_ts.cheap_ranker import rank_codes
                    scores = rank_codes(solver, [node.code for node in nodes], root, solver.state.current_step)
                else:
                    from dojo.solvers.fore_ts.reference_context import reference_context
                    from dojo.solvers.fore_ts.wallclock import budget
                    references = reference_context(solver, parent, budget_spec=budget())
                    scores = await rank_pool(solver.task_name, [node.code for node in nodes],
                                             solver.state.current_step, root, reference_context=references)
'''
    runtime=once(runtime,old,'                scores = await rank_nodes(solver, nodes)\n')
    runtime=runtime.replace('no partial contextual-rank replay','no partial frozen-reward replay').replace('incomplete contextual rank','incomplete frozen reward')
    if 'contextual_rank' in runtime or 'rank_codes' in runtime or 'reference_context' in runtime:raise ValueError('legacy scoring path remains')
    result[base.RUNTIME]=runtime.encode()
    result[MODULE]=Path(__file__).with_name('forets_local_reward_transport_20260919.py').read_bytes().replace(b'\r\n',b'\n')
    for raw in result.values():ast.parse(raw)
    return result
