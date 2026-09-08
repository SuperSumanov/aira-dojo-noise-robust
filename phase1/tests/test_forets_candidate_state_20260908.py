"""Synthetic I/O tests of the real patched ForeTS/Node/Journal method bodies.

Not a real model, Hydra configuration, Jupyter restart or full search experiment.
"""
import ast
import asyncio
import dataclasses
import json
import os
import random
import sqlite3
import subprocess
import time
import typing
import uuid
from functools import total_ordering
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

from phase1.forets_candidate_ledger_20260908 import CandidateLedger, LedgerError
from phase1.forets_batch_runtime_20260908 import expand_batch
from phase1.forets_state_patch_20260908 import revised as build_revised, FORE, MCTS, LEDGER, BATCH
from phase1.forets_upstream_hotfix_20260908 import ROOT, UPSTREAM, SECRET, MEMORY, source
from phase1.tests.test_forets_upstream_hotfix_20260908 import Parent


def revised(path):
    tree = os.environ.get('FORETS_STATE_TREE')
    if tree:
        assert len(tree) == 40 and all(c in '0123456789abcdef' for c in tree)
        raw = subprocess.check_output(['git', 'show', f'{tree}:{path}'], cwd=ROOT)
        assert len(raw) < 1024 * 1024 and not SECRET.search(raw)
        return raw.decode()
    return build_revised(path)


def node_record(i=0):
    return dict(id=f'n{i}', ctime=1., code=f'print({i})', plan='synthetic plan',
                operators_used=['draft'], operators_metrics=[{'tokens': 3}])


def make_scored(ledger, slot):
    ledger.begin_generation(slot)
    ledger.generated(slot, node_record(slot))
    ledger.begin_score(slot)
    ledger.scored(slot, float(slot))


def test_durable_slots_and_selection(tmp_path):
    file = tmp_path / 'private' / 'batch.sqlite'
    with CandidateLedger(file, {'boundary': 'synthetic'}, 3) as ledger:
        for i in range(3):
            make_scored(ledger, i)
        ledger.select([2, 0])
    with CandidateLedger(file, {'boundary': 'synthetic'}, 3) as ledger:
        ledger.ensure_preexecution()
        assert ledger.data['selected'] == [2, 0]
        ledger.begin_execution(2)
        ledger.execution_completed(2)
        ledger.finish()
        assert [c['state'] for c in ledger.data['candidates']] == ['skipped_budget', 'scored', 'completed']
        assert all('metric' not in c and 'is_buggy' not in c for c in ledger.data['candidates'])
    with CandidateLedger(file, {'boundary': 'synthetic'}, 3) as ledger:
        with pytest.raises(LedgerError, match='reconciliation'):
            ledger.ensure_preexecution()


@pytest.mark.parametrize('phase', ['generating', 'scoring', 'executing'])
def test_unknown_operation_cannot_auto_retry(tmp_path, phase):
    file = tmp_path / 'private' / 'batch.sqlite'
    with CandidateLedger(file, {}, 1) as ledger:
        ledger.begin_generation(0)
        if phase != 'generating':
            ledger.generated(0, node_record())
            ledger.begin_score(0)
        if phase == 'executing':
            ledger.scored(0, .5)
            ledger.select([0])
            ledger.begin_execution(0)
    with CandidateLedger(file, {}, 1) as ledger:
        with pytest.raises(LedgerError):
            ledger.ensure_preexecution()


def test_single_writer_and_idempotent_close(tmp_path):
    file = tmp_path / 'private' / 'batch.sqlite'
    one = CandidateLedger(file, {}, 1)
    with pytest.raises(LedgerError, match='lock'):
        CandidateLedger(file, {}, 1)
    one.close()
    with CandidateLedger(file, {}, 1) as two:
        one.close()  # Must not remove the second writer's lock.
        assert two.lock.exists()


