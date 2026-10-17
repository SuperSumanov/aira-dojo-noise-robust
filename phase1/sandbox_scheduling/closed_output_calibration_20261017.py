"""Independent raw DEV Denoise reconstruction + predeclared affine baseline.

All12closed pools, two fixed image-group directions; no new programs/labels.
Independent Gram-matrix greedy implementation, not importing prior analyzer.
Still post-adaptive sensitivity, NOT fresh holdout or equal-budget E2E benefit.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import time

import numpy as np
import pandas as pd
from PIL import Image

BASE = Path('/research/d7/spc/yzyang4')
TASK = 'denoising-dirty-documents'
RECEIPT_PIN = '87480e08d6b41edfdf7dc73b7abba9ac351c3eeca50a036d85db2b8252266fd2'
SPECS = ((18770, 'scheduling-pooling-20261016-v3', 'adaptation-lineage-extension-20261017.safe.json'),
         (18807, 'scheduling-colocation-20261016-v1', 'adaptation-lineage-extension-20261017.safe.json'),
         (18997, 'scheduling-selective-20261017-v1', 'adaptation-lineage-20261017.safe.json'))
SECRET = re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,}|Bearer\s+[a-z0-9_.-]{20,})')


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(8388608), b''): h.update(b)
    return h.hexdigest()


def read(path):
    b = Path(path).read_bytes()
    assert not SECRET.search(b), 'credential-shaped metadata refused'
    return json.loads(b)


def load_prediction(path, pin, ids):
    assert digest(path) == pin
    df = pd.read_csv(path, dtype={'id': str})
    assert list(df.columns) == ['id', 'value']
    assert len(df) == len(ids) and not df.id.isna().any() and not df.id.duplicated().any()
    assert set(df.id) == set(ids)
    pred = df.set_index('id').loc[ids, 'value'].to_numpy(dtype=float)
    assert np.isfinite(pred).all() and pred.min() >= 0 and pred.max() <= 1
    return pred


def reference(root, pin):
    view = root / 'dev-views' / TASK
    assert digest(view/'manifest.json') == pin
    manifest = read(view/'manifest.json')
    assert manifest['not_official_test'] and manifest['not_confirmation'] and manifest['reserved_content_not_copied']
    assert manifest['split_seed'] == 'r14-image-dev-20261011'
    query = manifest['query_ids']
    assert not set(query).intersection(set(manifest['train_ids']) | set(manifest['reserved_ids']))
    assert set(query) == set(manifest['search_reference_files'])
    targets, ids, groups = [], [], []
    for name in query:
        assert Path(name).name == name
        source = view/'search-reference'/name
        assert digest(source) == manifest['search_reference_files'][name]
        with Image.open(source) as image:
            assert list(image.size) == manifest['query_dimensions'][name]
            pixels = np.asarray(image.convert('L'), dtype=np.float64)/255
        image_id = str(int(Path(name).stem))
        targets.append(pixels.reshape(-1))
        ids.extend(f'{image_id}_{row+1}_{col+1}' for row in range(pixels.shape[0]) for col in range(pixels.shape[1]))
        groups.extend([image_id]*pixels.size)
    assert pd.read_csv(view/'public/test.csv', dtype={'id': str}).id.tolist() == ids
    order = sorted(set(groups), key=lambda x: hashlib.sha256(('closed-ensemble-sensitivity-v1:'+x).encode()).digest())
    assert len(order) >= 4
    left = set(order[:len(order)//2])
    mask = np.fromiter((x in left for x in groups), dtype=bool, count=len(groups))
    return ids, np.concatenate(targets), (mask, ~mask)


def quadratic_greedy(g):
    """20selection steps/best fit prefix via residual Gram, deterministic ties."""
    n = len(g)
    counts = np.zeros(n)
    best_value = math.inf
    best_counts = None
    for step in range(1, 21):
        options = (counts[None, :] + np.eye(n))/step
        losses = np.einsum('ij,jk,ik->i', options, g, options)
        pick = int(np.argmin(losses))
        counts[pick] += 1
        if losses[pick] < best_value:
            best_value = float(losses[pick])
            best_counts = counts.copy()
    return best_counts/best_counts.sum()


def rmse(x, y):
    residual = x-y
    return float(np.linalg.norm(residual)/math.sqrt(len(y)))


def analyze_library(x, y, masks):
    singles = [rmse(p, y) for p in x]
    rows = []
    for fit, check in ((masks[0], masks[1]), (masks[1], masks[0])):
        errors = x[:, fit]-y[fit]
        gram = errors@errors.T/int(fit.sum())
        chosen = int(np.argmin(np.diag(gram)))
        weights = quadratic_greedy(gram)
        greedy = weights@x
        raw = x[chosen]
        # Fit each library member's two-parameter affine correction on fit only.
        # Clip to legal [0,1], then select lowest FIT loss. No check-side choices.
        centered_y = y[fit]-y[fit].mean()
        calibrated = []
        parameters = []
        for prediction in x:
            xf = prediction[fit]
            centered_x = xf-xf.mean()
            variance = float(centered_x@centered_x)
            slope = float(centered_x@centered_y/variance) if variance > 1e-20 else 0.
            intercept = float(y[fit].mean()-slope*xf.mean())
            calibrated.append(np.clip(slope*prediction+intercept, 0., 1.))
            parameters.append([slope, intercept])
        calibrated_index = min(range(len(x)), key=lambda i: (rmse(calibrated[i][fit], y[fit]), i))
        check_scores = dict(selected_single=rmse(raw[check], y[check]), greedy20=rmse(greedy[check], y[check]),
                            calibrated_single=rmse(calibrated[calibrated_index][check], y[check]))
        rows.append(dict(fit_rows=int(fit.sum()), check_rows=int(check.sum()), values=check_scores,
                         greedy_gain=check_scores['selected_single']-check_scores['greedy20'],
                         calibration_gain=check_scores['selected_single']-check_scores['calibrated_single'],
                         greedy_over_calibration=check_scores['calibrated_single']-check_scores['greedy20'],
                         raw_index=chosen, calibrated_index=calibrated_index,
                         calibration_parameters=parameters[calibrated_index], greedy_weights=weights.tolist()))
    return singles, rows


def main(source, output):
    started = time.monotonic()
    assert digest(source) == RECEIPT_PIN
    original = read(source)
    rows, differences = [], []
    for job, name, lineage_name in SPECS:
        root = BASE/name
        source_pin = original['source_hashes'][name]
        assert digest(root/lineage_name) == source_pin['lineage']
        assert digest(root/'plan.json') == source_pin['plan']
        assert digest(root/'warm-receipt.json') == source_pin['warm']
        lineage = read(root/lineage_name)
        assert lineage['assigned'] == read(root/'closed.json')['complete'] == 32
        plan = read(root/'plan.json')
        assert plan['common_start_receipt_sha256'] == source_pin['warm']
        spec = read(root/'dev-views/spec.json')[TASK]
        ids, y, masks = reference(root, spec['view_sha'])
        warm = read(root/'warm-receipt.json')[TASK]
        warm_root = Path(warm['root'])
        assert warm_root == BASE/'scheduling-image-live-2plus4-20261011-v3'
        assert digest(warm_root/'plan.json') == '95825b54b256eb69f7a2a372db66c4f63b4c0d9840d3253f5ade5685f448fe66'
        wfiles = []
        for path in sorted((warm_root/f'episode-{warm["run"]}').glob('scored-*.json')):
            if digest(path) in {g['receipt_sha256'] for g in warm['grounded']}:
                receipt = read(path)['receipt']
                assert receipt['view_manifest_sha256'] == spec['view_sha']
                wfiles.append((receipt['submission_sha256'], path.with_suffix('.private.csv')))
        assert wfiles and len({h for h, _ in wfiles}) == 1
        whash, wpath = wfiles[0]
        wpred = load_prediction(wpath, whash, ids)
        assert abs(rmse(wpred, y)-warm['score']) < 1e-12
        for block in range(4):
            expected = next(r for r in original['rows'] if (r['job'],r['block'],r['task']) == (job,block,TASK))
            library = {whash: wpred}
            selected = [c for c in lineage['candidates'] if c['block'] == block and c['task'] == TASK and c['valid']]
            assert len(selected) == expected['timely_valid_candidates']
            for candidate in selected:
                rel = f'episode-{candidate["index"]}/candidate-{candidate["candidate"]}.json'
                assert digest(root/rel) == lineage['source_hashes'][rel]
                raw = read(root/rel)
                assert raw['elapsed_seconds'] <= 1020 and raw['exit_code'] == 0 and not raw['timed_out']
                h = raw['aux']['submission_sha256']
                found = []
                for path in sorted((root/f'episode-{candidate["index"]}').glob('scored-*.json')):
                    receipt = read(path)['receipt']
                    if receipt['submission_sha256'] == h:
                        assert receipt['split'] == 'D_search_development_only' and receipt['view_manifest_sha256'] == spec['view_sha']
                        assert abs(receipt['rmse']-candidate['score']) < 1e-12
                        found.append(path.with_suffix('.private.csv'))
                assert found
                if h not in library: library[h] = load_prediction(found[0], h, ids)
            assert list(library) == expected['prediction_hashes']
            x = np.array(list(library.values()))
            singles, folds = analyze_library(x, y, masks)
            delta = max(abs(a-b) for a,b in zip(singles,expected['single_scores']))
            for fold, old in zip(folds, expected['post_adaptive_resplit_sensitivity']):
                assert fold['fit_rows'] == old['fit_rows'] and fold['check_rows'] == old['check_rows']
                for key in ('selected_single', 'greedy20'):
                    delta = max(delta, abs(fold['values'][key]-old['values'][key]))
            assert delta < 5e-10, 'independent raw/Gram verification failed'
            differences.append(delta)
            rows.append(dict(job=job, block=block, task=TASK, assigned_runs=4,
                             library_size=len(library), max_independent_difference=delta, folds=folds))
            print(json.dumps(dict(job=job,block=block,raw_verification_passed=True)),flush=True)
    assert len(rows) == 12
    def summary(key):
        values = [min(f[key] for f in r['folds']) for r in rows]
        return dict(pools=12,both_positive=sum(v>1e-12 for v in values),
                    both_atleast_001=sum(v>=.001 for v in values),median_worse_direction=float(np.median(values)),
                    sample_sd_worse_direction=float(np.std(values,ddof=1)),min=min(values),max=max(values))
    result = dict(schema=1, source_sha256=digest(__file__), original_receipt_sha256=RECEIPT_PIN,
                  closed_batches=3,denoise_assigned_runs=48,task_pools=12,rows=rows,
                  max_independent_difference=max(differences),
                  summaries={key:summary(key) for key in ('greedy_gain','calibration_gain','greedy_over_calibration')},
                  elapsed_cpu_host_wall_seconds=time.monotonic()-started,
                  limits=['Reconstructed raw Denoise labels/IDs/predictions and eligibility from pinned original artifacts; independent quadratic greedy implementation.',
                          'Same known adaptively searched DEV references and same two image-group splits, NOT fresh holdout or causal confirmation.',
                          'Affine clipping and library-member selection use fit direction only. Both directions reported, no check-side selection.',
                          'Single-model calibration is a known cheap baseline, not a new search method. Extra CPU not charged to oldGPUbatches; no equal-budget E2E claim.',
                          'Only Denoise12pools; no excluded failed library/warm fallback, no newGPU/API/model/program, no invalid19004/currentquota read.',
                          '.001 is descriptive magnitude, not a new success criterion or replacement for frozen quota quality gates.'])
    with output.open('x') as f: json.dump(result,f,sort_keys=True,indent=2,allow_nan=False)
    print(json.dumps(dict(output_sha256=digest(output),summaries=result['summaries'],max_independent_difference=result['max_independent_difference'])))


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('source',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args();main(args.source,args.output)
