import copy
import pytest

from phase1.historical_global_local_source_gate import project_cards, project_batches, summarize
from phase1.historical_global_local_pool_readiness import project_pairs
from phase1.verify_historical_global_local_source_gate import recompute


def fixture():
    def card(cid, config):
        return dict(id=cid, task={'name': 't'}, client=config, hardware='cpu', time_limit=10, execution_timeout=2)
    grouped = {'r1': [card('a', 'x'), card('b', 'x'), card('c', 'x')],
               'r2': [card('d', 'y'), card('e', 'y')],
               'r3': [card('f', 'x')], 'r4': [card('g', 'x')]}
    rows = [dict(run_id=r, task='t', original_hold=False, source_match_status=s,
                 source_candidate_batches=n, source_day=None, batch_sha256=h)
            for r, s, n, h in [('r1', 'unique', 1, 'a'*64), ('r2', 'ambiguous', 2, None),
                                ('r3', 'unique', 1, 'a'*64), ('r4', 'missing', 0, None)]]
    l = [('a', 'b'), ('d', 'e')]
    g = [('a', 'c'), ('a', 'd'), ('a', 'b'), ('a', 'f'), ('a', 'missing')]
    return grouped, rows, g, l


def compare(grouped, rows, g, l):
    actual = summarize(g, l, project_cards(grouped), project_batches(rows))
    pair_rows = lambda ps: [dict(better=a, worse=b, intask_split='train') for a, b in ps]
    assert actual == recompute(grouped, rows, pair_rows(g), pair_rows(l))
    return actual


def test_applicability_not_eligibility():
    r = compare(*fixture())
    assert r['global_candidate']['rows'] == 2
    assert r['global_candidate']['unequal_observed_config_pairs'] == 1
    assert r['global_candidate']['unresolved_source_pairs'] == 1
    assert r['known_source_batches_shared_with_outside_local_train'] == 1
    assert r['outside_local_train_is_not_assumed_to_be_dev_or_test']
    assert not r['effect_authorized'] and not r['experiment_closed_split_verified']


def test_missing_config_cannot_count_as_complete():
    grouped, rows, g, l = fixture()
    grouped['r1'][0]['client'] = None
    result = compare(grouped, rows, g, l)
    assert result['global_candidate']['incomplete_observed_config_pairs'] == 2
    assert result['train_runs_with_varying_observed_config'] == 1


def test_orientation_order_and_unrelated_values_invariant():
    grouped, rows, g, l = fixture()
    original = compare(grouped, rows, g, l)
    for cards in grouped.values():
        for c in cards:
            c.update(code='DO_NOT_USE', grade=123456, outcome={'forbidden': True})
    assert compare(grouped, rows[::-1], g[::-1], l[::-1]) == original
    import json
    assert project_pairs(json.dumps(dict(better='b', worse='a', intask_split='train'))) == [('a','b')]


@pytest.mark.parametrize('failure', ['duplicate', 'missing', 'status', 'task'])
def test_bad_provenance_rejected(failure):
    grouped, rows, g, l = fixture()
    if failure == 'duplicate': rows.append(copy.deepcopy(rows[0]))
    if failure == 'missing': rows.pop()
    if failure == 'status': rows[1]['batch_sha256'] = 'b'*64
    if failure == 'task': rows[0]['task'] = 'wrong'
    with pytest.raises(ValueError):
        summarize(g, l, project_cards(grouped), project_batches(rows))


def test_duplicate_candidate_never_silently_deduped():
    grouped, rows, g, l = fixture()
    g.append(g[0])
    with pytest.raises(ValueError): compare(grouped, rows, g, l)
