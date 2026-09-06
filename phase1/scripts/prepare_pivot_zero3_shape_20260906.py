"""One bounded, synthetic-only pivot-size job; real source registry stays empty."""
import argparse,ast,hashlib,json,os,re,subprocess
from pathlib import Path
from phase1.scripts import prepare_zero3_engineering_20260905 as c

c.OUT=c.BASE/'critic-pivot-shape/submission-20260906-capacity-recovered'
PREVIOUS_OUT=c.BASE/'critic-pivot-shape/submission-20260906'
PREVIOUS_COMMIT='ef19d100ac6cb1a747c332eb1b8596051f47a695'
CLEANUP_RECEIPT=c.BASE/'storage-cleanup-receipts-20260906/SUMMARY.json'
CLEANUP_SHA='b5cd4dd02f8c5418106bbc0966371496b1d937e1bc5be04734f3df75bf3d9564'
SCRIPT='phase1/scripts/pivot_zero3_shape_20260906.sbatch'
APPROVAL='phase1/manifests/pivot_zero3_shape_approval_20260906.json'
MANIFEST='phase1/manifests/qwen3-1.7b-base-ea980cb0a6c2ae4b936e82123acc929f1cec04c1.sha256'
TESTS=['test_pivot_zero3_shape_fixture','test_pivot_checkpoint_space','test_pivot_shape_profile',
    'test_critic_training_entry','test_critic_training_definition','test_critic_training_worker',
    'test_global_local_zero3_session','test_cpu_adam_native_cache','test_zero3_consumed_gradients']
PRIOR=[('12181','FAILED',156,2),('12288','FAILED',4,2),('12377','FAILED',131,2),('12486','FAILED',191,2),
    ('12497','COMPLETED',1,1),('12499','COMPLETED',2192,2),('12510','FAILED',149,2),
    ('12570','FAILED',1,2),('12571','COMPLETED',5,1),('12572','FAILED',73,2),('12573','FAILED',133,2),
    ('12574','FAILED',199,2),('12575','COMPLETED',271,2)]
CAP=3840
TINY_SHA='14dae4dbc7e1497695d1081517a1603833f4a6f97bd8ac3d534b5e0debdffaa2'


def files(commit):
    tracked=set(c.run(['git','-C',c.REPO,'ls-tree','-r','--name-only',commit]).decode().splitlines())
    pending=['phase1/scripts/prepare_pivot_zero3_shape_20260906.py','phase1/scripts/validate_pivot_zero3_shape_20260906.py',
        'phase1/critic_offline_setup.py','phase1/critic_training_run.py','phase1/pivot_checkpoint_space.py',
        'phase1/check_g0_r5_build_tools.py',*['phase1/tests/'+n+'.py' for n in TESTS]]
    seen={SCRIPT,APPROVAL,MANIFEST}
    while pending:
        path=pending.pop()
        if path in seen:continue
        raw=c.run(['git','-C',c.REPO,'show',commit+':'+path]);seen.add(path)
        for node in ast.walk(ast.parse(raw)):
            if isinstance(node,ast.ImportFrom):names=[node.module]+[node.module+'.'+x.name for x in node.names] if node.module else []
            elif isinstance(node,ast.Import):names=[x.name for x in node.names]
            else:continue
            for name in names:
                p=(name or '').replace('.','/')+'.py'
                if name and name.startswith('phase1.') and p in tracked and p not in seen:pending.append(p)
    for path in ('phase1/__init__.py','phase1/scripts/__init__.py','phase1/tests/__init__.py'):
        if path in tracked:seen.add(path)
    return sorted(seen)


