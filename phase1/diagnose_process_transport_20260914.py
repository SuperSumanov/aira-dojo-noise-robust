"""Bounded original-image process transport diagnostic, not an e2e deployment.

No task data, model API, base-model training, current trial mutation, or replay.
Fresh containment per program: do not introduce shared interpreter state.
"""
import argparse
import datetime as dt
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time

BASE=Path('/research/d7/spc/yzyang4')
SOURCE=BASE/'forets-wallclock-20260912-88v5m9dr/source'
DONOR=BASE/'forets-classic-control-20260914-6jkjkwd5'
TREE='8bb325fa167a9db54656dd6535ce1f3d69859c22'
HELPERS=('forets_closed_pool_native_20260911.py','forets_current_pool_native_20260912.py',
    'forets_gpu_binding_20260911.py','forets_native_cuda_identity_20260911.py',
    'forets_native_gpu_binding_20260911.py','forets_opencl_allowlist_20260911.py',
    'forets_opencl_readonly_ab.py','forets_closed_pool_20260911.py','bin/singularity')
SECRET=re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{16,}|gh[pousr]_[a-z0-9]{16,}|github_pat_[a-z0-9_]{20,}|Bearer\s+[a-z0-9_.-]{20,})')


def sha(raw):return hashlib.sha256(raw).hexdigest()
def read(p):return json.loads(p.read_bytes())
def write(p,value):
    raw=(json.dumps(value,sort_keys=True,allow_nan=False)+'\n').encode()
    if SECRET.search(raw):raise ValueError('credential-shaped diagnostic output')
    with p.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    return sha(raw)
def utc():return dt.datetime.now(dt.timezone.utc).isoformat()
def checked_root(p):
    p=p.resolve(strict=True)
    if p.parent!=BASE or not re.fullmatch(r'forets-process-transport-20260914-[a-z0-9_]+',p.name):raise ValueError('root scope')
    return p


def binding_context(env):
    root=checked_root(Path(env['FORETS_CURRENT_POOL_ROOT']))
    identity=Path(env['DOJO_WORKER_IDENTITY_PATH'])
    if identity.parent!=root or not re.fullmatch(r'identity-[0-9]+\.json',identity.name):raise ValueError('identity scope')
    if read(root/'execution.claim.json')['job']!=env['SLURM_JOB_ID']:raise ValueError('allocation identity')
    return identity.with_suffix('.native-binding.json')


def prepare(commit):
    if not re.fullmatch('[0-9a-f]{40}',commit):raise ValueError('commit')
    p=read(DONOR/'prepared.json');root=Path(tempfile.mkdtemp(prefix='forets-process-transport-20260914-',dir=BASE))
    for n in HELPERS:
        source=DONOR/n;raw=source.read_bytes()
        if sha(raw)!=p['files'][n]:raise ValueError('qualified helper drift')
        out=root/n;out.parent.mkdir(exist_ok=True,parents=True);shutil.copy2(source,out)
    shutil.copy2(Path(__file__),root/Path(__file__).name)
    (root/'forets_current_pool_20260912.py').write_text('from diagnose_process_transport_20260914 import binding_context\n')
    (root/'opencl-vendors').mkdir();(root/'opencl-vendors/nvidia.icd').write_text('libnvidia-opencl.so.1\n')
    script='''#!/bin/bash
#SBATCH --job-name=process-transport-diagnostic
#SBATCH --partition=gpu_24h
#SBATCH --account=gpu
#SBATCH --qos=gpu
#SBATCH --nodelist=gpu28
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=6
#SBATCH --time=00:15:00
#SBATCH --no-requeue
set -euo pipefail
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export PYTHON_DOTENV_DISABLED=1
export PYTHONDONTWRITEBYTECODE=1
srun --exclusive --ntasks=1 --cpus-per-task=6 --gres=gpu:1 --time=00:14:00 timeout --signal=TERM --kill-after=10s 790s /research/d7/spc/yzyang4/venvs/aira/bin/python -B ROOT/diagnose_process_transport_20260914.py execute --root ROOT
'''.replace('ROOT',str(root))
    (root/'run.sbatch').write_text(script)
    files={str(p.relative_to(root)):sha(p.read_bytes()) for p in root.rglob('*') if p.is_file()}
    prep=dict(commit=commit,source_tree=TREE,files=files,utc=utc(),scope='synthetic_transport_only',
        paired_fixture_repeats=4,additional_direct_markers=4,direct_error_cases=1,direct_timeout_cases=1,
        gpu_liveness_cases=1,post_timeout_cases=1,api_calls=0,gpu_hours_cap=.25,active_source_changed=False)
    h=write(root/'prepared.json',prep);print(json.dumps(dict(root=str(root),prepared_sha256=h,**{k:v for k,v in prep.items() if k!='files'})))


