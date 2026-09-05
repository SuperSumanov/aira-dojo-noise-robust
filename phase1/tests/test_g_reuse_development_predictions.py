from copy import deepcopy
import hashlib
import pytest

from phase1.g_reuse_development_predictions import blind_development_margins, join_development_truth
from phase1.g_reuse_development_readout import KEYS
from phase1.g_reuse_effect_readout_statistics import ReadoutError


def fixture():
    sha = lambda x: hashlib.sha256(x.encode()).hexdigest()
    pairs = [dict(pair_sha256=sha(f'p{i}'), task_sha256=sha(f't{i}'), parent_sha256=sha(f'parent{i}'),
                  run_sha256=sha(f'run{i}'), a=f'a{i}', b=f'b{i}') for i in range(2)]
    scores = {key: {'a0': 2, 'b0': -1, 'a1': 3, 'b1': 4} for key in KEYS}
    return pairs, scores


def test_blind_join_then_exact_truth_and_no_mutation():
    pairs, scores = fixture(); old = deepcopy((pairs, scores))
    blind = blind_development_margins(pairs, scores)
    assert all('truth_sign' not in row and 'a' not in row for row in blind)
    targets = {p['pair_sha256']: 1 for p in pairs}
    actual = join_development_truth(blind, targets)
    expected = {pairs[0]['pair_sha256']: 3, pairs[1]['pair_sha256']: -1}
    assert all(set(row['margins'].values()) == {expected[row['pair_sha256']]} for row in actual)
    assert (pairs, scores) == old and all('truth_sign' not in row for row in blind)


@pytest.mark.parametrize('failure', ['missing_model', 'extra_model', 'endpoint', 'reverse', 'duplicate_edge', 'truth', 'nan', 'overflow'])
def test_invalid_blind_projection(failure):
    pairs, scores = fixture()
    if failure == 'missing_model': scores.pop('Lbudget|6')
    if failure == 'extra_model': scores['Lbudget|8'] = scores['Lbudget|6']
    if failure == 'endpoint': scores['tfidf'].pop('a0')
    if failure == 'reverse': pairs[0]['a'], pairs[0]['b'] = pairs[0]['b'], pairs[0]['a']
    if failure == 'duplicate_edge': pairs[1]['a'], pairs[1]['b'] = pairs[0]['a'], pairs[0]['b']
    if failure == 'truth': pairs[0]['truth_sign'] = 1
    if failure == 'nan': scores['tfidf']['a0'] = float('nan')
    if failure == 'overflow': scores['tfidf'].update(a0=1e308, b0=-1e308)
    with pytest.raises(ReadoutError): blind_development_margins(pairs, scores)


def test_truth_extra_or_missing_not_silently_inner_joined():
    pairs, scores = fixture(); blind = blind_development_margins(pairs, scores)
    for targets in ({}, {p['pair_sha256']: 1 for p in pairs}|{'unexpected': 1}):
        with pytest.raises(ReadoutError, match='exact_truth_support'): join_development_truth(blind, targets)
