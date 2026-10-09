"""R14: fixed live MCTS, one vs two sandbox execution leases, <=4.5 GPUh.

16 assigned 600s native trajectories; 4 independent runs per block, ABBA blocks.
The established Pizza/Spooky development adapters are used, not protected/test
cohorts. This is a new workload scope, not a neural-workload replication.
"""
import argparse
import ast
import copy
import csv
import hashlib
import importlib.util
import inspect
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from lifecycle_pilot import read, write, sha
from live_admission import initialize, audit_events
from live_runtime_hooks import install as install_hooks

B=Path('/research/d7/spc/yzyang4')
R=B/'scheduling-live-search-20261009-v1'
D=B/'policy9b-paired-20261005-gpu27-v1'
PY=B/'venvs/aira/bin/python'
NAME='live_search_trial_20261009.py'
DONOR_PLAN='12d1264457158c936e4f1eff8e9c844ce5044365e77056066c4ded2ecfe6cd79'
DONOR_RUNTIME='b422a17094a6971218731054b53b56888505150b82f5309990b0b629577da4c9'
CAP=5400
MODEL_ID='qwen3.5-9b'
MODEL_DIR=B/'models/Qwen3.5-9B-c202236'
PROFILE='9b'
NODE='gpu27'
NODE_QUALIFICATION=False
SEED_BASE=140901
GENERATOR_ELIGIBILITY_GATE=True
FIXED_BLOCK_SECONDS=0
SERVICE27=B/'task-feedback-real-20261001-v6/service_entry.py'
SERVICE27_SHA='cd9e143abe79cdc71c97db3dba07930e0642b28faf52ac4f6b2ca5ba36a8379a'
TASKS=('random-acts-of-pizza','spooky-author-identification')
FILES=(NAME,'live_admission.py','live_runtime_hooks.py','bounded_readiness.py','lifecycle_pilot.py')


class GeneratorEligibilityFailed(RuntimeError):pass


def schedule():
    rows=[]
    for rep in range(2):
        for arm in (('pipeline','share2') if rep==0 else ('share2','pipeline')):
            block=len(rows)//4
            for slot in range(4):
                rows.append(dict(index=len(rows),block=block,arm=arm,repeat=rep,
                    slot=slot,task=TASKS[slot%2],seed=SEED_BASE+100*rep+slot))
    return rows


def replace_once(source,before,after):
    if source.count(before)!=1:raise ValueError('exact native insertion changed')
    return source.replace(before,after)


def host():
    path=R/'runtime.py'
    if sha(path)!=DONOR_RUNTIME:raise ValueError('donor runtime drift')
    spec=importlib.util.spec_from_file_location('live_fixed_host',path)
    m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
    m.R=R;m.CAP=CAP;m.SECONDS=600;m.schedule=schedule;m.check=check;m.install_hooks=install_hooks
    source=inspect.getsource(m.worker)
    source=replace_once(source,"deadline=ExperimentDeadline(SECONDS);write(ep/'deadline.json',deadline.receipt())",
        "deadline=ExperimentDeadline(SECONDS);write(ep/'deadline.json',deadline.receipt())\n    install_hooks(s,ep,deadline)")
    source=replace_once(source,"read(R/'service-native.json')", "read(R/f'block-{s[\"block\"]}/service-native.json')")
    source=replace_once(source,'PRIMARY_KEY=key,PRIMARY_KEY_QWEN3_5_9B=key',
        'PRIMARY_KEY=key,PRIMARY_KEY_QWEN3_8_27B=key,PRIMARY_KEY_QWEN3_5_9B=key')
    exec(compile(source,'live-native-worker','exec'),m.__dict__)
    episode_pattern='episode-(?:[0-9]|1[0-5]|qualification)' if NODE_QUALIFICATION else 'episode-(?:[0-9]|1[0-5])'
    source=replace_once(inspect.getsource(m.task_runtime),'episode-[0-7]',episode_pattern)
    exec(compile(source,'live-native-runtime','exec'),m.__dict__)
    source=inspect.getsource(m.service)
    for old,new in (("R/'service-native.json'","R/f'block-{os.environ[\"R14_BLOCK\"]}/service-native.json'"),
                    ("R/'service-cache/tmp'","R/f'block-{os.environ[\"R14_BLOCK\"]}/service-cache/tmp'"),
                    ("R/'service-cache'","R/f'block-{os.environ[\"R14_BLOCK\"]}/service-cache'")):
        source=replace_once(source,old,new)
    exec(compile(source,'live-native-service','exec'),m.__dict__)
    if PROFILE=='27b':
        m.service=service27
        m.health=lambda:set(x['id'] for x in m.api('/v1/models')['data'])=={MODEL_ID}
    return m


