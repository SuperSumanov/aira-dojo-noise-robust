"""Posthoc historical reference context; not a new concurrent treatment arm.

Uses published aggregate files only. The fixed prior manual recipe is not a
best-of-history oracle. No pooling protocols or interpreting seed repeats as
independent states. Never changes the current frozen score or expansion gate.
"""
import csv
import hashlib
import json
from pathlib import Path
import statistics

BASE = Path(__file__).resolve().parents[1]/'results'
OLD = BASE/'natural_opportunity_20261003/qualification'
CURRENT = BASE/'diagnostic_information_20261004/closed'

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def table(p):
    with p.open(newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))

def main():
    old = table(OLD/'readout-runs.csv')
    current = table(CURRENT/'runs.csv')
    assert len(current)==12
    assert {r['plan_sha256'] for r in current} == {'63322ce2f5e38ac22c2a98b2c7bae5fa27334c4d5f3052297938418c26627679'}
    refs={}
    for task,state,recipe,direction in (
        ('random-acts-of-pizza','4','xgb_early_stopping',1),
        ('spooky-author-identification','0','cv_selected_member',-1)):
        relevant = [r for r in old if r['task']==task and r['state']==state and r['seed']=='42']
        assert len(relevant)==2 and all(r['valid']=='True' for r in relevant)
        ref={r['arm']:r for r in relevant}
        assert set(ref)=={'original','modified'}
        refs[task] = dict(recipe=recipe,direction=direction,score=float(ref['modified']['score']),
            original_score=float(ref['original']['score']),
            original_submission_sha256=ref['original']['submission_sha256'],
            modified_submission_sha256=ref['modified']['submission_sha256'],
            modified_code_sha256=ref['modified']['code_sha256'],
            old_plan_sha256=ref['modified']['plan_sha256'],old_index=int(ref['modified']['index']),
            old_execution_seconds=float(ref['modified']['seconds']))
    rows=[]
    for r in current:
        ref=refs[r['task']]
        own_initial=bool(r['initial'])
        if own_initial:
            assert r['initial_sha256']==ref['original_submission_sha256']
            assert float(r['initial'])==ref['original_score']
        rows.append(dict(index=int(r['index']),task=r['task'],arm=r['arm'],seed=int(r['seed']),
            own_initial_matches_historical_prediction=own_initial,
            selected=float(r['selected']) if r['selected'] else None,
            historical_reference=ref['score'],
            oriented_selected_minus_reference=(ref['direction']*(float(r['selected'])-ref['score']) if r['selected'] else None)))
    stats=[]
    for task in sorted(refs):
        for arm in 'ABC':
            rr=[r for r in rows if r['task']==task and r['arm']==arm]
            v=[r['oriented_selected_minus_reference'] for r in rr if r['oriented_selected_minus_reference'] is not None]
            stats.append(dict(task=task,arm=arm,n=len(rr),observed_selected=len(v),
                own_initial_matches=sum(r['own_initial_matches_historical_prediction'] for r in rr),
                values=v,median=statistics.median(v),sample_variance=statistics.variance(v),
                above=sum(x>1e-12 for x in v),below=sum(x < -1e-12 for x in v),ties=sum(abs(x)<=1e-12 for x in v)))
    files=(OLD/'readout-runs.csv',OLD/'plan-public.json',CURRENT/'runs.csv')
    out=dict(status='POSTHOC_HISTORICAL_CONTEXT_ONLY',assigned=12,references=refs,rows=rows,contrasts=stats,
        files={str(p.relative_to(BASE)):sha(p) for p in files},script_sha256=sha(Path(__file__)),
        boundary='Historical manually designed references selected in the earlier qualification, not concurrent randomized controls, not strongest possible methods or best-of-history selection. Matching initial prediction bytes and published scores does not alone prove full environment/cost equality. Old execution seconds exclude manual discovery and serving costs, so no cost-efficiency claim. Index11 has no own initial: final level is listed but not a matched gain. No pooling across protocols, new independent states, GPU execution or confirmatory inference.')
    raw=(json.dumps(out,indent=2,sort_keys=True,allow_nan=False)+'\n').encode()
    with (CURRENT/'historical-reference-context.json').open('xb') as f:
        f.write(raw)
    print(json.dumps(dict(status=out['status'],contrasts=stats,sha256=hashlib.sha256(raw).hexdigest())))

if __name__=='__main__':
    main()
