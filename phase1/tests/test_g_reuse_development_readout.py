from copy import deepcopy
from fractions import Fraction
import hashlib
import json
from pathlib import Path

import pytest

from phase1.g_reuse_development_readout import evaluate_development, KEYS, PROTOCOL_SHA256, FULL
from phase1.g_reuse_effect_readout_statistics import ReadoutError


def sha(s): return hashlib.sha256(s.encode()).hexdigest()


def rows_fixture(counts=(3, 9, 2), gains=(1, 1)):
    rows = []
    for task, count in enumerate(counts):
        for i in range(count):
            margins = {'Lbudget|6': 0, 'Lbudget|7': 0, f'{FULL}|6': gains[0], f'{FULL}|7': gains[1], 'tfidf': 1}
            rows.append(dict(pair_sha256=sha(f'p{task}-{i}'), task_sha256=sha(f't{task}'),
                parent_sha256=sha(f'parent{task}'), run_sha256=sha(f'run{task}'), truth_sign=1, margins=margins))
    return rows


def evaluate(rows):
    return evaluate_development(rows, protocol_sha256=PROTOCOL_SHA256,
        fit_status={key: 'COMPLETED' for key in KEYS-{'tfidf'}})


def test_bound_screen_protocol_unchanged():
    path = Path(__file__).parents[1]/'g_reuse_development_screen_v1.json'
    assert hashlib.sha256(path.read_bytes()).hexdigest() == PROTOCOL_SHA256


def test_known_positive_and_tfidf_not_used_to_rescue():
    result = evaluate(rows_fixture())
    primary = result['primary_full_minus_lbudget']
    assert primary['point'] == .5 and primary['task_clustered_descriptive_ci95'] == [.5, .5]
    assert primary['loto_minimum'] == .5 and primary['seed_effects'] == {'6': .5, '7': .5}
    assert result['descriptive_full_minus_tfidf']['point'] == 0
    assert result['decision'] == 'POSITIVE_DEVELOPMENT_SCREEN_ONLY'
    assert not result['confirmatory_claim_allowed'] and not result['automatic_gpu_expansion_allowed']


@pytest.mark.parametrize('gains,expected', [((-1, -1), 'BOTH_SEEDS_NONPOSITIVE_NO_ESCALATION'),
    ((1, -1), 'INCONCLUSIVE_NO_AUTOMATIC_EXPANSION'), ((0, 0), 'BOTH_SEEDS_NONPOSITIVE_NO_ESCALATION')])
def test_negative_mixed_and_ties(gains, expected):
    assert evaluate(rows_fixture(gains=gains))['decision'] == expected


def test_independent_fraction_task_not_pair_weighting_and_loto():
    rows = rows_fixture(counts=(10, 2, 1))
    for row in rows:
        if row['task_sha256'] != sha('t0'):
            row['margins'][f'{FULL}|6'] = -1
            row['margins'][f'{FULL}|7'] = -1
    result = evaluate(rows)['primary_full_minus_lbudget']
    expected = (Fraction(1, 2)-Fraction(1, 2)-Fraction(1, 2))/3
    assert result['point'] == float(expected)
    assert result['loto_minimum'] == -.5
    assert sum(.5 if r['task_sha256'] == sha('t0') else -.5 for r in rows)/len(rows) > 0


def test_order_and_orientation_invariance():
    rows = rows_fixture(gains=(1, -1))
    expected = evaluate(rows)
    swapped = deepcopy(rows[::-1])
    for row in swapped:
        row['truth_sign'] *= -1
        row['margins'] = {k: -v for k, v in row['margins'].items()}
    assert evaluate(swapped) == expected


@pytest.mark.parametrize('failure', ['duplicate', 'missing_seed', 'extra_seed', 'nan', 'boolean', 'sign', 'parent', 'run'])
def test_bad_inputs_fail_closed(failure):
    rows = rows_fixture()
    if failure == 'duplicate': rows.append(deepcopy(rows[0]))
    if failure == 'missing_seed': rows[0]['margins'].pop('Lbudget|6')
    if failure == 'extra_seed': rows[0]['margins']['Lbudget|8'] = 1
    if failure == 'nan': rows[0]['margins']['tfidf'] = float('nan')
    if failure == 'boolean': rows[0]['margins']['tfidf'] = True
    if failure == 'sign': rows[0]['truth_sign'] = True
    if failure == 'parent': rows[-1]['parent_sha256'] = rows[0]['parent_sha256']
    if failure == 'run': rows[-1]['run_sha256'] = rows[0]['run_sha256']
    with pytest.raises(ReadoutError): evaluate(rows)


def test_incomplete_not_classified_as_method_failure():
    statuses = {key: 'COMPLETED' for key in KEYS-{'tfidf'}}
    statuses['Lbudget|6'] = 'CHECKPOINTED_NOT_COMPLETED'
    with pytest.raises(ReadoutError, match='incomplete_fit'):
        evaluate_development(rows_fixture(), protocol_sha256=PROTOCOL_SHA256, fit_status=statuses)


def test_exact_two_percent_boundary_not_lost_to_subtraction_roundoff():
    rows = rows_fixture(counts=(50, 50))
    for row in rows:
        row['margins'].update({'Lbudget|6': 1, 'Lbudget|7': 1})
    for index in (0, 50):
        rows[index]['margins'].update({'Lbudget|6': -1, 'Lbudget|7': -1})
    result = evaluate(rows)
    assert result['primary_full_minus_lbudget']['point'] == .02
    assert result['decision'] == 'POSITIVE_DEVELOPMENT_SCREEN_ONLY'
    json.dumps(result, allow_nan=False)