def service27():
    check();m=host();x=m.infra();block=os.environ['R14_BLOCK']
    if socket.gethostname().split('.')[0]!=NODE:raise ValueError('wrong service node')
    with socket.socket() as probe:probe.bind(('127.0.0.1',m.PORT))
    devices=x.native_uuids(2)
    extra={}
    if FIXED_BLOCK_SECONDS:
        from live_identity import cpu_topology
        extra['cpu_topology']=cpu_topology()
    write(R/f'block-{block}/service-native.json',dict(job=os.environ['SLURM_JOB_ID'],
        step=os.environ['SLURM_STEP_ID'],gpu_uuids=devices,**extra))
    cmd=['/usr/bin/singularity','exec','--containall','--cleanenv','--no-home','--nv','--no-mount','bind-paths,cwd',
        '--bind',str(MODEL_DIR)+':/model:ro','--bind',str(R/'service-cache')+':/cache:rw',
        '--bind',str(R/'service-cache/tmp')+':/tmp:rw','--bind',str(R/'service_entry.py')+':/run/service_entry.py:ro',
        '--pwd','/cache',str(m.VLLM),'/usr/bin/python3','/run/service_entry.py']
    values=dict(CUDA_VISIBLE_DEVICES=','.join(devices),EXPECTED_GPU_UUIDS=','.join(devices),VLLM_API_KEY=x.local_key(),
        VLLM_WORKER_MULTIPROC_METHOD='spawn',VLLM_CACHE_ROOT='/cache/vllm',TRITON_HOME='/cache/triton',TORCH_HOME='/cache/torch',
        HF_HOME='/cache/hf',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',FLASHINFER_WORKSPACE_BASE='/cache/flashinfer',
        XDG_CACHE_HOME='/cache/xdg',TMPDIR='/tmp',MAX_JOBS='2',VLLM_NO_USAGE_STATS='1',VLLM_CONFIG_ROOT='/cache/vllm-config')
    env={k:os.environ[k] for k in ('PATH','HOME','USER','LOGNAME') if k in os.environ}
    env.update({'SINGULARITYENV_'+k:v for k,v in values.items()});os.execve(cmd[0],cmd,env)


def check():
    p=read(R/'plan.json')
    if p['schedule']!=schedule() or p['allocation_seconds']!=CAP or p['gpus']!=3:
        raise ValueError('frozen matrix')
    if p.get('node','gpu27')!=NODE:raise ValueError('placement changed')
    if p.get('fixed_block_seconds',0)!=FIXED_BLOCK_SECONDS or p.get('generator_eligibility_gate',True)!=GENERATOR_ELIGIBILITY_GATE:
        raise ValueError('budget/eligibility protocol changed')
    for name,pin in p['files'].items():
        if sha(R/name)!=pin:raise ValueError('frozen file drift')
    return p


def scientific(cfg):
    c=copy.deepcopy(cfg)
    for key in ('id','metadata','logger'):c.pop(key,None)
    for key in ('checkpoint_path','exp_name'):c['solver'].pop(key,None)
    c['task'].pop('results_output_dir',None)
    c['interpreter'].pop('working_dir',None)
    return c


