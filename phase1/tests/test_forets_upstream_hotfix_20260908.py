"""Execute exact upstream method bodies with synthetic nodes and mocked I/O.

These are directed defect reproductions, NOT a full Dojo/Hydra/GPU integration.
Untouched upstream failures are asserted explicitly, beside patched expectations.
"""
import ast
import asyncio
import dataclasses
import json
import math
import os
import random
import subprocess
import sys
import typing
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

from phase1.forets_upstream_hotfix_20260908 import (
    CONFIG, FORE, MEMORY, TASK, ROOT, SECRET, revised, source,
)


@pytest.fixture(autouse=True)
def applied_patch_source(monkeypatch):
    """Optional second pass reads Git's applied tree instead of the patch builder."""
    tree = os.environ.get('FORETS_PATCHED_TREE')
    if tree is None:
        return
    assert len(tree) == 40 and all(c in '0123456789abcdef' for c in tree)
    def from_tree(path):
        assert path in {FORE, CONFIG, TASK}
        raw = subprocess.check_output(['git', 'show', f'{tree}:{path}'], cwd=ROOT)
        assert len(raw) <= 1024 * 1024 and not SECRET.search(raw)
        return raw.decode('utf-8')
    monkeypatch.setattr(sys.modules[__name__], 'revised', from_tree)


class Parent:
    def __init__(self, cfg, task_info):
        self.cfg = cfg
        self.state = NS(current_step=0, running_time=0)
        self.logger = Mock()
        self.journal = []
        self.log_journal = Mock()
        self._backprop_step = Mock()
        self.set_global_q_values = Mock()

    @property
    def remaining_steps(self):
        return self.cfg.step_limit - self.state.current_step


class ConfigParent:
    def validate(self):
        pass


def load_class(path, name, patched, extras):
    tree = ast.parse(revised(path) if patched else source(path))
    klass = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == name)
    env = dict(vars(typing), **extras)
    env.update(dataclass=dataclasses.dataclass, field=dataclasses.field, MISSING='???')
    exec(compile(ast.Module(body=[klass], type_ignores=[]), path, 'exec'), env)
    return env[name], env


def runtime(patched=True):
    async def no_wait(_):
        return None
    # Do not patch the process-global asyncio module or its event loop.
    aio = NS(run=asyncio.run, gather=asyncio.gather, sleep=no_wait)
    transport = NS(Request=lambda *a, **kw: NS(args=a, kwargs=kw), urlopen=Mock())
    klass, env = load_class(FORE, 'ForeTS', patched, {
        'MCTS': Parent, 'MCTSNode': NS, 'ForeTSSolverConfig': NS,
        'asyncio': aio, '_rq': transport, 'random': random.Random(6),
        'json': json, 'math': math, 'extract_code': lambda code: code,
    })
    cfg = NS(critic_host='localhost', critic_port=8765, critic_top_k=4,
             num_children_to_choose=2, num_children=5, critic_max_attempts=2,
             step_limit=10, validate=lambda: None)
    solver = klass(cfg, {'name': 'synthetic-task'})
    return solver, transport, env


class Response:
    def __init__(self, score):
        self.score = score

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps({'score': self.score}).encode()


def test_original_undefined_task_name_prevents_every_http_request():
    solver, transport, _ = runtime(False)
    transport.urlopen.return_value = Response(.75)
    value = asyncio.run(solver._query_critic(NS(code='print(1)')))
    assert value is None
    assert transport.urlopen.call_count == 0
    assert solver.logger.warning.call_count == 2
    assert '_rm_task_name' in solver.logger.warning.call_args.args[0]


def test_fixed_query_sends_real_task_name():
    solver, transport, _ = runtime()
    transport.urlopen.return_value = Response(.75)
    assert asyncio.run(solver._query_critic(NS(code='print(1)'))) == .75
    request = transport.urlopen.call_args.args[0]
    assert json.loads(request.args[1]) == {'task': 'synthetic-task', 'code': 'print(1)'}
    assert transport.urlopen.call_count == 1


def test_original_exhaustion_returns_none_even_if_task_field_is_injected():
    solver, transport, _ = runtime(False)
    solver._rm_task_name = 'synthetic-task'  # isolate the second defect
    transport.urlopen.side_effect = OSError('synthetic failure')
    assert asyncio.run(solver._query_critic(NS(code='x'))) is None
    assert transport.urlopen.call_count == 2


def test_fixed_exhaustion_stops_with_bounded_attempts():
    solver, transport, _ = runtime()
    transport.urlopen.side_effect = OSError('synthetic failure')
    with pytest.raises(RuntimeError, match='attempts exhausted'):
        asyncio.run(solver._query_critic(NS(code='x')))
    assert transport.urlopen.call_count == 2


def test_original_accepts_nan():
    solver, transport, _ = runtime(False)
    solver._rm_task_name = 'synthetic-task'
    transport.urlopen.return_value = Response(float('nan'))
    assert math.isnan(asyncio.run(solver._query_critic(NS(code='x'))))


@pytest.mark.parametrize('score', [float('nan'), float('inf'), -float('inf'), True, None, 'bad'])
def test_fixed_invalid_score_stops(score):
    solver, transport, _ = runtime()
    transport.urlopen.return_value = Response(score)
    with pytest.raises(RuntimeError, match='attempts exhausted'):
        asyncio.run(solver._query_critic(NS(code='x')))
    assert transport.urlopen.call_count == 2


