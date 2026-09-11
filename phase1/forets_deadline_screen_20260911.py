"""Exploratory deadline-completion prediction on an exact OLD-development scope.

No GPU/API, grades or protected cohorts. The old provenance is NOT certified.
"""
from __future__ import annotations
import argparse
import ast
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import signal
import tarfile
import time

ROOT = Path('/research/d7/spc/yzyang4')
PACK = 'historical-program-pack-f702ba2-r2-20260907/A-pack.private.json'
PACK_SHA = '0912a2e6cf8342fe6c209645d2d1b56c142f91a066197fcd5e37d07f8c0955e7'
LINEAGE = 'historical-pool-lineage-e7244fb-20260906-A/pool_lineage.private.json'
LINEAGE_SHA = 'fe05dddcd4fe8a3f2208652ce51c9b06df9b9b8f57a5fa655d2029caddcf9981'
LEDGER = 'historical-source-ledger-faf04cc-20260905/source_ledger.private.json'
LEDGER_SHA = '8e48b4c6598cf8efe205fc6cba5cdd27d14621eb13fad42a7fd4180953da00d1'
ARCHIVES = 'senior-true-batch-identity-support/a466888-v3/producer_1/archive_manifest.jsonl'
ARCHIVES_SHA = '72b74df7387254afc5ca3ec5d79029e74ae8371faa6216742e63be899419e8fd'
SECRET = re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{16,}|gh[pousr]_[a-z0-9]{16,}|github_pat_[a-z0-9_]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9a-z_-]{30,}|Bearer\s+[a-z0-9_.-]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')
WORDS = ('lightgbm','xgboost','catboost','torch','transformers','tensorflow',
         'randomforest','logisticregression','ridge','svc','ensemble','n_splits',
         'num_boost_round','n_estimators','epochs','early_stopping','gpu','cuda',
         'num_threads','n_jobs','train_test_split','standardscaler','pca','polynomialfeatures')
SEED = 20260911

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def unique(pairs):
    result = {}
    for k, v in pairs:
        if k in result: raise ValueError('duplicate_json_key')
        result[k] = v
    return result

def locked(relative, digest, lines=False):
    p = ROOT / relative
    if p.is_symlink() or p.resolve() != p: raise ValueError('unsafe_metadata_path')
    raw = p.read_bytes()
    if sha(raw) != digest or SECRET.search(raw): raise ValueError('metadata_drift_or_credential')
    return [json.loads(s, object_pairs_hook=unique) for s in raw.splitlines()] if lines else json.loads(raw, object_pairs_hook=unique)

def target(node):
    t, e = node.get('exec_time'), node.get('exit_code')
    if type(t) not in (int, float) or not math.isfinite(t) or t <= 0: return None, 'missing_invalid_duration'
    if type(e) is not int: return None, 'missing_invalid_exit_code'
    return (int(e == 0 and t <= 300), int(e == 0)), None

def code_features(code):
    low = code.lower()
    features = {'log_chars': math.log1p(len(code)), 'log_lines': math.log1p(len(code.splitlines()))}
    features.update({f'word:{w}': math.log1p(low.count(w)) for w in WORDS})
    try:
        tree = ast.parse(code)
        counts = Counter(type(n).__name__ for n in ast.walk(tree))
        for name in ('Call','For','While','ListComp','DictComp','If','FunctionDef','Import','ImportFrom','Try'):
            features[f'ast:{name}'] = math.log1p(counts[name])
        canonical = ast.dump(tree, include_attributes=False)
        features['syntax_error'] = 0.0
    except (SyntaxError, ValueError, RecursionError):
        canonical = code
        for name in ('Call','For','While','ListComp','DictComp','If','FunctionDef','Import','ImportFrom','Try'):
            features[f'ast:{name}'] = 0.0
        features['syntax_error'] = 1.0
    return features, sha(canonical.encode())

def split_indices(rows, task, component):
    test = [i for i, r in enumerate(rows) if r['task'] == task and r['component'] == component]
    forbidden_code = {rows[i]['code_sha'] for i in test}
    forbidden_ast = {rows[i]['ast_sha'] for i in test}
    train = [i for i, r in enumerate(rows) if r['task'] == task and r['component'] != component
             and r['code_sha'] not in forbidden_code and r['ast_sha'] not in forbidden_ast]
    return train, test