def accounting():
    raw=c.run(['sacct','-X','-n','-P','-j',','.join(x[0] for x in PRIOR),
        '--format=JobIDRaw,State,ElapsedRaw,AllocTRES,ExitCode']).decode()
    expected={r[0]:r for r in PRIOR};seen=set();total=0
    for line in raw.splitlines():
        if not line.strip():continue
        jid,state,elapsed,tres,exitcode=line.split('|')[:5]
        c.require(jid in expected and jid not in seen,'unexpected_accounting');seen.add(jid)
        _,s,t,g=expected[jid]
        c.require(state==s and elapsed==str(t) and exitcode==('0:0' if s=='COMPLETED' else '1:0')
            and f'gres/gpu={g}' in tres.split(','),'prior_accounting_drift')
        total+=t*g
    c.require(seen==set(expected) and total==7006 and total+CAP==10846<=14400,'enumerated_engineering_cap')
    return total


def queue(own=None):
    q=c.run(['squeue','-h','-u','yzyang4','-o','%i']).decode().split()
    c.require(len(q)==len(set(q)) and set(q)=={'12535'}|({own} if own else set()),'unknown_or_missing_queued_job')
    f=fields('12535')
    c.require(f.get('JobState')=='PENDING' and f.get('Reason')=='JobHeldUser' and f.get('RunTime')=='00:00:00'
        and f.get('TimeLimit')=='00:26:00' and f.get('TresPerNode')=='gpu:pro6000:2'
        and f.get('ReqNodeList')=='projgpu39','obsolete_job_must_remain_held')


def fields(jid):
    return dict(x.split('=',1) for x in c.run(['scontrol','show','job','-o',jid]).decode().split() if '=' in x)


def bind(control,commit):
    c.safe_root(control);c.safe_root(c.SOURCE)
    c.require(c.run(['git','-C',control,'rev-parse','HEAD']).decode().strip()==commit and
        not c.run(['git','-C',control,'status','--porcelain','--untracked-files=all']).strip(),'control_changed')
    c.require(c.run(['git','-C',c.SOURCE,'rev-parse','HEAD']).decode().strip()==c.SOURCE_SHA and not os.access(c.SOURCE,os.W_OK),'source_changed')
    hashes={p:c.sha(control/p) for p in files(commit)}
    for n,h in hashes.items():c.require(h==hashlib.sha256(c.run(['git','-C',c.REPO,'show',commit+':'+n])).hexdigest(),'control_blob_drift')
    a=json.loads((control/APPROVAL).read_text())
    c.require(a['gpu_seconds_upper_bound']==CAP==2*(1560+300+60) and a['driver_seconds']==1200
        and a['automatic_retries']==0 and a['real_corpus_reads']==0 and a['pretrained_critic_weights_allowed'] is True
        and a['agent_base_update_allowed'] is False and a['source_admission'] is False,'approval_drift')
    c.require(all(a[k]==v for k,v in {'jobs':1,'gpu_count':2,'gpu_type':'pro6000','node':'projgpu39',
        'walltime_seconds':1560,'parameters':1720577025,'context_length':16384,'microbatch_per_rank':8,
        'accumulation':8,'seed':6,'checkpoints':2,'actual_space_probe_bytes':68719476736}.items()),'approval_matrix_drift')
    tiny=c.BASE/'critic-zero3-engineering/job-12575/TERMINAL_VERIFIED.json'
    c.require(c.sha(tiny)==TINY_SHA==a['tiny_terminal_sha256'],'tiny_acceptance_drift')
    c.require(json.loads(tiny.read_text())['classification']=='REAL_TINY_ZERO3_RESTART_AND_FINAL_READOUT_ACCEPTED_NOT_PIVOT_OR_EFFECT','tiny_not_accepted')
    c.require(hashes[MANIFEST]=='ceb388235719297e3647478ad2d96486a41d1f84e4c3fd8301c4772d6840e148','model_manifest_drift')
    c.require(c.sha(c.RUNTIME/'bin/ninja')=='696f9628a79d9ce50314cf9556d7cd1a1d1ec52b8fd52828f6f9db1719565b67','ninja_drift')
    accounting()
    return hashes


