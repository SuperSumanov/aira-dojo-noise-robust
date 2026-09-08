"""ForeTS batch integration, pre-execution recovery only; no result labels here.

Intended for an isolated upstream patch, NOT the active producer. Operator-internal
retries/cost traces, rendered prompt isolation and full search recovery remain open.
"""
import asyncio
import random
from pathlib import Path

from phase1.forets_candidate_ledger_20260908 import CandidateLedger, LedgerError, digest


def expand_batch(solver, path, state, task, node_type, extract_code, config_snapshot):
    count = min(solver.cfg.num_children, solver.remaining_steps)
    if count <= 0:
        return state
    if type(solver.cfg.selector_seed) is not int:
        raise LedgerError('explicit independent selector seed required')
    parent = path[-1]
    # Bind the actual in-memory boundary, not merely its step or parent identity.
    boundary = dict(
        task=solver.task_name, task_description=solver.task_desc,
        config=config_snapshot, state=vars(solver.state), preview=solver.data_preview,
        journal=solver.journal.node_list(), path=[n.id for n in path],
        tree=[dict(id=n.id, parents=[p.id for p in n.parents],
                   children=sorted(c.id for c in n.children),
                   explore_count=n.explore_count, node_value=n.node_value)
              for n in solver.journal.nodes],
        global_q=[solver.global_min_q_val, solver.global_max_q_val],
    )
    binding = dict(schema=1, boundary_sha256=digest(boundary), parent_id=parent.id,
                   task=solver.task_name, step=solver.state.current_step)
    root = Path(solver.cfg.checkpoint_path)
    root.mkdir(parents=True, exist_ok=True)
    file = root / 'forets-candidates-private' / f'batch-{solver.state.current_step}.sqlite'
    with CandidateLedger(file, binding, count) as ledger:
        ledger.ensure_preexecution()  # Check EVERY slot before any possible paid call.

        async def obtain(slot):
            c = ledger.data['candidates'][slot]
            if c['state'] == 'pending':
                ledger.begin_generation(slot)
                node = await (solver._draft(parent) if not parent.parents else solver._improve(parent))
                if node.parents or node.children or node.metric is not None or node.is_buggy is not None:
                    raise LedgerError('generated candidate attached or labeled before execution')
                ledger.generated(slot, {k: getattr(node, k) for k in
                    ('id', 'ctime', 'code', 'plan', 'operators_used', 'operators_metrics')})
            else:
                node = node_type(**c['node'], parents=[])
            if c['state'] == 'generated':
                ledger.begin_score(slot)
                ledger.scored(slot, await solver._query_critic(node))
            return node

        async def gather():
            return await asyncio.gather(*(obtain(i) for i in range(count)))

        nodes = asyncio.run(gather())
        if ledger.data['selected'] is None:
            top = sorted(range(count), key=lambda i: ledger.data['candidates'][i]['score'],
                         reverse=True)[:solver.critic_top_k]
            # Batch-local selector stream: generation/global RNG calls cannot advance it.
            # Output paths / critic arm settings bind recovery, but must not seed selection.
            rng = random.Random(digest(dict(domain='forets-selector-v1',
                                           seed=solver.cfg.selector_seed,
                                           task=solver.task_name, step=solver.state.current_step)))
            ledger.select(rng.sample(top, min(solver.num_children_to_choose, len(top))))

        for slot in ledger.data['selected']:
            if solver.remaining_steps <= 0:
                break
            child = nodes[slot]
            ledger.begin_execution(slot)  # Durable intent BEFORE external effects.
            state, eval_result = task.step_task(state, extract_code(child.code))
            solver.parse_eval_result(node=child, eval_result=eval_result)
            # Only executed and parsed nodes enter memory/UCT. Never synthesize a score.
            child.parents = [parent]
            parent.children.add(child)
            solver.journal.append(child)
            solver.log_journal()
            solver.state.current_step += 1
            if not child.is_buggy:
                solver._backprop_step(path=path + [child], value_estimate=child.metric.value)
                solver.set_global_q_values(child.metric.value)
            else:
                state, debug_path, fixed_metric = solver.debug_cycle(state, task, child)
                if fixed_metric is not None:
                    solver._backprop_step(path=path + debug_path, value_estimate=fixed_metric)
                    solver.set_global_q_values(fixed_metric)
            ledger.execution_completed(slot)
        ledger.finish()
    return state