def expansion(patched, remaining, debug_consumes_last=False):
    solver, _, env = runtime(patched)
    solver.cfg.step_limit = remaining
    generated, executed = [], []
    task = NS()
    async def generate(parent):
        node = NS(code='candidate-' + str(len(generated)), is_buggy=False,
                  metric=NS(value=.5), parents=[parent])
        generated.append(node)
        return node, .75
    def execute(state, code):
        executed.append(code)
        return state, {}
    def parse(node, eval_result):
        node.is_buggy = debug_consumes_last and len(executed) == 1
    def debug(state, _task, _node):
        # Stub the inherited debug cycle: one additional full task step.
        _task.step_task(state, 'debug')
        solver.state.current_step += 1
        return state, [], None
    solver._draft = generate
    solver.parse_eval_result = parse
    solver.debug_cycle = debug
    task.step_task = execute
    return solver, task, generated, executed


def test_original_tail_sampling_fails_with_one_remaining_step():
    solver, task, generated, executed = expansion(False, 1)
    with pytest.raises(ValueError, match='Sample larger'):
        solver._expand_leaf_and_backprop([NS(parents=[])], {}, task)
    assert len(generated) == 1 and executed == []


def test_fixed_tail_executes_one():
    solver, task, generated, executed = expansion(True, 1)
    solver._expand_leaf_and_backprop([NS(parents=[])], {}, task)
    assert len(generated) == len(executed) == solver.state.current_step == 1


def test_fixed_zero_budget_does_not_generate():
    solver, task, generated, executed = expansion(True, 0)
    solver._expand_leaf_and_backprop([NS(parents=[])], {}, task)
    assert generated == executed == []


def test_original_debug_then_execution_exceeds_step_limit():
    solver, task, _, executed = expansion(False, 2, True)
    solver._expand_leaf_and_backprop([NS(parents=[])], {}, task)
    assert len(executed) == solver.state.current_step == 3
    assert solver.cfg.step_limit == 2


def test_fixed_debug_consumption_prevents_next_execution():
    solver, task, _, executed = expansion(True, 2, True)
    solver._expand_leaf_and_backprop([NS(parents=[])], {}, task)
    assert len(executed) == solver.state.current_step == solver.cfg.step_limit == 2


def config(patched):
    klass, _ = load_class(CONFIG, 'ForeTSSolverConfig', patched, {'SolverConfig': ConfigParent})
    cfg = klass(num_children=5, critic_top_k=4, num_children_to_choose=2, critic_max_attempts=2)
    if patched:
        cfg.uct_c = .25
    return cfg


def test_original_config_omits_uct_c_and_accepts_invalid_selection():
    cfg = config(False)
    assert not hasattr(cfg, 'uct_c')
    cfg.num_children_to_choose = 9
    cfg.validate()


def test_fixed_valid_config():
    config(True).validate()


@pytest.mark.parametrize('field,value', [
    ('num_children_to_choose', 9), ('critic_top_k', 6), ('critic_max_attempts', 0),
    ('num_children', True), ('critic_top_k', 1.5), ('uct_c', float('nan')),
])
def test_fixed_invalid_config_stops(field, value):
    cfg = config(True)
    setattr(cfg, field, value)
    with pytest.raises(ValueError):
        cfg.validate()


@pytest.mark.parametrize('patched,expect_name', [(False, False), (True, True)])
def test_actual_task_prepare_identity_handoff(patched, expect_name):
    tree = ast.parse(revised(TASK) if patched else source(TASK))
    klass = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'MLEBenchTask')
    method = next(n for n in klass.body if isinstance(n, ast.FunctionDef) and n.name == 'prepare')
    env = {'Path': Path, 'TASK_DESCRIPTION': 'description', 'evaluate': NS(is_lower_better=lambda c: False)}
    exec(compile(ast.Module(body=[method], type_ignores=[]), TASK, 'exec'), env)
    task = NS(cfg=NS(submission_fname='submission.csv', name='synthetic-task'),
              competition=None, task_description='synthetic description')
    state, info = env['prepare'](task, solver_interpreter=NS(working_dir='synthetic-unused'))
    assert ('name' in info) is expect_name
    if expect_name:
        assert info['name'] == task.cfg.name


def test_residual_unexecuted_node_memory_failure_is_not_claimed_fixed():
    tree = ast.parse(source(MEMORY))
    method = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'get_node_summary')
    env = {'Node': NS}
    exec(compile(ast.Module(body=[method], type_ignores=[]), MEMORY, 'exec'), env)
    node = NS(plan='synthetic plan', code='print(1)', operators_used=['draft'], is_buggy=None,
              analysis=None, metric=None)
    with pytest.raises(AttributeError):
        env['get_node_summary'](node)
    # Hotfix deliberately does not reinterpret unexecuted nodes as bad/good labels.
    assert 'self.journal.append(unselected_node)' in revised(FORE)


def test_patch_retains_existing_critic_char_limit_and_batch_information_boundary():
    patched = revised(FORE)
    assert '(node.code or "")[:40000]' in patched
    assert patched.index('asyncio.run(_gather())') < patched.index('task.step_task(')
    # This static order does NOT certify rendered prompts, full cost or journal isolation.
