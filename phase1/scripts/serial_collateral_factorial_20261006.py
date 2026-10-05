"""Pre-outcome scheduling amendment: one available 3090, same 4 GPUh cap.

Original frozen plan/config/programs remain unchanged. The unstarted two-GPU
allocation is explicitly withdrawn; only execution concurrency/deadline differ.
"""
import argparse
import json
import os
import subprocess
from pathlib import Path
from run_collateral_factorial_20261006 import R, PY, NAME, check, read, runtime, schedule, sha, write

THIS='serial_collateral_factorial_20261006.py'

def submit():
    p=check();runtime()
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    old=read(R/'launch.json')['job'];assert old=='16536'
    assert not list(R.glob('episode-*/native.json'))
    q=subprocess.check_output(['squeue','-j',old,'-h','-o','%i|%j|%T'],env=env,text=True,timeout=20).strip()
    assert q==old+'|collateral-factorial|PENDING'
    assert read(R/'preflight.json')['plan_sha256']==sha(R/'plan.json')
    assert not (R/'serial-launch.json').exists()
    # The image content was verified by the successful original submit, and is
    # unchanged by this scheduler-only amendment; reuse that receipt.
    original=R/THIS
    assert sha(original)==sha(__file__)
    write(R/'scheduling-amendment.json',dict(original_job=old,original_plan_sha256=sha(R/'plan.json'),
        reason='gpu27 has one RTX3090 available; two-GPU request cannot start in research window.',
        unstarted_verified=True,gpus=1,allocation_seconds=14400,gpu_hours_cap=4,
        program_seconds=240,worker_seconds=390,step_seconds=420,assigned=32,
        node='gpu27',cpus=6,concurrency=1,script_sha256=sha(__file__),
        scientific_configs_and_candidates_unchanged=True,outcome_values_read=False))
    batch=f'''#!/bin/bash
#SBATCH --job-name=collateral-serial
#SBATCH --partition=gpu_24h
#SBATCH --account=gpu
#SBATCH --qos=gpu
#SBATCH --nodelist=gpu27
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=6
#SBATCH --time=04:00:00
#SBATCH --no-requeue
set -euo pipefail
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1
timeout --signal=TERM --kill-after=20s 14320s {PY} -B {R}/{THIS} controller
'''
    with (R/'serial.sbatch').open('x') as f:f.write(batch)
    subprocess.run(['bash','-n',str(R/'serial.sbatch')],check=True)
    # Pending state rechecked immediately before cancelling our own identified job.
    q=subprocess.check_output(['squeue','-j',old,'-h','-o','%i|%j|%T'],env=env,text=True,timeout=20).strip()
    assert q==old+'|collateral-factorial|PENDING' and not list(R.glob('episode-*/native.json'))
    subprocess.run(['scancel',old],env=env,check=True,timeout=20)
    write(R/'withdrawn-unstarted.json',dict(job=old,reason='one-GPU scheduler amendment',started=0))
    write(R/'serial-submit-intent.json',dict(amendment_sha256=sha(R/'scheduling-amendment.json')))
    q=subprocess.run(['sbatch','--parsable','--chdir='+str(R),'--output='+str(R/'serial-allocation-%j.out'),
        '--error='+str(R/'serial-allocation-%j.err'),str(R/'serial.sbatch')],env=env,capture_output=True,text=True,timeout=25)
    job=q.stdout.strip().split(';')[0]
    assert q.returncode==0 and job.isdigit(),'ambiguous submission; no retry'
    write(R/'serial-launch.json',dict(job=job,amendment_sha256=sha(R/'scheduling-amendment.json'),
        sbatch_sha256=sha(R/'serial.sbatch'),plan_sha256=sha(R/'plan.json')))
    print(json.dumps(dict(job=job,withdrawn_unstarted=old,gpus=1,gpu_hours_cap=4)))

def controller():
    check();m=runtime();a=read(R/'scheduling-amendment.json');launch=read(R/'serial-launch.json')
    assert launch['job']==os.environ['SLURM_JOB_ID']
    assert launch['amendment_sha256']==sha(R/'scheduling-amendment.json')
    assert a['script_sha256']==sha(__file__) and launch['sbatch_sha256']==sha(R/'serial.sbatch')
    codes=[]
    for s in schedule():
        i=s['index'];ep=R/f'episode-{i}';assert not (ep/'native.json').exists()
        cmd=['srun','--exclusive','--nodes=1','--ntasks=1','--cpus-per-task=6','--gres=gpu:1',
            '--time=00:07:00',str(PY),'-B',str(R/NAME),'worker','--index',str(i)]
        with (ep/'worker.private.log').open('xb') as f:
            q=subprocess.run(cmd,env=m.infra().clean_env(),stdout=f,stderr=f)
        write(ep/'closed.json',dict(returncode=q.returncode));codes.append(q.returncode)
    write(R/'closed.json',dict(returncodes=codes,assigned=32,scheduling_amendment_sha256=sha(R/'scheduling-amendment.json')))

if __name__=='__main__':
    os.umask(0o077);p=argparse.ArgumentParser();p.add_argument('mode',choices=['submit','controller'])
    globals()[p.parse_args().mode]()
