"""Preregistered conditional random-group diagnostic after exploratory readout.

Not a prospective confirmatory p-value: the candidates saw length diagnostics
during generation and development outcomes were already observed. This tests
whether the already optimistic two exceptions exceed random grouping opportunity.
"""
import csv
import hashlib
import json
import os
import statistics
import sys
import time
from pathlib import Path

B=Path('/research/d7/spc/yzyang4')
OLD=B/'task-feedback-real-20261001-v6'
SOURCE=B/'repair-opportunity-20261002-v1'
OUT=SOURCE/'group-placebo-v1'
TASK='random-acts-of-pizza'
REPLICATES=1000
SEED=102501


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_bytes())
def rows(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def save(p,v):
    with p.open('x') as f:json.dump(v,f,sort_keys=True,indent=2,allow_nan=False);f.write('\n')


def main():
    os.umask(0o077);OUT.mkdir();started=time.monotonic()
    assert sha(SOURCE/'summary.json')=='c714d7daf46ed431f87a7d0428a60a188613b7452541b932b9e7ad20dfb37139'
    assert read(SOURCE/'review-v1/verification.json')['status']=='PASS'
    plan=dict(role='POSTHOC_CONDITIONAL_RANDOM_GROUP_SANITY_CHECK_NOT_CONFIRMATORY',source_sha256=sha(Path(__file__)),
              producer_summary_sha256=sha(SOURCE/'summary.json'),replicates=REPLICATES,seed=SEED,
              candidates='all15 valid automatic Pizza parent-child proposals, out of28 eligible proposals; no cherry-picked pair subset',
              randomization='joint permutation of group membership within each class; SAME permuted group vector for all candidates per replicate',
              preserved='all prediction vectors, labels, group counts per class, candidate correlations, same-parent repetition, failure denominator',
              primary='maximum global AUC across all15x3 one-group replacements minus fixed strongest historical AUC',
              secondary='number of distinct candidates with any replacement above strong reference; rescue count among whole-child regressions',
              boundary='pure descriptive reference distribution, not a formal causal null: length facts influenced candidate creation; labels/history reused',
              gpu=0,api_calls=0,fits=0,hard_cpu_seconds=180)
    save(OUT/'plan.json',plan)
    import numpy as np
    from scipy.stats import rankdata
    sys.path.insert(0,str(OLD));import task_feedback_real_20261001 as runtime
    runtime.setup()
    from dojo.config_dataclasses.run import RunConfig
    from dojo.tasks.mlebench.task import MLEBenchTask
    from task_feedback_facts_20261001 import groups
    idx=next(s['index'] for s in read(OLD/'plan.json')['schedule'] if s['task']==TASK)
    task=MLEBenchTask(RunConfig.load_from_json(OLD/'configs'/f'{idx}.json').task)
    spec=task._search_only_module.SPEC[TASK]
    truth_path=B/spec.get('source',spec.get('view'))/'private/dsearch.csv'
    bindings=read(SOURCE/'bindings.private.json');assert sha(truth_path)==bindings[str(truth_path)]
    truth=rows(truth_path);ids=[r['request_id'] for r in truth]
    y=np.array([int(r['requester_received_pizza']) for r in truth]);pos=y==1;neg=~pos
    np_,nn=int(pos.sum()),int(neg.sum());_,bins=groups(TASK,task.public_dir)
    real_groups=np.array([bins[i] for i in ids]);ref=read(SOURCE/'summary.json')['references'][TASK]['utility']
    candidates=[r for r in rows(SOURCE/'pairs.csv') if r['task']==TASK and r['automatic_guidance']=='True' and r['child_valid']=='True']
    assert len(candidates)==15
    def auc(p):return float((rankdata(p,method='average')[pos].sum()-np_*(np_+1)/2)/(np_*nn))
    def loadp(path):
        assert sha(path)==bindings[str(path)];d={r['request_id']:float(r['requester_received_pizza']) for r in rows(path)}
        assert set(d)==set(ids);return np.array([d[i] for i in ids])
    arrays=[]
    for r in candidates:
        ep=B/r['batch']/f'episode-{r["episode"]}'
        p=loadp(ep/f'action-{r["parent_step"]}/submission.private.csv')
        c=loadp(ep/f'action-{r["step"]}/submission.private.csv')
        assert abs(auc(p)-float(r['parent_utility']))<1e-12 and abs(auc(c)-float(r['child_utility']))<1e-12
        arrays.append((p,c,auc(p),auc(c)))
    def statistic(g):
        peaks=[];rescue=0
        for p,c,u0,u1 in arrays:
            best=max(auc(np.where(g==k,c,p)) for k in range(3));peaks.append(best)
            rescue+=u1<u0-1e-12 and best>u0+1e-12
        return dict(max_margin=max(peaks)-ref,above_reference=sum(u>ref+1e-12 for u in peaks),rescue_worse_child=int(rescue))
    observed=statistic(real_groups)
    assert observed['above_reference']==2 and observed['rescue_worse_child']==5
    rng=np.random.default_rng(SEED);sim=[]
    for repetition in range(REPLICATES):
        g=real_groups.copy()
        for label in (0,1):
            ix=np.flatnonzero(y==label);g[ix]=rng.permutation(real_groups[ix])
            for k in range(3):assert np.sum(g[ix]==k)==np.sum(real_groups[ix]==k)
        sim.append(dict(repetition=repetition,**statistic(g)))
    with (OUT/'replicates.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(sim[0]));w.writeheader();w.writerows(sim)
    summary={}
    for name,value in observed.items():
        values=[r[name] for r in sim];exceed=sum(v>=value-1e-12 for v in values)
        summary[name]=dict(observed=value,random_median=statistics.median(values),random_variance=statistics.variance(values),
                           random_q025=float(np.quantile(values,.025)),random_q975=float(np.quantile(values,.975)),
                           random_at_least_observed=exceed,replicates=REPLICATES,plus_one_reference_tail=(exceed+1)/(REPLICATES+1))
    result=dict(status='DESCRIPTIVE_RANDOM_GROUP_REFERENCE',plan_sha256=sha(OUT/'plan.json'),seed=SEED,
                results=summary,elapsed_seconds=time.monotonic()-started,replicates_sha256=sha(OUT/'replicates.csv'),
                note='The reference tail is NOT an independent-test or causal p-value; no method selection may be made from individual random partitions.')
    save(OUT/'summary.json',result);print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
