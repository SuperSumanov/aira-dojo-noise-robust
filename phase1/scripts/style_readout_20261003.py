"""Frozen readout for the last known style reference, never an agent claim."""
import csv,hashlib,json,os,statistics,subprocess,sys
from pathlib import Path
import numpy as np
R=Path('/research/d7/spc/yzyang4/style-opportunity-20261003-v1')
OLD=Path('/research/d7/spc/yzyang4/calibration-opportunity-20261003-v1')
PLAN='dfa60c1c84544d02e8effd5a3d5e18ce38839d502c8e6d615700856164032371'
CLASSES=['EAP','HPL','MWS']

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_bytes())
def rows(p):
    with p.open(newline='',encoding='utf-8-sig') as f:return list(csv.DictReader(f))
def lossvec(y,p):return -np.log(np.clip(p[np.arange(len(y)),y],np.finfo(float).eps,1))
def norm(p):
    p=np.clip(p,1e-15,1-1e-15);return p/p.sum(1,keepdims=True)
def weight(a,b,y):
    x=a[np.arange(len(y)),y];d=b[np.arange(len(y)),y]-x
    derivative=lambda w:-float(np.mean(d/(x+w*d)))
    if derivative(0)>=0:return 0.
    if derivative(1)<=0:return 1.
    lo,hi=0.,1.
    for _ in range(70):
        mid=(lo+hi)/2
        if derivative(mid)>0:hi=mid
        else:lo=mid
    return (hi+lo)/2

