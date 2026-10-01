"""Bounded AIRA native-operator, code-start continuation pilot; NOT full-search E2E."""
from __future__ import annotations
import argparse,asyncio,copy,datetime,hashlib,importlib.util,json,logging,os,random,re,secrets,shutil,signal,socket,subprocess,sys,time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
os.environ['PYTHON_DOTENV_DISABLED']='1'
B=Path('/research/d7/spc/yzyang4')
ROOT=B/'task-feedback-real-20261001-v5'
SOURCE=B/'root-failure-four-task-source-feedback-20260928-v2'
PY=B/'venvs/aira/bin/python'
ASSETS=B/'local-qwen27b-20260914-zcx1k1dy'
INFRA=B/'repair-replace-dev-20260927-v1/tests/fresh_first_slot_gpu27_20260927.py'
PORT=19441
SECONDS=1800
CAP=14400
COMMIT='bc74d8774eadbf3f82773bb456badde6e3b77f7f'
TASKS=('spooky-author-identification','random-acts-of-pizza','tweet-sentiment-extraction')
DONORS=(('root-failure-randomized-gpu27-20260927-v1',0),('root-failure-randomized-gpu27-20260927-v1',1),('root-failure-text-tasks-gpu27-20260928-v2',1),('root-failure-randomized-gpu27-20260927-v1',3),('root-failure-randomized-gpu27-20260927-v1',2),('root-failure-text-unstarted-gpu27-20260928-v1',0))
SECRET=re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,}|Bearer\s+[a-z0-9_.-]{20,})')

def load(name,p):
    s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
infra=load('feedback_old_infra',INFRA)
infra.ROOT=ROOT;infra.SERVICE_PORT=PORT
sha=infra.digest
read=infra.read
write=infra.write

