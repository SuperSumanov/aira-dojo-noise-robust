"""Exact dyadic-rational two-predictor AUC mixture oracle on opened development.

Labels choose AND score the weight: opportunity diagnostic only, never a method
result. This is an upper bound only for mixtures of at most TWO library members,
not the whole convex hull. No new predictions or task training are performed.
"""
import csv,hashlib,itertools,json,os,statistics,sys,time
from fractions import Fraction
from pathlib import Path
import numpy as np
from sklearn.metrics import roc_auc_score
B=Path('/research/d7/spc/yzyang4');OUT=B/'pairmix-opportunity-20261003-v1'
TASK='random-acts-of-pizza'
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
def integer_vectors(p,q):
    rr=[float(x).as_integer_ratio() for x in list(p)+list(q)]
    scale=max(d for n,d in rr);v=[n*(scale//d) for n,d in rr]
    return v[:len(p)],v[len(p):]
def exact_auc(y,p):
    pos=[v for v,t in zip(p,y) if t==1];neg=[v for v,t in zip(p,y) if t==0]
    return Fraction(sum(2*(a>b)+(a==b) for a in pos for b in neg),2*len(pos)*len(neg))
def pair_oracle(y,p,q):
    a,b=integer_vectors(p,q);d=[v-u for u,v in zip(a,b)];events={};count=0
    pos=[i for i,t in enumerate(y) if t==1];neg=[i for i,t in enumerate(y) if t==0]
    for i in pos:
        for j in neg:
            u=a[i]-a[j];v=d[i]-d[j]
            count+=2*(u>0 or (u==0 and v>0))+(u==0 and v==0)
            if v:
                t=Fraction(-u,v)
                if 0<t<1:events[t]=events.get(t,0)+(2 if v>0 else -2)
    den=2*len(pos)*len(neg);best=exact_auc(y,a);weight=Fraction(0)
    def consider(c,t):
        nonlocal best,weight
        value=Fraction(c,den)
        if value>best:best,weight=value,t
    prev=Fraction(0)
    for t,change in sorted(events.items()):
        consider(count,(prev+t)/2)
        consider(count+change//2,t)
        count+=change;prev=t
    consider(count,(prev+1)/2)
    end=exact_auc(y,b)
    if end>best:best,weight=end,Fraction(1)
    # Independent all-pairs integer arithmetic at the chosen rational weight.
    z=[(weight.denominator-weight.numerator)*u+weight.numerator*v for u,v in zip(a,b)]
    assert exact_auc(y,z)==best
    native=float(roc_auc_score(y,(1-float(weight))*np.asarray(p)+float(weight)*np.asarray(q)))
    return best,weight,native
def tests():
    rng=np.random.default_rng(104201)
    for _ in range(25):
        y=np.array([0,1]*5);p=rng.integers(0,12,10).astype(float);q=rng.integers(0,12,10).astype(float)
        best,w,native=pair_oracle(y,p,q);cuts={Fraction(0),Fraction(1)}
        for i in range(10):
            for j in range(10):
                if y[i]!=1 or y[j]!=0:continue
                u=int(p[i]-p[j]);v=int(q[i]-p[i]-q[j]+p[j])
                if v and 0<Fraction(-u,v)<1:cuts.add(Fraction(-u,v))
        ordered=sorted(cuts);grid=ordered+[(u+v)/2 for u,v in zip(ordered[:-1],ordered[1:])]
        scores=[exact_auc(y,[(1-t)*int(u)+t*int(v) for u,v in zip(p,q)]) for t in grid]
        assert best==max(scores) and abs(native-float(best))<1e-12
    for p,q in [([.1,.9],[.1,.9]),([.5,.5],[.5,.5]),([0.,1.],[1.,0.])]:pair_oracle([0,1],p,q)
    return dict(status='PASS',random_exhaustive_fixtures=25,edge_fixtures=3)
def main():
    os.umask(0o077);began=time.monotonic();test=tests();OUT.mkdir()
    write(OUT/'plan.json',dict(role='LABEL_USING_TWO_MODEL_MIXTURE_ORACLE_NOT_METHOD',roots=ROOTS,
        source_sha256=sha(Path(__file__)),commit='8ec74c5a4e7eaaa334a7f0f34dbfd220120e6a02',
        library='all valid outputs in each closed Pizza trajectory; exact numeric-vector dedup',
        endpoint='best same-trajectory TWO-predictor mixture AUC minus best individual; every real breakpoint enumerated with rational arithmetic',
        limitations='Labels choose AND score coefficients. Not generalization or E2E. Not an upper bound for 3+ mixtures, rank transforms, conditional selectors or new candidates. Same adaptive historical dataset; original costs remain.',
        cpu_cap_seconds=180,gpu=0,api=0,new_task_fits=0))
    old=B/'task-feedback-real-20261001-v6';sys.path.insert(0,str(old))
    assert sha(old/'task_feedback_real_20261001.py')=='4b155d927c12f063e0838b5708085fe1bc55c4983197a3d8d2453696d73c55ad'
    import task_feedback_real_20261001 as rt;rt.setup()
    from dojo.config_dataclasses.run import RunConfig
    from dojo.tasks.mlebench.task import MLEBenchTask
    index=next(s['index'] for s in read(old/'plan.json')['schedule'] if s['task']==TASK)
    obj=MLEBenchTask(RunConfig.load_from_json(old/f'configs/{index}.json').task)
    assert obj._search_only_score and not obj.private_dir.exists()
    spec=obj._search_only_module.SPEC[TASK];rr=rows(B/spec.get('source',spec.get('view'))/'private/dsearch.csv')
    lookup={r['request_id']:int(r['requester_received_pizza']) for r in rr};assert len(lookup)==len(rr)
    ids=sorted(lookup);y=np.array([lookup[k] for k in ids]);out=[];private=[]
    for batch,h in ROOTS.items():
        root=B/batch;plan=read(root/'plan.json');assert sha(root/'plan.json')==h and (root/'all-closed.json').is_file()
        for s in plan['schedule']:
            if s['task']!=TASK:continue
            ep=root/f'episode-{s["index"]}';assert (ep/'closed.json').is_file()
            ps=[];seen=set();steps=[];metrics=[]
            for a in sorted(ep.glob('action-*'),key=lambda x:int(x.name.split('-')[-1])):
                if not (a/'result.json').is_file():continue
                r=read(a/'result.json')
                if not r['valid']:continue
                rr=rows(a/'submission.private.csv');pred={v['request_id']:float(v['requester_received_pizza']) for v in rr}
                assert len(pred)==len(rr)==len(ids) and set(pred)==set(ids)
                p=np.array([pred[k] for k in ids]);assert np.isfinite(p).all()
                score=float(roc_auc_score(y,p));assert abs(score-r['metric'])<1e-12
                assert abs(float(exact_auc(y,p))-score)<1e-12;metrics.append(score)
                fingerprint=hashlib.sha256(p.tobytes()).hexdigest()
                if fingerprint not in seen:ps.append(p);seen.add(fingerprint);steps.append(int(a.name.split('-')[-1]))
            rec=dict(batch=batch,index=s['index'],task=TASK,arm=s['arm'],seed=s['seed'],
                automatic=(batch.endswith('20261001-v6') or ('upper' in batch and s['arm'] in ('A','B')) or 'public-example' in batch),
                valid_actions=len(metrics),unique_predictions=len(ps),best_single=None,two_model_oracle=None,gain=None,
                native_at_oracle_weight=None,native_gain=None,native_matches_exact=None,pairs_checked=0)
            if ps:
                singles=[exact_auc(y,p) for p in ps];ii=max(range(len(ps)),key=lambda i:singles[i]);best=singles[ii];choice=(ii,ii,Fraction(0));native=float(best)
                for i,j in itertools.combinations(range(len(ps)),2):
                    v,w,real=pair_oracle(y,ps[i],ps[j]);rec['pairs_checked']+=1
                    if v>best:best,choice,native=v,(i,j,w),real
                base=max(metrics);i,j,w=choice
                rec.update(best_single=base,two_model_oracle=float(best),gain=float(best)-base,
                    native_at_oracle_weight=native,native_gain=native-base,native_matches_exact=abs(native-float(best))<1e-12)
                private.append(dict(batch=batch,index=s['index'],steps=[steps[i],steps[j]],weight=[w.numerator,w.denominator]))
            out.append(rec)
    with (OUT/'runs.csv').open('x',newline='') as f:w=csv.DictWriter(f,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
    groups={}
    for scope in ('all','automatic','manual','current_public_examples'):
        rr=[r for r in out if scope=='all' or (scope=='automatic' and r['automatic']) or (scope=='manual' and not r['automatic']) or (scope=='current_public_examples' and 'public-example' in r['batch'])]
        vv=[r for r in rr if r['best_single'] is not None];g=[r['gain'] for r in vv]
        groups[scope]=dict(assigned=len(rr),with_predictions=len(vv),multiple_unique=sum(r['unique_predictions']>1 for r in vv),
            median_gain=statistics.median(g) if g else None,sample_variance=statistics.variance(g) if len(g)>1 else None,
            at_least_005=sum(v>=.005 for v in g),max_gain=max(g,default=None),native_mismatches=sum(not r['native_matches_exact'] for r in vv))
    write(OUT/'bindings.private.json',HASHES);write(OUT/'weights.private.json',private)
    result=dict(status='EMPIRICAL_LABEL_USING_TWO_MODEL_ORACLE_ONLY',groups=groups,rows=out,tests=test,
        plan_sha256=sha(OUT/'plan.json'),runs_sha256=sha(OUT/'runs.csv'),elapsed_seconds=time.monotonic()-began,
        gpu=0,api=0,new_task_fits=0,scope='adaptive old development; pairwise mixture class only; failed trajectories retained')
    write(OUT/'summary.json',result);print(json.dumps({k:v for k,v in result.items() if k!='rows'},sort_keys=True))
if __name__=='__main__':
    if '--test' in sys.argv:print(json.dumps(tests()))
    else:main()