def checked(root):
    root=checked_root(root);p=read(root/'prepared.json')
    for n,h in p['files'].items():
        if sha((root/n).read_bytes())!=h:raise ValueError('diagnostic code drift')
    art=read(SOURCE.parent/'artifact.json')
    if art['source_tree']!=TREE:raise ValueError('source identity')
    for n,h in art['source_files'].items():
        if sha((SOURCE/n).read_bytes())!=h:raise ValueError('active source drift')
    return p


def stop_owned(child):
    if child.poll() is not None:return
    if child.pid<=1 or os.getpgid(child.pid)!=child.pid:raise ValueError('not an owned process group')
    os.killpg(child.pid,signal.SIGTERM)
    try:child.wait(timeout=4)
    except subprocess.TimeoutExpired:
        if child.poll() is None:os.killpg(child.pid,signal.SIGKILL)
        child.wait(timeout=4)


def replace_bootstrap(args,image,code):
    """Preserve every image/mount/env argument; remove the server-only tail."""
    if args.count(str(image))!=1:raise ValueError('ambiguous image')
    boundary=args.index(str(image));offset=args.index('python',boundary+1)
    if args[offset+1]!='-c':raise ValueError('bootstrap shape')
    return args[:offset]+['python','-c',code]


def direct(root,index,code,seconds=35):
    from dojo.core.interpreters.jupyter.singularity_jupyter_server import _build_singularity_command,_build_container_environment,_build_runtime_environment
    from forets_opencl_allowlist_20260911 import IMAGE
    work=root/f'work-{index}';work.mkdir();(work/'.home').mkdir();(work/'.local').mkdir()
    identity=root/f'identity-{index}.json';write(identity,{})
    os.environ['DOJO_WORKER_IDENTITY_PATH']=str(identity)
    args=_build_singularity_command(runtime_executable=str(root/'bin/singularity'),image_path=IMAGE,
        working_dir=work,bind_inputs_dir=None,read_only_overlays=[],read_only_binds={},
        container_env=_build_container_environment({}),token='unused-diagnostic-no-server')
    args=replace_bootstrap(args,IMAGE,code)
    start=time.monotonic();timed=False
    with (work/'private.log').open('xb') as log:
        child=subprocess.Popen(args,stdout=log,stderr=log,start_new_session=True,env=_build_runtime_environment(os.environ))
        try:child.wait(timeout=seconds)
        except subprocess.TimeoutExpired:timed=True;stop_owned(child)
        finally:
            if child.poll() is None:stop_owned(child)
    raw=(work/'private.log').read_bytes()
    if SECRET.search(raw):raise ValueError('credential shape; no raw log export')
    values=[]
    for line in raw.decode(errors='replace').splitlines():
        if line.startswith('PROCESS_FIXTURE '):values.append(json.loads(line.removeprefix('PROCESS_FIXTURE ')))
    return dict(index=index,mode='direct',exit_code=child.returncode,timed_out=timed,wall_seconds=time.monotonic()-start,
        values=values,entered=(work/'entered').exists(),binding_present=identity.with_suffix('.native-binding.json').exists())


