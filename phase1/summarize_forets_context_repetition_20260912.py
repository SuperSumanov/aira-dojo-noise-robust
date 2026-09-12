"""Combine exactly the two matching contextual seeds AFTER independent closure.

No selection, grading, training or paid calls. Missing scores stay missing.
Seed13 and older eight-billion-parameter critic runs cannot enter this table.
"""
from collections import defaultdict
import csv
from decimal import Decimal
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import subprocess

SPECS=((14,'13124','forets-repeat-20260912-x3pkniqp','f70eb4859c48c61bba37b298fbf8e32e367644ae'),
       (15,'13128','forets-repeat-20260912-3no2iopd','54e353963a6899965896b2e8ea492207829b3cbd'))
BASE=Path('/research/d7/spc/yzyang4')
TASKS={'leaf-classification','spaceship-titanic'}
ARMS={'uniform_random','critic_topk_random'}


def combine(blocks):
    if len(blocks)!=2:raise ValueError('exactly two matching contextual seeds required')
    pairs=[];bytask=defaultdict(list);rows=[];billing=[]
    for (seed,job,_,tree),(verified,diagnostic) in zip(SPECS,blocks):
        if (verified['seed']!=seed or verified['job']!=job or verified['source_tree']!=tree
            or verified['verification']!='passed' or len(verified['rows'])!=4):
            raise ValueError('wrong independently verified block')
        if {(r['task'],r['arm']) for r in verified['rows']}!={(t,a) for t in TASKS for a in ARMS}:
            raise ValueError('planned task/arm matrix differs')
        if len(verified['pairs'])!=2 or {p['task'] for p in verified['pairs']}!=TASKS:
            raise ValueError('missing task pair')
        for p in verified['pairs']:
            if p['seed']!=seed:raise ValueError('pair seed mismatch')
            delta=p['conditional_benefit_delta']
            if p['availability']=='both_valid':
                if delta is None or not math.isfinite(float(delta)):raise ValueError('missing valid difference')
                bytask[p['task']].append(Decimal(delta))
            elif delta is not None:raise ValueError('missing outcome imputed')
            pairs.append(p)
        costs={r['run_id']:r for r in diagnostic['runs']}
        for r in verified['rows']:
            if r['seed']!=seed or r['run_id'] not in costs:raise ValueError('cost row mismatch')
            c=costs[r['run_id']]
            if (c['seed'],c['task'],c['arm'])!=(seed,r['task'],r['arm']):raise ValueError('cost binding differs')
            rows.append(r|dict(source_tree=tree,job=job)|{k:c[k] for k in ('api_calls','settled_api_cost_usd','unresolved_api_calls',
                'task_calls','execution_timeout_seconds','step_limit','worker_wall_cap_seconds')})
        billing.append(dict(seed=seed,job=job,allocation_gpu_hours=verified['allocation_gpu_hours'],
            new_api_calls_including_route=diagnostic['billing']['new_api_calls'],
            new_settled_usd=diagnostic['billing']['new_settled_usd']))
    tasks=[]
    for task in sorted(TASKS):
        valid=bytask[task]
        tasks.append(dict(task=task,total_seed_pairs=2,comparable_seed_pairs=len(valid),
            median_conditional_benefit=str(statistics.median(valid)) if valid else None,
            sample_std_conditional_benefit=statistics.stdev([float(v) for v in valid]) if len(valid)>1 else None,
            positive_comparable_pairs=sum(v>0 for v in valid),negative_comparable_pairs=sum(v<0 for v in valid),
            valid_score_ties=sum(v==0 for v in valid)))
    availability=[]
    for arm in sorted(ARMS):
        selected=[r for r in rows if r['arm']==arm]
        availability.append(dict(arm=arm,total_runs=len(selected),valid_final_runs=sum(r['comparable_final'] for r in selected),
            settled_api_usd=str(sum(Decimal(str(r['settled_api_cost_usd'])) for r in selected)),
            api_calls=sum(r['api_calls'] for r in selected)))
    return dict(role='two_seed_contextual_e2e_development_comparison',rows=rows,pairs=pairs,
        task_summaries=tasks,availability=availability,billing=billing,
        limitations=['Two exploratory seeds on two tasks; no formal significance or broad generalization established.',
            'Conditional score summaries exclude missing scores; complete availability counts must accompany them.',
            'Different task metrics are not averaged together.',
            'Equal search/resource caps do not imply identical realized token, dollar or wall-time expenditure.',
            'Independent LLM generation and downstream trajectories prevent attributing every final difference to one selection.'])


def main():
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    blocks=[];hashes={}
    from verify_forets_review_final_20260912 import SECRET
    for seed,job,name,tree in SPECS:
        status=subprocess.check_output(['sacct','-X','-j',job,'-nP','--format=JobIDRaw,State'],text=True,env=env,timeout=25).strip()
        if status!=job+'|COMPLETED':raise ValueError('both blocks must be independently complete')
        values=[]
        for file in ('independent-context-verification.json','diagnostics.json'):
            path=BASE/name/file;raw=path.read_bytes()
            if SECRET.search(raw.decode()):raise ValueError('credential-shaped result')
            hashes[name+'/'+file]=hashlib.sha256(raw).hexdigest();values.append(json.loads(raw))
        blocks.append(values)
    report=combine(blocks)|dict(evidence_sha256=hashes,script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    output=BASE/SPECS[1][2]/'two-seed-contextual-summary.json'
    with output.open('x') as f:json.dump(report,f,indent=2,allow_nan=False)
    with output.with_suffix('.csv').open('x',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(report['rows'][0]))
        writer.writeheader();writer.writerows(report['rows'])
    print(json.dumps({k:v for k,v in report.items() if k not in ('rows','evidence_sha256')}))


if __name__=='__main__':main()