def previous_preparation():
    """Fresh preparation only after the fixed, never-submitted capacity failure."""
    c.safe_root(PREVIOUS_OUT)
    c.require(c.OUT!=PREVIOUS_OUT,'previous_failed_root_must_be_preserved')
    c.require(not any((PREVIOUS_OUT/n).exists() for n in ('READY.json','SUBMISSION_INTENT.json',
        'SUBMITTED.json','RELEASED.json')),'previous_preparation_may_have_submitted')
    previous=json.loads((PREVIOUS_OUT/'prepare_intent.json').read_text())
    probe=json.loads((PREVIOUS_OUT/'space-probe.json').read_text())
    released=json.loads((PREVIOUS_OUT/'space-probe-released.json').read_text())
    c.require(previous['commit']==PREVIOUS_COMMIT and probe['passed'] is False
        and probe['requested_bytes']==68719476736 and probe['allocated_bytes']==0
        and probe['error']=={'errno':122,'type':'OSError'},'previous_failure_drift')
    c.require(released['own_inode_removed'] is True and not (PREVIOUS_OUT/'own-checkpoint-space-probe.bin').exists()
        and (released['device'],released['inode'])==(probe['device'],probe['inode']),'previous_probe_not_released')
    c.require(c.sha(CLEANUP_RECEIPT)==CLEANUP_SHA,'cleanup_receipt_drift')
    cleanup=json.loads(CLEANUP_RECEIPT.read_text())
    c.require(cleanup['real_64GiB_allocation_passed'] is True and cleanup['real_probe_allocated_bytes']==68719476736
        and cleanup['probe_own_inode_released'] is True and cleanup['protected_fingerprints_equal'] is True,'cleanup_not_accepted')
    return {'previous_commit':PREVIOUS_COMMIT,'previous_output':str(PREVIOUS_OUT),'cleanup_summary_sha256':CLEANUP_SHA,
        'previous_evidence_sha256':{n:c.sha(PREVIOUS_OUT/n) for n in
            ('prepare_intent.json','space-probe.json','space-probe-released.json')},
        'prior_gpu_job_submitted':False,'fresh_space_probe_still_required':True}


