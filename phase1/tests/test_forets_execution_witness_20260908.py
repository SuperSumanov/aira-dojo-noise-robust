"""Task-boundary engineering tests; no production labels, models or paid calls."""
import ast
import asyncio
import contextlib
import copy
import dataclasses
import hashlib
import json
import os
import sqlite3
import subprocess
import time
import typing
from pathlib import Path
from types import SimpleNamespace as NS, MethodType
from unittest.mock import Mock

import pytest

from phase1 import forets_execution_patch_20260908 as build
from phase1.forets_execution_witness_20260908 import ExecutionWitness, ExecutionWitnessError


def revised(path):
    tree = os.environ.get('FORETS_EXECUTION_TREE')
    if not tree:
        return build.revised(path)
    assert len(tree) == 40 and all(c in '0123456789abcdef' for c in tree)
    raw = subprocess.check_output(['git', 'show', tree + ':' + path], cwd=build.ROOT)
    assert not build.SECRET.search(raw)
    return raw.decode()


def ledger_class():
    env = {}
    exec(compile(revised(build.LEDGER), build.LEDGER, 'exec'), env)
    return env['CandidateLedger']


def witness_class():
    env = {}
    exec(compile(revised(build.WITNESS), build.WITNESS, 'exec'), env)
    return env['ExecutionWitness']


@contextlib.contextmanager
def selected(tmp_path, count=1):
    with ledger_class()(tmp_path / 'private' / 'batch.sqlite', {'fixture': 'synthetic'}, count) as ledger:
        for i in range(count):
            ledger.begin_generation(i)
            ledger.generated(i, dict(id=str(i), ctime=1., code='print(1)', plan='',
                                     operators_used=['draft'], operators_metrics=[]))
            ledger.begin_score(i)
            ledger.scored(i, float(i))
        ledger.select(list(range(count)))
        ledger.begin_execution(0)
        yield ledger


def output(**kw):
    return NS(exit_code=kw.get('exit_code', 0), timed_out=kw.get('timed_out', False),
              exec_time=kw.get('exec_time', .02), term_out=['not copied'])


def state(timeout=30):
    return {'solver_interpreter': NS(timeout=timeout)}


def fake_task(out=None):
    return NS(step_task=Mock(side_effect=lambda s, a: (s, {'execution_output': out or output(),
                                                       'synthetic_score_not_for_receipt': 123.45})))


def test_return_is_durable_and_preserves_real_objects_without_scores(tmp_path):
    with selected(tmp_path) as ledger:
        task, s = fake_task(), state()
        ticks = iter([100, 160])
        witness = witness_class()(ledger, task, 2, 30, 'execution_output', lambda: next(ticks))
        returned = witness.task_for(0, 'candidate').step_task(s, 'print(1)')
        assert returned[0] is s
        with sqlite3.connect(ledger.path) as db:
            saved = json.loads(db.execute('SELECT payload FROM snapshot').fetchone()[0])
        call = saved['task_calls'][0]
        assert call['state'] == 'returned' and call['task_wall_ns'] == 60
        assert call['execution_metadata']['exec_time_reported_seconds'] == .02
        assert call['intent']['code_sha256'] == hashlib.sha256(b'print(1)').hexdigest()
        assert 'synthetic_score_not_for_receipt' not in json.dumps(call)
        assert 'not copied' not in json.dumps(call)
        assert saved['candidates'][0]['state'] == 'executing'
        assert witness.task_for(0, 'debug').step_task.__self__ is not task


def test_exception_records_observed_wall_but_unknown_execution_and_no_message(tmp_path):
    with selected(tmp_path) as ledger:
        task = NS(step_task=Mock(side_effect=RuntimeError('synthetic confidential message')))
        ticks = iter([10, 90])
        witness = witness_class()(ledger, task, 2, 30, 'execution_output', lambda: next(ticks))
        with pytest.raises(RuntimeError):
            witness.task_for(0, 'candidate').step_task(state(), 'print(1)')
        call = ledger.data['task_calls'][0]
        assert call['state'] == 'raised' and call['task_wall_ns'] == 80
        assert call['execution_metadata'] is None and call['error_type'] == 'RuntimeError'
        assert 'confidential' not in json.dumps(call)
        with pytest.raises(RuntimeError, match='unknown previous'):
            witness.task_for(0, 'debug').step_task(state(), 'print(2)')
        assert task.step_task.call_count == 1


