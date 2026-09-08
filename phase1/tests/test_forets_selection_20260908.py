"""New random/critic batch-contract tests; synthetic pools, no trained model."""
import ast
import asyncio
import contextlib
import hashlib
import json
import os
import random
import sqlite3
import subprocess
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

from phase1 import forets_selection_patch_20260908 as build
from phase1.forets_execution_witness_20260908 import ExecutionWitness
# Reuse fixture types only. The previous test matrix is NOT collected or run.
from phase1.tests.test_forets_execution_witness_20260908 import Node, Solver, Journal, output, state


def revised(path):
    tree = os.environ.get('FORETS_SELECTION_TREE')
    if not tree:
        return build.revised(path)
    assert len(tree) == 40 and all(c in '0123456789abcdef' for c in tree)
    raw = subprocess.check_output(['git', 'show', tree + ':' + path], cwd=build.ROOT)
    assert not build.SECRET.search(raw)
    return raw.decode()


def modules():
    ledger_env, select_env = {}, {}
    exec(compile(revised(build.LEDGER), build.LEDGER, 'exec'), ledger_env)
    exec(compile(revised(build.SELECTOR), build.SELECTOR, 'exec'), select_env)
    return ledger_env, select_env


def read_batch(root):
    file = next((root / 'forets-candidates-private').glob('*.sqlite'))
    with sqlite3.connect(file) as db:
        return json.loads(db.execute('SELECT payload FROM snapshot').fetchone()[0])


def fixture(root, policy, count=5, top_k=5, choose=2):
    solver = Solver()
    solver.cfg = NS(num_children=count, selector_seed=6, checkpoint_path=str(root),
                    max_llm_call_retries=1, execution_timeout=30, step_limit=10,
                    selection_policy=policy)
    solver.state = NS(current_step=0)
    solver.task_name, solver.task_desc, solver.data_preview = 'artificial', 'fixed artificial input', ''
    solver.root_node = Node('root', code='')
    solver.journal = Journal(solver.root_node)
    solver.global_min_q_val, solver.global_max_q_val = 0., 1.
    solver.critic_top_k, solver.num_children_to_choose = top_k, choose
    calls = dict(generation=0, critic=0, execution=0)
    async def generate(parent):
        slot = calls['generation']
        calls['generation'] += 1
        await asyncio.sleep(0)  # A scheduling yield, not a timed wait.
        return Node(str(slot), code=f'print({slot})')
    async def critic(node):
        calls['critic'] += 1
        saved = read_batch(root)
        assert saved['pool_sha256'] is not None
        assert all(c['node'] is not None for c in saved['candidates'])
        assert calls['generation'] == count and calls['execution'] == 0
        return float(node.id)
    def task_step(s, code):
        assert calls['generation'] == count
        assert calls['critic'] == (count if policy == 'critic_topk_random' else 0)
        calls['execution'] += 1
        return s, {'execution_output': output()}
    def parse(node, eval_result):
        node.is_buggy = False
        node.metric = NS(value=.5)
    solver._draft = solver._improve = generate
    solver._query_critic = critic
    solver.parse_eval_result = parse
    solver.debug_cycle = Mock(side_effect=AssertionError('not a debug fixture'))
    solver.log_journal = solver._backprop_step = solver.set_global_q_values = Mock()
    ledger_env, select_env = modules()
    class NoPaidGeneration:
        def __init__(self, *args): pass
        def slot(self, slot): return contextlib.nullcontext()
    env = {k: ledger_env[k] for k in ('CandidateLedger', 'LedgerError', 'digest')}
    env.update({k: select_env[k] for k in ('POLICIES', 'choose_slots')})
    env.update(ExecutionWitness=ExecutionWitness, EXECUTION_OUTPUT='execution_output',
               BatchRequestGuard=NoPaidGeneration)
    module = ast.parse(revised(build.BATCH))
    module.body = [n for n in module.body if not (isinstance(n, ast.ImportFrom) and n.module.startswith('dojo.'))]
    exec(compile(module, build.BATCH, 'exec'), env)
    def run():
        return env['expand_batch'](solver, [solver.root_node], state(), NS(step_task=task_step),
                                   Node, lambda code: code, vars(solver.cfg))
    return solver, calls, env, run