FIXTURE='''import json
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import log_loss
X=np.random.default_rng(5).normal(size=(120,5)); y=np.tile([0,1,2],40)
m=RandomForestClassifier(n_estimators=8,max_depth=3,random_state=0,n_jobs=1).fit(X[:90],y[:90])
print('PROCESS_FIXTURE '+json.dumps({'loss':float(log_loss(y[90:],m.predict_proba(X[90:]),labels=m.classes_)),'rows':30}))
'''
MARKER="import json; print('PROCESS_FIXTURE '+json.dumps({'marker':6}))"


def jupyter(root,index):
    from dojo.core.interpreters.jupyter.singularity_jupyter_server import SingularityJupyterServer
    from forets_opencl_allowlist_20260911 import IMAGE
    work=root/f'work-{index}';work.mkdir();identity=root/f'identity-{index}.json';write(identity,{})
    os.environ['DOJO_WORKER_IDENTITY_PATH']=str(identity);start=time.monotonic();server=None
    row=dict(index=index,mode='jupyter',ready=False,values=[])
    try:
        server=SingularityJupyterServer(working_dir=work,superimage_directory=IMAGE.parent,
            superimage_version='2026-07-macos-v1',startup_timeout=35)
        client=server.get_client();kernel=client.start_kernel('python3')
        with client.get_kernel_client(kernel) as k:
            row['ready']=k.wait_for_ready(timeout_seconds=120)
            if row['ready']:
                result=k.execute(FIXTURE,timeout_seconds=35)
                row.update(is_ok=bool(result.is_ok),timed_out=bool(result.timed_out))
                for part in result.output:
                    for line in part.splitlines():
                        if line.startswith('PROCESS_FIXTURE '):row['values'].append(json.loads(line.removeprefix('PROCESS_FIXTURE ')))
    except Exception as exc:row['error_type']=type(exc).__name__
    finally:
        if server is not None:server.stop()
    row['wall_seconds']=time.monotonic()-start;return row