def test_candidate_and_debug_share_attempt_cap_and_preserve_timeout_field(tmp_path):
    with selected(tmp_path) as ledger:
        task = fake_task(output(exit_code=1, timed_out=True, exec_time=30))
        witness = witness_class()(ledger, task, 2, 30, 'execution_output')
        witness.task_for(0, 'candidate').step_task(state(), 'print(1)')
        witness.task_for(0, 'debug').step_task(state(), 'print(2)')
        with pytest.raises(RuntimeError, match='cap exhausted'):
            witness.task_for(0, 'debug').step_task(state(), 'print(3)')
        assert task.step_task.call_count == 2
        assert [c['intent']['role'] for c in ledger.data['task_calls']] == ['candidate', 'debug']
        assert all(c['execution_metadata']['timed_out_reported'] for c in ledger.data['task_calls'])


@pytest.mark.parametrize('timeout', [None, False, -1, 0, float('inf'), float('nan'), 31])
def test_actual_interpreter_timeout_mismatch_stops_before_dispatch(tmp_path, timeout):
    with selected(tmp_path) as ledger:
        task = fake_task()
        witness = witness_class()(ledger, task, 1, 30, 'execution_output')
        with pytest.raises(RuntimeError, match='timeout mismatch'):
            witness.task_for(0, 'candidate').step_task(state(timeout), 'print(1)')
        assert not ledger.data['task_calls'] and task.step_task.call_count == 0


def test_runtime_drift_and_role_reordering_are_not_retried(tmp_path):
    with selected(tmp_path) as ledger:
        task = fake_task()
        witness = witness_class()(ledger, task, 3, 30, 'execution_output')
        with pytest.raises(RuntimeError, match='order mismatch'):
            witness.task_for(0, 'debug').step_task(state(), 'print(1)')
        witness.task_for(0, 'candidate').step_task(state(), 'print(1)')
        with pytest.raises(RuntimeError, match='timeout mismatch'):
            witness.task_for(0, 'debug').step_task(state(31), 'print(2)')
        with pytest.raises(RuntimeError, match='order mismatch'):
            witness.task_for(0, 'candidate').step_task(state(), 'print(3)')
        assert task.step_task.call_count == 1


def test_invalid_return_cannot_complete_candidate(tmp_path):
    with selected(tmp_path) as ledger:
        witness = witness_class()(ledger, NS(step_task=lambda s, a: (s, {})), 1, 30, 'execution_output')
        with pytest.raises(RuntimeError, match='valid execution metadata'):
            witness.task_for(0, 'candidate').step_task(state(), 'print(1)')
        assert ledger.data['task_calls'][0]['state'] == 'invalid_return'
        with pytest.raises(RuntimeError, match='receipts incomplete'):
            ledger.execution_completed(0)


def test_secret_canary_and_unselected_call_do_not_dispatch(tmp_path):
    with selected(tmp_path) as ledger:
        task = fake_task()
        witness = witness_class()(ledger, task, 1, 30, 'execution_output')
        with pytest.raises(RuntimeError, match='security/schema'):
            witness.task_for(0, 'candidate').step_task(state(), 's = "' + 'sk-' + 'A' * 32 + '"')
        with pytest.raises(RuntimeError, match='outside selected'):
            witness.task_for(1, 'candidate').step_task(state(), 'print(2)')
        assert task.step_task.call_count == 0 and not ledger.data['task_calls']


