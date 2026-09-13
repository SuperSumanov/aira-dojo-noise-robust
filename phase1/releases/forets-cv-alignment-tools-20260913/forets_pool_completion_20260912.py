import argparse
import datetime as dt
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time

BASE=Path('/research/d7/spc/yzyang4')
PARENT=BASE/'forets-wallclock-20260912-5_czzimk'
SOURCE=PARENT/'source'
TREE='f1cdee3a9e553e8efeedaa1a66a2c6bd778f9798'
SUMMARY='4d89d47dd47877c04ceebeb24adc6a7773f13cfbe3bdc65517eef878b933d11e'
ADAPTER=BASE/'forets-current-pool-20260912-0hz06xtj'
HELPERS=('forets_closed_pool_native_20260911.py','forets_current_pool_native_20260912.py',
    'forets_gpu_binding_20260911.py','forets_native_cuda_identity_20260911.py',
    'forets_native_gpu_binding_20260911.py','forets_opencl_allowlist_20260911.py',
    'forets_opencl_readonly_ab.py','bin/singularity')
SECRET=re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{16,}|gh[pousr]_[a-z0-9]{16,}|github_pat_[a-z0-9_]{20,}|AKIA[0-9A-Z]{16}|Bearer\s+[a-z0-9_.-]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')

def sha(b):return hashlib.sha256(b).hexdigest()
def now():return dt.datetime.now(dt.timezone.utc).isoformat()
def unattempted_slots(codes,attempted,selected):
    hashes=[sha(c.encode()) for c in codes]
    if len(codes)!=4 or len(set(hashes))!=4:raise ValueError('four distinct candidates required')
    old=[i for i,h in enumerate(hashes) if h in attempted]
    if len(selected)!=2 or not set(old).issubset(selected) or len(old) not in (1,2):raise ValueError('unexpected attempted overlap')
    return [i for i,h in enumerate(hashes) if h not in attempted]
def write(p,d):
    with p.open('x') as f:json.dump(d,f,indent=2,allow_nan=False)
def safe_bytes(p,base):
    p=Path(p)
    if p.is_symlink() or not p.resolve(strict=True).is_relative_to(base.resolve(strict=True)):raise ValueError('path scope')
    b=p.read_bytes()
    if SECRET.search(b):raise ValueError('credential shape; no export')
    return b
def snap(p):
    before=sha(safe_bytes(p,PARENT))
    with sqlite3.connect(p.as_uri()+'?mode=ro',uri=True) as db:values=db.execute('SELECT payload,sha256 FROM snapshot WHERE id=1').fetchall()
    if len(values)!=1 or sha(values[0][0].encode())!=values[0][1] or sha(p.read_bytes())!=before:raise ValueError('snapshot drift')
    return json.loads(values[0][0]),before
def source_check():
    artifact=json.loads((PARENT/'artifact.json').read_bytes())
    if artifact['source_tree']!=TREE:raise ValueError('source tree')
    for name,h in artifact['source_files'].items():
        if sha((SOURCE/name).read_bytes())!=h:raise ValueError('source drift')

def prepare(commit):
    from forets_cv_alignment_contract_20260913 import prepare as diagnostic_prepare
    diagnostic_prepare(commit,globals())


def checked(root):
    root=Path(root).resolve(strict=True)
    if root.parent!=BASE or not re.fullmatch('forets-pool-completion-20260912-[A-Za-z0-9_]+',root.name):raise ValueError('root scope')
    p=json.loads((root/'prepared.json').read_bytes())
    if p['root']!=str(root) or p['source_tree']!=TREE or len(p['rows'])!=1:raise ValueError('plan drift')
    for n,h in p['files'].items():
        if sha((root/n).read_bytes())!=h:raise ValueError('code/file drift')
    return root,p

def binding_context(env):
    root,p=checked(env['FORETS_CURRENT_POOL_ROOT']);identity=Path(env['DOJO_WORKER_IDENTITY_PATH'])
    if identity.parent!=root or identity.is_symlink() or not re.fullmatch('identity-(?:[0-9]|1[01])\\.json',identity.name):raise ValueError('identity scope')
    if env.get('FORETS_NATIVE_RELEASE') or env.get('FORETS_CLOSED_POOL_ROOT'):raise ValueError('ambiguous execution mode')
    if json.loads((root/'execution.claim.json').read_bytes())['job']!=env['SLURM_JOB_ID']:raise ValueError('job binding')
    return identity.with_suffix('.native-binding.json')

