"""Evaluate only unattempted codes from all four closed critic first-draft pools.

Development mechanism completion, not a new end-to-end or held-out effect test.
Never invokes a generator, reranks, edits candidate code, or retries an attempt.
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
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time

BASE=Path('/research/d7/spc/yzyang4')
PARENT=BASE/'forets-wallclock-20260912-cxb9p0og'
SOURCE=PARENT/'source'
TREE='e07cb8c61bca347c61bb8253c84eda826b1add6a'
SUMMARY='a127831408688b545e3d666b790fe1f75b65e82f9324d21c8c4cfc0243d39e90'
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
    if old!=selected or len(old)!=1:raise ValueError('unexpected attempted overlap')
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
    if not re.fullmatch('[a-f0-9]{40}',commit):raise ValueError('exact commit')
    source_check(); raw=safe_bytes(PARENT/'wallclock-summary.json',PARENT)
    receipt=json.loads(safe_bytes(PARENT/'recovery-readout-finished.json',PARENT))
    if sha(raw)!=SUMMARY or receipt['status']!='verified' or receipt['summary_sha256']!=SUMMARY:raise ValueError('parent closure')
    summary=json.loads(raw); first=[];attempted=set();evidence={}
    if len(summary['rows'])!=8 or summary['job']!='13156':raise ValueError('parent matrix')
    for r in summary['rows']:
        cfg=json.loads(safe_bytes(PARENT/'configs'/(r['run_id']+'.json'),PARENT));cp=Path(cfg['solver']['checkpoint_path'])
        for path in sorted((cp/'forets-candidates-private').glob('batch-*.sqlite')):
            d,h=snap(path);evidence[str(path.relative_to(PARENT))]=h
            if d['binding']['task']!=r['task'] or d['binding']['selection_policy']!=r['arm']:raise ValueError('pool binding')
            attempted.update(c['intent']['code_sha256'] for c in d['task_calls'])
            if path.name=='batch-1.sqlite' and r['arm']=='critic_topk_random':first.append((r,cp,d))
    if len(first)!=4 or {(r['task'],r['seed']) for r,_,_ in first}!={(t,s) for t in ('leaf-classification','spaceship-titanic') for s in (24,25)}:raise ValueError('all four first pools')
    root=Path(tempfile.mkdtemp(prefix='forets-pool-completion-20260912-',dir=BASE));os.chmod(root,0o700);(root/'codes').mkdir()
    rows=[];pools=[];unique=set()
    for r,cp,d in first:
        candidates=d['candidates'];rankdir=cp/'forets-contextual-judge-private/batch-1'
        if len(candidates)!=4 or d['binding']['step']!=1:raise ValueError('first draft width')
        hashes=[sha(c['node']['code'].encode()) for c in candidates]
        eligible=unattempted_slots([c['node']['code'] for c in candidates],attempted,d['selected'])
        inp=json.loads(safe_bytes(rankdir/'input.json',PARENT));done=json.loads(safe_bytes(rankdir/'finished.json',PARENT))
        if inp['codes_sha256']!=hashes or done['observed_task_outcomes'] is not False:raise ValueError('frozen rank binding')
        for name in ('input.json','finished.json','rank-0.json','rank-1.json','response-0.json','response-1.json','request-0.json','request-1.json'):
            evidence[str((rankdir/name).relative_to(PARENT))]=sha(safe_bytes(rankdir/name,PARENT))
        omitted=[]
        for slot,c in enumerate(candidates):
            code=c['node']['code'].encode();h=sha(code)
            if SECRET.search(code):raise ValueError('candidate secret')
            if h in unique:raise ValueError('duplicate first-pool code')
            unique.add(h)
            if slot not in eligible:
                omitted.append(slot);continue
            i=len(rows);(root/'codes'/f'{i}.py').write_bytes(code)
            rows.append(dict(index=i,parent_run_id=r['run_id'],task=r['task'],seed=r['seed'],parent_slot=slot,code_sha256=h))
        if omitted!=d['selected'] or len(omitted)!=1:raise ValueError('unexpected attempted overlap')
        pools.append(dict(parent_run_id=r['run_id'],task=r['task'],seed=r['seed'],code_sha256=hashes,
            previously_attempted_slots=omitted,rankings=done['rankings'],borda=done['borda']))
    if len(rows)!=12:raise ValueError('fixed twelve unattempted codes')
    donor=json.loads((ADAPTER/'submit-intent.json').read_bytes())
    for name in HELPERS:
        b=safe_bytes(ADAPTER/name,ADAPTER)
        if sha(b)!=donor['code_sha256'][name]:raise ValueError('adapter drift')
        dest=root/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ADAPTER/name,dest)
    for name in ('forets_pool_completion_20260912.py','forets_pool_completion_20260912.sbatch','forets_closed_pool_20260911.py','FORETS_POOL_COMPLETION_PLAN_20260912.md'):
        shutil.copy2(Path(__file__).with_name(name),root/name)
    (root/'forets_current_pool_20260912.py').write_text('from forets_pool_completion_20260912 import binding_context\n')
    (root/'opencl-vendors').mkdir();(root/'opencl-vendors/nvidia.icd').write_text('libnvidia-opencl.so.1\n')
    files={str(p.relative_to(root)):sha(p.read_bytes()) for p in root.rglob('*') if p.is_file()}
    write(root/'prepared.json',dict(root=str(root),commit=commit,utc=now(),parent_summary_sha256=SUMMARY,
        source_tree=TREE,rows=rows,pools=pools,parent_evidence=evidence,files=files,
        fixed_program_timeout_seconds=300,handshake_timeout_seconds=120,api_calls=0,
        maximum_allocation_gpu_hours=1.5,role='posthoc_frozen_rank_development_completion_not_e2e'))
    print(json.dumps(dict(root=str(root),prepared_sha256=sha((root/'prepared.json').read_bytes()),programs=len(rows))))

def checked(root):
    root=Path(root).resolve(strict=True)
    if root.parent!=BASE or not re.fullmatch('forets-pool-completion-20260912-[A-Za-z0-9_]+',root.name):raise ValueError('root scope')
    p=json.loads((root/'prepared.json').read_bytes())
    if p['root']!=str(root) or p['source_tree']!=TREE or len(p['rows'])!=12:raise ValueError('plan drift')
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
            code_hashes=tuple(x['code_sha256'] for x in p['rows']),order=tuple((i,0) for i in range(12)),
            device_label='original_unedited_candidate_choice',ready_timeout=120)
        done.append(r)
        if r['status']=='infrastructure_error':stop='infrastructure_stop_no_retry';break
    write(root/'execution-finished.json',dict(job=launch['job'],utc=now(),planned=12,completed=len(done),
        stop_reason=stop,complete=len(done)==12 and all(r['status']!='infrastructure_error' for r in done),seconds=time.monotonic()-start))
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
