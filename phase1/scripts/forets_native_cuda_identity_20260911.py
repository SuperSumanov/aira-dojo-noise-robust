"""Observe native CUDA-selected identities in two fresh Slurm steps.

No container, model, task, API, CUDA context/allocation or arithmetic. CUDA
driver initialization/identity queries are explicit, unlike the earlier
filesystem-only diagnostic. Does not infer permission from devices.list.
"""
from __future__ import annotations
import argparse
import ctypes as C
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import sys
import time
import uuid


def write(path, value):
    with path.open('x') as f:json.dump(value,f,indent=2,sort_keys=True)


def identity():
    if socket.gethostname().split('.')[0]!='gpu28':raise RuntimeError('wrong node')
    if os.environ.get('CUDA_VISIBLE_DEVICES')!='0':raise RuntimeError('expected native single-device mask')
    device_list=os.environ.get('SLURM_STEP_GPUS','')
    if not re.fullmatch(r'\d+',device_list):raise RuntimeError('requires a single Slurm GPU')
    driver=C.CDLL('libcuda.so.1')
    def call(name,*args):
        rc=getattr(driver,name)(*args)
        if rc:raise RuntimeError(name+' returned '+str(rc))
    call('cuInit',C.c_uint(0))
    count=C.c_int();call('cuDeviceGetCount',C.byref(count))
    if count.value!=1:raise RuntimeError('native CUDA exposes other than one device')
    device=C.c_int();call('cuDeviceGet',C.byref(device),C.c_int(0))
    raw_uuid=(C.c_ubyte*16)();call('cuDeviceGetUuid',C.byref(raw_uuid),device)
    bus=C.create_string_buffer(64);call('cuDeviceGetPCIBusId',bus,C.c_int(64),device)
    version=C.c_int();call('cuDriverGetVersion',C.byref(version))
    name=C.create_string_buffer(128);call('cuDeviceGetName',name,C.c_int(128),device)
    selected_uuid='GPU-'+str(uuid.UUID(bytes=bytes(raw_uuid)))
    proc=[]
    # CPU-readable driver metadata, not nvidia-smi ordinals or config files.
    for info in Path('/proc/driver/nvidia/gpus').glob('*/information'):
        values=dict((k.strip(),v.strip()) for line in info.read_text().splitlines()
                    if ':' in line for k,v in [line.split(':',1)])
        if values.get('GPU UUID')==selected_uuid:
            proc.append(dict(path=str(info),device_minor=values.get('Device Minor'),
                             bus_location=values.get('Bus Location')))
    return dict(node=socket.gethostname(),job=os.environ['SLURM_JOB_ID'],
                step=os.environ['SLURM_STEP_ID'],slurm_step_gpus=device_list,
                cuda_visible_devices=os.environ['CUDA_VISIBLE_DEVICES'],
                device_count=count.value,selected_uuid=selected_uuid,
                pci_bus_id=bus.value.decode(),device_name=name.value.decode(),
                cuda_driver_version=version.value,driver_metadata_matches=proc,
                gpu_arithmetic_calls=0,cuda_contexts_created_by_script=0,
                utc=dt.datetime.now(dt.timezone.utc).isoformat())


def worker():
    def expired(*_):raise TimeoutError('bounded metadata worker')
    signal.signal(signal.SIGALRM,expired);signal.alarm(200)
    try:
        result=identity()
        print('NATIVE_IDENTITY '+json.dumps(result),flush=True)
        if sys.stdin.readline().strip()!='release':raise RuntimeError('controller acknowledgement absent')
    finally:signal.alarm(0)


def controller(root):
    job=os.environ.get('SLURM_JOB_ID','')
    if (not job.isdigit() or root.parent!=Path('/research/d7/spc/yzyang4')
            or not root.name.startswith('forets-native-identity-20260911-')):
        raise RuntimeError('new diagnostic allocation/root required')
    pids=[];result=dict(job=job,source_commit=os.environ.get('FORETS_SOURCE_COMMIT'),
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        role='native_cuda_identity_not_effect',steps=[],gpu_arithmetic_calls=0,
        api_calls=0,model_loads=0)
    def expired(*_):raise TimeoutError('bounded metadata controller')
    signal.signal(signal.SIGALRM,expired);signal.alarm(250)
    try:
        for slot in range(2):
            command=['srun','--jobid='+job,'--exclusive','--nodes=1','--ntasks=1',
                '--cpus-per-task=6','--gres=gpu:1','--time=00:04:00',
                '--job-name=forets-native-id-'+str(slot),sys.executable,str(Path(__file__).resolve()),
                '--root',str(root),'--role=worker']
            env=dict(os.environ)
            for key in ('SLURM_STEP_GPUS','SLURM_STEP_ID','CUDA_VISIBLE_DEVICES','GPU_DEVICE_ORDINAL'):
                env.pop(key,None)
            p=subprocess.Popen(command,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE,text=True)
            pids.append(p);result['steps'].append(dict(command=command))
        for index,p in enumerate(pids):
            line=p.stdout.readline()
            if not line.startswith('NATIVE_IDENTITY '):raise RuntimeError('identity response missing')
            result['steps'][index]['identity']=json.loads(line.removeprefix('NATIVE_IDENTITY '))
        result['simultaneously_active']=all(p.poll() is None for p in pids)
        rows=[r['identity'] for r in result['steps']]
        result['distinct_native_devices']=len({r['selected_uuid'] for r in rows})==2
        result['distinct_slurm_gpu_lists']=len({r['slurm_step_gpus'] for r in rows})==2
        result['status']='identity_observed_not_compute_qualified'
    except Exception as exc:
        result.update(status='failed',error_type=type(exc).__name__)
    finally:
        signal.alarm(0)
        for index,p in enumerate(pids):
            if p.poll() is None:
                try:p.stdin.write('release\n');p.stdin.flush()
                except BrokenPipeError:pass
            try:out,err=p.communicate(timeout=15)
            except subprocess.TimeoutExpired:
                p.terminate()
                try:out,err=p.communicate(timeout=10)
                except subprocess.TimeoutExpired:p.kill();out,err=p.communicate(timeout=5)
            result['steps'][index].update(rc=p.returncode,stderr=err[-1500:])
        write(root/'result.json',result);print(json.dumps(result))
    return 0 if result['status']=='identity_observed_not_compute_qualified' else 1


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',required=True,type=Path);p.add_argument('--role',choices=('worker','controller'),required=True)
    a=p.parse_args()
    if a.role=='controller':raise SystemExit(controller(a.root.resolve(strict=True)))
    worker()
