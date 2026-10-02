"""Posthoc convex-direction diagnosis of two closed recipes; no new model fit."""
import argparse,csv,hashlib,json,math,statistics,sys,time
from pathlib import Path
import numpy as np
from scipy.optimize import minimize_scalar
B=Path('/research/d7/spc/yzyang4')
OUT=B/'blend-direction-20261003-v1'
ROOTS={
'nb_ratio':('nb-ratio-opportunity-20261003-v1','b810f31f70ea89e81bf1a1557544c0e9fe072ce6534fdb1449665be7f12e53fc','f0238c5aef32e889c8d4e9fc56fcdca0fb960ba73049c33258092e2fa6d282a1'),
'style':('style-opportunity-20261003-v1','dfa60c1c84544d02e8effd5a3d5e18ce38839d502c8e6d615700856164032371','718c1b94811325474d5e2ff53049446cc170b0d06348aa95ed12b790be16d2a5')}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_bytes())
def write(p,x):
    with Path(p).open('x') as f:json.dump(x,f,sort_keys=True,indent=2,allow_nan=False)
def rows(p):
    with Path(p).open(newline='',encoding='utf-8-sig') as f:return list(csv.DictReader(f))
def solve(x,q):
    x=np.asarray(x,float);q=np.asarray(q,float);d=q-x
    assert np.isfinite(x).all() and np.isfinite(q).all() and (x>0).all() and (q>0).all()
    der=lambda w:-float(np.mean(d/(x+w*d)))
    loss=lambda w:-float(np.log(x+w*d).mean())
    if der(0)>=0:w=0.
    elif der(1)<=0:w=1.
    else:
        lo,hi=0.,1.
        for _ in range(70):
            m=(lo+hi)/2
            if der(m)>0:hi=m
            else:lo=m
        w=(lo+hi)/2
    opt=minimize_scalar(loss,bounds=(0.,1.),method='bounded',options={'xatol':1e-12})
    assert opt.success
    other=min([0.,float(opt.x),1.],key=loss)
    assert abs(loss(other)-loss(w))<1e-10
    scalar=-math.fsum(float(b-a)/float(a) for a,b in zip(x,q))/len(x)
    assert math.isclose(scalar,der(0),rel_tol=1e-11,abs_tol=1e-12)
    # Convex tangent lower bound over [0,1], not statistical confidence.
    gap=max(0.,der(w)*w,der(w)*(w-1))
    gain=loss(0)-loss(w)
    return dict(slope_at_zero=der(0),oracle_weight=w,oracle_gain=gain,
                oracle_gain_upper=gap+gain+1e-12,boundary_zero_optimal=bool(der(0)>=0))
def tests():
    assert solve([.5,.5],[.4,.4])['boundary_zero_optimal']
    assert solve([.4,.4],[.6,.6])['oracle_weight']==1
    assert solve([.5,.5],[.5,.5])['oracle_gain']==0
    assert abs(solve([.9,.2],[.2,.9])['oracle_weight']-.5)<1e-10
    return 4
def prepare():
    assert not OUT.exists()
    for root,ph,sh in ROOTS.values():
        assert sha(B/root/'plan.json')==ph and sha(B/root/'readout-v1/summary.json')==sh
    OUT.mkdir(mode=0o700)
    write(OUT/'plan.json',dict(role='POSTHOC_DIRECTION_DIAGNOSIS_NOT_POLICY_OR_NEW_METHOD',
        source_sha256=sha(__file__),roots=ROOTS,commit='ad2eff1c005e093cf2fc60e3c50b6d2e962a6eea',
        endpoint='public OOF vs already-used external development derivative at zero mixture weight; exact 1D empirical oracle',
        comparison='Both closed recipes, all3 seeds each, no outcome-based exclusion or fitted replacement.',
        bootstrap_seed=104401,bootstrap_replicates=5000,cpu_cap_seconds=180,gpu=0,api=0,new_task_model_fits=0,
        limitations='Historical selected parent; same task and adaptively reused D_search. Direction is descriptive empirical convex geometry, not proof of population shift. Query oracle is label-fitted and never deployed.',
        tests=tests()))
    print(json.dumps(dict(status='PREPARED',plan_sha256=sha(OUT/'plan.json'))))
