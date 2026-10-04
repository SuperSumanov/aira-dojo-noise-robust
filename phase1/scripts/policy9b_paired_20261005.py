"""One bounded, native-Dojo, as-delivered base/LoRA development qualification.

No official grading, protected cohorts, training, paid endpoints or old-run resume.
Native solver/operators/parser are pinned; task scoring uses the established dev adapter.
"""
from __future__ import annotations
import argparse, asyncio, copy, datetime, hashlib, importlib.util, io, json, logging
import os, random, re, secrets, shutil, signal, socket, subprocess, sys, tarfile, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import urllib.request, urllib.error

os.environ.update(PYTHON_DOTENV_DISABLED='1', PYTHONDONTWRITEBYTECODE='1',
                  LITELLM_LOCAL_MODEL_COST_MAP='True')
B=Path('/research/d7/spc/yzyang4')
R=B/'policy9b-paired-20261005-gpu27-v1'
REPO=B/'aira-dojo'
COMMIT='b8e75052a9f69e19436f12bc5a36a0ca26a69a57'
DONOR=B/'task-feedback-real-20261001-v6'
DEVICE_DONOR=B/'diagnostic-information-20261004-v1'
MODEL=B/'models/Qwen3.5-9B-c202236'
ADAPTER=B/'policy9b-adapter-20261005-b6jjvjwh/accepted_adapter'
PY=B/'venvs/aira/bin/python'
VLLM=B/'local-qwen27b-20260914-zcx1k1dy/vllm.sif'
TASK_IMAGE=B/'aira-dojo/build/superimage/superimage.root.2026-07-macos-v1.sif'
PORT=19475
SECONDS=600
CAP=5400
TASKS=('random-acts-of-pizza','spooky-author-identification')
MODELS={'base':'qwen3.5-9b','sft':'qwen3.5-9b-mle-lora'}
SECRET=re.compile(rb'(?i)(?:\bsk-[a-z0-9_.-]{12,}|\bhf_[a-z0-9]{20,}|\bgh[pousr]_[a-z0-9]{20,}|Bearer\s+[a-z0-9_.-]{20,})')

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for part in iter(lambda:f.read(8*1024*1024),b''):h.update(part)
    return h.hexdigest()
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def read(p):return json.loads(Path(p).read_bytes())
def write(p,x):
    raw=(json.dumps(x,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
    if SECRET.search(raw):raise ValueError('credential-shaped artifact')
    with Path(p).open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
def load(name,path):
    sp=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(sp)
    sys.modules[name]=m;sp.loader.exec_module(m);return m
def schedule():
    # Counterbalance arm order over the two paired generation seeds.
    return [dict(index=4*b+2*j+t,wave=2*b+j,task=task,seed=108501+10*b+t,arm=arm)
            for b in range(2) for j,arm in enumerate(('base','sft') if b==0 else ('sft','base'))
            for t,task in enumerate(TASKS)]
def setup():
    sys.path.insert(0,str(R/'source/src'));sys.path.insert(0,str(R))
    os.environ.update(LOGGING_DIR=str(R),SUPERIMAGE_DIR=str(TASK_IMAGE.parent),
        MLE_BENCH_DATA_DIR=str(R/'no-official-data'),HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',
        WANDB_DISABLED='true',NO_PROXY='127.0.0.1,localhost',no_proxy='127.0.0.1,localhost')
def infra():
    p=B/'repair-replace-dev-20260927-v1/tests/fresh_first_slot_gpu27_20260927.py'
    assert sha(p)=='daf6b0e80db3577aa5f3219a47e166171958672cae00249248251bf78fd51857'
    x=load('policy9b_infra',p);x.ROOT=R;x.SERVICE_PORT=PORT;return x
def check():
    p=read(R/'plan.json');assert p['schedule']==schedule()
    for name,h in p['files'].items():
        if sha(R/name)!=h:raise ValueError('frozen source/config drift: '+name)
    return p

def prepare():
    if (R/'plan.json').exists() or (R/'submit-intent.json').exists():raise FileExistsError('frozen root exists')
    if R.exists() and list(R.glob('episode-*/native.json')):raise ValueError('attempted root cannot prepare')
    R.mkdir(mode=0o700,exist_ok=True);(R/'source').mkdir(exist_ok=True)
    raw=subprocess.check_output(['git','-C',str(REPO),'archive',COMMIT,'src/dojo'],timeout=60)
    with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
        for member in archive:
            if member.isdir():continue
            rel=Path(member.name)
            if not member.isfile() or '..' in rel.parts or not rel.is_relative_to('src/dojo'):
                raise ValueError('unsafe source member')
            p=R/'source'/rel;p.parent.mkdir(parents=True,exist_ok=True)
            p.write_bytes(archive.extractfile(member).read())
    overlays={
        'src/dojo/tasks/mlebench/task.py':'39e60193d40947e6b638e126ac5feb85e25e326dc8b0079746fa7e8cc72e553d',
        'src/dojo/config_dataclasses/task/mlebench.py':'c58a35ab0a1b8bbfa2c5a97d6eb7fbd04ac2673bea3c14de5355e4fbffc0d996',
        'src/dojo/utils/experiment_deadline.py':None}
    for rel,h in overlays.items():
        source=DONOR/'source'/rel
        if h is not None and sha(source)!=h:raise ValueError('dev adapter drift')
        shutil.copyfile(source,R/'source'/rel);overlays[rel]=sha(source)
    here=Path(__file__).parent
    for name in ('0020-policy9b-generation-kwargs-20261004.patch','0011-ForeTS-bounded-single-transport-20260909.patch'):
        shutil.copyfile(here/name,R/name)
        subprocess.run(['git','apply','--check',str(R/name)],cwd=R/'source',check=True,capture_output=True)
        subprocess.run(['git','apply',str(R/name)],cwd=R/'source',check=True,capture_output=True)
    for name in ('forets_gpu_binding_20260911.py','forets_native_cuda_identity_20260911.py',
                 'forets_native_gpu_binding_20260911.py','forets_opencl_allowlist_20260911.py',
                 'forets_opencl_readonly_ab.py','root_trial_step_supervisor_20260927.py'):
        shutil.copyfile(DEVICE_DONOR/name,R/name)
    for folder in ('configs','bin','opencl-vendors','service-cache/tmp'):(R/folder).mkdir(parents=True,exist_ok=True)
    (R/'opencl-vendors/nvidia.icd').write_text('libnvidia-opencl.so.1\n')
    shutil.copyfile(__file__,R/Path(__file__).name)
    shutil.copyfile(here/'policy9b_service_20261005.py',R/'service_entry.py')
    (R/'bin/singularity').write_text(f'#!{PY}\nimport sys\nsys.path.insert(0,{str(R)!r})\nfrom policy9b_paired_20261005 import task_runtime\ntask_runtime()\n')
    os.chmod(R/'bin/singularity',0o700)
    if not (R/'.service.env').exists():
        with (R/'.service.env').open('x') as f:f.write('PRIMARY_KEY_QWEN3_8_27B='+secrets.token_hex(32)+'\n')
    os.chmod(R/'.service.env',0o600)
    setup()
    import hydra
    from hydra import compose, initialize_config_dir
    from omegaconf import OmegaConf
    from dojo.config_dataclasses.omegaconf.resolvers import register_new_resolvers
    from dojo.config_dataclasses.run import RunConfig
    register_new_resolvers()
    for row in schedule():
        ep=R/f"episode-{row['index']}";ep.mkdir(exist_ok=True)
        # Only task development adapter configuration is reused, never old code or outcome.
        old=read(DONOR/'configs'/('1.json' if row['task']==TASKS[0] else '0.json'))
        assert old['task']['name']==row['task']
        overrides=['task=mlebench/_default',f"task.name={row['task']}",'solver=mlebench/mcts',
                   'interpreter=jupyter','solver/memory=no_memory',f"metadata.seed={row['seed']}",
                   'metadata.script_id=policy9b-paired-20261005',f'+metadata.git_commit_id={COMMIT}',
                   f'+metadata.base_path={R}/source',f'+logger.output_dir={ep}/native-log',
                   'logger.write_env_vars=false','logger.use_wandb=false','logger.print_config=false','logger.use_console=false',
                   'solver.time_limit_secs=600','solver.execution_timeout=240','solver.step_limit=10000',
                   'solver.max_llm_call_retries=1','solver.export_search_results=false','solver.use_test_score=false',
                   f'+solver.checkpoint_path={ep}/checkpoint']
        with initialize_config_dir(version_base='1.3',config_dir=str(R/'source/src/dojo/configs')):
            cfg=compose(config_name='default_run',overrides=overrides)
        for k in ('public_dir','private_dir','data_dir','search_only_dev_scorer_path','search_only_dev_scorer_sha256'):
            OmegaConf.update(cfg,'task.'+k,old['task'][k],force_add=True)
        OmegaConf.update(cfg,'task.cache_dir',str(R/'no-official-data'),force_add=True)
        OmegaConf.update(cfg,'interpreter.working_dir',str(ep/'work'),force_add=True)
        OmegaConf.update(cfg,'interpreter.env',dict(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',
            PYTHONHASHSEED=str(row['seed']),OMP_NUM_THREADS='6',OPENBLAS_NUM_THREADS='6',MKL_NUM_THREADS='6',NUMEXPR_NUM_THREADS='6'),force_add=True)
        for role in ('draft','improve','debug','analyze'):
            prefix='solver.operators.'+role+'.llm'
            OmegaConf.update(cfg,prefix+'.client',dict(_target_='dojo.config_dataclasses.client.base.ClientConfig',
                api='litellm',model_id=MODELS[row['arm']],base_url=f'http://127.0.0.1:{PORT}/v1',
                use_azure_client=False,provider='selfhosted'),force_add=True)
            kwargs=OmegaConf.to_container(OmegaConf.select(cfg,prefix+'.generation_kwargs'))
            kwargs.update(max_tokens=8192,seed=row['seed'],reasoning_effort='minimal',
                allowed_openai_params=['reasoning_effort'],extra_body={'chat_template_kwargs':{'enable_thinking':False}},
                structured_output_retries=0,bounded_transport=True,bounded_request_timeout_seconds=180)
            OmegaConf.update(cfg,prefix+'.generation_kwargs',kwargs,force_add=True)
        run=OmegaConf.to_object(OmegaConf.structured(hydra.utils.instantiate(cfg)))
        assert isinstance(run,RunConfig);run.validate()
        write(R/'configs'/f"{row['index']}.json",run.to_typed_dict())
    batch=f'''#!/bin/bash
#SBATCH --job-name=policy9b-base-lora
#SBATCH --partition=gpu_24h
#SBATCH --account=gpu
#SBATCH --qos=gpu
#SBATCH --nodelist=gpu27
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:4
#SBATCH --cpus-per-task=24
#SBATCH --time=01:30:00
#SBATCH --no-requeue
set -euo pipefail
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1
timeout --signal=TERM --kill-after=20s 5320s {PY} -B {R}/policy9b_paired_20261005.py controller
'''
    (R/'run.sbatch').write_text(batch)
    files={str(p.relative_to(R)):sha(p) for p in R.rglob('*') if p.is_file() and p.name!='.service.env' and '__pycache__' not in p.parts}
    write(R/'plan.json',dict(protocol='native-mcts-base-lora-development-v1',utc=utc(),source_commit=COMMIT,
        files=files,common_overlays=overlays,schedule=schedule(),runs=8,run_seconds=600,
        allocation_seconds=5400,allocated_gpus=4,gpu_hours_cap=6,budget_approval='user six-hour autonomy 2026-10-05 03:26 HKT',
        base=str(MODEL),base_revision='c202236235762e1c871ad0ccb60c8ee5ba337b9a',adapter=str(ADAPTER),
        adapter_weights_sha256='87a996545f516cef4480b1642ff6647f3a4eeab3e898e79dca5b445184597a08',
        adapter_config_sha256='7a1f06dc55ba770704436f9bd50d8464082d0de80fd827e1b8687116aab7b486',
        task_image_sha256='801f646bed3cae6e74e10d793e71b0086658d4303d54552333c58125ddf9beda',
        service_image_sha256='495ca35a3fa7fc534bbd855829af1b86ce75ab9a5675b3b1ab7dba58ca74b7fa',
        primary='Native journal-selected final development score at absolute 600s including startup, preview, generation, code, grading and analysis; null remains failure.',
        secondary='Any-valid rate, externally valid best-so-far as diagnostic only, valid time, operators/calls/tokens. No inherited placeholder monetary cost.',
        comparison='Same seed/task paired SFT minus base, oriented per task; all8 assignments, failures, median and sample variance. No pooled raw score or significant claim at n=2.',
        advance='Only if both tasks have two valid paired native-selected endpoints and both oriented paired differences positive: consider new common-parent qualification. Not automatic additional GPU.',
        context_tokens=32768,max_output_tokens=8192,sampling='native temperature/top_p; explicit nonthinking; paired per-run seed',
        fresh_start=True,native_solver=True,native_prompts=True,native_parser=True,official_grade=False,
        own_training=False,paid_api=0,protected_opened=False,training_base_revision_verified=False,
        interpretation='As-delivered short-budget development qualification; known reused development views, unknown training coverage. Neither algorithm novelty nor clean held-out confirmation.'))
    cpu()
    print(json.dumps(dict(status='PREPARED',root=str(R),plan_sha256=sha(R/'plan.json'),gpu_hours_cap=6)))

def cpu():
    plan=check();setup()
    from dojo.config_dataclasses.run import RunConfig
    from dojo.tasks.mlebench.task import MLEBenchTask
    from dojo.config_dataclasses.interpreter import INTERPRETER_MAP
    from dojo.utils.config import build
    from dojo.solvers.mcts.mcts import MCTS
    from dojo.core.tasks.constants import TASK_DESCRIPTION
    from dojo.utils.logger import config_logger
    from omegaconf import OmegaConf
    os.environ['PRIMARY_KEY']='offline-fixture';os.environ['PRIMARY_KEY_QWEN3_5_9B']='offline-fixture';os.environ['PRIMARY_KEY_QWEN3_5_9B_MLE_LORA']='offline-fixture'
    configs=[];views={}
    for s in schedule():
        cfg=RunConfig.load_from_json(R/'configs'/f"{s['index']}.json");cfg.validate();configs.append(cfg.to_typed_dict())
        task=MLEBenchTask(cfg.task);interp=build(cfg.interpreter,INTERPRETER_MAP,data_dir=cfg.task.data_dir)
        assert task._search_only_score is not None and not task.private_dir.exists() and interp.factory
        assert cfg.solver.use_test_score is False and cfg.solver.num_children==5 and cfg.solver.max_debug_depth==20
        assert cfg.interpreter.timeout==240 and cfg.solver.time_limit_secs==600
        assert sha(Path(cfg.task.search_only_dev_scorer_path))==cfg.task.search_only_dev_scorer_sha256
        views[s['task']]=dict(public_dir=str(task.public_dir),scorer_path=cfg.task.search_only_dev_scorer_path,
            scorer_sha256=cfg.task.search_only_dev_scorer_sha256,view_manifest_sha256=task._search_only_module.SPEC[s['task']]['view_sha'])
        config_logger(cfg)
        solver=MCTS(OmegaConf.structured(cfg.solver),{TASK_DESCRIPTION:task.task_description,'lower_is_better':task._search_only_lower_is_better})
        assert len(solver.journal.nodes)==0
        for op in cfg.solver.operators.values():
            assert op.llm.client.model_id==MODELS[s['arm']]
            assert op.llm.generation_kwargs['seed']==s['seed']
            assert op.llm.generation_kwargs['extra_body']['chat_template_kwargs']['enable_thinking'] is False
    # Normalize bookkeeping (paths, IDs) and the four intended model IDs only.
    def scientific(cfg):
        x=copy.deepcopy(cfg)
        for k in ('id','logger','metadata'):x.pop(k,None)
        x['solver'].pop('checkpoint_path',None);x['solver'].pop('exp_name',None);x['interpreter'].pop('working_dir',None)
        x['task'].pop('results_output_dir',None)
        for op in x['solver']['operators'].values():op['llm']['client']['model_id']='PAIR'
        return x
    for i,j in ((0,2),(1,3),(4,6),(5,7)):assert scientific(configs[i])==scientific(configs[j])
    from dojo.utils.experiment_deadline import ExperimentDeadline,ExperimentDeadlineExpired
    caught=False
    try:
        with ExperimentDeadline(.02).activate():time.sleep(.05)
    except ExperimentDeadlineExpired:caught=True
    assert caught
    subprocess.run(['bash','-n',str(R/'run.sbatch')],check=True)
    write(R/'cpu.json',dict(status='PASS',utc=utc(),configs=8,pairs_equal_except_model=4,dev_views=views,
        native_solver_instantiated=8,absolute_deadline_checked=True,plan_sha256=sha(R/'plan.json'),model_calls=0))

def submit():
    p=check();assert read(R/'cpu.json')['plan_sha256']==sha(R/'plan.json')
    assert sha(TASK_IMAGE)==p['task_image_sha256'] and sha(VLLM)==p['service_image_sha256']
    assert sha(ADAPTER/'adapter_model.safetensors')==p['adapter_weights_sha256']
    assert sha(ADAPTER/'adapter_config.json')==p['adapter_config_sha256']
    env=infra().clean_env()
    jobs=subprocess.check_output(['squeue','-u','yzyang4','-h','-o','%i'],env=env,text=True,timeout=20).split()
    assert not set(jobs)-{'12535'},'unexpected current allocation'
    assert not (R/'submit-intent.json').exists()
    write(R/'submit-intent.json',dict(utc=utc(),plan_sha256=sha(R/'plan.json')))
    r=subprocess.run(['sbatch','--parsable','--chdir='+str(R),'--output='+str(R/'allocation-%j.out'),
        '--error='+str(R/'allocation-%j.err'),str(R/'run.sbatch')],env=env,capture_output=True,text=True,timeout=25)
    job=r.stdout.strip().split(';')[0]
    if r.returncode or not job.isdigit():raise RuntimeError('ambiguous submission; do not retry')
    write(R/'launch.json',dict(job=job,utc=utc(),plan_sha256=sha(R/'plan.json')))
    print(json.dumps(dict(status='SUBMITTED',job=job,gpu_hours_cap=6)))

def service():
    check();x=infra();assert socket.gethostname().split('.')[0]=='gpu27'
    with socket.socket() as probe:probe.bind(('127.0.0.1',PORT))
    devices=x.native_uuids(2)
    write(R/'service-native.json',dict(job=os.environ['SLURM_JOB_ID'],step=os.environ['SLURM_STEP_ID'],gpu_uuids=devices))
    cmd=['/usr/bin/singularity','exec','--containall','--cleanenv','--no-home','--nv','--no-mount','bind-paths,cwd',
        '--bind',str(MODEL)+':/model:ro','--bind',str(ADAPTER)+':/adapter:ro',
        '--bind',str(R/'service-cache')+':/cache:rw','--bind',str(R/'service-cache/tmp')+':/tmp:rw',
        '--bind',str(R/'service_entry.py')+':/run/service_entry.py:ro','--pwd','/cache',str(VLLM),
        '/usr/bin/python3','/run/service_entry.py']
    values=dict(CUDA_VISIBLE_DEVICES=','.join(devices),EXPECTED_GPU_UUIDS=','.join(devices),VLLM_API_KEY=x.local_key(),
        VLLM_WORKER_MULTIPROC_METHOD='spawn',VLLM_CACHE_ROOT='/cache/vllm',TRITON_HOME='/cache/triton',TORCH_HOME='/cache/torch',
        HF_HOME='/cache/hf',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',FLASHINFER_WORKSPACE_BASE='/cache/flashinfer',
        XDG_CACHE_HOME='/cache/xdg',TMPDIR='/tmp',MAX_JOBS='2',VLLM_NO_USAGE_STATS='1',VLLM_CONFIG_ROOT='/cache/vllm-config')
    env={k:os.environ[k] for k in ('PATH','HOME','USER','LOGNAME') if k in os.environ}
    env.update({'SINGULARITYENV_'+k:v for k,v in values.items()});os.execve(cmd[0],cmd,env)

def api(route,body=None,timeout=5):
    request=urllib.request.Request(f'http://127.0.0.1:{PORT}'+route,
        data=None if body is None else json.dumps(body).encode(),headers={'Authorization':'Bearer '+infra().local_key(),'Content-Type':'application/json'})
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request,timeout=timeout) as r:return json.load(r)
def health():return set(x['id'] for x in api('/v1/models')['data'])==set(MODELS.values())

def task_runtime():
    setup()
    from forets_gpu_binding_20260911 import REAL_SINGULARITY,split_command,rewrite
    from forets_native_gpu_binding_20260911 import native_identity,resolve_native
    from forets_opencl_allowlist_20260911 import driver_binds
    args=sys.argv[1:]
    if args==['--version']:os.execv(REAL_SINGULARITY,[REAL_SINGULARITY,'--version'])
    split_command(args);ep=Path(os.environ['POLICY9B_EPISODE'])
    assert ep.parent==R and re.fullmatch('episode-[0-7]',ep.name)
    native=read(ep/'native.json');assert native['job']==os.environ['SLURM_JOB_ID'] and native['step']==os.environ['SLURM_STEP_ID']
    observed=native_identity();minor,uid=resolve_native(observed);assert [uid]==native['gpu_uuids']
    cache=subprocess.check_output(['/sbin/ldconfig','-p'],text=True,timeout=10)
    final,gate=rewrite(args,minor=minor,uuid=uid,libraries=driver_binds(cache),vendors=R/'opencl-vendors')
    env={k:os.environ[k] for k in ('PATH','HOME','USER','LOGNAME') if k in os.environ}
    p=subprocess.run(gate,env=env,capture_output=True,text=True,timeout=25)
    rows=[json.loads(v.removeprefix('ALLOWLIST_GATE ')) for v in p.stdout.splitlines() if v.startswith('ALLOWLIST_GATE ')]
    assert p.returncode==0 and len(rows)==1 and rows[0].get('exact_device_namespace') is True
    write(ep/f'binding-{os.getpid()}.json',dict(native_identity=observed,namespace=rows[0],system_bindpaths_disabled=True))
    os.execve(REAL_SINGULARITY,final,env)

def worker(index):
    check();setup();x=infra();s=schedule()[index];ep=R/f'episode-{index}'
    own=x.native_uuids(1);assert not set(own)&set(read(R/'service-native.json')['gpu_uuids'])
    key=x.local_key()
    os.environ.update(PRIMARY_KEY=key,PRIMARY_KEY_QWEN3_5_9B=key,PRIMARY_KEY_QWEN3_5_9B_MLE_LORA=key,
        DOJO_GPU_UUIDS=own[0],POLICY9B_EPISODE=str(ep),DOJO_WORKER_IDENTITY_PATH=str(ep/'identity.json'),
        DOJO_EXECUTION_ID=f'{os.environ["SLURM_JOB_ID"]}.{os.environ["SLURM_STEP_ID"]}:{index}',
        HARDWARE='one NVIDIA RTX3090, six CPU cores',TIME_LIMIT='10 minutes',TIME_LIMIT_SECS='600',STEP_LIMIT='10000',
        PATH=str(R/'bin')+':'+os.environ['PATH'])
    from dojo.main_local_worker import _process_start_ticks,_host_boot_id
    write(ep/'identity.json',dict(pid=os.getpid(),pgid=os.getpgid(0),process_start_ticks=_process_start_ticks(os.getpid()),
        host_boot_id=_host_boot_id(),gpu_uuids=own,container_pid=None,container_process_start_ticks=None))
    write(ep/'native.json',dict(index=index,job=os.environ['SLURM_JOB_ID'],step=os.environ['SLURM_STEP_ID'],
        config_sha256=sha(R/'configs'/f'{index}.json'),gpu_uuids=own))
    from dojo.utils.experiment_deadline import ExperimentDeadline,ExperimentDeadlineExpired
    deadline=ExperimentDeadline(SECONDS);write(ep/'deadline.json',deadline.receipt())
    status='failed';solver=None;task=None;state=None;scored=[]
    try:
        with deadline.activate():
            from dojo.config_dataclasses.run import RunConfig
            from dojo.tasks.mlebench.task import MLEBenchTask
            from dojo.config_dataclasses.interpreter import INTERPRETER_MAP
            from dojo.utils.config import build
            from dojo.utils.logger import config_logger
            from dojo.solvers.mcts.mcts import MCTS
            from dojo.core.tasks.constants import EXECUTION_OUTPUT,VALID_SOLUTION,VALIDATION_FITNESS,AUX_EVAL_INFO
            from omegaconf import OmegaConf
            import numpy as np
            random.seed(s['seed']);np.random.seed(s['seed'])
            cfg=RunConfig.load_from_json(R/'configs'/f'{index}.json');cfg.validate();config_logger(cfg)
            cfg.save()
            for name in ('openai','httpx','httpcore','LiteLLM'):logging.getLogger(name).setLevel(logging.ERROR)
            task=MLEBenchTask(cfg.task)
            interp=build(cfg.interpreter,INTERPRETER_MAP,data_dir=cfg.task.data_dir)
            state,info=task.prepare(solver_interpreter=interp,eval_interpreter=None)
            solver=MCTS(OmegaConf.structured(cfg.solver),info)
            original_score=task._search_only_score
            def capture(name,submission):
                receipt=original_score(name,submission)
                ordinal=len(scored)
                shutil.copyfile(submission,ep/f'scored-{ordinal}.private.csv')
                write(ep/f'scored-{ordinal}.json',dict(receipt=receipt,elapsed_seconds=deadline.elapsed()))
                scored.append(receipt)
                return receipt
            task._search_only_score=capture
            step_task=task.step_task;attempts=[]
            def stepped(state,code):
                deadline.check();i=len(attempts);attempts.append(i)
                write(ep/f'candidate-{i}.private.json',dict(code=code,elapsed_seconds=deadline.elapsed()))
                # Same common RNG initializer for task model training, not a new prompt.
                executable=f'import random as _r, numpy as _n\n_r.seed({s["seed"]})\n_n.random.seed({s["seed"]})\n'+code
                out,result=step_task(state,executable)
                execution=result[EXECUTION_OUTPUT]
                write(ep/f'candidate-{i}.json',dict(valid=bool(result.get(VALID_SOLUTION)),score=result.get(VALIDATION_FITNESS),
                    aux=result.get(AUX_EVAL_INFO),elapsed_seconds=deadline.elapsed(),exit_code=execution.exit_code,
                    timed_out=execution.timed_out,exec_seconds=execution.exec_time,code_sha256=hashlib.sha256(code.encode()).hexdigest()))
                deadline.check();return out,result
            task.step_task=stepped
            original_log=solver.log_journal
            def log_journal():
                original_log();solver.save_checkpoint()
            solver.log_journal=log_journal
            solver(task,state);status='completed'
    except ExperimentDeadlineExpired:status='budget_exhausted'
    except Exception as exc:
        write(ep/'failure.json',dict(error_type=type(exc).__name__,utc=utc()))
        raise
    finally:
        best=None
        if solver is not None:
            solver.save_checkpoint();best=solver.journal.get_best_node()
        write(ep/'finished.json',dict(status=status,utc=utc(),elapsed_seconds=deadline.elapsed(),
            native_selected_valid=best is not None,native_selected_score=None if best is None else best.metric.value,
            native_selected_code_sha256=None if best is None else hashlib.sha256(best.code.encode()).hexdigest(),
            external_valid_submissions=len(scored)))
        if task is not None and state is not None:task.close(state)

def controller():
    check();setup();assert socket.gethostname().split('.')[0]=='gpu27'
    job=os.environ['SLURM_JOB_ID']
    for _ in range(20):
        if (R/'launch.json').exists():break
        time.sleep(.5)
    assert read(R/'launch.json')['job']==job
    from root_trial_step_supervisor_20260927 import supervise
    began=time.monotonic();write(R/'claim.json',dict(job=job,utc=utc()))
    env=infra().clean_env();base=['srun','--exclusive','--nodes=1','--ntasks=1']
    with (R/'service.private.log').open('xb') as log:
        server=subprocess.Popen(base+['--cpus-per-task=12','--gres=gpu:2','--time=01:29:00',str(PY),'-B',str(R/Path(__file__).name),'service'],
            env=env,stdout=log,stderr=log,start_new_session=True)
        try:
            while time.monotonic()-began<1200:
                if server.poll() is not None:raise RuntimeError('service exited')
                try:
                    if health():break
                except Exception:pass
                time.sleep(3)
            else:raise TimeoutError('service readiness')
            qualification=[]
            for model in MODELS.values():
                response=api('/v1/chat/completions',dict(model=model,messages=[dict(role='user',content='Reply with OK only.')],
                    max_tokens=8,temperature=0,seed=108500,chat_template_kwargs={'enable_thinking':False}),timeout=120)
                assert response['model']==model and response.get('choices')
                qualification.append(dict(requested=model,returned=response['model'],usage=response.get('usage')))
            write(R/'service-ready.json',dict(utc=utc(),startup_seconds=time.monotonic()-began,qualification=qualification))
            def run(s):
                i=s['index'];ep=R/f'episode-{i}';write(ep/'launch.json',dict(utc=utc(),**s))
                cmd=base+['--cpus-per-task=6','--gres=gpu:1','--time=00:13:00',str(PY),'-B',str(R/Path(__file__).name),'worker','--index',str(i)]
                result=supervise(cmd,env=env,log_path=ep/'worker.private.log',native_path=ep/'native.json',
                    deadline_path=ep/'deadline.json',job_id=job,config_sha256=sha(R/'configs'/f'{i}.json'),index=i,
                    seconds=SECONDS,startup_seconds=100,cleanup_seconds=60)
                identity=read(ep/'identity.json')
                def gone(pid,ticks):
                    if pid is None:return True
                    try:
                        v=Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()
                        return v[0]=='Z' or int(v[19])!=ticks
                    except FileNotFoundError:return True
                if not gone(identity['pid'],identity['process_start_ticks']) or not gone(identity.get('container_pid'),identity.get('container_process_start_ticks')):
                    raise RuntimeError('worker/container cleanup uncertain')
                own=read(ep/'native.json')['gpu_uuids']
                applications=subprocess.check_output(['nvidia-smi','--query-compute-apps=gpu_uuid,pid','--format=csv,noheader,nounits'],text=True,timeout=10)
                if any(line.split(',')[0].strip() in own for line in applications.splitlines()):raise RuntimeError('worker GPU still occupied')
                result['image_cleanup_certified']=True
                write(ep/'closed.json',result)
                # Retain early failures; stop only for uncertain cleanup/step identity.
                return i
            for wave in range(4):
                if CAP-(time.monotonic()-began)<800:raise TimeoutError('no whole next wave budget')
                if server.poll() is not None or not health():raise RuntimeError('service failed between waves')
                with ThreadPoolExecutor(max_workers=2) as pool:done=list(pool.map(run,[s for s in schedule() if s['wave']==wave]))
                write(R/f'wave-{wave}.json',dict(indices=done,utc=utc()))
            write(R/'all-closed.json',dict(attempts=8,utc=utc()))
        except Exception as exc:
            write(R/'controller-error.json',dict(error_type=type(exc).__name__,utc=utc()));raise
        finally:
            if server.poll() is None:
                server.send_signal(signal.SIGTERM)
                try:server.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    step=read(R/'service-native.json')['step'];assert step.isdigit()
                    subprocess.run(['scancel','--signal=KILL',job+'.'+step],check=True,timeout=30);server.wait(timeout=30)
            write(R/'closed.json',dict(utc=utc(),elapsed_seconds=time.monotonic()-began,service_closed=server.poll() is not None))

if __name__=='__main__':
    os.umask(0o077);p=argparse.ArgumentParser();p.add_argument('mode',choices=('prepare','cpu','submit','service','worker','controller','check'));p.add_argument('--index',type=int);a=p.parse_args()
    if a.mode=='worker':worker(a.index)
    elif a.mode=='check':check();print('FROZEN_PLAN_VALID')
    else:globals()[a.mode]()
