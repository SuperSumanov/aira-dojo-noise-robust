"""Closed-cohort readout with independent convex derivative and loss checks."""
import csv,hashlib,json,math,os,statistics,subprocess,sys
from pathlib import Path
import numpy as np
R=Path('/research/d7/spc/yzyang4/calibration-opportunity-20261003-v1')
PLAN='bb2652e5957b6e043138c1c50de95874c487a8ea4fd5e72bb164fe6e03fd8a94'
CLASSES=['EAP','HPL','MWS']
def read(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p):
    with p.open(newline='',encoding='utf-8-sig') as f:return list(csv.DictReader(f))
def normalize(z):
    z=z-z.max(axis=1,keepdims=True);e=np.exp(z);return e/e.sum(axis=1,keepdims=True)
def independent_beta(prob,y):
    z=np.log(np.clip(prob,1e-15,1))
    def derivative(b):return float(np.mean((normalize(b*z)*z).sum(1)-z[np.arange(len(y)),y]))
    if derivative(.25)>=0:return .25
    if derivative(4)<=0:return 4.
    lo,hi=.25,4.
    for _ in range(70):
        mid=(lo+hi)/2
        if derivative(mid)>0:hi=mid
        else:lo=mid
    return (lo+hi)/2
def loss(y,p):return -math.fsum(math.log(max(np.finfo(float).eps,float(p[i,c]))) for i,c in enumerate(y))/len(y)
def analyze():
    assert sha(R/'plan.json')==PLAN and (R/'closed.json').is_file()
    plan=read(R/'plan.json');assert len(read(R/'closed.json')['returncodes'])==3
    for f,h in plan['files'].items():assert sha(R/f)==h,f
    # All assigned workers must be terminal before any score is opened.
    for i in range(3):assert (R/f'episode-{i}/closed.json').is_file()
    sys.path.insert(0,str(R));from calibration_opportunity_20261003 import runtime
    m=runtime();from dojo.config_dataclasses.run import RunConfig
    from dojo.tasks.mlebench.task import MLEBenchTask
    cfg=RunConfig.load_from_json(R/'configs/0.json');task=MLEBenchTask(cfg.task)
    assert task._search_only_score and not task.private_dir.exists()
    spec=task._search_only_module.SPEC[cfg.task.name]
    truthrows=rows(m.B/spec.get('source',spec.get('view'))/'private/dsearch.csv')
    truth={r['id']:CLASSES.index(r['author']) for r in truthrows};assert len(truth)==len(truthrows)
    records=[];bindings=[]
    for i,seed in enumerate(plan['seeds']):
        a=R/f'episode-{i}/action-0';rp=a/'result.json'
        r=read(rp) if rp.is_file() else None
        rec=dict(index=i,seed=seed,valid=False,original=None,calibrated=None,improvement=None,beta=None,
                 original_sha256=None,calibrated_sha256=None,public_original_loss=None,public_calibrated_loss=None,
                 best_embedding_weight=None,changed_argmax=None,seconds=r['seconds'] if r else None,
                 calibration_seconds=None,commit=plan['commit'],plan_sha256=PLAN)
        if r and r['valid']:
            assert r['index']==i and r['seed']==seed and r['plan_sha256']==PLAN
            assert r['exit_code']==0 and not r['timed_out'] and r['error_type'] is None
            receipt=read(a/'calibration-receipt.json')
            for f,h in receipt['files'].items():assert sha(a/f)==h
            arr=np.load(a/'public-calibration.private.npz',allow_pickle=False)
            oof=arr['oof'];y=arr['labels'];raw=arr['query_original'];cal=arr['query_calibrated'];b=receipt['beta']
            assert oof.shape==(len(y),3) and raw.shape==cal.shape and raw.shape[1]==3
            assert np.isfinite(oof).all() and np.isfinite(raw).all() and np.isfinite(cal).all()
            assert np.allclose(oof.sum(1),1) and np.allclose(raw.sum(1),1) and np.allclose(cal.sum(1),1)
            estimated=independent_beta(oof,y)
            assert abs(estimated-b)<1e-5,(estimated,b)
            expected=normalize(b*np.log(np.clip(raw,1e-15,1)))
            assert np.allclose(expected,cal,atol=1e-13,rtol=0)
            assert abs(loss(y,oof)-receipt['public_original_loss'])<1e-12
            assert abs(loss(y,normalize(b*np.log(np.clip(oof,1e-15,1))))-receipt['public_calibrated_loss'])<1e-12
            native=[];predictions=[]
            for arm,expected in [('original',raw),('calibrated',cal)]:
                path=a/f'{arm}.csv';rr=rows(path);ids=[x['id'] for x in rr]
                assert len(ids)==len(set(ids)) and set(ids)==set(truth)
                pred=np.array([[float(x[c]) for c in CLASSES] for x in rr]);assert np.allclose(expected,pred,atol=1e-12,rtol=0)
                value=loss([truth[x] for x in ids],pred)
                score=task._search_only_score(cfg.task.name,path);assert score['split']=='D_search_development_only'
                assert abs(value-score['log_loss'])<1e-12
                native.append(value);predictions.append(pred)
                rec[arm]=value;rec[arm+'_sha256']=sha(path)
            binding=read(a/'binding.json');assert binding['system_bindpaths_disabled'] and binding['namespace']['exact_device_namespace']
            rec.update(valid=True,improvement=native[0]-native[1],beta=b,public_original_loss=receipt['public_original_loss'],
                public_calibrated_loss=receipt['public_calibrated_loss'],best_embedding_weight=receipt['best_embedding_weight'],
                changed_argmax=int(np.sum(predictions[0].argmax(1)!=predictions[1].argmax(1))),calibration_seconds=receipt['calibration_seconds'])
            bindings.append(dict(index=i,receipt_sha256=sha(a/'calibration-receipt.json'),array_sha256=sha(a/'public-calibration.private.npz'),
                result_sha256=sha(rp),binding_sha256=sha(a/'binding.json')))
        records.append(rec)
    vv=[r['improvement'] for r in records if r['valid']]
    accounting=subprocess.check_output(['sacct','-X','-j',read(R/'launch.json')['job'],'-n','-P','-o','JobIDRaw,State,ElapsedRaw,AllocTRES'],env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf'),text=True,timeout=25).strip()
    dest=R/'readout-v1';dest.mkdir()
    with (dest/'runs.csv').open('x',newline='') as f:w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
    result=dict(status='CLOSED_OPPORTUNITY_CHECK_NOT_AGENT_METHOD',verification='PASS',assigned=3,valid_pairs=len(vv),rows=records,
        median_improvement=statistics.median(vv) if vv else None,sample_variance=statistics.variance(vv) if len(vv)>1 else None,
        opportunity_gate=len(vv)==3 and statistics.median(vv)>0 and min(vv)>=0,
        distinct_original_predictions=len({r['original_sha256'] for r in records if r['valid']}),
        distinct_calibrated_predictions=len({r['calibrated_sha256'] for r in records if r['valid']}),
        plan_sha256=PLAN,readout_source_sha256=sha(Path(__file__)),bindings=bindings,accounting=accounting,
        files={'runs.csv':sha(dest/'runs.csv')},scope=plan['limitations'])
    with (dest/'summary.json').open('x') as f:json.dump(result,f,sort_keys=True,indent=2,allow_nan=False)
    print(json.dumps(result,sort_keys=True))
if __name__=='__main__':analyze()
