"""Retrospective, label-using convex-hull opportunity bound, NOT deployable gain.

Each library is confined to its own already closed Spooky trajectory. No new
program or model is run. The numerical Frank-Wolfe gap bounds optimization error;
it does not bound statistical/generalization error. MLE-STAR already ensembles.
"""
import csv,hashlib,json,os,statistics,sys,time
from pathlib import Path
import numpy as np
from scipy.optimize import minimize
from sklearn.metrics import log_loss
B=Path('/research/d7/spc/yzyang4');OUT=B/'convex-opportunity-20261003-v1'
TASK='spooky-author-identification';CLASSES=['EAP','HPL','MWS']
ROOTS={
 'task-feedback-real-20261001-v6':'15751d3b52bdc42617df02006ce724635f4bf49df6e477686769fd1979d53403',
 'task-feedback-upper-20261002-v1':'9fe231e1b9e2da8cb51fadb7ff9844b074c10e8e3dc64d1d1f3be170fb0703a0',
 'task-feedback-local-edit-20261002-v1':'7bd84ff0e867043b2787d5c07af867eff50370f4e7b6bafa811ef215196c4139',
 'public-example-feedback-20261003-v1':'40e6bc3301c1db52fa09a794577c0b5dc95533302b0e460a044942a6485c5376'}
HASHES={}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):
    raw=p.read_bytes();HASHES[str(p)]=hashlib.sha256(raw).hexdigest();return json.loads(raw)
def rows(p):
    HASHES[str(p)]=sha(p)
    with p.open(newline='',encoding='utf-8-sig') as f:return list(csv.DictReader(f))
def write(p,o):
    with p.open('x') as f:json.dump(o,f,sort_keys=True,indent=2,allow_nan=False)
def solve(a):
    """Columns are fixed candidates' positive true-class probabilities."""
    assert a.ndim==2 and a.shape[1]>0 and np.isfinite(a).all() and (a>0).all()
    f=lambda w:-float(np.log(a@w).mean())
    jac=lambda w:-np.mean(a/(a@w)[:,None],axis=0)
    m=a.shape[1];single=-np.log(a).mean(0);best=int(single.argmin())
    w=np.eye(m)[best];success=True
    if m>1:
        opt=minimize(f,np.full(m,1/m),jac=jac,method='SLSQP',bounds=[(0.,1.)]*m,
            constraints=[dict(type='eq',fun=lambda x:x.sum()-1,jac=lambda x:np.ones(m))],
            options=dict(ftol=1e-13,maxiter=1000))
        v=np.maximum(opt.x,0);v=v/v.sum();success=bool(opt.success)
        if f(v)<f(w):w=v
    assert (w>=0).all() and abs(w.sum()-1)<1e-12
    value=f(w);g=jac(w);gap=max(0.,float(g@w-g.min()))
    baseline=float(single[best]);gain=baseline-value
    assert gain>=-1e-12
    return dict(best_single_loss=baseline,mixture_loss=value,
        empirical_gain_lower=max(0.,gain),empirical_gain_upper=max(0.,gain)+gap+1e-12,
        numerical_dual_gap=gap,numerically_resolved=gap<1e-7,optimizer_success=success,
        nonzero_weights=int(np.sum(w>1e-8))),w
def tests():
    # Neither specialist beats the .5 incumbent, yet their mean does: the
    # checker must not confuse best-single headroom with convex-hull headroom.
    a=np.array([[.5,.9,.2],[.5,.2,.9]])
    r,w=solve(a);assert abs(r['mixture_loss']+np.log(.55))<1e-10
    assert r['empirical_gain_lower']>.09 and r['numerical_dual_gap']<1e-8
    r,_=solve(np.array([[.8,.5,.6],[.8,.5,.6]]));assert r['empirical_gain_upper']<1e-9
    r,_=solve(np.full((10,3),.7));assert r['empirical_gain_upper']<1e-9
    r,_=solve(np.array([[.7],[.8]]));assert r['numerical_dual_gap']==0
    rng=np.random.default_rng(104101);a=rng.uniform(.05,.95,(19,4));w=np.full(4,.25)
    g=-np.mean(a/(a@w)[:,None],axis=0)
    for i in range(4):
        d=np.eye(4)[i]*1e-6
        fd=(-np.log(a@(w+d)).mean()+np.log(a@(w-d)).mean())/2e-6
        assert abs(fd-g[i])<1e-8
    return dict(status='PASS',fixtures=5,scope='algorithm checks only; not research effect')
