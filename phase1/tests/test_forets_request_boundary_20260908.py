"""Real request/renderer/operator bodies, synthetic backend and templates only."""
import ast
import asyncio
import copy
import dataclasses
import hashlib
import json
import os
import random
import re
import subprocess
import sys
import time
import typing
import types
from functools import partial
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest
from jinja2 import Environment, StrictUndefined

from phase1.forets_request_guard_20260908 import (
    ACTIVE, BatchRequestGuard, audited_query, package_order,
)
from phase1.forets_request_patch_20260908 import revised, upstream, LEDGER, GENERIC, DRAFT, IMPROVE
from phase1.forets_upstream_hotfix_20260908 import ROOT, UPSTREAM, SECRET


@pytest.fixture(autouse=True)
def applied_request_tree(monkeypatch):
    tree = os.environ.get('FORETS_REQUEST_TREE')
    if not tree:
        return
    assert len(tree) == 40 and all(c in '0123456789abcdef' for c in tree)
    from phase1 import forets_request_patch_20260908 as patcher
    def from_tree(path):
        raw = subprocess.check_output(['git', 'show', f'{tree}:{path}'], cwd=ROOT)
        assert len(raw) < 1048576 and not SECRET.search(raw)
        return raw.decode()
    guard_env = {'__name__': 'applied_request_guard'}
    exec(compile(from_tree(patcher.GUARD), patcher.GUARD, 'exec'), guard_env)
    for name in ('ACTIVE', 'BatchRequestGuard', 'audited_query', 'package_order'):
        monkeypatch.setattr(sys.modules[__name__], name, guard_env[name])
    monkeypatch.setattr(sys.modules[__name__], 'revised', from_tree)
    monkeypatch.setattr(patcher, 'revised', from_tree)


def extra_source(path):
    assert path in {'src/dojo/core/solvers/llm_helpers/prompt_template.py',
                    'src/dojo/core/solvers/utils/response.py',
                    'src/dojo/core/solvers/operators/core.py'}
    raw = subprocess.check_output(['git', 'show', f'{UPSTREAM}:{path}'], cwd=ROOT)
    assert len(raw) < 1048576 and not SECRET.search(raw)
    return raw.decode()


def definitions(text, names, env):
    body = [n for n in ast.parse(text).body if isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in names]
    assert len(body) == len(names)
    exec(compile(ast.Module(body=body, type_ignores=[]), 'upstream-method-body', 'exec'), env)


def ledger_at(tmp_path, count=1):
    env = {}
    exec(compile(revised(LEDGER), LEDGER, 'exec'), env)
    ledger = env['CandidateLedger'](tmp_path / 'private' / 'batch.sqlite', {'synthetic': True}, count)
    for slot in range(count):
        ledger.begin_generation(slot)
    return ledger


class Backend:
    client_content_key = 'content'
    def __init__(self, answers=None):
        self.answers = iter(answers or [('print(1)', {'total_tokens': 11})] * 20)
        self.messages = []
        self.call_kwargs = []
        self.mutate = False
    async def query(self, messages, **kwargs):
        self.messages.append(copy.deepcopy(messages))
        self.call_kwargs.append(copy.deepcopy(kwargs))
        await asyncio.sleep(0)
        if self.mutate:
            messages.append({'role': 'system', 'content': 'backend mutation'})
        answer = next(self.answers)
        if isinstance(answer, BaseException):
            raise answer
        return copy.deepcopy(answer)


def llm(backend, patched=True):
    env = dict(vars(typing), OperatorConfig=NS, ClientConfig=NS, audited_query=audited_query, log=Mock())
    definitions(revised(GENERIC) if patched else upstream(GENERIC), {'GenericLLM'}, env)
    obj = env['GenericLLM'].__new__(env['GenericLLM'])
    renderer_env = dict(Environment=Environment, StrictUndefined=StrictUndefined, JinjaPromptConfig=NS)
    definitions(extra_source('src/dojo/core/solvers/llm_helpers/prompt_template.py'), {'JinjaPrompt'}, renderer_env)
    def renderer(template):
        cls = renderer_env['JinjaPrompt']
        instance = cls.__new__(cls)
        instance.environment = Environment(undefined=StrictUndefined)
        instance.template, instance.partial_variables = template, {}
        return instance
    obj.system_message_prompt_template = renderer('Task={{ task_desc }}')
    obj.init_user_message_prompt_template = renderer('Packages={{ packages }}; Memory={{ memory }}; Time={{ time_remaining }}')
    obj.user_message_prompt_template = obj.init_user_message_prompt_template
    obj.client, obj.generation_kwargs = backend, {'temperature': .7, 'max_tokens': 64}
    obj.call_tracker, obj.logger = 0, Mock()
    return obj


def operator(path, patched=True):
    env = dict(vars(typing), os=os, random=random, time=time,
               humanize=NS(naturaldelta=lambda x: f'{x} seconds'),
               DictConfig=NS, GenericLLM=NS, Journal=NS, Node=NS, Complexity=NS,
               package_order=package_order, wrap_code=lambda x, **kw: x)
    name = 'draft_op' if path == DRAFT else 'improve_op'
    definitions(revised(path) if patched else upstream(path), {name}, env)
    return env[name]


