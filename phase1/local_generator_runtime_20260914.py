"""Bounded two-draft local-generator integration, never a search-effect trial.

Uses the existing native draft/source and original MLE image. One own allocation:
2 generator GPUs + 1 execution GPU, 12 CPUs, at most 60 minutes. No fit or critic.
"""
import argparse,asyncio,copy,csv,ctypes,datetime,hashlib,inspect,json,logging,os
from pathlib import Path
import random,re,secrets,shutil,signal,socket,subprocess,sys,tarfile,time,urllib.error,urllib.request,uuid

BASE=Path('/research/d7/spc/yzyang4')
ASSETS=BASE/'local-qwen27b-20260914-zcx1k1dy'
ROOT=ASSETS/'integration-v6'
PREVIOUS_ATTEMPTS={'13365':80,'13366':123,'13367':369}
ATTEMPT_SECONDS=3600-sum(PREVIOUS_ATTEMPTS.values())
PLAN_SHA='982e97a454ee502f89a0df72b2c3ae1626d24cc942f828137ed6f45aaaf8e4cd'
PYTHON=BASE/'venvs/aira/bin/python'
SOURCE_SHA='c1206c13df05d9ab6b73119aabfb75820e90807e55a76f9f288f5d305a769291'
INPUT_SHA='7da450b0e9a2517216de79f8ad4398621d68bd615a865b259784cb37608d1f77'
DONOR=BASE/'forets-fresh-integration-20260914-ih6u0mpw'
HELPERS=('forets_closed_pool_native_20260911.py','forets_current_pool_native_20260912.py',
 'forets_gpu_binding_20260911.py','forets_native_cuda_identity_20260911.py',
 'forets_native_gpu_binding_20260911.py','forets_opencl_allowlist_20260911.py',
 'forets_opencl_readonly_ab.py','forets_closed_pool_20260911.py','bin/singularity')
SHAPES=re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,}|Bearer\s+[a-z0-9_.-]{20,})')

