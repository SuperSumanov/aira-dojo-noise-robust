"""Post-readout paired request bootstrap, descriptive only, no changed gate.

Stratified resampling preserves positive/negative counts. Intervals describe
these fixed predictions conditional on this already-used development set;
they are NOT independent validation, seed variance, or multiplicity-adjusted
tests. Historical incumbent selection and adaptive proposal selection remain.
"""
import hashlib,json,math,re,sys,time
from pathlib import Path
import numpy as np
from sklearn.metrics import roc_auc_score
R=Path('/research/d7/spc/yzyang4/state-feedback-pizza-20261002-v1')
REPS=2000;SEED=103401
def read(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def grouped_auc(y,p,w):
    _,g=np.unique(p,return_inverse=True)
    a=np.bincount(g,weights=w*y);b=np.bincount(g,weights=w*(1-y))
    return float(np.dot(a,np.cumsum(b)-.5*b)/(a.sum()*b.sum()))
def self_test():
    for y,p,w in [([0,1,0,1],[.2,.8,.7,.9],[1,1,1,1]),
                  ([0,1,0,1],[.5,.5,.8,.8],[1,3,2,1]),
                  ([1,0,1,0],[.1,.7,.6,.9],[2,0,1,2])]:
        y,p,w=map(np.asarray,(y,p,w))
        expected=roc_auc_score(y,p,sample_weight=w)
        assert math.isclose(grouped_auc(y,p,w),expected,abs_tol=1e-13)
def main():
    begin=time.monotonic();self_test()
    s=read(R/'readout-v1/summary.json');v=read(R/'readout-v1/verification.json')
    assert v['status']=='PASS' and v['summary_sha256']==sha(R/'readout-v1/summary.json')
    assert read(R/'closed.json')['service_closed'] and (R/'all-closed.json').exists()
    sys.path.insert(0,str(R));from task_feedback_real_20261001 import m
    p=m.check();m.setup()
    from dojo.config_dataclasses.run import RunConfig
    from dojo.tasks.mlebench.task import MLEBenchTask
    import csv
    def csvrows(path):
        with path.open(newline='',encoding='utf-8-sig') as f:return list(csv.DictReader(f))
    cfg=RunConfig.load_from_json(R/'configs/0.json');task=MLEBenchTask(cfg.task)
    spec=task._search_only_module.SPEC['random-acts-of-pizza']
    truth=csvrows(m.B/spec.get('source',spec.get('view'))/'private/dsearch.csv')
    ids=sorted(x['request_id'] for x in truth);assert len(ids)==len(set(ids))
    byid={x['request_id']:x for x in truth}
    y=np.array([int(byid[k]['requester_received_pizza']) for k in ids]);assert set(y)=={0,1}
    bindings={};pred=[];meta=[]
    def prediction(rel):
        path=R/rel;assert sha(path)==s['input_hashes'][rel];bindings[rel]=sha(path)
        values=csvrows(path);a={r['request_id']:float(r['requester_received_pizza']) for r in values}
        assert len(values)==len(a)==len(ids) and set(a)==set(ids)
        z=np.array([a[k] for k in ids]);assert np.isfinite(z).all();return z
    baseline=prediction('episode-0/action-0/submission.private.csv')
    for run in p['schedule']:
        i=run['index'];base=prediction(f'episode-{i}/action-0/submission.private.csv')
        assert np.array_equal(base,baseline)
        for step in range(1,5):
            q=R/f'episode-{i}/action-{step}/result.json'
            if not q.exists() or not read(q)['valid']:continue
            r=read(q);z=prediction(f'episode-{i}/action-{step}/submission.private.csv')
            assert math.isclose(roc_auc_score(y,z),r['metric'],abs_tol=1e-12)
            pred.append(z);meta.append(dict(index=i,step=step,arm=run['arm'],seed=run['seed'],
                delta=float(roc_auc_score(y,z)-roc_auc_score(y,baseline)),exact_prediction_equal=np.array_equal(z,baseline)))
    assert len(pred)==6
    allpred=[baseline,*pred];groups=[np.unique(z,return_inverse=True)[1] for z in allpred]
    pos=np.flatnonzero(y);neg=np.flatnonzero(1-y);rng=np.random.default_rng(SEED)
    boot=[]
    for _ in range(REPS):
        ix=np.r_[rng.choice(pos,len(pos),replace=True),rng.choice(neg,len(neg),replace=True)]
        w=np.bincount(ix,minlength=len(ids));vals=[]
        for g in groups:
            a=np.bincount(g,weights=w*y);b=np.bincount(g,weights=w*(1-y))
            vals.append(np.dot(a,np.cumsum(b)-.5*b)/(len(pos)*len(neg)))
        boot.append(np.asarray(vals[1:])-vals[0])
    boot=np.asarray(boot)
    for j,row in enumerate(meta):
        row['request_bootstrap_95_interval']=np.quantile(boot[:,j],[.025,.975]).tolist()
    out=dict(status='PASS',summary_sha256=sha(R/'readout-v1/summary.json'),producer_sha256=sha(Path(__file__)),
        seed=SEED,replicates=REPS,requests=len(ids),positive_count=len(pos),negative_count=len(neg),
        candidates=meta,input_hashes=bindings,elapsed_seconds=time.monotonic()-begin,
        decision_gate_unchanged=s['numerical_gate'],self_tests=3,
        scope='Post-readout descriptive paired within-label request bootstrap for all six valid new candidates. No new fitting, generation or execution.',
        limitations='Assumes exchangeable requests within label; not user-clustered. Same reused development set; historical/within-run selection not corrected. Conditional intervals are neither seed uncertainty nor independent generalization evidence; no significance or equivalence claims.')
    payload=json.dumps(out,sort_keys=True,indent=2).encode()
    assert not re.search(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,})',payload)
    with (R/'readout-v1/sensitivity.json').open('xb') as f:f.write(payload)
    print(json.dumps({k:v for k,v in out.items() if k!='input_hashes'},sort_keys=True))
if __name__=='__main__':main()