def cfg():
    return NS(available_packages=['numpy', 'pandas', 'sklearn'], execution_timeout=10,
              step_limit=10, data_preview=True)


def test_original_operator_mutates_shared_config_and_renders_different_prompt(monkeypatch):
    monkeypatch.setattr(random, 'shuffle', lambda xs: xs.reverse())
    backend = Backend()
    model = llm(backend, False)
    conf = cfg()
    async def run():
        for _ in range(2):
            await operator(DRAFT, False)(model, conf, None, 'synthetic task', None, 1, 50)
    asyncio.run(run())
    assert backend.messages[0] != backend.messages[1]
    # This controlled two-call reversal returns the list to its starting order.
    assert conf.available_packages == ['numpy', 'pandas', 'sklearn']


@pytest.mark.parametrize('path', [DRAFT, IMPROVE])
def test_guarded_real_jinja_and_operator_keep_config_and_messages_fixed(tmp_path, path):
    backend, conf = Backend(), cfg()
    model = llm(backend)
    with ledger_at(tmp_path) as ledger:
        guard = BatchRequestGuard(ledger, 2)
        async def run():
            with guard.slot(0):
                for _ in range(2):
                    args = (model, conf, lambda *a: 'fixed memory', 'synthetic task', None)
                    if path == IMPROVE:
                        args += (NS(code='print(1)', term_out='synthetic'),)
                    await operator(path)(*args, 1, 50)
        asyncio.run(run())
        assert conf.available_packages == ['numpy', 'pandas', 'sklearn']
        assert backend.messages[0] == backend.messages[1]
        calls = ledger.data['llm_requests']
        assert [c['state'] for c in calls] == ['returned', 'returned']
        assert [c['usage']['total_tokens'] for c in calls] == [11, 11]
        # GenericLLM mutates returned usage; pre-return records must not alias it.
        assert all('cumulative_num_llm_calls' not in c['usage'] for c in calls)
        assert ACTIVE.get() is None


@pytest.mark.parametrize('drift', ['memory', 'temperature'])
def test_drift_stops_before_second_backend_call(tmp_path, drift):
    backend, model = Backend(), None
    model = llm(backend)
    with ledger_at(tmp_path) as ledger:
        guard = BatchRequestGuard(ledger, 2)
        async def run():
            with guard.slot(0):
                data = dict(task_desc='test', packages='fixed', memory='A', time_remaining='50')
                await model(query_data=data)
                if drift == 'memory':
                    data['memory'] = 'B'
                else:
                    model.generation_kwargs['temperature'] = .3
                await model(query_data=data)
        with pytest.raises(RuntimeError, match='drift before dispatch'):
            asyncio.run(run())
        assert len(backend.messages) == len(ledger.data['llm_requests']) == 1


def real_async_extraction():
    env = dict(Callable=typing.Callable, re=re, asyncio=asyncio,
               format_code=lambda code: code)
    definitions(extra_source('src/dojo/core/solvers/utils/response.py'),
                {'extract_code', 'extract_text_up_to_code', 'parse_thinking_tags', 'is_valid_python_script'}, env)
    definitions(extra_source('src/dojo/core/solvers/operators/core.py'), {'async_execute_op_plan_code'}, env)
    return env['async_execute_op_plan_code']


def test_extraction_retry_preserves_every_returned_usage(tmp_path):
    backend = Backend([('this is not valid python!', {'total_tokens': 11}),
                       ('plan\n```python\nprint(1)\n```', {'total_tokens': 17})])
    model = llm(backend)
    with ledger_at(tmp_path) as ledger:
        guard = BatchRequestGuard(ledger, 2)
        async def call():
            return await model(messages=[{'role': 'user', 'content': 'fixed actual request'}])
        async def run():
            with guard.slot(0):
                return await real_async_extraction()(call, max_operator_tries=2)
        plan, code, metrics = asyncio.run(run())
        assert code == 'print(1)' and plan == 'plan'
        assert metrics['usage']['total_tokens'] == 17  # Original return still describes last call.
        assert [c['usage']['total_tokens'] for c in ledger.data['llm_requests']] == [11, 17]


def test_call_cap_prevents_extra_dispatch(tmp_path):
    backend = Backend([('not valid python!', {'total_tokens': 11})] * 3)
    model = llm(backend)
    with ledger_at(tmp_path) as ledger:
        guard = BatchRequestGuard(ledger, 2)
        async def call():
            return await model(messages=[{'role': 'user', 'content': 'fixed request'}])
        async def run():
            with guard.slot(0):
                await real_async_extraction()(call, max_operator_tries=3)
        with pytest.raises(RuntimeError, match='cap exhausted'):
            asyncio.run(run())
        assert len(backend.messages) == 2


