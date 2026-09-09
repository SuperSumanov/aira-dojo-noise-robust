"""Verify only the new opt-in full-pool critic bypass using real batch runtime.

Generated candidates, critic values and task returns are synthetic. No GPU, API,
model, task program, or protected data. Counts are not measured runtime savings.
"""
import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import socket
import sqlite3
import sys
import tempfile
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--source-tree', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise RuntimeError('do not overwrite a prior receipt')
    os.environ.update(CUDA_VISIBLE_DEVICES='', PYTHONDONTWRITEBYTECODE='1',
        HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', LITELLM_LOCAL_MODEL_COST_MAP='True',
        LOGGING_DIR='/tmp', DEFAULT_SLURM_PARTITION='gpu_24h', DEFAULT_SLURM_ACCOUNT='gpu',
        DEFAULT_SLURM_QOS='gpu', MLE_BENCH_DATA_DIR='/unread', SUPERIMAGE_DIR='/unread')
    sys.path.insert(0, str(args.source_root/'src'))
    checks, trajectories = [], []
    with patch.object(socket.socket, 'connect', side_effect=AssertionError('network forbidden')):
        from dojo.core.solvers.utils.journal import Journal
        from dojo.core.solvers.utils.metric import MetricValue
        from dojo.solvers.fore_ts.batch_runtime import expand_batch
        from dojo.solvers.fore_ts.candidate_ledger import CandidateLedger, LedgerError
        from dojo.solvers.fore_ts.fore_ts import ForeTS
        from dojo.solvers.mcts.mcts import MCTSNode
        from dojo.config_dataclasses.solver.fore_ts import ForeTSSolverConfig
        assert ForeTSSolverConfig.__dataclass_fields__['skip_redundant_critic'].default is False
        checks.append('opt_in_default_false')

        def trajectory(folder, seed, enabled, policy='critic_topk_random'):
            solver = ForeTS.__new__(ForeTS)
            solver.cfg = NS(num_children=4, selector_seed=seed, checkpoint_path=str(folder),
                selection_policy=policy, skip_redundant_critic=enabled,
                max_llm_call_retries=1, execution_timeout=300, step_limit=4, max_debug_depth=1)
            solver.state = NS(current_step=0)
            solver.task_name, solver.task_desc, solver.data_preview = 'artificial', 'fixed', ''
            solver.root_node = MCTSNode(id='root', code='', plan='', ctime=0.)
            solver.journal, solver.journal_for_unselected = Journal([solver.root_node]), Journal()
            solver.global_min_q_val, solver.global_max_q_val = 0., 1.
            solver.critic_top_k, solver.num_children_to_choose = 2, 1
            calls = dict(generate=0, critic=0, execute=0)
            async def generate(parent):
                slot = calls['generate']
                calls['generate'] += 1
                return MCTSNode(id=str(slot), code='print('+str(slot)+')', plan='', ctime=1.)
            async def critic(node):
                if enabled and solver.remaining_steps <= 2:
                    raise AssertionError('unnecessary critic must not be called')
                calls['critic'] += 1
                return -float(node.id)  # No outcome used; fixed artificial ordering.
            def execute(state, code):
                calls['execute'] += 1
                return state, {'execution_output':NS(exit_code=0, timed_out=False, exec_time=.01)}
            def analyze(node, eval_result):
                node.is_buggy, node.metric = False, MetricValue(.5, maximize=True)
            solver._draft = solver._improve = generate
            solver._query_critic, solver.parse_eval_result = critic, analyze
            solver.log_journal = solver._backprop_step = solver.set_global_q_values = Mock()
            solver.logger = Mock()
            state, task = {'solver_interpreter':NS(timeout=300)}, NS(step_task=execute)
            selected, counts, bypassed = [], [], []
            for step in range(4):
                state = expand_batch(solver, [solver.root_node], state, task,
                    MCTSNode, lambda code:code, vars(solver.cfg))
                with closing(sqlite3.connect(folder/'forets-candidates-private'/('batch-'+str(step)+'.sqlite'))) as db:
                    saved = json.loads(db.execute('SELECT payload FROM snapshot').fetchone()[0])
                assert saved['phase'] == 'complete' and saved['binding']['selection_policy'] == policy
                counts.append(len(saved['candidates']))
                selected.append(saved['selected'])
                was_bypassed = saved['binding'].get('score_bypass') == 'full_pool_no_pruning'
                bypassed.append(was_bypassed)
                if was_bypassed:
                    assert all(c['score'] is None for c in saved['candidates'])
                    assert all(c['state'] in ('generated','completed') for c in saved['candidates'])
                assert len(saved['task_calls']) == 1
            assert counts == [4,3,2,1] and calls['generate'] == 10 and calls['execute'] == 4
            expected = (7 if enabled else 10) if policy == 'critic_topk_random' else 0
            assert calls['critic'] == expected
            assert bypassed == ([False,False,True,True] if enabled and policy=='critic_topk_random' else [False]*4)
            return dict(seed=seed, enabled=enabled, policy=policy, counts=counts,
                        selected_slots=selected, calls=calls, bypassed=bypassed)

        with tempfile.TemporaryDirectory(prefix='forets-nonpruning-', dir='/tmp') as tmp:
            root = Path(tmp)
            for seed in (6,7):
                off = trajectory(root/(str(seed)+'-off'), seed, False)
                on = trajectory(root/(str(seed)+'-on'), seed, True)
                assert off['selected_slots'] == on['selected_slots']
                trajectories.extend([off,on])
            checks.append('actual_batch_runtime_same_selected_slots_10_to_7_synthetic_critic_calls')
            a = trajectory(root/'random-off',6,False,'uniform_random')
            b = trajectory(root/'random-on',6,True,'uniform_random')
            assert a['selected_slots'] == b['selected_slots'] and a['calls'] == b['calls']
            checks.append('random_arm_unchanged')
            for number, extra in enumerate((
                {'score_bypass':'full_pool_no_pruning','critic_top_k':2},
                {'score_bypass':'full_pool_no_pruning','critic_top_k':True},
                {'score_bypass':'unknown','critic_top_k':4},
            )):
                try:
                    CandidateLedger(root/('invalid'+str(number))/'batch.sqlite',
                                    dict(selection_policy='critic_topk_random',**extra),4)
                    raise AssertionError('invalid bypass accepted')
                except LedgerError:
                    pass
            checks.append('pruning_pool_boolean_k_unknown_bypass_rejected')
            valid = dict(selection_policy='critic_topk_random', score_bypass='full_pool_no_pruning', critic_top_k=2)
            with CandidateLedger(root/'no-score'/'batch.sqlite',valid,2) as ledger:
                try:
                    ledger.begin_score(0)
                    raise AssertionError('scoring in bypass mode accepted')
                except LedgerError:
                    pass
            checks.append('bypass_forbids_scoring_no_fake_predictions')
    result = dict(status='TARGETED_PASS', source_tree=args.source_tree, checks=checks,
        artificial_trajectories=trajectories, synthetic_call_reduction_fraction=(10-7)/10,
        model_runtime_speedup=None, model_quality_effect=None,
        external_api_calls=0,gpu_jobs=0,real_task_programs_executed=0,protected_data_read=False,
        scope='fixed artificial candidates/returns; equal per-batch selection, not full stochastic e2e equivalence')
    with args.output.open('x') as file:
        json.dump(result,file,indent=2)
        file.write('\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
