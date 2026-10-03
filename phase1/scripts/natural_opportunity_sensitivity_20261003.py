"""Post-readout conditional sample sensitivity, not a new qualification gate."""
import csv,hashlib,json,math,sys,time
from pathlib import Path
import numpy as np
from scipy.stats import rankdata
R=Path('/research/d7/spc/yzyang4/natural-opportunity-20261003-v1')
def read(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def auc(y,p):
    n1=int(y.sum());n0=len(y)-n1;assert n1 and n0
    return float((rankdata(p,method='average')[y==1].sum()-n1*(n1+1)/2)/(n1*n0))
assert auc(np.array([0,1,0,1]),np.array([.1,.9,.1,.9]))==1
assert auc(np.array([0,1]),np.array([.5,.5]))==.5
began=time.monotonic();summary=read(R/'readout.json');assert read(R/'verification.json')['status']=='PASS'
bindings=read(R/'readout-bindings.private.json')
for p,h in bindings.items():assert sha(Path(p))==h
sys.path.insert(0,str(R));import natural_opportunity_20261003 as m
m.check();m.runtime()
from dojo.config_dataclasses.run import RunConfig
from dojo.tasks.mlebench.task import MLEBenchTask
results=[]
for state in (0,1,3,4,5):
    st=next(s for s in summary['states'] if s['state']==state)
    if st['valid_pairs']!=2:
        results.append(dict(state=state,status='INCOMPLETE_TWO_SEED_PAIR',interval=None));continue
    schedule=[s for s in read(R/'plan.json')['schedule'] if s['state']==state]
    cfg=RunConfig.load_from_json(R/'configs'/f'{schedule[0]["index"]}.json');task=MLEBenchTask(cfg.task);spec=task._search_only_module.SPEC[cfg.task.name]
    label=m.B/spec.get('source',spec.get('view'))/'private/dsearch.csv';truth=rows(label)
    is_auc=cfg.task.name=='random-acts-of-pizza';key='request_id' if is_auc else 'id';target='requester_received_pizza' if is_auc else 'author'
    y=np.array([int(t[target]) if is_auc else {'EAP':0,'HPL':1,'MWS':2}[t[target]] for t in truth]);pred={}
    for s in schedule:
        pr={r[key]:r for r in rows(R/f'episode-{s["index"]}/action-0/submission.private.csv')}
        pred[(s['seed'],s['arm'])]=np.array([float(pr[t[key]][target]) if is_auc else -math.log(max(float(pr[t[key]][t[target]]),1e-15)) for t in truth])
    def delta(index):
        if is_auc:return float(np.mean([auc(y[index],pred[(seed,'modified')][index])-auc(y[index],pred[(seed,'original')][index]) for seed in (42,173)]))
        return float(np.mean([np.mean(pred[(seed,'original')][index]-pred[(seed,'modified')][index]) for seed in (42,173)]))
    observed=delta(np.arange(len(y)));assert math.isclose(observed,st['median_gain'],abs_tol=1e-11)
    rng=np.random.default_rng(104041+state);strata=[np.flatnonzero(y==v) for v in np.unique(y)];values=[]
    for _ in range(5000):values.append(delta(np.concatenate([rng.choice(idx,len(idx),replace=True) for idx in strata])))
    lo,hi=np.quantile(values,[.025,.975]);results.append(dict(state=state,task=cfg.task.name,n_queries=len(y),status='DESCRIPTIVE_CONDITIONAL',observed_gain=observed,interval=[float(lo),float(hi)],rng_seed=104041+state,bootstrap_replicates=5000))
out=dict(status='COMPLETE',plan_sha256=sha(R/'plan.json'),summary_sha256=sha(R/'readout.json'),script_sha256=sha(Path(__file__)),results=results,seconds=time.monotonic()-began,
    definition='Stratified paired query bootstrap; average of the two fixed training-seed metric differences within each resample. Same query resample across both seeds and arms. Percentile conditional intervals.',
    limitations='Posthoc sensitivity only. Conditional on reused developer data, chosen states/changes and fitted predictions; excludes discovery/selection bias, training uncertainty, new-task uncertainty and multiple-testing adjustment. Does not alter frozen gate or establish confirmation significance.')
with (R/'conditional-sensitivity.json').open('x') as f:json.dump(out,f,sort_keys=True,indent=2)
print(json.dumps(out))