def read_rows():
    pack = locked(PACK, PACK_SHA)
    closure = locked(LINEAGE, LINEAGE_SHA)['closure']
    ledger = locked(LEDGER, LEDGER_SHA)
    if len(pack) != 84 or sum(n['nonempty_code'] for r in pack.values() for n in r['nodes']) != 3447: raise ValueError('scope_changed')
    components = {r['component_sha256'] for r in pack.values()}
    if len(components) != 24: raise ValueError('components_changed')
    for rid, r in pack.items():
        if r['source_admitted'] is not False or closure[rid]['old_hold_closure_blocks_train'] is not False: raise ValueError('role_changed')
        if closure[rid]['component_sha256'] != r['component_sha256']: raise ValueError('component_changed')
        if ledger[rid]['old_hold_closure_blocks_train'] is not False: raise ValueError('ledger_hold')
    if {rid for rid, c in closure.items() if c['component_sha256'] in components} != set(pack): raise ValueError('partial_component')
    paths = {o['sha256']: ROOT/'external/senior_data/mle'/o['relative_path'] for o in locked(ARCHIVES, ARCHIVES_SHA, True) if o['status'] == 'ok'}
    paths['8ade376fb045aa47bffa63b493fa5e4b02d376815d7700c9c9f441c1848edfa4'] = Path('/tmp/historical-source-repair-download-20260905/candidate-02.tar.gz')
    wanted = defaultdict(dict)
    for rid, r in sorted(pack.items()):
        if r['journal_member'] in wanted[r['archive_sha256']]: raise ValueError('duplicate_member_binding')
        wanted[r['archive_sha256']][r['journal_member']] = (rid, r)
    rows, counts, found = [], Counter(), set()
    for archive_sha, members in sorted(wanted.items()):
        path = paths[archive_sha]
        if path.is_symlink() or path.resolve() != path: raise ValueError('unsafe_archive_path')
        with path.open('rb') as handle:
            if hashlib.file_digest(handle, 'sha256').hexdigest() != archive_sha: raise ValueError('archive_drift')
        before = path.stat()
        seen = set()
        with tarfile.open(path, 'r|gz') as arc:
            for m in arc:
                if m.name not in members: continue
                if m.name in seen or not m.isfile() or m.size > 32*1024**2: raise ValueError('bad_member')
                seen.add(m.name)
                rid, r = members[m.name]
                raw = arc.extractfile(m).read()
                if sha(raw) != r['member_sha256']: raise ValueError('journal_drift')
                hits = len(SECRET.findall(raw)); counts['credential_shapes_redacted'] += hits
                safe = SECRET.sub(b'[REDACTED]', raw)
                nodes = [json.loads(line, object_pairs_hook=unique) for line in safe.splitlines() if line.strip()]
                by_step = {}
                for node in nodes:
                    step = node['step']
                    if type(step) is not int or step in by_step: raise ValueError('duplicate_or_invalid_step')
                    by_step[step] = node
                if set(by_step) != {n['step'] for n in r['nodes']}: raise ValueError('step_set_drift')
                for n in r['nodes']:
                    if not n['nonempty_code']: continue
                    counts['nonempty_programs'] += 1
                    node = by_step[n['step']]
                    code = node['code']
                    if sha(code.encode()) != n['code_sha256']: raise ValueError('code_drift_or_redacted_candidate')
                    labels, reason = target(node)
                    if reason: counts[reason] += 1; continue
                    features, ast_sha = code_features(code)
                    rows.append(dict(task=r['task'], component=r['component_sha256'], run_sha=sha(rid.encode()),
                                     step=n['step'], code_sha=n['code_sha256'], ast_sha=ast_sha,
                                     deadline=labels[0], eventual=labels[1], features=features))
                found.add(rid)
        after = path.stat()
        if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino): raise ValueError('archive_changed')
        if seen != set(members): raise ValueError('missing_members')
    if found != set(pack): raise ValueError('missing_runs')
    task_components = defaultdict(set)
    for r in pack.values(): task_components[r['task']].add(r['component_sha256'])
    eligible = {task: sorted(cs) for task, cs in task_components.items() if len(cs) >= 2}
    if len(eligible) != 6: raise ValueError('task_support_changed')
    return rows, counts, eligible

def estimate(rows, indices, test, label):
    import numpy as np
    from sklearn.feature_extraction import DictVectorizer
    from sklearn.preprocessing import StandardScaler
    from sklearn.linear_model import LogisticRegression
    from sklearn.exceptions import ConvergenceWarning
    import warnings
    if not indices: return [0.5]*len(test), 0, 'empty_train_fallback'
    sizes = Counter(rows[i]['component'] for i in indices)
    weights = np.array([1/sizes[rows[i]['component']] for i in indices]); weights *= len(weights)/weights.sum()
    labels = np.array([rows[i][label] for i in indices])
    if len(set(labels)) < 2:
        p = (float(weights@labels)+1)/(float(weights.sum())+2)
        return [p]*len(test), 0, 'single_class_fallback'
    vector = DictVectorizer(sparse=False)
    x = vector.fit_transform([rows[i]['features'] for i in indices])
    xt = vector.transform([rows[i]['features'] for i in test])
    scaler = StandardScaler(); x = scaler.fit_transform(x, sample_weight=weights); xt = scaler.transform(xt)
    model = LogisticRegression(C=1.0, solver='lbfgs', max_iter=1000, random_state=SEED)
    with warnings.catch_warnings():
        warnings.simplefilter('error', ConvergenceWarning)
        model.fit(x, labels, sample_weight=weights)
    return model.predict_proba(xt)[:, 1].tolist(), 1, None