@dataclasses.dataclass(eq=False)
class Node:
    id: str
    ctime: float = 1.
    code: str = 'print(1)'
    plan: str = ''
    operators_used: list = dataclasses.field(default_factory=lambda: ['draft'])
    operators_metrics: list = dataclasses.field(default_factory=list)
    parents: list = dataclasses.field(default_factory=list)
    children: set = dataclasses.field(default_factory=set)
    metric: object = None
    is_buggy: object = None
    explore_count: int = 0
    node_value: float = 0.
    exec_time: float = .02
    debug_depth: int = 1


class Journal:
    def __init__(self, root): self.nodes = [root]
    def node_list(self): return [{'id': n.id, 'code': n.code} for n in self.nodes]
    def append(self, n): self.nodes.append(n)


class Solver:
    @property
    def remaining_steps(self): return self.cfg.step_limit - self.state.current_step


def batch_fixture(tmp_path):
    solver = Solver()
    solver.cfg = NS(num_children=2, selector_seed=6, checkpoint_path=str(tmp_path),
                    max_llm_call_retries=1, execution_timeout=30, step_limit=3,
                    max_debug_depth=1, max_debug_time=30)
    solver.state = NS(current_step=0)
    solver.task_name, solver.task_desc, solver.data_preview = 'synthetic', 'synthetic', ''
    solver.root_node = Node('root', code='')
    solver.journal = Journal(solver.root_node)
    solver.global_min_q_val, solver.global_max_q_val = 0., 1.
    solver.critic_top_k, solver.num_children_to_choose = 2, 1
    counter = iter(range(2))
    async def draft(parent): return Node(str(next(counter)))
    async def critic(node): return float(node.id)
    solver._draft = solver._improve = draft
    solver._query_critic = critic
    solver.log_journal = Mock()
    solver._backprop_step = Mock()
    solver.set_global_q_values = Mock()
    solver.logger = Mock()
    # Actual shared debug_cycle method body, with only generated code/analysis synthetic.
    env = dict(MCTSNode=Node, extract_code=lambda code: code)
    klass = next(n for n in ast.parse(build.source('src/dojo/solvers/mcts/mcts.py')).body
                 if isinstance(n, ast.ClassDef) and n.name == 'MCTS')
    fn = next(n for n in klass.body if isinstance(n, ast.FunctionDef) and n.name == 'debug_cycle')
    exec(compile(ast.Module(body=[fn], type_ignores=[]), '<pinned debug_cycle>', 'exec'), env)
    solver.debug_cycle = MethodType(env['debug_cycle'], solver)
    solver._debug = lambda n: Node('debug', parents=[n], code='print(2)')
    def parse(node, eval_result):
        node.is_buggy = node.id != 'debug'
        node.metric = NS(value=None if node.is_buggy else .5)
    solver.parse_eval_result = parse
    class NoPaidGeneration:
        def __init__(self, *args): pass
        def slot(self, slot): return contextlib.nullcontext()
    batch_env = dict(CandidateLedger=ledger_class(), LedgerError=RuntimeError,
                     digest=lambda v: hashlib.sha256(json.dumps(v, sort_keys=True).encode()).hexdigest(),
                     ExecutionWitness=witness_class(), EXECUTION_OUTPUT='execution_output',
                     BatchRequestGuard=NoPaidGeneration)
    module = ast.parse(revised(build.BATCH))
    module.body = [n for n in module.body if not (isinstance(n, ast.ImportFrom) and
                    n.module.startswith('dojo.'))]
    exec(compile(module, build.BATCH, 'exec'), batch_env)
    task = fake_task()
    return solver, task, batch_env['expand_batch']


def read_batch(tmp_path):
    path = next((tmp_path / 'forets-candidates-private').glob('*.sqlite'))
    with sqlite3.connect(path) as db:
        return json.loads(db.execute('SELECT payload FROM snapshot').fetchone()[0])