def test_binding_change_refused(tmp_path):
    file = tmp_path / 'private' / 'batch.sqlite'
    with CandidateLedger(file, {'commit': 'A'}, 1):
        pass
    with pytest.raises(LedgerError, match='binding'):
        CandidateLedger(file, {'commit': 'B'}, 1)


def test_accidental_snapshot_drift_refused(tmp_path):
    file = tmp_path / 'private' / 'batch.sqlite'
    with CandidateLedger(file, {}, 1):
        pass
    with sqlite3.connect(file) as db:
        db.execute("UPDATE snapshot SET payload='{}'")
    with pytest.raises(LedgerError, match='hash drift'):
        CandidateLedger(file, {}, 1)


@pytest.mark.parametrize('value', [True, float('nan'), float('inf'), None, '0.5'])
def test_bad_scores_remain_unknown_not_silently_negative(tmp_path, value):
    with CandidateLedger(tmp_path / 'private' / 'batch.sqlite', {}, 1) as ledger:
        ledger.begin_generation(0)
        ledger.generated(0, node_record())
        ledger.begin_score(0)
        with pytest.raises(LedgerError):
            ledger.scored(0, value)
        assert ledger.data['candidates'][0]['state'] == 'scoring'


def test_selection_cannot_use_partial_batch_or_resample(tmp_path):
    with CandidateLedger(tmp_path / 'private' / 'batch.sqlite', {}, 2) as ledger:
        make_scored(ledger, 0)
        with pytest.raises(LedgerError):
            ledger.select([0])
        make_scored(ledger, 1)
        ledger.select([1])
        for attempt in ([1], [0], [0, 0], [True]):
            with pytest.raises(LedgerError):
                ledger.select(attempt)
        with pytest.raises(LedgerError):
            ledger.begin_execution(0)


def test_duplicate_identity_and_label_fields_refused(tmp_path):
    with CandidateLedger(tmp_path / 'private' / 'batch.sqlite', {}, 2) as ledger:
        make_scored(ledger, 0)
        ledger.begin_generation(1)
        with pytest.raises(LedgerError, match='duplicate'):
            ledger.generated(1, node_record(0))
        with pytest.raises(LedgerError, match='schema'):
            ledger.generated(1, node_record(1) | {'metric': 0})


def test_preexecution_record_does_not_alias_caller_lists(tmp_path):
    record = node_record()
    with CandidateLedger(tmp_path / 'private' / 'batch.sqlite', {}, 1) as ledger:
        ledger.begin_generation(0)
        ledger.generated(0, record)
        record['operators_used'].append('analysis')
        record['operators_metrics'][0]['tokens'] = 999
        assert ledger.data['candidates'][0]['node'] == node_record()


def real_data_classes():
    path = 'src/dojo/core/solvers/utils/journal.py'
    if os.environ.get('FORETS_SOURCE_CACHE'):
        from phase1.forets_linux_validation_20260908 import cached_source
        raw = cached_source(path).encode()
    else:
        raw = subprocess.check_output(['git', 'show', f'{UPSTREAM}:{path}'], cwd=ROOT)
    assert len(raw) < 1024 * 1024 and not SECRET.search(raw)
    env = dict(vars(typing), dataclass=dataclasses.dataclass, field=dataclasses.field,
               total_ordering=total_ordering, DataClassJsonMixin=object,
               ExecutionResult=NS, MetricValue=NS, WorstMetricValue=NS,
               time=time, uuid=uuid, trim_long_string=lambda s: s, log=Mock())
    for text, names in [(raw.decode(), {'Node', 'Journal'}), (source(MCTS), {'MCTSNode'})]:
        body = [n for n in ast.parse(text).body if isinstance(n, ast.ClassDef) and n.name in names]
        exec(compile(ast.Module(body=body, type_ignores=[]), path, 'exec'), env)
    return env['MCTSNode'], env['Journal']


