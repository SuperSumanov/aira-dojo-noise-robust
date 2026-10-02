"""Fixed, label-free finalizers for each already closed development trajectory.

Prediction construction never loads labels or numeric result metrics. All outputs
are frozen before a separate scoring phase. Historical trajectories themselves
were adaptive to D_search: this is NOT prospective or independent evaluation.
"""
import csv
import hashlib
import json
import os
import statistics
import sys
import time
from pathlib import Path

B = Path('/research/d7/spc/yzyang4')
OLD = B/'task-feedback-real-20261001-v6'
PRIOR = B/'repair-opportunity-20261002-v1'
OUT = B/'trajectory-ensemble-reference-20261002-v1'
TASKS = ('spooky-author-identification', 'random-acts-of-pizza', 'tweet-sentiment-extraction')
KEYS = dict(zip(TASKS, ('id', 'request_id', 'textID')))
ROOTS = {
    OLD.name: '15751d3b52bdc42617df02006ce724635f4bf49df6e477686769fd1979d53403',
    'task-feedback-upper-20261002-v1': '9fe231e1b9e2da8cb51fadb7ff9844b074c10e8e3dc64d1d1f3be170fb0703a0',
    'task-feedback-local-edit-20261002-v1': '7bd84ff0e867043b2787d5c07af867eff50370f4e7b6bafa811ef215196c4139',
}


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p): return json.loads(p.read_bytes())
def rows(p):
    with p.open(encoding='utf-8-sig', newline='') as f: return list(csv.DictReader(f))
def save(p, obj):
    with p.open('x') as f: json.dump(obj, f, sort_keys=True, indent=2, allow_nan=False); f.write('\n')
def digest(value): return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()
def distribution(values):
    return dict(n=len(values), median=statistics.median(values) if values else None,
                sample_variance=statistics.variance(values) if len(values)>1 else None)
def jaccard(a, b):
    x, y = set(a.lower().split()), set(b.lower().split())
    return len(x & y)/len(x | y) if x | y else 0.


def finalize(task, predictions):
    """One fixed primary method; a predeclared rank-mean secondary for AUC."""
    import numpy as np
    from scipy.stats import rankdata
    if task == TASKS[2]:
        selected = []
        for row in zip(*predictions):
            quality = [sum(jaccard(a, b) for b in row) for a in row]
            # Earliest action breaks all exact ties, independent of outcome.
            selected.append(row[max(range(len(row)), key=lambda i: quality[i])])
        return {'consensus': selected}
    values = np.asarray(predictions, dtype=float)
    out = {'mean': values.mean(axis=0).tolist()}
    if task == TASKS[1]:
        out['rank_mean'] = np.mean([rankdata(p, method='average')/len(p) for p in values], axis=0).tolist()
    return out


