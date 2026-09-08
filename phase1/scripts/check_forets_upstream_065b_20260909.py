"""Targeted real-source integration tests; all model/task responses are artificial.

Run with the aira Python environment, no credentials and CUDA_VISIBLE_DEVICES=''.
No provider call, real task execution, model load, or protected dataset access.
"""
import argparse
from contextlib import closing
import importlib.metadata
import io
import json
import logging
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
    parser.add_argument('--reproduce-before-fix', action='store_true')
    args = parser.parse_args()
    root = args.source_root.resolve()
    assert (root / 'src/dojo').is_dir()
    assert not args.output.exists(), 'do not overwrite a prior result'
    os.environ.update(CUDA_VISIBLE_DEVICES='', PYTHONDONTWRITEBYTECODE='1',
        HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', LITELLM_LOCAL_MODEL_COST_MAP='True',
        LOGGING_DIR=str(root / 'logs'), DEFAULT_SLURM_PARTITION='gpu_24h',
        DEFAULT_SLURM_ACCOUNT='gpu', DEFAULT_SLURM_QOS='gpu',
        MLE_BENCH_DATA_DIR='/research/d7/spc/yzyang4/mle-bench-data',
        SUPERIMAGE_DIR='/research/d7/spc/yzyang4/aira-dojo/build/superimage')
    os.chdir(root)
    sys.path.insert(0, str(root / 'src'))
    checks, evidence = [], {}
    with patch.object(socket.socket, 'connect', side_effect=AssertionError('network forbidden')):
        from dojo.config_dataclasses.solver.mcts import MCTSSolverConfig
        from dojo.core.solvers.llm_helpers.backends.lite_llm import FunctionSpec, LiteLLMClient
        from dojo.core.solvers.utils.journal import Journal
        from dojo.core.solvers.utils.metric import MetricValue
        from dojo.solvers.fore_ts.batch_runtime import expand_batch
        from dojo.solvers.fore_ts.candidate_ledger import CandidateLedger, LedgerError
        from dojo.solvers.fore_ts.fore_ts import ForeTS
        from dojo.solvers.mcts.mcts import MCTSNode
        from dojo.utils import code_parsing

        class State:
            def __init__(self): self.current_step = 0
            def state_dict(self): return vars(self).copy()

        def read_batch(folder):
            with closing(sqlite3.connect(folder / 'forets-candidates-private/batch-0.sqlite')) as db:
                return json.loads(db.execute('SELECT payload FROM snapshot').fetchone()[0])

        def retry_case(folder, policy, drift=False):
            solver = ForeTS.__new__(ForeTS)
            solver.cfg = NS(num_children=5, selector_seed=6, checkpoint_path=str(folder),
                selection_policy=policy, max_llm_call_retries=1, execution_timeout=300,
                step_limit=5, max_debug_depth=1)
            solver.state = State()
            solver.task_name, solver.task_desc, solver.data_preview = 'artificial', 'fixed', ''
            solver.root_node = MCTSNode(id='root', code='', plan='', ctime=0.)
            solver.journal = Journal([solver.root_node])
            solver.journal_for_unselected = Journal()
            solver.global_min_q_val, solver.global_max_q_val = 0., 1.
            solver.critic_top_k, solver.num_children_to_choose = 3, 2
            calls = dict(generate=0, critic=0, execute=0)
            async def generate(parent):
                slot = calls['generate']
                calls['generate'] += 1
                return MCTSNode(id=str(slot), code='print(' + str(slot) + ')', plan='', ctime=1.)
            async def critic(node):
                assert calls['generate'] == 5
                frozen = read_batch(folder)
                assert frozen['pool_sha256'] and len(frozen['candidates']) == 5
                calls['critic'] += 1
                return float(node.id)
            def execute(state, action):
                calls['execute'] += 1
                return state, {'execution_output': NS(exit_code=0, timed_out=False, exec_time=.01)}
            def analyze(node, eval_result):
                node.is_buggy, node.metric = False, MetricValue(.5, maximize=True)
            solver._draft = solver._improve = generate
            solver._query_critic = critic
            solver.parse_eval_result = analyze
            solver.log_journal = Mock()
            solver._backprop_step = Mock()
            solver.set_global_q_values = Mock()
            solver.logger = Mock()
            state = {'solver_interpreter': NS(timeout=300)}
            task = NS(step_task=execute)
            def run():
                return expand_batch(solver, [solver.root_node], state, task,
                    MCTSNode, lambda code: code, vars(solver.cfg))
            with patch.object(CandidateLedger, 'begin_execution', side_effect=RuntimeError('before intent')):
                try:
                    run()
                    raise AssertionError('expected artificial interruption')
                except RuntimeError as exc:
                    assert str(exc) == 'before intent'
            before = read_batch(folder)
            assert calls['execute'] == 0 and len(solver.journal.nodes) == 1
            assert len(solver.journal_for_unselected.nodes) == 3
            if drift:
                solver.journal_for_unselected.nodes[0].code = 'print(999)'
                try:
                    run()
                    raise AssertionError('changed export must fail')
                except LedgerError:
                    assert calls['execute'] == 0 and calls['generate'] == 5
                return {'drift_rejected_before_execution': True}
            run()
            saved = read_batch(folder)
            assert saved['selected'] == before['selected'] and saved['pool_sha256'] == before['pool_sha256']
            assert calls == dict(generate=5, critic=0 if policy == 'uniform_random' else 5, execute=2)
            unselected = solver.journal_for_unselected.nodes
            unique = {n.id for n in unselected}
            assert all(n.metric is None and n.is_buggy is None and not n.parents and not n.children
                       for n in unselected)
            assert unique.isdisjoint(n.id for n in solver.journal.nodes)
            assert len(solver.journal.nodes) == 3 and len(solver.root_node.children) == 2
            assert saved['phase'] == 'complete'
            solver.save_checkpoint()  # Actual ForeTS -> MCTS -> Solver export, no stub.
            exported = [json.loads(line) for line in (folder / 'journal_for_unselected.jsonl').read_text().splitlines()]
            executed = [json.loads(line) for line in (folder / 'journal.jsonl').read_text().splitlines()]
            assert [n['id'] for n in exported] == [n.id for n in unselected]
            assert len(executed) == 3 and all(n['metric'] is None for n in exported)
            duplicate = len(unselected) != len(unique)
            assert duplicate == args.reproduce_before_fix
            return dict(exported=len(unselected), unique=len(unique), duplicate=duplicate,
                        generated=calls['generate'], critic_calls=calls['critic'], artificial_executions=calls['execute'])

        with tempfile.TemporaryDirectory(prefix='forets-targeted-') as work:
            for policy in ('uniform_random', 'critic_topk_random'):
                evidence[policy] = retry_case(Path(work) / policy, policy)
                checks.append('retry_export_' + policy)
            if not args.reproduce_before_fix:
                evidence['drift'] = retry_case(Path(work) / 'drift', 'uniform_random', drift=True)
                checks.append('changed_export_rejected')

        code = 'print("x, }") # preserve exactly'
        payload = {'code': code}
        wrapped = '```json\n' + json.dumps(payload) + '\n```'
        logs = io.StringIO()
        handler = logging.StreamHandler(logs)
        old_level = code_parsing.log.level
        code_parsing.log.setLevel(logging.INFO)
        code_parsing.log.addHandler(handler)
        try:
            observed = code_parsing.parse_json_output(wrapped)
        finally:
            code_parsing.log.removeHandler(handler)
            code_parsing.log.setLevel(old_level)
        changed = observed != payload
        leaked = 'Original response:' in logs.getvalue() or code in logs.getvalue()
        evidence['json_before_or_after'] = dict(code_changed=changed, raw_response_logged=leaked)
        assert changed == args.reproduce_before_fix
        assert leaked == args.reproduce_before_fix
        checks.append('wrapped_json_preserves_string_and_no_raw_log')

        if not args.reproduce_before_fix:
            import jsonschema
            from hydra import compose, initialize_config_dir
            from hydra.utils import instantiate
            from omegaconf import OmegaConf
            from dojo.config_dataclasses.omegaconf.resolvers import register_new_resolvers
            register_new_resolvers()
            for seed in (6, 7):
                configs = []
                for policy in ('uniform_random', 'critic_topk_random'):
                    overrides = ['+_exp=mlebench/aira_forets_dsf_mle',
                        'benchmark.tasks=[leaf-classification,spaceship-titanic]', 'launcher=srun_pool',
                        'launcher.max_parallel=1', 'launcher.gpus_per_step=1', 'launcher.cpus_per_step=6',
                        'launcher.debug=false', 'launcher.max_retries=0', 'logger.use_wandb=false',
                        'solver.selection_policy=' + policy, 'solver.selector_seed=' + str(seed),
                        'solver.num_children=4', 'solver.critic_top_k=2', 'solver.num_children_to_choose=1',
                        'solver.execution_timeout=300', 'solver.time_limit_secs=1800', 'solver.step_limit=4',
                        'solver.max_debug_depth=1', 'solver.max_llm_call_retries=2', 'solver.critic_max_attempts=1',
                        'metadata.git_issue_id=e2e-development-draft', 'vars={metadata.seed:[6,7]}']
                    with initialize_config_dir(config_dir=str(root / 'src/dojo/configs'), version_base=None):
                        config = compose(config_name='default_runner', overrides=overrides)
                    obj = instantiate(config.solver)
                    obj.validate()
                    assert isinstance(obj, MCTSSolverConfig) and obj.uct_c == .25
                    configs.append(OmegaConf.to_container(config.solver, resolve=True))
                a, b = configs
                assert sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k)) == ['selection_policy']
                checks.append('actual_config_inheritance_and_fairness_seed_' + str(seed))

            client = LiteLLMClient.__new__(LiteLLMClient)
            spec = FunctionSpec('emit_code', {'type': 'object', 'properties': {'code': {'type': 'string'}},
                                'required': ['code'], 'additionalProperties': False}, 'artificial test')
            def parse(value, transport='json'):
                message = NS(content=value, tool_calls=[NS(function=NS(name='emit_code', arguments=value))])
                return client._parse_structured_output(NS(choices=[NS(message=message)]), spec, transport)
            assert parse(payload) == parse(json.dumps(payload)) == parse(wrapped) == payload
            assert parse(wrapped, 'tools') == payload
            # A real trailing comma may be repaired, but punctuation INSIDE code is immutable.
            comma = 'json ' + json.dumps(payload)[:-1] + ',}'
            assert parse(comma) == payload
            escaped = {'code': 'print("escaped \\\" , } and , ]")'}
            assert parse('```json\n' + json.dumps(escaped) + '\n```') == escaped
            checks.append('actual_backend_plain_fenced_tools_and_trailing_comma')
            for invalid in ('{}', '{"code":2}', '[]', 'not-json'):
                try:
                    parse(invalid)
                    raise AssertionError('schema-invalid result accepted')
                except (jsonschema.ValidationError, TypeError):
                    pass
            checks.append('actual_backend_schema_rejection')

    report = dict(status='REPRODUCED_BEFORE_FIX' if args.reproduce_before_fix else 'TARGETED_CPU_PASS',
        upstream_commit='065b0fbaa89e0eb663f2834ec768081f5d56394d', source_tree=args.source_tree,
        checks=checks, checks_passed=len(checks), evidence=evidence, model_loaded=False,
        gpu_requested=False, api_calls=0, protected_data_read=False, real_task_executed=False,
        versions={p: importlib.metadata.version(p) for p in ('hydra-core', 'litellm', 'torch')})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(json.dumps(report, sort_keys=True))


if __name__ == '__main__':
    main()
