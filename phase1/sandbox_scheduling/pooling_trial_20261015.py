"""Approved32-run fixed-device vs shared-FIFO qualification; <=10 whole GPUh.

Common4-GPU execution Slurm step, exact ONE-device namespace per sandbox, fixed
two physical CPU cores/run. Eligibility is the only arm difference. This is a
standard strong baseline qualification, NOT an algorithm-novelty claim.
"""
import argparse
import concurrent.futures
import csv
import inspect
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import signal
import stat
import subprocess
import sys
import threading
import time
import traceback

DONOR=Path('/research/d7/spc/yzyang4/scheduling-metric-deployment-20261015-v2')
sys.path.insert(1,str(DONOR))
import generation_joint_trial_20261012 as base
import joint_generation_policy_20261012 as old_parent
import feedback_parent_policy_20261012 as parent
import weight_effort_policy_20261014 as policy
from lifecycle_pilot import read,write,sha
from fixed_public_preview_20261014 import load_text,install,digest,public_manifest
import shared_pool_20261015 as pool

R=DONOR.parent/'scheduling-pooling-20261015-v1'
NODE='gpu3';NAME=Path(__file__).name
ORDER=('fixed','shared','shared','fixed');RUN,SLOT,CAP=1020,1180,6000
DONOR_SHA='e3baf5d2fa704cdd0c3fc458549aa21449fdbf3209bac87337b370e2a416e154'
BUNDLE_SHA='d12d04af8684983be97f5ae6277731a65b505b5034244be34343daee02947006'
NAMES=(NAME,'shared_pool_20261015.py','test_shared_pool_20261015.py','pooling_readout_20261015.py',
       'test_pooling_qualification_20261015.py')


