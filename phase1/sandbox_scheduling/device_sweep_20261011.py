"""Eight owned GPUs: default/unset mask, host/task image; no ML/data/API.

Removing a visibility mask is diagnostic ONLY inside our8-GPU allocation.
Do not run GPU arithmetic when a probe sees more than its single expected GPU.
"""
import ctypes
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time
import uuid
import hashlib

BASE=Path('/research/d7/spc/yzyang4');ROOT=BASE/'resource-device-sweep-20261011-v1'
PY=BASE/'venvs/aira/bin/python';IMAGE=BASE/'aira-dojo/build/superimage/superimage.root.2026-07-macos-v1.sif'
NAME=Path(__file__).name
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def write(p,v):
    with p.open('x') as f:json.dump(v,f,indent=2,sort_keys=True,allow_nan=False)
def safe_mask(value):
    return value if value is None or re.fullmatch(r'(?:\d+|GPU-[a-fA-F0-9-]+)(?:,(?:\d+|GPU-[a-fA-F0-9-]+))*',value) else '<nonstandard-suppressed>'


def image_command(ep,mask,environment):
    env={k:v for k,v in environment.items() if not k.startswith(('SINGULARITYENV_','APPTAINERENV_'))
         and k not in ('SINGULARITY_BIND','SINGULARITY_BINDPATH','APPTAINER_BIND','APPTAINER_BINDPATH')}
    if mask=='unset':env.pop('CUDA_VISIBLE_DEVICES',None)
    cmd=['singularity','exec','--containall','--cleanenv','--no-home','--nv','--no-mount','hostfs,bind-paths',
         '--bind',str(ep)+':/workspace:rw','--bind',str(ROOT/NAME)+':/device_sweep.py:ro','--pwd','/workspace',str(IMAGE),'env']
    if mask=='unset':cmd+=['-u','CUDA_VISIBLE_DEVICES']
    cmd+=['PYTHONDONTWRITEBYTECODE=1','OMP_NUM_THREADS=1','OPENBLAS_NUM_THREADS=1','MKL_NUM_THREADS=1']
    if mask=='default' and 'CUDA_VISIBLE_DEVICES' in env:cmd+=['CUDA_VISIBLE_DEVICES='+env['CUDA_VISIBLE_DEVICES']]
    return cmd+['python','-B','/device_sweep.py','probe','1'],env


def probe(arithmetic):
    result=dict(mask=safe_mask(os.environ.get('CUDA_VISIBLE_DEVICES')),pid=os.getpid(),affinity_count=len(os.sched_getaffinity(0)))
    try:
        lib=ctypes.CDLL('libcuda.so.1');rc=lib.cuInit(0);name=ctypes.c_char_p();lib.cuGetErrorName(rc,ctypes.byref(name))
        result.update(cuinit_rc=rc,cuinit_name=(name.value or b'UNKNOWN').decode('ascii'))
        if rc:return result
        count=ctypes.c_int();rc=lib.cuDeviceGetCount(ctypes.byref(count));result.update(count_rc=rc,visible_devices=count.value,uuids=[])
        if rc:return result
        for i in range(min(count.value,8)):
            dev=ctypes.c_int();raw=(ctypes.c_ubyte*16)();assert lib.cuDeviceGet(ctypes.byref(dev),i)==0 and lib.cuDeviceGetUuid(ctypes.byref(raw),dev)==0
            result['uuids'].append('GPU-'+str(uuid.UUID(bytes=bytes(raw))))
        result['arithmetic_requested']=arithmetic
        if arithmetic and count.value==1:
            import torch
            assert torch.cuda.device_count()==1
            x=torch.tensor([[1.,2.],[3.,4.]],device='cuda:0');assert (x@x).cpu().tolist()==[[7.,10.],[15.,22.]]
            result.update(arithmetic_pass=True,torch_version=torch.__version__,torch_cuda_version=torch.version.cuda)
        else:result['arithmetic_pass']=None
    except Exception as exc:result['error_type']=type(exc).__name__
    return result


