"""Posthoc CV on fixed old libraries; NOT independent of adaptive generation.

Same training rows choose either the best single or the best TWO-member mixture.
Report pair-count-weighted within-fold AUC, never pool differently scaled scores
across folds. This sensitivity cannot rehabilitate a reused development cohort.
"""
import csv,hashlib,itertools,json,os,statistics,sys,time
from pathlib import Path
import numpy as np
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import roc_auc_score
B=Path('/research/d7/spc/yzyang4');R=B/'pairmix-opportunity-20261003-v1';OUT=B/'pairmix-sensitivity-20261003-v1'
def read(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def write(p,o):
    with p.open('x') as f:json.dump(o,f,sort_keys=True,indent=2,allow_nan=False)
def main():
    os.umask(0o077);began=time.monotonic();prior=read(R/'summary.json');plan=read(R/'plan.json')
    assert sha(R/'plan.json')=='e72d40e131eaa2a05d8588b96c23f468ae7a5a626436918faa9dfa05bf0f2e43'
    source=B/'pairmix_opportunity_20261003.py';assert sha(source)==plan['source_sha256']
    for name,h in read(R/'bindings.private.json').items():assert sha(Path(name))==h
    sys.path.insert(0,str(B));from pairmix_opportunity_20261003 import pair_oracle
    OUT.mkdir();write(OUT/'plan.json',dict(role='POSTHOC_FIXED_LIBRARY_CV_SENSITIVITY_NOT_CONFIRMATION',
        commit='8ec74c5a4e7eaaa334a7f0f34dbfd220120e6a02',
        prior_summary_sha256=sha(R/'summary.json'),source_sha256=sha(Path(__file__)),seed=104301,folds=5,
        cohort='Every automatic Pizza trajectory in prior full four-root census; no oracle-gain screening',
        method='Exact two-member AUC mixture selected on fold-train labels, deployed as float64 on fold-validation',
        comparator='Best individual candidate selected on EXACT SAME fold-train rows',
        endpoint='Within-fold validation AUC gain, weighted by positive-negative pair count; no pooled cross-fold AUC',
        limits='All candidates were previously generated/adapted using this development dataset. Held-fold labels affected candidate generation. Does not provide honest new generalization, task replication or end-to-end method benefit.',
        cpu_cap_seconds=180,gpu=0,api=0,new_task_fits=0))
    bindings=read(R/'bindings.private.json');truthpaths=[p for p in bindings if p.endswith('/private/dsearch.csv')];assert len(truthpaths)==1
    truth={r['request_id']:int(r['requester_received_pizza']) for r in rows(Path(truthpaths[0]))};ids=sorted(truth);y=np.array([truth[k] for k in ids])
    folds=list(StratifiedKFold(n_splits=5,shuffle=True,random_state=104301).split(np.zeros(len(y)),y));out=[];foldrows=[]
    assert sorted(np.concatenate([vi for ti,vi in folds]).tolist())==list(range(len(y)))
    for ti,vi in folds:assert not set(ti)&set(vi) and len(ti)+len(vi)==len(y)
    for r in prior['rows']:
        if not r['automatic']:continue
        root=B/r['batch']/f'episode-{r["index"]}';ps=[];seen=set()
        for a in sorted(root.glob('action-*'),key=lambda p:int(p.name.split('-')[-1])):
            if not (a/'result.json').is_file() or not read(a/'result.json')['valid']:continue
            rr=rows(a/'submission.private.csv');lookup={x['request_id']:float(x['requester_received_pizza']) for x in rr}
            assert len(lookup)==len(rr)==len(ids) and set(lookup)==set(ids)
            p=np.array([lookup[k] for k in ids]);fingerprint=hashlib.sha256(p.tobytes()).hexdigest()
            if fingerprint not in seen:ps.append(p);seen.add(fingerprint)
        assert len(ps)==r['unique_predictions'];numerator=0.;denominator=0;positive=0;negative=0
        for fold,(ti,vi) in enumerate(folds):
            if not ps:continue
            scores=[float(roc_auc_score(y[ti],p[ti])) for p in ps];chosen=int(np.argmax(scores));score=scores[chosen]
            pair=(chosen,chosen);weight=0.
            for i,j in itertools.combinations(range(len(ps)),2):
                value,w,_=pair_oracle(y[ti],ps[i][ti],ps[j][ti])
                if float(value)>score+1e-12:score=float(value);pair=(i,j);weight=float(w)
            base=float(roc_auc_score(y[vi],ps[chosen][vi]))
            p=(1-weight)*ps[pair[0]][vi]+weight*ps[pair[1]][vi]
            mixed=float(roc_auc_score(y[vi],p));gain=mixed-base
            count=int(np.sum(y[vi]==1)*np.sum(y[vi]==0));numerator+=count*gain;denominator+=count
            positive+=gain>1e-12;negative+=gain< -1e-12
            foldrows.append(dict(batch=r['batch'],index=r['index'],seed=r['seed'],fold=fold,
                train_rows=len(ti),validation_rows=len(vi),pair_count=count,baseline_auc=base,mixture_auc=mixed,gain=gain,
                train_best_single=max(scores),train_mixture=score,weight=weight,same_single=pair[0]==pair[1]))
        out.append(dict(batch=r['batch'],index=r['index'],seed=r['seed'],arm=r['arm'],task=r['task'],
            cv_seed=104301,commit='8ec74c5a4e7eaaa334a7f0f34dbfd220120e6a02',plan_sha256=sha(OUT/'plan.json'),
            predictions=len(ps),evaluated_folds=5 if ps else 0,cv_gain=numerator/denominator if denominator else None,
            positive_folds=positive,negative_folds=negative,full_development_oracle_gain=r['gain']))
    groups={}
    for scope in ('all_automatic','current_public_examples'):
        rr=[r for r in out if scope=='all_automatic' or 'public-example' in r['batch']];v=[r['cv_gain'] for r in rr if r['cv_gain'] is not None]
        groups[scope]=dict(assigned=len(rr),valid=len(v),median=statistics.median(v) if v else None,
            sample_variance=statistics.variance(v) if len(v)>1 else None,wins=sum(x>1e-12 for x in v),
            losses=sum(x< -1e-12 for x in v),ties=sum(abs(x)<=1e-12 for x in v))
    for name,data in [('runs.csv',out),('folds.csv',foldrows)]:
        with (OUT/name).open('x',newline='') as f:w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
    result=dict(status='POSTHOC_ADAPTIVE_DEVELOPMENT_SENSITIVITY_ONLY',groups=groups,rows=out,
        plan_sha256=sha(OUT/'plan.json'),files={n:sha(OUT/n) for n in ('runs.csv','folds.csv')},elapsed_seconds=time.monotonic()-began,
        gpu=0,api=0,new_task_fits=0,limitations=read(OUT/'plan.json')['limits'])
    write(OUT/'summary.json',result);print(json.dumps({k:v for k,v in result.items() if k!='rows'},sort_keys=True))
if __name__=='__main__':main()
