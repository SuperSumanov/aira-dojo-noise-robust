"""Separately approved two-program entry diagnostic, <=1x3090x15min.

Reuses immutable job16846 sources/input/worker. Only invocation argv changes;
per-cell diagnostic receipts add observability, not training settings. No retry,
quality scoring, API, source substitution, full sharing trial, or model updates.
"""
import argparse
import csv
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time

from lifecycle_pilot import sha,read,write,load
from entry_contract import SCRIPT_ENTRY

B=Path('/research/d7/spc/yzyang4')
D=B/'scheduling-throughput-20261007-v1'
R=B/'scheduling-entry-20261008-v2'
PY=B/'venvs/aira/bin/python'
NAME='entry_recheck.py'
DONOR_PLAN='accaceffe7e847b71a66c6cdf910d1e3506ffbbefc5dec5e79231380b2618a9b'
DONOR_PILOT='b30eed3feffccedb676f2c6aa6035295c07a780d3377c2068a5db8f3ee6c75ea'


def schedule():
    return [dict(index=i,program=p,repeat=0,arm='script_entry',seed=130701,original_index=p)
            for i,p in enumerate((0,4))]


def pilot():
    if sha(R/'throughput_pilot.py')!=DONOR_PILOT:raise ValueError('immutable donor worker drift')
    p=load('entry_pilot',R/'throughput_pilot.py');p.R=R;p.schedule=schedule
    p.GPU_INSTRUMENT=SCRIPT_ENTRY+p.GPU_INSTRUMENT
    return p


def check():
    p=read(R/'plan.json')
    if p['schedule']!=schedule() or p['gpu_hours_cap']!=.25:raise ValueError('plan drift')
    for name,h in p['files'].items():
        if sha(R/name)!=h:raise ValueError('source drift')
    for item in p['public_inputs']:
        if sha(item['path'])!=item['sha256']:raise ValueError('input drift')
    return p


def cell_receipt(result, stage, start, end):
    """Preserve the frozen executor's required fields; optional phase is unknown.

    Older pinned ExecutionResult has no timeout_phase. Absence is not a claim
    about where execution stopped and must not turn successful execution into a
    recorder failure. Required status fields still fail loudly if incompatible.
    """
    return dict(stage=stage, start=start, end=end, exit_code=result.exit_code,
                timed_out=result.timed_out, exec_seconds=result.exec_time,
                timeout_phase=getattr(result, 'timeout_phase', None),
                timeout_phase_available=hasattr(result, 'timeout_phase'))


