"""Posthoc all-assigned final-level contrasts, without imputing any initial.

All12 final retained scores were independently verified and observed. This is
distinct from the frozen optimization-gain estimand requiring identical actual
initial predictions. Includes the run whose initial execution failed, so does
not condition this descriptive endpoint on successful initialization.
"""
import csv
import hashlib
import json
from pathlib import Path
import statistics

R = Path(__file__).resolve().parents[1]/'results/diagnostic_information_20261004/closed'

def main():
    with (R/'runs.csv').open(newline='',encoding='utf-8') as f:
        runs=list(csv.DictReader(f))
    verify=json.loads((R/'verification.json').read_bytes())
    assert verify['status']=='PASS' and not verify['numerical_C_gate']
    assert len(runs)==12 and len({r['index'] for r in runs})==12
    scored={(str(x['index']),str(x['step'])):x['metric'] for x in verify['score_checks']}
    assert all(r['closed']=='True' and r['selected'] and float(r['selected'])==scored[r['index'],r['selected_step']] for r in runs)
    pairs=[]
    stats=[]
    for task in sorted({r['task'] for r in runs}):
        sign=1 if task=='random-acts-of-pizza' else -1
        for seed in sorted({r['seed'] for r in runs if r['task']==task}):
            group={r['arm']:r for r in runs if r['task']==task and r['seed']==seed}
            assert set(group)==set('ABC')
            assert len({(r['source_state'],r['run_seconds'],r['max_calls'],r['max_tokens'],r['plan_sha256']) for r in group.values()})==1
            scores={a:float(r['selected']) for a,r in group.items()}
            row=dict(task=task,seed=int(seed),final_scores=scores,
                own_initial_available={a:bool(r['initial']) for a,r in group.items()})
            for a,b in (('B','A'),('C','A'),('C','B')):
                row[a+'_minus_'+b]=sign*(scores[a]-scores[b])
            pairs.append(row)
        for contrast in ('B_minus_A','C_minus_A','C_minus_B'):
            values=[r[contrast] for r in pairs if r['task']==task]
            stats.append(dict(task=task,contrast=contrast,assigned_pairs=2,observed_pairs=len(values),
                values=values,median=statistics.median(values),sample_variance=statistics.variance(values)))
    assert next(r for r in runs if r['index']=='11')['initial']==''
    out=dict(status='POSTHOC_ALL_ASSIGNED_FINAL_LEVELS',assigned=12,observed_final=12,
        plan_sha256=verify['plan_sha256'],full_summary_sha256=verify['summary_sha256'],pairs=pairs,contrasts=stats,
        runs_csv_sha256=hashlib.sha256((R/'runs.csv').read_bytes()).hexdigest(),
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        boundary='Endpoint changed explicitly for a descriptive supplement only. Direct final-level differences, not within-run gain: index11 initial remains missing. All assigned runs retained, including failed initialization and format rejection. The frozen complete-ABC initial-matched analysis and gate stay unchanged. Two reused parents, only two generation seeds; no significance, fresh generalization, diagnostic-causal attribution, or automatic-method cost-parity claim.')
    raw=(json.dumps(out,indent=2,sort_keys=True,allow_nan=False)+'\n').encode()
    with (R/'posthoc-final-levels.json').open('xb') as f:
        f.write(raw)
    print(json.dumps(dict(status=out['status'],assigned=12,observed_final=12,contrasts=stats,
                         sha256=hashlib.sha256(raw).hexdigest())))

if __name__=='__main__':
    main()
