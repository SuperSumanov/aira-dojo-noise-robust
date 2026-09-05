"""One bounded same-scope repair after terminal 12510; no effect training."""
import argparse
import datetime as dt
import json
import os
import re
import subprocess

from phase1.scripts import prepare_zero3_engineering_20260905 as c

c.OUT=c.BASE/'critic-zero3-engineering/submission-20260905-r3'
WALL=1560
TOTAL=4320
PREVIOUS='12510'
CHECK='phase1/scripts/check_zero3_initial_padding_20260905.py'
CONTROLLER='phase1/scripts/prepare_zero3_padding_retry_20260905.py'
old_files=c.code_files


def files(commit):
    return sorted(set(old_files(commit)) | {CHECK,CONTROLLER,'phase1/scripts/prepare_zero3_engineering_20260905.py'})


c.code_files=files


def ledger():
    raw=c.run(['sacct','-X','-n','-P','-j',PREVIOUS,
        '--format=JobIDRaw,State,ElapsedRaw,AllocTRES,ExitCode'])
    rows=[line.split('|') for line in raw.decode().splitlines() if line.strip()]
    c.require(len(rows)==1,'unexpected_accounting_rows')
    jid,state,elapsed,tres,exitcode=rows[0][:5]
    resources=dict(x.split('=',1) for x in tres.split(','))
    c.require(jid==PREVIOUS and state=='FAILED' and exitcode=='1:0'
              and elapsed=='149' and resources.get('gres/gpu')=='2','previous_terminal_drift')
    used=int(elapsed)*int(resources['gres/gpu'])
    reserved=2*(WALL+300+60)
    c.require(used+reserved<=TOTAL,'cumulative_budget_exceeded')
    return {'previous_job_id':jid,'previous_state':state,'previous_exit':exitcode,
            'previous_elapsed_seconds':int(elapsed),'previous_allocated_gpu_seconds':used,
            'retry_walltime_seconds':WALL,'retry_gpu_seconds_upper_bound':reserved,
            'cumulative_gpu_seconds_upper_bound':used+reserved,'original_cap_gpu_seconds':TOTAL,
            'remaining_after_worst_case':TOTAL-used-reserved}


def prepare(control,commit):
    budget=ledger()
    c.prepare(control,commit)
    reserve=c.OUT/'own-retry-storage-check.bin'
    size=1 << 30
    with reserve.open('xb') as f:
        os.posix_fallocate(f.fileno(),0,size);os.fsync(f.fileno());st=os.fstat(f.fileno())
    c.require(st.st_size==size and st.st_blocks*512>=size and reserve.stat().st_ino==st.st_ino
              and reserve.stat().st_nlink==1,'retry_storage_check')
    reserve.unlink()
    c.record('retry_storage.json',{'allocated_bytes':st.st_blocks*512,'requested_bytes':size,
                                 'own_file_removed':True,'not_a_future_space_guarantee':True})
    # Actual pinned partition code with CPU receiver and strict negative controls,
    # twice in fresh processes. Not counted as real-engine/GPU acceptance.
    env=dict(c.ENV,PYTHONPATH=str(control),TRITON_CACHE_DIR=str(c.OUT/'triton'))
    for suffix in ('A','B'):
        output=c.run([c.RUNTIME/'bin/python','-B','-m',CHECK[:-3].replace('/','.')],
                     cwd=control,env=env,timeout=240)
        (c.OUT/('padding_cpu_'+suffix+'.log')).write_bytes(output)
        rows=[json.loads(line) for line in output.decode().splitlines() if line.startswith('{')]
        c.require(len(rows)==1 and len(rows[0]['cases'])==8
                  and rows[0]['real_nan_negative_controls']==2
                  and rows[0]['gpu_initialized'] is False,'padding_cpu_check')
        if suffix=='A':reference=rows[0]
        else:c.require(rows[0]==reference,'padding_cpu_AB_mismatch')
    c.require(ledger()==budget,'ledger_changed')
    ready=json.loads((c.OUT/'READY.json').read_text())
    c.require(c.bind(control,commit)==ready['hashes'],'post_cpu_code_drift')
    c.record('RETRY_READY.json',{'commit':commit,'budget':budget,'ready_sha256':c.sha(c.OUT/'READY.json'),
                              'controller_sha256':c.sha(__file__),'cpu_AB_equal':True})
    print(json.dumps({'status':'RETRY_READY_NOT_SUBMITTED','budget':budget},sort_keys=True))