def run():
    t=time.monotonic();plan=read(OUT/'plan.json')
    assert plan['source_sha256']==sha(__file__) and not (OUT/'summary.json').exists()
    tests()
    r0=B/ROOTS['nb_ratio'][0]
    sys.path.insert(0,str(r0));from nb_ratio_opportunity_20261003 import runtime
    m=runtime();from dojo.config_dataclasses.run import RunConfig
    from dojo.tasks.mlebench.task import MLEBenchTask
    cfg=RunConfig.load_from_json(r0/'configs/0.json');task=MLEBenchTask(cfg.task)
    assert task._search_only_score and not task.private_dir.exists()
    spec=task._search_only_module.SPEC[cfg.task.name]
    truthrows=rows(m.B/spec.get('source',spec.get('view'))/'private/dsearch.csv')
    classes=['EAP','HPL','MWS'];truth={r['id']:classes.index(r['author']) for r in truthrows}
    assert len(truth)==len(truthrows)
    rr=[];bootinputs={};bindings=[]
    for name,(root,ph,sh) in ROOTS.items():
        root=B/root;assert sha(root/'plan.json')==ph and sha(root/'readout-v1/summary.json')==sh
        summ=read(root/'readout-v1/summary.json');assert summ['verification']=='PASS' and summ['valid_pairs']==3
        grad=[];aligned=None
        for i,seed in enumerate(read(root/'plan.json')['seeds']):
            a=root/f'episode-{i}/action-0';rec=read(a/'calibration-receipt.json')
            for f,h in rec['files'].items():assert sha(a/f)==h
            z=np.load(a/'public-calibration.private.npz',allow_pickle=False)
            ids=[r['id'] for r in rows(a/'original.csv')]
            assert len(ids)==len(set(ids)) and set(ids)==set(truth)
            if aligned is None:aligned=ids
            else:assert aligned==ids
            y=np.array([truth[k] for k in ids]);yp=z['labels']
            row=dict(recipe=name,index=i,seed=seed,public_selected_weight=rec['weight'],
                deployed_improvement=summ['rows'][i]['improvement'],summary_sha256=sh)
            for label,p,q,yy in [('public',z['original_oof'],z['nb_oof'],yp),
                                 ('query',z['query_original'],z['query_nb'],y)]:
                assert p.shape==q.shape==(len(yy),3)
                assert np.allclose(p.sum(1),1,atol=1e-12) and np.allclose(q.sum(1),1,atol=1e-12)
                x=p[np.arange(len(yy)),yy];v=q[np.arange(len(yy)),yy]
                ans=solve(x,v)
                row.update({label+'_'+k:value for k,value in ans.items()})
                if label=='public':assert abs(ans['oracle_weight']-rec['weight'])<1e-5
                else:
                    grad.append(1-v/x)
                    gain=-float(np.log(x).mean())+float(np.log((1-rec['weight'])*x+rec['weight']*v).mean())
                    assert abs(gain-row['deployed_improvement'])<1e-12
            rr.append(row);bindings.append(dict(recipe=name,index=i,array_sha256=sha(a/'public-calibration.private.npz')))
        bootinputs[name]=(np.array(grad),y)
    rng=np.random.default_rng(plan['bootstrap_seed']);summary={}
    for name,(g,y) in bootinputs.items():
        strata=[np.flatnonzero(y==c) for c in range(3)]
        sims=[]
        for _ in range(plan['bootstrap_replicates']):
            ix=np.concatenate([rng.choice(s,size=len(s),replace=True) for s in strata])
            sims.append(float(np.median(g[:,ix].mean(1))))
        selected=[r for r in rr if r['recipe']==name]
        summary[name]=dict(runs=len(selected),public_negative_directions=sum(r['public_slope_at_zero']<0 for r in selected),
            query_nonnegative_directions=sum(r['query_slope_at_zero']>=0 for r in selected),
            median_query_slope=statistics.median(r['query_slope_at_zero'] for r in selected),
            conditional_median_slope_ci=np.quantile(sims,[.025,.975]).tolist(),
            maximum_query_oracle_gain_upper=max(r['query_oracle_gain_upper'] for r in selected),
            median_query_oracle_gain=statistics.median(r['query_oracle_gain'] for r in selected))
    with (OUT/'runs.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
    out=dict(role=plan['role'],status='PASS',plan_sha256=sha(OUT/'plan.json'),source_sha256=sha(__file__),
        groups=summary,rows=rr,bindings=bindings,runs_sha256=sha(OUT/'runs.csv'),
        gpu=0,api=0,new_task_model_fits=0,elapsed_seconds=time.monotonic()-t,
        limitations=plan['limitations']+' Conditional bootstrap resamples the same requests jointly across3 fits; no task/training/adaptive-selection uncertainty correction.')
    write(OUT/'summary.json',out)
    print(json.dumps(dict(status='PASS',groups=summary,summary_sha256=sha(OUT/'summary.json'),elapsed_seconds=out['elapsed_seconds'])))
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('mode',choices=['prepare','run']);mode=a.parse_args().mode
    prepare() if mode=='prepare' else run()

