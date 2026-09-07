"""Separate synthetic RTX3090 qualification, never a production fallback.

One held allocation, one full-size two-update trajectory, fresh exclusive output.
Original PRO6000 controller remains unchanged. No real-data admission or polling.
"""
import argparse,ast,datetime,hashlib,json,os,re,subprocess
from pathlib import Path

BASE=Path('/research/d7/spc/yzyang4');REPO=BASE/'aira-dojo'
RUNTIME=BASE/'venvs/critic-blackwell-g0-20260905-r5'
SOURCE=BASE/'worktrees/critic-g0-final-only-20260903-b'
SOURCE_SHA='5f3bc362db922c8edee2ef134656dfdb9a2b74fb'
OUT=BASE/'critic-pivot-ampere/submission-20260907'
BUILD=BASE/'flash-attn-build-ampere-20260907-r1'
BUILD_JOB='12649';BUILD_COMMIT='41da8a97e876055b8136595891db1457ff4f44bf'
BUILD_SCRIPT_SHA='c5b578e51f1fe05cf1b3a4a98f9ecbad0a6dfddd2bca48008cc95eab85e42275'
SCRIPT='phase1/scripts/pivot_ampere_shape_20260907.sbatch'
APPROVAL='phase1/manifests/pivot_ampere_shape_approval_20260907.json'
MANIFEST='phase1/manifests/qwen3-1.7b-base-ea980cb0a6c2ae4b936e82123acc929f1cec04c1.sha256'
MODEL_SHA='ceb388235719297e3647478ad2d96486a41d1f84e4c3fd8301c4772d6840e148'
PLAN_SHA='4783949509ad998150ff1217d9d01344886a3de100f90c5c48a054c8f3ceb7ff'
TINY_SHA='14dae4dbc7e1497695d1081517a1603833f4a6f97bd8ac3d534b5e0debdffaa2'
CAP=7920;DRIVER=3000;WALL=3600
PRIOR=[('12181','FAILED',156,2),('12288','FAILED',4,2),('12377','FAILED',131,2),('12486','FAILED',191,2),
 ('12497','COMPLETED',1,1),('12499','COMPLETED',2192,2),('12510','FAILED',149,2),('12570','FAILED',1,2),
 ('12571','COMPLETED',5,1),('12572','FAILED',73,2),('12573','FAILED',133,2),('12574','FAILED',199,2),
 ('12575','COMPLETED',271,2),('12577','FAILED',98,2),('12635','FAILED',89,1),('12638','FAILED',1,1),
 ('12639','COMPLETED',5,1),('12641','FAILED',2126,1)]
TESTS=['test_pivot_ampere_profile','test_critic_ampere_build_receipt','test_pivot_ampere_artifact_check',
 'test_pivot_checkpoint_space','test_critic_training_entry','test_critic_training_definition',
 'test_critic_training_worker','test_global_local_zero3_session','test_cpu_adam_native_cache',
 'test_zero3_consumed_gradients','test_critic_fa2_preflight']
EVIDENCE=('cpu-tests.log','runtime-plan.log','runtime-plan.json','space-probe.json',
 'space-probe-released.json','fa2-build-binding.json','fa2-cpu.json')
ENV=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf',GIT_LFS_SKIP_SMUDGE='1',
 PYTHONDONTWRITEBYTECODE='1',CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',
 MKL_NUM_THREADS='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
SECRET=re.compile(
    rb"(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|"
    rb"github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16}|Bearer[ \t]+[A-Za-z0-9._-]{20,})"
)

def require(ok,reason):
    if not ok:raise RuntimeError(reason)

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(2**20),b''):h.update(b)
    return h.hexdigest()

def safe_root(p):
    require(p.is_absolute() and p.resolve(strict=True)==p and not any(x.is_symlink() for x in (p,*p.parents)),'unsafe_root')

