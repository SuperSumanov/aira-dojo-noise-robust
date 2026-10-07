"""Read only this approved development batch; export aggregates, never predictions.

No scoring labels, official grading, source selection, retries or GPU calls.
All 36 slots retained even if Slurm killed the controller before its final write.
"""
import csv
import itertools
import json
import math
import os
from pathlib import Path
import statistics
import subprocess

from throughput_pilot import R, read, sha, schedule
from lifecycle_pilot import write


def distribution(values):
    return dict(n=len(values),median=statistics.median(values) if values else None,
        min=min(values) if values else None,max=max(values) if values else None,
        sample_std=statistics.stdev(values) if len(values)>1 else None)


def load_predictions(path):
    with path.open(newline='') as f:
        reader=csv.reader(f);header=next(reader);rows=list(reader)
    data={r[0]:[float(v) for v in r[1:]] for r in rows}
    if len(data)!=len(rows) or any(not math.isfinite(v) for row in data.values() for v in row):raise ValueError('prediction validity')
    return header,data


def difference(a,b):
    if a[0]!=b[0] or a[1].keys()!=b[1].keys():raise ValueError('output contract mismatch')
    values=[abs(x-y) for k in sorted(a[1]) for x,y in zip(a[1][k],b[1][k])]
    return dict(max_abs=max(values,default=0),different_values=sum(v!=0 for v in values),values=len(values))


def overlap(intervals):
    events=sorted([(t,delta) for start,end in intervals for t,delta in [(start,1),(end,-1)]])
    active=peak=0;shared=0.;last=None
    for t,delta in events:
        if last is not None and active>=2:shared+=t-last
        active+=delta;peak=max(peak,active);last=t
    return dict(max_simultaneous=peak,two_or_more_seconds=shared)


def main():
    plan=read(R/'plan.json');job=read(R/'launch.json')['job']
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    accounting=subprocess.check_output(['sacct','-j',job,'-n','-P','-o','JobIDRaw,State,ElapsedRaw,AllocTRES,ExitCode'],env=env,text=True,timeout=20)
    allocation=[x.split('|') for x in accounting.splitlines() if x.split('|')[0]==job]
    if len(allocation)!=1 or allocation[0][1] in ('RUNNING','PENDING','COMPLETING'):raise ValueError('allocation not terminal')
    a=allocation[0];tres=dict(x.split('=',1) for x in a[3].split(',') if '=' in x)
    if int(tres['gres/gpu'])!=1:raise ValueError('allocation scope')
    duration=int(a[2]);runs=[];outputs={};block_stats=[]
    for row in schedule():
        ep=R/f'episode-{row["index"]}';value=dict(**row,status='not_started',program_name=plan['programs'][row['program']]['name'],task=plan['programs'][row['program']]['task'])
        for filename,prefix in [('started.json','start_receipt'),('closed.json','supervisor'),('completed.json','completion')]:
            if (ep/filename).exists():value[prefix]=read(ep/filename);value['status']='incomplete'
        done=value.get('completion',{});closed=value.get('supervisor',{})
        if closed:value['status']='failed'
        if done.get('complete') and closed.get('returncode')==0:
            value['status']='complete';outputs[row['index']]=load_predictions(ep/'work/submission.csv')
        runs.append(value)
    for b in range(6):
        p=R/f'block-{b}.json'
        if not p.exists():continue
        record=read(p);rows=[r for r in runs if r['index']//6==b]
        intervals=[]
        for row in rows:
            ep=R/f'episode-{row["index"]}'
            if (ep/'candidate_started.json').exists() and (ep/'candidate_ended.json').exists():
                intervals.append((read(ep/'candidate_started.json')['time'],read(ep/'candidate_ended.json')['time']))
        block_stats.append(dict(block=b,arm=record['arm'],repeat=record['repeat'],makespan_seconds=record['end']-record['start'],
            completed=sum(r['status']=='complete' for r in rows),candidate_overlap=overlap(intervals),
            summed_candidate_exec_seconds=sum(r.get('completion',{}).get('exec_seconds',0) for r in rows),
            missing_exec_times=sum('exec_seconds' not in r.get('completion',{}) for r in rows)))
    equivalence=[]
    for program in range(6):
        rows=[r for r in runs if r['program']==program and r['index'] in outputs]
        comparisons=[]
        for x,y in itertools.combinations(rows,2):
            comparisons.append(dict(arms=[x['arm'],y['arm']],indices=[x['index'],y['index']],**difference(outputs[x['index']],outputs[y['index']])))
        equivalence.append(dict(program=program,available=len(rows),all_outputs_exactly_equal=all(c['max_abs']==0 for c in comparisons) if len(rows)==6 else None,comparisons=comparisons,
            gpu_training_receipts=[r.get('completion',{}).get('gpu_training') for r in rows]))
    complete=sum(r['status']=='complete' for r in runs)==36 and len(block_stats)==6
    ratios=[]
    if complete:
        for repeat in range(3):
            d={b['arm']:b['makespan_seconds'] for b in block_stats if b['repeat']==repeat}
            ratios.append(d['serial']/d['share2'])
    result=dict(job=job,allocation_state=a[1],allocation_exit=a[4],allocation_seconds=duration,whole_pool_gpu_hours=duration/3600,
        within_cap=duration<=5400,plan_sha256=sha(R/'plan.json'),source_commit=plan['source_commit'],planned=36,
        attempted=sum(r['status']!='not_started' for r in runs),completed=sum(r['status']=='complete' for r in runs),
        complete_fixed_workload=complete,serial_over_share2_makespan=distribution(ratios),paired_ratios=ratios,
        all_program_outputs_exactly_equal=all(e['all_outputs_exactly_equal'] for e in equivalence) if complete else None,
        block_stats=block_stats,output_equivalence=equivalence,runs=runs,
        boundary='Small development workloads; three fixed-seed restarts, three tasks, related GPU sources. No quality scoring, no semantic scheduler, no live E2E claim.')
    # Completion objects contain ONLY aggregate structure/versions/GPU-fit receipts, no predictions.
    return result


if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('--save',action='store_true');args=ap.parse_args()
    result=main()
    if args.save:
        output=R/'readout-v1';output.mkdir(mode=0o700,exist_ok=False)
        write(output/'summary.json',result)
        print(json.dumps(dict(job=result['job'],planned=result['planned'],attempted=result['attempted'],completed=result['completed'],whole_pool_gpu_hours=result['whole_pool_gpu_hours'],summary_sha256=sha(output/'summary.json'))))
    else:print(json.dumps(result,sort_keys=True,allow_nan=False))
