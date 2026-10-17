"""Bounded descriptive ensemble baseline on three CLOSED, pinned DEV libraries.

Never a fresh-holdout test: the original search already used these D_search
references. Split sensitivity is explicitly post-adaptive. No new GPU/model
calls, generated programs, original artifact writes or policy-benefit claims.
"""
import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path
import re
import time

import numpy as np
import pandas as pd
from PIL import Image
from sklearn.metrics import roc_auc_score

BASE = Path('/research/d7/spc/yzyang4')
TASKS = ('aerial-cactus-identification', 'denoising-dirty-documents')
SPECS = (
 (18770, 'scheduling-pooling-20261016-v3', 'adaptation-lineage-extension-20261017.safe.json', 'ce2df3e9c801da6c1a8e407d542f963d61c47d9fcde807c52b15c2308e14e644'),
 (18807, 'scheduling-colocation-20261016-v1', 'adaptation-lineage-extension-20261017.safe.json', 'b47201384f5d3c385f471becba37bb2f546747de89a529f55d48f0ff9a264430'),
 (18997, 'scheduling-selective-20261017-v1', 'adaptation-lineage-20261017.safe.json', '6ec665d244a8cd54820542b175526975d2a13ed24a0185ddd56a7d8dd2d19698'),
)
SECRET = re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,}|Bearer\s+[a-z0-9_.-]{20,})')


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(8 * 1024**2), b''): h.update(chunk)
    return h.hexdigest()


def read(path):
    raw = Path(path).read_bytes()
    assert not SECRET.search(raw), 'credential-shaped metadata refused'
    return json.loads(raw)


def metric(y, pred, task):
    return float(roc_auc_score(y, pred)) if task == TASKS[0] else float(np.sqrt(np.mean((y-pred)**2)))


def prediction(path, digest, ids, field):
    assert sha(path) == digest
    frame = pd.read_csv(path, dtype={'id': str})
    assert list(frame.columns) == ['id', field]
    assert len(frame) == len(ids) and not frame.id.isna().any() and not frame.id.duplicated().any()
    assert set(frame.id) == set(ids)
    values = frame.set_index('id').loc[ids, field].to_numpy(dtype=np.float64)
    assert np.isfinite(values).all() and (values >= 0).all() and (values <= 1).all()
    return values