def run(args,*,timeout=120,env=None,cwd=None,data=None):
    p=subprocess.run(list(map(str,args)),env=env or ENV,cwd=cwd,input=data,capture_output=True,timeout=timeout)
    require(not SECRET.search(p.stdout+p.stderr),'credential_shape_withheld')
    if p.returncode:
        if OUT.is_dir():
            tag='failed-'+datetime.datetime.now(datetime.timezone.utc).strftime('%H%M%S%f')
            for ext,raw in [('stdout',p.stdout),('stderr',p.stderr)]:
                with (OUT/(tag+'.'+ext)).open('xb') as f:f.write(raw)
        raise RuntimeError('subprocess_failed:'+Path(str(args[0])).name)
    return p.stdout

def record(name,value):
    with (OUT/name).open('x') as f:json.dump(value,f,sort_keys=True,indent=2);f.flush();os.fsync(f.fileno())

def read(p):
    from phase1.critic_fa2_build_receipt import read as safe_read
    return safe_read(p.parent,p.name)

def fields(jid):return dict(x.split('=',1) for x in run(['scontrol','show','job','-o',jid]).decode().split() if '=' in x)

def queue(own=None):
    ids=run(['squeue','-h','-u','yzyang4','-o','%i']).decode().split()
    require(len(ids)==len(set(ids)) and set(ids)=={'12535'}|({own} if own else set()),'other_job_or_duplicate')
    old=fields('12535')
    require(old['JobState']=='PENDING' and old['Reason']=='JobHeldUser' and old['RunTime']=='00:00:00'
        and old['ReqNodeList']=='projgpu39' and old['TresPerNode']=='gpu:pro6000:2','old_job_not_held')

def parse_accounting(raw):
    prior={j:(s,t,g) for j,s,t,g in PRIOR};seen=set();total=0
    for line in raw.splitlines():
        if not line.strip():continue
        j,s,t,a,e=line.split('|')[:5];require(j not in seen,'duplicate_accounting');seen.add(j)
        require(t.isdecimal(),'invalid_accounting_time');t=int(t)
        if j in ('12648',BUILD_JOB):
            require(s=='COMPLETED' and e=='0:0' and 0<t<=5760 and 'gres/gpu=1' in a.split(','),'build_terminal_not_accepted')
            total+=t
        else:
            require(j in prior,'unknown_accounting');es,et,g=prior[j]
            require((s,t)==(es,et) and e==('0:0' if es=='COMPLETED' else '1:0') and f'gres/gpu={g}' in a.split(','),'prior_accounting_drift')
            total+=t*g
    require(seen==set(prior)|{'12648',BUILD_JOB} and sum(t*g for _,_,t,g in PRIOR)==9423,'incomplete_accounting')
    require(total+CAP+3840<=36000,'combined_envelope_exceeded')
    return total

def accounting():
    return parse_accounting(run(['sacct','-X','-n','-P','-j',','.join([j for j,_,_,_ in PRIOR]+['12648',BUILD_JOB]),
        '--format=JobIDRaw,State,ElapsedRaw,AllocTRES,ExitCode']).decode())

def build_binding():
    from phase1.critic_ampere_preflight import bind_completed_ampere
    b=bind_completed_ampere(BUILD,expected_commit=BUILD_COMMIT,expected_job=BUILD_JOB,expected_script_sha=BUILD_SCRIPT_SHA)
    proof=read(BUILD/'terminal-independent/VERIFIED.json')
    require(proof['classification']=='INDEPENDENT_FA2_AMPERE_BUILD_ACCEPTED_NOT_GPU_NUMERICS_OR_MODEL_EFFECT'
        and proof['job_id']==BUILD_JOB and proof['build_receipt_sha256']==b['build_receipt_sha256']
        and proof['source_files_checked']==6608 and proof['gpu_math_verified'] is False,'independent_build_missing')
    return b