def prepare(commit):
    if not re.fullmatch('[a-f0-9]{40}',commit) or sha(D/'plan.json')!=DONOR_PLAN:
        raise ValueError('exact provenance')
    old=read(D/'plan.json')
    if not read(D/'closed.json')['service_closed']:raise ValueError('donor not closed')
    R.mkdir(mode=0o700,exist_ok=False)
    helpers=('forets_gpu_binding_20260911.py','forets_native_cuda_identity_20260911.py',
        'forets_native_gpu_binding_20260911.py','forets_opencl_allowlist_20260911.py',
        'forets_opencl_readonly_ab.py','service_entry.py')
    for name,pin in old['files'].items():
        if not (name.startswith('source/') or name in helpers):continue
        if sha(D/name)!=pin:raise ValueError('donor file drift')
        dst=R/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(D/name,dst)
    if sha(D/'policy9b_paired_20261005.py')!=DONOR_RUNTIME:raise ValueError('donor runtime')
    shutil.copyfile(D/'policy9b_paired_20261005.py',R/'runtime.py')
    for name in FILES:shutil.copyfile(Path(__file__).with_name(name),R/name)
    if NODE!='gpu27':
        path=R/'forets_native_cuda_identity_20260911.py'
        path.write_text(replace_once(path.read_text(),"split('.')[0]!='gpu27'",f"split('.')[0]!={NODE!r}"))
    for d in ('configs','bin','opencl-vendors'):(R/d).mkdir()
    (R/'service-cache/tmp').mkdir(parents=True)
    if NODE_QUALIFICATION:
        (R/'episode-qualification/work').mkdir(parents=True)
        (R/'qualification-empty-data').mkdir()
    model_files={}
    if PROFILE=='27b':
        if sha(SERVICE27)!=SERVICE27_SHA:raise ValueError('local 27B entry changed')
        service=replace_once(SERVICE27.read_text(),"'--port','19441'","'--port','19475'")
        (R/'service_entry.py').write_text(service)
        for file in MODEL_DIR.iterdir():
            if file.is_file() and file.suffix in ('.json','.safetensors','.model','.txt'):
                model_files[str(file)]=sha(file)
        if not any(p.endswith('.safetensors') for p in model_files):raise ValueError('missing local model weights')
    (R/'opencl-vendors/nvidia.icd').write_text('libnvidia-opencl.so.1\n')
    (R/'bin/singularity').write_text(f'#!{PY}\nimport sys\nsys.path.insert(0,{str(R)!r})\nfrom {Path(NAME).stem} import host\nhost().task_runtime()\n')
    os.chmod(R/'bin/singularity',0o700)
    with (R/'.service.env').open('x') as f:f.write('PRIMARY_KEY_QWEN3_8_27B='+secrets.token_hex(32)+'\n')
    os.chmod(R/'.service.env',0o600)
    configs=[];public_inputs={}
    for row in schedule():
        ep=R/f'episode-{row["index"]}';ep.mkdir()
        old_name=f'configs/{row["slot"]%2}.json'
        if sha(D/old_name)!=old['files'][old_name]:raise ValueError('donor config')
        cfg=read(D/old_name)
        if cfg['task']['name']!=row['task']:raise ValueError('task mapping')
        cfg['id']='r14-live-'+str(row['index'])
        cfg['metadata'].update(seed=row['seed'],script_id='r14-live-20261009',base_path=str(R/'source'))
        cfg['logger'].update(output_dir=str(ep/'native-log'),write_env_vars=False,use_console=False,
                             print_config=False,use_wandb=False)
        cfg['solver']['checkpoint_path']=str(ep/'checkpoint')
        cfg['task']['results_output_dir']=str(ep/'native-task-results')
        cfg['task']['cache_dir']=str(R/'no-official-data')
        cfg['interpreter']['working_dir']=str(ep/'work')
        cfg['interpreter']['env']['PYTHONHASHSEED']=str(row['seed'])
        for op in cfg['solver']['operators'].values():
            op['llm']['client']['model_id']=MODEL_ID
            op['llm']['generation_kwargs']['seed']=row['seed']
        write(R/f'configs/{row["index"]}.json',cfg);configs.append(cfg)
        scorer=Path(cfg['task']['search_only_dev_scorer_path'])
        if sha(scorer)!=cfg['task']['search_only_dev_scorer_sha256'] or Path(cfg['task']['private_dir']).exists():
            raise ValueError('dev scoring/isolation changed')
        public_inputs[str(scorer)]=sha(scorer)
        for file in Path(cfg['task']['public_dir']).rglob('*'):
            if file.is_file():public_inputs[str(file)]=sha(file)
    for block in range(4):(R/f'block-{block}/service-cache/tmp').mkdir(parents=True)
    for rep in range(2):
        for slot in range(4):
            i=rep*8+slot;j=i+4
            if scientific(configs[i])!=scientific(configs[j]):raise ValueError('unequal paired configuration')
    batch=f'''#!/bin/bash
#SBATCH --job-name=r14-live-admission
#SBATCH --partition=gpu_24h
#SBATCH --account=gpu
#SBATCH --qos=gpu
#SBATCH --nodelist={NODE}
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:3
#SBATCH --cpus-per-task=18
#SBATCH --time=01:30:00
#SBATCH --no-requeue
set -euo pipefail
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1
timeout --signal=TERM --kill-after=20s 5320s {PY} -B {R/NAME} controller
'''
    (R/'run.sbatch').write_text(batch)
    write(R/'plan.json',dict(source_commit=commit,source_dojo_commit=old['source_commit'],
        donor_plan_sha256=DONOR_PLAN,schedule=schedule(),gpus=3,total_cpu=18,node=NODE,
        node_qualification_required=NODE_QUALIFICATION,
        gateway_contract='Unique job/run-index gateway ports; all workers share the same native Slurm step but not a server port.',
        service_gpus=2,execution_gpus=1,service_cpu=12,execution_cpu=6,
        allocation_seconds=CAP,gpu_hours_cap=4.5,run_seconds=600,candidate_timeout_seconds=240,
        active_runs=4,rolling_replacement=False,service_restart_between_blocks=True,
        fixed_block_seconds=FIXED_BLOCK_SECONDS,generator_eligibility_gate=GENERATOR_ELIGIBILITY_GATE,
        independent_question=('Unfiltered feedback throughput at equal whole-pool reserved slot time; invalid endpoints retained. '
            'No outcome-dependent continuation. Final-score effects only where both endpoints exist; never impute missing quality.'
            if FIXED_BLOCK_SECONDS else None),
        throughput_signal=('All16 workers close cleanly, all4 structure and equal-slot audits pass, both paired pool blocks '
            'strictly increase valid timely candidate returns, and neither pool reduces valid-endpoint count. '
            'This is feedback-throughput evidence only; final-quality exploratory_go remains the stricter original rule.'
            if FIXED_BLOCK_SECONDS else None),
        source_model=str(MODEL_DIR),base_revision=old['base_revision'] if PROFILE=='9b' else None,used_model=MODEL_ID,
        model_files=model_files,profile=PROFILE,service_adapter_loaded=PROFILE=='9b',
        service_compile_cache_common=PROFILE=='27b',service_kv_cache_reset_by_process_restart=True,
        qualification=('Only image/safety qualifications. Complete all16 regardless of generator validity; stop on infrastructure/cleanup failure, retain16, no seed replacement.' if not GENERATOR_ELIGIBILITY_GATE else 'For 27B only: after the first pipeline block, require all four clean workers and finite valid native-selected dev endpoints. Otherwise stop the assigned batch, retain all16 denominator, no replacement seeds. Any full comparison is conditional exploratory evidence.'),
        adapter_unused=True,task_image_sha256=old['task_image_sha256'],
        service_image_sha256=old['service_image_sha256'],model_training=False,paid_api=False,
        single_change='FIFO execution lease limit 1 versus 2; both overlap startup and preserve native within-run MCTS order.',
        common_adapter='Close preview and failed task kernels before lease release; queue counted in 600s deadline but excluded from execution-duration feedback. Bounded info-only handshake common.',
        primary='Full assigned 16-run denominator: valid task.step candidate returns recorded by common 600s deadline, infrastructure failures, queue/ready/generation time, selected development score only where observed. A scored receipt without a completed task return does not count. No imputation of missing quality.',
        inference='Pool block is the scheduling intervention unit: only two paired block repeats. Run counts are not independent scheduling replications. No population significance or neural generalization claim.',
        advance='Exploratory go only if all 16 endpoints, all 8 pairs of finite valid native-selected dev scores, and cleanup/audits complete, both paired pool blocks yield strictly more valid dev returns under share2, and per-task paired selected dev score medians are nonnegative with no additional infrastructure failures. Otherwise do not rescue with replacement seeds.',
        boundary='Pizza and Spooky development workloads, not the reused neural fixed-program experiment; no protected cohorts, D_val, official test, critic or policy training.',
        allocation_accounting='Count all three reserved GPUs including model startup, idle/queue and failure; no reuse of old batch budgets.',
        public_inputs=public_inputs,
        files={str(p.relative_to(R)):sha(p) for p in R.rglob('*') if p.is_file() and p.name!='.service.env'}))
    cpu()
    m=host()
    if sha(m.TASK_IMAGE)!=old['task_image_sha256'] or sha(m.VLLM)!=old['service_image_sha256']:
        raise ValueError('image drift')
    if PROFILE=='9b' and sha(m.ADAPTER/'adapter_model.safetensors')!=old['adapter_weights_sha256']:
        raise ValueError('service unused-adapter binding drift')
    write(R/'preflight.json',dict(plan_sha256=sha(R/'plan.json'),model_calls=0,gpu_executions=0,
        images_verified=True,paired_configs=8,service_restarts=4))
    print(json.dumps(dict(status='PREPARED',plan_sha256=sha(R/'plan.json'),runs=16,gpu_hours_cap=4.5)))


