"""All-eight closure then one independent external grade of each CV incumbent."""
import argparse
import csv
import json
import math
import os
from pathlib import Path
import statistics
import subprocess
from run_classic_control_20260914 import BASE,checked,read,write,sha,source_check,setup,now


def select_incumbent(work,row,result):
    if result['status']!='completed':return None
    finish=work/'classic-finished.json'
    if sha(finish.read_bytes())!=result['finished_sha256']:raise ValueError('finish drift')
    f=read(finish);cfg=read(work/'classic-config.json')
    if sha((work/'classic-config.json').read_bytes())!=result['config_sha256']:raise ValueError('config drift')
    if (f['task'],f['seed'],f['deadline_ns'])!=(row['task'],row['seed'],result['deadline_ns']):raise ValueError('runtime identity')
    if cfg['started_ns']+1200*10**9!=f['deadline_ns']:raise ValueError('total budget')
    attempts=f['rows']
    if len(attempts)!=f['attempts'] or [a['index'] for a in attempts]!=list(range(len(attempts))):raise ValueError('attempt completeness')
    best=None;last=None;previous_time=cfg['started_ns']
    for a in attempts:
        i=a['index'];logged=read(work/'classic-trials'/f'{i:03d}'/'attempt.json')
        if logged!=a:raise ValueError('attempt binding')
        if not a['published']:continue
        p=read(work/'classic-incumbents'/f'trial-{i:03d}.json')
        if (p['task'],p['seed'],p['spec_sha256'])!=(row['task'],row['seed'],a['spec_sha256']):raise ValueError('publication identity')
        v=p['validation']
        if not math.isfinite(v) or not (best is None or (v<best if row['task']=='leaf-classification' else v>best)):
            raise ValueError('selection is not strictly validation-based')
        if p['validation']!=a['validation'] or not p['eligible'] or not previous_time<=p['durable_ns']<f['deadline_ns']:
            raise ValueError('late or unordered publication')
        if p['deadline_ns']!=f['deadline_ns'] or p['file']!=f'trial-{i:03d}.csv':raise ValueError('publication path')
        path=work/'classic-incumbents'/p['file']
        if path.is_symlink() or sha(path.read_bytes())!=p['sha256']:raise ValueError('submission hash')
        best=v;previous_time=p['durable_ns'];last=dict(path=path,index=i,sha256=p['sha256'],validation=v)
    if best!=f['best_validation']:raise ValueError('last incumbent differs')
    return last


def run(root):
    p=checked(root);source_check();launch=read(root/'launch.json');finish=read(root/'execution-finished.json')
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    acct=subprocess.check_output(['sacct','-X','-j',launch['job'],'-nP','-o','JobIDRaw,State%32,ElapsedRaw,AllocCPUS,AllocTRES,NodeList'],env=env,text=True,timeout=25)
    lines=[s for s in acct.splitlines() if s.startswith(launch['job']+'|')]
    if len(lines)!=1 or lines[0].split('|')[1] not in ('COMPLETED','FAILED','TIMEOUT','CANCELLED'):raise ValueError('allocation not terminal')
    if finish['job']!=launch['job'] or launch['prepared_sha256']!=sha((root/'prepared.json').read_bytes()):raise ValueError('closure binding')
    setup(root,p)
    from dojo.tasks.mlebench.evaluate import evaluate_submission
    from mlebench.grade import validate_submission
    from mlebench.registry import registry
    registry=registry.set_data_dir(BASE/'mle-bench-data')
    rows=[];proof={}
    for slot in p['rows']:
        i=slot['index'];rpath=root/f'result-{i}.json'
        row=dict(slot,score=None,valid=None,status='not_executed',wall_seconds=None,selected_index=None,submission_sha256=None,
            source_commit=p['commit'],source_tree=p['source_tree'],budget_seconds=1200,api_cost_usd=0,job=launch['job'])
        if rpath.exists():
            r=read(rpath)
            if any(r[k]!=slot[k] for k in slot):raise ValueError('result identity')
            row.update(status=r['status'],wall_seconds=r['wall_seconds']);proof[rpath.name]=sha(rpath.read_bytes())
            chosen=select_incumbent(root/f'work-{i}',slot,r)
            if r['status']=='completed':row['valid']=False
            if chosen is not None:
                row.update(selected_index=chosen['index'],submission_sha256=chosen['sha256'])
                comp=registry.get_competition(slot['task']);valid,_=validate_submission(chosen['path'],comp)
                if valid:
                    score,_=evaluate_submission(chosen['path'],BASE/'mle-bench-data',slot['task'],root/f'grade-{i}')
                    if score is not None and math.isfinite(float(score)):row.update(score=float(score),valid=True)
                if sha(chosen['path'].read_bytes())!=chosen['sha256']:raise ValueError('grade mutated submission')
        rows.append(row)
    groups=[]
    for task in ('leaf-classification','spaceship-titanic'):
        rs=[r for r in rows if r['task']==task];scores=[r['score'] for r in rs if r['valid'] is True]
        groups.append(dict(task=task,planned=4,valid=len(scores),unknown=sum(r['valid'] is None for r in rs),
            median=statistics.median(scores) if scores else None,sd=statistics.stdev(scores) if len(scores)>1 else None))
    result=dict(role='fixed_space_traditional_reference_not_single_knob_causal_ablation',utc=now(),rows=rows,groups=groups,
        allocation=lines,allocation_gpu_hours=int(lines[0].split('|')[2])/3600,proof=proof,prepared_sha256=sha((root/'prepared.json').read_bytes()))
    h=write(root/'summary.json',result)
    with (root/'runs.csv').open('x',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    write(root/'readout-finished.json',dict(utc=now(),summary_sha256=h,csv_sha256=sha((root/'runs.csv').read_bytes())))
    print(json.dumps(dict(summary_sha256=h,groups=groups,rows=rows,allocation_gpu_hours=result['allocation_gpu_hours'])))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);run(p.parse_args().root.resolve(strict=True))