def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def slurm_duration(seconds):return f'{seconds//3600:02d}:{seconds//60%60:02d}:{seconds%60:02d}'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_bytes())
def write(path,value):
    raw=(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n').encode()
    if SHAPES.search(raw):raise ValueError('credential-shaped output withheld')
    with path.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    return hashlib.sha256(raw).hexdigest()
def check_files():
    if ROOT.resolve(strict=True)!=ROOT:raise ValueError('integration scope')
    p=read(ROOT/'prepared.json')
    for name,digest in p['files'].items():
        path=ROOT/name
        if path.is_symlink() or sha(path)!=digest:raise ValueError('prepared code drift')
    if sha(ASSETS/'calibration-inputs.json')!=INPUT_SHA or sha(ASSETS/'source.tar')!=SOURCE_SHA:
        raise ValueError('native source/input drift')
    with tarfile.open(ASSETS/'source.tar') as bundle:
        for member in bundle.getmembers():
            path=Path(member.name)
            if path.is_absolute() or '..' in path.parts or not (member.isfile() or member.isdir()):raise ValueError('source archive path')
            if member.isfile() and (ASSETS/'source'/path).read_bytes()!=bundle.extractfile(member).read():raise ValueError('extracted native source drift')
    return p

def step_command(role,gpus):
    if (role,gpus) not in (('server',2),('worker',1)):raise ValueError('fixed role layout')
    # Site Slurm is 19.05.4: --exact is not supported. Keep the tested exclusive
    # per-step CPU/GRES requests rather than introducing a newer CLI option.
    return ['srun','--jobid='+os.environ['SLURM_JOB_ID'],'--exclusive','--nodes=1','--ntasks=1',
            '--cpus-per-task=6','--gres=gpu:'+str(gpus),'--time='+slurm_duration(ATTEMPT_SECONDS-60),'--job-name=local27b-'+role,
            str(PYTHON),'-u','-B',str(ROOT/Path(__file__).name),role]

def binding_context(env):
    if env['FORETS_CURRENT_POOL_ROOT']!=str(ROOT):raise ValueError('wrong MLE root')
    identity=Path(env['DOJO_WORKER_IDENTITY_PATH'])
    if identity.parent!=ROOT or not re.fullmatch(r'identity-[0-3]\.json',identity.name):raise ValueError('MLE identity scope')
    if read(ROOT/'execution.claim.json')['job']!=env['SLURM_JOB_ID']:raise ValueError('wrong allocation')
    return identity.with_suffix('.native-binding.json')

def native_service_devices():
    """Observe CUDA-selected UUIDs, not a Slurm ordinal-to-NVML conversion."""
    if socket.gethostname().split('.')[0]!='gpu28' or not os.environ.get('SLURM_STEP_ID','').isdigit():
        raise ValueError('own gpu28 Slurm step required')
    C=ctypes;driver=C.CDLL('libcuda.so.1')
    def call(name,*args):
        rc=getattr(driver,name)(*args)
        if rc:raise RuntimeError(name+' failed '+str(rc))
    call('cuInit',C.c_uint(0));count=C.c_int();call('cuDeviceGetCount',C.byref(count))
    if count.value!=2:raise ValueError('generator must see exactly two allocated CUDA devices')
    devices=[]
    for i in range(2):
        device=C.c_int();call('cuDeviceGet',C.byref(device),C.c_int(i))
        raw=(C.c_ubyte*16)();call('cuDeviceGetUuid',C.byref(raw),device)
        devices.append('GPU-'+str(uuid.UUID(bytes=bytes(raw))))
    if len(set(devices))!=2:raise ValueError('duplicate service GPU')
    return devices

def service_command():
    return ['/usr/bin/singularity','exec','--containall','--cleanenv','--no-home','--nv',
            '--no-mount','bind-paths,cwd','--bind',str(ASSETS/'model')+':/model:ro',
            '--bind',str(ROOT/'service-cache')+':/cache:rw',
            '--bind',str(ROOT/'service-cache/tmp')+':/tmp:rw',
            '--bind',str(ROOT/'service_entry.py')+':/run/service_entry.py:ro',
            '--pwd','/cache',str(ASSETS/'vllm.sif'),'/usr/bin/python3','/run/service_entry.py']

def local_key():
    path=ROOT/'.service.env'
    if path.is_symlink() or path.stat().st_mode & 0o077:raise ValueError('private local auth mode')
    raw=path.read_text().strip()
    if not re.fullmatch(r'PRIMARY_KEY_QWEN3_8_27B=[0-9a-f]{64}',raw):raise ValueError('local auth shape')
    return raw.split('=',1)[1]

def server():
    check_files();devices=native_service_devices();command=service_command()
    write(ROOT/'service-native.json',dict(utc=utc(),job=os.environ['SLURM_JOB_ID'],step=os.environ['SLURM_STEP_ID'],
          uuid=devices,cuda_visible_devices=os.environ.get('CUDA_VISIBLE_DEVICES'),command=command))
    env={k:os.environ[k] for k in ('PATH','HOME','USER','LOGNAME') if k in os.environ}
    values=dict(CUDA_VISIBLE_DEVICES=','.join(devices),EXPECTED_GPU_UUIDS=','.join(devices),
                VLLM_API_KEY=local_key(),VLLM_WORKER_MULTIPROC_METHOD='spawn',
                VLLM_CACHE_ROOT='/cache/vllm',TRITON_HOME='/cache/triton',TORCH_HOME='/cache/torch',
                HF_HOME='/cache/hf',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',
                FLASHINFER_WORKSPACE_BASE='/cache/flashinfer',XDG_CACHE_HOME='/cache/xdg',
                TMPDIR='/tmp',MAX_JOBS='2',VLLM_NO_USAGE_STATS='1',VLLM_CONFIG_ROOT='/cache/vllm-config',
                NO_PROXY='127.0.0.1,localhost',no_proxy='127.0.0.1,localhost')
    # Do not override LD_LIBRARY_PATH: preserve the supplied CUDA-13 image setup.
    env.update({'SINGULARITYENV_'+k:v for k,v in values.items()})
    os.execve(command[0],command,env)

def own_health():
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    # Require authentication before sending our token. A coincidental node-local
    # service that accepts all keys must never be mistaken for our allocation.
    try:
        with opener.open('http://127.0.0.1:8000/v1/models',timeout=3):return False
    except urllib.error.HTTPError as e:
        if e.code!=401:return False
    request=urllib.request.Request('http://127.0.0.1:8000/v1/models',headers={'Authorization':'Bearer '+local_key()})
    with opener.open(request,timeout=3) as response:
        value=json.loads(response.read(100000))
    return [row['id'] for row in value.get('data',[])]==['qwen3.8-27b']

def setup_worker(p):
    for k in ('PRIMARY_KEY','OPENROUTER_API_KEY','FORETS_RUN_BUDGET_PATH','FORETS_PAID_SCOPE',
              'FORETS_NATIVE_RELEASE','FORETS_CLOSED_POOL_ROOT','FORETS_NATIVE_INTEGRATION_ROOT'):
        os.environ.pop(k,None)
    os.environ.update(PYTHON_DOTENV_DISABLED='1',PYTHONDONTWRITEBYTECODE='1',LITELLM_LOCAL_MODEL_COST_MAP='True',
       LOGGING_DIR=str(ROOT),MLE_BENCH_DATA_DIR=str(BASE/'mle-bench-data'),
       SUPERIMAGE_DIR=str(BASE/'aira-dojo/build/superimage'),DEFAULT_SLURM_PARTITION='gpu_24h',
       DEFAULT_SLURM_ACCOUNT='gpu',DEFAULT_SLURM_QOS='gpu',FORETS_CURRENT_POOL_ROOT=str(ROOT),
       FORETS_SOURCE_COMMIT=p['commit'],PRIMARY_KEY_QWEN3_8_27B=local_key(),
       HARDWARE='one NVIDIA RTX 3090 (24 GiB), six CPU cores',
       PATH=str(ROOT/'bin')+':'+os.environ['PATH'],NO_PROXY='127.0.0.1,localhost',no_proxy='127.0.0.1,localhost')
    sys.path[:0]=[str(ROOT),str(ASSETS/'source/src')];logging.disable(logging.CRITICAL)

def config_for(case,index,timeout):
    from dojo.config_dataclasses.interpreter.fresh_container import FreshContainerInterpreterConfig
    from dojo.config_dataclasses.utils import dataclass_from_dict
    cfg=copy.deepcopy(case['interpreter']);cfg['working_dir']=str(ROOT/f'work-{index}');cfg['timeout']=timeout
    cfg=dataclass_from_dict(FreshContainerInterpreterConfig,cfg);cfg.validate()
    return cfg

def interpreter(case,index,timeout):
    from dojo.core.interpreters.fresh_container import FreshContainerInterpreter
    cfg=config_for(case,index,timeout)
    write(ROOT/f'identity-{index}.json',{})
    os.environ['DOJO_WORKER_IDENTITY_PATH']=str(ROOT/f'identity-{index}.json')
    return FreshContainerInterpreter(cfg,data_dir=Path(case['public_data_dir']))

async def generate_one(case,preview):
    import numpy as np
    from omegaconf import OmegaConf
    import dojo.core.solvers.llm_helpers.generic_llm as generic
    from dojo.core.solvers.operators.draft import draft_op
    from dojo.core.solvers.utils.journal import Journal
    from dojo.core.solvers.utils.response import extract_code
    random.seed(49);np.random.seed(49)
    # Only suppress the optional global experiment logger, never the transport.
    generic.get_logger=lambda:None
    llm=generic.GenericLLM(OmegaConf.create(case['operator']));started=time.monotonic()
    row=dict(index=case['index'],task=case['task'],seed=49,status='generation_unknown')
    try:
        answer,info=await asyncio.wait_for(draft_op(llm,OmegaConf.create(case['solver_draft']),None,
                 case['description'],Journal(),0,1800,data_preview=preview),timeout=1200)
        write(ROOT/f'draft-{case["index"]}.private.json',dict(answer=answer,info=info))
        code=extract_code(answer);finish=info['usage'].get('finish_reason')
        row.update(status='truncated' if finish=='length' else ('code_ready' if code.strip() else 'no_code'),
                   finish_reason=finish,prompt_tokens=info['usage'].get('prompt_tokens'),
                   completion_tokens=info['usage'].get('completion_tokens'),code_chars=len(code))
        if row['status']=='code_ready':
            with (ROOT/f'code-{case["index"]}.private.py').open('x') as f:f.write(code)
    except Exception as e:row.update(status='generation_failed',error_type=type(e).__name__)
    row['generation_seconds']=time.monotonic()-started
    write(ROOT/f'generation-{case["index"]}.json',row)
    return row

async def warmups():
    import httpx
    out=[]
    async with httpx.AsyncClient(timeout=80,trust_env=False) as client:
        for structured in (False,True):
            payload=dict(model='qwen3.8-27b',messages=[{'role':'user','content':'Return a JSON object with an ok field set to true.' if structured else 'Reply with the word ready.'}],
                         max_tokens=256,temperature=.6,top_p=.95,seed=49,chat_template_kwargs={'enable_thinking':True})
            if structured:payload['response_format']={'type':'json_object'}
            started=time.monotonic()
            r=await client.post('http://127.0.0.1:8000/v1/chat/completions',json=payload,headers={'Authorization':'Bearer '+local_key()})
            r.raise_for_status();v=r.json();choice=v['choices'][0]
            row=dict(structured=structured,wall_seconds=time.monotonic()-started,finish_reason=choice.get('finish_reason'),usage=v.get('usage'))
            if structured:
                try:row['json_object_parsed']=isinstance(json.loads(choice['message']['content']),dict)
                except (ValueError,TypeError):row['json_object_parsed']=False
            out.append(row)
    write(ROOT/'warmup.json',dict(rows=out,not_timed_drafts=True))

def worker():
    p=check_files();setup_worker(p);start=time.monotonic()
    if socket.gethostname().split('.')[0]!='gpu28':raise ValueError('wrong worker node')
    cases=read(ASSETS/'calibration-inputs.json')['cases'];previews=[]
    from dojo.core.solvers.utils import data_preview
    script=Path(inspect.getsourcefile(data_preview)).read_text()+"\nprint(generate(Path('.').resolve()))"
    for i,case in enumerate(cases):
        w=interpreter(case,i,120)
        try:
            ans=w.run(script,include_exec_time=False)
            if ans.exit_code or ans.timed_out:raise RuntimeError('native data preview failed')
            text='\n'.join(ans.term_out)
            if SHAPES.search(text.encode()):raise ValueError('preview security')
            previews.append(text);write(ROOT/f'preview-{i}.private.json',dict(text=text,execution_seconds=ans.exec_time))
        finally:w.close()
    # Both previews must be produced before using the service. Check actual
    # disjoint native devices before ANY generator request is sent.
    until=start+900
    while time.monotonic()<until:
        try:
            if (ROOT/'service-native.json').exists() and own_health():break
        except Exception:pass
        time.sleep(2)
    else:raise TimeoutError('service startup deadline')
    service=set(read(ROOT/'service-native.json')['uuid'])
    execution={read(ROOT/f'identity-{i}.native-binding.json')['native_identity']['selected_uuid'] for i in range(2)}
    if len(execution)!=1 or service & execution:raise ValueError('service/execution GPUs overlap')
    write(ROOT/'ready.json',dict(utc=utc(),startup_seconds=time.monotonic()-start,service_uuids=sorted(service),execution_uuids=sorted(execution),disjoint=True))
    asyncio.run(warmups())
    async def drafts():return await asyncio.gather(*(generate_one(case,previews[i]) for i,case in enumerate(cases)))
    rows=asyncio.run(drafts())
    for i,(row,case) in enumerate(zip(rows,cases)):
        row.update(execution_status='not_started',submission_present=False)
        if row['status']!='code_ready':continue
        w=None
        try:
            w=interpreter(case,i+2,300);ans=w.run((ROOT/f'code-{i}.private.py').read_text(),file_name='solution.py',include_exec_time=False)
            raw=''.join(ans.term_out)
            if SHAPES.search(raw.encode()):raise ValueError('program-output security')
            with (ROOT/f'execution-{i}.private.log').open('x') as f:f.write(raw)
            row.update(execution_status='returned',execution_seconds=ans.exec_time,exit_code=ans.exit_code,timed_out=ans.timed_out)
            path=w.fetch_file(ROOT/f'work-{i+2}'/'submission.csv')
            if path is not None:
                row.update(submission_present=True,submission_sha256=sha(Path(path)))
        except Exception as e:row.update(execution_status='infrastructure_unknown',execution_error=type(e).__name__)
        finally:
            if w is not None:w.close()
        write(ROOT/f'execution-{i}.json',row)
    for row in rows:row.update(commit=p['commit'],model=p['model'],revision=p['revision'],job=os.environ['SLURM_JOB_ID'],gpu_hours_cap=3)
    fields=sorted(set().union(*(r.keys() for r in rows)))
    with (ROOT/'runs.csv').open('x',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows)
    result=dict(status='COMPLETED_DEVELOPMENT_NOT_EFFECT',utc=utc(),rows=rows,worker_seconds=time.monotonic()-start,
                no_critic=True,no_training=True,no_external_score_read=True,protected_cohorts_untouched=True)
    write(ROOT/'calibration-results.json',result)
    print(json.dumps(result),flush=True)

def stop_owned(p):
    if p.poll() is None:
        try:os.killpg(p.pid,signal.SIGTERM)
        except ProcessLookupError:pass
        try:p.wait(timeout=15)
        except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait(timeout=5)

def controller():
    p=check_files();asset_check(p)
    if read(ROOT/'cpu-preflight.json')['status']!='PASS_CPU_WIRING_NOT_GPU_ACCEPTANCE':raise ValueError('CPU wiring absent')
    if socket.gethostname().split('.')[0]!='gpu28':raise ValueError('wrong allocation')
    with socket.socket() as sock:sock.bind(('127.0.0.1',8000))
    write(ROOT/'execution.claim.json',dict(utc=utc(),job=os.environ['SLURM_JOB_ID'],prepared_sha256=sha(ROOT/'prepared.json')))
    with (ROOT/'.service.env').open('x') as f:f.write('PRIMARY_KEY_QWEN3_8_27B='+secrets.token_hex(32)+'\n')
    processes=[];logs=[];started=time.monotonic();state='infrastructure_failed'
    env=dict(os.environ)
    for k in ('CUDA_VISIBLE_DEVICES','SLURM_STEP_GPUS','SLURM_STEP_ID','GPU_DEVICE_ORDINAL','PRIMARY_KEY','OPENROUTER_API_KEY'):
        env.pop(k,None)
    try:
        for role,gpus in (('server',2),('worker',1)):
            log=(ROOT/f'{role}.private.log').open('xb');logs.append(log)
            processes.append(subprocess.Popen(step_command(role,gpus),env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True))
        while time.monotonic()-started<ATTEMPT_SECONDS-100:
            if processes[1].poll() is not None:
                state='worker_finished' if processes[1].returncode==0 else 'worker_failed';break
            if processes[0].poll() is not None:state='service_exited';break
            time.sleep(2)
        else:state='controller_deadline'
    finally:
        for child in reversed(processes):stop_owned(child)
        for log in logs:log.close()
        write(ROOT/'closed.json',dict(utc=utc(),status=state,controller_seconds=time.monotonic()-started,
              job=os.environ['SLURM_JOB_ID'],process_codes=[x.returncode for x in processes],actual_gpu_hours_from_sacct_pending=True,gpu_hours_cap=3))
    if state!='worker_finished':raise SystemExit(1)

def asset_check(p):
    if sha(ASSETS/'plan.json')!=PLAN_SHA:raise ValueError('fixed asset plan drift')
    complete=read(ASSETS/'complete.json');plan=read(ASSETS/'plan.json')
    if (not complete.get('model_ready') or complete['revision']!=p['revision'] or
        complete['model']!=p['model'] or complete['plan_sha256']!=sha(ASSETS/'plan.json')):raise ValueError('assets incomplete')
    records={v['path']:v for v in complete['files']}
    if (len(records)!=len(complete['files']) or len(records)!=len(plan['files']) or
        set(records)!={v['path'] for v in plan['files']}):raise ValueError('incomplete or duplicate asset manifest')
    for entry in plan['files']:
        path=ASSETS/entry['path'];row=records[entry['path']]
        if path.is_symlink() or path.stat().st_size!=entry['size'] or row['bytes']!=entry['size']:raise ValueError('asset size drift')
        if entry['expected'] is not None and row['digest']!=entry['expected']:raise ValueError('publisher digest differs')
    if records['vllm.sif']['digest']!='495ca35a3fa7fc534bbd855829af1b86ce75ab9a5675b3b1ab7dba58ca74b7fa':raise ValueError('image identity differs')
    return sha(ASSETS/'complete.json')

def cpu():
    p=check_files()
    os.environ.update(PYTHON_DOTENV_DISABLED='1',LOGGING_DIR=str(ROOT),MLE_BENCH_DATA_DIR=str(BASE/'mle-bench-data'),
       SUPERIMAGE_DIR=str(BASE/'aira-dojo/build/superimage'),DEFAULT_SLURM_PARTITION='gpu_24h',
       DEFAULT_SLURM_ACCOUNT='gpu',DEFAULT_SLURM_QOS='gpu',PRIMARY_KEY_QWEN3_8_27B='synthetic-cpu-only',
       HARDWARE='one NVIDIA RTX 3090 (24 GiB), six CPU cores')
    sys.path[:0]=[str(ROOT),str(ASSETS/'source/src')]
    cases=read(ASSETS/'calibration-inputs.json')['cases']
    if [x['task'] for x in cases]!=p['tasks'] or len(cases)!=2:raise ValueError('case mismatch')
    for i,case in enumerate(cases):
        for index,timeout in ((i,120),(i+2,300)):
            cfg=config_for(case,index,timeout)
            if cfg.timeout!=timeout or cfg.working_dir!=str(ROOT/f'work-{index}'):raise ValueError('actual interpreter configuration mismatch')
        generation=case['operator']['llm']['generation_kwargs']
        if generation['seed']!=49 or generation['max_tokens']!=32768 or generation['bounded_max_attempts']!=1:raise ValueError('draft config mismatch')
    compile((ROOT/'service_entry.py').read_text(),'service_entry.py','exec')
    subprocess.run(['bash','-n',str(ROOT/'run.sbatch')],check=True,timeout=10)
    write(ROOT/'cpu-preflight.json',dict(status='PASS_CPU_WIRING_NOT_GPU_ACCEPTANCE',utc=utc(),prepared_sha256=sha(ROOT/'prepared.json'),
          actual_config_paths=4,source_sha256=SOURCE_SHA,real_generation=0,task_executions=0,gpu_jobs=0))
    print('PASS_CPU_WIRING_NOT_GPU_ACCEPTANCE',flush=True)

def submit():
    p=check_files();complete_sha=asset_check(p);preflight=read(ROOT/'cpu-preflight.json')
    if preflight['status']!='PASS_CPU_WIRING_NOT_GPU_ACCEPTANCE' or preflight['prepared_sha256']!=sha(ROOT/'prepared.json'):raise ValueError('CPU preflight')
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    previous=subprocess.check_output(['sacct','-X','-j',','.join(PREVIOUS_ATTEMPTS),'-n','-P','-o','JobID,State,ElapsedRaw,AllocTRES'],env=env,text=True,timeout=20).strip().splitlines()
    if len(previous)!=len(PREVIOUS_ATTEMPTS):raise ValueError('prior allocation accounting unknown')
    seen=set()
    for line in previous:
        row=line.split('|');job=row[0]
        if job in seen or job not in PREVIOUS_ATTEMPTS or row[1:3]!=['FAILED',str(PREVIOUS_ATTEMPTS[job])] or 'gres/gpu=3' not in row[3].split(','):
            raise ValueError('prior allocation resource accounting differs')
        seen.add(job)
    if (sum(PREVIOUS_ATTEMPTS.values())+ATTEMPT_SECONDS)*3>3*3600:raise ValueError('combined GPU budget exceeded')
    queue=subprocess.check_output(['squeue','-u','yzyang4','-h','-o','%i|%T'],env=env,text=True,timeout=20).strip().splitlines()
    if queue not in ([],['12535|PENDING']):raise ValueError('unexpected concurrent jobs: reassess resource budget')
    write(ROOT/'submit-intent.json',dict(utc=utc(),prepared_sha256=sha(ROOT/'prepared.json'),complete_sha256=complete_sha,gpu_hours_cap=3))
    result=subprocess.run(['sbatch','--parsable','--chdir='+str(ROOT),'--output='+str(ROOT/'allocation-%j.out'),
        '--error='+str(ROOT/'allocation-%j.err'),str(ROOT/'run.sbatch')],env=env,capture_output=True,text=True,timeout=25)
    job=result.stdout.strip().split(';')[0]
    if result.returncode or not job.isdigit():raise RuntimeError('submission uncertain; inspect before retry')
    write(ROOT/'launch.json',dict(job=job,utc=utc(),commit=p['commit'],gpu_hours_cap=3))
    print(json.dumps(dict(event='SUBMITTED',job=job,root=str(ROOT),gpu_hours_cap=3)),flush=True)

SERVICE_ENTRY=r'''import json,os,sys

def start_service():
 import torch
 expected=os.environ['EXPECTED_GPU_UUIDS'].split(',')
 if not torch.cuda.is_available() or torch.cuda.device_count()!=2:raise RuntimeError('two CUDA GPUs required; no CPU fallback')
 actual=[]
 for i in range(2):
  p=torch.cuda.get_device_properties(i)
  actual.append(str(p.uuid).lower().removeprefix('gpu-'))
  x=torch.tensor([[1.,2.],[3.,4.]],device='cuda:'+str(i))
  if (x@x).cpu().tolist()!=[[7.,10.],[15.,22.]]:raise RuntimeError('service CUDA arithmetic')
 if actual!=[x.lower().removeprefix('gpu-') for x in expected]:raise RuntimeError('container GPU identity mismatch')
 print('LOCAL_SERVICE_CUDA '+json.dumps({'torch':torch.__version__,'uuids':expected,'correct':True}),flush=True)
 sys.argv=['vllm','serve','/model','--served-model-name','qwen3.8-27b','--host','127.0.0.1','--port','8000',
  '--tensor-parallel-size','2','--max-model-len','131072','--gpu-memory-utilization','0.95','--kv-cache-dtype','fp8_e5m2',
  '--limit-mm-per-prompt','{"image":0,"video":0}','--max-num-seqs','6','--seed','49']
 from vllm.entrypoints.cli.main import main
 main()

if __name__=='__main__':
 start_service()
'''

def prepare(commit):
    if not re.fullmatch('[0-9a-f]{40}',commit):raise ValueError('exact commit')
    if sha(ASSETS/'source.tar')!=SOURCE_SHA or sha(ASSETS/'calibration-inputs.json')!=INPUT_SHA:raise ValueError('input identity')
    # Preserve the CPU-only predecessors. v3 fixes the manifest count gate:
    # 17 model files plus one image, derived from the fixed plan, not a literal.
    for previous in ('integration','integration-v2'):
        if (ASSETS/previous/'submit-intent.json').exists():raise ValueError('prior integration may have been submitted')
    for folder,job in (('integration-v3','13365'),('integration-v4','13366'),('integration-v5','13367')):
        failed=read(ASSETS/folder/'closed.json')
        if failed['job']!=job or failed['status']!='service_exited':raise ValueError('previous service attempt not closed')
    ROOT.mkdir(exist_ok=False);prior=read(DONOR/'prepared.json')
    for name in HELPERS:
        if sha(DONOR/name)!=prior['files'][name]:raise ValueError('existing GPU helper changed')
        target=ROOT/name;target.parent.mkdir(exist_ok=True);shutil.copy2(DONOR/name,target)
    shutil.copy2(Path(__file__),ROOT/Path(__file__).name)
    (ROOT/'forets_current_pool_20260912.py').write_text('from local_generator_runtime_20260914 import binding_context\n')
    (ROOT/'opencl-vendors').mkdir();(ROOT/'opencl-vendors/nvidia.icd').write_text('libnvidia-opencl.so.1\n')
    (ROOT/'service-cache').mkdir();(ROOT/'service-cache/tmp').mkdir();(ROOT/'service_entry.py').write_text(SERVICE_ENTRY)
    sbatch='''#!/bin/bash
#SBATCH --job-name=local27b-native-drafts
#SBATCH --partition=gpu_24h
#SBATCH --account=gpu
#SBATCH --qos=gpu
#SBATCH --nodelist=gpu28
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:3
#SBATCH --cpus-per-task=12
#SBATCH --time=ATTEMPT_TIME
#SBATCH --no-requeue
set -euo pipefail
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHON_DOTENV_DISABLED=1
timeout --signal=TERM --kill-after=20s ATTEMPT_TIMEOUTs PYTHON -u -B ROOT/local_generator_runtime_20260914.py controller
'''.replace('PYTHON -u',str(PYTHON)+' -u').replace('ROOT',str(ROOT)).replace('ATTEMPT_TIMEOUT',str(ATTEMPT_SECONDS-50)).replace('ATTEMPT_TIME',slurm_duration(ATTEMPT_SECONDS))
    (ROOT/'run.sbatch').write_text(sbatch)
    files={str(p.relative_to(ROOT)):sha(p) for p in ROOT.rglob('*') if p.is_file()}
    write(ROOT/'prepared.json',dict(utc=utc(),commit=commit,files=files,source_sha256=SOURCE_SHA,input_sha256=INPUT_SHA,
          model='cyankiwi/Qwen3.8-27B-AWQ-BF16-INT4',revision='dc430725f831dd90d9271738b877879a46a82239',
          tasks=['leaf-classification','spaceship-titanic'],seed=49,drafts=2,warmup_calls=2,training=False,gpu_hours_cap=3,
          attempt_seconds_cap=ATTEMPT_SECONDS,previous_attempts=PREVIOUS_ATTEMPTS,total_gpu_hours_cap=3))
    print(json.dumps(dict(event='PREPARED_NOT_SUBMITTED',root=str(ROOT),prepared_sha256=sha(ROOT/'prepared.json'))))

if __name__=='__main__':
    os.umask(0o077);p=argparse.ArgumentParser();p.add_argument('role',choices=('prepare','cpu','submit','controller','server','worker'));p.add_argument('--commit');a=p.parse_args()
    if a.role=='prepare':prepare(a.commit)
    else:globals()[a.role]()