def cpu():
    p=check();m=host();m.setup()
    from dojo.config_dataclasses.run import RunConfig
    from dojo.tasks.mlebench.task import MLEBenchTask
    from dojo.solvers.mcts.mcts import MCTS
    from dojo.core.tasks.constants import TASK_DESCRIPTION
    from dojo.utils.logger import config_logger
    from omegaconf import OmegaConf
    os.environ['PRIMARY_KEY']='offline-fixture'
    os.environ['PRIMARY_KEY_QWEN3_5_9B']='offline-fixture'
    os.environ['PRIMARY_KEY_QWEN3_8_27B']='offline-fixture'
    for row in schedule():
        cfg=RunConfig.load_from_json(R/f'configs/{row["index"]}.json');cfg.validate();config_logger(cfg)
        task=MLEBenchTask(cfg.task)
        if task._search_only_score is None or task.private_dir.exists() or cfg.solver.use_test_score:
            raise ValueError('not dev-only')
        solver=MCTS(OmegaConf.structured(cfg.solver),{TASK_DESCRIPTION:task.task_description,'lower_is_better':task._search_only_lower_is_better})
        if solver.journal.nodes or cfg.solver.time_limit_secs!=600 or cfg.interpreter.timeout!=240:
            raise ValueError('not fresh fixed run')
        for op in cfg.solver.operators.values():
            if op.llm.client.model_id!=MODEL_ID or op.llm.generation_kwargs['seed']!=row['seed']:
                raise ValueError('model/seed contract')
    subprocess.run(['bash','-n',str(R/'run.sbatch')],check=True)
    write(R/'cpu.json',dict(configs=16,native_solvers_instantiated=16,model_calls=0,plan_sha256=sha(R/'plan.json')))