def test_random_arm_never_queries_critic_and_preserves_unselected_unknown(tmp_path):
    solver, calls, _, run = fixture(tmp_path, 'uniform_random', top_k=3)
    solver._query_critic = Mock(side_effect=AssertionError('baseline must not call critic'))
    run()
    assert calls == dict(generation=5, critic=0, execution=2)
    saved = read_batch(tmp_path)
    assert saved['pool_sha256'] and saved['phase'] == 'complete'
    assert all(c['score'] is None for c in saved['candidates'])
    assert [c['state'] for c in saved['candidates']].count('generated') == 3
    assert len(solver.journal.nodes) == 3


def test_real_batch_full_pool_critic_null_exactly_matches_random(tmp_path):
    records = []
    for policy in ('uniform_random', 'critic_topk_random'):
        root = tmp_path / policy
        solver, calls, _, run = fixture(root, policy)
        run()
        records.append(read_batch(root))
        assert calls['execution'] == 2 and solver.state.current_step == 2
    assert records[0]['pool_sha256'] == records[1]['pool_sha256']
    assert records[0]['selected'] == records[1]['selected']
    # Different policy/output paths must still bind separate recovery ledgers.
    assert records[0]['binding'] != records[1]['binding']


def test_critic_uses_complete_frozen_pool_and_top_k(tmp_path):
    _, calls, _, run = fixture(tmp_path, 'critic_topk_random', top_k=2)
    run()
    assert calls == dict(generation=5, critic=5, execution=2)
    assert set(read_batch(tmp_path)['selected']) == {3, 4}


def test_generator_failure_makes_no_critic_or_execution_call(tmp_path):
    solver, calls, _, run = fixture(tmp_path, 'critic_topk_random')
    async def fail(parent): raise RuntimeError('artificial generation failure')
    solver._draft = fail
    with pytest.raises(RuntimeError, match='generation failure'): run()
    saved = read_batch(tmp_path)
    assert saved['pool_sha256'] is None and calls['critic'] == calls['execution'] == 0
    with pytest.raises(RuntimeError, match='ambiguous'): run()


def test_critic_failure_keeps_frozen_pool_but_does_not_execute(tmp_path):
    solver, calls, _, run = fixture(tmp_path, 'critic_topk_random')
    async def fail(node): raise RuntimeError('artificial critic failure')
    solver._query_critic = fail
    with pytest.raises(RuntimeError, match='critic failure'): run()
    saved = read_batch(tmp_path)
    assert saved['pool_sha256'] is not None and all(c['node'] for c in saved['candidates'])
    assert calls['execution'] == 0
    with pytest.raises(RuntimeError, match='ambiguous'): run()


def test_critic_cannot_mutate_frozen_program(tmp_path):
    solver, calls, _, run = fixture(tmp_path, 'critic_topk_random')
    async def mutate(node):
        node.code = 'print("changed")'
        return .5
    solver._query_critic = mutate
    with pytest.raises(RuntimeError, match='candidate changed'): run()
    assert calls['execution'] == 0
    assert read_batch(tmp_path)['candidates'][0]['node']['code'] == 'print(0)'


def test_random_known_selection_resumes_without_regeneration_or_resampling(tmp_path, monkeypatch):
    _, calls, env, run = fixture(tmp_path, 'uniform_random')
    klass = env['CandidateLedger']
    original = klass.begin_execution
    monkeypatch.setattr(klass, 'begin_execution', lambda *a: (_ for _ in ()).throw(RuntimeError('before intent')))
    with pytest.raises(RuntimeError, match='before intent'): run()
    selected = read_batch(tmp_path)['selected']
    monkeypatch.setattr(klass, 'begin_execution', original)
    random.seed(901)
    run()
    assert calls == dict(generation=5, critic=0, execution=2)
    assert read_batch(tmp_path)['selected'] == selected


