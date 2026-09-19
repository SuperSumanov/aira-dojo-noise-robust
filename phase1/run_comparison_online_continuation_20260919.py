"""Same-budget, fresh conditioned repair episodes; not full-search E2E."""
import argparse,asyncio,copy,hashlib,json,logging,math,os,random,re,secrets,shutil,socket,subprocess,sys,tarfile,tempfile,time,types,urllib.error,urllib.request
from pathlib import Path,PurePosixPath
from unittest.mock import patch
import local_generator_runtime_20260914 as rt
import run_comparison_live_debug_20260919 as first

BASE=rt.BASE
SCRIPT=Path(__file__).name
PLAN='comparison_online_continuation_plan_20260919.json'
TASK='spooky-author-identification'
ROOT_PREFIX='comparison-online-continuation-20260919-'
CONTEXT_MODULE='run_comparison_online_continuation_20260919'
EPISODE=2100
CAP=6000
FULL_DEADLINE=False
FILES=(SCRIPT,PLAN,'local_generator_runtime_20260914.py','run_comparison_live_debug_20260919.py')
BANKS={1:BASE/'comparison-reuse-20260919-5m6jrtah',2:BASE/'comparison-reuse-20260919-851fmp2v'}
PREPARED={1:'5d7e98280f3b223bbf8c6968ebd3c84857b5329eac0744a51d3c16d3ced24518',2:'40b291747042f3a1e04781870e3d67e33342a29ac1aea896c1a1a93d2a65c399'}

def scope(root):
    root=root.resolve(strict=True)
    if root.parent!=BASE or not re.fullmatch(re.escape(ROOT_PREFIX)+r'[a-z0-9_]+',root.name):raise ValueError('root scope')
    return root

def check(root):
    scope(root);p=rt.read(root/'prepared.json')
    for name,digest in p['files'].items():
        f=root/name
        if f.is_symlink() or rt.sha(f)!=digest:raise ValueError('prepared drift')
    return p

def select_cache(rows,seed):
    if len(rows)!=4 or len({r['node'] for r in rows})!=4 or any(r['role']!='cache' for r in rows):raise ValueError('four distinct caches')
    ordered=sorted(rows,key=lambda r:r['index'])
    return random.Random(f'continuation-online-v1:20260919:{seed}').choice(ordered)

def inputs():
    cases=first.prefix_inputs();configs={}
    with tarfile.open(first.ARCHIVE,'r|gz') as bundle:
        for member in bundle:
            path=PurePosixPath(member.name)
            if not member.isfile() or path.name!='dojo_config.json':continue
            run=hashlib.sha256(str(path.parent).encode()).hexdigest()[:16]
            if run not in first.CONFIG_SHAS:continue
            raw=bundle.extractfile(member).read()
            if hashlib.sha256(raw).hexdigest()!=first.CONFIG_SHAS[run] or rt.SHAPES.search(raw):raise ValueError('config drift/security')
            configs[run]=json.loads(raw)['solver']
    for case in cases:
        cfg=configs[case['run']]
        if cfg['max_debug_depth']!=20 or cfg['use_test_score'] is not False:raise ValueError('original bounds')
        case['analysis_operator']=copy.deepcopy(cfg['operators']['analyze'])
        case['analysis_sampling']={k:cfg['operators']['analyze']['llm']['generation_kwargs'].get(k) for k in ('temperature','top_p')}
        root=BANKS[case['seed']]
        if rt.sha(root/'prepared.json')!=PREPARED[case['seed']]:raise ValueError('bank identity')
        rows=[r for r in rt.read(root/'prepared.json')['rows'] if r['role']=='cache' and r['seed']==case['seed']]
        row=select_cache(rows,case['seed']);raw=(root/'codes'/f'{row["index"]}.private.py').read_bytes()
        if hashlib.sha256(raw).hexdigest()!=row['code_sha256'] or rt.SHAPES.search(raw):raise ValueError('cache code identity/security')
        # No outcome table, score, native-analysis or external grade is loaded here.
        case['cache']=dict(code=raw.decode(),code_sha256=row['code_sha256'],node=row['node'],index=row['index'])
    return cases

