"""Join four frozen model scorers plus TF-IDF before admitting dev truths.

Pure in-memory schema/coverage operations; no checkpoint or dataset admission.
The separately reviewed caller owns all final-checkpoint locks and provenance.
"""
import math

from phase1.g_reuse_development_readout import KEYS, PROTOCOL_SHA256, validate
from phase1.g_reuse_effect_readout_statistics import is_sha, require

PAIR_KEYS = {'pair_sha256', 'task_sha256', 'parent_sha256', 'run_sha256', 'a', 'b'}


def blind_development_margins(pairs, by_model):
    require(type(pairs) is list and bool(pairs), 'development_pair_projection')
    seen = set(); edges = set(); endpoints = set()
    for row in pairs:
        require(type(row) is dict and set(row) == PAIR_KEYS, 'development_blind_pair_schema')
        require(all(is_sha(row[k]) for k in PAIR_KEYS-{'a', 'b'}), 'development_blind_identity')
        require(all(type(row[k]) is str and bool(row[k]) for k in ('a', 'b')) and row['a'] < row['b'],
                'development_canonical_orientation')
        require(row['pair_sha256'] not in seen and (row['a'], row['b']) not in edges, 'development_duplicate_edge')
        seen.add(row['pair_sha256']); edges.add((row['a'], row['b'])); endpoints.update((row['a'], row['b']))
    require(type(by_model) is dict and set(by_model) == KEYS, 'development_frozen_model_matrix')
    for values in by_model.values():
        require(type(values) is dict and set(values) == endpoints, 'development_endpoint_coverage')
        require(all(type(v) in (int, float) and math.isfinite(float(v)) for v in values.values()), 'development_endpoint_score')
    result = []
    for row in sorted(pairs, key=lambda r: r['pair_sha256']):
        margins = {key: by_model[key][row['a']]-by_model[key][row['b']] for key in sorted(KEYS)}
        require(all(math.isfinite(float(x)) for x in margins.values()), 'development_margin_overflow')
        result.append({**{k: row[k] for k in PAIR_KEYS-{'a', 'b'}}, 'margins': margins})
    return result


def join_development_truth(blinded, true_sign_by_pair):
    require(type(blinded) is list and bool(blinded), 'development_blind_rows')
    expected = {'pair_sha256', 'task_sha256', 'parent_sha256', 'run_sha256', 'margins'}
    require(all(type(row) is dict and set(row) == expected for row in blinded), 'development_blind_rows_schema')
    keys = {row['pair_sha256'] for row in blinded}
    require(len(keys) == len(blinded), 'development_duplicate_blind_pair')
    require(type(true_sign_by_pair) is dict and set(true_sign_by_pair) == keys, 'development_exact_truth_support')
    rows = [{**row, 'margins': dict(row['margins']), 'truth_sign': true_sign_by_pair[row['pair_sha256']]} for row in blinded]
    validate(rows, protocol_sha256=PROTOCOL_SHA256)
    return rows