def runtime(tmp_path, choose=1, count=3, limit=4):
    node_type, journal_type = real_data_classes()
    # Read actual new module blobs on the independent applied-tree test pass.
    # Only rewrite their import routing so tests do not import the full Dojo stack.
    ledger_env = {}
    exec(compile(revised(LEDGER), LEDGER, 'exec'), ledger_env)
    batch_env = {k: ledger_env[k] for k in ('CandidateLedger', 'LedgerError', 'digest')}
    module = ast.parse(revised(BATCH))
    module.body = [n for n in module.body if not (isinstance(n, ast.ImportFrom)
                   and n.module.endswith(('forets_candidate_ledger_20260908', 'candidate_ledger')))]
    exec(compile(module, BATCH, 'exec'), batch_env)
    klass = next(n for n in ast.parse(revised(FORE)).body if isinstance(n, ast.ClassDef) and n.name == 'ForeTS')
    calls = {'generation': 0, 'critic': 0, 'execution': 0}
    async def operator(*args, **kwargs):
        calls['generation'] += 1
        return 'synthetic plan', f'print({calls["generation"]})', {'tokens': 3}
    env = dict(vars(typing), MCTS=Parent, MCTSNode=node_type, ForeTSSolverConfig=NS,
               expand_batch=batch_env['expand_batch'], extract_code=lambda x: x,
               OmegaConf=NS(structured=lambda x: x, to_container=lambda x, **kw: vars(x)),
               async_execute_op_plan_code=operator, get_complextiy_level=lambda n: None,
               Path=Path, asyncio=asyncio)
    exec(compile(ast.Module(body=[klass], type_ignores=[]), FORE, 'exec'), env)
    cfg = NS(critic_host='localhost', critic_port=8765, critic_top_k=count,
             num_children_to_choose=choose, num_children=count, critic_max_attempts=1,
             step_limit=limit, selector_seed=6, checkpoint_path=str(tmp_path),
             time_limit_secs=60, use_complexity=False, max_llm_call_retries=1,
             validate=None)
    # Validation callable is omitted from the serialized fixture config.
    cfg.validate = lambda: None
    solver = env['ForeTS'](cfg, {'name': 'synthetic-task'})
    del cfg.validate
    solver.journal = journal_type()
    solver.root_node = node_type(id='root', ctime=1., code='', plan='', is_buggy=True,
                                metric=NS(value=None, info={}, maximize=True))
    solver.journal.append(solver.root_node)
    solver.state.current_step = 1
    solver.task_desc = 'synthetic description'
    solver.data_preview = 'synthetic preview'
    solver.draft_fn = solver.improve_fn = object()
    solver.global_min_q_val, solver.global_max_q_val = 1e8, -1e8
    async def critic(node):
        calls['critic'] += 1
        assert not node.parents and not node.children
        assert node.metric is None and node.is_buggy is None
        assert len(solver.journal.nodes) == 1
        return float(node.code[6:-1])
    def execute(state, code):
        calls['execution'] += 1
        assert calls['critic'] == count
        return state, {}
    def parse(node, eval_result):
        node.metric = NS(value=.5, info={}, maximize=True)
        node.analysis, node.is_buggy = 'synthetic analysis', False
    solver._query_critic = critic
    solver.parse_eval_result = parse
    solver.debug_cycle = Mock()
    return solver, NS(step_task=execute), calls, batch_env


def stored(tmp_path):
    file = next((tmp_path / 'forets-candidates-private').glob('*.sqlite'))
    with sqlite3.connect(file) as db:
        return json.loads(db.execute('SELECT payload FROM snapshot').fetchone()[0])


