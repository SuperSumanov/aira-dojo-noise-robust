"""One separately bounded portability job. Existing12535 is untouched."""
import argparse
import hashlib
import json
import os
import re
import subprocess
from phase1.scripts import prepare_zero3_engineering_20260905 as c

c.OUT=c.BASE/'critic-zero3-engineering/submission-20260906-3090-private'
c.APPROVAL='phase1/manifests/zero3_3090_private_approval_20260906.json'
c.SCRIPT='phase1/scripts/zero3_3090_private_20260906.sbatch'
CAP=2880


def files(commit):
    return sorted(set(c.code_files(commit))|{
        'phase1/scripts/prepare_zero3_3090_private_20260906.py','phase1/scripts/prepare_zero3_engineering_20260905.py',
        'phase1/scripts/validate_zero3_3090_20260906.py','phase1/scripts/check_zero3_private_tools_20260906.py',
        'phase1/scripts/verify_zero3_engineering_20260905.py','phase1/tests/test_verify_zero3_engineering.py',
        'phase1/scripts/verify_private_cuda128_20260906.py','phase1/tests/test_zero3_private_toolchain_binding.py'})


def queue(own=None):
    rows=c.run(['squeue','-h','-u','yzyang4','-o','%i']).decode().split()
    c.require(len(rows)==len(set(rows)) and set(rows).issubset({'12535'}|({own} if own else set())),'unknown_queue')
    if '12535' in rows:
        raw=c.run(['scontrol','show','job','-o','12535'])
        f=dict(x.split('=',1) for x in raw.decode().split() if '=' in x)
        c.require(f['TresPerNode']=='gpu:pro6000:2' and f['ReqNodeList']=='projgpu39'
            and f['TimeLimit']=='00:26:00' and f['Requeue']=='0','existing_job_changed')


def prior_and_toolchain(control):
    for job,expected in [('12570',('FAILED','1','1:0',2)),('12571',('COMPLETED','5','0:0',1))]:
        row=c.run(['sacct','-X','-n','-P','-j',job,'--format=JobIDRaw,State,ElapsedRaw,AllocTRES,ExitCode']).decode().strip().split('|')
        state,elapsed,code,gpus=expected
        c.require(row[0:3]==[job,state,elapsed] and row[4]==code and f'gres/gpu={gpus}' in row[3].split(','),'prior_gpu_accounting_drift')
    toolkit=c.BASE/'private-cuda128-toolchain-20260906'
    c.require(c.sha(toolkit/'RECOVERY_COMPLETE.json')=='8701d0fc275c5c0f7a124d05e622bbe0a1e7f5313b7260911000326808b5730a','toolkit_recovery_drift')
    c.require(c.sha(toolkit/'INDEPENDENT_VERIFIED.json')=='6732f4045503fb658cce9a0fbf7c449985ecee41f01886d3e4f2a704463dd2fe','toolkit_verification_drift')
    c.require(c.sha(toolkit/'installed_manifest.json')=='ce7f9f18218799db0776d08a2c3e2342e51273bcaccae61c1ebab8e340e959f1','toolkit_manifest_drift')


def bind(control,commit):
    prior_and_toolchain(control)
    c.safe_root(control);c.safe_root(c.SOURCE)
    c.require(c.run(['git','-C',control,'rev-parse','HEAD']).decode().strip()==commit,'control_head')
    c.require(not c.run(['git','-C',control,'status','--porcelain','--untracked-files=all']).strip(),'dirty_control')
    c.require(c.run(['git','-C',c.SOURCE,'rev-parse','HEAD']).decode().strip()==c.SOURCE_SHA
              and not os.access(c.SOURCE,os.W_OK),'source_binding')
    hashes={p:c.sha(control/p) for p in files(commit)}
    for p,h in hashes.items():
        c.require(h==hashlib.sha256(c.run(['git','-C',c.REPO,'show',commit+':'+p])).hexdigest(),'code_drift')
    a=json.loads((control/c.APPROVAL).read_text())
    c.require(a['gpu_seconds_upper_bound']==CAP==2*(1080+300+60) and a['jobs_initial']==1
        and a['automatic_retries']==0 and a['node']=='gpu28' and a['gpu_model']=='RTX 3090'
        and a['prior_actual_gpu_seconds']==7 and a['aggregate_cap_gpu_seconds']==3120
        and a['aggregate_conservative_upper_bound']==3062<=3120,'approval_binding')
    c.require(c.sha(c.RUNTIME/'bin/ninja')=='696f9628a79d9ce50314cf9556d7cd1a1d1ec52b8fd52828f6f9db1719565b67','ninja_drift')
    return hashes