def run(out, commit):
    import numpy as np
    import sklearn
    start = time.monotonic(); signal.alarm(600); os.umask(0o077)
    out.mkdir(exist_ok=False)
    intent = dict(source_commit=commit, source_sha256=sha(Path(__file__).read_bytes()), seed=SEED,
                  python=platform.python_version(), sklearn=sklearn.__version__, numpy=np.__version__,
                  started_at_utc=datetime.now(timezone.utc).isoformat(), cpu_limit_seconds=600,
                  pack_sha256=PACK_SHA, target_seconds=300, gpu=0, api=0, base_model_updates=0)
    (out/'intent.json').write_text(json.dumps(intent, indent=2)+'\n')
    rows, counts, eligible = read_rows()
    predictions, folds, fit_count = [], [], 0
    for task, components in sorted(eligible.items()):
        for component in components:
            train, test = split_indices(rows, task, component)
            if not test: raise ValueError('entire_component_missing_labels')
            train_components = defaultdict(list)
            for i in train: train_components[rows[i]['component']].append(rows[i]['deadline'])
            # Equal component mass, normalized to row count, same smoothing as
            # single-class fallback; do not shrink small-component priors to .5.
            sizes=Counter(rows[i]['component'] for i in train)
            w=np.array([1/sizes[rows[i]['component']] for i in train])
            if train: w*=len(w)/w.sum()
            d_mass=float(sum(w[j]*rows[i]['deadline'] for j,i in enumerate(train)))
            e_mass=float(sum(w[j]*rows[i]['eventual'] for j,i in enumerate(train)))
            prior=(d_mass+1)/(len(train)+2)
            conditional_deadline=(d_mass+1)/(e_mass+2)
            pd, nd, fd = estimate(rows, train, test, 'deadline')
            pe, ne, fe = estimate(rows, train, test, 'eventual')
            pe=[x*conditional_deadline for x in pe]
            fit_count += nd+ne
            folds.append(dict(task=task, component=component, train=len(train), test=len(test),
                              train_components=len(train_components), deadline_fallback=fd, eventual_fallback=fe))
            for j, i in enumerate(test):
                r = rows[i]
                predictions.append(dict(task=task, component=component, run_sha=r['run_sha'], step=r['step'],
                                        code_sha=r['code_sha'], ast_sha=r['ast_sha'], target=r['deadline'],
                                        prior=float(prior), deadline=pd[j], eventual=pe[j]))
    with (out/'predictions.private.csv').open('x', newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(predictions[0]));writer.writeheader();writer.writerows(predictions)
    per_task=[]
    for task in sorted(eligible):
        components = sorted({r['component'] for r in predictions if r['task']==task})
        item=dict(task=task, components=len(components), rows=sum(r['task']==task for r in predictions))
        for model in ('prior','eventual','deadline'):
            item[model+'_brier']=float(np.mean([np.mean([(r[model]-r['target'])**2 for r in predictions if r['task']==task and r['component']==c]) for c in components]))
            item[model+'_logloss']=float(np.mean([np.mean([-(r['target']*math.log(max(1e-15,r[model]))+(1-r['target'])*math.log(max(1e-15,1-r[model]))) for r in predictions if r['task']==task and r['component']==c]) for c in components]))
        item['deadline_prevalence']=float(np.mean([np.mean([r['target'] for r in predictions if r['task']==task and r['component']==c]) for c in components]))
        per_task.append(item)
    rng=np.random.default_rng(SEED); resamples=rng.integers(0,len(per_task),(5000,len(per_task)))
    comparisons={}
    for baseline in ('prior','eventual'):
        delta=np.array([r[baseline+'_brier']-r['deadline_brier'] for r in per_task])
        comparisons[baseline]=dict(brier_improvement=float(delta.mean()), positive_tasks=int((delta>0).sum()),
                                  task_bootstrap_95=np.quantile(delta[resamples].mean(axis=1),[.025,.975]).tolist())
    gate=all(x['brier_improvement']>=.01 and x['positive_tasks']>=4 for x in comparisons.values())
    summary=dict(**intent, classification='WEAK_HISTORICAL_DEADLINE_SCREEN_NOT_E2E',
                 counts=dict(counts), available_rows=len(rows), evaluated_rows=len(predictions),
                 model_fits=fit_count, folds=folds, per_task=per_task, comparisons=comparisons,
                 investment_signal=gate, source_admitted=False, independent_e2e_gain=False,
                 elapsed_seconds=time.monotonic()-start,
                 predictions_sha256=sha((out/'predictions.private.csv').read_bytes()))
    (out/'summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
    print(json.dumps(summary,allow_nan=False));signal.alarm(0)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--commit',required=True)
    args=p.parse_args()
    if not re.fullmatch('[a-f0-9]{40}',args.commit): raise ValueError('full_commit_required')
    run(args.output,args.commit)