def main():
    os.umask(0o077); OUT.mkdir(); began = time.monotonic()
    assert sha(PRIOR/'summary.json') == 'c714d7daf46ed431f87a7d0428a60a188613b7452541b932b9e7ad20dfb37139'
    assert sha(OLD/'task_feedback_real_20261001.py') == '4b155d927c12f063e0838b5708085fe1bc55c4983197a3d8d2453696d73c55ad'
    save(OUT/'plan.json', dict(role='RETROSPECTIVE_FIXED_FINALIZATION_BASELINE_NOT_NEW_METHOD',
        source_sha256=sha(Path(__file__)), public_source_commit='df7dc14eb2103558708574ae3373b9123cd8b3c4', roots=ROOTS,
        cohort='every scheduled trajectory from all three closed roots; no-valid ones retained',
        primary_subset='original ABC + upper A/B only; manual arms separately descriptive',
        library='all valid executed actions within SAME trajectory; exact post-rule prediction-vector dedup, keep earliest',
        primary='probability mean for Spooky/Pizza; candidate-set word-Jaccard MBR for Tweet, ties earliest',
        secondary='uniform average of midranks for Pizza only; no selection between primary/secondary',
        neutral='same already frozen public neutral-copy rule applied to every Tweet candidate and selected comparator',
        comparator='last native selected.json action, not reselected after neutral rule; strongest historical program is contextual only',
        costs='new single-thread CPU capped 180sec; all inherited generator/task execution retained, not free E2E',
        boundary='source search already adapted to D_search; output finalization is label-free, not whole pipeline',
        gpu=0, api_calls=0, fits=0, protected_opened=False, python=sys.version.split()[0], invocation=sys.argv))
    sys.path.insert(0, str(OLD)); import task_feedback_real_20261001 as runtime
    runtime.setup()
    from dojo.config_dataclasses.run import RunConfig
    from dojo.tasks.mlebench.task import MLEBenchTask
    assert sha(B/'task-feedback-public-rule-20261002-v1/rule.json') == '2beaad25ab591c957f1183de5b17457ff738b25130d13075df500c36bb4fbfc0'
    bindings = read(PRIOR/'bindings.private.json')
    task_data = {}
    for task in TASKS:
        index = next(r['index'] for r in read(OLD/'plan.json')['schedule'] if r['task']==task)
        obj = MLEBenchTask(RunConfig.load_from_json(OLD/'configs'/f'{index}.json').task)
        public_path = obj.public_dir/('test.json' if task==TASKS[1] else 'test.csv')
        assert sha(public_path) == bindings[str(public_path)]
        public = read(public_path) if task==TASKS[1] else rows(public_path)
        ids = [r[KEYS[task]] for r in public]
        assert len(ids)==len(set(ids))
        task_data[task] = obj, ids, {r[KEYS[task]]:r for r in public}

    # Phase 1: no labels or numeric outcome values used to build libraries.
    frozen = []
    for batch, h in ROOTS.items():
        root = B/batch
        assert sha(root/'plan.json')==h and (root/'all-closed.json').is_file()
        for s in read(root/'plan.json')['schedule']:
            ep = root/f'episode-{s["index"]}'
            assert (ep/'closed.json').is_file()
            task = s['task']; obj, ids, public = task_data[task]
            predictions = []; steps = []; seen = set(); selected_steps = []; sources = {}
            all_by_step = {}
            for action in sorted(ep.glob('action-*'), key=lambda p:int(p.name.split('-')[-1])):
                if not (action/'result.json').is_file(): continue
                if not read(action/'result.json')['valid']: continue
                path = action/'submission.private.csv'
                assert sha(path)==bindings[str(path)]
                sources[str(path)] = sha(path)
                data = rows(path); lookup = {r[KEYS[task]]:r for r in data}
                assert len(data)==len(lookup)==len(ids) and set(lookup)==set(ids)
                if task == TASKS[0]:
                    p = [[float(lookup[i][c]) for c in ('EAP','HPL','MWS')] for i in ids]
                elif task == TASKS[1]:
                    p = [float(lookup[i]['requester_received_pizza']) for i in ids]
                else:
                    p = [public[i]['text'] if public[i]['sentiment']=='neutral' else lookup[i]['selected_text'] for i in ids]
                step = int(action.name.split('-')[-1]); all_by_step[step] = p
                if (action/'selected.json').is_file(): selected_steps.append(step)
                fingerprint = digest(p)
                if fingerprint in seen: continue
                seen.add(fingerprint); steps.append(step); predictions.append(p)
            assert bool(predictions)==bool(selected_steps)
            key = f'{list(ROOTS).index(batch)}-{s["index"]}'
            result = dict(batch=batch, episode=s['index'], task=task, arm=s['arm'],
                          generation_seed=s.get('generation_seed', s.get('seed')),
                          automatic_guidance=(batch==OLD.name or (batch=='task-feedback-upper-20261002-v1' and s['arm'] in ('A','B'))),
                          n_valid_actions=len(all_by_step), n_unique=len(predictions), library_steps=steps,
                          selected_step=max(selected_steps) if selected_steps else None, prediction_sources=sources,
                          methods=finalize(task,predictions) if predictions else {},
                          selected=all_by_step[max(selected_steps)] if selected_steps else None)
            path = OUT/f'{key}.private.json'; save(path,result)
            frozen.append(dict(key=key,path=str(path),sha256=sha(path)))
    save(OUT/'predictions-frozen.json',dict(plan_sha256=sha(OUT/'plan.json'),records=frozen,
        labels_used_for_finalization=False, construction_seconds=time.monotonic()-began))

    # Phase 2: score only after the entire candidate finalization was frozen.
    import numpy as np
    from sklearn.metrics import roc_auc_score, log_loss
    labels = {}
    for task,(obj,ids,_) in task_data.items():
        spec = obj._search_only_module.SPEC[task]
        path = B/spec.get('source',spec.get('view'))/'private/dsearch.csv'
        assert sha(path)==bindings[str(path)]
        lookup = {r[KEYS[task]]:r for r in rows(path)}
        assert set(lookup)==set(ids)
        col = 'author' if task==TASKS[0] else 'requester_received_pizza' if task==TASKS[1] else 'selected_text'
        labels[task] = [lookup[i][col] for i in ids]
    def utility(task,p):
        y=labels[task]
        if task==TASKS[0]: return -float(log_loss(y,p,labels=['EAP','HPL','MWS']))
        if task==TASKS[1]: return float(roc_auc_score([int(a) for a in y],p))
        return float(np.mean([jaccard(a,b) for a,b in zip(y,p)]))
    references = read(PRIOR/'summary.json')['references']
    output=[]
    for f in frozen:
        path=Path(f['path']);assert sha(path)==f['sha256'];r=read(path);task=r['task']
        base={k:r[k] for k in ('batch','episode','task','arm','generation_seed','automatic_guidance','n_valid_actions','n_unique','selected_step')}
        base['plan_sha256']=sha(OUT/'plan.json'); base['public_source_commit']='df7dc14eb2103558708574ae3373b9123cd8b3c4'
        choices=('consensus',) if task==TASKS[2] else ('mean','rank_mean') if task==TASKS[1] else ('mean',)
        for method in choices:
            row=dict(base,method=method,coverage=bool(r['methods']),selected_utility=None,utility=None,gain=None,beyond_historical_strong=None)
            if r['methods']:
                u=utility(task,r['methods'][method]);b=utility(task,r['selected'])
                row.update(selected_utility=b,utility=u,gain=u-b,beyond_historical_strong=u-references[task]['utility'])
            output.append(row)
    with (OUT/'rows.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(output[0]));w.writeheader();w.writerows(output)
    summaries={}
    for task in TASKS:
        for scope in ('all','automatic'):
            for method in sorted({r['method'] for r in output if r['task']==task}):
                sub=[r for r in output if r['task']==task and r['method']==method and (scope=='all' or r['automatic_guidance'])]
                valid=[r for r in sub if r['coverage']]
                summaries[f'{task}:{scope}:{method}']=dict(total=len(sub),valid=len(valid),
                    multiple_unique=sum(r['n_unique']>1 for r in valid),
                    wins=sum(r['gain']>1e-12 for r in valid),ties=sum(abs(r['gain'])<=1e-12 for r in valid),
                    losses=sum(r['gain'] < -1e-12 for r in valid),beats_historical_strong=sum(r['beyond_historical_strong']>1e-12 for r in valid),
                    gain=distribution([r['gain'] for r in valid]),score=distribution([r['utility'] for r in valid]))
    result=dict(status='CLOSED_DEVELOPMENT_FIXED_BASELINE_ONLY',trajectories=len(frozen),summaries=summaries,
                plan_sha256=sha(OUT/'plan.json'),predictions_frozen_sha256=sha(OUT/'predictions-frozen.json'),rows_sha256=sha(OUT/'rows.csv'),
                elapsed_seconds=time.monotonic()-began,gpu=0,api_calls=0,fits=0)
    save(OUT/'summary.json',result);print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