def prepare(control,commit):
    queue();previous=previous_preparation();c.safe_root(c.BASE);c.OUT.parent.mkdir(mode=0o700,exist_ok=True);c.safe_root(c.OUT.parent)
    c.OUT.mkdir(mode=0o700);c.record('prepare_intent.json',{'commit':commit,'gpu_seconds_upper_bound':CAP,'controller_sha256':c.sha(__file__)})
    c.record('PREVIOUS_CAPACITY_FAILURE.json',previous)
    c.run(['git','-C',c.REPO,'fetch','--no-tags','https://github.com/SuperSumanov/aira-dojo-noise-robust.git',commit],timeout=240)
    c.require(not control.exists(),'control_exists')
    c.run(['git','-C',c.REPO,'worktree','add','--detach','--no-checkout',control,commit])
    c.run(['git','-C',control,'sparse-checkout','set','--no-cone','--stdin'],data=('\n'.join('/'+n for n in files(commit))+'\n').encode())
    c.run(['git','-C',control,'checkout','--detach',commit]);hashes=bind(control,commit)
    c.run(['bash','-n',control/SCRIPT])
    env=dict(c.ENV,PYTHONPATH=str(control),TRITON_CACHE_DIR='/tmp/critic-pivot-shape-capacity-recovered-triton')
    Path(env['TRITON_CACHE_DIR']).mkdir(mode=0o700)
    command="import sys; sys.path.append('/research/d7/spc/yzyang4/venvs/exp/lib/python3.11/site-packages'); import pytest; raise SystemExit(pytest.main("+repr(['-q','-p','no:cacheprovider',*['phase1/tests/'+t+'.py' for t in TESTS]])+"))"
    (c.OUT/'cpu-tests.log').write_bytes(c.run([c.RUNTIME/'bin/python','-B','-c',command],env=env,cwd=control,timeout=240))
    check="import json,torch; from phase1.pivot_zero3_shape_fixture import summary; from phase1.global_local_zero3_session import runtime_binding; from phase1.scripts.validate_pivot_zero3_shape_20260906 import SNAPSHOT,MANIFEST,MANIFEST_SHA; from phase1.verify_critic_component_g0 import validate_model_snapshot,sha256_file; from pathlib import Path; assert sha256_file(Path(MANIFEST))==MANIFEST_SHA; validate_model_snapshot(SNAPSHOT,Path(MANIFEST)); b=runtime_binding(); assert not torch.cuda.is_initialized(); print(json.dumps({'plan':summary(),'runtime':b,'model_manifest_sha256':MANIFEST_SHA,'gpu_context_created':False},sort_keys=True))"
    runtime_log=c.run([c.RUNTIME/'bin/python','-B','-c',check],env=env,cwd=control,timeout=240)
    (c.OUT/'runtime-plan.log').write_bytes(runtime_log)
    runtime=json.loads(runtime_log.decode().strip().splitlines()[-1])
    c.require(runtime['gpu_context_created'] is False and runtime['plan']['plan_sha256']=='d1fcdddc6ecb6e58d025f97ae9633b2bd5cb0390b20a05cb9cbd597e0a6e5ec6','runtime_plan_drift')
    c.record('runtime-plan.json',runtime)
    c.run([c.BASE/'venvs/exp/bin/python','-B','-c','from phase1.pivot_checkpoint_space import probe; import sys; probe(sys.argv[1])',c.OUT],env=env,cwd=control,timeout=180)
    c.require(bind(control,commit)==hashes,'end_prepare_drift')
    c.record('READY.json',{'commit':commit,'control':str(control),'hashes':hashes,'approval_sha256':hashes[APPROVAL],
        'gpu_seconds_upper_bound':CAP,'status':'READY_NOT_SUBMITTED','real_corpus_reads':0,
        'evidence_hashes':{n:c.sha(c.OUT/n) for n in ('cpu-tests.log','runtime-plan.log','runtime-plan.json','space-probe.json','space-probe-released.json')}})
    print(json.dumps({'status':'READY_NOT_SUBMITTED','files':len(hashes),'gpu_seconds_upper_bound':CAP}))


def ready(control,commit):
    r=json.loads((c.OUT/'READY.json').read_text())
    c.require(r['commit']==commit and r['hashes']==bind(control,commit),'ready_drift')
    c.require(set(r['evidence_hashes'])=={'cpu-tests.log','runtime-plan.log','runtime-plan.json','space-probe.json','space-probe-released.json'}
        and all(c.sha(c.OUT/n)==h for n,h in r['evidence_hashes'].items()),'preparation_evidence_drift')
    space=json.loads((c.OUT/'space-probe.json').read_text());released=json.loads((c.OUT/'space-probe-released.json').read_text())
    c.require(space['passed'] is True and space['requested_bytes']==68719476736 and space['allocated_bytes']>=68719476736
        and released['own_inode_removed'] is True and not (c.OUT/'own-checkpoint-space-probe.bin').exists(),'space_proof_failed')
    return r