def test_actual_batch_and_shared_debug_both_write_before_analysis(tmp_path):
    solver, task, expand = batch_fixture(tmp_path)
    seen = []
    parse = solver.parse_eval_result
    def checked_parse(node, eval_result):
        saved = read_batch(tmp_path)
        assert saved['task_calls'][-1]['state'] == 'returned'
        seen.append(saved['task_calls'][-1]['intent']['role'])
        return parse(node, eval_result)
    solver.parse_eval_result = checked_parse
    expand(solver, [solver.root_node], state(), task, Node, lambda c: c, vars(solver.cfg))
    assert seen == ['candidate', 'debug']
    assert task.step_task.call_count == 2 and solver.state.current_step == 2
    saved = read_batch(tmp_path)
    assert saved['phase'] == 'complete'
    assert sum(c['state'] == 'completed' for c in saved['candidates']) == 1
    assert len(solver.journal.nodes) == 3


def test_actual_batch_analysis_crash_preserves_return_no_replay(tmp_path):
    solver, task, expand = batch_fixture(tmp_path)
    solver.parse_eval_result = Mock(side_effect=RuntimeError('artificial postprocess crash'))
    with pytest.raises(RuntimeError, match='postprocess crash'):
        expand(solver, [solver.root_node], state(), task, Node, lambda c: c, vars(solver.cfg))
    saved = read_batch(tmp_path)
    assert saved['task_calls'][0]['state'] == 'returned'
    assert saved['candidates'][saved['selected'][0]]['state'] == 'executing'
    with pytest.raises(RuntimeError, match='reconciliation'):
        expand(solver, [solver.root_node], state(), task, Node, lambda c: c, vars(solver.cfg))
    assert task.step_task.call_count == 1 and len(solver.journal.nodes) == 1


@pytest.mark.skipif(os.name != 'posix', reason='real pinned PythonInterpreter process test is Linux-only')
def test_real_python_interpreter_benign_process_through_task_witness(tmp_path):
    import signal, queue, sys, traceback, types, multiprocessing
    import humanize
    from abc import ABC, abstractmethod
    from dataclasses_json import DataClassJsonMixin
    # Keep exact upstream class/function bodies. Only import routing/config/logger
    # are injected; the process, IPC, timeout loop and ExecutionResult are real.
    env = dict(vars(typing), ABC=ABC, abstractmethod=abstractmethod, dataclass=dataclasses.dataclass,
               DataClassJsonMixin=DataClassJsonMixin, Path=Path)
    module = ast.parse(build.source('src/dojo/core/interpreters/base.py'))
    module.body = [n for n in module.body if isinstance(n, ast.ClassDef)]
    exec(compile(module, '<pinned interpreter base>', 'exec'), env)
    env.update(os=os, queue=queue, signal=signal, sys=sys, time=time, traceback=traceback,
               types=types, Process=multiprocessing.Process, Queue=multiprocessing.Queue,
               humanize=humanize, PythonInterpreterConfig=NS, get_logger=lambda: Mock(),
               log=Mock(), logging=Mock(), LogEvent=NS(INTERPRETER='interpreter'))
    module = ast.parse(build.source('src/dojo/core/interpreters/python.py'))
    module.body = [n for n in module.body if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and
                   n.name != 'main']
    exec(compile(module, '<pinned PythonInterpreter>', 'exec'), env)
    cfg = NS(working_dir=tmp_path / 'cpu-workspace', timeout=30, startup_timeout=10,
             format_tb_ipython=False)
    interpreter = env['PythonInterpreter'](cfg)
    task = NS(step_task=lambda s, a: (s, {'execution_output': interpreter.run(a)}))
    try:
        with selected(tmp_path) as ledger:
            witness = witness_class()(ledger, task, 1, 30, 'execution_output')
            s, result = witness.task_for(0, 'candidate').step_task(
                {'solver_interpreter': interpreter}, 'print("benign CPU witness")')
            assert result['execution_output'].exit_code == 0
            assert 'benign CPU witness' in ''.join(result['execution_output'].term_out)
            call = ledger.data['task_calls'][0]
            assert call['state'] == 'returned' and call['task_wall_ns'] > 0
            assert call['execution_metadata']['exec_time_reported_seconds'] >= 0
            assert 'benign CPU witness' not in json.dumps(call['execution_metadata'])
    finally:
        interpreter.cleanup_session()
    assert interpreter.process is None
