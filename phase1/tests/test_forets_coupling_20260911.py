"""Test the actual optional source patch; no generation/model/network clients."""
import ast
import dataclasses
import subprocess

import pytest

from phase1 import forets_common_priority as prototype
from phase1.scripts.prepare_forets_coupling_20260911 import prepare, ROOT
from phase1.tests.test_forets_selection_20260908 import fixture, read_batch, Journal

SELECTOR = 'src/dojo/solvers/fore_ts/selection.py'
CONFIG = 'src/dojo/config_dataclasses/solver/fore_ts.py'


@pytest.fixture(scope='module')
def source():
    return prepare()


def read(tree, path):
    return subprocess.check_output(['git', 'show', tree+':'+path], cwd=ROOT).decode()


def namespace(tree, path):
    env = {}
    exec(compile(read(tree, path), path, 'exec'), env)
    return env


def test_default_matches_old_choices_and_option_matches_prototype(source):
    new = namespace(source['source_tree'], SELECTOR)['choose_slots']
    old = namespace(source['base_tree'], SELECTOR)['choose_slots']
    for count in range(1, 6):
        for top_k in range(1, count+1):
            for choose in range(1, top_k+1):
                for seed in (6, 7, 8, 9):
                    for policy in ('uniform_random', 'critic_topk_random'):
                        for tied in (False, True):
                            scores = None if policy == 'uniform_random' else ([0.] * count if tied else list(range(count)))
                            args = (count, top_k, choose, policy, seed, 'artificial', 1, scores)
                            assert new(*args) == old(*args)
                            assert new(*args, coupling='common_priority_v1') == prototype.choose_slots(*args)


def batch(root, source, monkeypatch, coupling, top_k=2):
    monkeypatch.setenv('FORETS_SELECTION_TREE', source['source_tree'])
    solver, calls, env, run = fixture(root, 'critic_topk_random', count=3, top_k=top_k, choose=1)
    solver.cfg.selection_coupling = coupling
    solver.cfg.step_limit=4; solver.state.current_step=1
    solver.journal_for_unselected = Journal(solver.root_node)
    solver.journal_for_unselected.nodes.clear()
    return solver, calls, env, run


@pytest.mark.parametrize('coupling', ['independent_subset_v2', 'common_priority_v1'])
def test_real_batch_records_coupling_and_executes_once(tmp_path, source, monkeypatch, coupling):
    _, calls, _, run = batch(tmp_path, source, monkeypatch, coupling)
    run()
    saved = read_batch(tmp_path)
    assert saved['binding']['selection_coupling'] == coupling
    assert saved['phase'] == 'complete'
    assert calls == {'generation': 3, 'critic': 3, 'execution': 1}


def test_coupling_change_refused_even_if_snapshot_drops_new_field(tmp_path, source, monkeypatch):
    solver, calls, env, run = batch(tmp_path, source, monkeypatch, 'common_priority_v1')
    expand = env['expand_batch']
    def omit_snapshot_field(*args):
        args = list(args)
        args[-1] = {k:v for k,v in args[-1].items() if k != 'selection_coupling'}
        return expand(*args)
    env['expand_batch'] = omit_snapshot_field
    def before_execution(*args): raise RuntimeError('artificial stop before execution')
    monkeypatch.setattr(env['CandidateLedger'], 'begin_execution', before_execution)
    with pytest.raises(RuntimeError, match='artificial stop'): run()
    before = read_batch(tmp_path)
    solver.cfg.selection_coupling = 'independent_subset_v2'
    with pytest.raises(RuntimeError): run()
    assert read_batch(tmp_path) == before
    assert calls == {'generation': 3, 'critic': 3, 'execution': 0}


def test_unknown_coupling_fails_before_any_generation(tmp_path, source, monkeypatch):
    _, calls, _, run = batch(tmp_path, source, monkeypatch, 'unrecognized')
    with pytest.raises(RuntimeError, match='unsupported selection coupling'): run()
    assert calls == {'generation': 0, 'critic': 0, 'execution': 0}


def test_full_pool_common_coupling_agrees_with_random(tmp_path, source, monkeypatch):
    _, _, _, run = batch(tmp_path, source, monkeypatch, 'common_priority_v1', top_k=3)
    run()
    assert read_batch(tmp_path)['selected'] == prototype.choose_slots(3, 3, 1, 'uniform_random', 6, 'artificial', 1)


def test_dataclass_default_and_validation(source):
    parsed = ast.parse(read(source['source_tree'], CONFIG))
    klass = next(n for n in parsed.body if isinstance(n, ast.ClassDef))
    env = dict(dataclass=dataclasses.dataclass, field=dataclasses.field, MISSING='???',
               MCTSSolverConfig=type('MCTSSolverConfig', (), {'validate': lambda self: None}))
    exec(compile(ast.Module(body=[klass], type_ignores=[]), CONFIG, 'exec'), env)
    cfg = env['ForeTSSolverConfig']()
    assert cfg.selection_coupling == 'independent_subset_v2'
    cfg.selection_policy='uniform_random'; cfg.selector_seed=8
    cfg.num_children=4; cfg.critic_top_k=2; cfg.num_children_to_choose=1; cfg.critic_max_attempts=1; cfg.uct_c=0.25
    cfg.validate()
    cfg.selection_coupling='common_priority_v1'; cfg.validate()
    cfg.selection_coupling='unknown'
    with pytest.raises(ValueError, match='unsupported selection coupling'): cfg.validate()
