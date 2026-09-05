"""Bounded one-job engineering controller; no real-data/model readers."""
import argparse
import ast
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

BASE=Path('/research/d7/spc/yzyang4')
REPO=BASE/'aira-dojo'
SOURCE=BASE/'worktrees/critic-g0-final-only-20260903-b'
SOURCE_SHA='5f3bc362db922c8edee2ef134656dfdb9a2b74fb'
RUNTIME=BASE/'venvs/critic-blackwell-g0-20260905-r5'
OUT=BASE/'critic-zero3-engineering/submission-20260905-r2'
APPROVAL='phase1/manifests/zero3_engineering_approval_20260905.json'
SCRIPT='phase1/scripts/zero3_session_engineering_20260905.sbatch'
ENV=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf',GIT_LFS_SKIP_SMUDGE='1',
         PYTHONDONTWRITEBYTECODE='1',CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='1',
         OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
SHAPE=re.compile(rb'(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|Bearer[ \t]+[A-Za-z0-9._-]{20,})')

def require(ok,reason):
    if not ok:raise RuntimeError(reason)

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def run(cmd,*,timeout=120,data=None,env=None,cwd=None):
    p=subprocess.run(list(map(str,cmd)),env=env or ENV,input=data,capture_output=True,timeout=timeout,cwd=cwd)
    require(not SHAPE.search(p.stdout+p.stderr),'credential_shape_withheld')
    if p.returncode:
        if OUT.is_dir():
            stem='failed-'+dt.datetime.now(dt.timezone.utc).strftime('%H%M%S%f')
            (OUT/(stem+'.stdout')).write_bytes(p.stdout);(OUT/(stem+'.stderr')).write_bytes(p.stderr)
        raise RuntimeError('subprocess_failed:'+Path(str(cmd[0])).name)
    return p.stdout

def record(name,obj):
    with (OUT/name).open('x') as f:json.dump(obj,f,sort_keys=True,indent=2);f.write('\n')

def safe_root(p):
    require(p.is_absolute() and p.resolve(strict=True)==p and not any(x.is_symlink() for x in (p,*p.parents)), 'unsafe_root')

def code_files(commit):
    files=set(run(['git','-C',REPO,'ls-tree','-r','--name-only',commit]).decode().splitlines())
    pending=['phase1/global_local_zero3_session.py','phase1/tests/test_global_local_zero3_session.py',
        'phase1/scripts/check_zero3_partition_roundtrip_20260905.py',
        'phase1/scripts/validate_zero3_session_gpu_20260905.py','phase1/tests/test_zero3_gpu_allocation_gate.py',
        'phase1/tests/test_global_local_ds_restore_observer.py','phase1/tests/test_global_local_critic_session.py',
        'phase1/check_g0_r5_build_tools.py']
    seen={APPROVAL,SCRIPT}
    while pending:
        path=pending.pop()
        if path in seen:continue
        source=run(['git','-C',REPO,'show',commit+':'+path]).decode();seen.add(path)
        for node in ast.walk(ast.parse(source)):
            if isinstance(node,ast.ImportFrom):names=[node.module]+[node.module+'.'+n.name for n in node.names] if node.module else []
            elif isinstance(node,ast.Import):names=[a.name for a in node.names]
            else:continue
            for name in names:
                if name and name.startswith('phase1.'):
                    candidate=name.replace('.','/')+'.py'
                    if candidate in files and candidate not in seen:pending.append(candidate)
    for parent in ('phase1/__init__.py','phase1/scripts/__init__.py','phase1/tests/__init__.py'):
        if parent in files:seen.add(parent)
    return sorted(seen)

