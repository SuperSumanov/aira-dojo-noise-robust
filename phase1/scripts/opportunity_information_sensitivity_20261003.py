"""Pre-readout frozen, conditional query sensitivity; not confirmation inference."""
import argparse,csv,hashlib,json,math,sys,time
from pathlib import Path
import numpy as np
from scipy.stats import rankdata
R=Path('/research/d7/spc/yzyang4/opportunity-information-20261003-v2')
PLAN='6b91aba97ee53f6da2335064f1dbe4277020b8744fd95a3575e4c99329936d2f'
def read(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def write(p,x):
    with p.open('x') as f:json.dump(x,f,indent=2,sort_keys=True,allow_nan=False)
def auc(y,p):
    n1=int(y.sum());n0=len(y)-n1;assert n1 and n0
    return float((rankdata(p,method='average')[y==1].sum()-n1*(n1+1)/2)/(n1*n0))
def freeze():
    assert sha(R/'plan.json')==PLAN and not (R/'readout-v1').exists()
    assert auc(np.array([0,1]),np.array([.1,.9]))==1
    assert auc(np.array([0,1]),np.array([.5,.5]))==.5
    write(R/'sensitivity-freeze.json',dict(script_sha256=sha(Path(__file__)),plan_sha256=PLAN,
        utc=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),
        status='FROZEN_BEFORE_EFFECT_READOUT_AFTER_RUN_STARTED',replicates=5000,seed_base=104050,
        method='Class-stratified paired query bootstrap. Shared query resample across both generation seeds and all arms. Average two within-seed final retained-score differences; same as median with two seeds.',
        scope='Conditional descriptive intervals only. Adaptive developer-query selection and human witness selection are not accounted for; no new task/run/training uncertainty or multiplicity correction. Does not change original numerical gate.'))
    print('SENSITIVITY_FROZEN_NO_EFFECT_READ')
def analyze():
    began=time.monotonic();f=read(R/'sensitivity-freeze.json')
    assert sha(R/'plan.json')==PLAN and sha(Path(__file__))==f['script_sha256']
    assert read(R/'closed.json')['service_closed'] and read(R/'readout-v1/verification.json')['status']=='PASS'
    out=R/'readout-v1';summary=read(out/'summary.json');sys.path.insert(0,str(R))
    import task_feedback_real_20261001 as x
    m=x.m;m.check();m.setup()
    from dojo.config_dataclasses.run import RunConfig
    from dojo.tasks.mlebench.task import MLEBenchTask
    results=[];inputs={str(out/'summary.json'):sha(out/'summary.json')}
    for ti,name in enumerate(sorted({r['task'] for r in summary['runs']})):
        pairs=[p for p in summary['pairs'] if p['task']==name]
        if len(pairs)!=2 or not all(p['comparable'] for p in pairs):
            results.append(dict(task=name,status='INCOMPLETE_COMPARABLE_PAIRS'));continue
        records=[r for r in summary['runs'] if r['task']==name];seeds=sorted({r['seed'] for r in records})
        cfg=RunConfig.load_from_json(R/'configs'/f'{records[0]["index"]}.json');task=MLEBenchTask(cfg.task)
        assert task._search_only_score and not task.private_dir.exists();spec=task._search_only_module.SPEC[name]
        label=m.B/spec.get('source',spec.get('view'))/'private/dsearch.csv';inputs[str(label)]=sha(label);truth=rows(label)
        is_auc=name=='random-acts-of-pizza';key='request_id' if is_auc else 'id';target='requester_received_pizza' if is_auc else 'author'
        y=np.array([int(t[target]) if is_auc else {'EAP':0,'HPL':1,'MWS':2}[t[target]] for t in truth]);pred={}
        for r in records:
            path=R/f'episode-{r["index"]}/action-{r["selected_step"]}/submission.private.csv';inputs[str(path)]=sha(path)
            rr=rows(path);d={t[key]:t for t in rr};assert len(d)==len(rr)==len(truth) and set(d)=={t[key] for t in truth}
            values=np.array([float(d[t[key]][target]) if is_auc else -math.log(max(float(d[t[key]][t[target]]),1e-15)) for t in truth])
            v=auc(y,values) if is_auc else float(values.mean());assert math.isclose(v,r['selected'],abs_tol=1e-11)
            pred[(r['seed'],r['arm'])]=values
        def contrasts(idx):
            scores={k:auc(y[idx],v[idx]) if is_auc else -float(v[idx].mean()) for k,v in pred.items()}
            return [float(np.mean([scores[(s,a)]-scores[(s,b)] for s in seeds])) for a,b in [('B','A'),('C','A'),('C','B')]]
        observed=contrasts(np.arange(len(y)));names=['B_minus_A','C_minus_A','C_minus_B']
        for k,v in zip(names,observed):
            expected=next(c['median'] for c in summary['contrasts'] if c['task']==name and c['contrast']==k)
            assert math.isclose(v,expected,abs_tol=1e-11)
        strata=[np.flatnonzero(y==v) for v in np.unique(y)];rng=np.random.default_rng(104050+ti);draws=[]
        for _ in range(5000):draws.append(contrasts(np.concatenate([rng.choice(idx,len(idx),replace=True) for idx in strata])))
        bounds=np.quantile(np.array(draws),[.025,.975],axis=0)
        for j,k in enumerate(names):results.append(dict(task=name,contrast=k,observed=observed[j],conditional_interval=[float(bounds[0,j]),float(bounds[1,j])],n_queries=len(y),rng_seed=104050+ti,status='DESCRIPTIVE_CONDITIONAL'))
    for p,h in inputs.items():assert sha(Path(p))==h
    result=dict(status='COMPLETE',plan_sha256=PLAN,freeze=f,summary_sha256=sha(out/'summary.json'),seconds=time.monotonic()-began,results=results)
    write(out/'conditional-sensitivity.json',result);print(json.dumps(result))
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('mode',choices=['freeze','analyze']);globals()[a.parse_args().mode]()
