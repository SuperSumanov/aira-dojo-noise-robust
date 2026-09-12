"""Combine closed development pools, never select a favorable batch or impute a score."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import statistics

TASKS=('leaf-classification','spaceship-titanic')
MODELS=('qwen/qwen3-coder-flash','qwen/qwen3-coder-plus')
BATCHES=((16,17),(18,19),(20,21))


def subset(rows, slots):
    if len(slots)!=len(set(slots)) or any(type(i)!=int or not 0<=i<len(rows) for i in slots):
        raise ValueError('invalid selection')
    valid=[float(rows[i]['score']) for i in slots if rows[i]['valid']=='True']
    return dict(valid=len(valid),total=len(slots),valid_probability=len(valid)/len(slots),
                conditional_mean_score=statistics.mean(valid) if valid else None)


def combine(base):
    inputs=[]; allrows=[];selection=[];cost=0;rankcost=0;gpuh=0
    for seeds in BATCHES:
        directory=base/f'forets_generation_capacity_s{seeds[0]}_s{seeds[1]}_20260912'
        sp=directory/'generation-capacity-summary.json';cp=directory/'generation-capacity-runs.csv'
        summary=json.loads(sp.read_text()); rows=list(csv.DictReader(cp.open(newline='')))
        expected={(t,str(s),m) for t in TASKS for s in seeds for m in MODELS}
        if len(rows)!=8 or {(r['task'],r['replicate'],r['model']) for r in rows}!=expected:
            raise ValueError('missing/duplicate matrix')
        if not summary['same_native_gpu'] or not summary['all_program_slots_included'] or summary['protected_cohort_read']:
            raise ValueError('incomplete verification')
        if len({r['source_tree'] for r in rows})!=1 or any(r['node']!='gpu28' for r in rows):
            raise ValueError('environment mismatch')
        for r in rows:
            if r['valid'] not in ('True','False') or (r['status']=='valid')!=(r['valid']=='True'):
                raise ValueError('validity mismatch')
            if r['status'] not in ('valid','program_error','program_timeout','missing_submission','invalid_submission'):
                raise ValueError('infrastructure is not quality')
            if (r['valid']=='False')!=(r['score']==''):raise ValueError('missingness imputed')
        if summary['independent_numerical_regrades']!=sum(r['valid']=='True' for r in rows):
            raise ValueError('numeric receipt incomplete')
        cost+=sum(float(r['api_cost_usd']) for r in rows)
        rankcost+=summary.get('ranking_api_cost_usd',0);gpuh+=summary['allocation_gpu_hours']
        inputs.append(dict(seeds=seeds,job=summary['job'],summary_sha256=hashlib.sha256(sp.read_bytes()).hexdigest(),
                           csv_sha256=hashlib.sha256(cp.read_bytes()).hexdigest()))
        allrows+=rows
        if seeds==(16,17):
            if 'blind_selection' in summary:raise ValueError('first batch was not blind ranked')
            continue
        if {s['task'] for s in summary['blind_selection']}!=set(TASKS):raise ValueError('both tasks required')
        for record in summary['blind_selection']:
            task=record['task'];rs=sorted([r for r in rows if r['task']==task],key=lambda r:int(r['index']))
            computed={}
            for key in ('uniform4','blind_borda_top2','prior_batch_metadata_flash'):
                slots=record[key]['slots']
                if len(slots)!=(4 if key=='uniform4' else 2):raise ValueError('selection width')
                result=subset(rs,slots)
                for field,value in result.items():
                    if value is None:
                        if record[key][field] is not None:raise ValueError('imputed mean')
                    elif abs(value-record[key][field])>1e-12:raise ValueError('aggregate mismatch')
                computed[key]=result
            selection.append(dict(task=task,batch=list(seeds),**computed,
                validity_gain=computed['blind_borda_top2']['valid_probability']-computed['uniform4']['valid_probability'],
                order_top2_invariant=record['order_top2_invariant']))
    if len({r['source_tree'] for r in allrows})!=1:raise ValueError('source varied across batches')
    taskgroups=[]
    for t in TASKS:
        rs=[r for r in selection if r['task']==t]
        if len(rs)!=2:raise ValueError('both blind batches required')
        taskgroups.append(dict(task=t,pools=2,validity_gains=[r['validity_gain'] for r in rs],
            median_validity_gain=statistics.median(r['validity_gain'] for r in rs),
            sample_std_validity_gain=statistics.stdev(r['validity_gain'] for r in rs),
            selected_valid=sum(r['blind_borda_top2']['valid'] for r in rs),selected_total=4,
            uniform_valid=sum(r['uniform4']['valid'] for r in rs),uniform_total=8,
            metadata_flash_valid=sum(r['prior_batch_metadata_flash']['valid'] for r in rs),metadata_flash_total=4))
    models=[dict(model=m,valid=sum(r['valid']=='True' for r in allrows if r['model']==m),total=12) for m in MODELS]
    return dict(inputs=inputs,programs=24,blind_pools=4,generation_models=models,selection=selection,taskgroups=taskgroups,
        generation_api_usd=cost,ranking_api_usd=rankcost,total_api_usd=cost+rankcost,allocation_gpu_hours=gpuh,
        repeated_code_hashes=len(allrows)-len({r['code_sha256'] for r in allrows}),
        limitation='Four finite mixed-generator development pools on two tasks, not four independent tasks or e2e searches. No significance/generalization/equal-budget search claim. All three generator batches included.')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    result=combine(args.base)
    with args.output.open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
    print(json.dumps(result,allow_nan=False))
