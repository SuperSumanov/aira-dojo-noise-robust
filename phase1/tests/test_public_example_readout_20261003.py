"""CPU-only adversarial fixtures for the already frozen readout; no task values."""
import copy,math,random,runpy
from pathlib import Path
W=Path(__file__).resolve().parents[1]/'scripts'
compare=runpy.run_path(str(W/'public_example_readout_20261003.py'))['compare']
metric=runpy.run_path(str(W/'public_example_verify_20261003.py'))['metric']
rows=[dict(task=t,seed=s,arm=a,initial=.5,gain=g,diagnostic_prediction_sha256=t,
           public_labels_sha256=t,closed=True,improved_candidates=1)
      for t,seeds in [('pizza',(1,2)),('spooky',(3,4))] for s in seeds
      for a,g in [('uniform',.01),('contrast',.03)]]
p,s,g=compare(rows);assert g and len(p)==4 and all(math.isclose(t['median_delta'],.02) for t in s)
tests=1
for field,value in [('initial',None),('initial',.7),('diagnostic_prediction_sha256',None),
                    ('diagnostic_prediction_sha256','changed'),('public_labels_sha256','changed'),('closed',False)]:
    rr=copy.deepcopy(rows);rr[0][field]=value
    assert not compare(rr)[2];tests+=1
for rr in (copy.deepcopy(rows),copy.deepcopy(rows),copy.deepcopy(rows)):
    if tests==7:
        for r in rr:r['gain']=0
    elif tests==8:
        rr[1]['gain']=0
    else:
        for r in rr:r['improved_candidates']=0
    assert not compare(rr)[2];tests+=1
for k in range(100):
    rng=random.Random(k);yy=[1,0]+[rng.randrange(2) for _ in range(8)];pp=[rng.choice([0,.2,.5,.8,1]) for _ in yy]
    y={str(i):{'requester_received_pizza':str(v)} for i,v in enumerate(yy)}
    p={str(i):{'requester_received_pizza':str(v)} for i,v in enumerate(pp)}
    ordered=sorted(zip(pp,yy));rank_sum=0.;i=0
    while i<len(ordered):
        j=i+1
        while j<len(ordered) and ordered[j][0]==ordered[i][0]:j+=1
        rank_sum+=sum(y for _,y in ordered[i:j])*(i+1+j)/2;i=j
    n=sum(yy);expected=(rank_sum-n*(n+1)/2)/(n*(len(yy)-n))
    assert math.isclose(metric(y,p,'random-acts-of-pizza'),expected,abs_tol=1e-12)
assert math.isclose(metric({'x':{'author':'EAP'}},{'x':dict(EAP=.5,HPL=.25,MWS=.25)},'spooky-author-identification'),math.log(2))
print(f'PASS {tests} comparison fixtures, 100 independent tied-AUC fixtures, 1 log-loss fixture; frozen producer unchanged')