def reference(root, task, spec):
    view = Path(spec[task]['view'])
    if not view.is_absolute(): view = root / view
    assert view.resolve() == (root / 'dev-views' / task).resolve()
    assert sha(view / 'manifest.json') == spec[task]['view_sha']
    m = read(view / 'manifest.json')
    assert m['not_official_test'] and m['not_confirmation'] and m['reserved_content_not_copied']
    assert m['split_seed'] == 'r14-image-dev-20261011'
    query = m['query_ids']
    assert not set(query) & (set(m['train_ids']) | set(m['reserved_ids']))
    names = {'labels.csv'} if task == TASKS[0] else set(query)
    assert set(m['search_reference_files']) == names
    for name, h in m['search_reference_files'].items():
        assert Path(name).name == name and sha(view / 'search-reference' / name) == h
    ids = pd.read_csv(view / 'public/test.csv', dtype={'id': str}).id.tolist()
    assert len(ids) == len(set(ids))
    if task == TASKS[0]:
        frame = pd.read_csv(view / 'search-reference/labels.csv', dtype={'id': str})
        assert set(frame.id) == set(query) == set(ids)
        y = frame.set_index('id').loc[ids, 'has_cactus'].to_numpy()
        groups = ids
    else:
        y, expected, groups = [], [], []
        for name in query:
            with Image.open(view / 'search-reference' / name) as im:
                assert list(im.size) == m['query_dimensions'][name]
                a = np.asarray(im.convert('L'), dtype=np.float64) / 255.0
            key = str(int(Path(name).stem))
            y.append(a.ravel())
            expected.extend(f'{key}_{r+1}_{c+1}' for r in range(a.shape[0]) for c in range(a.shape[1]))
            groups.extend([key] * a.size)
        assert ids == expected, 'reference must match canonical image/pixel IDs'
        y = np.concatenate(y)
    # Freeze split by whole image, never split correlated document pixels.
    group_ids = sorted(set(groups), key=lambda k: hashlib.sha256(('closed-ensemble-sensitivity-v1:' + k).encode()).digest())
    assert len(group_ids) >= 4
    left = set(group_ids[:len(group_ids)//2])
    masks = (np.array([x in left for x in groups]), np.array([x not in left for x in groups]))
    assert all(mask.any() for mask in masks) and not (masks[0] & masks[1]).any()
    if task == TASKS[0]: assert all(set(y[mask]) == {0, 1} for mask in masks)
    return ids, y, masks, len(group_ids), [len(left), len(group_ids)-len(left)]


def compare(matrix, y, masks, task):
    n = len(matrix)
    sign = 1 if task == TASKS[0] else -1
    singles = [metric(y, x, task) for x in matrix]
    best = max(singles, key=lambda x: sign*x)
    uniform = matrix.mean(axis=0)
    full = dict(best_single=best, uniform=metric(y, uniform, task))
    # Oracle among observed equal pairs is an opportunity diagnostic, not a policy.
    pairs = [metric(y, (matrix[i]+matrix[j])/2, task) for i, j in itertools.combinations(range(n), 2)]
    full['oracle_equal_pair'] = max(pairs, key=lambda x: sign*x) if pairs else best
    full['uniform_gain'] = sign*(full['uniform']-best)
    full['oracle_pair_gain'] = sign*(full['oracle_equal_pair']-best)
    sensitivity = []
    for fit, check in ((masks[0], masks[1]), (masks[1], masks[0])):
        fit_scores = [metric(y[fit], x[fit], task) for x in matrix]
        order = sorted(range(n), key=lambda i: (-sign*fit_scores[i], i))
        selected = matrix[order[0]]
        top2 = matrix[order[:2]].mean(axis=0)
        # Classic selection with replacement; exactly20steps, best fit prefix.
        total = np.zeros_like(y, dtype=np.float64)
        best_fit = -math.inf
        greedy = None
        chosen_counts = np.zeros(n, dtype=int)
        best_counts = None
        for step in range(20):
            values = [sign*metric(y[fit], (total[fit]+x[fit])/(step+1), task) for x in matrix]
            chosen = max(range(n), key=lambda i: (values[i], -i))
            total += matrix[chosen]
            chosen_counts[chosen] += 1
            if values[chosen] > best_fit:
                best_fit = values[chosen]
                greedy = total/(step+1)
                best_counts = chosen_counts.copy()
        # Separate weighted-sum reconstruction catches incremental weighting errors.
        recomposed = np.average(matrix, axis=0, weights=best_counts)
        assert np.max(np.abs(greedy-recomposed)) < 1e-12
        values = {k: metric(y[check], v[check], task) for k, v in
                  (('selected_single', selected), ('uniform', uniform), ('top2', top2), ('greedy20', greedy))}
        sensitivity.append(dict(values=values,
            gains={k: sign*(v-values['selected_single']) for k, v in values.items() if k != 'selected_single'},
            fit_rows=int(fit.sum()), check_rows=int(check.sum())))
    return dict(full_development=full, post_adaptive_resplit_sensitivity=sensitivity, single_scores=singles)


def analyze(output):
    start = time.monotonic()
    all_rows, source_hashes = [], {}
    for job, name, lineage_file, pin in SPECS:
        root = BASE / name
        assert sha(root / lineage_file) == pin
        origin = read(root / lineage_file)
        assert origin['assigned'] == read(root / 'closed.json')['complete'] == 32
        assert sha(root / 'plan.json') == origin['plan_sha256']
        plan = read(root / 'plan.json')
        assert sha(root / 'warm-receipt.json') == plan['common_start_receipt_sha256']
        warm = read(root / 'warm-receipt.json')
        spec = read(root / 'dev-views/spec.json')
        source_hashes[name] = dict(plan=origin['plan_sha256'], lineage=pin, warm=sha(root/'warm-receipt.json'))
        for task in TASKS:
            ids, y, masks, group_count, split_group_counts = reference(root, task, spec)
            field = 'has_cactus' if task == TASKS[0] else 'value'
            scorefield = 'auc' if task == TASKS[0] else 'rmse'
            w = warm[task]
            wr = Path(w['root'])
            assert wr == BASE / 'scheduling-image-live-2plus4-20261011-v3'
            assert sha(wr / 'plan.json') == '95825b54b256eb69f7a2a372db66c4f63b4c0d9840d3253f5ade5685f448fe66'
            warm_paths = []
            for path in sorted((wr / f'episode-{w["run"]}').glob('scored-*.json')):
                if any(sha(path) == rec['receipt_sha256'] for rec in w['grounded']):
                    rec = read(path)['receipt']
                    assert rec['view_manifest_sha256'] == spec[task]['view_sha']
                    warm_paths.append((path.with_suffix('.private.csv'), rec['submission_sha256']))
            assert warm_paths and len(set(h for _, h in warm_paths)) == 1
            wp, wh = warm_paths[0]
            warm_pred = prediction(wp, wh, ids, field)
            assert abs(metric(y, warm_pred, task)-w['score']) < 1e-12
            for block in range(4):
                library = [(wh, warm_pred)]
                selected = [c for c in origin['candidates'] if c['block'] == block and c['task'] == task and c['valid']]
                for c in selected:
                    rel = f'episode-{c["index"]}/candidate-{c["candidate"]}.json'
                    assert sha(root / rel) == origin['source_hashes'][rel]
                    candidate = read(root / rel)
                    assert candidate['elapsed_seconds'] <= 1020 and candidate['exit_code'] == 0 and not candidate['timed_out']
                    target = candidate['aux']['submission_sha256']
                    files = []
                    for path in sorted((root / f'episode-{c["index"]}').glob('scored-*.json')):
                        rec = read(path)['receipt']
                        if rec['submission_sha256'] == target:
                            assert rec['split'] == 'D_search_development_only' and rec['view_manifest_sha256'] == spec[task]['view_sha']
                            assert abs(rec[scorefield]-c['score']) < 1e-12
                            files.append(path.with_suffix('.private.csv'))
                    assert files
                    if target not in {h for h, _ in library}:
                        pred = prediction(files[0], target, ids, field)
                        assert abs(metric(y, pred, task)-c['score']) < 1e-12
                        library.append((target, pred))
                result = compare(np.array([p for _, p in library]), y, masks, task)
                group = next(g for g in origin['groups'] if g['block'] == block and g['task'] == task)
                assert abs(result['full_development']['best_single']-group['final_best']) < 1e-12
                row = dict(job=job, block=block, task=task, assigned_runs=4, timely_valid_candidates=len(selected),
                           library_size=len(library), prediction_hashes=[h for h, _ in library],
                           query_groups=group_count, split_group_counts=split_group_counts, **result)
                all_rows.append(row)
                print(json.dumps(dict(job=job, block=block, task=task, library_size=len(library), done=True)), flush=True)
        assert sha(root / lineage_file) == pin and sha(root / 'plan.json') == origin['plan_sha256']
    result = dict(schema=1, source_sha256=sha(__file__), elapsed_cpu_host_wall_seconds=time.monotonic()-start,
                  assigned_runs=96, task_pools=24, source_hashes=source_hashes, rows=all_rows,
                  methods=['best_single', 'uniform', 'top2', 'classic_greedy20', 'observed_oracle_equal_pair'],
                  limits=['All three closed valid DEV batches and all24task-pools; not cherry-picked winners.',
                          'No cross-pool libraries. Duplicated prediction bytes deduplicated; warm included and common sunk cost remains.',
                          'Existing search used D_search adaptively. Image-group resplit is sensitivity, NOT fresh generalization or confirmation.',
                          'Equal-pair oracle is post-hoc observed-library potential, NOT a global upper bound or deployable policy.',
                          'Extra CPU aggregation/selection cost measured, NOT charged to closed batches retroactively; no same-budget E2E claim.',
                          'Classic ensemble baselines are prior art, not method novelty. No labels or predictions exported.',
                          'New quota batch and invalid19004 not read; original frozen quality gates unchanged.'])
    with output.open('x') as f: json.dump(result, f, sort_keys=True, indent=2, allow_nan=False)
    print(json.dumps(dict(output_sha256=sha(output), task_pools=24, assigned_runs=96, completed=True)), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    analyze(args.output)