def approval_valid(a):
    return a=={'schema':'bounded-synthetic-ampere-shape-v1','jobs':1,'gpu_count':2,'gpu_type':'rtx3090','node':'gpu28',
      'walltime_seconds':WALL,'driver_seconds':DRIVER,'fa2_gpu_check_seconds':180,'gpu_seconds_upper_bound':CAP,
      'combined_engineering_envelope_gpu_seconds':36000,'parameters':1720577025,'context_length':16384,
      'microbatch_per_rank':1,'accumulation':64,'global_pair_batch':128,'seed':6,'checkpoints':2,
      'actual_space_probe_bytes':68719476736,'automatic_retries':0,'source_admission':False,
      'real_corpus_reads':0,'agent_base_update_allowed':False,'paid_api_allowed':False,'model_effect_measured':False,
      'full_size_uninterrupted_parity_measured':False,'build_job':BUILD_JOB,'build_commit':BUILD_COMMIT,
      'build_script_sha256':BUILD_SCRIPT_SHA,'model_manifest_sha256':MODEL_SHA,'plan_sha256':PLAN_SHA,
      'tiny_terminal_sha256':TINY_SHA}

def files(commit):
    tracked=set(run(['git','-C',REPO,'ls-tree','-r','--name-only',commit]).decode().splitlines())
    pending=['phase1/scripts/prepare_pivot_ampere_shape_20260907.py','phase1/scripts/validate_pivot_ampere_shape_20260907.py',
      'phase1/scripts/verify_pivot_ampere_artifacts_20260907.py','phase1/check_g0_r5_build_tools.py',
      'phase1/pivot_checkpoint_space.py',*['phase1/tests/'+n+'.py' for n in TESTS]]
    seen={SCRIPT,APPROVAL,MANIFEST}
    while pending:
        path=pending.pop()
        if path in seen:continue
        raw=run(['git','-C',REPO,'show',commit+':'+path]);seen.add(path)
        for node in ast.walk(ast.parse(raw)):
            if isinstance(node,ast.ImportFrom):names=[node.module]+[node.module+'.'+x.name for x in node.names] if node.module else []
            elif isinstance(node,ast.Import):names=[x.name for x in node.names]
            else:continue
            for name in names:
                n=(name or '').replace('.','/')+'.py'
                if name and name.startswith('phase1.') and n in tracked and n not in seen:pending.append(n)
    for p in ('phase1/__init__.py','phase1/scripts/__init__.py','phase1/tests/__init__.py'):
        if p in tracked:seen.add(p)
    return sorted(seen)

def bind(control,commit):
    safe_root(control);safe_root(SOURCE)
    require(run(['git','-C',control,'rev-parse','HEAD']).decode().strip()==commit
        and not run(['git','-C',control,'status','--porcelain','--untracked-files=all']).strip(),'control_changed')
    require(run(['git','-C',SOURCE,'rev-parse','HEAD']).decode().strip()==SOURCE_SHA and not os.access(SOURCE,os.W_OK),'senior_code_changed')
    hashes={n:sha(control/n) for n in files(commit)}
    for n,h in hashes.items():require(h==hashlib.sha256(run(['git','-C',REPO,'show',commit+':'+n])).hexdigest(),'source_drift')
    require(approval_valid(read(control/APPROVAL)),'approval_drift')
    require(hashes[MANIFEST]==MODEL_SHA and sha(RUNTIME/'bin/ninja')=='696f9628a79d9ce50314cf9556d7cd1a1d1ec52b8fd52828f6f9db1719565b67','model_or_tools_drift')
    tiny=BASE/'critic-zero3-engineering/job-12575/TERMINAL_VERIFIED.json'
    require(sha(tiny)==TINY_SHA and read(tiny)['classification']=='REAL_TINY_ZERO3_RESTART_AND_FINAL_READOUT_ACCEPTED_NOT_PIVOT_OR_EFFECT','tiny_drift')
    build_binding();accounting();return hashes