def prepare(commit):
    import re
    if not re.fullmatch('[a-f0-9]{40}',commit):raise ValueError('exact commit required')
    if sha(D/'plan.json')!=DONOR_PLAN or not (D/'closed.json').exists():raise ValueError('donor not closed/pinned')
    old=read(D/'plan.json');R.mkdir(mode=0o700,exist_ok=False)
    for name,h in old['files'].items():
        if name in ('run.sbatch','bin/singularity'):continue
        if sha(D/name)!=h:raise ValueError('donor file drift')
        dest=R/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(D/name,dest)
    for name in (NAME,'entry_contract.py'):shutil.copyfile(Path(__file__).with_name(name),R/name)
    (R/'bin').mkdir(exist_ok=True)
    (R/'bin/singularity').write_text(f'#!{PY}\nimport sys\nsys.path.insert(0,{str(R)!r})\nfrom entry_recheck import pilot\npilot().task_runtime()\n')
    os.chmod(R/'bin/singularity',0o700)
    for row in schedule():(R/f'episode-{row["index"]}/work').mkdir(parents=True)
    batch=f'''#!/bin/bash
#SBATCH --job-name=r14-entry-v2
#SBATCH --partition=gpu_24h
#SBATCH --account=gpu
#SBATCH --qos=gpu
#SBATCH --nodelist=gpu27
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=6
#SBATCH --time=00:15:00
#SBATCH --no-requeue
set -euo pipefail
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1
timeout --signal=TERM --kill-after=15s 850s srun --exclusive --ntasks=1 --cpus-per-task=6 --gres=gpu:1 --cpu-bind=cores {PY} -B {R}/{NAME} controller
'''
    (R/'run.sbatch').write_text(batch)
    inputs=old['public_inputs']+[dict(path=str(D/'data-dec'/p.name),sha256=sha(p)) for p in (D/'data-dec').glob('*.csv')]
    plan=dict(source_commit=commit,donor_source_commit=old['source_commit'],donor_plan_sha256=DONOR_PLAN,
        schedule=schedule(),programs=old['programs'],gpu_hours_cap=.25,allocation_seconds=900,gpus=1,total_cpu=6,
        planned_executions=2,candidate_timeout_seconds=120,worker_hard_seconds=180,public_inputs=inputs,
        only_behavior_change='sys.argv=[candidate.py], ordinary defaults, no debug flag',
        previous_closed_batch='scheduling-entry-20261007-v1',
        recorder_fix='optional timeout_phase missing in frozen executor remains null; required fields unchanged',
        no_api=True,no_base_training=True,no_quality_scoring=True,no_comparison_claim=True,
        files={str(p.relative_to(R)):sha(p) for p in R.rglob('*') if p.is_file()})
    write(R/'plan.json',plan)
    m=pilot().runtime();image=m.TASK_IMAGE
    # Exercise the actual frozen return class, not only a current-tree/mock type.
    from dojo.core.interpreters.base import ExecutionResult
    result_contract=cell_receipt(ExecutionResult(term_out=[],exec_time=0.0,exit_code=0),0,0,0)
    if result_contract['exit_code']!=0 or result_contract['timed_out']:raise ValueError('frozen return contract')
    if sha(image)!='801f646bed3cae6e74e10d793e71b0086658d4303d54552333c58125ddf9beda':raise ValueError('image drift')
    subprocess.run(['bash','-n',str(R/'run.sbatch')],check=True)
    write(R/'preflight.json',dict(plan_sha256=sha(R/'plan.json'),image_sha256='801f646bed3cae6e74e10d793e71b0086658d4303d54552333c58125ddf9beda',donor_preflight_sha256=sha(D/'preflight.json'),image_content_pin_verified=True,
        same_candidate_sources=True,same_inputs=True,same_timeouts=True,no_candidate_executed_yet=True,
        actual_frozen_result_contract=result_contract))
    print(json.dumps(dict(status='PREPARED',root=str(R),plan_sha256=sha(R/'plan.json'))))


def worker(index):
    p=pilot();p.runtime();ep=R/f'episode-{index}'
    import dojo.utils.config as config
    original=config.build
    class DiagnosticInterpreter:
        def __init__(self,obj):self.obj=obj;self.calls=0
        def __getattr__(self,name):return getattr(self.obj,name)
        def run(self,*args,**kwargs):
            stage=self.calls;self.calls+=1;start=time.time()
            try:
                result=self.obj.run(*args,**kwargs)
                (ep/f'cell-{stage}.private.txt').write_text('\n'.join(map(str,result.term_out)))
                write(ep/f'cell-{stage}.json',cell_receipt(result,stage,start,time.time()))
                return result
            except Exception as exc:
                write(ep/f'cell-{stage}-exception.json',dict(stage=stage,error_type=type(exc).__name__,start=start,end=time.time()))
                raise
    config.build=lambda *args,**kwargs:DiagnosticInterpreter(original(*args,**kwargs))
    return p.worker(index)