def execute(root):
    p=checked(root)
    if socket.gethostname().split('.')[0]!='gpu28' or not os.environ.get('SLURM_STEP_ID','').isdigit():raise ValueError('dedicated gpu28 step')
    write(root/'execution.claim.json',dict(job=os.environ['SLURM_JOB_ID'],utc=utc()))
    for key in ('OPENROUTER_API_KEY','PRIMARY_KEY','FORETS_NATIVE_RELEASE','FORETS_CLOSED_POOL_ROOT'):os.environ.pop(key,None)
    os.environ.update(PYTHON_DOTENV_DISABLED='1',LOGGING_DIR=str(root),MLE_BENCH_DATA_DIR=str(BASE/'mle-bench-data'),
        SUPERIMAGE_DIR=str(BASE/'aira-dojo/build/superimage'),DEFAULT_SLURM_PARTITION='gpu_24h',DEFAULT_SLURM_ACCOUNT='gpu',
        DEFAULT_SLURM_QOS='gpu',FORETS_CURRENT_POOL_ROOT=str(root),FORETS_SOURCE_COMMIT=p['commit'],
        PATH=str(root/'bin')+':'+os.environ['PATH'],NO_PROXY='localhost,127.0.0.1,0.0.0.0')
    sys.path[:0]=[str(root),str(SOURCE/'src')];logging.disable(logging.CRITICAL)
    from forets_opencl_allowlist_20260911 import IMAGE
    st=IMAGE.stat()
    if (st.st_size,st.st_mtime_ns)!=(19717783552,1784638286000000000):raise ValueError('image changed')
    rows=[];paired=[];start=time.monotonic();use_jupyter=True
    for repeat in range(4):
        pair={}
        for mode in (('direct','jupyter') if repeat%2==0 else ('jupyter','direct')):
            if time.monotonic()-start>500:raise RuntimeError('diagnostic time allowance')
            if mode=='jupyter' and not use_jupyter:continue
            row=direct(root,len(rows),FIXTURE) if mode=='direct' else jupyter(root,len(rows))
            rows.append(row);pair[mode]=row
            if mode=='jupyter' and (not row['ready'] or not row.get('is_ok')):use_jupyter=False
            write(root/f'case-{row["index"]}.json',row)
        if set(pair)=={'direct','jupyter'} and pair['jupyter'].get('is_ok'):
            paired.append(dict(repeat=repeat,equal_payload=pair['direct']['values']==pair['jupyter']['values']))
    for _ in range(4):rows.append(direct(root,len(rows),MARKER))
    error=direct(root,len(rows),"raise RuntimeError('intentional_process_fixture')");rows.append(error)
    timeout=direct(root,len(rows),"from pathlib import Path; import time; Path('entered').write_text('1'); time.sleep(90)",seconds=20);rows.append(timeout)
    after=direct(root,len(rows),MARKER);rows.append(after)
    gpu=direct(root,len(rows),"import torch,json; x=torch.tensor([1.,2.,3.],device='cuda'); print('PROCESS_FIXTURE '+json.dumps({'cuda':bool(x.is_cuda),'sum':float(x.sum().item()),'devices':torch.cuda.device_count()}))",seconds=45);rows.append(gpu)
    normal=[r for r in rows if r['mode']=='direct' and r not in (error,timeout)]
    conditions=dict(direct_normal_calls_complete=len(normal)==10 and all(r['exit_code']==0 and not r['timed_out'] and r['values'] and r['binding_present'] for r in normal),
        available_paired_outputs_equal=bool(paired) and all(r['equal_payload'] for r in paired),
        code_error_preserved=error['exit_code']!=0 and not error['timed_out'],
        timeout_after_payload_entry=timeout['timed_out'] and timeout['entered'],
        post_timeout_call_ok=after['values']==[dict(marker=6)],
        actual_container_cuda=gpu['values']==[dict(cuda=True,sum=6.,devices=1)])
    result=dict(status='PASS_DIAGNOSTIC_NOT_DEPLOYED' if all(conditions.values()) else 'DIAGNOSTIC_INCOMPLETE_OR_FAILED',
        utc=utc(),rows=rows,paired=paired,conditions=conditions,elapsed_seconds=time.monotonic()-start,
        api_calls=0,task_data_read=False,active_source_changed=False,source_tree=TREE,commit=p['commit'],
        limitation='Synthetic standalone Python only; not arbitrary notebook/IPython semantics, task efficacy, or proof of general reliability. Old failures are not replayed or fixed retroactively.')
    write(root/'result.json',result);print(json.dumps(result),flush=True)


def submit(root):
    p=checked(root);env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    queue=subprocess.check_output(['squeue','-u','yzyang4','-h','-o','%i'],env=env,text=True,timeout=25)
    if len(queue.strip().splitlines())>=4:raise ValueError('job quota')
    write(root/'submit-intent.json',dict(utc=utc(),prepared_sha256=sha((root/'prepared.json').read_bytes()),gpu_hours_cap=.25,api_calls=0))
    out=subprocess.run(['sbatch','--parsable','--chdir='+str(root),'--output='+str(root/'allocation-%j.out'),
        '--error='+str(root/'allocation-%j.err'),str(root/'run.sbatch')],env=env,capture_output=True,text=True,timeout=25)
    job=out.stdout.strip().split(';')[0]
    if out.returncode or not re.fullmatch('[0-9]+',job):raise ValueError('ambiguous submission; no retry')
    write(root/'launch.json',dict(job=job,utc=utc(),commit=p['commit']));print(json.dumps(dict(root=str(root),job=job)))


if __name__=='__main__':
    os.umask(0o077);p=argparse.ArgumentParser();p.add_argument('mode',choices=('prepare','execute','submit'));p.add_argument('--root',type=Path);p.add_argument('--commit');a=p.parse_args()
    prepare(a.commit) if a.mode=='prepare' else globals()[a.mode](a.root)
