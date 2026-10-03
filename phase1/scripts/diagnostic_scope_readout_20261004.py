"""Frozen full-denominator public-OOF readout for diagnostic_scope_20261004.

No hidden evaluator is imported. Raw arrays and public-training labels stay
remote. A scope effect on internal CV is NOT an agent or deployment benefit.
"""
import argparse
import csv
import datetime
import hashlib
import json
from pathlib import Path
import statistics

import numpy as np
from sklearn.metrics import roc_auc_score

ROOT = Path('/research/d7/spc/yzyang4/diagnostic-scope-20261004-v1')
PUBLIC = Path('/research/d7/spc/yzyang4/search-only-dev-pizza-20260927-v1/public')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def write(path, obj):
    with path.open('x') as f:
        json.dump(obj, f, indent=2, sort_keys=True, allow_nan=False)


def auc_pairs(y, values):
    """Pair count via sorted negatives, independent of sklearn's rank ROC."""
    pos = np.asarray(values)[np.asarray(y) == 1]
    neg = np.sort(np.asarray(values)[np.asarray(y) == 0])
    assert len(pos) and len(neg)
    left = np.searchsorted(neg, pos, side='left')
    right = np.searchsorted(neg, pos, side='right')
    return float((left.sum() + (right-left).sum()/2)/(len(pos)*len(neg)))


def tests():
    rng = np.random.default_rng(106511)
    checked = 0
    for n in range(2, 31):
        for _ in range(12):
            y = rng.integers(0, 2, n)
            if len(set(y)) < 2:
                continue
            p = rng.integers(-3, 4, n).astype(float)
            a = auc_pairs(y, p)
            b = roc_auc_score(y, p)
            assert abs(a-b) < 1e-12
            assert abs(auc_pairs(y, 2*p+7)-a) < 1e-12
            checked += 1
    assert auc_pairs([1, 0], [0.4, 0.4]) == 0.5
    assert auc_pairs([1, 0], [0.9, 0.1]) == 1
    assert auc_pairs([1, 0], [0.1, 0.9]) == 0
    assert statistics.variance([0.1, 0.3]) > 0
    return dict(random_tie_cases=checked, boundary_fixtures=3)


def freeze():
    assert not (ROOT/'launch.json').exists()
    result = tests()
    write(ROOT/'analysis-freeze.json', dict(status='FROZEN_BEFORE_SUBMISSION', utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        script_sha256=digest(Path(__file__)), plan_sha256=digest(ROOT/'plan.json'), tests=result,
        decision='Full10 denominator, four numeric OOF scope contrasts; zero omitted failures. Reference and text controls predeclared. No D_search reads, continuation or deployment claim.',
        material_threshold=0.01, seeds=[42, 173], confidence_intervals=False,
        text_setting_order=['maxf5000_word1to2', 'maxf10000_word1to2', 'maxf10000_word1to3', 'maxf20000_word1to3'],
        bounds='Post-outcome selected source checks. Seeds are public CV/model settings, not independent tasks. Historical agent behavior is not counterfactually rerun. All signs reported, including non-reversals.'))
    print(json.dumps(dict(status='ANALYSIS_FROZEN', plan_sha256=digest(ROOT/'plan.json'), tests=result)))


def sign(x):
    return 1 if x > 1e-12 else -1 if x < -1e-12 else 0


def summarize(values):
    if not values:
        return dict(n=0, median=None, sample_variance=None)
    return dict(n=len(values), median=statistics.median(values), sample_variance=statistics.variance(values) if len(values)>1 else None)