def prepare(control,commit):
    queue();accounting();b=build_binding();safe_root(BASE)
    OUT.parent.mkdir(mode=0o700,exist_ok=True);safe_root(OUT.parent);OUT.mkdir(mode=0o700)
    record('prepare_intent.json',{'commit':commit,'gpu_seconds_upper_bound':CAP,'controller_sha256':sha(__file__),'real_corpus_reads':0})
    record('fa2-build-binding.json',b);require(not control.exists(),'control_exists')
    run(['git','-C',REPO,'fetch','--no-tags','https://github.com/SuperSumanov/aira-dojo-noise-robust.git',commit],timeout=240)
    run(['git','-C',REPO,'worktree','add','--detach','--no-checkout',control,commit])
    run(['git','-C',control,'sparse-checkout','set','--no-cone','--stdin'],data=('\n'.join('/'+n for n in files(commit))+'\n').encode())
    run(['git','-C',control,'checkout','--detach',commit]);hashes=bind(control,commit);run(['bash','-n',control/SCRIPT])
    env=dict(ENV,PYTHONPATH=str(BUILD/'overlay')+os.pathsep+str(control),TRITON_CACHE_DIR='/tmp/critic-pivot-ampere-20260907-triton')
    Path(env['TRITON_CACHE_DIR']).mkdir(mode=0o700)
    tests=['-q','--tb=short','-p','no:cacheprovider',*['phase1/tests/'+n+'.py' for n in TESTS]]
    code="import sys;sys.path.append('/research/d7/spc/yzyang4/venvs/exp/lib/python3.11/site-packages');import pytest;raise SystemExit(pytest.main("+repr(tests)+"))"
    (OUT/'cpu-tests.log').write_bytes(run([RUNTIME/'bin/python','-B','-c',code],env=env,cwd=control,timeout=300))
    run([RUNTIME/'bin/python','-B','-m','phase1.critic_fa2_preflight','--overlay',BUILD/'overlay','--manifest',BUILD/'BUILT.json',
        '--expected-sha256',b['build_receipt_sha256'],'--output',OUT/'fa2-cpu.json'],env=env,cwd=control,timeout=90)
    code="import json,torch;from phase1.pivot_ampere_shape_fixture import summary;from phase1.global_local_zero3_session import runtime_binding;from phase1.scripts.validate_pivot_ampere_shape_20260907 import SNAPSHOT,MANIFEST,MANIFEST_SHA;from phase1.verify_critic_component_g0 import validate_model_snapshot,sha256_file;from pathlib import Path;assert sha256_file(Path(MANIFEST))==MANIFEST_SHA;validate_model_snapshot(SNAPSHOT,Path(MANIFEST));b=runtime_binding();assert not torch.cuda.is_initialized();print(json.dumps({'plan':summary(),'runtime':b,'model_manifest_sha256':MANIFEST_SHA,'gpu_context_created':False},sort_keys=True))"
    raw=run([RUNTIME/'bin/python','-B','-c',code],env=env,cwd=control,timeout=240);(OUT/'runtime-plan.log').write_bytes(raw)
    runtime=json.loads(raw.decode().strip().splitlines()[-1]);require(runtime['gpu_context_created'] is False and runtime['plan']['plan_sha256']==PLAN_SHA,'runtime_plan_drift')
    record('runtime-plan.json',runtime)
    run([BASE/'venvs/exp/bin/python','-B','-c','from phase1.pivot_checkpoint_space import probe;import sys;probe(sys.argv[1])',OUT],env=env,cwd=control,timeout=180)
    require(bind(control,commit)==hashes and build_binding()==b,'end_prepare_drift')
    record('READY.json',{'commit':commit,'control':str(control),'hashes':hashes,'approval_sha256':hashes[APPROVAL],
      'gpu_seconds_upper_bound':CAP,'prior_actual_gpu_seconds':accounting(),'status':'READY_NOT_SUBMITTED',
      'real_corpus_reads':0,'fa2_build_receipt_sha256':b['build_receipt_sha256'],
      'evidence_hashes':{n:sha(OUT/n) for n in EVIDENCE}})
    print(json.dumps({'status':'AMPERE_SHAPE_READY_NOT_SUBMITTED','files':len(hashes),'gpu_seconds_upper_bound':CAP}))