def main():
    assert sha(R/'plan.json')==PLAN and (R/'closed.json').is_file()
    plan=read(R/'plan.json');assert len(read(R/'closed.json')['returncodes'])==3
    for f,h in plan['files'].items():assert sha(R/f)==h,f
    dep=plan['external_dependency'];assert sha(Path(dep['path']))==dep['sha256']
    for i in range(3):assert (R/f'episode-{i}/closed.json').is_file()
    sys.path.insert(0,str(R));from style_opportunity_20261003 import runtime
    m=runtime();from dojo.config_dataclasses.run import RunConfig
    from dojo.tasks.mlebench.task import MLEBenchTask
    cfg=RunConfig.load_from_json(R/'configs/0.json');task=MLEBenchTask(cfg.task)
    assert task._search_only_score and not task.private_dir.exists()
    spec=task._search_only_module.SPEC[cfg.task.name]
    truthrows=rows(m.B/spec.get('source',spec.get('view'))/'private/dsearch.csv')
    truth={r['id']:CLASSES.index(r['author']) for r in truthrows};assert len(truth)==len(truthrows)
    oldpath=OLD/'episode-0/action-0/calibrated.csv'
    assert sha(oldpath)=='f558c3f27b27343f42c64878441016e58043a2e2d85db6739cfeeca052f21f38'
    old={r['id']:[float(r[c]) for c in CLASSES] for r in rows(oldpath)}
    records=[];paired=[];oldpaired=[];aligned_y=None;aligned_ids=None;bindings=[]
    for i,seed in enumerate(plan['seeds']):
        a=R/f'episode-{i}/action-0';rp=a/'result.json';r=read(rp) if rp.is_file() else None
        rec=dict(index=i,seed=seed,valid=False,original=None,style=None,blend=None,improvement=None,
            gain_over_temperature_reference=None,weight=None,public_original_loss=None,public_style_loss=None,public_blend_loss=None,
            original_sha256=None,style_array_sha256=None,blend_sha256=None,changed_argmax=None,
            additional_seconds=None,seconds=r['seconds'] if r else None,commit=plan['commit'],plan_sha256=PLAN)
        if r and r['valid']:
            assert r['index']==i and r['seed']==seed and r['plan_sha256']==PLAN and r['exit_code']==0 and not r['timed_out']
            receipt=read(a/'calibration-receipt.json')
            for f,h in receipt['files'].items():assert sha(a/f)==h
            assert receipt['fold_seed']==seed and receipt['fits']==5 and receipt['convergence_warnings']==0
            assert receipt['feature_count']==31 and receipt['role']=='KNOWN_STYLE_HGB_REFERENCE_NOT_NB_OR_AGENT'
            arr=np.load(a/'public-calibration.private.npz',allow_pickle=False)
            y=arr['labels'];ao=arr['original_oof'];bo=arr['nb_oof'];raw=arr['query_original'];style=arr['query_nb'];blend=arr['query_blend'];w=receipt['weight']
            assert set(arr['fold_id'].tolist())==set(range(5))
            for p in (ao,bo,raw,style,blend):assert p.shape[1]==3 and np.isfinite(p).all() and (p>=0).all() and np.allclose(p.sum(1),1)
            assert abs(weight(ao,bo,y)-w)<1e-5
            assert np.allclose(norm((1-w)*raw+w*style),blend,atol=1e-13,rtol=0)
            for name,key,p in [('original','original',ao),('style','nb',bo),('blend','blend',norm((1-w)*ao+w*bo))]:
                assert abs(float(lossvec(y,p).mean())-receipt[f'public_{key}_loss'])<1e-12
                rec[f'public_{name}_loss']=receipt[f'public_{key}_loss']
            rr=rows(a/'original.csv');ids=[row['id'] for row in rr]
            assert len(ids)==len(set(ids)) and set(ids)==set(truth)==set(old)
            if aligned_ids is None:aligned_ids=ids
            else:assert ids==aligned_ids
            yy=np.array([truth[k] for k in ids]);aligned_y=yy
            oldpred=np.array([old[k] for k in ids]);oldloss=lossvec(yy,oldpred)
            ll={}
            for arm,p,file in [('original',raw,'original.csv'),('blend',blend,'calibrated.csv')]:
                data=rows(a/file);assert [row['id'] for row in data]==ids
                fromcsv=np.array([[float(row[c]) for c in CLASSES] for row in data])
                assert np.allclose(fromcsv,p,atol=1e-12,rtol=0)
                ll[arm]=lossvec(yy,p)
                native=task._search_only_score(cfg.task.name,a/file)
                assert native['split']=='D_search_development_only' and abs(native['log_loss']-ll[arm].mean())<1e-12
                rec[arm]=float(ll[arm].mean());rec[arm+'_sha256']=sha(a/file)
            rec['style']=float(lossvec(yy,style).mean());rec['style_array_sha256']=hashlib.sha256(style.tobytes()).hexdigest()
            binding=read(a/'binding.json');assert binding['system_bindpaths_disabled'] and binding['namespace']['exact_device_namespace']
            rec.update(valid=True,improvement=rec['original']-rec['blend'],gain_over_temperature_reference=float(oldloss.mean())-rec['blend'],weight=w,
                additional_seconds=receipt['additional_seconds'],changed_argmax=int(np.sum(raw.argmax(1)!=blend.argmax(1))))
            paired.append(ll['original']-ll['blend']);oldpaired.append(oldloss-ll['blend'])
            bindings.append(dict(index=i,result_sha256=sha(rp),receipt_sha256=sha(a/'calibration-receipt.json'),array_sha256=sha(a/'public-calibration.private.npz'),binding_sha256=sha(a/'binding.json')))
        records.append(rec)
    vv=[r['improvement'] for r in records if r['valid']];ci=None;oldci=None
    if len(vv)==3:
        rng=np.random.default_rng(104099);groups=[np.flatnonzero(aligned_y==c) for c in range(3)]
        effects=np.array(paired);oldeffects=np.array(oldpaired);bb=[];bbold=[]
        for _ in range(5000):
            ii=np.concatenate([rng.choice(g,size=len(g),replace=True) for g in groups])
            bb.append(float(np.median(effects[:,ii].mean(1))));bbold.append(float(np.median(oldeffects[:,ii].mean(1))))
        ci=np.quantile(bb,[.025,.975]).tolist();oldci=np.quantile(bbold,[.025,.975]).tolist()
    accounting=subprocess.check_output(['sacct','-X','-j',read(R/'launch.json')['job'],'-n','-P','-o','JobIDRaw,State,ElapsedRaw,AllocTRES'],env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf'),text=True,timeout=25).strip()
    dest=R/'readout-v1';dest.mkdir()
    with (dest/'runs.csv').open('x',newline='') as f:w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
    out=dict(status='CLOSED_KNOWN_STYLE_REFERENCE_NOT_AGENT_METHOD',verification='PASS',assigned=3,valid_pairs=len(vv),rows=records,
        median_improvement=statistics.median(vv) if vv else None,sample_variance=statistics.variance(vv) if len(vv)>1 else None,
        opportunity_gate=len(vv)==3 and statistics.median(vv)>=.005 and min(vv)>=0,
        distinct_style_predictions=len({r['style_array_sha256'] for r in records if r['valid']}),distinct_blend_predictions=len({r['blend_sha256'] for r in records if r['valid']}),
        conditional_median_request_ci=ci,conditional_median_vs_temperature_ci=oldci,
        bootstrap=dict(replicates=5000,seed=104099,unit='class-stratified request, paired jointly across fixed3 fits',limitations='adaptive reused development data; no simultaneous/multiple-look or task uncertainty correction'),
        plan_sha256=PLAN,readout_source_sha256=sha(Path(__file__)),bindings=bindings,accounting=accounting,files={'runs.csv':sha(dest/'runs.csv')},scope=plan['limitation'])
    with (dest/'summary.json').open('x') as f:json.dump(out,f,sort_keys=True,indent=2,allow_nan=False)
    print(json.dumps(out,sort_keys=True))
if __name__=='__main__':main()