def prepare(control,commit):
    queue();c.safe_root(c.BASE);c.safe_root(c.OUT.parent);c.OUT.mkdir(mode=0o700)
    c.record('prepare_intent.json',{'commit':commit,'controller_sha256':c.sha(__file__),'separate_cap':CAP})
    c.run(['git','-C',c.REPO,'fetch','--no-tags','https://github.com/SuperSumanov/aira-dojo-noise-robust.git',commit],timeout=240)
    c.require(not control.exists(),'control_exists')
    c.run(['git','-C',c.REPO,'worktree','add','--detach','--no-checkout',control,commit])
    c.run(['git','-C',control,'sparse-checkout','set','--no-cone','--stdin'],data=('\n'.join('/'+p for p in files(commit))+'\n').encode())
    c.run(['git','-C',control,'checkout','--detach',commit]);hashes=bind(control,commit)
    c.run(['bash','-n',control/c.SCRIPT])
    c.run(['/usr/bin/strace','-f','-qq','-e','trace=%file','-o',c.OUT/'trace-smoke.log','/bin/true'])
    reserve=c.OUT/'own-storage-check.bin';size=64*1024*1024
    with reserve.open('xb') as f:
        os.posix_fallocate(f.fileno(),0,size);os.fsync(f.fileno());st=os.fstat(f.fileno())
        c.require(st.st_size==size and st.st_blocks*512>=size,'space_not_reserved')
    c.require(reserve.stat().st_ino==st.st_ino and reserve.stat().st_nlink==1,'reserve_changed');reserve.unlink()
    c.record('storage.json',{'requested_bytes':size,'allocated_bytes':st.st_blocks*512,'own_file_removed':True})
    tests=['test_global_local_zero3_session','test_zero3_gpu_allocation_gate',
           'test_global_local_ds_restore_observer','test_global_local_critic_session','test_verify_zero3_engineering','test_zero3_private_toolchain_binding']
    out=c.run([c.BASE/'venvs/exp/bin/python','-B','-m','pytest','-q','-p','no:cacheprovider',
               *['phase1/tests/'+t+'.py' for t in tests]],cwd=control,timeout=240)
    (c.OUT/'cpu-tests.log').write_bytes(out)
    check="import os,json,torch; from phase1.scripts.validate_global_local_critic_consumer_20260905 import fixture; from phase1.global_local_zero3_session import runtime_binding; assert os.environ['CUDA_VISIBLE_DEVICES']=='0,1'; b=runtime_binding(); assert not torch.cuda.is_initialized(); print(json.dumps({'runtime':b,'gpu_context_created':False},sort_keys=True))"
    (c.OUT/'runtime.json').write_bytes(c.run([c.RUNTIME/'bin/python','-B','-c',check],cwd=c.OUT,
        env=dict(c.ENV,PYTHONPATH=str(control),CUDA_VISIBLE_DEVICES='0,1'),timeout=180))
    c.require(bind(control,commit)==hashes,'end_prepare_drift')
    c.record('READY.json',{'commit':commit,'control':str(control),'hashes':hashes,
        'approval_sha256':hashes[c.APPROVAL],'gpu_seconds_upper_bound':CAP,'status':'READY_NOT_SUBMITTED'})
    print(json.dumps({'status':'READY_NOT_SUBMITTED','commit':commit,'files':len(hashes),'cap_gpu_seconds':CAP}))