def main():
    os.umask(0o077);began=time.monotonic();test=tests();OUT.mkdir()
    write(OUT/'plan.json',dict(role='LABEL_USING_RETROSPECTIVE_OPPORTUNITY_BOUND_NOT_METHOD',
        roots=ROOTS,source_sha256=sha(Path(__file__)),commit='8ec74c5a4e7eaaa334a7f0f34dbfd220120e6a02',
        library='all valid submissions within each closed Spooky trajectory, exact probability-vector dedup',
        endpoint='best single empirical logloss minus optimum over convex mixtures; numerical dual-gap interval',
        comparator='within-trajectory best already observed candidate, not cross-run cherry-picked candidate',
        limitations='D_search labels fit the mixture AND score it. No generalization, E2E or novel method claim. Historical adaptive libraries; no correction for selection. Original costs retained, new CPU only.',
        gpu=0,api=0,new_task_fits=0,cohort_permission='only already-open Spooky development',cpu_cap_seconds=180))
    old=B/'task-feedback-real-20261001-v6';sys.path.insert(0,str(old))
    assert sha(old/'task_feedback_real_20261001.py')=='4b155d927c12f063e0838b5708085fe1bc55c4983197a3d8d2453696d73c55ad'
    import task_feedback_real_20261001 as rt;rt.setup()
    from dojo.config_dataclasses.run import RunConfig
    from dojo.tasks.mlebench.task import MLEBenchTask
    index=next(s['index'] for s in read(old/'plan.json')['schedule'] if s['task']==TASK)
    cfg=RunConfig.load_from_json(old/f'configs/{index}.json');obj=MLEBenchTask(cfg.task)
    assert obj._search_only_score and not obj.private_dir.exists()
    spec=obj._search_only_module.SPEC[TASK]
    truthrows=rows(B/spec.get('source',spec.get('view'))/'private/dsearch.csv')
    truth={r['id']:CLASSES.index(r['author']) for r in truthrows};assert len(truth)==len(truthrows)
    ids=sorted(truth);y=np.array([truth[i] for i in ids]);out=[];private=[]
    for batch,h in ROOTS.items():
        root=B/batch;plan=read(root/'plan.json');assert sha(root/'plan.json')==h and (root/'all-closed.json').is_file()
        for s in plan['schedule']:
            if s['task']!=TASK:continue
            ep=root/f'episode-{s["index"]}';assert (ep/'closed.json').is_file()
            ps=[];seen=set();metrics=[];steps=[]
            for a in sorted(ep.glob('action-*'),key=lambda p:int(p.name.split('-')[-1])):
                if not (a/'result.json').is_file():continue
                result=read(a/'result.json')
                if not result['valid']:continue
                rr=rows(a/'submission.private.csv');lookup={r['id']:r for r in rr}
                assert len(rr)==len(lookup)==len(ids) and set(lookup)==set(ids)
                p=np.array([[float(lookup[i][c]) for c in CLASSES] for i in ids])
                assert p.shape==(len(ids),3) and np.isfinite(p).all() and (p>=0).all() and np.allclose(p.sum(1),1)
                p=np.clip(p,np.finfo(float).eps,1-np.finfo(float).eps);p/=p.sum(1,keepdims=True)
                loss=float(-np.log(p[np.arange(len(y)),y]).mean())
                assert abs(log_loss(y,p,labels=[0,1,2])-loss)<1e-12 and abs(result['metric']-loss)<1e-10
                metrics.append(loss);digest=hashlib.sha256(p.tobytes()).hexdigest()
                if digest not in seen:ps.append(p);steps.append(int(a.name.split('-')[-1]));seen.add(digest)
            rec=dict(batch=batch,index=s['index'],arm=s['arm'],seed=s['seed'],task=TASK,
                automatic=(batch.endswith('20261001-v6') or ('upper' in batch and s['arm'] in ('A','B')) or 'public-example' in batch),
                n_valid=len(metrics),n_unique=len(ps),has_predictions=bool(ps),
                best_single_loss=None,mixture_loss=None,empirical_gain_lower=None,empirical_gain_upper=None,
                numerical_dual_gap=None,numerically_resolved=None,optimizer_success=None,nonzero_weights=None)
            if ps:
                a=np.column_stack([p[np.arange(len(y)),y] for p in ps]);v,w=solve(a);rec.update(v)
                assert abs(rec['best_single_loss']-min(metrics))<1e-12
                private.append(dict(batch=batch,index=s['index'],steps=steps,weights=w.tolist()))
            out.append(rec)
    with (OUT/'runs.csv').open('x',newline='') as f:w=csv.DictWriter(f,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
    groups={}
    for scope in ('all','automatic','current_public_examples'):
        rr=[r for r in out if scope=='all' or (scope=='automatic' and r['automatic']) or (scope=='current_public_examples' and 'public-example' in r['batch'])]
        vv=[r for r in rr if r['has_predictions']];g=[r['empirical_gain_lower'] for r in vv]
        groups[scope]=dict(assigned=len(rr),with_predictions=len(vv),multiple_unique=sum(r['n_unique']>1 for r in vv),
            numerical_unresolved=sum(not r['numerically_resolved'] for r in vv),
            empirical_gain_median=statistics.median(g) if g else None,sample_variance=statistics.variance(g) if len(g)>1 else None,
            certified_below_005=sum(r['empirical_gain_upper']<.005 for r in vv),attained_at_least_005=sum(r['empirical_gain_lower']>=.005 for r in vv),
            max_gain_upper=max((r['empirical_gain_upper'] for r in vv),default=None))
    write(OUT/'bindings.private.json',HASHES);write(OUT/'weights.private.json',private)
    result=dict(status='DESCRIPTIVE_EMPIRICAL_CONVEX_ORACLE_ONLY',groups=groups,rows=out,tests=test,
        plan_sha256=sha(OUT/'plan.json'),runs_sha256=sha(OUT/'runs.csv'),elapsed_seconds=time.monotonic()-began,
        interpretation='Numerical optimum on used development labels, not statistical confidence or deployable improvement; no discarded failed trajectory.',gpu=0,api=0,new_task_fits=0)
    write(OUT/'summary.json',result);print(json.dumps({k:v for k,v in result.items() if k!='rows'},sort_keys=True))
if __name__=='__main__':
    if '--test' in sys.argv:print(json.dumps(tests()))
    else:main()