def lane_setup(root,lane):
    p=check(root);rt.ROOT=root/f'lane-{lane}';rt.ATTEMPT_SECONDS=CAP
    rt.check_files();rt.setup_worker(p);sys.path.insert(0,str(root))
    os.environ['PATH']=str(root/'bin')+':'+os.environ['PATH']
    import dojo.core.solvers.llm_helpers.backends.selfhosted_guard as guard
    if not hasattr(guard,'_original_paired_key'):guard._original_paired_key=guard.selfhosted_key
    original=guard._original_paired_key;port=8000+lane
    def local_key(model,url,env):
        if url!=f'http://127.0.0.1:{port}/v1':raise ValueError('wrong dedicated lane endpoint')
        return original(model,'http://127.0.0.1:8000/v1',env)
    guard.selfhosted_key=local_key
    if FULL_DEADLINE:
        import dojo.core.solvers.llm_helpers.backends.lite_llm as backend
        from comparison_full_deadline_policy_20260919 import install
        install(backend)
    return p

def operator(case,kind,lane,depth,remaining):
    cfg=copy.deepcopy(case['analysis_operator'] if kind=='analyze' else case['operator'])
    cfg['llm']['client']=dict(api='litellm',model_id='qwen3.8-27b',base_url=f'http://127.0.0.1:{8000+lane}/v1',provider='selfhosted',use_azure_client=False)
    seed=(300000+case['seed']) if kind=='analyze' and depth==0 else (200000 if kind=='analyze' else 100000)+100*case['seed']+depth
    sampling=case['analysis_sampling'] if kind=='analyze' else dict(temperature=.6,top_p=.95)
    request_limit=EPISODE if FULL_DEADLINE else (300 if kind=='analyze' else 1200)
    cfg['llm']['generation_kwargs']=dict(bounded_transport=True,bounded_max_attempts=1,bounded_request_timeout_seconds=max(1,min(request_limit,remaining)),
        max_tokens=32768,temperature=.6 if sampling.get('temperature') is None else sampling['temperature'],top_p=.95 if sampling.get('top_p') is None else sampling['top_p'],seed=seed,
        extra_body={'chat_template_kwargs':{'enable_thinking':True}},structured_output_retries=0)
    if kind=='analyze':cfg['llm']['generation_kwargs']['structured_output_mode']='json'
    return cfg

def new_journal(case):
    from dojo.core.solvers.utils.journal import Journal,Node
    from dojo.core.solvers.utils.metric import WorstMetricValue
    journal=Journal();root=Node(code='',plan='',analysis='',is_buggy=True,metric=WorstMetricValue());journal.append(root)
    node=Node(code=case['code'],plan=case['plan'],analysis=case['analysis'],parents=[root],
        is_buggy=True,metric=WorstMetricValue(),_term_out=[case['term_out']],exit_code=1,operators_used=['draft'])
    journal.append(node)
    return journal,root,node

async def call_native(case,kind,lane,depth,remaining,node,journal,preview):
    from omegaconf import OmegaConf
    import numpy as np
    import dojo.core.solvers.llm_helpers.generic_llm as generic
    from dojo.core.solvers.operators.debug import debug_op
    from dojo.core.solvers.operators.analyze import analyze_op
    from dojo.core.solvers.operators.memory import create_memory_op
    cfg=operator(case,kind,lane,depth,remaining);seed=cfg['llm']['generation_kwargs']['seed']
    random.seed(seed);np.random.seed(seed);generic.get_logger=lambda:None
    llm=generic.GenericLLM(OmegaConf.create(cfg));solver=OmegaConf.create(copy.deepcopy(case['solver']))
    if kind=='analyze':value=analyze_op(llm,solver,case['description'],node)
    else:value=debug_op(llm,solver,create_memory_op(OmegaConf.create(case['debug_memory'])),case['description'],journal,node,len(journal.nodes),remaining,data_preview=preview)
    outer_limit=EPISODE if FULL_DEADLINE else (310 if kind=='analyze' else 1210)
    return await asyncio.wait_for(first.resolve(value),timeout=max(1,min(remaining,outer_limit)))

def apply_native(node,result,response,*,lower_is_better=True):
    from dojo.solvers.mcts.mcts import MCTS
    from dojo.core.tasks.constants import EXECUTION_OUTPUT
    solver=types.SimpleNamespace(cfg=types.SimpleNamespace(use_test_score=False),lower_is_better=lower_is_better,
        logger=logging.getLogger('episode'),_analyze=lambda _:copy.deepcopy(response))
    MCTS.parse_eval_result(solver,node,{EXECUTION_OUTPUT:result})
    return not node.is_buggy