def schedule():
    return [dict(index=8*b+2*l+k,block=b,lane=l,slot=2*l+k,repeat=b//2,
        arm='old_fast',pool_mode=mode,task=t,seed=215501+100*(b//2)+2*l+k)
        for b,mode in enumerate(ORDER) for l in range(4) for k,t in enumerate(base.c.trial.TASKS)]


def configure():
    base.R,base.CAP,base.RUN,base.SLOT=R,CAP,RUN,SLOT
    base.NAME,base.schedule,base.install_hooks=NAME,schedule,install_hooks
    base.configure();old_parent.initialize=parent.initialize


def host():
    m=base.host();m.task_runtime=task_runtime
    return m


def install_hooks(row,ep,deadline):
    import live_runtime_hooks as hooks
    hooks.Lease=pool.Lease
    source=inspect.getsource(hooks.install)
    change=base.c.trial.change
    source=change(source,'ep.parent/f"queue-{row[\'block\']}"','ep.parent/f"pool-{row[\'block\']}"')
    # Both arms admit BEFORE creating a kernel. A task is never initialized on
    # an unassigned GPU, and startup/cleanup occupy the lease in both arms.
    source=change(source,'        try:\n            yield','        try:\n            lease.acquire()\n            yield')
    ns=dict(vars(hooks));exec(compile(source,'shared-execution-common-hooks','exec'),ns)
    ns['install'](row,ep,deadline)
    policy.install(row,ep,deadline,read(R/'warm.private.json')[row['task']])
    from dojo.solvers.mcts.mcts import MCTS
    from dojo.core.solvers.llm_helpers.generic_llm import GenericLLM
    from live_admission import append_event
    ref=read(R/'input-matrix/summary.safe.json')['rows'][row['index']]
    assert all(ref[k]==row[k] for k in ('index','task','arm','seed'))
    text=load_text(R/'public-preview.private.json',BUNDLE_SHA,row['task'])
    install(MCTS,GenericLLM,text,ref['first_prompt_sha256'],
            lambda e:append_event(ep/'input-gate.jsonl',dict(e,index=row['index'])))


def namespace_command(args,uid):
    from forets_gpu_binding_20260911 import split_command,rewrite
    from forets_opencl_allowlist_20260911 import driver_binds
    split_command(args)
    matches=[]
    for path in Path('/proc/driver/nvidia/gpus').glob('*/information'):
        values=dict((k.strip(),v.strip()) for line in path.read_text().splitlines()
                    if ':' in line for k,v in [line.split(':',1)])
        if values.get('GPU UUID')==uid:matches.append(values)
    if len(matches)!=1:raise ValueError('UUID does not uniquely map to driver device')
    minor=int(matches[0]['Device Minor']);info=os.lstat(f'/dev/nvidia{minor}')
    if not stat.S_ISCHR(info.st_mode) or os.major(info.st_rdev)!=195 or os.minor(info.st_rdev)!=minor:
        raise ValueError('driver/device disagreement')
    cache=subprocess.check_output(['/sbin/ldconfig','-p'],text=True,timeout=10)
    final,gate=rewrite(args,minor=minor,uuid=uid,libraries=driver_binds(cache),vendors=R/'opencl-vendors')
    env={k:os.environ[k] for k in ('PATH','HOME','USER','LOGNAME') if k in os.environ}
    checked=subprocess.run(gate,env=env,capture_output=True,text=True,timeout=25)
    rows=[json.loads(x.removeprefix('ALLOWLIST_GATE ')) for x in checked.stdout.splitlines() if x.startswith('ALLOWLIST_GATE ')]
    if checked.returncode or len(rows)!=1 or rows[0].get('exact_device_namespace') is not True:
        raise RuntimeError('exact one-device mount gate failed')
    return final,env,dict(gpu_uuid=uid,minor=minor,namespace=rows[0])


def task_runtime():
    from forets_gpu_binding_20260911 import REAL_SINGULARITY
    args=sys.argv[1:]
    if args==['--version']:os.execv(REAL_SINGULARITY,[REAL_SINGULARITY,'--version'])
    ep=Path(os.environ['POLICY9B_EPISODE'])
    if ep.parent!=R or not re.fullmatch(r'episode-(?:[0-9]|[12][0-9]|3[01])',ep.name):
        raise ValueError('unexpected sandbox path')
    index=int(ep.name.split('-')[1]);row=schedule()[index]
    native=read(R/f"block-{row['block']}/execution-native.json")
    assert native['job']==os.environ['SLURM_JOB_ID'] and native['step']==os.environ['SLURM_STEP_ID']
    key,lease=pool.assigned(R,row['block'],index)
    uid=native['gpu_uuids'][lease['device']]
    # This process is fresh. UUID selection is not the security boundary:
    # rewrite removes --nv, binds only the selected device, and runs its gate.
    os.environ['CUDA_VISIBLE_DEVICES']=uid
    from resource_gpu_identity import gpu_uuids
    assert gpu_uuids(1)==[uid]
    final,env,receipt=namespace_command(args,uid)
    write(ep/f'binding-{os.getpid()}.json',dict(receipt,key=key,device=lease['device'],
        home=row['lane'],system_bindpaths_disabled=True,job=native['job'],step=native['step']))
    os.execve(REAL_SINGULARITY,final,env)


def cpu_slots(topology):
    # Exactly one hardware thread/core; keep the same16 cores and same run
    # affinity over all four pools, independent of where its GPU work lands.
    groups={}
    for r in topology:groups.setdefault((r['socket'],r['core']),[]).append(r['logical_cpu'])
    cores=sorted(min(v) for v in groups.values())
    if len(cores)!=16:raise ValueError('expected16 physical execution cores')
    return [cores[2*i:2*i+2] for i in range(8)]


def worker(index):
    row=schedule()[index];native=read(R/f"block-{row['block']}/execution-native.json")
    chosen=native['cpu_slots'][row['slot']]
    os.sched_setaffinity(0,chosen)
    from live_identity import cpu_topology,cores
    top=cpu_topology();assert len(cores(top))==2
    ep=R/f'episode-{index}'
    write(ep/'cpu-partition.json',dict(worker_topology=top,chosen=chosen,slot=row['slot']))
    os.environ['CUDA_VISIBLE_DEVICES']=native['gpu_uuids'][row['lane']]
    return host().worker(index)


def qualification(native):
    # No development data/score/model calls. Same exact command builder/image
    # as production; actual CUDA arithmetic and capabilities on all four GPUs.
    q=R/'dispatch-qualification';q.mkdir();work=q/'work';work.mkdir()
    s=pool.State('shared')
    for i in range(4):s.request(str(i),3)
    # Hold all four logical leases before the sequential device checks. Releasing
    # device0 first correctly makes FIFO select it again; requiring device1 in
    # that situation was a qualification-harness bug (closed batch18468).
    assigned=[s.admit(str(i)) for i in range(4)]
    assert assigned==list(range(4))
    results=[]
    for i,uid in enumerate(native['gpu_uuids']):
        device=assigned[i]
        code=("import json,os,torch; from pathlib import Path; "
              "assert torch.cuda.is_available() and torch.cuda.device_count()==1; "
              "caps=dict(line.split(':',1) for line in Path('/proc/self/status').read_text().splitlines() if ':' in line); "
              "assert int(caps['CapEff'].strip(),16)==0; "
              "a=torch.ones((16,16),device='cuda'); b=a@a; torch.cuda.synchronize(); "
              "assert b.sum().item()==4096; "
              "print('POOL_CUDA_GATE '+json.dumps(dict(passed=True,device_count=1,cap_eff=0,result=4096)))")
        args=['exec','--containall','--cleanenv','--no-home','--nv','--bind',str(work)+':/workspace:rw',
              '--pwd','/workspace',str(host().TASK_IMAGE),'env','HOME=/workspace/.home','python','-c',code]
        cmd,env,receipt=namespace_command(args,uid)
        p=subprocess.run(cmd,env=env,capture_output=True,text=True,timeout=45)
        rows=[json.loads(x.removeprefix('POOL_CUDA_GATE ')) for x in p.stdout.splitlines() if x.startswith('POOL_CUDA_GATE ')]
        if p.returncode or len(rows)!=1 or rows[0].get('passed') is not True:
            write(q/f'failed-{i}.safe.json',dict(device=i,returncode=p.returncode,gate_records=len(rows)))
            raise RuntimeError('real CUDA/isolation qualification failed')
        results.append(dict(receipt,device=device,home=3,cuda=rows[0]));s.release(str(i),True)
    write(R/'dispatch-qualification.json',dict(passed=True,rows=results,source_commit=read(R/'plan.json')['source_commit'],
        boundary='Known arithmetic only, no quality benefit. Container namespace is one device; trusted execution step owns4.'))


def executor(block):
    base.c.trial.check();base.c.trial.activate_helpers();host().setup()
    from resource_gpu_identity import gpu_uuids
    from live_identity import cpu_topology,cores
    devices=gpu_uuids(4);top=cpu_topology();slots=cpu_slots(top)
    service=read(R/f'block-{block}/service-native.json')
    assert not set(devices)&set(service['gpu_uuids']) and not cores(top)&cores(service['cpu_topology'])
    if block:
        old=read(R/'block-0/execution-native.json')
        assert set(devices)==set(old['gpu_uuids']) and slots==old['cpu_slots']
        devices=old['gpu_uuids']
    native=dict(job=os.environ['SLURM_JOB_ID'],step=os.environ['SLURM_STEP_ID'],gpu_uuids=devices,cpu_topology=top,cpu_slots=slots)
    write(R/f'block-{block}/execution-native.json',native)
    assert all(not base.c.trial.t.gpu_sample(g)['pids'] for g in devices)
    if block==0:qualification(native)
    assert read(R/'dispatch-qualification.json')['passed']
    pool.initialize(R/f'pool-{block}',ORDER[block])
    rows=[r for r in schedule() if r['block']==block]
    samples=[];errors=[];stop=threading.Event()
    def observe():
        while not stop.is_set():
            try:samples.append(dict(time=time.time(),devices=[base.c.trial.t.gpu_sample(g) for g in devices]))
            except Exception as e:errors.append(type(e).__name__);break
            stop.wait(2)
    thread=threading.Thread(target=observe,daemon=True);thread.start()
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as workers:
            results=list(workers.map(base.c.trial.t.run_one,rows))
    finally:stop.set();thread.join(45)
    events=[json.loads(x) for x in (R/f'pool-{block}/events.jsonl').read_text().splitlines()]
    audit=pool.audit(events,ORDER[block]);clean=all(not base.c.trial.t.gpu_sample(g)['pids'] for g in devices)
    write(R/f'block-{block}/execution-telemetry.json',samples)
    write(R/f'block-{block}/execution-closed.json',dict(results=results,queue_audit=audit,gpu_clean=clean,telemetry_errors=errors))
    assert clean and not errors and not thread.is_alive() and audit['all_released'] and all(r['cleanup_verified'] for r in results)
    for row in rows:
        ep=R/f"episode-{row['index']}"
        from weight_confirmation_readout_20261014 import runtime_inputs
        # Full runtime input check is also independently repeated at readout.
        if not runtime_inputs(R,read(R/'plan.json'),[row])[0]['passed']:
            raise RuntimeError('runtime input drift; no next pool')


def controller():
    base.c.trial.check();base.c.trial.activate_helpers();m=host();m.setup()
    job=os.environ['SLURM_JOB_ID'];start=time.monotonic();server=None;worker_proc=None;logs=[];attempted=[];error=None
    for _ in range(40):
        if (R/'launch.json').exists():break
        time.sleep(.25)
    assert read(R/'launch.json')['job']==job
    env=m.infra().clean_env();cmd=['srun','--exclusive','--nodes=1','--ntasks=1','--hint=nomultithread']
    try:
        log=(R/'block-0/service.private.log').open('xb');logs.append(log)
        server=subprocess.Popen(cmd+['--cpus-per-task=8','--gres=gpu:2','--time=01:39:00',str(base.c.trial.PY),'-B',str(R/NAME),'service'],env=env,stdout=log,stderr=log,start_new_session=True)
        while time.monotonic()-start<600:
            if server.poll() is not None:raise RuntimeError('service died')
            try:
                if 'qwen3.8-27b' in {x['id'] for x in m.api('/v1/models')['data']}:break
            except Exception:pass
            time.sleep(2)
        else:raise TimeoutError('service startup')
        write(R/'service-ready.json',dict(startup_seconds=time.monotonic()-start))
        for block in range(4):
            if CAP-(time.monotonic()-start)<SLOT+100:raise TimeoutError('no complete slot left')
            bd=R/f'block-{block}'
            if block:write(bd/'service-native.json',read(R/'block-0/service-native.json'))
            parent.initialize(R/f'generation-{block}',[r for r in schedule() if r['block']==block],read(R/'warm.private.json'))
            begin=time.monotonic();wall=time.time();attempted.append(block)
            log=(bd/'executor.private.log').open('xb');logs.append(log)
            worker_proc=subprocess.Popen(cmd+['--cpus-per-task=16','--gres=gpu:4','--time=00:24:00',str(base.c.trial.PY),'-B',str(R/NAME),'executor','--block',str(block)],env=env,stdout=log,stderr=log,start_new_session=True)
            # Qualification is common initialization charged to the allocation,
            # not charged only to the first fixed arm's1180s search slot.
            if block==0:
                while not (R/'dispatch-qualification.json').exists():
                    if worker_proc.poll() is not None:raise RuntimeError('dispatch qualification failed')
                    if time.monotonic()-begin>240:raise TimeoutError('dispatch qualification timeout')
                    time.sleep(.2)
                begin=time.monotonic();wall=time.time()
            while worker_proc.poll() is None:
                if server.poll() is not None:raise RuntimeError('model died')
                if time.monotonic()-begin>SLOT-25:raise TimeoutError('pool cleanup deadline')
                time.sleep(1)
            write(bd/'steps.json',dict(returncodes=[worker_proc.returncode]))
            assert worker_proc.returncode==0,'executor failed; stop all remaining pools'
            gs=read(R/f'generation-{block}/state.json');assert not gs['active'] and not gs['waiting']
            active=time.monotonic()-begin
            while time.monotonic()-begin<SLOT:time.sleep(min(1,SLOT-(time.monotonic()-begin)))
            write(bd/'budget-slot.json',dict(reserved_seconds=SLOT,actual_seconds=time.monotonic()-begin,active_seconds=active,start=wall,gpus=6))
    except BaseException as e:
        error=dict(type=type(e).__name__,frames=[dict(file=Path(f.filename).name,line=f.lineno,function=f.name) for f in traceback.extract_tb(e.__traceback__)])
        raise
    finally:
        if worker_proc is not None and worker_proc.poll() is None:
            worker_proc.terminate()
            try:worker_proc.wait(timeout=20)
            except subprocess.TimeoutExpired:os.killpg(worker_proc.pid,signal.SIGKILL);worker_proc.wait(timeout=10)
        if server is not None:base.c.trial.t.stop_service(server,0,job)
        for log in logs:log.close()
        rows=[]
        for row in schedule():
            ep=R/f"episode-{row['index']}";out=dict(row,source_commit=read(R/'plan.json')['source_commit'],status='not_started')
            if (ep/'closed.json').exists():out.update(read(ep/'closed.json'));out['status']='incomplete'
            if (ep/'finished.json').exists():
                out.update(read(ep/'finished.json'))
                out['status']='complete' if out.get('returncode')==0 and out.get('cleanup_verified') and out['status'] in ('completed','budget_exhausted') else 'incomplete'
            rows.append(out)
        write(R/'runs.json',rows)
        with (R/'runs.csv').open('x',newline='') as f:
            w=csv.DictWriter(f,fieldnames=sorted({k for r in rows for k in r}));w.writeheader();w.writerows(rows)
        write(R/'closed.json',dict(planned=32,attempted_blocks=attempted,complete=sum(r['status']=='complete' for r in rows),error=error,elapsed_seconds=time.monotonic()-start))


def prepare(commit):
    assert re.fullmatch('[a-f0-9]{40}',commit) and sha(DONOR/'plan.json')==DONOR_SHA
    assert read(DONOR/'closed.json')['complete']==48
    p=read(DONOR/'plan.json');assert all(sha(DONOR/n)==h for n,h in p['files'].items())
    assert sha(DONOR/'public-preview.private.json')==BUNDLE_SHA
    preview=read(DONOR/'public-preview.private.json')
    for task,v in preview['tasks'].items():
        assert digest(public_manifest(v['public_path']))==v['public_manifest_sha256']
        load_text(DONOR/'public-preview.private.json',BUNDLE_SHA,task)
    R.mkdir(mode=0o700)
    inherited=[n for n in p['files'] if not n.startswith(('configs/','input-matrix/')) and n!='preparation-plan.json']
    for n in inherited:
        assert not n.endswith('.env')
        dst=R/n;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(DONOR/n,dst)
    (R/'dev-views').symlink_to((DONOR/'dev-views').resolve(),target_is_directory=True)
    (R/'configs').mkdir()
    for b in range(4):(R/f'block-{b}/service-cache/tmp').mkdir(parents=True)
    change=base.c.trial.change
    scorer=R/'image_scorer.py';scorer.write_text(scorer.read_text().replace(str(DONOR),str(R)))
    for row in schedule():
        i=row['index'];ep=R/f'episode-{i}';(ep/'work/input_cache').mkdir(parents=True)
        cfg=json.loads(json.dumps(read(DONOR/f"configs/{row['slot']}.json")).replace(str(DONOR),str(R)).replace(f"episode-{row['slot']}/",f'episode-{i}/'))
        cfg['id']=f'pooling-{i}';cfg['metadata'].update(seed=row['seed'],script_id='pooling-20261015')
        cfg['solver']['time_limit_secs']=RUN
        cfg['interpreter']['env']['PYTHONHASHSEED']=str(row['seed'])
        cfg['task']['search_only_dev_scorer_sha256']=sha(scorer)
        for role,op in cfg['solver']['operators'].items():
            e=policy.effort('old_fast',role)
            op['llm']['client']['model_id']=policy.model('old_fast')
            op['llm']['generation_kwargs'].update(seed=row['seed'],reasoning_effort=e)
            op['llm']['generation_kwargs']['extra_body']['chat_template_kwargs']['enable_thinking']=e!='none'
        write(R/f'configs/{i}.json',cfg)
    driver=R/'image_live_2plus4_20261011.py'
    s=change(driver.read_text(),"TIME_LIMIT='30 minutes',TIME_LIMIT_SECS='1800'","TIME_LIMIT='17 minutes',TIME_LIMIT_SECS='1020'")
    driver.write_text(change(s,"'timeout=1890'","'timeout=1110'"))
    cpu=R/'fixed_preview_native_cpu_20261014.py'
    s=change(cpu.read_text(),"TIME_LIMIT='30 minutes', TIME_LIMIT_SECS='1800'","TIME_LIMIT='17 minutes', TIME_LIMIT_SECS='1020'")
    cpu.write_text(s)
    for n in NAMES:shutil.copyfile(Path(__file__).with_name(n),R/n)
    shim=R/'bin/singularity'
    shim.write_text(f'#!{base.c.trial.PY}\nimport sys\nsys.path.insert(0,{str(R)!r})\nfrom {Path(__file__).stem} import task_runtime\ntask_runtime()\n');shim.chmod(0o700)
    with (R/'.service.env').open('x') as f:f.write('PRIMARY_KEY_QWEN3_8_27B='+secrets.token_hex(32)+'\n')
    (R/'.service.env').chmod(0o600)
    sb=R/'run.sbatch';s=sb.read_text().replace(str(DONOR),str(R))
    s=change(s,'r14-metric-deploy','r14-pooling')
    s=change(s,'metric_deployment_trial_20261015.py controller',NAME+' controller')
    s=change(s,'#SBATCH --time=03:45:00','#SBATCH --time=01:40:00')
    sb.write_text(change(s,'13440s','5940s'));subprocess.run(['bash','-n',str(sb)],check=True)
    for cache in ('vllm','triton'):
        src=DONOR/'block-0/service-cache'/cache
        if src.is_dir():shutil.copytree(src,R/'block-0/service-cache'/cache,symlinks=True)
    p.update(source_commit=commit,source_parent_commit=p['source_commit'],source_donor_plan_sha256=DONOR_SHA,
        schedule=schedule(),planned=32,native_trial_module=Path(__file__).stem,independent_pool_pairs=2,
        allocation_seconds=CAP,gpu_hours_cap=10,combined_gpu_seconds_cap=36000,new_window_gpu_seconds_cap=36000,
        prior_failures=[],run_seconds=RUN,slot_seconds=SLOT,
        approval='Explicit user approval2026-10-15HK:32 runs,2service+4execution,<=6000seconds including qualification/startup/failure/cleanup,<=10GPUh. No retry.',
        primary='Task-best externally validated returned solution within each1020s trajectory deadline, aggregated over its four-run pool; common warm incumbent included. Run-level best/median/SD and native-selected endpoint separate. Fixed vs shared FIFO, same initial history/seeds/old-fast generator.',
        single_change='Fixed GPU eligibility vs any free execution GPU. Both use common4GPU Slurm step, exact single-device namespace, lease before startup through cleanup, fixed2physical CPU cores/run. No duration/score/identity prediction.',
        advance='All32complete; input/isolation/dispatch/cleanup/cost gates pass; shared denoising pool-best improves fixed by>=.001 in BOTH reverse repeats and aerial pool-best nondeclines in BOTH. Report medians/SD/all endpoints regardless. No interim quality or pooled rescue.',
        limitation='Standard FIFO pooling is NOT novelty. Exploratory strong-baseline qualification on reused development tasks; two pool repeats share one service, not32 independent replicates. Warm starts and public preview are common sunk inputs. No training or history-transfer gain.',
        stop='Fixed32; infrastructure/input/namespace/dispatch/cleanup failure stops remaining pools. No substitution/retry or old-budget reuse.',
        common_execution_change='Both arms now share4GPU host step but sandbox mounts exactly one GPU. CPU affinity fixed by run, never migrated. Admit before startup in BOTH arms; unlike historical traces. Real capability and namespace gate before search.',
        public_preview_sha256=BUNDLE_SHA,common_preview_preparation_wall_seconds=preview['preparation_wall_seconds'])
    write(R/'preparation-plan.json',dict(source_commit=commit,native_trial_module=p['native_trial_module'],schedule=schedule()))
    cp=subprocess.run([str(base.c.trial.PY),'-B',str(R/'fixed_preview_cpu_matrix_20261014.py'),str(R),str(R/'public-preview.private.json'),str(R/'input-matrix')],cwd=R,capture_output=True)
    (R/'input-preflight.private.log').write_bytes(cp.stdout+cp.stderr)
    if cp.returncode:raise RuntimeError('native CPU matrix failed; no submission')
    matrix=read(R/'input-matrix/summary.safe.json')
    assert matrix['assigned']==matrix['passed']==32 and matrix['exact_input_gate'] and len(matrix['paired_groups'])==16
    p['files']={n:sha(R/n) for n in inherited}
    p['files'].update({f'configs/{i}.json':sha(R/f'configs/{i}.json') for i in range(32)})
    p['files'].update({n:sha(R/n) for n in NAMES+('preparation-plan.json','input-matrix/summary.safe.json')})
    write(R/'plan.json',p)
    cp=subprocess.run([str(base.c.trial.PY),'-B',str(R/NAME),'preflight'],cwd=R,capture_output=True)
    (R/'preflight.private.log').write_bytes(cp.stdout+cp.stderr)
    if cp.returncode:raise RuntimeError('frozen CPU preflight failed; no submission')
    print(json.dumps(read(R/'preflight.json')))


def preflight():
    p=base.c.trial.check()
    assert len(schedule())==32 and p['gpu_hours_cap']==10
    for row in schedule():
        ref=next(r for r in schedule() if r['seed']==row['seed'] and r['pool_mode']=='fixed')
        a,b=(read(R/f"configs/{r['index']}.json") for r in (row,ref))
        assert base.c.trial.t.scientific(a)==base.c.trial.t.scientific(b)
        assert a['solver']['time_limit_secs']==1020 and a['interpreter']['timeout']==300
        for role,op in a['solver']['operators'].items():
            kw=op['llm']['generation_kwargs']
            assert op['llm']['client']['model_id']=='qwen3.8-27b'
            assert kw['reasoning_effort']==policy.effort('old_fast',role)
            assert kw['max_tokens']==(8192 if role=='analyze' else 32768)
    subprocess.run([str(base.c.trial.PY),'-B','-m','unittest','test_shared_pool_20261015',
                    'test_pooling_qualification_20261015','test_fixed_public_preview_20261014','-v'],cwd=R,check=True)
    write(R/'cpu.json',dict(plan_sha256=sha(R/'plan.json'),configs=32,exact_inputs=True,no_gpu=True))
    write(R/'preflight.json',dict(source_commit=p['source_commit'],plan_sha256=sha(R/'plan.json'),configs=32,
        exact_input_gate=True,gpu_hours_cap=10,no_gpu=True,no_model_calls=True))
    print(json.dumps(read(R/'preflight.json')))


configure()
if __name__=='__main__':
    os.umask(0o077);os.environ.update(PYTHON_DOTENV_DISABLED='1',PYTHONDONTWRITEBYTECODE='1')
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['prepare','preflight','submit','controller','service','executor','worker'])
    ap.add_argument('--commit');ap.add_argument('--block',type=int);ap.add_argument('--index',type=int);a=ap.parse_args()
    if a.mode=='prepare':prepare(a.commit)
    elif a.mode=='submit':base.c.submit()
    elif a.mode=='service':base.c.trial.service(0)
    elif a.mode=='executor':executor(a.block)
    elif a.mode=='worker':worker(a.index)
    else:globals()[a.mode]()