def test_policy_change_cannot_reuse_ledger(tmp_path, monkeypatch):
    solver, calls, env, run = fixture(tmp_path, 'uniform_random')
    monkeypatch.setattr(env['CandidateLedger'], 'begin_execution', lambda *a: (_ for _ in ()).throw(RuntimeError('before intent')))
    with pytest.raises(RuntimeError, match='before intent'): run()
    solver.cfg.selection_policy = 'critic_topk_random'
    with pytest.raises(RuntimeError, match='binding mismatch'): run()
    assert calls == dict(generation=5, critic=0, execution=0)


def test_selector_null_coupling_tail_and_global_rng_isolation():
    select = modules()[1]['choose_slots']
    for seed in (6, 7, 112):
        random.seed(seed * 29)
        for _ in range(seed): random.random()
        a = select(5, 5, 2, 'uniform_random', seed, 'artificial', 0)
        b = select(5, 5, 2, 'critic_topk_random', seed, 'artificial', 0, [3., -1., 8., 4., 2.])
        assert a == b
    assert select(1, 5, 2, 'uniform_random', 6, 'artificial', 9) == [0]
    assert select(1, 5, 2, 'critic_topk_random', 6, 'artificial', 9, [0.]) == [0]


@pytest.mark.parametrize('scores', [[0., float('nan')], [0., True], [0.], None])
def test_ranked_invalid_score_vector_rejected(scores):
    with pytest.raises(ValueError, match='finite score'):
        modules()[1]['choose_slots'](2, 2, 1, 'critic_topk_random', 6, 'artificial', 0, scores)


def test_random_rejects_score_input_and_missing_policy():
    select = modules()[1]['choose_slots']
    with pytest.raises(ValueError, match='must not receive'): select(2, 2, 1, 'uniform_random', 6, 'artificial', 0, [0., 1.])
    with pytest.raises(ValueError, match='supported'): select(2, 2, 1, 'automatic', 6, 'artificial', 0)


def test_pool_drift_and_premature_scoring_are_blocked(tmp_path):
    klass = modules()[0]['CandidateLedger']
    with klass(tmp_path / 'private' / 'ledger.sqlite', {'selection_policy': 'critic_topk_random'}, 1) as ledger:
        ledger.begin_generation(0)
        ledger.generated(0, dict(id='0', ctime=1., code='print(0)', plan='', operators_used=[], operators_metrics=[]))
        with pytest.raises(RuntimeError, match='frozen ranked pool'): ledger.begin_score(0)
        ledger.freeze_pool()
        ledger.data['candidates'][0]['node']['code'] = 'print(1)'
        with pytest.raises(RuntimeError, match='pool drift'): ledger.freeze_pool()


def test_configuration_requires_explicit_policy():
    text = revised(build.CONFIG)
    assert 'selection_policy: str = field(default=MISSING)' in text
    assert 'selection_policy: ???' in revised(build.YAML)
    import dataclasses
    class Base:
        def validate(self): pass
    env = dict(dataclass=dataclasses.dataclass, field=dataclasses.field, MISSING='???', SolverConfig=Base)
    tree = ast.parse(text)
    tree.body = [n for n in tree.body if isinstance(n, ast.ClassDef)]
    exec(compile(tree, build.CONFIG, 'exec'), env)
    config = env['ForeTSSolverConfig'](selector_seed=6, uct_c=.25, num_children=5,
        critic_top_k=3, num_children_to_choose=2, critic_max_attempts=1)
    with pytest.raises(ValueError, match='selection_policy'): config.validate()
    for policy in ('uniform_random', 'critic_topk_random'):
        config.selection_policy = policy
        config.validate()