def ready(control,commit):
    r=json.loads((c.OUT/'READY.json').read_text())
    c.require(r['commit']==commit and r['hashes']==bind(control,commit),'ready_drift')
    return r


def submit(control,commit):
    r=ready(control,commit);queue()
    c.record('SUBMISSION_INTENT.json',{'commit':commit,'max_new_jobs':1,'separate_gpu_seconds_upper_bound':CAP,'automatic_retries':0})
    export=','.join(['PATH=/usr/local/bin:/usr/bin:/bin',f'ZERO3_CONTROL_ROOT={control}',f'ZERO3_CODE_COMMIT={commit}',
                     'ZERO3_GPU_APPROVAL_RECEIPT_SHA='+r['approval_sha256']])
    command=['sbatch','--parsable','--hold','--no-requeue',f'--chdir={control}',
        f'--output={c.OUT}/slurm-%j.out',f'--error={c.OUT}/slurm-%j.out',f'--export={export}',str(control/c.SCRIPT)]
    c.record('command.json',command)
    p=subprocess.run(command,env=c.ENV,capture_output=True,timeout=60)
    c.require(not c.SHAPE.search(p.stdout+p.stderr),'output_withheld')
    (c.OUT/'sbatch.stdout').write_bytes(p.stdout);(c.OUT/'sbatch.stderr').write_bytes(p.stderr)
    c.record('sbatch_status.json',{'returncode':p.returncode})
    c.require(p.returncode==0,'submit_failed_never_retry_blindly')
    jid=p.stdout.decode().strip().split(';')[0];c.require(re.fullmatch('[0-9]+',jid),'unknown_submission')
    c.record('SUBMITTED.json',{'job_id':jid,'commit':commit});print(json.dumps({'status':'HELD','job_id':jid}))


def release(control,commit):
    ready(control,commit);sub=json.loads((c.OUT/'SUBMITTED.json').read_text());jid=sub['job_id'];queue(jid)
    c.require(sub['commit']==commit,'submitted_commit')
    raw=c.run(['scontrol','show','job','-o',jid]);f=dict(x.split('=',1) for x in raw.decode().split() if '=' in x)
    expected={'JobId':jid,'JobState':'PENDING','Reason':'JobHeldUser','RunTime':'00:00:00','TimeLimit':'00:18:00',
        'Requeue':'0','Restarts':'0','NumCPUs':'12','CPUs/Task':'12','MinMemoryNode':'0','NumTasks':'1',
        'ReqNodeList':'gpu28','Partition':'gpu_24h','QOS':'gpu','TresPerNode':'gpu:rtx3090:2',
        'Command':str(control/c.SCRIPT),'WorkDir':str(control)}
    c.require(all(f.get(k)==v for k,v in expected.items()),'held_mismatch')
    c.require(f.get('NumNodes') in ('1','1-1') and {'node=1','gres/gpu=2'}.issubset(f.get('TRES','').split(',')),'held_tres')
    c.record('VERIFIED_HELD.json',{'fields':f,'separate_gpu_seconds_upper_bound':CAP})
    c.run(['scontrol','release',jid]);c.record('RELEASED.json',sub)
    print(json.dumps({'status':'RELEASED','job_id':jid,'separate_cap_gpu_seconds':CAP}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','submit','release']);p.add_argument('--commit',required=True)
    args=p.parse_args();c.require(re.fullmatch('[0-9a-f]{40}',args.commit),'commit');os.umask(0o077)
    control=c.BASE/'worktrees'/('zero3-3090-private-'+args.commit[:12])
    try:globals()[args.action](control,args.commit)
    except Exception as exc:
        print(json.dumps({'status':'FAILED_CLOSED','reason':str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__}))
        raise SystemExit(1)