def ready(control,commit):
    r=read(OUT/'READY.json');require(r['commit']==commit and r['hashes']==bind(control,commit),'ready_drift')
    require(set(r['evidence_hashes'])==set(EVIDENCE) and all(sha(OUT/n)==h for n,h in r['evidence_hashes'].items()),'preparation_drift')
    b=build_binding();require(read(OUT/'fa2-build-binding.json')==b and r['fa2_build_receipt_sha256']==b['build_receipt_sha256'],'build_changed')
    cpu=read(OUT/'fa2-cpu.json');require(cpu['classification']=='FA2_CPU_BINDING_NOT_GPU_ACCEPTANCE'
        and cpu['binding']['build_sha256']==b['build_receipt_sha256'],'cpu_binding_changed')
    p=read(OUT/'space-probe.json');q=read(OUT/'space-probe-released.json')
    require(p['passed'] is True and p['requested_bytes']==68719476736 and p['allocated_bytes']>=68719476736
        and q['own_inode_removed'] is True and not (OUT/'own-checkpoint-space-probe.bin').exists(),'space_proof_failed')
    return r

def submit(control,commit):
    r=ready(control,commit);queue();record('SUBMISSION_INTENT.json',{'commit':commit,'jobs':1,'automatic_retry':False})
    export=','.join(['PATH=/usr/local/bin:/usr/bin:/bin','ZERO3_CONTROL_ROOT='+str(control),'ZERO3_CODE_COMMIT='+commit,
        'ZERO3_GPU_APPROVAL_RECEIPT_SHA='+r['approval_sha256']])
    cmd=['sbatch','--parsable','--hold','--no-requeue','--chdir='+str(control),'--output='+str(OUT/'slurm-%j.log'),
        '--error='+str(OUT/'slurm-%j.log'),'--export='+export,str(control/SCRIPT)]
    record('command.json',cmd);p=subprocess.run(cmd,env=ENV,capture_output=True,timeout=60)
    require(not SECRET.search(p.stdout+p.stderr),'submission_credential_shape')
    (OUT/'sbatch.stdout').write_bytes(p.stdout);(OUT/'sbatch.stderr').write_bytes(p.stderr)
    record('sbatch_status.json',{'returncode':p.returncode});require(p.returncode==0,'submit_failed_no_retry')
    jid=p.stdout.decode().strip().split(';')[0];require(jid.isdecimal(),'unknown_job')
    record('SUBMITTED.json',{'job_id':jid,'commit':commit});print(json.dumps({'status':'HELD','job_id':jid}))

def allocation(control,jid,state):
    f=fields(jid);wanted={'JobId':jid,'JobState':state,'Requeue':'0','Restarts':'0','TimeLimit':'01:00:00',
      'NumCPUs':'12','CPUs/Task':'12','MinMemoryNode':'0','NumTasks':'1','ReqNodeList':'gpu28','TresPerNode':'gpu:rtx3090:2',
      'Partition':'gpu_24h','QOS':'gpu','Command':str(control/SCRIPT),'WorkDir':str(control)}
    if state=='PENDING':wanted.update(Reason='JobHeldUser',RunTime='00:00:00')
    else:wanted.update(NodeList='gpu28')
    require(all(f.get(k)==v for k,v in wanted.items()) and f.get('NumNodes') in ('1','1-1')
        and {'cpu=12','node=1','gres/gpu=2'}<=set(f.get('TRES','').split(',')),'allocation_mismatch')
    return f