def bind(control,commit):
    safe_root(control);safe_root(SOURCE)
    require(run(['git','-C',control,'rev-parse','HEAD']).decode().strip()==commit,'control_head')
    require(not run(['git','-C',control,'status','--porcelain','--untracked-files=all']).strip(),'dirty_control')
    require(run(['git','-C',SOURCE,'rev-parse','HEAD']).decode().strip()==SOURCE_SHA and not os.access(SOURCE,os.W_OK),'source_binding')
    require(sha(RUNTIME/'bin/ninja')=='696f9628a79d9ce50314cf9556d7cd1a1d1ec52b8fd52828f6f9db1719565b67','ninja_drift')
    paths=code_files(commit)
    hashes={p:sha(control/p) for p in paths}
    for p in paths:
        require(hashes[p]==hashlib.sha256(run(['git','-C',REPO,'show',commit+':'+p])).hexdigest(),'code_drift')
    approval=json.loads((control/APPROVAL).read_text())
    require(approval['gpu_seconds_upper_bound']==2*(1800+300+60)==4320 and approval['jobs_initial']==1,'budget_binding')
    return hashes

def prepare(control,commit):
    safe_root(BASE)
    parent=OUT.parent
    parent.mkdir(mode=0o700,exist_ok=True);safe_root(parent)
    OUT.mkdir(mode=0o700)
    record('prepare_intent.json',{'commit':commit,'controller_sha256':sha(__file__),'utc':dt.datetime.now(dt.timezone.utc).isoformat()})
    require(not run(['squeue','-h','-u','yzyang4','-o','%i']).strip(),'unknown_queue_do_not_submit')
    run(['git','-C',REPO,'fetch','--no-tags','https://github.com/SuperSumanov/aira-dojo-noise-robust.git',commit],timeout=240)
    files=code_files(commit)
    require(not control.exists(),'control_already_exists')
    run(['git','-C',REPO,'worktree','add','--detach','--no-checkout',control,commit])
    run(['git','-C',control,'sparse-checkout','set','--no-cone','--stdin'],data=('\n'.join('/'+p for p in files)+'\n').encode())
    run(['git','-C',control,'checkout','--detach',commit])
    hashes=bind(control,commit)
    run(['bash','-n',control/SCRIPT])
    run(['/usr/bin/strace','-f','-qq','-e','trace=%file','-o',OUT/'trace-smoke.log','/bin/true'])
    # Real allocation, no sparse-file/free-space fiction; remove only own inode.
    reserve=OUT/'own-storage-check.bin';size=64*1024*1024
    with reserve.open('xb') as f:
        os.posix_fallocate(f.fileno(),0,size);os.fsync(f.fileno());st=os.fstat(f.fileno())
        require(st.st_size==size and st.st_blocks*512>=size,'space_not_reserved')
    require(reserve.stat().st_ino==st.st_ino and reserve.stat().st_nlink==1,'space_inode_changed')
    reserve.unlink()
    record('storage.json',{'reserved_bytes':size,'allocated_bytes':st.st_blocks*512,'own_file_removed':True})
    tests=['test_global_local_zero3_session.py','test_zero3_gpu_allocation_gate.py',
           'test_global_local_ds_restore_observer.py','test_global_local_critic_session.py']
    output=run([BASE/'venvs/exp/bin/python','-B','-m','pytest','-q','-p','no:cacheprovider',
        *['phase1/tests/'+t for t in tests]],cwd=control,timeout=180)
    (OUT/'tests.log').write_bytes(output)
    check="import os,json,torch; from phase1.scripts.validate_global_local_critic_consumer_20260905 import fixture; from phase1.global_local_zero3_session import runtime_binding; assert os.environ['CUDA_VISIBLE_DEVICES']=='0,1'; b=runtime_binding(); assert not torch.cuda.is_initialized(); print(json.dumps({'runtime':b,'imports_preserve_allocation':True,'gpu_context_created':False},sort_keys=True))"
    import_env=dict(ENV,PYTHONPATH=str(control),CUDA_VISIBLE_DEVICES='0,1')
    (OUT/'runtime.json').write_bytes(run([RUNTIME/'bin/python','-B','-c',check],cwd=OUT,env=import_env,timeout=180))
    require(bind(control,commit)==hashes,'end_prepare_drift')
    record('READY.json',{'commit':commit,'control':str(control),'hashes':hashes,'approval_sha256':hashes[APPROVAL],
                        'gpu_seconds_upper_bound':4320,'status':'READY_NOT_SUBMITTED'})
    print(json.dumps({'status':'READY_NOT_SUBMITTED','code_commit':commit,'files':len(hashes),'approval_sha256':hashes[APPROVAL]}))