def controller():
    plan=check();p=pilot();m=p.runtime();start=time.time();outcomes=[];error=None
    for _ in range(40):
        if (R/'launch.json').exists():break
        time.sleep(.25)
    if read(R/'launch.json')['job']!=os.environ['SLURM_JOB_ID'] or socket.gethostname().split('.')[0]!='gpu27':raise ValueError('allocation identity')
    gpu=m.infra().native_uuids(1)[0]
    write(R/'allocation.json',dict(job=os.environ['SLURM_JOB_ID'],gpu_uuid=gpu,start=start,affinity=sorted(os.sched_getaffinity(0))))
    try:
        for row in schedule():
            if time.time()-start+190>800:raise TimeoutError('allocation budget')
            if p.gpu_sample(gpu)['apps']:raise ValueError('unexpected/residual GPU client')
            ep=R/f'episode-{row["index"]}';begin=time.time()
            with (ep/'worker.private.log').open('xb') as f:
                process=subprocess.Popen([str(PY),'-B',str(R/NAME),'worker','--index',str(row['index'])],stdout=f,stderr=f,start_new_session=True)
                try:rc=process.wait(timeout=180)
                except subprocess.TimeoutExpired:p.terminate_owned(process,ep);rc=124
            result=dict(**row,returncode=rc,start=begin,end=time.time())
            write(ep/'closed.json',result);outcomes.append(result)
            # Both fixed diagnostic targets are attempted; safety/release failure stops.
            if p.gpu_sample(gpu)['apps']:raise ValueError('release gate failed')
    except Exception as exc:error=type(exc).__name__
    finally:
        rows=[]
        for row in schedule():
            ep=R/f'episode-{row["index"]}';out=dict(**row,status='not_started',source_commit=plan['source_commit'])
            if (ep/'started.json').exists():out['status']='incomplete'
            if (ep/'closed.json').exists():out.update(read(ep/'closed.json'));out['status']='failed'
            if (ep/'completed.json').exists():
                c=read(ep/'completed.json');out.update({k:v for k,v in c.items() if k not in ('output','gpu_training')})
                out['status']='complete' if c['complete'] and out.get('returncode')==0 else 'failed'
                out['gpu_training_verified']=bool(c.get('gpu_training'))
                out['output_sha256']=c.get('output',{}).get('sha256')
            rows.append(out)
        write(R/'closed.json',dict(planned=2,attempted=sum(r['status']!='not_started' for r in rows),complete=sum(r['status']=='complete' for r in rows),controller_error=error,elapsed_seconds=time.time()-start))
        write(R/'runs.json',rows)
        with (R/'runs.csv').open('x',newline='') as f:
            w=csv.DictWriter(f,fieldnames=sorted({k for r in rows for k in r}));w.writeheader();w.writerows(rows)
    return 0 if error is None and all(r['status']=='complete' for r in rows) else 1


def submit():
    check();env=pilot().runtime().infra().clean_env()
    if read(R/'preflight.json')['plan_sha256']!=sha(R/'plan.json'):raise ValueError('preflight drift')
    jobs=subprocess.check_output(['squeue','-u','yzyang4','-h','-o','%i'],env=env,text=True,timeout=15).split()
    if set(jobs)-{'12535'}:raise ValueError('unexpected active job')
    write(R/'submit-intent.json',dict(gpu_hours_cap=.25,planned=2,plan_sha256=sha(R/'plan.json')))
    result=subprocess.run(['sbatch','--parsable','--chdir='+str(R),'--output='+str(R/'allocation-%j.out'),'--error='+str(R/'allocation-%j.err'),str(R/'run.sbatch')],env=env,capture_output=True,text=True,timeout=20)
    job=result.stdout.strip().split(';')[0]
    if result.returncode or not job.isdigit():raise RuntimeError('ambiguous submission, do not retry')
    write(R/'launch.json',dict(job=job,plan_sha256=sha(R/'plan.json')))
    print(json.dumps(dict(status='SUBMITTED',job=job,gpu_hours_cap=.25)))


if __name__=='__main__':
    os.umask(0o077);os.environ.update(PYTHON_DOTENV_DISABLED='1',PYTHONDONTWRITEBYTECODE='1')
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['prepare','submit','worker','controller']);ap.add_argument('--commit');ap.add_argument('--index',type=int);a=ap.parse_args()
    if a.mode=='prepare':prepare(a.commit)
    elif a.mode=='worker':sys.exit(worker(a.index))
    else:sys.exit(globals()[a.mode]())