def test_actual_generation_methods_detach_then_only_executed_enters_journal(tmp_path):
    solver, task, calls, _ = runtime(tmp_path)
    solver._expand_leaf_and_backprop([solver.root_node], {}, task)
    assert calls == dict(generation=3, critic=3, execution=1)
    assert len(solver.journal.nodes) == 2 and len(solver.root_node.children) == 1
    assert solver.state.current_step == 2
    data = stored(tmp_path)
    assert sum(c['state'] == 'scored' for c in data['candidates']) == 2
    assert sum(c['state'] == 'completed' for c in data['candidates']) == 1
    # Exercise the actual memory function that previously crashed on unexecuted nodes.
    method = next(n for n in ast.parse(source(MEMORY)).body if isinstance(n, ast.FunctionDef) and n.name == 'get_node_summary')
    env = {'Node': type(solver.root_node)}
    exec(compile(ast.Module(body=[method], type_ignores=[]), MEMORY, 'exec'), env)
    assert all('0.5' in env['get_node_summary'](n) for n in solver.journal.good_nodes)
    child = solver.journal.nodes[-1]
    detached = asyncio.run(solver._improve(child))
    assert not detached.parents and not child.children


def test_critic_failure_keeps_generated_code_without_journal_pollution(tmp_path):
    solver, task, calls, _ = runtime(tmp_path, count=1)
    async def fail(node):
        raise RuntimeError('synthetic critic outage')
    solver._query_critic = fail
    with pytest.raises(RuntimeError, match='synthetic critic'):
        solver._expand_leaf_and_backprop([solver.root_node], {}, task)
    assert stored(tmp_path)['candidates'][0]['node']['code'] == 'print(1)'
    assert len(solver.journal.nodes) == 1 and not solver.root_node.children
    with pytest.raises(RuntimeError, match='ambiguous'):
        solver._expand_leaf_and_backprop([solver.root_node], {}, task)
    assert calls['generation'] == 1 and calls['execution'] == 0


def test_known_scored_batch_reuses_selection_without_calls_or_resampling(tmp_path, monkeypatch):
    solver, task, calls, env = runtime(tmp_path)
    real_begin = env['CandidateLedger'].begin_execution
    monkeypatch.setattr(env['CandidateLedger'], 'begin_execution', lambda *a: (_ for _ in ()).throw(RuntimeError('before intent')))
    with pytest.raises(RuntimeError, match='before intent'):
        solver._expand_leaf_and_backprop([solver.root_node], {}, task)
    selected = stored(tmp_path)['selected']
    monkeypatch.setattr(env['CandidateLedger'], 'begin_execution', real_begin)
    random.seed(93841)
    solver._expand_leaf_and_backprop([solver.root_node], {}, task)
    assert calls == dict(generation=3, critic=3, execution=1)
    assert stored(tmp_path)['selected'] == selected


@pytest.mark.parametrize('resume', [False, True])
def test_analysis_cannot_rewrite_persisted_generation_record(tmp_path, monkeypatch, resume):
    solver, task, _, env = runtime(tmp_path)
    original_parse = solver.parse_eval_result
    def parse(node, eval_result):
        original_parse(node, eval_result)
        node.operators_used.append('analysis')
        node.operators_metrics.append({'synthetic_analysis_tokens': 7})
    solver.parse_eval_result = parse
    if resume:
        original_begin = env['CandidateLedger'].begin_execution
        monkeypatch.setattr(env['CandidateLedger'], 'begin_execution', lambda *a: (_ for _ in ()).throw(RuntimeError('before intent')))
        with pytest.raises(RuntimeError, match='before intent'):
            solver._expand_leaf_and_backprop([solver.root_node], {}, task)
        monkeypatch.setattr(env['CandidateLedger'], 'begin_execution', original_begin)
    solver._expand_leaf_and_backprop([solver.root_node], {}, task)
    for candidate in stored(tmp_path)['candidates']:
        assert candidate['node']['operators_used'] == ['draft']
        assert candidate['node']['operators_metrics'] == [{'tokens': 3}]
    assert solver.journal.nodes[-1].operators_used == ['draft', 'analysis']