def submit(control,commit):
    r=ready(control,commit);queue();c.record('SUBMISSION_INTENT.json',{'commit':commit,'jobs':1,'automatic_retry':False})
    export=','.join(['PATH=/usr/local/bin:/usr/bin:/bin',f'ZERO3_CONTROL_ROOT={control}',f'ZERO3_CODE_COMMIT={commit}',
        'ZERO3_GPU_APPROVAL_RECEIPT_SHA='+r['approval_sha256']])
    cmd=['sbatch','--parsable','--hold','--no-requeue',f'--chdir={control}',f'--output={c.OUT}/slurm-%j.out',
        f'--error={c.OUT}/slurm-%j.out',f'--export={export}',str(control/SCRIPT)]
    c.record('command.json',cmd);p=subprocess.run(cmd,env=c.ENV,capture_output=True,timeout=60)
    c.require(not c.SHAPE.search(p.stdout+p.stderr),'submission_output_withheld')
    (c.OUT/'sbatch.stdout').write_bytes(p.stdout);(c.OUT/'sbatch.stderr').write_bytes(p.stderr)
    c.record('sbatch_status.json',{'returncode':p.returncode});c.require(p.returncode==0,'submit_failed_do_not_retry')
    jid=p.stdout.decode().strip().split(';')[0];c.require(re.fullmatch('[0-9]+',jid),'unknown_job_id')
    c.record('SUBMITTED.json',{'job_id':jid,'commit':commit});print(json.dumps({'status':'HELD','job_id':jid}))


def allocation(control,jid,state):
    f=fields(jid)
    expected={'JobId':jid,'JobState':state,'Requeue':'0','Restarts':'0','TimeLimit':'00:26:00',
        'NumCPUs':'12','CPUs/Task':'12','MinMemoryNode':'0','NumTasks':'1','ReqNodeList':'projgpu39',
        'TresPerNode':'gpu:pro6000:2','Partition':'gpu_24h','QOS':'gpu','Command':str(control/SCRIPT),'WorkDir':str(control)}
    if state=='PENDING':expected.update(Reason='JobHeldUser',RunTime='00:00:00')
    else:expected.update(NodeList='projgpu39')
    c.require(all(f.get(k)==v for k,v in expected.items()) and f.get('NumNodes') in ('1','1-1')
        and {'cpu=12','node=1','gres/gpu=2'}.issubset(f.get('TRES','').split(',')),'allocation_mismatch')
    return f


def release(control,commit):
    ready(control,commit);s=json.loads((c.OUT/'SUBMITTED.json').read_text());jid=s['job_id'];queue(jid)
    c.require(s['commit']==commit,'submitted_commit')
    c.record('VERIFIED_HELD.json',{'fields':allocation(control,jid,'PENDING'),'new_gpu_upper_bound':CAP})
    c.require((c.OUT/'INDEPENDENT_PRE_RELEASE.json').is_file(),'independent_held_review_required')
    c.run(['scontrol','release',jid]);c.record('RELEASED.json',s);print(json.dumps({'status':'RELEASED','job_id':jid}))


def allocated(control,commit):
    r=ready(control,commit);s=json.loads((c.OUT/'RELEASED.json').read_text());jid=os.environ.get('SLURM_JOB_ID')
    c.require(s=={'job_id':jid,'commit':commit},'allocated_job_identity')
    f=allocation(control,jid,'RUNNING')
    from phase1.critic_training_worker import duration
    elapsed=duration(f['RunTime']);c.require(elapsed+1200+60<=1560,'insufficient_worker_time')
    root=c.BASE/'critic-pivot-shape'/('job-'+jid);c.safe_root(root)
    with (root/'allocation.json').open('x') as out:json.dump({'fields':f,'source_commit':commit,'prior_gpu_seconds':accounting(),
        'gpu_upper_bound':CAP,'approval_sha256':r['approval_sha256']},out,sort_keys=True,indent=2)
    print('ALLOCATED_PIVOT_SHAPE_GATES_PASS')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','submit','release','allocated']);p.add_argument('--commit',required=True)
    a=p.parse_args();c.require(re.fullmatch('[0-9a-f]{40}',a.commit),'commit');os.umask(0o077)
    control=c.BASE/'worktrees'/('critic-pivot-shape-'+a.commit[:12])
    try:globals()[a.action](control,a.commit)
    except Exception as exc:
        print(json.dumps({'status':'FAILED_CLOSED','reason':str(exc) if isinstance(exc,(RuntimeError,ValueError)) else type(exc).__name__}))
        raise SystemExit(1)
