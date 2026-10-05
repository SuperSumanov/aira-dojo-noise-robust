"""Post-hoc conditional paired uncertainty on every complete fixed quartet.

This resamples the already reused D_search examples. It does NOT correct research
adaptation, selection of tasks, multiple contrasts or training randomness, and
cannot convert the known rescue example into an independent confirmation.
"""
import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import time

import numpy as np
from sklearn.metrics import roc_auc_score

B=Path('/research/d7/spc/yzyang4')
R=B/'collateral-factorial-20261006-v1'
ARMS=('P','C','CP','PC')
SEED=116099
N=2000


def digest(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p): return json.loads(Path(p).read_bytes())
def rows(p):
    with Path(p).open(newline='',encoding='utf-8-sig') as f: return list(csv.DictReader(f))
def save(p,x):
    with p.open('x') as f:json.dump(x,f,sort_keys=True,indent=2,allow_nan=False);f.write('\n')


def differences(v):
    p,c,cp,pc=v
    return np.array([cp-p,c-p,cp-c,pc-p,c-cp,c-cp-pc+p, c-pc])


def main():
    start=time.monotonic()
    def alarm(*args):raise TimeoutError('analysis wall cap')
    signal.signal(signal.SIGALRM,alarm);signal.alarm(180)
    summary_path=R/'readout-v1/summary.json'
    assert digest(summary_path)=='1adfe476893432ac944bae327fe8e32add995bb15c6ff416433716fa623b2185'
    assert read(R/'closed.json')['assigned']==32
    source=read(summary_path)
    complete=[c['case'] for c in source['contrasts'] if c['complete']]
    data=rows(R/'readout-v1/runs.csv')
    frozen=read(R/'readout-v1/prediction-freeze.json')
    out=R/'bootstrap-v1';out.mkdir(mode=0o700,exist_ok=False)
    save(out/'plan.json',dict(source_summary_sha256=digest(summary_path),script_sha256=digest(__file__),
        complete_cases=complete,selection='Every complete original quartet; missing quartets remain in primary result.',
        samples=N,seed=SEED,method='Paired stratified-example bootstrap for AUC, paired-example bootstrap for Jaccard.',
        confidence=.95,posthoc=True,boundary=__doc__,model_fits=0,gpu_hours=0))
    output=[]
    for case in complete:
        group={r['arm']:r for r in data if int(r['case'])==case}
        cfg=read(R/'configs'/f"{group['P']['index']}.json")['task']
        assert digest(cfg['search_only_dev_scorer_path'])==cfg['search_only_dev_scorer_sha256']
        spec=importlib.util.spec_from_file_location('fixed_scorer',cfg['search_only_dev_scorer_path'])
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        task=group['P']['task'];s=module.SPEC[task]
        manifest=B/s['view']/'manifest.json';assert digest(manifest)==s['view_sha']
        if task=='random-acts-of-pizza':
            truth_path=B/s['source']/'private/dsearch.csv';ident=s['id'];label=s['label']
            assert digest(truth_path)==read(manifest)['source_dsearch_sha256']
        else:
            truth_path=B/s['view']/'private/dsearch.csv';ident='textID';label='selected_text'
            assert digest(truth_path)==read(manifest)['files_sha256']['dsearch']
        truth=rows(truth_path);predictions=[]
        for arm in ARMS:
            r=group[arm];p=R/f"episode-{r['index']}/action-0/submission.private.csv"
            assert digest(p)==r['prediction_sha256']==frozen[str(p.relative_to(R))]
            pred_rows=rows(p);pred={x[ident]:x[label] for x in pred_rows}
            assert len(pred)==len(pred_rows)==len(truth) and set(pred)=={x[ident] for x in truth}
            if task=='random-acts-of-pizza':
                predictions.append(np.array([float(pred[x[ident]]) for x in truth]))
            else:
                values=[]
                for x in truth:
                    a,z=set(x[label].lower().split()),set(pred[x[ident]].lower().split())
                    assert a;values.append(len(a&z)/len(a|z))
                predictions.append(np.array(values))
        rng=np.random.default_rng(SEED)  # same within-task example draws for related cases
        draws=[]
        if task=='random-acts-of-pizza':
            y=np.array([int(x[label]) for x in truth]);groups=[np.flatnonzero(y==v) for v in (0,1)]
            observed=[roc_auc_score(y,p) for p in predictions]
            for _ in range(N):
                ix=np.concatenate([rng.choice(g,len(g),replace=True) for g in groups])
                draws.append(differences([roc_auc_score(y[ix],p[ix]) for p in predictions]))
        else:
            observed=[float(p.mean()) for p in predictions]
            for _ in range(N):
                ix=rng.integers(0,len(truth),len(truth))
                draws.append(differences([float(p[ix].mean()) for p in predictions]))
        assert max(abs(v-float(group[a]['dev_metric'])) for a,v in zip(ARMS,observed))<1e-12
        lo,hi=np.quantile(np.array(draws),[.025,.975],axis=0)
        keys=['CP_minus_P','C_minus_P','CP_minus_C','PC_minus_P','C_minus_CP','interaction','C_minus_PC']
        output.append(dict(case=case,task=task,n=len(truth),contrasts={k:dict(estimate=float(v),conditional_low=float(l),conditional_high=float(h)) for k,v,l,h in zip(keys,differences(observed),lo,hi)}))
    save(out/'summary.json',dict(plan_sha256=digest(out/'plan.json'),rows=output,
        elapsed_seconds=time.monotonic()-start,posthoc=True,boundary=__doc__,no_new_execution=True))
    print(json.dumps(read(out/'summary.json')))


if __name__=='__main__':
    os.umask(0o077);main()