def submit(control,commit):
    ready=json.loads((OUT/'READY.json').read_text())
    require(ready['commit']==commit and bind(control,commit)==ready['hashes'],'ready_drift')
    require(not run(['squeue','-h','-u','yzyang4','-o','%i']).strip(),'unexpected_queue')
    record('SUBMISSION_INTENT.json',{'commit':commit,'max_jobs':1,'gpu_seconds_upper_bound':4320,'retry':False})
    export=','.join(['PATH=/usr/local/bin:/usr/bin:/bin',f'ZERO3_CONTROL_ROOT={control}',f'ZERO3_CODE_COMMIT={commit}',
                     'ZERO3_GPU_APPROVAL_RECEIPT_SHA='+ready['approval_sha256']])
    command=['sbatch','--parsable','--hold','--no-requeue','--time=00:30:00',f'--chdir={control}',
        f'--output={OUT}/slurm-%j.out',f'--error={OUT}/slurm-%j.out',f'--export={export}',str(control/SCRIPT)]
    record('command.json',command)
    p=subprocess.run(command,env=ENV,capture_output=True,timeout=60)
    (OUT/'sbatch.stdout').write_bytes(p.stdout);(OUT/'sbatch.stderr').write_bytes(p.stderr)
    record('sbatch_status.json',{'returncode':p.returncode})
    require(p.returncode==0,'submit_failed_never_retry_blindly')
    jid=p.stdout.decode().strip().split(';')[0]
    require(re.fullmatch('[0-9]+',jid),'unknown_submit_result')
    record('SUBMITTED.json',{'job_id':jid,'commit':commit})
    print(json.dumps({'status':'SUBMITTED_HELD','job_id':jid}))

def release(control,commit):
    ready=json.loads((OUT/'READY.json').read_text());sub=json.loads((OUT/'SUBMITTED.json').read_text());jid=sub['job_id']
    require(sub['commit']==ready['commit']==commit and bind(control,commit)==ready['hashes'],'release_binding')
    require(run(['squeue','-h','-u','yzyang4','-o','%i']).decode().split()==[jid],'unexpected_queue')
    raw=run(['scontrol','show','job','-o',jid]);fields=dict(p.split('=',1) for p in raw.decode().split() if '=' in p)
    exact={'JobId':jid,'JobState':'PENDING','Reason':'JobHeldUser','RunTime':'00:00:00','TimeLimit':'00:30:00',
        'Requeue':'0','Restarts':'0','NumCPUs':'12','CPUs/Task':'12','MinMemoryNode':'0',
        'ReqNodeList':'projgpu39','Partition':'gpu_24h','QOS':'gpu','NumNodes':'1'}
    require(all(fields.get(k)==v for k,v in exact.items()),'held_resource_mismatch')
    require('gres/gpu=2' in fields.get('TRES','').split(','),'held_gpu_mismatch')
    record('VERIFIED_HELD.json',{'fields':fields,'gpu_seconds_upper_bound':4320})
    run(['scontrol','release',jid])
    record('RELEASED.json',{'job_id':jid,'commit':commit,'utc':dt.datetime.now(dt.timezone.utc).isoformat()})
    print(json.dumps({'status':'RELEASED','job_id':jid,'gpu_seconds_upper_bound':4320}))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','submit','release'])
    parser.add_argument('--commit',required=True);args=parser.parse_args()
    require(re.fullmatch('[0-9a-f]{40}',args.commit),'bad_commit');os.umask(0o077)
    control=BASE/'worktrees'/('zero3-engineering-'+args.commit[:12])
    try:globals()[args.action](control,args.commit)
    except Exception as exc:
        print(json.dumps({'status':'FAILED_CLOSED','reason':str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__}))
        raise SystemExit(1)
