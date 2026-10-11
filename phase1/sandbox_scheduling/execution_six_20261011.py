"""Six physical GPU program diagnostic, WITHOUT a model service or quality claims."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time

import six_gpu_capacity_20261011 as r
from device_sweep_20261011 import probe
from live_identity import cores

ROOT=Path('/research/d7/spc/yzyang4/resource-execution-six-20261011-v1')
DONOR=ROOT.parent/'resource-unet-six-capacity-20261011-v2'
PIN='0e41eb5b34d3918357b60999ddff2ac929a0498c7aedbd9b4034fefb76943ff1'
NAME=Path(__file__).name
CAP=1800
FLAGS=('resource temporarily unavailable','pthread_create',"can't start new thread",'out of memory')
for module in (r,r.s,r.s.d):module.ROOT=ROOT;module.NAME=NAME

def read(p):return json.loads(p.read_text())
def write(p,x):r.s.d.write(p,x)
def sha(p):return r.s.d.sha(p)

def schedule():
    return [dict(index=i,block=b,slot=s,program=1,width=w) for i,(b,s,w) in enumerate(
        [(0,0,1),(1,0,1)]+[(b,s,6) for b in (2,3) for s in range(6)])]

def placement(identities,job):
    devices=set();cpus=set();steps=set()
    for v in identities:
        g=set(v['gpu_uuids']);c=cores(v['cpu_topology'])
        assert v['job']==job and v['step'] not in steps
        assert len(g)==1 and len(c)==4 and not(g&devices) and not(c&cpus)
        devices|=g;cpus|=c;steps.add(v['step'])
    return dict(gpu_count=len(devices),physical_cores=len(cpus))

def prepare():
    assert sha(DONOR/'plan.json')==PIN and read(DONOR/'allocation-closed.json')['service_stopped']
    old=read(DONOR/'plan.json')
    assert old['schedule']==schedule() and old['source_families']==1
    for n,h in old['files'].items():assert sha(DONOR/n)==h
    for n,h in old['input_files'].items():assert sha(n)==h
    ROOT.mkdir(mode=0o700)
    for n in old['files']:
        if n=='run.sbatch':continue
        dest=ROOT/n;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(DONOR/n,dest)
    for n in (NAME,'device_sweep_20261011.py'):
        shutil.copyfile(Path(__file__).with_name(n),ROOT/n)
    for row in schedule():(ROOT/f"episode-{row['index']}/input_cache").mkdir(parents=True)
    batch=f'''#!/bin/bash
#SBATCH --job-name=execution-six
#SBATCH --partition=gpu_24h
#SBATCH --account=gpu
#SBATCH --qos=gpu
#SBATCH --nodelist=gpu3
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:6
#SBATCH --cpus-per-task=24
#SBATCH --hint=nomultithread
#SBATCH --time=00:30:00
#SBATCH --no-requeue
set -euo pipefail
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1
timeout --signal=TERM --kill-after=20s 1740s {r.s.d.PY} -B {ROOT}/{NAME} allocation
'''
    (ROOT/'run.sbatch').write_text(batch);subprocess.run(['bash','-n',str(ROOT/'run.sbatch')],check=True)
    subprocess.run([str(r.s.d.PY),'-B',str(ROOT/NAME),'preflight'],check=True)
    p={k:old[k] for k in ('source_commit','programs','input_files','task_image_sha256','candidate_seconds','source_seed','libraries_threads')}
    p.update(question='Can6 isolated real GPU executions coexist without a model service?',schedule=schedule(),planned=14,
        donor_plan_sha256=PIN,source_families=1,gpus=6,cpus=24,worker_cpus=4,node='gpu3',
        allocation_seconds_cap=CAP,gpu_seconds_cap=CAP*6,no_model=True,no_api=True,no_base_training=True,
        readiness_overlay='Same pinned f7 source plus existing buffered-pipe fix; no new timeout or kernel-info retry.',
        source_policy='Same UNet, original588 steps,seed42,public fixture inputs,450s timeout and task image. Post-failure narrower workload,not new tasks.',
        instrumentation='Host cuInit numeric receipt; all execute-call resource error enums including successful calls;1Hz host pressure.',
        acceptance='14/14,588 CUDA steps each,14 outputs all91 pairs within1e-5,distinct GPU UUIDs/physical CPU sets,complete cost and cleanup.',
        stop='Any worker/prelude/candidate failure closes remainder; no replacement. Whole allocation bounded30min.',
        boundary='Not2+6 joint capacity, historical EAGAIN causal reproduction, new-seed confirmation, speedup or quality.',
        files={str(f.relative_to(ROOT)):sha(f) for f in ROOT.rglob('*') if f.is_file() and '__pycache__' not in f.parts})
    write(ROOT/'plan.json',p)
    print(json.dumps(dict(prepared=True,plan_sha256=sha(ROOT/'plan.json'),planned=14,gpu_seconds_cap=CAP*6)))

def observe_executor(base,ep):
    class Observed(base):
        def execute_code(self,*args,**kwargs):
            started=time.time();number=getattr(self,'observed_calls',0);self.observed_calls=number+1
            result=None;error=None
            try:
                result=super().execute_code(*args,**kwargs);return result
            except Exception as exc:error=type(exc).__name__;raise
            finally:
                output='' if result is None else '\n'.join(map(str,result.term_out)).lower()
                write(ep/f'execute-observation-{number}.json',dict(call=number,start=started,end=time.time(),error_type=error,
                    flags={key:key in output for key in FLAGS},exit_code=None if result is None else result.exit_code,
                    timed_out=None if result is None else result.timed_out))
    return Observed

def worker(index):
    ep=ROOT/f'episode-{index}';write(ep/'cuda-before.json',probe(False))
    r.s.d.configure()
    from dojo.core.interpreters.jupyter import jupyter_code_executor as module
    module.JupyterCodeExecutor=observe_executor(module.JupyterCodeExecutor,ep)
    return r.worker(index)

def controller():
    p=read(ROOT/'plan.json');assert all(sha(ROOT/n)==h for n,h in p['files'].items())
    start=time.monotonic();stop=threading.Event();results=[];error=None;processes=[]
    def sample():
        with (ROOT/'pressure.jsonl').open('x') as f:
            while not stop.is_set():f.write(json.dumps(r.s.d.resource_pressure.snapshot())+'\n');f.flush();stop.wait(1)
    observer=threading.Thread(target=sample,daemon=True);observer.start()
    try:
        for block in range(4):
            group=[x for x in schedule() if x['block']==block]
            if time.monotonic()+650>start+CAP-60:break
            processes=[];logs=[];failed=False
            try:
                for row in group:
                    log=(ROOT/f"episode-{row['index']}/worker.private.log").open('x');logs.append(log)
                    proc=subprocess.Popen(['srun','--exclusive','--ntasks=1','--gres=gpu:1','--cpus-per-task=4','--hint=nomultithread',str(r.s.d.PY),'-B',str(ROOT/NAME),'worker',str(row['index'])],stdout=log,stderr=log,start_new_session=True)
                    processes.append((row,proc))
                deadline=time.monotonic()+140
                while not all((ROOT/f"episode-{x['index']}/ready.json").exists() for x in group):
                    if any(proc.poll() is not None for _,proc in processes):raise RuntimeError('worker prelude')
                    if time.monotonic()>deadline:raise TimeoutError('readiness')
                    time.sleep(.5)
                ids=[read(ROOT/f"episode-{x['index']}/identity.json") for x in group]
                checked=placement(ids,os.environ['SLURM_JOB_ID']);write(ROOT/f'block-{block}-go.json',dict(time=time.time(),**checked))
                for row,proc in processes:
                    rc=proc.wait(timeout=max(1,deadline+510-time.monotonic()));results.append(dict(index=row['index'],returncode=rc))
                failed=any(x['returncode'] for x in results[-len(group):])
            except Exception as exc:
                failed=True;write(ROOT/f'block-{block}-failure.json',dict(error_type=type(exc).__name__))
                for row,proc in processes:
                    if not any(x['index']==row['index'] for x in results):results.append(dict(index=row['index'],returncode=proc.poll()))
            finally:
                for _,proc in processes:r.s.stop_owned(proc)
                for f in logs:f.close()
                time.sleep(3);write(ROOT/f'block-{block}-after.json',r.s.d.resource_pressure.snapshot())
            if failed:break
    except Exception as exc:error=type(exc).__name__
    finally:
        for _,proc in processes:r.s.stop_owned(proc)
        stop.set();observer.join(timeout=10)
        complete=sum((ROOT/f"episode-{x['index']}/complete.json").exists() and read(ROOT/f"episode-{x['index']}/complete.json")['complete'] for x in schedule())
        write(ROOT/'closed.json',dict(planned=14,attempted=len(results),complete=complete,rows=results,error_type=error))
        write(ROOT/'allocation-after.json',r.s.d.resource_pressure.snapshot())
    return int(error is not None or complete!=14)

if __name__=='__main__':
    os.umask(0o077)
    if sys.argv[1]=='prepare':prepare()
    elif sys.argv[1]=='preflight':
        r.s.d.configure()
        from dojo.core.interpreters.jupyter.jupyter_code_executor import JupyterCodeExecutor
        from dojo.core.interpreters.jupyter.singularity_jupyter_server import SingularityJupyterServer
        assert callable(JupyterCodeExecutor.execute_code) and callable(JupyterCodeExecutor.fetch_file)
        assert r.ROOT==r.s.ROOT==r.s.d.ROOT==ROOT
        write(ROOT/'entry-preflight.json',dict(imports_pass=True,no_kernel_started=True,no_model=True))
    elif sys.argv[1]=='worker':sys.exit(worker(int(sys.argv[2])))
    elif sys.argv[1]=='allocation':sys.exit(controller())
    else:raise ValueError('mode')
