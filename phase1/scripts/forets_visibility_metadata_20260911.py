"""Read only own Slurm device-cgroup metadata; never load or open a GPU.

Run controller under a NEW two-GPU, five-minute salloc on gpu28.
The baseline and two concurrent one-GPU steps run plain Python only.
No container, model, credentials, task data, GPU library or result access.
"""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import sys
import time


def save(path, value):
    with path.open('x', encoding='utf8') as f:
        json.dump(value, f, sort_keys=True, indent=2)


def observe():
    if socket.gethostname().split('.')[0] != 'gpu28':
        raise RuntimeError('wrong node')
    groups = Path('/proc/self/cgroup').read_text().splitlines()
    devices = [line.split(':', 2)[2] for line in groups
               if 'devices' in line.split(':', 2)[1].split(',')]
    if len(devices) != 1:
        raise RuntimeError('requires a single cgroup-v1 device controller')
    cg = Path('/sys/fs/cgroup/devices') / devices[0].lstrip('/')
    job = os.environ['SLURM_JOB_ID']
    step = os.environ['SLURM_STEP_ID']
    if (not job.isdigit() or not step.isdigit()
            or 'job_'+job not in cg.parts or 'step_'+step not in cg.parts):
        raise RuntimeError('not inside the claimed job/step device cgroup')
    # Read current process rule file; no permission changes or device opens.
    rule_file = cg / 'devices.list'
    rules = rule_file.read_text().splitlines()
    nodes = []
    for path in sorted(Path('/dev').glob('nvidia[0-9]*')):
        if not re.fullmatch(r'nvidia[0-9]+', path.name):
            continue
        info = path.lstat()
        if not stat.S_ISCHR(info.st_mode):
            raise RuntimeError('unexpected non-character GPU path')
        nodes.append(dict(path=str(path), major=os.major(info.st_rdev),
                          minor=os.minor(info.st_rdev)))
    env_names = ('SLURM_JOB_ID','SLURM_STEP_ID','SLURM_JOB_GPUS',
                 'SLURM_STEP_GPUS','CUDA_VISIBLE_DEVICES','CUDA_DEVICE_ORDER')
    return dict(utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                node=socket.gethostname(), env={k:os.environ.get(k) for k in env_names},
                devices_cgroup=str(cg), rules=rules, device_nodes=nodes,
                gpu_device_opens=0, gpu_library_loads=0, gpu_compute_calls=0)


def worker(root, role):
    save(root / (role+'.started.json'), dict(
        utc=dt.datetime.now(dt.timezone.utc).isoformat(),
        node=socket.gethostname(), step=os.environ.get('SLURM_STEP_ID')))
    record = observe()
    record['role'] = role
    save(root / (role+'.json'), record)
    if role != 'zero':
        end = time.monotonic()+130
        while not (root/'release-workers').exists():
            if time.monotonic() >= end:
                raise TimeoutError('metadata peer barrier expired')
            time.sleep(.2)
    return record


def controller(root):
    job = os.environ.get('SLURM_JOB_ID','')
    if not job.isdigit() or root.parent != Path('/research/d7/spc/yzyang4'):
        raise RuntimeError('new owned allocation and explicit research root required')
    if not root.name.startswith('forets-visibility-meta-20260911-'):
        raise RuntimeError('wrong diagnostic directory')
    result = dict(job_id=job, role='device_visibility_metadata_only',
                  script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  source_commit=os.environ.get('FORETS_SOURCE_COMMIT'), steps={},
                  gpu_compute_calls=0, api_calls=0, model_loads=0)
    children = []
    def start(role, count):
        env = dict(os.environ)
        for name in ('SLURM_STEP_GPUS','SLURM_STEP_ID','CUDA_VISIBLE_DEVICES','GPU_DEVICE_ORDINAL'):
            env.pop(name, None)
        cmd = ['srun','--jobid='+job,'--exclusive','--nodes=1','--ntasks=1',
               '--cpus-per-task='+str(6 if count else 1),
               '--gres=gpu:'+str(count),'--time=00:03:00',
               '--job-name=forets-meta-'+role, sys.executable, str(Path(__file__).resolve()),
               '--root',str(root),'--role',role]
        p = subprocess.Popen(cmd, env=env, stdin=subprocess.DEVNULL,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        children.append((role,p))
        result['steps'][role] = dict(command=cmd)
        return p
    try:
        zero=start('zero',0)
        _, err=zero.communicate(timeout=45)
        result['steps']['zero'].update(rc=zero.returncode, stderr=err[-1000:])
        if zero.returncode: raise RuntimeError('zero GPU metadata step failed')
        first=start('one_a',1)
        end=time.monotonic()+90
        while not (root/'one_a.json').exists():
            if first.poll() is not None or time.monotonic() >= end:
                raise RuntimeError('first single GPU step did not become ready')
            time.sleep(.2)
        second=start('one_b',1)
        end=time.monotonic()+90
        while not (root/'one_b.json').exists():
            if second.poll() is not None or first.poll() is not None or time.monotonic() >= end:
                raise RuntimeError('concurrent single GPU step did not become ready')
            time.sleep(.2)
        result['single_gpu_steps_simultaneously_active']=first.poll() is None and second.poll() is None
        save(root/'release-workers', {'release':True})
        for role,p in children[1:]:
            _,err=p.communicate(timeout=20)
            result['steps'][role].update(rc=p.returncode,stderr=err[-1000:])
            if p.returncode: raise RuntimeError('single GPU metadata step failed')
        result['status']='metadata_collected_not_compute_qualified'
    except Exception as exc:
        result['status']='failed'
        result['error_type']=type(exc).__name__
    finally:
        for role,p in children:
            if p.poll() is None:
                p.terminate()
                try:_,err=p.communicate(timeout=10)
                except subprocess.TimeoutExpired:
                    p.kill();_,err=p.communicate(timeout=5)
                result['steps'][role]['stderr']=err[-1000:]
            elif 'stderr' not in result['steps'][role]:
                _,err=p.communicate(timeout=5)
                result['steps'][role]['stderr']=err[-1000:]
            result['steps'][role]['rc']=p.returncode
        for role in ('zero','one_a','one_b'):
            path=root/(role+'.json')
            if path.exists():result['steps'][role]['observation']=json.loads(path.read_text())
            started=root/(role+'.started.json')
            if started.exists():result['steps'][role]['python_started']=json.loads(started.read_text())
        save(root/'result.json',result)
        print(json.dumps(result,sort_keys=True))
    return 0 if result['status']=='metadata_collected_not_compute_qualified' else 1


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--role',choices=('controller','zero','one_a','one_b'),required=True)
    a=p.parse_args()
    if a.role=='controller':raise SystemExit(controller(a.root.resolve(strict=True)))
    worker(a.root.resolve(strict=True),a.role)
