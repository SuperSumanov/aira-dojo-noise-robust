"""Independent scalar-loop verification of empirical convex certificates."""
import csv,hashlib,json,math
from pathlib import Path
R=Path('/research/d7/spc/yzyang4/convex-opportunity-20261003-v1');B=R.parent
CLASSES=['EAP','HPL','MWS']
def read(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def main():
    summary=read(R/'summary.json');plan=read(R/'plan.json');bindings=read(R/'bindings.private.json')
    assert sha(R/'plan.json')==summary['plan_sha256'] and sha(R/'runs.csv')==summary['runs_sha256']
    for name,h in bindings.items():assert sha(Path(name))==h
    truthpaths=[p for p in bindings if p.endswith('/private/dsearch.csv')];assert len(truthpaths)==1
    truth={r['id']:CLASSES.index(r['author']) for r in rows(Path(truthpaths[0]))};ids=sorted(truth)
    weights={(r['batch'],r['index']):r for r in read(R/'weights.private.json')};checked=0
    assigned=[]
    for name,h in plan['roots'].items():
        p=B/name/'plan.json';assert sha(p)==h
        assigned.extend((name,s['index']) for s in read(p)['schedule'] if s['task']=='spooky-author-identification')
    assert sorted(assigned)==sorted((r['batch'],r['index']) for r in summary['rows'])
    for r in summary['rows']:
        if not r['has_predictions']:continue
        w=weights[(r['batch'],r['index'])];alpha=w['weights'];columns=[]
        assert len(alpha)==len(w['steps'])==r['n_unique'] and min(alpha)>=0 and abs(math.fsum(alpha)-1)<1e-12
        for step in w['steps']:
            rr=rows(B/r['batch']/f'episode-{r["index"]}/action-{step}/submission.private.csv')
            lookup={x['id']:x for x in rr};assert len(lookup)==len(rr)==len(ids) and set(lookup)==set(ids)
            c=[]
            for ident in ids:
                values=[min(max(float(lookup[ident][k]),2.220446049250313e-16),1-2.220446049250313e-16) for k in CLASSES]
                c.append(values[truth[ident]]/sum(values))
            columns.append(c)
        probs=[math.fsum(a*c[i] for a,c in zip(alpha,columns)) for i in range(len(ids))]
        loss=-math.fsum(math.log(x) for x in probs)/len(ids)
        deriv=[-math.fsum(c[i]/probs[i] for i in range(len(ids)))/len(ids) for c in columns]
        tangent=loss+min(deriv)-math.fsum(a*g for a,g in zip(alpha,deriv))
        best=min(-math.fsum(math.log(x) for x in c)/len(ids) for c in columns)
        assert abs(loss-r['mixture_loss'])<1e-12 and abs(best-r['best_single_loss'])<1e-12
        assert abs(max(0,best-loss)-r['empirical_gain_lower'])<1e-12
        assert best-tangent<=r['empirical_gain_upper']+1e-11
        assert abs(max(0,loss-tangent)-r['numerical_dual_gap'])<1e-10
        checked+=1
    out=dict(status='PASS',checked_trajectories=checked,assigned=len(assigned),summary_sha256=sha(R/'summary.json'),
        independent='Python scalar math.fsum, tangent hyperplane on simplex; no producer solve import',
        limitation='Numerical optimization bound only; not formal interval arithmetic or statistical confidence.',source_sha256=sha(Path(__file__)))
    with (R/'verification.json').open('x') as f:json.dump(out,f,sort_keys=True,indent=2)
    print(json.dumps(out))
if __name__=='__main__':main()
