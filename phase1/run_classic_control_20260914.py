"""Fixed-space, zero-API reference in the unchanged MLE task container."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time

BASE=Path('/research/d7/spc/yzyang4')
ESCOPE=BASE/'forets-wallclock-20260912-88v5m9dr'
SOURCE=ESCOPE/'source'
TREE='8bb325fa167a9db54656dd6535ce1f3d69859c22'
ADAPTER=BASE/'forets-current-pool-20260912-0hz06xtj'
HELPERS=('forets_closed_pool_native_20260911.py','forets_current_pool_native_20260912.py',
    'forets_gpu_binding_20260911.py','forets_native_cuda_identity_20260911.py',
    'forets_native_gpu_binding_20260911.py','forets_opencl_allowlist_20260911.py',
    'forets_opencl_readonly_ab.py','bin/singularity')
FILES=('classic_search_20260914.py','run_classic_control_20260914.py',
    'readout_classic_control_20260914.py','forets_closed_pool_20260911.py','ESCOPE_CLASSIC_CONTROL_PLAN_20260914.md')
SECRET=re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{16,}|gh[pousr]_[a-z0-9]{16,}|github_pat_[a-z0-9_]{20,}|Bearer\s+[a-z0-9_.-]{20,})')


def now():return datetime.now(timezone.utc).isoformat()
def sha(raw):return hashlib.sha256(raw).hexdigest()
def read(path):
    if path.is_symlink():raise ValueError('symlink input')
    raw=path.read_bytes()
    if SECRET.search(raw):raise ValueError('credential shape; no content output')
    return json.loads(raw)
def write(path,obj):
    raw=(json.dumps(obj,sort_keys=True,allow_nan=False)+'\n').encode()
    with path.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    return sha(raw)
def root_check(root):
    root=root.resolve(strict=True)
    if root.parent!=BASE or not re.fullmatch(r'forets-classic-control-20260914-[a-z0-9_]+',root.name):raise ValueError('root scope')
    return root
def source_check():
    a=read(ESCOPE/'artifact.json')
    if a['source_tree']!=TREE:raise ValueError('source tree')
    for n,h in a['source_files'].items():
        if sha((SOURCE/n).read_bytes())!=h:raise ValueError('source drift')


def matrix():
    return [dict(index=i,task=t,seed=s,arm='classic_random_search') for i,(s,t) in
        enumerate((s,t) for s in range(42,46) for t in ('leaf-classification','spaceship-titanic'))]


def prepare(commit):
    if not re.fullmatch(r'[a-f0-9]{40}',commit or ''):raise ValueError('commit')
    source_check();root=Path(tempfile.mkdtemp(prefix='forets-classic-control-20260914-',dir=BASE))
    donor=read(ADAPTER/'submit-intent.json')
    for n in HELPERS:
        raw=(ADAPTER/n).read_bytes()
        if sha(raw)!=donor['code_sha256'][n]:raise ValueError('native adapter drift')
        dest=root/n;dest.parent.mkdir(exist_ok=True,parents=True);shutil.copy2(ADAPTER/n,dest)
    for n in FILES:shutil.copy2(Path(__file__).with_name(n),root/n)
    (root/'forets_current_pool_20260912.py').write_text('from run_classic_control_20260914 import binding_context\n')
    (root/'opencl-vendors').mkdir();(root/'opencl-vendors/nvidia.icd').write_text('libnvidia-opencl.so.1\n')
    script='''#!/bin/bash
#SBATCH --job-name=classic-e2e-reference
#SBATCH --partition=gpu_24h
#SBATCH --account=gpu
#SBATCH --qos=gpu
#SBATCH --nodelist=gpu28
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=6
#SBATCH --time=04:00:00
#SBATCH --no-requeue
set -euo pipefail
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export PYTHON_DOTENV_DISABLED=1
export PYTHONDONTWRITEBYTECODE=1
export PYTHONUNBUFFERED=1
srun --exclusive --ntasks=1 --cpus-per-task=6 --gres=gpu:1 --time=03:58:00 timeout --signal=TERM --kill-after=10s 14100s /research/d7/spc/yzyang4/venvs/aira/bin/python -B ROOT/run_classic_control_20260914.py execute --root ROOT
'''.replace('ROOT',str(root))
    (root/'run.sbatch').write_text(script)
    files={str(p.relative_to(root)):sha(p.read_bytes()) for p in root.rglob('*') if p.is_file()}
    p=dict(commit=commit,source_tree=TREE,utc=now(),rows=matrix(),total_seconds=1200,trial_seconds=300,
        max_trials=64,api_calls=0,files=files)
    h=write(root/'prepared.json',p)
    print(json.dumps(dict(root=str(root),prepared_sha256=h,runs=len(p['rows']),max_gpu_hours=4,api_calls=0)))


def checked(root):
    root_check(root);p=read(root/'prepared.json')
    if p['rows']!=matrix() or p['total_seconds']!=1200 or p['trial_seconds']!=300 or p['source_tree']!=TREE:
        raise ValueError('fixed matrix drift')
    for n,h in p['files'].items():
        if sha((root/n).read_bytes())!=h:raise ValueError('worker drift')
    return p


def binding_context(env):
    root=root_check(Path(env['FORETS_CURRENT_POOL_ROOT']))
    identity=Path(env['DOJO_WORKER_IDENTITY_PATH'])
    if identity.parent!=root or identity.is_symlink() or not re.fullmatch(r'identity-[0-7]\.json',identity.name):raise ValueError('identity scope')
    if read(root/'execution.claim.json')['job']!=env['SLURM_JOB_ID']:raise ValueError('allocation identity')
    return identity.with_suffix('.native-binding.json')


def setup(root,p):
    logging.disable(logging.CRITICAL)
    for n in ('FORETS_NATIVE_RELEASE','FORETS_CLOSED_POOL_ROOT','OPENROUTER_API_KEY','PRIMARY_KEY'):os.environ.pop(n,None)
    os.environ.update(PYTHON_DOTENV_DISABLED='1',PYTHONDONTWRITEBYTECODE='1',LOGGING_DIR=str(root),
        SUPERIMAGE_DIR=str(BASE/'aira-dojo/build/superimage'),MLE_BENCH_DATA_DIR=str(BASE/'mle-bench-data'),
        DEFAULT_SLURM_PARTITION='gpu_24h',DEFAULT_SLURM_ACCOUNT='gpu',DEFAULT_SLURM_QOS='gpu',
        FORETS_SOURCE_COMMIT=p['commit'],FORETS_CURRENT_POOL_ROOT=str(root),PATH=str(root/'bin')+':'+os.environ['PATH'],
        NO_PROXY='localhost,127.0.0.1,0.0.0.0')
    sys.path[:0]=[str(root),str(SOURCE/'src')]


def execute_one(root,row,*,server_type=None):
    from forets_opencl_allowlist_20260911 import IMAGE
    if server_type is None:
        from dojo.core.interpreters.jupyter.singularity_jupyter_server import SingularityJupyterServer
        server_type=SingularityJupyterServer
    i=row['index'];work=root/f'work-{i}';work.mkdir();identity=root/f'identity-{i}.json';write(identity,{})
    os.environ['DOJO_WORKER_IDENTITY_PATH']=str(identity)
    shutil.copy2(root/'classic_search_20260914.py',work/'classic_search_20260914.py')
    # Monotonic clocks share the host kernel across this Singularity namespace.
    start=time.monotonic_ns();deadline=start+1200*10**9
    config=dict(row,started_ns=start,deadline_ns=deadline,total_seconds=1200,trial_seconds=300)
    config_sha=write(work/'classic-config.json',config)
    result=dict(row,started_utc=now(),started_ns=start,deadline_ns=deadline,config_sha256=config_sha,
        status='infrastructure_error',source_tree=TREE,api_calls=0,wall_seconds=None)
    srv=None
    try:
        srv=server_type(working_dir=work,bind_inputs_dir=BASE/'mle-bench-data'/row['task']/'prepared/public',
            superimage_directory=IMAGE.parent,superimage_version='2026-07-macos-v1',startup_timeout=90,
            env={'HF_HUB_OFFLINE':'0','NLTK_DATA':'/root/.nltk_data'})
        client=srv.get_client();kernel=client.start_kernel('python3')
        with client.get_kernel_client(kernel) as k:
            if not k.wait_for_ready(timeout_seconds=120):raise TimeoutError('kernel startup')
            remaining=(deadline-time.monotonic_ns())/1e9
            if remaining<=5:raise TimeoutError('no budget after startup')
            code="import subprocess, sys\nsubprocess.run([sys.executable, 'classic_search_20260914.py', 'search', 'classic-config.json'], check=True)\n"
            answer=k.execute(code,timeout_seconds=remaining+20)
            raw='\n'.join(answer.output).encode()
            if SECRET.search(raw):raise ValueError('credential shaped output')
            with (work/'controller-output.private.log').open('xb') as f:f.write(raw)
            result.update(kernel_ok=bool(answer.is_ok),timed_out=bool(answer.timed_out))
            finished=work/'classic-finished.json'
            if answer.is_ok and not answer.timed_out and finished.is_file():
                f=read(finished)
                if f['task']!=row['task'] or f['seed']!=row['seed'] or f['deadline_ns']!=deadline:raise ValueError('runtime binding')
                result.update(status='completed',attempts=f['attempts'],finished_sha256=sha(finished.read_bytes()))
            else:result['status']='controller_failure_unknown'
    except Exception as exc:result['error_type']=type(exc).__name__
    finally:
        if srv is not None:
            try:srv.stop()
            except Exception as exc:result.update(status='infrastructure_error',cleanup_error=type(exc).__name__)
        result.update(finished_utc=now(),wall_seconds=(time.monotonic_ns()-start)/1e9)
        write(root/f'result-{i}.json',result)
        print(json.dumps(dict(index=i,status=result['status'],wall_seconds=result['wall_seconds'])),flush=True)
    return result


def submit(root):
    p=checked(root);source_check()
    proof=read(root/'preflight.json')
    if proof.get('status')!='PASS' or proof.get('prepared_sha256')!=sha((root/'prepared.json').read_bytes()):raise ValueError('preflight binding')
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    q=subprocess.check_output(['squeue','-u','yzyang4','-h','-o','%i|%T'],env=env,text=True,timeout=25)
    if len(q.strip().splitlines())>=4:raise ValueError('job quota')
    cmd=['sbatch','--parsable','--chdir='+str(root),'--output='+str(root/'allocation-%j.out'),
        '--error='+str(root/'allocation-%j.err'),str(root/'run.sbatch')]
    intent=dict(utc=now(),commit=p['commit'],prepared_sha256=sha((root/'prepared.json').read_bytes()),command=cmd)
    write(root/'submit-intent.json',intent)
    out=subprocess.run(cmd,env=env,capture_output=True,text=True,timeout=25,check=True)
    job=out.stdout.strip().split(';')[0]
    if not job.isdigit():raise ValueError('ambiguous submission: no retry')
    write(root/'launch.json',dict(intent,job=job));print(json.dumps(dict(job=job,root=str(root),runs=8)))


def execute(root):
    p=checked(root);source_check()
    if socket.gethostname().split('.')[0]!='gpu28' or not os.environ.get('SLURM_STEP_ID','').isdigit():raise ValueError('dedicated gpu28 step')
    for _ in range(100):
        if (root/'launch.json').exists():break
        time.sleep(.1)
    launch=read(root/'launch.json')
    if launch['job']!=os.environ['SLURM_JOB_ID'] or launch['prepared_sha256']!=sha((root/'prepared.json').read_bytes()):raise ValueError('launch mismatch')
    write(root/'execution.claim.json',dict(job=launch['job'],utc=now()));setup(root,p)
    from forets_opencl_allowlist_20260911 import IMAGE
    st=IMAGE.stat()
    if (st.st_size,st.st_mtime_ns)!=(19717783552,1784638286000000000):raise ValueError('unchanged task image required')
    started=time.monotonic();done=[];stop='matrix_complete'
    for row in p['rows']:
        if time.monotonic()-started>12500:stop='allocation_deadline';break
        r=execute_one(root,row);done.append(r)
        if r['status']!='completed':stop='infrastructure_stop_no_retry';break
    write(root/'execution-finished.json',dict(utc=now(),planned=8,completed=len(done),stop_reason=stop,
        complete=len(done)==8 and stop=='matrix_complete',job=launch['job'],api_calls=0,seconds=time.monotonic()-started))
    return 0 if stop=='matrix_complete' else 1


if __name__=='__main__':
    os.umask(0o077)
    p=argparse.ArgumentParser();p.add_argument('mode',choices=('prepare','submit','execute'));p.add_argument('--root',type=Path);p.add_argument('--commit');a=p.parse_args()
    if a.mode=='prepare':prepare(a.commit)
    else:
        root=root_check(a.root)
        if a.mode=='execute':raise SystemExit(execute(root))
        submit(root)