def submit():
    if (R/'withdrawn.json').exists():raise ValueError('pre-submission withdrawal; do not run')
    check()
    if read(R/'preflight.json')['plan_sha256']!=sha(R/'plan.json'):raise ValueError('preflight mismatch')
    env=host().infra().clean_env()
    jobs=subprocess.check_output(['squeue','-u','yzyang4','-h','-o','%i'],env=env,text=True,timeout=15).split()
    if set(jobs)-{'12535'}:raise ValueError('unexpected active job')
    write(R/'submit-intent.json',dict(plan_sha256=sha(R/'plan.json'),gpu_hours_cap=4.5))
    out=subprocess.run(['sbatch','--parsable','--chdir='+str(R),'--output='+str(R/'allocation-%j.out'),
        '--error='+str(R/'allocation-%j.err'),str(R/'run.sbatch')],env=env,capture_output=True,text=True,timeout=25)
    job=out.stdout.strip().split(';')[0]
    if out.returncode or not job.isdigit():raise RuntimeError('ambiguous submit; do not retry')
    write(R/'launch.json',dict(job=job,plan_sha256=sha(R/'plan.json')))
    print(json.dumps(dict(status='SUBMITTED',job=job,gpu_hours_cap=4.5)))


def owned_cleanup(process,ep):
    from dojo.main_local_worker import _process_start_ticks
    if (ep/'identity.json').exists():
        identity=read(ep/'identity.json');pid=identity.get('container_pid');ticks=identity.get('container_process_start_ticks')
        try:
            if pid and ticks and _process_start_ticks(pid)==ticks and os.getpgid(pid)==identity.get('container_pgid'):
                os.killpg(os.getpgid(pid),signal.SIGTERM);time.sleep(1)
                if _process_start_ticks(pid)==ticks:os.killpg(os.getpgid(pid),signal.SIGKILL)
        except ProcessLookupError:pass # it exited between identity check and signal
    if process.poll() is None:
        try:os.killpg(process.pid,signal.SIGTERM)
        except ProcessLookupError:pass
        try:process.wait(timeout=3)
        except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait(timeout=3)