def analyze():
    p = read(ROOT/'plan.json')
    frozen = read(ROOT/'analysis-freeze.json')
    assert frozen['script_sha256'] == digest(Path(__file__))
    assert frozen['plan_sha256'] == digest(ROOT/'plan.json')
    assert (ROOT/'closed.json').is_file()
    for rel, expected in p['files'].items():
        assert digest(ROOT/rel) == expected, rel
    for rel, expected in p['public_data'].items():
        assert digest(PUBLIC/rel) == expected, rel
    # Public training labels only; never touch query labels or hidden scorer.
    public_y = np.asarray([int(r['requester_received_pizza']) for r in read(PUBLIC/'train.json')])
    rows, arrays, metas, sources = [], {}, {}, {}
    errors = []
    score_checks = []
    for slot in p['schedule']:
        i = slot['index']
        ep = ROOT/f'episode-{i}'
        result = read(ep/'action-0/result.json')
        assert all(result[k] == slot[k] for k in slot)
        assert result['plan_sha256'] == frozen['plan_sha256']
        assert result['code_sha256'] == digest(ROOT/'programs'/f'{i}.private.py')
        row = dict(**slot, task='random-acts-of-pizza', base_commit=p['base_commit'],
                   plan_sha256=frozen['plan_sha256'], seconds=result['seconds'], complete=result['complete'],
                   error_type=result['error_type'], exit_code=result['exit_code'], timed_out=result['timed_out'],
                   numeric_auc=None, feature_count=None)
        native = read(ep/'native.json')
        assert len(native['gpu_uuids']) == 1
        sources[str(i)] = dict(result_sha256=digest(ep/'action-0/result.json'), code_sha256=result['code_sha256'], artifacts=result['artifacts'], gpu_uuids=native['gpu_uuids'])
        if result['complete']:
            for name, expected in result['artifacts'].items():
                assert digest(ep/'action-0'/name) == expected
            with np.load(ep/'action-0/diagnostic_oof.npz', allow_pickle=False) as raw:
                a = {k:raw[k] for k in raw.files}
            meta = read(ep/'action-0/diagnostic_meta.json')
            assert all(meta[k] == slot[k] for k in ('case', 'seed', 'arm'))
            assert np.array_equal(a['y'], public_y)
            assert meta['rows'] == len(public_y)
            for name, values in a.items():
                assert values.shape == public_y.shape and np.all(np.isfinite(values))
                assert hashlib.sha256(np.ascontiguousarray(values).tobytes()).hexdigest() == meta['array_hashes'][name]
                if name == 'y':
                    continue
                left = float(roc_auc_score(public_y, values))
                right = auc_pairs(public_y, values)
                assert abs(left-right) < 1e-12 and abs(left-meta['scores'][name]) < 1e-12
                score_checks.append(abs(left-right))
            row.update(numeric_auc=meta['scores']['numeric'], feature_count=len(meta['columns']))
            arrays[i], metas[i] = a, meta
        rows.append(row)
    pairs = []
    for case in ('component_check', 'underfit_check'):
        for seed in (42, 173):
            subset = {r['arm']:r for r in rows if r['case']==case and r['seed']==seed}
            allrow, bounded = subset['all_numeric'], subset['deployment_scope']
            ref = next(r for r in rows if r['case']=='reference' and r['seed']==seed)
            row = dict(case=case, seed=seed, comparable=bool(allrow['complete'] and bounded['complete']),
                       all_auc=allrow['numeric_auc'], deployment_auc=bounded['numeric_auc'], reference_auc=ref['numeric_auc'],
                       inflation=None, text_exact=None, folds_equal=None, versions_equal=None, deployment_columns_equal_reference=None,
                       all_minus_reference=None, deployment_minus_reference=None, reference_sign_reversal=None,
                       all_minus_best_text=None, deployment_minus_best_text=None, text_rank_reversal=None)
            if row['comparable']:
                ai, bi = allrow['index'], bounded['index']
                ma, mb = metas[ai], metas[bi]
                aa, ab = arrays[ai], arrays[bi]
                text_keys = sorted(set(aa)-{'numeric','y'})
                assert set(aa) == set(ab)
                row.update(inflation=allrow['numeric_auc']-bounded['numeric_auc'],
                           text_exact=all(np.array_equal(aa[k],ab[k]) for k in text_keys),
                           folds_equal=ma['fold_hashes']==mb['fold_hashes'], versions_equal=ma['versions']==mb['versions'],
                           removed_fields=sorted(set(ma['columns'])-set(mb['columns'])),
                           removed_count=len(set(ma['columns'])-set(mb['columns'])),
                           added_count=len(set(mb['columns'])-set(ma['columns'])),
                           max_text_abs_diff=max(float(np.max(np.abs(aa[k]-ab[k]))) for k in text_keys))
                if not all(row[k] for k in ('text_exact','folds_equal','versions_equal')) or row['added_count']:
                    errors.append(dict(case=case,seed=seed,error='non_target_control_failed'))
                best_text_a = max(ma['scores'][k] for k in text_keys)
                best_text_b = max(mb['scores'][k] for k in text_keys)
                row['all_minus_best_text'] = row['all_auc']-best_text_a
                row['deployment_minus_best_text'] = row['deployment_auc']-best_text_b
                row['text_rank_reversal'] = sign(row['all_minus_best_text'])*sign(row['deployment_minus_best_text']) == -1
                if ref['complete']:
                    mr = metas[ref['index']]
                    row['deployment_columns_equal_reference'] = mb['columns'] == mr['columns']
                    row['reference_folds_equal'] = mb['fold_hashes'] == mr['fold_hashes']
                    row['all_minus_reference'] = row['all_auc']-row['reference_auc']
                    row['deployment_minus_reference'] = row['deployment_auc']-row['reference_auc']
                    row['reference_sign_reversal'] = sign(row['all_minus_reference'])*sign(row['deployment_minus_reference']) == -1
                    if not row['deployment_columns_equal_reference'] or not row['reference_folds_equal']:
                        errors.append(dict(case=case,seed=seed,error='reference_object_mismatch'))
            pairs.append(row)
    source_stats = {case:summarize([r['inflation'] for r in pairs if r['case']==case and r['inflation'] is not None]) for case in ('component_check','underfit_check')}
    ref42 = next(r for r in rows if r['case']=='reference' and r['seed']==42)
    result = dict(status='COMPLETE' if not errors else 'CONTROL_FAILURE', utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        plan_sha256=frozen['plan_sha256'], script_sha256=digest(Path(__file__)), assigned=len(rows), complete=sum(r['complete'] for r in rows),
        comparable_pairs=sum(r['comparable'] for r in pairs), controls=errors,
        scope_distortion_gate=not errors and all(r['comparable'] and r['inflation']>=0.01 for r in pairs),
        reference42_rounded_reproduction=None if ref42['numeric_auc'] is None else abs(ref42['numeric_auc']-0.677345)<=0.0000005,
        numeric_score_checks=len(score_checks), numeric_max_abs_error=max(score_checks,default=None),
        per_case=source_stats, pairs=pairs, rows=rows, input_sources=sources,
        scope='One task, two post-outcome selected diagnostic programs, two public-CV/model RNG settings. Classical component fits; no generation, no D_search, no final quality gain or agent behavior effect measured.',
        inference='Field-scope intervention can identify changes in these fixed diagnostic statistics when controls pass. It cannot identify the cause of original agent gains/failures or establish automatic detection, correction, novelty, or cross-task benefit.')
    out = ROOT/'readout-v1'
    out.mkdir()
    write(out/'summary.json',result)
    for name, data in [('runs.csv',rows),('pairs.csv',pairs)]:
        fields = sorted(set().union(*(set(r) for r in data)))
        with (out/name).open('x', newline='') as f:
            writer = csv.DictWriter(f,fieldnames=fields)
            writer.writeheader()
            writer.writerows(data)
    print(json.dumps({k:result[k] for k in ('status','assigned','complete','comparable_pairs','controls','scope_distortion_gate','reference42_rounded_reproduction','numeric_score_checks','numeric_max_abs_error','per_case','pairs')},ensure_ascii=False))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('mode',choices=['tests','freeze','analyze'])
    args = ap.parse_args()
    print(json.dumps(tests())) if args.mode=='tests' else globals()[args.mode]()
