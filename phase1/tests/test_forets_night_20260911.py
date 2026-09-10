"""New CPU checks only: budget projection and undeployed selector integration."""
import io
import json
from pathlib import Path
import sys
import tarfile
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import inspect_senior_budget_20260911 as budget
from phase1.forets_common_priority import choose_slots
from phase1.tests.test_forets_selection_20260908 import fixture, read_batch, Journal
from phase1.forets_next_budget_20260911 import plan, structural_paths

TREE = 'bbd22e323d6321925a145c12bdc02445c1ad80f4'


def test_planning_has_equal_caps_balanced_order_and_no_dispatch():
    p = plan()
    assert p['runs'] == 8 and p['pairs'] == 4
    assert p['status'] == 'DRAFT_NOT_SUBMITTABLE'
    assert p['gpu_submissions'] == p['api_requests'] == p['model_fits'] == 0
    for offset in range(0, 8, 2):
        a, b = p['matrix'][offset:offset+2]
        assert a['seed'] == b['seed'] and a['task'] == b['task']
        assert {a['arm'], b['arm']} == {'uniform_random', 'critic_topk_random'}
    assert sum(r['arm'] == 'uniform_random' for r in p['matrix'][::2]) == 2
    assert p['all_blocks_nominal_gpu_hours'] == 17


def test_core_attempt_arithmetic_includes_parse_transport_and_debug():
    paths = structural_paths(5)
    assert all(a == 5 for _, a, _ in paths)
    assert max(g for g, _, _ in paths) == 14
    assert max(n for _, _, n in paths) == 3
    assert max((2*g + a)*3 for g, a, _ in paths) == 99
    assert plan()['max_api_attempts_per_run'] >= 99


def config(**extra):
    return json.dumps({'metadata': {'git_commit_id': 'a'*40},
                       'solver': {'num_children': 2, 'step_limit': 20, **extra}}).encode()


def test_projection_does_not_guess_solver_from_budget_or_default():
    result = budget.budget_projection(config())
    assert result['step_limit'] == 20 and result['num_children'] == 2
    assert result['execution_timeout'] is None
    assert result['declared_solver_type_fields'] == {}


def test_projection_preserves_explicit_type_only():
    raw = config(_dojo_dataclass_type='dojo.config_dataclasses.solver.mcts:MCTSSolverConfig')
    assert budget.budget_projection(raw)['declared_solver_type_fields']


@pytest.mark.parametrize('bad', [True, float('nan'), -1, '${solver.limit}'])
def test_bad_budget_fails_without_imputing(bad):
    with pytest.raises(ValueError): budget.budget_projection(config(step_limit=bad))


def test_archive_only_opens_configs_not_other_bodies(tmp_path):
    file = tmp_path/'artificial.tar.gz'
    with tarfile.open(file, 'w:gz') as archive:
        for name, body in [('run/dojo_config.json', config()),
                           ('run/checkpoint/journal.jsonl', b'must not parse this'),
                           ('run/env_variables.json', b'must not open this')]:
            info = tarfile.TarInfo(name); info.size = len(body)
            archive.addfile(info, io.BytesIO(body))
        link = tarfile.TarInfo('run/unopened'); link.type = tarfile.SYMTYPE
        link.linkname = '/outside/must-not-read'
        archive.addfile(link)
    original = tarfile.TarFile.extractfile
    opened = []
    def guarded(self, member, *args, **kwargs):
        assert member.name.endswith('/dojo_config.json')
        opened.append(member.name)
        return original(self, member, *args, **kwargs)
    with patch.object(tarfile.TarFile, 'extractfile', guarded):
        rows, orphan = budget.inspect(file)
    assert opened == ['run/dojo_config.json'] and not orphan
    assert rows[0][2] == {'journal_header': 1, 'unopened_link': 1}


@pytest.mark.parametrize('seed', [6, 7])
@pytest.mark.parametrize('exclude_random', [False, True])
def test_current_real_batch_common_order_changes_only_if_excluded(tmp_path, monkeypatch, seed, exclude_random):
    monkeypatch.setenv('FORETS_SELECTION_TREE', TREE)
    random_slot = choose_slots(3, 2, 1, 'uniform_random', seed, 'artificial', 1)[0]
    eligible = ([i for i in range(3) if i != random_slot] if exclude_random
                else [random_slot, (random_slot+1) % 3])
    scores = [1. if i in eligible else 0. for i in range(3)]
    records = []
    for policy in ('uniform_random', 'critic_topk_random'):
        root = tmp_path/policy
        solver, calls, env, run = fixture(root, policy, count=3, top_k=2, choose=1)
        solver.cfg.selector_seed = seed
        solver.cfg.step_limit = 4; solver.state.current_step = 1
        solver.journal_for_unselected = Journal(solver.root_node)
        solver.journal_for_unselected.nodes.clear()
        # Replace only a callable in the synthetic fixture's namespace. No
        # production module, historical ledger or default is patched on disk.
        env['choose_slots'] = choose_slots
        original = solver._query_critic
        async def score(node):
            await original(node)
            return scores[int(node.id)]
        solver._query_critic = score
        run()
        records.append(read_batch(root))
        assert calls == {'generation': 3, 'critic': 3 if policy == 'critic_topk_random' else 0, 'execution': 1}
        assert len(solver.journal_for_unselected.nodes) == 2
        assert len(solver.journal.nodes) == 2
    assert records[0]['pool_sha256'] == records[1]['pool_sha256']
    assert records[0]['selected'] == [random_slot]
    assert (records[0]['selected'] != records[1]['selected']) == exclude_random
    assert records[1]['selected'][0] in eligible
    assert records[0]['phase'] == records[1]['phase'] == 'complete'