def execute(root):
    root,p=checked(root);source_check()
    if socket.gethostname().split('.')[0]!='gpu28' or not os.environ.get('SLURM_STEP_ID','').isdigit():raise ValueError('dedicated gpu28 step')
    end=time.monotonic()+10
    while not (root/'launch.json').exists() and time.monotonic()<end:time.sleep(.1)
    launch=json.loads((root/'launch.json').read_bytes())
    if launch['job']!=os.environ['SLURM_JOB_ID'] or launch['commit']!=p['commit'] or launch['prepared_sha256']!=sha((root/'prepared.json').read_bytes()):raise ValueError('launch binding')
    for n,h in p['parent_evidence'].items():
        if sha((PARENT/n).read_bytes())!=h:raise ValueError('closed parent changed')
    write(root/'execution.claim.json',dict(job=launch['job'],utc=now()))
    logging.disable(logging.CRITICAL)
    for name in ('FORETS_NATIVE_RELEASE','FORETS_CLOSED_POOL_ROOT'):os.environ.pop(name,None)
    os.environ.update(PYTHON_DOTENV_DISABLED='1',PYTHONDONTWRITEBYTECODE='1',LOGGING_DIR=str(root),
        SUPERIMAGE_DIR=str(BASE/'aira-dojo/build/superimage'),MLE_BENCH_DATA_DIR=str(BASE/'mle-bench-data'),
        DEFAULT_SLURM_PARTITION='gpu_24h',DEFAULT_SLURM_ACCOUNT='gpu',DEFAULT_SLURM_QOS='gpu',
        FORETS_SOURCE_COMMIT=p['commit'],FORETS_CURRENT_POOL_ROOT=str(root),PATH=str(root/'bin')+':'+os.environ['PATH'],
        NO_PROXY='localhost,127.0.0.1,0.0.0.0')
    sys.path[:0]=[str(root),str(SOURCE/'src')]
    from forets_closed_pool_20260911 import execute_one
    from forets_opencl_allowlist_20260911 import IMAGE
    st=IMAGE.stat()
    if (st.st_size,st.st_mtime_ns)!=(19717783552,1784638286000000000):raise ValueError('image changed')
    start=time.monotonic();done=[];stop='matrix_complete'
    for item in p['rows']:
        if time.monotonic()-start>4600:stop='bounded_time_stop';break
        r=execute_one(root,item['index'],task=item['task'],seed=item['seed'],source_tree=TREE,
            code_hashes=tuple(x['code_sha256'] for x in p['rows']),order=tuple((i,0) for i in range(1)),
            device_label='same_fit_cv_alignment_diagnostic',ready_timeout=120)
        done.append(r)
        if r['status']=='infrastructure_error':stop='infrastructure_stop_no_retry';break
    write(root/'execution-finished.json',dict(job=launch['job'],utc=now(),planned=1,completed=len(done),
        stop_reason=stop,complete=len(done)==1 and all(r['status']!='infrastructure_error' for r in done),seconds=time.monotonic()-start))
    return 0 if stop=='matrix_complete' else 1

def submit(root,commit):
    root,p=checked(root);source_check()
    if p['commit']!=commit or any((root/n).exists() for n in ('submit-intent.json','launch.json','execution.claim.json')):raise ValueError('no repeat submit')
    env={**os.environ,'SLURM_CONF':'/opt1/slurm/gpu-slurm.conf'}
    q=subprocess.check_output(['squeue','-u','yzyang4','-h','-o','%i %T %j'],env=env,text=True,timeout=25)
    if 'forets-pool-completion' in q:raise ValueError('matching job exists')
    command=['sbatch','--parsable','--chdir='+str(root),'--output='+str(root/'allocation-%j.out'),
        '--error='+str(root/'allocation-%j.err'),str(root/'forets_pool_completion_20260912.sbatch'),str(root)]
    receipt=dict(commit=commit,utc=now(),prepared_sha256=sha((root/'prepared.json').read_bytes()),command=command)
    write(root/'submit-intent.json',receipt)
    r=subprocess.run(command,env=env,capture_output=True,text=True,timeout=25,check=True)
    job=r.stdout.strip().split(';')[0]
    if not job.isdigit():raise ValueError('ambiguous submit; no retry')
    receipt['job']=job;write(root/'launch.json',receipt);print(json.dumps(receipt))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=('prepare','execute','submit'))
    parser.add_argument('--root',type=Path);parser.add_argument('--commit');a=parser.parse_args()
    if a.mode=='prepare':prepare(a.commit)
    elif a.mode=='submit':submit(a.root,a.commit)
    else:raise SystemExit(execute(a.root))