def test_unknown_usage_remains_ambiguous_and_error_text_not_logged(tmp_path):
    backend = Backend([OSError('sensitive diagnostic must not be persisted')])
    with ledger_at(tmp_path) as ledger:
        guard = BatchRequestGuard(ledger, 1)
        async def run():
            with guard.slot(0):
                await audited_query(backend, [{'role': 'user', 'content': 'test'}])
        with pytest.raises(OSError):
            asyncio.run(run())
        call = ledger.data['llm_requests'][0]
        assert call['state'] == 'ambiguous' and call['usage'] is None
        assert call['error_type'] == 'OSError'
        assert 'sensitive diagnostic' not in json.dumps(ledger.data)
        with pytest.raises(RuntimeError, match='ambiguous'):
            ledger.ensure_preexecution()


def test_backend_mutation_does_not_corrupt_retained_prompt_and_stops(tmp_path):
    backend = Backend()
    backend.mutate = True
    messages = [{'role': 'user', 'content': 'fixed'}]
    with ledger_at(tmp_path) as ledger:
        async def run():
            with BatchRequestGuard(ledger, 1).slot(0):
                await audited_query(backend, messages)
        with pytest.raises(RuntimeError, match='mutated'):
            asyncio.run(run())
        assert messages == [{'role': 'user', 'content': 'fixed'}]
        assert ledger.data['prompt_snapshot']['messages'] == messages
        assert ledger.data['llm_requests'][0]['usage']['total_tokens'] == 11


def test_credential_shape_blocks_before_private_storage_and_network(tmp_path):
    backend = Backend()
    with ledger_at(tmp_path) as ledger:
        async def run():
            with BatchRequestGuard(ledger, 1).slot(0):
                await audited_query(backend, [{'role': 'user', 'content': 'sk-' + 'x' * 40}])
        with pytest.raises(RuntimeError, match='credential-shaped'):
            asyncio.run(run())
        assert backend.messages == []
        assert ledger.data['llm_requests'] == [] and ledger.data['prompt_snapshot'] is None


def test_concurrent_slots_keep_separate_call_receipts(tmp_path):
    backend = Backend()
    with ledger_at(tmp_path, count=3) as ledger:
        guard = BatchRequestGuard(ledger, 3)
        async def call(slot):
            with guard.slot(slot):
                return await audited_query(backend, [{'role': 'user', 'content': 'same request'}])
        async def run():
            await asyncio.gather(*(call(i) for i in range(3)))
        asyncio.run(run())
        assert [c['slot'] for c in ledger.data['llm_requests']] == [0, 1, 2]
        assert all(c['state'] == 'returned' for c in ledger.data['llm_requests'])


def test_inactive_guard_preserves_backend_forwarding():
    backend = Backend()
    response = asyncio.run(audited_query(backend, [{'role': 'user', 'content': 'outside audit'}], temperature=.2))
    assert response == ('print(1)', {'total_tokens': 11})
    assert backend.call_kwargs == [{'temperature': .2}]


def test_guard_requires_explicit_positive_cap(tmp_path):
    with ledger_at(tmp_path) as ledger:
        for cap in (0, -1, True, None):
            with pytest.raises(ValueError):
                BatchRequestGuard(ledger, cap)


def test_actual_forets_batch_wires_guard_and_reuses_completed_requests(tmp_path, monkeypatch):
    from phase1.tests import test_forets_candidate_state_20260908 as state_tests
    from phase1.forets_request_patch_20260908 import revised as request_revised
    module = types.ModuleType('dojo.solvers.fore_ts.request_guard')
    module.BatchRequestGuard = BatchRequestGuard
    module.package_order = package_order
    module.audited_query = audited_query
    monkeypatch.setitem(sys.modules, module.__name__, module)
    monkeypatch.setattr(state_tests, 'build_revised', request_revised)
    solver, task, _, batch_env = state_tests.runtime(tmp_path)
    solver.cfg.available_packages = ['numpy', 'pandas', 'sklearn']
    solver.cfg.execution_timeout = 10
    solver.cfg.data_preview = True
    backend = Backend()
    solver.draft_fn = partial(operator(DRAFT), llm(backend), solver.cfg, None)
    solver._draft.__func__.__globals__['async_execute_op_plan_code'] = real_async_extraction()
    real_begin = batch_env['CandidateLedger'].begin_execution
    monkeypatch.setattr(batch_env['CandidateLedger'], 'begin_execution',
                        lambda *a: (_ for _ in ()).throw(RuntimeError('pause before execution intent')))
    with pytest.raises(RuntimeError, match='pause before'):
        solver._expand_leaf_and_backprop([solver.root_node], {}, task)
    before = state_tests.stored(tmp_path)
    assert before['schema'] == 2 and len(before['llm_requests']) == 3
    assert solver.cfg.available_packages == ['numpy', 'pandas', 'sklearn']
    assert len({c['request_sha256'] for c in before['llm_requests']}) == 1
    assert len(backend.messages) == 3
    monkeypatch.setattr(batch_env['CandidateLedger'], 'begin_execution', real_begin)
    solver._expand_leaf_and_backprop([solver.root_node], {}, task)
    after = state_tests.stored(tmp_path)
    assert after['llm_requests'] == before['llm_requests']
    assert len(backend.messages) == 3 and len(solver.journal.nodes) == 2
