"""Pre-outcome secondary: local improvement versus improving the fixed-pool best.

An outcome-aware envelope is an optimistic algebraic bound for this observed pool,
not a deployable selector, confidence limit, or a bound on other future programs.
"""
import argparse
import json
import os
from natural_opportunity_20261006 import R,TASKS,read,write,sha,check


def envelope(task,rows):
    assert task in TASKS
    sign=1 if task==TASKS[0] else -1
    output=[]
    for repeat in range(2):
        q=[r for r in rows if r['task']==task and r['repeat']==repeat]
        assert len(q)==4 and len({(r['case'],r['arm']) for r in q})==4
        complete=all(r['valid'] for r in q)
        out=dict(repeat=repeat,complete=complete,oracle_additional_gain=None,child_vs_best_parent=[])
        if complete:
            best=max(sign*r['dev_metric'] for r in q if r['arm']=='P')
            out['best_parent_metric']=sign*best
            out['oracle_additional_gain']=max(sign*r['dev_metric'] for r in q)-best
            out['child_vs_best_parent']=[dict(case=r['case'],gain=sign*r['dev_metric']-best) for r in q if r['arm']=='C']
        output.append(out)
    return dict(task=task,restarts=output,all_restarts_complete=all(r['complete'] for r in output))


def tests():
    rows=[dict(task=TASKS[0],repeat=j,case=k,arm=a,valid=True,
        dev_metric={(0,'P'):.5,(0,'C'):.6,(1,'P'):.8,(1,'C'):.79}[(k,a)])
        for j in range(2) for k in range(2) for a in ['P','C']]
    x=envelope(TASKS[0],rows)
    assert all(r['oracle_additional_gain']==0 for r in x['restarts'])
    rows[0]['valid']=False
    assert envelope(TASKS[0],rows)['restarts'][0]['oracle_additional_gain'] is None
    return dict(status='PASS',weak_branch_gain_is_not_search_gain=True,missing_not_zero=True)


def freeze():
    check();tests()
    assert not (R/'readout-v1').exists() and not any(R.glob('episode-*/native.json'))
    write(R/'incumbent-secondary-plan.json',dict(source_sha256=sha(__file__),
        primary_plan_sha256=sha(R/'plan.json'),pre_execution=True,source_note=__doc__,
        comparison='For each task and fixed-source-seed restart, every child versus max of BOTH newly rerun parents in the original frozen cohort. Four endpoints required; no imputation.',
        bound='max(P0,P1,C0,C1)-max(P0,P1), all higher-is-better; pointwise observed-pool algebra only.',
        effect_on_primary='None. Keep the original per-parent primary, thresholds and uncertainty unchanged.',
        interpretation='Positive own-parent change is insufficient for improving an existing better incumbent. A zero envelope stops investment in a selector over THIS pool, not generation/repair/other future pools.',
        additional_gpu_hours=0,additional_model_runs=0,automatic_expansion=False))
    print(json.dumps(dict(status='PRE_EXECUTION_SECONDARY_FROZEN',sha256=sha(R/'incumbent-secondary-plan.json'))))


def analyze():
    check();p=read(R/'incumbent-secondary-plan.json');assert p['source_sha256']==sha(__file__)
    assert p['primary_plan_sha256']==sha(R/'plan.json') and p['pre_execution']
    path=R/'readout-v1/runs.csv'
    import csv
    with path.open(newline='') as f:rows=list(csv.DictReader(f))
    for r in rows:
        for k in ['repeat','case']:r[k]=int(r[k])
        assert r['valid'] in ['True','False'];r['valid']=r['valid']=='True'
        r['dev_metric']=float(r['dev_metric']) if r['dev_metric'] else None
    result=dict(plan_sha256=sha(R/'incumbent-secondary-plan.json'),runs_sha256=sha(path),
        tests=tests(),tasks=[envelope(t,rows) for t in TASKS],limitation=__doc__,
        no_new_method_claim=True,no_population_confidence_claim=True,no_additional_execution=True)
    write(R/'readout-v1/incumbent-secondary.json',result);print(json.dumps(result))


if __name__=='__main__':
    os.umask(0o077);p=argparse.ArgumentParser();p.add_argument('mode',choices=['tests','freeze','analyze']);a=p.parse_args()
    if a.mode=='tests':print(json.dumps(tests()))
    else:globals()[a.mode]()