def test_execution_failure_never_replays_or_attaches(tmp_path):
    solver, task, calls, _ = runtime(tmp_path, count=1)
    def fail(*args):
        calls['execution'] += 1
        raise RuntimeError('unknown external execution')
    task.step_task = fail
    with pytest.raises(RuntimeError, match='unknown external'):
        solver._expand_leaf_and_backprop([solver.root_node], {}, task)
    with pytest.raises(RuntimeError, match='reconciliation'):
        solver._expand_leaf_and_backprop([solver.root_node], {}, task)
    assert calls['execution'] == 1 and not solver.root_node.children


def test_selector_ignores_output_directory_and_global_generation_rng(tmp_path):
    selections = []
    for index in range(2):
        solver, task, _, _ = runtime(tmp_path / str(index), choose=2, count=5, limit=6)
        random.seed(index * 1832)
        for _ in range(index * 37):
            random.random()
        solver._expand_leaf_and_backprop([solver.root_node], {}, task)
        selections.append(stored(tmp_path / str(index))['selected'])
    assert selections[0] == selections[1]


def test_zero_remaining_steps_makes_no_ledger_or_calls(tmp_path):
    solver, task, calls, _ = runtime(tmp_path, limit=1)
    solver._expand_leaf_and_backprop([solver.root_node], {}, task)
    assert calls == dict(generation=0, critic=0, execution=0)
    assert not (tmp_path / 'forets-candidates-private').exists()


def test_journal_change_prevents_recovery_before_any_more_calls(tmp_path, monkeypatch):
    solver, task, calls, env = runtime(tmp_path)
    monkeypatch.setattr(env['CandidateLedger'], 'begin_execution', lambda *a: (_ for _ in ()).throw(RuntimeError('before intent')))
    with pytest.raises(RuntimeError):
        solver._expand_leaf_and_backprop([solver.root_node], {}, task)
    solver.root_node.plan = 'changed memory'
    with pytest.raises(RuntimeError, match='binding mismatch'):
        solver._expand_leaf_and_backprop([solver.root_node], {}, task)
    assert calls == dict(generation=3, critic=3, execution=0)


def test_debug_consumes_tail_marks_budget_skip(tmp_path):
    solver, task, calls, _ = runtime(tmp_path, choose=2, count=2, limit=3)
    def parse(node, eval_result):
        node.is_buggy = True
        node.metric = NS(value=None, info={}, maximize=True)
    def debug(state, task, node):
        solver.state.current_step += 1
        return state, [node], None
    solver.parse_eval_result = parse
    solver.debug_cycle = debug
    solver._expand_leaf_and_backprop([solver.root_node], {}, task)
    assert solver.state.current_step == 3 and calls['execution'] == 1
    assert sorted(c['state'] for c in stored(tmp_path)['candidates']) == ['completed', 'skipped_budget']


def test_unimplemented_full_restore_is_explicitly_blocked(tmp_path):
    solver, task, _, _ = runtime(tmp_path)
    solver._expand_leaf_and_backprop([solver.root_node], {}, task)
    with pytest.raises(RuntimeError, match='full checkpoint reconciliation'):
        solver.load_checkpoint()


def test_upstream_loop_boundary_is_strict_in_common_mcts():
    assert 'while self.state.current_step <= self.cfg.step_limit:' in source(MCTS)
    assert 'while self.state.current_step < self.cfg.step_limit:' in revised(MCTS)
    tree = ast.parse(revised(MCTS))
    klass = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'MCTS')
    method = next(n for n in klass.body if isinstance(n, ast.FunctionDef) and n.name == '__call__')
    env = dict(time=time, export_search_results=Mock())
    exec(compile(ast.Module(body=[method], type_ignores=[]), MCTS, 'exec'), env)
    solver = NS(logger=Mock(), search_name='test', create_root_node=Mock(),
                cfg=NS(step_limit=1, time_limit_secs=60), state=NS(current_step=1),
                step=Mock(side_effect=AssertionError('must not step at exhausted budget')),
                save_checkpoint=Mock(), journal=NS(get_best_node=lambda: None))
    assert env['__call__'](solver, None, {}) == ({}, None, None)
    solver.step.assert_not_called()