def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def setup():
    sys.path.insert(0,str(ROOT/'source/src'));sys.path.insert(0,str(ROOT))
    os.environ.update(LOGGING_DIR=str(ROOT),SUPERIMAGE_DIR=str(B/'aira-dojo/build/superimage'),MLE_BENCH_DATA_DIR=str(ROOT/'no-official-data'),HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',WANDB_DISABLED='true',PYTHON_DOTENV_DISABLED='1')

def schedule():
    # One random pre-result order, second start uses its reverse. Same-arm waves only.
    order=list('ABC');random.Random(20261001).shuffle(order)
    return [dict(index=len(order)*3*s+3*j+t,start=3*s+t,task=TASKS[t],arm=a,seed=101001+t+3*s,wave=3*s+j)
            for s in range(2) for j,a in enumerate(order if s==0 else order[::-1]) for t in range(3)]

def prepare():
    if ROOT.exists():raise FileExistsError('one-shot experiment root exists')
    ROOT.mkdir(mode=0o700);(ROOT/'source').mkdir();(ROOT/'starts').mkdir();(ROOT/'configs').mkdir();(ROOT/'service-cache/tmp').mkdir(parents=True)
    for tree in ('src','tests'):
        for p in (SOURCE/tree).rglob('*'):
            if not p.is_file() or '__pycache__' in p.parts or p.suffix not in ('.py','.yaml','.txt'):continue
            raw=p.read_bytes()
            if p.is_symlink() or SECRET.search(raw):raise ValueError('source shape/path withheld')
            dest=ROOT/'source'/p.relative_to(SOURCE);dest.parent.mkdir(exist_ok=True,parents=True);shutil.copyfile(p,dest)
    here=Path(__file__).parent
    for name in ('task_feedback_real_20261001.py','task_feedback_facts_20261001.py','FEEDBACK_REAL_PILOT_20261001.md'):
        shutil.copyfile(here/name,ROOT/name)
    # Common parser repair, not a treatment. Compare original parser bytes first.
    for rel in ('src/dojo/core/solvers/utils/response.py','src/dojo/utils/code_parsing.py'):
        if (ROOT/'source'/rel).read_bytes()!=(here/'parser-baseline'/rel).read_bytes():raise ValueError('parser baseline drift: '+rel)
    for rel in ('src/dojo/core/solvers/utils/response.py','src/dojo/utils/code_parsing.py','src/dojo/utils/python_code_blocks.py'):
        shutil.copyfile(here/'parser-candidate'/rel,ROOT/'source'/rel)
    shutil.copyfile(B/'root-failure-text-unstarted-gpu27-20260928-v1/root_trial_step_supervisor_20260927.py',ROOT/'root_trial_step_supervisor_20260927.py')
    donor=B/'forets-fresh-integration-20260914-ih6u0mpw';pinned=read(donor/'prepared.json')['files']
    for name in ('forets_gpu_binding_20260911.py','forets_native_cuda_identity_20260911.py','forets_native_gpu_binding_20260911.py','forets_opencl_allowlist_20260911.py','forets_opencl_readonly_ab.py'):
        if sha(donor/name)!=pinned[name]:raise ValueError('namespace helper drift')
        shutil.copyfile(donor/name,ROOT/name)
    (ROOT/'bin').mkdir();(ROOT/'opencl-vendors').mkdir();(ROOT/'opencl-vendors/nvidia.icd').write_text('libnvidia-opencl.so.1\n')
    (ROOT/'bin/singularity').write_text(f'#!{PY}\nimport sys\nsys.path.insert(0,{str(ROOT)!r})\nfrom task_feedback_real_20261001 import task_runtime\ntask_runtime()\n')
    os.chmod(ROOT/'bin/singularity',0o700)
    entry=infra.SERVICE_ENTRY.read_text()
    if entry.count("'--port','8000'")!=1 or sha(infra.SERVICE_ENTRY)!=infra.SERVICE_ENTRY_SHA:raise ValueError('service entry drift')
    (ROOT/'service_entry.py').write_text(entry.replace("'--port','8000'",f"'--port','{PORT}'"))
    with (ROOT/'.service.env').open('x') as f:f.write('PRIMARY_KEY_QWEN3_8_27B='+secrets.token_hex(32)+'\n')
    os.chmod(ROOT/'.service.env',0o600)
    starts=[];configs=[]
    from task_feedback_facts_20261001 import groups
    for i,(name,run) in enumerate(DONORS):
        donor=B/name;config=read(donor/f'configs/run-{run}.json');task=TASKS[i%3]
        if config['task']['name']!=task:raise ValueError('donor task mapping')
        journal=donor/f'run-{run}/checkpoint/journal.jsonl';raw=journal.read_bytes()
        if SECRET.search(raw):raise ValueError('source journal credential hit')
        rows=[json.loads(x) for x in raw.splitlines() if x.strip()]
        eligible=[(j,x) for j,x in enumerate(rows) if x.get('code') and x.get('metric_info',{}).get('execution_started') is True]
        if not eligible:raise ValueError('no actual executed code in donor')
        j,row=eligible[0]
        start=dict(task=task,donor=name,donor_run=run,journal_sha256=sha(journal),row=j,code_sha256=hashlib.sha256(row['code'].encode()).hexdigest(),selection='first execution_started=true; no score ranking',group_cuts=groups(task,Path(config['task']['public_dir']))[0])
        write(ROOT/'starts'/f'{i}.private.json',{'code':row['code'],'plan':row.get('plan') or ''})
        starts.append(start);configs.append(config)
    for s in schedule():
        cfg=copy.deepcopy(configs[s['start']]);ep=ROOT/f'episode-{s["index"]}';ep.mkdir()
        cfg['id']=f'feedback-20261001-{s["index"]}'
        cfg['logger'].update(output_dir=str(ep/'native-log'),write_env_vars=False,use_wandb=False,print_config=False,use_console=False)
        cfg['metadata'].update(seed=s['seed'],script_id='task-feedback-real-20261001',git_commit_id=COMMIT,base_path=str(ROOT/'source'))
        cfg['solver'].update(root_failure_randomization=False,acquisition_first_slot=False,record_slate_hashes=False,use_test_score=False,time_limit_secs=SECONDS,execution_timeout=480,checkpoint_path=str(ep/'unused-checkpoint'),max_debug_depth=2)
        cfg['interpreter']['working_dir']=str(ep/'unused-work')
        cfg['interpreter']['timeout']=480
        cfg['interpreter'].setdefault('env',{}).update(PYTHONHASHSEED=str(s['seed']),OMP_NUM_THREADS='6',OPENBLAS_NUM_THREADS='6',MKL_NUM_THREADS='6',NUMEXPR_NUM_THREADS='6')
        cfg['task']['cache_dir']=str(ROOT/'no-official-data')
        for op in cfg['solver']['operators'].values():
            op['llm']['client']['base_url']=f'http://127.0.0.1:{PORT}/v1'
            op['llm']['generation_kwargs'].update(max_tokens=8192,seed=s['seed'],extra_body={'chat_template_kwargs':{'enable_thinking':False}},bounded_transport=True,bounded_max_attempts=1,bounded_request_timeout_seconds=600,structured_output_retries=0)
        write(ROOT/'configs'/f'{s["index"]}.json',cfg)
    batch=f'''#!/bin/bash
#SBATCH --job-name=task-feedback-ABC
#SBATCH --partition=gpu_24h
#SBATCH --account=gpu
#SBATCH --qos=gpu
#SBATCH --nodelist=gpu28
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:5
#SBATCH --cpus-per-task=30
#SBATCH --time=04:00:00
#SBATCH --no-requeue
set -euo pipefail
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1
timeout --signal=TERM --kill-after=20s 14340s {PY} -B {ROOT}/task_feedback_real_20261001.py controller
'''
    (ROOT/'run.sbatch').write_text(batch)
    files={str(p.relative_to(ROOT)):sha(p) for p in ROOT.rglob('*') if p.is_file() and p.name!='.service.env'}
    write(ROOT/'plan.json',dict(protocol='code-start-feedback-ABC-v1',base_commit=COMMIT,source_donor=str(SOURCE),utc=utc(),schedule=schedule(),starts=starts,files=files,run_seconds=SECONDS,allocation_seconds=CAP,gpu_hours_cap=20,paid_api=0,training=False,renewal='user confirmed 2026-10-01',protected_opened=False,final_evaluation=False))
    setup();cpu();print(json.dumps({'status':'PREPARED','root':str(ROOT),'plan_sha256':sha(ROOT/'plan.json')}))

def check():
    p=read(ROOT/'plan.json')
    if p['schedule']!=schedule():raise ValueError('schedule drift')
    for f,h in p['files'].items():
        if sha(ROOT/f)!=h:raise ValueError('frozen file drift: '+f)
    return p

def cpu():
    p=check();setup()
    from dojo.config_dataclasses.run import RunConfig
    from dojo.tasks.mlebench.task import MLEBenchTask
    from dojo.utils.config import build
    from dojo.config_dataclasses.interpreter import INTERPRETER_MAP
    from task_feedback_facts_20261001 import feedback,auc
    from omegaconf import OmegaConf
    from dojo.core.solvers.llm_helpers.generic_llm import GenericLLM
    from dojo.core.solvers.operators.improve import improve_op
    from dojo.core.solvers.operators.debug import debug_op
    from dojo.core.solvers.utils.journal import Journal,Node
    os.environ['PRIMARY_KEY_QWEN3_8_27B']=infra.local_key()
    counts=0
    for s in schedule():
        cfg=RunConfig.load_from_json(ROOT/'configs'/f'{s["index"]}.json');cfg.validate()
        task=MLEBenchTask(cfg.task)
        interp=build(cfg.interpreter,INTERPRETER_MAP,data_dir=cfg.task.data_dir)
        if task._search_only_score is None or task.private_dir.exists() or not interp.factory:raise ValueError('task isolation')
        for kind,op in [('improve',improve_op),('debug',debug_op)]:
            native=GenericLLM(OmegaConf.structured(cfg.solver.operators[kind]));j=Journal();n=Node(code='pass',plan='common goal',_term_out=['log']);j.append(n)
            async def mock(**kw):
                q=kw['query_data'];native.system_message_prompt_template.format(**q);native.init_user_message_prompt_template.format(**q)
                return '```python\npass\n```',{}
            text,_=feedback(s['arm'],{'valid':False},None,n.plan)
            asyncio.run(op(mock,OmegaConf.structured(cfg.solver),None,task.task_description+text,j,n,0,100,data_preview='public-only'))
            counts+=1
    b,f=feedback('B',{'valid':True},{'n':3},'goal');c,g=feedback('C',{'valid':True},{'n':3},'goal')
    assert f==g and b!=c and auc([0,1],[0,1])==1 and auc([1,1],[0,1]) is None
    from forets_gpu_binding_20260911 import rewrite
    args=['exec','--containall','--cleanenv','--no-home','--nv','--bind','/fake-work:/workspace:rw','--bind','/fake-public:/workspace/data:ro','--pwd','/workspace',str(infra.TASK_IMAGE),'env','HOME=/workspace/.home','python','-c','pass']
    final,gate=rewrite(args,minor=1,uuid='GPU-11111111-1111-1111-1111-111111111111',libraries={},vendors=ROOT/'opencl-vendors')
    assert '--nv' not in final and final[final.index('--no-mount')+1]=='bind-paths,cwd'
    subprocess.run(['bash','-n',str(ROOT/'run.sbatch')],check=True)
    write(ROOT/'cpu.json',dict(status='PASS',typed_configs=18,actual_native_prompt_renders=counts,same_state_B_C_facts_equal=True,real_model_calls=0,plan_sha256=sha(ROOT/'plan.json')))

def submit():
    p=check()
    if read(ROOT/'cpu.json')['plan_sha256']!=sha(ROOT/'plan.json'):raise ValueError('CPU check stale')
    # Reuse exact previously validated images; hash before new real allocation.
    if sha(infra.TASK_IMAGE)!=infra.IMAGE_SHA or sha(ASSETS/'vllm.sif')!=infra.VLLM_SHA:raise ValueError('image drift')
    receipt=read(ASSETS/'complete.json')
    for r in receipt['files']:
        if r['path'].endswith('.safetensors') and ((ASSETS/r['path']).stat().st_size!=r['bytes'] or sha(ASSETS/r['path'])!=r['digest']):raise ValueError('weights drift')
    with (ROOT/'capacity.tmp').open('xb') as f:os.posix_fallocate(f.fileno(),0,1024**3)
    (ROOT/'capacity.tmp').unlink()
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    queue=subprocess.check_output(['squeue','-u','yzyang4','-h','-o','%i'],env=env,text=True,timeout=20).split()
    if set(queue)-{'12535'}:raise ValueError('unexpected owned allocation')
    write(ROOT/'submit-intent.json',dict(utc=utc(),plan_sha256=sha(ROOT/'plan.json')))
    r=subprocess.run(['sbatch','--parsable','--chdir='+str(ROOT),'--output='+str(ROOT/'allocation-%j.out'),'--error='+str(ROOT/'allocation-%j.err'),str(ROOT/'run.sbatch')],env=env,capture_output=True,text=True,timeout=25)
    job=r.stdout.strip().split(';')[0]
    if r.returncode or not job.isdigit():raise RuntimeError('submission ambiguous; no retry')
    write(ROOT/'launch.json',dict(job=job,utc=utc(),plan_sha256=sha(ROOT/'plan.json')));print(json.dumps({'job':job,'status':'SUBMITTED','gpu_hours_cap':20}))

def service():
    check()
    if socket.gethostname().split('.')[0]!='gpu28':raise ValueError('node')
    with socket.socket() as s:s.bind(('127.0.0.1',PORT))
    devices=infra.native_uuids(2)
    write(ROOT/'service-native.json',dict(job=os.environ['SLURM_JOB_ID'],step=os.environ['SLURM_STEP_ID'],gpu_uuids=devices))
    command=['/usr/bin/singularity','exec','--containall','--cleanenv','--no-home','--nv','--no-mount','bind-paths,cwd','--bind',str(ASSETS/'model')+':/model:ro','--bind',str(ROOT/'service-cache')+':/cache:rw','--bind',str(ROOT/'service-cache/tmp')+':/tmp:rw','--bind',str(ROOT/'service_entry.py')+':/run/service_entry.py:ro','--pwd','/cache',str(ASSETS/'vllm.sif'),'/usr/bin/python3','/run/service_entry.py']
    values=dict(CUDA_VISIBLE_DEVICES=','.join(devices),EXPECTED_GPU_UUIDS=','.join(devices),VLLM_API_KEY=infra.local_key(),VLLM_WORKER_MULTIPROC_METHOD='spawn',VLLM_CACHE_ROOT='/cache/vllm',TRITON_HOME='/cache/triton',TORCH_HOME='/cache/torch',HF_HOME='/cache/hf',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',FLASHINFER_WORKSPACE_BASE='/cache/flashinfer',XDG_CACHE_HOME='/cache/xdg',TMPDIR='/tmp',MAX_JOBS='2',VLLM_NO_USAGE_STATS='1',VLLM_CONFIG_ROOT='/cache/vllm-config',NO_PROXY='127.0.0.1,localhost',no_proxy='127.0.0.1,localhost')
    env={k:os.environ[k] for k in ('PATH','HOME','USER','LOGNAME') if k in os.environ};env.update({'SINGULARITYENV_'+k:v for k,v in values.items()});os.execve(command[0],command,env)

def task_runtime():
    """Use the already validated pure UUID/minor binding, not ordinal inference."""
    from forets_gpu_binding_20260911 import REAL_SINGULARITY,split_command,rewrite
    from forets_native_gpu_binding_20260911 import native_identity,resolve_native
    from forets_opencl_allowlist_20260911 import driver_binds
    args=sys.argv[1:]
    if args==['--version']:os.execv(REAL_SINGULARITY,[REAL_SINGULARITY,'--version'])
    split_command(args)
    action=Path(os.environ['FEEDBACK_ACTION_ROOT'])
    if action.parent.parent!=ROOT or not re.fullmatch('episode-[0-9]+',action.parent.name) or not re.fullmatch('action-[0-4]',action.name):raise ValueError('binding scope')
    native=read(action.parent/'native.json')
    if native['job']!=os.environ['SLURM_JOB_ID'] or native['step']!=os.environ['SLURM_STEP_ID']:raise ValueError('binding allocation')
    observed=native_identity();minor,uid=resolve_native(observed)
    if [uid]!=native['gpu_uuids']:raise ValueError('physical GPU mismatch')
    cache=subprocess.check_output(['/sbin/ldconfig','-p'],text=True,timeout=10)
    final,gate=rewrite(args,minor=minor,uuid=uid,libraries=driver_binds(cache),vendors=ROOT/'opencl-vendors')
    env={k:os.environ[k] for k in ('PATH','HOME','USER','LOGNAME') if k in os.environ}
    result=subprocess.run(gate,env=env,capture_output=True,text=True,timeout=25)
    rows=[json.loads(v.removeprefix('ALLOWLIST_GATE ')) for v in result.stdout.splitlines() if v.startswith('ALLOWLIST_GATE ')]
    if result.returncode or len(rows)!=1 or rows[0].get('exact_device_namespace') is not True:raise RuntimeError('GPU namespace gate')
    write(action/'binding.json',dict(native_identity=observed,namespace=rows[0],system_bindpaths_disabled=True))
    os.execve(REAL_SINGULARITY,final,env)

def worker(index):
    p=check();setup();s=schedule()[index];ep=ROOT/f'episode-{index}'
    own=infra.native_uuids(1);serv=read(ROOT/'service-native.json')['gpu_uuids']
    if set(own)&set(serv):raise ValueError('GPU overlap')
    os.environ.update(DOJO_GPU_UUIDS=own[0],PRIMARY_KEY_QWEN3_8_27B=infra.local_key(),DOJO_WORKER_IDENTITY_PATH=str(ep/'identity.json'),DOJO_EXECUTION_ID=f'{os.environ["SLURM_JOB_ID"]}.{os.environ["SLURM_STEP_ID"]}:{index}',HARDWARE='one NVIDIA RTX3090, 6 CPU cores',TIME_LIMIT='30 minutes',TIME_LIMIT_SECS=str(SECONDS),STEP_LIMIT='5',PATH=str(ROOT/'bin')+':'+os.environ['PATH'])
    from dojo.main_local_worker import _process_start_ticks,_host_boot_id
    write(ep/'identity.json',dict(pid=os.getpid(),pgid=os.getpgid(0),process_start_ticks=_process_start_ticks(os.getpid()),host_boot_id=_host_boot_id(),gpu_uuids=own,container_pid=None,container_process_start_ticks=None))
    write(ep/'native.json',dict(index=index,job=os.environ['SLURM_JOB_ID'],step=os.environ['SLURM_STEP_ID'],config_sha256=sha(ROOT/'configs'/f'{index}.json'),gpu_uuids=own))
    from dojo.utils.experiment_deadline import ExperimentDeadline,ExperimentDeadlineExpired
    deadline=ExperimentDeadline(SECONDS);write(ep/'deadline.json',deadline.receipt())
    status='unknown'
    try:
        with deadline.activate():episode(s,ep,deadline)
        status='completed'
    except ExperimentDeadlineExpired:status='budget_exhausted'
    except Exception as e:
        write(ep/'failure.json',dict(error_type=type(e).__name__,utc=utc()));raise
    finally:write(ep/'finished.json',dict(status=status,utc=utc(),elapsed_seconds=deadline.elapsed()))

def episode(s,ep,deadline):
    from dojo.config_dataclasses.run import RunConfig
    from dojo.config_dataclasses.interpreter import INTERPRETER_MAP
    from dojo.tasks.mlebench.task import MLEBenchTask
    from dojo.utils.config import build
    from dojo.utils.logger import config_logger
    from dojo.core.tasks.constants import EXECUTION_OUTPUT,VALID_SOLUTION,VALIDATION_FITNESS,VALID_SOLUTION_FEEDBACK,AUX_EVAL_INFO
    from dojo.core.solvers.utils.journal import Journal,Node
    from dojo.core.solvers.utils.metric import MetricValue,WorstMetricValue
    from dojo.utils.code_parsing import extract_code
    from dojo.core.solvers.operators.improve import improve_op
    from dojo.core.solvers.operators.debug import debug_op
    from dojo.core.solvers.llm_helpers.generic_llm import GenericLLM
    from omegaconf import OmegaConf
    from task_feedback_facts_20261001 import diagnostics,feedback,compare_to_parent
    import numpy as np
    cfg=RunConfig.load_from_json(ROOT/'configs'/f'{s["index"]}.json');Path(cfg.logger.output_dir).mkdir();config_logger(cfg)
    for n in ('openai','httpx','httpcore','LiteLLM'):logging.getLogger(n).setLevel(logging.ERROR)
    initial=read(ROOT/'starts'/f'{s["start"]}.private.json');journal=Journal();node=Node(code=initial['code'],plan=initial['plan'],_term_out=[],is_buggy=True,metric=WorstMetricValue());best=None;debug_streak=0
    cfgsolver=OmegaConf.structured(cfg.solver)
    for step in range(5):
        deadline.check();action=ep/f'action-{step}';action.mkdir();facts=None;generated='initial_reexecution';parent_facts=None;parent_sha=None
        if step:
            parent=node
            if not node.is_buggy or (debug_streak>=2 and best is not None):parent=best;debug_streak=0
            basic={'valid':not parent.is_buggy,'metric':None if parent.is_buggy else parent.metric.value,'lower_is_better':s['task']==TASKS[0],'execution_exit':parent.exit_code}
            # Facts must correspond to the chosen parent, not the last failed sibling.
            pfacts=getattr(parent,'feedback_facts',None)
            parent_facts=pfacts;parent_sha=hashlib.sha256(parent.code.encode()).hexdigest()
            message,encoded=feedback(s['arm'],basic,pfacts,parent.plan or '')
            write(action/'feedback.json',dict(arm=s['arm'],facts_json=encoded,facts_sha256=hashlib.sha256(encoded.encode()).hexdigest(),instructions=message))
            kind='debug' if parent.is_buggy else 'improve';generated=kind
            opc=copy.deepcopy(cfg.solver.operators[kind]);kw=opc.llm.generation_kwargs;kw['seed']=s['seed']*10+step;kw['bounded_request_timeout_seconds']=max(1,min(600,int(deadline.remaining())))
            random.seed(kw['seed']);np.random.seed(kw['seed']);llm=GenericLLM(OmegaConf.structured(opc))
            task=MLEBenchTask(cfg.task)
            call=(debug_op if kind=='debug' else improve_op)(llm,cfgsolver,lambda _j,_n:message,task.task_description,journal,parent,step,int(deadline.remaining()),data_preview='Use the public data files in /workspace/data; no hidden labels are available.')
            began=time.monotonic()
            try:response,info=asyncio.run(asyncio.wait_for(call,timeout=max(1,min(610,deadline.remaining()))))
            except (asyncio.TimeoutError,TimeoutError):
                write(action/'generation_failed.json',dict(status='generation_timeout',elapsed=deadline.elapsed()));break
            raw=str(response)
            if SECRET.search(raw.encode()):raise ValueError('credential output refused')
            write(action/'generation.private.json',dict(response=raw,usage=info.get('usage',{}),generation_seconds=time.monotonic()-began))
            # Store the declared goal text before the first fence, not a post-result explanation.
            plan=raw.split('```',1)[0];node=Node(code=raw,plan=plan,parents=[parent],_term_out=[],is_buggy=True,metric=WorstMetricValue())
            debug_streak=debug_streak+1 if kind=='debug' else 0
        task=MLEBenchTask(cfg.task);original=task._search_only_score
        def score_capture(task_name,submission):
            nonlocal facts
            receipt=original(task_name,submission);shutil.copyfile(submission,action/'submission.private.csv')
            if s['arm']!='A':
                spec=task._search_only_module.SPEC[task_name]
                label=(B/spec['source']/'private/dsearch.csv') if 'source' in spec else B/spec['view']/'private/dsearch.csv'
                facts=diagnostics(task_name,task.public_dir,label,submission,receipt)
                facts=compare_to_parent(facts,parent_facts,parent_sha)
            return receipt
        task._search_only_score=score_capture
        icfg=copy.deepcopy(cfg.interpreter);icfg.working_dir=str(action/'work');icfg.timeout=max(1,min(480,int(deadline.remaining())));Path(icfg.working_dir).mkdir()
        os.environ['FEEDBACK_ACTION_ROOT']=str(action)
        random.seed(s['seed']);np.random.seed(s['seed']);interpreter=build(icfg,INTERPRETER_MAP,data_dir=cfg.task.data_dir)
        state,_=task.prepare(solver_interpreter=interpreter,eval_interpreter=None)
        write(action/'started.json',dict(step=step,kind=generated,utc=utc(),elapsed=deadline.elapsed(),code_sha256=hashlib.sha256(node.code.encode()).hexdigest()))
        try:
            # Same deterministic initialization in every actual task interpreter.
            # Programs may explicitly reseed themselves; raw and executed hashes remain distinct.
            try:
                executable=extract_code(node.code)
                executable=(f'import random as _feedback_random\nimport numpy as _feedback_numpy\n_feedback_random.seed({s["seed"]})\n_feedback_numpy.random.seed({s["seed"]})\n'+f'exec(compile({executable!r}, "solution.py", "exec"))\n')
            except Exception:
                executable=node.code  # Native invalid-code result enters the common Debug path.
            state,result=task.step_task(state,executable);deadline.check()
        finally:
            interpreter.close()
            if hasattr(interpreter,'cleanup_session'):interpreter.cleanup_session()
        out=result[EXECUTION_OUTPUT];node.absorb_exec_result(out);node.is_buggy=not bool(result[VALID_SOLUTION]);node.feedback_facts=facts
        value=result.get(VALIDATION_FITNESS)
        if not node.is_buggy:node.metric=MetricValue(value,maximize=s['task']!=TASKS[0])
        node._term_out=list(node._term_out or [])+['\nTrusted development feedback: '+str(result.get(VALID_SOLUTION_FEEDBACK,''))]
        journal.append(node)
        if not node.is_buggy and (best is None or node.metric>best.metric):best=node
        write(action/'result.json',dict(step=step,kind=generated,valid=not node.is_buggy,metric=value,execution_started=result.get(AUX_EVAL_INFO,{}).get('execution_started',False),exit_code=out.exit_code,timed_out=out.timed_out,exec_seconds=out.exec_time,elapsed_seconds=deadline.elapsed(),code_sha256=hashlib.sha256(node.code.encode()).hexdigest(),executed_code_sha256=result.get(AUX_EVAL_INFO,{}).get('executed_code_sha256'),facts=facts,selected_metric=None if best is None else best.metric.value))
        write(action/'node.private.json',dict(code=node.code,plan=node.plan,terminal=node.term_out))
        if best is node:write(action/'selected.json',dict(step=step,metric=best.metric.value,elapsed=deadline.elapsed()))
    write(ep/'completed.json',dict(selected_metric=None if best is None else best.metric.value,valid=best is not None,elapsed_seconds=deadline.elapsed()))

def cleanup(index):
    ep=ROOT/f'episode-{index}';identity=read(ep/'identity.json')
    def gone(pid,ticks):
        if pid is None:return True
        try:
            v=Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split();return v[0]=='Z' or int(v[19])!=ticks
        except FileNotFoundError:return True
    if not gone(identity['pid'],identity['process_start_ticks']) or not gone(identity.get('container_pid'),identity.get('container_process_start_ticks')):raise RuntimeError('process cleanup uncertain')
    own=read(ep/'native.json')['gpu_uuids'];out=subprocess.check_output(['nvidia-smi','--query-compute-apps=gpu_uuid,pid','--format=csv,noheader,nounits'],text=True,timeout=10)
    if any(line.split(',')[0].strip() in own for line in out.splitlines()):raise RuntimeError('task GPU still occupied')

def controller():
    check();setup();job=os.environ['SLURM_JOB_ID']
    if socket.gethostname().split('.')[0]!='gpu28' or read(ROOT/'launch.json')['job']!=job:raise ValueError('allocation mismatch')
    from root_trial_step_supervisor_20260927 import supervise
    write(ROOT/'claim.json',dict(job=job,utc=utc()));env=infra.clean_env();began=time.monotonic()
    base=['srun','--exclusive','--nodes=1','--ntasks=1']
    with (ROOT/'service.private.log').open('xb') as log:
        server=subprocess.Popen(base+['--cpus-per-task=12','--gres=gpu:2','--time=03:59:00',str(PY),'-B',str(ROOT/'task_feedback_real_20261001.py'),'service'],env=env,stdout=log,stderr=log,start_new_session=True)
        try:
            while time.monotonic()-began<900:
                if server.poll() is not None:raise RuntimeError('service exited')
                try:
                    if infra.health():break
                except Exception:pass
                time.sleep(3)
            else:raise TimeoutError('service readiness')
            write(ROOT/'service-ready.json',dict(utc=utc(),startup_seconds=time.monotonic()-began))
            def run(s):
                i=s['index'];ep=ROOT/f'episode-{i}'
                write(ep/'launch.json',dict(utc=utc(),**s))
                cmd=base+['--cpus-per-task=6','--gres=gpu:1','--time=00:33:00',str(PY),'-B',str(ROOT/'task_feedback_real_20261001.py'),'worker','--index',str(i)]
                result=supervise(cmd,env=env,log_path=ep/'worker.private.log',native_path=ep/'native.json',deadline_path=ep/'deadline.json',job_id=job,config_sha256=sha(ROOT/'configs'/f'{i}.json'),index=i,seconds=SECONDS,startup_seconds=120,cleanup_seconds=60)
                cleanup(i);write(ep/'closed.json',result)
                if not result['worker_deadline_reached'] and (not (ep/'finished.json').exists() or read(ep/'finished.json')['status'] not in ('completed','budget_exhausted')):raise RuntimeError('early worker failure')
                return i
            for wave in range(6):
                if CAP-(time.monotonic()-began)<SECONDS+120:raise TimeoutError('no whole next wave budget')
                if server.poll() is not None or not infra.health():raise RuntimeError('service failed between waves')
                rows=[s for s in schedule() if s['wave']==wave]
                with ThreadPoolExecutor(max_workers=3) as pool:done=list(pool.map(run,rows))
                write(ROOT/f'wave-{wave}.json',dict(indices=done,utc=utc()))
            write(ROOT/'all-closed.json',dict(attempts=18,utc=utc()))
        except Exception as e:
            write(ROOT/'controller-error.json',dict(error_type=type(e).__name__,utc=utc()));raise
        finally:
            if server.poll() is None:
                server.send_signal(signal.SIGTERM)
                try:server.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    n=read(ROOT/'service-native.json')
                    if n['job']!=job or not n['step'].isdigit():raise ValueError('service step identity')
                    subprocess.run(['scancel','--signal=KILL',job+'.'+n['step']],check=True,timeout=45);server.wait(timeout=30)
            write(ROOT/'closed.json',dict(utc=utc(),elapsed_seconds=time.monotonic()-began,service_closed=server.poll() is not None))

if __name__=='__main__':
    os.umask(0o077);a=argparse.ArgumentParser();a.add_argument('mode',choices=['prepare','check','cpu','submit','service','worker','controller']);a.add_argument('--index',type=int);x=a.parse_args()
    if x.mode=='worker':worker(x.index)
    elif x.mode=='check':check();print('FROZEN_PLAN_VALID')
    else:globals()[x.mode]()