def process_gone(pid,ticks):
    if not pid or not ticks:return True
    try:
        v=Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()
        return v[0]=='Z' or int(v[19])!=ticks
    except FileNotFoundError:return True


def run_one(row):
    ep=R/f'episode-{row["index"]}';start=time.time()
    with (ep/'worker.private.log').open('xb') as log:
        proc=subprocess.Popen([str(PY),'-B',str(R/NAME),'worker','--index',str(row['index'])],
            stdout=log,stderr=log,start_new_session=True)
        try:rc=proc.wait(timeout=690)
        except subprocess.TimeoutExpired:owned_cleanup(proc,ep);rc=124
    if (ep/'identity.json').exists():
        identity=read(ep/'identity.json')
        clean=all(process_gone(identity.get(p),identity.get(t)) for p,t in
            (('pid','process_start_ticks'),('container_pid','container_process_start_ticks')))
    else:clean=False
    if not clean:
        owned_cleanup(proc,ep)
        if (ep/'identity.json').exists():
            identity=read(ep/'identity.json')
            clean=all(process_gone(identity.get(p),identity.get(t)) for p,t in
                (('pid','process_start_ticks'),('container_pid','container_process_start_ticks')))
    result=dict(index=row['index'],returncode=rc,cleanup_verified=clean,start=start,end=time.time(),
        finished=(ep/'finished.json').exists())
    write(ep/'closed.json',result)
    return result


def gpu_sample(gpu):
    raw=subprocess.check_output(['nvidia-smi','--id='+gpu,'--query-gpu=utilization.gpu,memory.used',
        '--format=csv,noheader,nounits'],text=True,timeout=10).strip().split(',')
    apps=subprocess.check_output(['nvidia-smi','--query-compute-apps=gpu_uuid,pid',
        '--format=csv,noheader,nounits'],text=True,timeout=10).splitlines()
    pids=[int(v.split(',')[1]) for v in apps if v.split(',')[0].strip()==gpu]
    return dict(time=time.time(),utilization=float(raw[0]),memory_mib=float(raw[1]),pids=pids)


def block_run(block):
    check();m=host();m.setup()
    rows=[r for r in schedule() if r['block']==block]
    gpu=m.infra().native_uuids(1)[0]
    if gpu in read(R/f'block-{block}/service-native.json')['gpu_uuids']:
        raise ValueError('service/execution GPU overlap')
    if gpu_sample(gpu)['pids']:raise ValueError('unclean execution GPU')
    arm=rows[0]['arm'];initialize(R/f'queue-{block}',1 if arm=='pipeline' else 2)
    start=time.time();stop=threading.Event();samples=[];errors=[]
    extra={}
    if FIXED_BLOCK_SECONDS:
        from live_identity import cpu_topology
        extra['cpu_topology']=cpu_topology()
    write(R/f'block-{block}/execution-native.json',dict(job=os.environ['SLURM_JOB_ID'],
        step=os.environ['SLURM_STEP_ID'],gpu_uuid=gpu,affinity=sorted(os.sched_getaffinity(0)),start=start,**extra))
    def monitor():
        while not stop.is_set():
            try:samples.append(gpu_sample(gpu))
            except Exception as e:errors.append(type(e).__name__);break
            stop.wait(1)
    observer=threading.Thread(target=monitor,daemon=True);observer.start()
    try:
        with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(run_one,rows))
    finally:stop.set();observer.join(timeout=22)
    write(R/f'block-{block}/telemetry.json',samples)
    queue=R/f'queue-{block}'
    events=[json.loads(v) for v in (queue/'events.jsonl').read_text().splitlines()] if (queue/'events.jsonl').exists() else []
    audit=audit_events(events,1 if arm=='pipeline' else 2)
    clean=not gpu_sample(gpu)['pids']
    write(R/f'block-{block}/closed.json',dict(block=block,arm=arm,start=start,end=time.time(),
        results=results,queue_audit=audit,telemetry_errors=errors,gpu_clean=clean))
    if errors or observer.is_alive() or not clean or not audit['all_released'] or not all(r['cleanup_verified'] for r in results):
        raise ValueError('block infrastructure/cleanup failed')
    return 0