def prepare():
    donor=BASE/'resource-unet-six-capacity-20261011-v2'
    assert sha(donor/'plan.json')=='0e41eb5b34d3918357b60999ddff2ac929a0498c7aedbd9b4034fefb76943ff1'
    assert read(donor/'allocation-closed.json')['service_stopped']
    ROOT.mkdir(mode=0o700);shutil.copyfile(__file__,ROOT/NAME)
    for i in range(8):(ROOT/f'slot-{i}').mkdir()
    batch=f'''#!/bin/bash
#SBATCH --job-name=device-sweep8
#SBATCH --partition=gpu_24h
#SBATCH --account=gpu
#SBATCH --qos=gpu
#SBATCH --nodelist=gpu1
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:8
#SBATCH --cpus-per-task=32
#SBATCH --hint=nomultithread
#SBATCH --time=00:10:00
#SBATCH --no-requeue
set -euo pipefail
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1
timeout --signal=TERM --kill-after=20s 570s {PY} -B {ROOT}/{NAME} controller
'''
    (ROOT/'run.sbatch').write_text(batch);subprocess.run(['bash','-n',str(ROOT/'run.sbatch')],check=True)
    write(ROOT/'plan.json',dict(question='CUDA failure localization, not OpenBLAS EAGAIN attribution',slots=8,
        matrix='8 independentSlurm steps x host/task-image x default/unset visibility mask; no compute on multi-visible probes',
        expected_subprobes=32,gpus=8,node='gpu1',physical_cpus=32,per_step_cpus=4,allocation_seconds_cap=600,gpu_seconds_cap=4800,
        mask_removal='Only diagnostic fresh subprocess inside our owned8-GPU allocation. No automatic production fallback.',
        task_image_sha256=read(donor/'plan.json')['task_image_sha256'],image_reuse='Existing exact pinned image, no image upgrade',
        no_task_data=True,no_training=True,no_model=True,no_paid_api=True,
        stop='Fixed8 steps, each4 subprobes<=40s;180s worker collective;no replacement/retry',
        files={NAME:sha(ROOT/NAME),'run.sbatch':sha(ROOT/'run.sbatch')}))
    print(json.dumps(dict(prepared=True,plan_sha256=sha(ROOT/'plan.json'),gpu_seconds_cap=4800)))


def worker(index):
    ep=ROOT/f'slot-{index}';rows=[]
    physical=[]
    for cpu in sorted(os.sched_getaffinity(0)):
        top=Path(f'/sys/devices/system/cpu/cpu{cpu}/topology')
        physical.append([int((top/'physical_package_id').read_text()),int((top/'core_id').read_text())])
    write(ep/'identity.json',dict(job=os.environ['SLURM_JOB_ID'],step=os.environ['SLURM_STEP_ID'],
        masks={k:safe_mask(os.environ.get(k)) for k in ('CUDA_VISIBLE_DEVICES','SLURM_STEP_GPUS','SLURM_JOB_GPUS')},
        affinity=sorted(os.sched_getaffinity(0)),physical_cores=sorted({tuple(x) for x in physical})))
    for mode in ('host','image'):
        for mask in ('default','unset'):
            env=dict(os.environ)
            if mask=='unset':env.pop('CUDA_VISIBLE_DEVICES',None)
            if mode=='host':cmd=[str(PY),'-B',str(ROOT/NAME),'probe','0']
            else:cmd,env=image_command(ep,mask,env)
            start=time.time()
            try:
                out=subprocess.run(cmd,env=env,capture_output=True,text=True,timeout=40)
                values=[json.loads(x) for x in out.stdout.splitlines() if x.startswith('{')];assert len(values)==1
                row=dict(mode=mode,mask=mask,returncode=out.returncode,seconds=time.time()-start,probe=values[0])
            except Exception as exc:row=dict(mode=mode,mask=mask,error_type=type(exc).__name__,seconds=time.time()-start)
            rows.append(row);write(ep/f'{mode}-{mask}.json',row)
    write(ep/'complete.json',dict(index=index,observed=len(rows),rows=rows));return 0


def controller():
    p=read(ROOT/'plan.json');assert all(sha(ROOT/n)==h for n,h in p['files'].items())
    procs=[];logs=[];error=None;start=time.monotonic()
    try:
        for i in range(8):
            log=(ROOT/f'slot-{i}/worker.private.log').open('x');logs.append(log)
            procs.append(subprocess.Popen(['srun','--exclusive','--ntasks=1','--gres=gpu:1','--cpus-per-task=4','--hint=nomultithread',
                str(PY),'-B',str(ROOT/NAME),'worker',str(i)],stdout=log,stderr=log,start_new_session=True))
        for proc in procs:proc.wait(timeout=max(1,180-(time.monotonic()-start)))
    except Exception as exc:error=type(exc).__name__
    finally:
        for proc in procs:
            if proc.poll() is None:
                os.killpg(proc.pid,signal.SIGTERM)
                try:proc.wait(timeout=5)
                except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait(timeout=5)
        for f in logs:f.close()
        rows=[read(f) for f in sorted(ROOT.glob('slot-*/complete.json'))]
        write(ROOT/'closed.json',dict(planned_slots=8,observed_slots=len(rows),expected_subprobes=32,observed_subprobes=sum(r['observed'] for r in rows),
            returncodes=[p.returncode for p in procs],error_type=error,rows=rows))
    return int(error is not None)


if __name__=='__main__':
    os.umask(0o077)
    if sys.argv[1]=='probe':print(json.dumps(probe(sys.argv[2]=='1')))
    elif sys.argv[1]=='prepare':prepare()
    elif sys.argv[1]=='worker':sys.exit(worker(int(sys.argv[2])))
    elif sys.argv[1]=='controller':sys.exit(controller())
    else:raise ValueError('mode')
