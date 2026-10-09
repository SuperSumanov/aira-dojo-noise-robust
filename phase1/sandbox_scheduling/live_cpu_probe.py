"""Bounded Slurm CPU-step binding probe, no model/data/container execution.

One allocation, 3 reserved GPUs and 18 usable cores, maximum 120s / 0.1 GPUh.
Two simultaneous steps record actual topology; success requires 12+6 disjoint
physical cores. This is a resource contract diagnosis, not an experiment gain.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parent
PY='/research/d7/spc/yzyang4/venvs/aira/bin/python'


def write(name,value):
    with (ROOT/name).open('x') as file:
        json.dump(value,file,indent=2,sort_keys=True)


def topology():
    rows=[]
    for cpu in sorted(os.sched_getaffinity(0)):
        base=Path(f'/sys/devices/system/cpu/cpu{cpu}/topology')
        rows.append(dict(cpu=cpu,socket=int((base/'physical_package_id').read_text()),
                         core=int((base/'core_id').read_text())))
    return rows


def role(name):
    write(name+'.json',dict(role=name,topology=topology(),time=time.time(),
        job=os.environ['SLURM_JOB_ID'],step=os.environ['SLURM_STEP_ID'],
        cpus_per_task=os.environ.get('SLURM_CPUS_PER_TASK'),
        hint=os.environ.get('SLURM_HINT'),
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))
    time.sleep(10)


def controller():
    procs=[]
    try:
        for name,cpus,gpus in (('service',12,2),('execution',6,1)):
            with (ROOT/(name+'.log')).open('xb') as log:
                procs.append(subprocess.Popen(['srun','--exclusive','--nodes=1','--ntasks=1',
                    '--hint=nomultithread','--cpus-per-task='+str(cpus),'--gres=gpu:'+str(gpus),
                    '--time=00:01:00',PY,'-B',str(Path(__file__).resolve()),'role','--role',name],
                    stdout=log,stderr=log))
        returncodes=[p.wait(timeout=45) for p in procs]
        if any(returncodes):raise RuntimeError('step failure')
        s=json.loads((ROOT/'service.json').read_text());e=json.loads((ROOT/'execution.json').read_text())
        sc={(r['socket'],r['core']) for r in s['topology']}
        ec={(r['socket'],r['core']) for r in e['topology']}
        sl={r['cpu'] for r in s['topology']};el={r['cpu'] for r in e['topology']}
        result=dict(service_physical_cores=len(sc),execution_physical_cores=len(ec),
            service_logical_cpus=len(sl),execution_logical_cpus=len(el),
            physical_disjoint=not sc&ec,logical_disjoint=not sl&el,
            same_job=s['job']==e['job'],distinct_steps=s['step']!=e['step'],
            no_model_or_candidate_execution=True)
        result['passed']=len(sc)==12 and len(ec)==6 and not sc&ec and not sl&el and result['same_job'] and result['distinct_steps']
        write('closed.json',result);print(json.dumps(result))
    finally:
        for p in procs:
            if p.poll() is None:
                p.terminate()
                try:p.wait(timeout=8)
                except subprocess.TimeoutExpired:p.kill();p.wait(timeout=5)


def submit():
    batch=f'''#!/bin/bash
#SBATCH --job-name=r14-cpu-binding
#SBATCH --partition=gpu_24h
#SBATCH --account=gpu
#SBATCH --qos=gpu
#SBATCH --nodes=1
#SBATCH --nodelist=gpu27
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=18
#SBATCH --hint=nomultithread
#SBATCH --gres=gpu:3
#SBATCH --time=00:02:00
#SBATCH --no-requeue
set -euo pipefail
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
timeout --signal=TERM --kill-after=10s 100s {PY} -B {ROOT/'live_cpu_probe.py'} controller
'''
    with (ROOT/'run.sbatch').open('x') as file:file.write(batch)
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    write('submit-intent.json',dict(source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        gpu_seconds_cap=360,no_model_or_candidate_execution=True))
    r=subprocess.run(['sbatch','--parsable','--chdir='+str(ROOT),'--output='+str(ROOT/'allocation-%j.out'),
        '--error='+str(ROOT/'allocation-%j.err'),str(ROOT/'run.sbatch')],env=env,capture_output=True,text=True,timeout=25)
    job=r.stdout.strip().split(';')[0]
    if r.returncode or not job.isdigit():raise RuntimeError('ambiguous submission; do not retry')
    write('launch.json',dict(job=job));print(json.dumps(dict(job=job,gpu_seconds_cap=360)))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=('submit','controller','role'))
    p.add_argument('--role',choices=('service','execution'));a=p.parse_args()
    if a.mode=='role':role(a.role)
    else:globals()[a.mode]()