def stop_service(server,block,job):
    if server.poll() is None:
        server.send_signal(signal.SIGTERM)
        try:server.wait(timeout=25)
        except subprocess.TimeoutExpired:
            native=R/f'block-{block}/service-native.json'
            if not native.exists():raise ValueError('no service step identity')
            step=read(native)['step']
            if not str(step).isdigit():raise ValueError('invalid step identity')
            subprocess.run(['scancel','--signal=KILL',job+'.'+str(step)],check=True,timeout=15)
            server.wait(timeout=20)
    native=R/f'block-{block}/service-native.json'
    if native.exists():
        devices=read(native)['gpu_uuids']
        clean=all(not gpu_sample(gpu)['pids'] for gpu in devices)
        write(R/f'block-{block}/service-cleanup.json',dict(gpu_clean=clean,returncode=server.returncode))
        if not clean:raise RuntimeError('service GPU cleanup uncertain; no next block')


def controller():
    check();m=host();m.setup();start=time.monotonic();job=os.environ['SLURM_JOB_ID']
    if socket.gethostname().split('.')[0]!=NODE:raise ValueError('wrong node')
    for _ in range(40):
        if (R/'launch.json').exists():break
        time.sleep(.25)
    if read(R/'launch.json')['job']!=job:raise ValueError('job identity')
    env=m.infra().clean_env();base=['srun','--exclusive','--nodes=1','--ntasks=1','--cpu-bind=cores']
    error=None;attempted=[]
    try:
        if NODE_QUALIFICATION:
            with (R/'node-qualification.private.log').open('xb') as log:
                qualified=subprocess.run(base+['--cpus-per-task=6','--gres=gpu:1','--time=00:03:00',
                    str(PY),'-B',str(R/NAME),'qualify'],env=env,stdout=log,stderr=log,timeout=190)
            if qualified.returncode or read(R/'node-qualification.json').get('complete') is not True:
                raise ValueError('new node/original image qualification failed')
        for block in range(4):
            if CAP-(time.monotonic()-start)<(FIXED_BLOCK_SECONDS or 1530):raise TimeoutError('whole block admission budget')
            bdir=R/f'block-{block}';cycle_start=time.time();cycle_mono=time.monotonic()
            with (bdir/'service.private.log').open('xb') as log:
                server=subprocess.Popen(base+['--cpus-per-task=12','--gres=gpu:2','--time=00:25:00',
                    str(PY),'-B',str(R/NAME),'service'],env=dict(env,R14_BLOCK=str(block)),
                    stdout=log,stderr=log,start_new_session=True)
                try:
                    ready_start=time.monotonic()
                    while time.monotonic()-ready_start<600:
                        if server.poll() is not None:raise RuntimeError('service exited')
                        try:
                            if m.health():break
                        except Exception:pass
                        time.sleep(2)
                    else:raise TimeoutError('service readiness cap')
                    # Common startup request, not a separate model acceptance batch.
                    out=m.api('/v1/chat/completions',dict(model=MODEL_ID,
                        messages=[dict(role='user',content='Reply with OK only.')],max_tokens=8,
                        temperature=0,seed=140900,chat_template_kwargs={'enable_thinking':False}),timeout=40)
                    if out.get('model')!=MODEL_ID or not out.get('choices'):raise ValueError('wrong service')
                    write(bdir/'service-ready.json',dict(startup_seconds=time.monotonic()-ready_start,model=MODEL_ID))
                    cmd=base+['--cpus-per-task=6','--gres=gpu:1','--time=00:13:00',
                        str(PY),'-B',str(R/NAME),'block','--block',str(block)]
                    remaining=800 if not FIXED_BLOCK_SECONDS else min(800,FIXED_BLOCK_SECONDS-(time.monotonic()-cycle_mono)-50)
                    if remaining<690:raise TimeoutError('no whole search budget in fixed slot')
                    attempted.append(block)
                    with (bdir/'block.private.log').open('xb') as log2:
                        result=subprocess.run(cmd,env=env,stdout=log2,stderr=log2,timeout=remaining)
                    write(bdir/'step-return.json',dict(returncode=result.returncode))
                    if result.returncode:raise ValueError('block failed')
                finally:stop_service(server,block,job)
            write(bdir/'cycle-closed.json',dict(start=cycle_start,end=time.time(),service_returncode=server.returncode))
            if FIXED_BLOCK_SECONDS:
                active_seconds=time.monotonic()-cycle_mono
                if active_seconds>FIXED_BLOCK_SECONDS:raise TimeoutError('fixed pool slot exceeded')
                while time.monotonic()-cycle_mono<FIXED_BLOCK_SECONDS:
                    time.sleep(max(0,min(1,FIXED_BLOCK_SECONDS-(time.monotonic()-cycle_mono))))
                write(bdir/'budget-slot.json',dict(reserved_seconds=FIXED_BLOCK_SECONDS,
                    actual_seconds=time.monotonic()-cycle_mono,active_cycle_seconds=active_seconds,
                    padding_seconds=FIXED_BLOCK_SECONDS-active_seconds,gpus=3))
            if PROFILE=='27b' and GENERATOR_ELIGIBILITY_GATE and block==0:
                from live_readout import ground_scores
                qualification=[]
                for row in schedule()[:4]:
                    ep=R/f'episode-{row["index"]}'
                    closed=read(ep/'closed.json')
                    final=read(ep/'finished.json') if (ep/'finished.json').exists() else {}
                    value=final.get('native_selected_score')
                    candidates=[read(p) for p in ep.glob('candidate-*.json') if '.private.' not in p.name]
                    timely=[v for v in candidates if v['elapsed_seconds']<=600]
                    receipts=[read(p)['receipt'] for p in ep.glob('scored-*.json')]
                    grounded=ground_scores(final,timely,receipts)
                    qualification.append(closed.get('returncode')==0 and closed.get('cleanup_verified') is True
                        and final.get('status') in ('completed','budget_exhausted') and grounded
                        and final.get('native_selected_valid') is True and type(value) in (float,int) and __import__('math').isfinite(value))
                write(R/'generator-qualification.json',dict(passed=all(qualification),endpoints=qualification))
                if not all(qualification):raise GeneratorEligibilityFailed('no remaining blocks')
    except Exception as e:
        error=type(e).__name__
        raise
    finally:
        rows=[]
        for row in schedule():
            ep=R/f'episode-{row["index"]}';r=dict(**row,source_commit=read(R/'plan.json')['source_commit'],status='not_started')
            if (ep/'closed.json').exists():r.update(read(ep/'closed.json'));r['status']='failed'
            if (ep/'finished.json').exists():
                f=read(ep/'finished.json');r.update(f)
                r['status']='complete' if r.get('returncode')==0 and r.get('cleanup_verified') and f['status'] in ('completed','budget_exhausted') else 'incomplete'
            rows.append(r)
        write(R/'runs.json',rows)
        with (R/'runs.csv').open('x',newline='') as f:
            w=csv.DictWriter(f,fieldnames=sorted({k for r in rows for k in r}));w.writeheader();w.writerows(rows)
        write(R/'closed.json',dict(planned=16,attempted_blocks=attempted,
            complete=sum(r['status']=='complete' for r in rows),controller_error=error,elapsed_seconds=time.monotonic()-start))


def main():
    os.umask(0o077);os.environ.update(PYTHON_DOTENV_DISABLED='1',PYTHONDONTWRITEBYTECODE='1')
    p=argparse.ArgumentParser();p.add_argument('mode',choices=('prepare','submit','controller','service','block','worker','qualify'))
    p.add_argument('--commit');p.add_argument('--block',type=int);p.add_argument('--index',type=int)
    a=p.parse_args()
    if a.mode=='prepare':return prepare(a.commit)
    if a.mode=='worker':return host().worker(a.index)
    if a.mode=='service':return host().service()
    if a.mode=='block':return block_run(a.block)
    if a.mode=='qualify':
        if not NODE_QUALIFICATION:raise ValueError('qualification not enabled')
        from live_node_qualification import qualify
        return qualify(sys.modules[__name__])
    return globals()[a.mode]()

if __name__=='__main__':sys.exit(main())