def binding_context(env):
    ep=Path(env['FORETS_CURRENT_POOL_ROOT']);root=scope(ep.parent)
    if not re.fullmatch(r'episode-[0-3]',ep.name):raise ValueError('episode scope')
    identity=Path(env['DOJO_WORKER_IDENTITY_PATH'])
    if identity.parent!=ep or not re.fullmatch(r'identity-[0-9]+\.json',identity.name):raise ValueError('identity scope')
    if rt.read(root/'execution-claim.json')['job']!=env['SLURM_JOB_ID']:raise ValueError('allocation identity')
    return identity.with_suffix('.native-binding.json')

def execute(ep,code,index,remaining):
    from dojo.config_dataclasses.interpreter.fresh_container import FreshContainerInterpreterConfig
    from dojo.core.interpreters.fresh_container import FreshContainerInterpreter
    work=ep/f'work-{index}';work.mkdir();identity=ep/f'identity-{index}.json';rt.write(identity,{})
    os.environ['DOJO_WORKER_IDENTITY_PATH']=str(identity)
    cfg=FreshContainerInterpreterConfig(working_dir=str(work),timeout=max(1,min(7200,int(remaining))),
        container_runtime='singularity',superimage_directory=str(BASE/'aira-dojo/build/superimage'),superimage_version='2026-07-macos-v1',
        env={n:'6' for n in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')})
    cfg.validate();worker=FreshContainerInterpreter(cfg,data_dir=BASE/'mle-bench-data'/TASK/'prepared/public')
    try:
        result=worker.run(code,file_name='solution.py',include_exec_time=False)
        raw=''.join(result.term_out).encode()
        if rt.SHAPES.search(raw):raise ValueError('unsafe task output')
        (ep/f'output-{index}.private.log').write_bytes(raw)
        binding=rt.read(identity.with_suffix('.native-binding.json'))
        if binding['namespace']['exact_device_namespace'] is not True:raise ValueError('GPU isolation')
        submission=None
        if result.exit_code==0 and not result.timed_out:
            path=worker.fetch_file(work/'submission.csv')
            if path is not None:
                path=Path(path)
                if path.is_symlink() or path.resolve()!=work/'submission.csv':raise ValueError('submission scope')
                submission=rt.sha(path)
        return result,submission,rt.sha(identity.with_suffix('.native-binding.json'))
    finally:worker.close()

def episode(root,index,*,cpu_only=False):
    ep=root/f'{"cpu-episode" if cpu_only else "episode"}-{index}';start=rt.read(ep/'start.json');lane=start['lane'];p=lane_setup(root,lane)
    os.environ['FORETS_CURRENT_POOL_ROOT']=str(ep)
    case=rt.read(root/'inputs.private.json')['cases'][start['seed']-1]
    from dojo.core.solvers.utils import data_preview
    from dojo.core.solvers.utils.response import extract_code,extract_text_up_to_code
    from dojo.core.solvers.utils.journal import Node
    from dojo.core.solvers.utils.metric import WorstMetricValue
    preview=data_preview.generate(BASE/'mle-bench-data'/TASK/'prepared/public')
    if rt.SHAPES.search(preview.encode()):raise ValueError('unsafe preview')
    journal,parent,failed=new_journal(case);deadline=start['monotonic']+EPISODE
    def remaining():return deadline-time.monotonic()
    async def run():
        accepted=False;last=failed;actions=[];status='deadline';attempts=([0] if start['cache'] else [])+list(range(1,21))
        for depth in attempts:
            if remaining()<=1:break
            action=dict(depth=depth,kind='cache' if depth==0 else 'debug',started_seconds=time.monotonic()-start['monotonic'])
            action_index=len(actions);response=None;result=None
            try:
                if depth==0:code=case['cache']['code'];plan=''
                else:
                    answer,info=await call_native(case,'debug',lane,depth,remaining(),last,journal,preview)
                    rt.write(ep/f'generation-{depth}.private.json',dict(answer=answer,info=info))
                    action['generation_usage']=info.get('usage');finish=info.get('usage',{}).get('finish_reason')
                    if finish=='length':action['status']='truncated';actions.append(action);rt.write(ep/f'action-{action_index}.json',action);status='generation_incomplete';break
                    code=extract_code(answer);plan=extract_text_up_to_code(answer)
                    if not code.strip():raise ValueError('no complete code')
                if rt.SHAPES.search(code.encode()):raise ValueError('unsafe code')
                if remaining()<=1:break
                (ep/f'code-{action_index}.private.py').write_text(code)
                action['code_sha256']=hashlib.sha256(code.encode()).hexdigest()
                node=Node(code=code,plan=plan,parents=[parent if depth==0 else last],is_buggy=True,metric=WorstMetricValue(),operators_used=['draft' if depth==0 else 'debug'])
                result,submission,binding=execute(ep,code,action_index,remaining())
                node.absorb_exec_result(result)
                action.update(exit_code=result.exit_code,timed_out=result.timed_out,submission_sha256=submission,binding_sha256=binding)
                if remaining()<=1:break
                try:
                    response,info=await call_native(case,'analyze',lane,depth,remaining(),node,journal,preview)
                    rt.write(ep/f'analysis-{depth}.private.json',dict(response=response,info=info));action['analysis_status']='returned'
                except Exception as exc:
                    action.update(analysis_status='unknown',analysis_error_type=type(exc).__name__);response={}
                accepted=apply_native(node,result,response,lower_is_better=case.get('lower_is_better',True)) and bool(submission) and not result.timed_out
                journal.append(node)
                action.update(status='returned',native_accepted=accepted,completed_seconds=time.monotonic()-start['monotonic'])
                if remaining()<=0:action['native_accepted']=False;accepted=False;status='deadline'
                elif accepted:
                    rt.write(ep/'incumbent.json',dict(action_index=action_index,submission_sha256=submission,accepted_seconds=action['completed_seconds'],code_sha256=action['code_sha256']))
                    status='native_accepted'
                if depth>0:last=node
                # Failed sibling does not replace the original repair ancestry.
            except Exception as exc:
                action.update(status='infrastructure_or_generation_unknown',error_type=type(exc).__name__);status='unknown'
            actions.append(action);rt.write(ep/f'action-{action_index}.json',action)
            if accepted or status=='unknown':break
        return dict(status=status,actions=len(actions),native_accepted=accepted,elapsed_seconds=time.monotonic()-start['monotonic'])
    outcome=asyncio.run(run());rt.write(ep/'finished.json',outcome)

def health(lane_root,port):
    rt.ROOT=lane_root;opener=urllib.request.build_opener(urllib.request.ProxyHandler({}));url=f'http://127.0.0.1:{port}/v1/models'
    try:
        with opener.open(url,timeout=3):return False
    except urllib.error.HTTPError as exc:
        if exc.code!=401:return False
    req=urllib.request.Request(url,headers={'Authorization':'Bearer '+rt.local_key()})
    with opener.open(req,timeout=3) as result:value=json.loads(result.read(100000))
    return [m['id'] for m in value.get('data',[])]==['qwen3.8-27b']

def controller(root):
    p=check(root);job=os.environ['SLURM_JOB_ID']
    if socket.gethostname().split('.')[0]!='gpu28' or rt.read(root/'launch.json')['job']!=job:raise ValueError('allocation')
    rt.write(root/'execution-claim.json',dict(job=job,utc=rt.utc()));servers=[];began=time.monotonic();status='unknown'
    env={k:v for k,v in os.environ.items() if k not in ('CUDA_VISIBLE_DEVICES','SLURM_STEP_ID','SLURM_STEP_GPUS') and not re.search(r'(?i)(api.?key|primary_key|token|secret|password)',k)}
    def start(role,lane,gpus,index=None):
        limit='01:38:00' if role=='server' else '00:36:00'
        command=['srun','--exclusive','--ntasks=1','--cpus-per-task=6','--gres=gpu:'+str(gpus),'--time='+limit,str(rt.PYTHON),'-B',str(root/SCRIPT),role,'--root',str(root),'--lane',str(lane)]
        if index is not None:command+=['--index',str(index)]
        with (root/f'{role}-{lane}-{index}.private.log').open('xb') as out:return subprocess.Popen(command,stdout=out,stderr=out,env=env,start_new_session=True)
    try:
        for lane in (0,1):
            with (root/f'lane-{lane}/.service.env').open('w') as handle:handle.write('PRIMARY_KEY_QWEN3_8_27B='+secrets.token_hex(32)+'\n')
            with socket.socket() as sock:sock.bind(('127.0.0.1',8000+lane))
            servers.append(start('server',lane,2))
        ready=set()
        while time.monotonic()-began<1500 and len(ready)<2:
            if any(proc.poll() is not None for proc in servers):raise RuntimeError('owned server exited')
            for lane in (0,1):
                try:
                    if health(root/f'lane-{lane}',8000+lane):ready.add(lane)
                except (OSError,urllib.error.URLError):pass
            time.sleep(2)
        if len(ready)!=2:raise RuntimeError('service readiness deadline')
        native=[rt.read(root/f'lane-{lane}/service-native.json')['uuid'] for lane in (0,1)]
        if len(set(native[0]+native[1]))!=4:raise ValueError('service GPU overlap')
        rt.write(root/'services-ready.json',dict(utc=rt.utc(),startup_seconds=time.monotonic()-began,uuids=native))
        for wave,seed in enumerate((1,2)):
            if CAP-100-(time.monotonic()-began)<EPISODE+30:raise RuntimeError('insufficient whole episode budget')
            workers=[];wave_started=time.monotonic()
            for lane in (0,1):
                index=wave*2+lane;ep=root/f'episode-{index}';ep.mkdir()
                rt.write(ep/'start.json',dict(index=index,seed=seed,lane=lane,cache=lane==wave,monotonic=wave_started,utc=rt.utc(),budget_seconds=EPISODE))
                workers.append(start('bounded-worker',lane,1,index))
            codes=[proc.wait() for proc in workers]
            rt.write(root/f'wave-{wave}.json',dict(seed=seed,returncodes=codes,utc=rt.utc()))
            if any(code not in (0,124,137,143) for code in codes):raise RuntimeError('worker failed before protocol closure')
        status='all_four_episodes_closed'
    except Exception as exc:status='infrastructure_unknown';rt.write(root/'controller-error.json',dict(error_type=type(exc).__name__))
    finally:
        for proc in servers:rt.stop_owned(proc)
        rt.write(root/'closed.json',dict(status=status,job=job,utc=rt.utc(),elapsed_seconds=time.monotonic()-began))

def cpu(root):
    p=check(root);cases=rt.read(root/'inputs.private.json')['cases'];count=0;engine_cases=[]
    # Exercise the exact module imported by the task GPU wrapper, including
    # future task-specific binding-context configuration, without a Slurm job.
    import importlib.util
    bridge_spec=importlib.util.spec_from_file_location('cpu_exact_binding_bridge',root/'forets_current_pool_20260912.py')
    bridge=importlib.util.module_from_spec(bridge_spec);bridge_spec.loader.exec_module(bridge)
    read_original=rt.read
    def cpu_read(path):
        return {'job':'cpu-only'} if path==root/'execution-claim.json' else read_original(path)
    with patch.object(rt,'read',cpu_read):
        bound=bridge.binding_context(dict(FORETS_CURRENT_POOL_ROOT=str(root/'episode-0'),DOJO_WORKER_IDENTITY_PATH=str(root/'episode-0/identity-0.json'),SLURM_JOB_ID='cpu-only'))
    assert bound==root/'episode-0/identity-0.native-binding.json'
    for lane in (0,1):
        lane_setup(root,lane)
        import dojo.core.solvers.llm_helpers.backends.lite_llm as backend
        from dojo.core.solvers.utils.response import extract_code
        async def completion(**kwargs):
            nonlocal count
            assert kwargs['base_url']==f'http://127.0.0.1:{8000+lane}/v1'
            assert kwargs['max_retries']==kwargs['num_retries']==0
            assert ('max_tokens' not in kwargs) if FULL_DEADLINE else (kwargs['max_tokens']==32768)
            if FULL_DEADLINE:assert kwargs['request_timeout'].read in (1900,1500)
            text=json.dumps(dict(is_bug=True,summary='CPU native',metric=None)) if 'response_format' in kwargs else '```python\npass\n```'
            count+=1
            return types.SimpleNamespace(choices=[types.SimpleNamespace(message=types.SimpleNamespace(content=text),finish_reason='stop')],to_dict=lambda:{'usage':{'prompt_tokens':1,'completion_tokens':1}})
        async def test():
            with patch.object(backend,'completion_fn',completion):
                for case in cases:
                    journal,_,node=new_journal(case)
                    answer,_=await call_native(case,'debug',lane,1,1900,node,journal,'CPU_PUBLIC_PREVIEW')
                    assert extract_code(answer).strip()=='pass'
                    analysis,_=await call_native(case,'analyze',lane,1,1500,node,journal,'CPU_PUBLIC_PREVIEW')
                    assert isinstance(analysis,dict) and analysis['is_bug'] is True
        asyncio.run(test())
        # Full real episode wiring with fake network/task only; exercises parser,
        # ancestry, failed-cache fallback, two debug generations and first-success stop.
        from dojo.core.solvers.utils import data_preview
        for cached in (False,True):
            index=lane*2+int(cached);ep=root/f'cpu-episode-{index}';ep.mkdir()
            rt.write(ep/'start.json',dict(seed=lane+1,lane=lane,cache=cached,monotonic=time.monotonic()))
            executions=[];debug_depths=[]
            def fake_execute(where,code,i,remaining):
                executions.append(i);success=len(executions)==(3 if cached else 2)
                result=types.SimpleNamespace(term_out=['CPU_TASK_FAILURE' if not success else 'CPU_TASK_SUCCESS'],exit_code=0 if success else 1,exec_time=.01,timed_out=False)
                return result,'f'*64 if success else None,'e'*64
            async def full_completion(**kwargs):
                nonlocal count
                count+=1
                if 'response_format' in kwargs:
                    success=len(executions)==(3 if cached else 2)
                    answer=json.dumps(dict(is_bug=not success,summary='CPU_ANALYSIS',metric=.5 if success else None))
                else:
                    debug_depths.append(kwargs['seed']%100)
                    answer='```python\npass\n```'
                return types.SimpleNamespace(choices=[types.SimpleNamespace(message=types.SimpleNamespace(content=answer),finish_reason='stop')],to_dict=lambda:{'usage':{'prompt_tokens':1,'completion_tokens':1}})
            with patch.object(backend,'completion_fn',full_completion),patch.object(data_preview,'generate',lambda _: 'CPU_PUBLIC_PREVIEW'),patch(__name__+'.execute',fake_execute):
                episode(root,index,cpu_only=True)
            closed=rt.read(ep/'finished.json')
            assert closed['status']=='native_accepted' and debug_depths==[1,2]
            assert closed['actions']==(3 if cached else 2)
            engine_cases.append(dict(lane=lane,cache=cached,actions=closed['actions'],debug_depths=debug_depths))
    subprocess.run(['bash','-n',str(root/'run.sbatch')],check=True,timeout=10)
    rt.write(root/'cpu.json',dict(status='PASS_ACTUAL_NATIVE_OPERATORS_TWO_LANES',mock_calls=count,engine_cases=engine_cases,actual_binding_bridge_checked=True,real_calls=0,prepared_sha256=rt.sha(root/'prepared.json')))

def prepare(commit):
    if not re.fullmatch('[a-f0-9]{40}',commit):raise ValueError('commit')
    cases=inputs();root=Path(tempfile.mkdtemp(prefix=ROOT_PREFIX,dir=BASE))
    for name in FILES:shutil.copy2(Path(__file__).with_name(name),root/name)
    prior=rt.read(rt.DONOR/'prepared.json')
    for name in rt.HELPERS:
        if rt.sha(rt.DONOR/name)!=prior['files'][name]:raise ValueError('GPU helper drift')
        target=root/name;target.parent.mkdir(exist_ok=True,parents=True);shutil.copy2(rt.DONOR/name,target)
    (root/'forets_current_pool_20260912.py').write_text('from '+CONTEXT_MODULE+' import binding_context\n')
    (root/'opencl-vendors').mkdir();(root/'opencl-vendors/nvidia.icd').write_text('libnvidia-opencl.so.1\n')
    rt.write(root/'inputs.private.json',dict(cases=cases))
    for lane in (0,1):
        lane_root=root/f'lane-{lane}';(lane_root/'service-cache/tmp').mkdir(parents=True)
        entry=rt.SERVICE_ENTRY
        if entry.count("'--port','8000'")!=1:raise ValueError('service port patch')
        (lane_root/'service_entry.py').write_text(entry.replace("'--port','8000'",f"'--port','{8000+lane}'"))
        rt.write(lane_root/'prepared.json',dict(commit=commit,files={'service_entry.py':rt.sha(lane_root/'service_entry.py')}))
        with (lane_root/'.service.env').open('x') as h:h.write('PRIMARY_KEY_QWEN3_8_27B='+'0'*64+'\n')
    batch=f'''#!/bin/bash
#SBATCH --job-name=comparison-online-continuation
#SBATCH --partition=gpu_24h
#SBATCH --account=gpu
#SBATCH --qos=gpu
#SBATCH --nodelist=gpu28
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:6
#SBATCH --cpus-per-task=24
#SBATCH --time=01:40:00
#SBATCH --no-requeue
set -euo pipefail
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1
timeout --signal=TERM --kill-after=20s 5940s {rt.PYTHON} -B {root}/{SCRIPT} controller --root {root}
'''
    (root/'run.sbatch').write_text(batch)
    files={str(f.relative_to(root)):rt.sha(f) for f in root.rglob('*') if f.is_file() and f.name!='.service.env'}
    rt.write(root/'prepared.json',dict(commit=commit,utc=rt.utc(),files=files,task=TASK,episode_seconds=EPISODE,allocation_seconds=CAP,gpu_hours_cap=10,
        model='cyankiwi/Qwen3.8-27B-AWQ-BF16-INT4',revision='dc430725f831dd90d9271738b877879a46a82239'))
    cpu(root);print(json.dumps(dict(status='PREPARED_NOT_SUBMITTED',root=str(root),prepared_sha256=rt.sha(root/'prepared.json'))),flush=True)

def submit(root):
    p=check(root)
    if rt.read(root/'cpu.json')['prepared_sha256']!=rt.sha(root/'prepared.json'):raise ValueError('preflight drift')
    rt.asset_check(p)
    image=BASE/'aira-dojo/build/superimage/superimage.root.2026-07-macos-v1.sif';stat=image.stat()
    if (stat.st_size,stat.st_mtime_ns)!=(19717783552,1784638286000000000):raise ValueError('task image drift')
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    queue=subprocess.check_output(['squeue','-u','yzyang4','-h','-o','%i'],env=env,text=True,timeout=20).split()
    if set(queue)-{'12535'}:raise ValueError('unexpected other job')
    with (root/'capacity.tmp').open('xb') as handle:os.posix_fallocate(handle.fileno(),0,4*1024**3)
    (root/'capacity.tmp').unlink()
    rt.write(root/'submit-intent.json',dict(utc=rt.utc(),prepared_sha256=rt.sha(root/'prepared.json'),gpu_hours_cap=10))
    proc=subprocess.run(['sbatch','--parsable','--chdir='+str(root),'--output='+str(root/'allocation-%j.out'),'--error='+str(root/'allocation-%j.err'),str(root/'run.sbatch')],env=env,capture_output=True,text=True,timeout=25)
    job=proc.stdout.strip().split(';')[0]
    if proc.returncode or not job.isdigit():raise RuntimeError('ambiguous submit; no retry')
    rt.write(root/'launch.json',dict(job=job,utc=rt.utc(),commit=p['commit']));print(json.dumps(dict(status='SUBMITTED',job=job,root=str(root),gpu_hours_cap=10)))

if __name__=='__main__':
    os.umask(0o077);parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['prepare','cpu','submit','controller','server','bounded-worker','episode']);parser.add_argument('--root',type=Path);parser.add_argument('--commit');parser.add_argument('--lane',type=int);parser.add_argument('--index',type=int);a=parser.parse_args()
    if a.mode=='prepare':prepare(a.commit)
    elif a.mode=='server':
        check(a.root);rt.ROOT=a.root/f'lane-{a.lane}';rt.server()
    elif a.mode=='bounded-worker':
        start=rt.read(a.root/f'episode-{a.index}/start.json');left=max(1,start['monotonic']+EPISODE-time.monotonic())
        command=['timeout','--signal=TERM','--kill-after=10s',str(left)+'s',str(rt.PYTHON),'-B',str(a.root/SCRIPT),'episode','--root',str(a.root),'--index',str(a.index)]
        raise SystemExit(subprocess.call(command))
    elif a.mode=='episode':episode(a.root,a.index)
    else:globals()[a.mode](a.root)