def release(control,commit):
    ready(control,commit);s=read(OUT/'SUBMITTED.json');jid=s['job_id'];queue(jid)
    require(s['commit']==commit,'submitted_commit');f=allocation(control,jid,'PENDING')
    proof=read(OUT/'INDEPENDENT_PRE_RELEASE.json')
    require(proof['source_commit']==commit and proof['job_id']==jid and proof['source_and_resources_verified'] is True,'independent_held_review_missing')
    record('VERIFIED_HELD.json',{'fields':f});record('RELEASE_INTENT.json',s)
    run(['scontrol','release',jid]);record('RELEASED.json',s);print(json.dumps({'status':'RELEASED','job_id':jid}))

def kernel(control,commit):
    r=ready(control,commit);jid=os.environ.get('SLURM_JOB_ID')
    require(read(OUT/'RELEASED.json')=={'job_id':jid,'commit':commit} and os.environ.get('ZERO3_GPU_APPROVAL_RECEIPT_SHA')==r['approval_sha256'],'allocated_identity')
    allocation(control,jid,'RUNNING')
    from phase1.scripts.validate_zero3_session_gpu_20260905 import allocation_gate
    from phase1.critic_ampere_preflight import cpu_binding,check_device,kernel_receipt_valid,verify_overlay
    allocation_gate(os.environ);b=cpu_binding(BUILD/'overlay',BUILD/'BUILT.json',r['fa2_build_receipt_sha256'])
    import torch
    require(torch.cuda.device_count()==2,'two_gpus_required')
    value={'classification':'FA2_AMPERE_TWO_GPU_SYNTHETIC_KERNEL_CHECK_NOT_MODEL_EFFECT','binding':b,
      'devices':[check_device(i) for i in (0,1)],'job_id':jid,'code_commit':commit}
    verify_overlay(BUILD/'overlay',BUILD/'BUILT.json',r['fa2_build_receipt_sha256'])
    require(kernel_receipt_valid(value,job=jid,commit=commit,build_sha=r['fa2_build_receipt_sha256']),'kernel_receipt_failed')
    p=BASE/'critic-pivot-ampere'/('job-'+jid)/'fa2-kernel.json'
    with p.open('x') as f:json.dump(value,f,sort_keys=True,indent=2)
    print('FA2_AMPERE_TWO_GPU_KERNEL_PASS_NOT_MODEL_EFFECT')

def allocated(control,commit):
    r=ready(control,commit);jid=os.environ.get('SLURM_JOB_ID');queue(jid)
    require(read(OUT/'RELEASED.json')=={'job_id':jid,'commit':commit},'allocated_release')
    f=allocation(control,jid,'RUNNING')
    from phase1.critic_training_worker import duration
    from phase1.critic_ampere_preflight import kernel_receipt_valid
    require(duration(f['RunTime'])+DRIVER+60<=WALL,'insufficient_driver_walltime')
    root=BASE/'critic-pivot-ampere'/('job-'+jid);safe_root(root)
    require(kernel_receipt_valid(read(root/'fa2-kernel.json'),job=jid,commit=commit,build_sha=r['fa2_build_receipt_sha256']),'kernel_not_accepted')
    with (root/'allocation.json').open('x') as p:json.dump({'fields':f,'source_commit':commit,'prior_gpu_seconds':accounting(),
      'gpu_upper_bound':CAP,'approval_sha256':r['approval_sha256']},p,sort_keys=True,indent=2)
    print('ALLOCATED_AMPERE_PIVOT_SHAPE_GATES_PASS')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','submit','release','kernel','allocated']);p.add_argument('--commit',required=True)
    a=p.parse_args();require(re.fullmatch('[0-9a-f]{40}',a.commit),'exact_commit_required');os.umask(0o077)
    control=BASE/'worktrees'/('critic-pivot-ampere-'+a.commit[:12])
    try:globals()[a.action](control,a.commit)
    except Exception as exc:
        print(json.dumps({'status':'FAILED_CLOSED','reason':str(exc) if isinstance(exc,(RuntimeError,ValueError)) else type(exc).__name__}))
        raise SystemExit(1)
