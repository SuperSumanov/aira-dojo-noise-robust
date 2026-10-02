"""Separate exact-arithmetic diagnostic from an executable float64 coefficient."""
import csv,hashlib,json
from collections import Counter
from fractions import Fraction
from pathlib import Path
import numpy as np
from sklearn.metrics import roc_auc_score
R=Path('/research/d7/spc/yzyang4/pairmix-opportunity-20261003-v1');B=R.parent
def read(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p):
    with p.open(newline='',encoding='utf-8-sig') as f:return list(csv.DictReader(f))
def main():
    s=read(R/'summary.json');bindings=read(R/'bindings.private.json')
    for name,h in bindings.items():assert sha(Path(name))==h
    truthpaths=[p for p in bindings if p.endswith('/private/dsearch.csv')];assert len(truthpaths)==1
    truth={r['request_id']:int(r['requester_received_pizza']) for r in rows(Path(truthpaths[0]))};ids=sorted(truth)
    y=np.array([truth[i] for i in ids]);pos=np.flatnonzero(y==1);neg=np.flatnonzero(y==0)
    weights={(r['batch'],r['index']):r for r in read(R/'weights.private.json')};out=[]
    for r in s['rows']:
        if not r['unique_predictions']:continue
        w=weights[(r['batch'],r['index'])];t=Fraction(*w['weight']);ps=[]
        for step in w['steps']:
            rr=rows(B/r['batch']/f'episode-{r["index"]}/action-{step}/submission.private.csv')
            p={x['request_id']:float(x['requester_received_pizza']) for x in rr};assert len(p)==len(rr)==len(ids) and set(p)==set(ids)
            ps.append([p[i] for i in ids])
        exact=[(1-t)*Fraction(u)+t*Fraction(v) for u,v in zip(*ps)]
        native=(1-float(t))*np.array(ps[0])+float(t)*np.array(ps[1]);matrix=Counter();num=0
        for i in pos:
            for j in neg:
                a=(exact[i]>exact[j])-(exact[i]<exact[j]);b=int(native[i]>native[j])-int(native[i]<native[j])
                matrix[f'{a}:{b}']+=1;num+=2*(a>0)+(a==0)
        exact_score=num/(2*len(pos)*len(neg));native_score=float(roc_auc_score(y,native))
        assert abs(exact_score-r['two_model_oracle'])<1e-12 and abs(native_score-r['native_at_oracle_weight'])<1e-12
        out.append(dict(batch=r['batch'],index=r['index'],exact_auc=exact_score,native_auc=native_score,
            mismatch=abs(exact_score-native_score)>1e-12,
            exact_to_native_pair_relations=dict(matrix),changed_pair_relations=sum(v for k,v in matrix.items() if k.split(':')[0]!=k.split(':')[1])))
    # Scalar recomputation independently checks the fold-level aggregation, not
    # the absent statistical independence of these adaptively generated models.
    cv=B/'pairmix-sensitivity-20261003-v1';cs=read(cv/'summary.json');ff=rows(cv/'folds.csv')
    for name,h in cs['files'].items():assert sha(cv/name)==h
    for r in cs['rows']:
        sub=[f for f in ff if f['batch']==r['batch'] and int(f['index'])==r['index']]
        assert len(sub)==r['evaluated_folds']
        if sub:
            gain=sum(int(f['pair_count'])*(float(f['mixture_auc'])-float(f['baseline_auc'])) for f in sub)/sum(int(f['pair_count']) for f in sub)
            assert abs(gain-r['cv_gain'])<1e-12
    result=dict(status='NUMERICAL_RECONCILIATION_PASS_NOT_ALL_FLOAT_OUTPUTS_EQUAL',checked=len(out),mismatches=sum(r['mismatch'] for r in out),
        mismatched_rows=[r for r in out if r['mismatch']],summary_sha256=sha(R/'summary.json'),cv_summary_sha256=sha(cv/'summary.json'),
        cv_aggregation='PASS',source_sha256=sha(Path(__file__)),
        limitation='Rational oracle refers to real-valued convex interpolation of stored dyadic inputs. Native output rounding may change near-tie comparisons; native values separately reported. Neither is a deployable validated policy.')
    with (R/'numerics.json').open('x') as f:json.dump(result,f,sort_keys=True,indent=2)
    print(json.dumps(result,sort_keys=True))
if __name__=='__main__':main()
