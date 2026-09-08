"""New run-budget + four-operator integration only; no model/task/API access."""
import argparse
import asyncio
from contextlib import closing
import hashlib
import importlib.metadata
import io
import json
import logging
import multiprocessing
import os
from pathlib import Path
import socket
import sqlite3
import sys
import tempfile
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch
import uuid


def attempt_from_process(spec):
    from dojo.core.solvers.llm_helpers.backends.run_budget import reserve, RunBudgetError
    try:
        reserve(spec, uuid.uuid4().hex, 32)
        return True
    except RunBudgetError:
        return False


def count(path):
    with closing(sqlite3.connect(path)) as db:
        return db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dojo-root', type=Path, required=True)
    parser.add_argument('--plan-root', type=Path, required=True)
    parser.add_argument('--source-tree', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists()
    os.environ.update(CUDA_VISIBLE_DEVICES='', LITELLM_LOCAL_MODEL_COST_MAP='True',
        PYTHONDONTWRITEBYTECODE='1', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
        LOGGING_DIR='/tmp', DEFAULT_SLURM_PARTITION='gpu_24h', DEFAULT_SLURM_ACCOUNT='gpu',
        DEFAULT_SLURM_QOS='gpu', MLE_BENCH_DATA_DIR='/unread', SUPERIMAGE_DIR='/unread')
    # Never source .env. Client creation uses an explicit empty key in this test.
    for key in tuple(os.environ):
        if key.startswith('PRIMARY_KEY'):
            del os.environ[key]
    os.chdir(args.dojo_root)
    sys.path[:0] = [str(args.dojo_root / 'src'), str(args.plan_root)]
    checks, evidence = [], {}
    with tempfile.TemporaryDirectory(prefix='forets-run-budget-', dir='/tmp') as tmp:
        root = Path(tmp)
        with patch.object(socket.socket, 'connect', side_effect=AssertionError('network forbidden')):
            from dojo.core.solvers.llm_helpers.backends import lite_llm as backend
            from dojo.core.solvers.llm_helpers.backends import run_budget
            from dojo.core.solvers.llm_helpers.generic_llm import GenericLLM
            from dojo.config_dataclasses.omegaconf.resolvers import register_new_resolvers
            from forets_pilot_plan import overrides, run_order, OPERATORS
            from hydra import compose, initialize_config_dir
            from hydra.utils import instantiate
            from omegaconf import OmegaConf
            register_new_resolvers()

            configs, hashes = {}, []
            order = list(run_order())
            assert len(order) == 8 and len(set(order)) == 8
            for task, seed, policy in order:
                with initialize_config_dir(config_dir=str(args.dojo_root / 'src/dojo/configs'), version_base=None):
                    config = compose(config_name='default_runner', overrides=overrides(task, seed, policy,
                        max_output_tokens=8192, request_timeout_seconds=120))
                solver = instantiate(config.solver)
                solver.validate()
                plain = OmegaConf.to_container(config, resolve=True)
                for op in OPERATORS:
                    kwargs = plain['solver']['operators'][op]['llm']['generation_kwargs']
                    assert kwargs['bounded_transport'] is True and kwargs['bounded_run_budget_required'] is True
                    assert kwargs['max_tokens'] == 8192 and kwargs['bounded_request_timeout_seconds'] == 120
                assert plain['metadata']['seed'] == seed and plain['vars']['metadata.seed'] == [seed]
                configs[task, seed, policy] = (solver, plain)
                normalized = json.loads(json.dumps(plain))
                del normalized['solver']['selection_policy']
                hashes.append(hashlib.sha256(json.dumps(normalized, sort_keys=True).encode()).hexdigest())
            for i in range(0, 8, 2):
                assert hashes[i] == hashes[i+1], 'whole config differs beyond selector'
            checks.append('eight_actual_hydra_configs_four_paired_hashes_only_selector_differs')
            evidence['paired_normalized_config_sha256'] = hashes[::2]
            evidence['run_order'] = order

            policy_cfg = configs[order[0]][0]
            operators = {op: GenericLLM(policy_cfg.operators[op]) for op in OPERATORS}
            assert all(not op.client.api_key for op in operators.values())
            response = NS(choices=[NS(message=NS(content='artificial response'))],
                          to_dict=lambda: {'usage': {'prompt_tokens': 2, 'completion_tokens': 3}})
            async def query(op):
                return await operators[op](messages=[{'role': 'user', 'content': 'artificial input'}])
            ledger = root / 'operators.sqlite'
            run_budget.initialize(ledger, 4, 8192)
            os.environ['FORETS_RUN_BUDGET_PATH'] = str(ledger)
            mocked = AsyncMock(return_value=response)
            with patch.object(backend, 'completion_fn', mocked):
                for op in OPERATORS:
                    _, info = asyncio.run(query(op))
                    assert info['usage']['cost'] is None
                assert mocked.await_count == 4 and count(ledger) == 4
                for op in OPERATORS:
                    try:
                        asyncio.run(query(op))
                        raise AssertionError('run cap ignored')
                    except run_budget.RunBudgetError:
                        pass
                assert mocked.await_count == 4
            checks.append('real_genericllm_four_operators_share_cap_and_block_before_fifth_dispatch')

            for label, env, kwargs in (
                ('missing_budget', {}, dict(bounded_transport=True, bounded_run_budget_required=True, max_tokens=32)),
                ('unbounded_bypass', {'FORETS_RUN_BUDGET_PATH': str(ledger)}, dict(max_tokens=32)),
                ('missing_database', {'FORETS_RUN_BUDGET_PATH': str(root/'absent.sqlite')},
                 dict(bounded_transport=True, max_tokens=32)),
                ('output_exceeds_policy', {'FORETS_RUN_BUDGET_PATH': str(ledger)},
                 dict(bounded_transport=True, max_tokens=8193))):
                with patch.dict(os.environ, env, clear=True), patch.object(backend, 'completion_fn', mocked):
                    try:
                        asyncio.run(operators['draft'].client.query([{'role':'user','content':'artificial'}], **kwargs))
                        raise AssertionError('guard ignored')
                    except (ValueError, run_budget.RunBudgetError):
                        pass
                    assert mocked.await_count == 4
            assert not (root/'absent.sqlite').exists()
            checks.append('missing_or_bypassed_budget_and_output_limit_rejected_before_dispatch')

            failures = root / 'failures.sqlite'
            run_budget.initialize(failures, 3, 8192)
            os.environ['FORETS_RUN_BUDGET_PATH'] = str(failures)
            logs = io.StringIO()
            handler = logging.StreamHandler(logs)
            backend.logger.addHandler(handler)
            for exc in (TimeoutError('private response'), asyncio.CancelledError()):
                with patch.object(backend, 'completion_fn', AsyncMock(side_effect=exc)) as failing:
                    try:
                        asyncio.run(query('draft'))
                        raise AssertionError('failure hidden')
                    except (RuntimeError, asyncio.CancelledError):
                        pass
                    assert failing.await_count == 1
            backend.logger.removeHandler(handler)
            assert count(failures) == 2 and 'private response' not in logs.getvalue()
            assert 'CancelledError' in logs.getvalue() and 'transport_unknown' in logs.getvalue()
            # A newly constructed client sees the old budget, not a reset counter.
            operators['draft'] = GenericLLM(policy_cfg.operators['draft'])
            with patch.object(backend, 'completion_fn', AsyncMock(return_value=response)) as last:
                asyncio.run(query('draft'))
                try:
                    asyncio.run(query('draft'))
                    raise AssertionError('restart refunded failures')
                except run_budget.RunBudgetError:
                    pass
                assert last.await_count == 1 and count(failures) == 3
            try:
                run_budget.initialize(failures, 999, 8192)
                raise AssertionError('budget reset allowed')
            except FileExistsError:
                pass
            checks.append('timeout_cancellation_and_client_restart_never_refund_or_reset_budget')

            corrupt = root / 'corrupt.sqlite'
            corrupt.write_bytes(b'not a database')
            os.environ['FORETS_RUN_BUDGET_PATH'] = str(corrupt)
            with patch.object(backend, 'completion_fn', AsyncMock()) as unused:
                try:
                    asyncio.run(query('debug'))
                    raise AssertionError('corrupt budget allowed')
                except run_budget.RunBudgetError:
                    pass
                assert unused.await_count == 0
            checks.append('corrupt_budget_fails_closed')

        # Real independent processes contend for one node-local SQLite policy.
        concurrent = root / 'concurrent.sqlite'
        run_budget.initialize(concurrent, 7, 32)
        with multiprocessing.get_context('spawn').Pool(4) as pool:
            accepted = pool.map(attempt_from_process, [str(concurrent)] * 24)
        assert sum(accepted) == count(concurrent) == 7
        checks.append('four_processes_twentyfour_attempts_exactly_seven_reservations')
        evidence['concurrent_attempts'] = dict(processes=4, attempted=24, admitted=sum(accepted))

    os.environ.pop('FORETS_RUN_BUDGET_PATH', None)
    result = dict(status='PASS', source_tree=args.source_tree, checks=checks, evidence=evidence,
        api_cost_cap_usd=None, external_api_requests=0, gpu_jobs=0, model_loads=0,
        protected_data_read=False, interpretation='engineering preparation; no e2e or model benefit',
        versions={p: importlib.metadata.version(p) for p in ('hydra-core','litellm','openai')})
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