def binding(control,commit):
    rr=json.loads((c.OUT/'RETRY_READY.json').read_text())
    ready=json.loads((c.OUT/'READY.json').read_text())
    c.require(rr['commit']==ready['commit']==commit and rr['budget']==ledger()
              and rr['ready_sha256']==c.sha(c.OUT/'READY.json')
              and rr['controller_sha256']==c.sha(__file__)
              and ready['hashes']==c.bind(control,commit),'retry_binding_changed')
    return ready,rr


def submit(control,commit):
    ready,rr=binding(control,commit)
    c.require(not c.run(['squeue','-h','-u','yzyang4','-o','%i']).strip(),'unexpected_queue')
    c.record('SUBMISSION_INTENT.json',{'commit':commit,'budget':rr['budget'],'retry_of':PREVIOUS,'max_new_jobs':1})
    export=','.join(['PATH=/usr/local/bin:/usr/bin:/bin',f'ZERO3_CONTROL_ROOT={control}',f'ZERO3_CODE_COMMIT={commit}',
                     'ZERO3_GPU_APPROVAL_RECEIPT_SHA='+ready['approval_sha256']])
    command=['sbatch','--parsable','--hold','--no-requeue','--time=00:26:00',f'--chdir={control}',
        f'--output={c.OUT}/slurm-%j.out',f'--error={c.OUT}/slurm-%j.out',f'--export={export}',str(control/c.SCRIPT)]
    c.record('command.json',command)
    p=subprocess.run(command,env=c.ENV,capture_output=True,timeout=60)
    c.require(not c.SHAPE.search(p.stdout+p.stderr),'submission_output_withheld')
    (c.OUT/'sbatch.stdout').write_bytes(p.stdout);(c.OUT/'sbatch.stderr').write_bytes(p.stderr)
    c.record('sbatch_status.json',{'returncode':p.returncode})
    c.require(p.returncode==0,'submit_failed_no_blind_retry')
    jid=p.stdout.decode().strip().split(';')[0]
    c.require(re.fullmatch('[0-9]+',jid),'unknown_submit_result')
    c.record('SUBMITTED.json',{'job_id':jid,'commit':commit})
    print(json.dumps({'status':'SUBMITTED_HELD','job_id':jid,'budget':rr['budget']}))


def release(control,commit):
    ready,rr=binding(control,commit)
    sub=json.loads((c.OUT/'SUBMITTED.json').read_text());jid=sub['job_id']
    c.require(sub['commit']==commit,'submitted_commit_mismatch')
    c.require(c.run(['squeue','-h','-u','yzyang4','-o','%i']).decode().split()==[jid],'unexpected_queue')
    raw=c.run(['scontrol','show','job','-o',jid])
    fields=dict(p.split('=',1) for p in raw.decode().split() if '=' in p)
    exact={'JobId':jid,'JobState':'PENDING','Reason':'JobHeldUser','RunTime':'00:00:00','TimeLimit':'00:26:00',
        'Requeue':'0','Restarts':'0','NumCPUs':'12','CPUs/Task':'12','MinMemoryNode':'0',
        'ReqNodeList':'projgpu39','Partition':'gpu_24h','QOS':'gpu','NumTasks':'1',
        'TresPerNode':'gpu:pro6000:2','Command':str(control/c.SCRIPT),'WorkDir':str(control)}
    c.require(all(fields.get(k)==v for k,v in exact.items()),'held_resource_mismatch')
    c.require(fields.get('NumNodes') in ('1','1-1') and 'node=1' in fields.get('TRES','').split(',')
              and 'gres/gpu=2' in fields.get('TRES','').split(','),'held_gpu_node_mismatch')
    c.record('VERIFIED_HELD.json',{'fields':fields,'budget':rr['budget']})
    c.run(['scontrol','release',jid])
    c.record('RELEASED.json',{'job_id':jid,'commit':commit,'utc':dt.datetime.now(dt.timezone.utc).isoformat()})
    print(json.dumps({'status':'RELEASED','job_id':jid,'budget':rr['budget']}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','submit','release'])
    parser.add_argument('--commit',required=True);args=parser.parse_args()
    c.require(re.fullmatch('[0-9a-f]{40}',args.commit),'bad_commit');os.umask(0o077)
    control=c.BASE/'worktrees'/('zero3-engineering-'+args.commit[:12])
    try:globals()[args.action](control,args.commit)
    except Exception as exc:
        print(json.dumps({'status':'FAILED_CLOSED','reason':str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__}))
        raise SystemExit(1)
