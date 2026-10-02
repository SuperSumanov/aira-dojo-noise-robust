"""Small prospective development qualification, reusing the pinned AIRA runtime.

Only intervention: required decision-discriminating check before the next repair.
Ordinary improvement has the identical CHECK/SOLUTION interface and resource caps.
All starts selected on old development data; this is NOT a fresh test-set result.
"""
import argparse, ast, asyncio, copy, hashlib, importlib.util, inspect, json, logging
import os, random, re, secrets, shutil, subprocess, sys, time
from pathlib import Path

B = Path('/research/d7/spc/yzyang4')
OLD = B/'task-feedback-real-20261001-v6'
ROOT = B/'decision-diagnosis-20261002-v1'
BASE_SHA = '4b155d927c12f063e0838b5708085fe1bc55c4983197a3d8d2453696d73c55ad'
base = ROOT/'v6_runtime.py' if (ROOT/'v6_runtime.py').exists() else OLD/'task_feedback_real_20261001.py'
if hashlib.sha256(base.read_bytes()).hexdigest() != BASE_SHA:
    raise ValueError('pinned runtime drift')
spec = importlib.util.spec_from_file_location('diagnosis_v6', base)
m = importlib.util.module_from_spec(spec); sys.modules[spec.name] = m; spec.loader.exec_module(m)
m.ROOT=ROOT; m.PORT=19445; m.SECONDS=900; m.CAP=6000
m.COMMIT='ee0da919c11b4c4f1bc029aa1c3aa145b5758794'
m.infra.ROOT=ROOT; m.infra.SERVICE_PORT=m.PORT
TASKS=('random-acts-of-pizza','spooky-author-identification')
BATCHES=('task-feedback-real-20261001-v6','task-feedback-upper-20261002-v1',
         'task-feedback-local-edit-20261002-v1','task-feedback-evidence-edit-20261002-v1')

COMMON='''Improve a working machine-learning task program, not an evaluator.
Both modes below have the SAME public data, environment, tools and total budget.
You have at most two calls. Each response executes in a fresh isolated workspace.
First line must be CHECK or SOLUTION, followed by a short rationale and exactly
one fenced python block. No JSON or patch blocks. CHECK is a standalone program
which inspects public data/program behaviour and prints concise measured evidence;
it is not graded and has a 120-second execution cap. SOLUTION is the complete
runnable task program producing submission.csv, with a 300-second execution cap.
The current incumbent program is also available as /workspace/parent.py.
No persistent files transfer between actions. Actual output from a check WILL be
returned before your next call. Do not fabricate its output or run hidden data.
There are no hidden labels in this workspace. Do not download models/dependencies.
Use only /workspace/data and your own workspace. Six CPU cores and one RTX3090.
Keep useful components, use a focused change, and allow uncertainty/no justified
change. Explain the intended modification and an observation against it.
Cheap reference methods already tried include train-only word/character TFIDF
linear classification, numeric HistGradientBoosting, and Naive Bayes. They are
available ideas for BOTH modes, not new discoveries. Batch-relative date origins
are a known issue: transformations must share training-fitted state; fixing this
alone will not count as discovery of a new rule. Do not assume it is the cause.
The starting program is a strong historical development incumbent; improvement
is not guaranteed. External development scores are exploratory, not final test.
'''
ACTIVE='''For this FIRST call choose CHECK. State two plausible explanations that
would lead to different modifications, what each predicts, your provisional
modification before checking, and an explicit observation-dependent decision rule.
Then write a short executable check that could discriminate them. Both or neither
may hold; allow unknown. Do not write the repair before observing the check.
'''
ORDINARY='''For this FIRST call choose CHECK or SOLUTION, whichever you judge most
useful for improving the incumbent within the budget. You may diagnose, inspect,
test or directly improve it. Do not feel obliged to add unnecessary analysis.
'''
FINAL='''This is the final call. Choose SOLUTION. Use the actual preceding output
when useful, but do not treat a failed/inconclusive check as evidence. Briefly
state what observation changed (or did not change) your modification choice.
Produce the complete runnable program. Keeping the incumbent is allowed.
'''

def schedule():
    order=list('AB'); random.Random(2026100208).shuffle(order); rows=[]
    for seed_block in range(2):
        for j,arm in enumerate(order if seed_block==0 else order[::-1]):
            for t,task in enumerate(TASKS):
                rows.append(dict(index=len(rows),start=t,task=task,arm=arm,
                    seed=102801+2*seed_block+t,wave=2*seed_block+j))
    return rows
m.schedule=schedule

def decode(raw,arm,step):
    if m.SECRET.search(raw.encode()): raise ValueError('credential-shaped output')
    lines=raw.strip().splitlines(); mode=lines[0].strip() if lines else ''
    if mode not in ('CHECK','SOLUTION'): raise ValueError('missing action mode')
    if step==1 and arm=='B' and mode!='CHECK': raise ValueError('required check absent')
    if step==2 and mode!='SOLUTION': raise ValueError('final action not solution')
    blocks=re.findall(r'```python\s*\n(.*?)```',raw,re.S)
    if len(blocks)!=1 or raw.count('```')!=2: raise ValueError('one python block required')
    ast.parse(blocks[0]); return mode,blocks[0],raw.split('```',1)[0]

def prompt(task,arm,step,current,history,remaining):
    directive=(ACTIVE if arm=='B' else ORDINARY) if step==1 else FINAL
    return COMMON+directive+'\nTASK:\n'+task+'\nCURRENT INCUMBENT:\n'+current+'\nACTUAL HISTORY:\n'+history+f'\nTOTAL SECONDS REMAINING: {int(remaining)}\n'

def episode(s,ep,deadline):
    from dojo.config_dataclasses.run import RunConfig
    from dojo.config_dataclasses.interpreter import INTERPRETER_MAP
    from dojo.tasks.mlebench.task import MLEBenchTask
    from dojo.utils.config import build
    from dojo.utils.logger import config_logger
    from dojo.core.tasks.constants import EXECUTION_OUTPUT,VALID_SOLUTION,VALIDATION_FITNESS,AUX_EVAL_INFO
    from dojo.core.solvers.llm_helpers.generic_llm import GenericLLM
    from omegaconf import OmegaConf
    cfg=RunConfig.load_from_json(ROOT/'configs'/f'{s["index"]}.json')
    Path(cfg.logger.output_dir).mkdir(); config_logger(cfg)
    for name in ('openai','httpx','httpcore','LiteLLM','Backend'):
        logging.getLogger(name).setLevel(logging.ERROR)
    initial=m.read(ROOT/'starts'/f'{s["start"]}.private.json')
    current=initial['code']; best=None; best_step=None; history=''; generations=0
    lower=s['task']==TASKS[1]
    for step in range(3):
        deadline.check(); action=ep/f'action-{step}'; action.mkdir()
        task=MLEBenchTask(cfg.task); mode='SOLUTION'; code=current; plan='initial reexecution'
        if step:
            opc=copy.deepcopy(cfg.solver.operators['improve']); kw=opc.llm.generation_kwargs
            kw.update(seed=s['seed']*10+step,max_tokens=4096,
                      bounded_request_timeout_seconds=max(1,min(240,int(deadline.remaining()))))
            message=prompt(task.task_description,s['arm'],step,current,history,deadline.remaining())
            m.write(action/'request.private.json',dict(prompt=message,seed=kw['seed'],step=step))
            llm=GenericLLM(OmegaConf.structured(opc)); began=time.monotonic(); generations+=1
            try:
                response,info=asyncio.run(asyncio.wait_for(llm(messages=[{'role':'user','content':message}]),
                    timeout=max(1,min(250,deadline.remaining()))))
            except (TimeoutError,asyncio.TimeoutError):
                m.write(action/'generation_failed.json',dict(status='timeout',elapsed_seconds=deadline.elapsed()))
                history+='\nPrevious call timed out; no evidence obtained.'; continue
            raw=str(response)
            if m.SECRET.search(raw.encode()): raise ValueError('credential-shaped output')
            m.write(action/'generation.private.json',dict(response=raw,usage=info.get('usage',{}),
                generation_seconds=time.monotonic()-began))
            try: mode,code,plan=decode(raw,s['arm'],step)
            except (ValueError,SyntaxError) as exc:
                m.write(action/'format.json',dict(status='REJECT',error_type=type(exc).__name__))
                history+='\nPrevious output had invalid action format; no execution or evidence obtained.'; continue
            m.write(action/'format.json',dict(status='PASS',mode=mode))
        cap=120 if mode=='CHECK' else 300
        icfg=copy.deepcopy(cfg.interpreter); icfg.working_dir=str(action/'work')
        icfg.timeout=max(1,min(cap,int(deadline.remaining()))); Path(icfg.working_dir).mkdir()
        (Path(icfg.working_dir)/'parent.py').write_text(current)
        os.environ['FEEDBACK_ACTION_ROOT']=str(action)
        interpreter=build(icfg,INTERPRETER_MAP,data_dir=cfg.task.data_dir)
        state,_=task.prepare(solver_interpreter=interpreter,eval_interpreter=None)
        original=task._search_only_score
        def capture(name,path):
            result=original(name,path); shutil.copyfile(path,action/'submission.private.csv'); return result
        task._search_only_score=capture
        code_sha=hashlib.sha256(code.encode()).hexdigest()
        m.write(action/'started.json',dict(step=step,kind=mode,utc=m.utc(),elapsed=deadline.elapsed(),code_sha256=code_sha))
        executable=(f'import random as _r\nimport numpy as _n\n_r.seed({s["seed"]})\n_n.random.seed({s["seed"]})\n'
                    +f'exec(compile({code!r},"solution.py","exec"))\n')
        try:
            if mode=='CHECK':
                out=interpreter.run(executable,file_name='diagnostic.py'); result={}; valid=False; value=None
            else:
                _,result=task.step_task(state,executable); out=result[EXECUTION_OUTPUT]
                valid=bool(result[VALID_SOLUTION]); value=result.get(VALIDATION_FITNESS)
            deadline.check()
        finally:
            interpreter.close()
            if hasattr(interpreter,'cleanup_session'): interpreter.cleanup_session()
        successful_check=mode=='CHECK' and out.exit_code==0 and not out.timed_out
        terminal='\n'.join(out.term_out or [])
        if m.SECRET.search(terminal.encode()): raise ValueError('credential-shaped terminal')
        improved=valid and (best is None or ((value<best) if lower else (value>best)))
        if improved: best=value; best_step=step; current=code
        m.write(action/'node.private.json',dict(code=code,plan=plan,terminal=terminal))
        m.write(action/'result.json',dict(step=step,kind=mode,valid=valid,metric=value,
            successful_check=successful_check,execution_started=True,exit_code=out.exit_code,
            timed_out=out.timed_out,exec_seconds=out.exec_time,elapsed_seconds=deadline.elapsed(),
            code_sha256=code_sha,selected_metric=best,selected_step=best_step))
        history+=f'\nACTION {step} {mode}\nDECLARED BEFORE EXECUTION:\n{plan}\nACTUAL OUTPUT (last 12000 chars):\n{terminal[-12000:]}\n'
        history+=f'Exit={out.exit_code}; timed_out={out.timed_out}; valid_submission={valid}; external_development_score={value}; incumbent={best}\n'
        if improved: m.write(action/'selected.json',dict(step=step,metric=best,elapsed=deadline.elapsed()))
    m.write(ep/'completed.json',dict(selected_metric=best,selected_step=best_step,valid=best is not None,
        elapsed_seconds=deadline.elapsed(),generations=generations))
m.episode=episode

def adapt(name,pairs):
    source=inspect.getsource(getattr(m,name))
    for old,new in pairs:
        if source.count(old)!=1: raise ValueError('adaptation mismatch '+name)
        source=source.replace(old,new)
    exec(compile(source,'diagnosis_'+name,'exec'),m.__dict__)
adapt('worker',[("TIME_LIMIT='30 minutes'","TIME_LIMIT='15 minutes'"),("STEP_LIMIT='5'","STEP_LIMIT='3'")])
adapt('controller',[('03:39:00','01:39:00'),('00:33:00','00:18:00'),
                    ('for wave in range(6):','for wave in range(4):'),
                    ('max_workers=3','max_workers=2'),('dict(attempts=18,','dict(attempts=8,')])

def select_starts():
    selected=[]
    for task in TASKS:
        eligible=[]
        for batch in BATCHES:
            root=B/batch; p=m.read(root/'plan.json')
            for s in p['schedule']:
                if s['task']!=task: continue
                for path in sorted((root/f'episode-{s["index"]}').glob('action-*/result.json')):
                    r=m.read(path)
                    if r.get('valid') and isinstance(r.get('metric'),(int,float)) and (path.parent/'node.private.json').is_file():
                        eligible.append((r['metric'],str(path),root,s,path))
        if not eligible: raise ValueError('no valid start')
        chosen=sorted(eligible,key=lambda x:((x[0] if task==TASKS[1] else -x[0]),x[1]))[0]
        metric,_,root,s,path=chosen; node=path.parent/'node.private.json'
        selected.append(dict(task=task,metric=metric,node=str(node),node_sha256=m.sha(node),
            result=str(path),result_sha256=m.sha(path),config=str(root/f'configs/{s["index"]}.json'),
            selection='historical development best among all valid candidates in four frozen batches; exploratory'))
    return selected

def prepare():
    if ROOT.exists(): raise FileExistsError('one-shot root exists')
    p=m.read(OLD/'plan.json')
    if m.sha(OLD/'plan.json')!='15751d3b52bdc42617df02006ce724635f4bf49df6e477686769fd1979d53403': raise ValueError('source drift')
    starts=select_starts(); ROOT.mkdir(mode=0o700)
    for rel,h in p['files'].items():
        if not (rel.startswith(('source/','forets_','opencl-vendors/')) or rel=='root_trial_step_supervisor_20260927.py'): continue
        src=OLD/rel
        if m.sha(src)!=h: raise ValueError('support drift '+rel)
        dest=ROOT/rel; dest.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(src,dest)
    shutil.copyfile(base,ROOT/'v6_runtime.py'); shutil.copyfile(__file__,ROOT/'task_feedback_real_20261001.py')
    for rel in ('starts','configs','bin','service-cache/tmp'): (ROOT/rel).mkdir(parents=True,exist_ok=True)
    (ROOT/'bin/singularity').write_text(f'#!{m.PY}\nimport sys\nsys.path.insert(0,{str(ROOT)!r})\nfrom task_feedback_real_20261001 import m\nm.task_runtime()\n')
    os.chmod(ROOT/'bin/singularity',0o700)
    entry=(OLD/'service_entry.py').read_text(); assert entry.count("'19441'")==1
    (ROOT/'service_entry.py').write_text(entry.replace("'19441'","'19445'"))
    with (ROOT/'.service.env').open('x') as f: f.write('PRIMARY_KEY_QWEN3_8_27B='+secrets.token_hex(32)+'\n')
    os.chmod(ROOT/'.service.env',0o600); m.setup()
    from dojo.utils.code_parsing import extract_code
    for i,info in enumerate(starts):
        node=m.read(Path(info['node'])); code=extract_code(node['code']); ast.parse(code)
        if m.SECRET.search(code.encode()): raise ValueError('source credential shape')
        m.write(ROOT/'starts'/f'{i}.private.json',dict(code=code,plan=node['plan']))
        info['code_sha256']=hashlib.sha256(code.encode()).hexdigest()
    for s in schedule():
        cfg=m.read(Path(starts[s['start']]['config'])); ep=ROOT/f'episode-{s["index"]}'; ep.mkdir()
        cfg['id']=f'decision-diagnosis-{s["index"]}'
        cfg['logger'].update(output_dir=str(ep/'native-log'),write_env_vars=False,use_wandb=False,print_config=False,use_console=False)
        cfg['metadata'].update(seed=s['seed'],script_id='decision-diagnosis-20261002',git_commit_id=m.COMMIT,base_path=str(ROOT/'source'))
        cfg['solver'].update(time_limit_secs=m.SECONDS,step_limit=3,checkpoint_path=str(ep/'unused-checkpoint'))
        cfg['interpreter']['working_dir']=str(ep/'unused-work'); cfg['interpreter']['env']['PYTHONHASHSEED']=str(s['seed'])
        cfg['task']['cache_dir']=str(ROOT/'no-official-data')
        for op in cfg['solver']['operators'].values():
            op['llm']['client']['base_url']=f'http://127.0.0.1:{m.PORT}/v1'
            op['llm']['generation_kwargs'].update(max_tokens=4096,seed=s['seed'],bounded_request_timeout_seconds=240)
        m.write(ROOT/'configs'/f'{s["index"]}.json',cfg)
    batch=(OLD/'run.sbatch').read_text().replace(str(OLD),str(ROOT)).replace('task-feedback-ABC','decision-diagnosis')
    batch=batch.replace('--gres=gpu:5','--gres=gpu:4').replace('--cpus-per-task=30','--cpus-per-task=24')
    batch=batch.replace('03:40:00','01:40:00').replace('13140s','5940s')
    (ROOT/'run.sbatch').write_text(batch)
    files={str(f.relative_to(ROOT)):m.sha(f) for f in ROOT.rglob('*') if f.is_file() and f.name!='.service.env'}
    m.write(ROOT/'plan.json',dict(protocol='decision-diagnosis-qualification-v1',base_commit=m.COMMIT,utc=m.utc(),
        schedule=schedule(),starts=starts,files=files,run_seconds=900,allocation_seconds=6000,
        gpus=4,gpu_hours_cap=4*6000/3600,max_calls=2,max_tokens_per_call=4096,
        check_seconds_cap=120,solution_seconds_cap=300,paid_api=0,agent_training=False,
        primary='paired final incumbent difference after full common budget; all attempts count',
        continue_gate='both tasks have positive median paired gain AND real check-to-new-repair evidence; otherwise narrow or stop',
        metric_directions={'random-acts-of-pizza':'higher','spooky-author-identification':'lower'},
        renewal='confirmed',protected_opened=False,final_evaluation=False,
        limits='2 seeds/task, historical selected starts and reused development labels; not significance/novelty/generalization proof'))
    print(json.dumps(dict(status='PREPARED',plan_sha256=m.sha(ROOT/'plan.json'),runs=8,gpu_hours_cap=4*6000/3600)))

def submit():
    p=m.check()
    for name in ('cpu.json','transport-cpu.json'):
        r=m.read(ROOT/name)
        if r['status']!='PASS' or r['plan_sha256']!=m.sha(ROOT/'plan.json'): raise ValueError('stale preflight')
    if (ROOT/'submit-intent.json').exists(): raise ValueError('existing submission intent; resolve before retry')
    if m.sha(m.infra.TASK_IMAGE)!=m.infra.IMAGE_SHA or m.sha(m.ASSETS/'vllm.sif')!=m.infra.VLLM_SHA: raise ValueError('image drift')
    for r in m.read(m.ASSETS/'complete.json')['files']:
        if r['path'].endswith('.safetensors') and m.sha(m.ASSETS/r['path'])!=r['digest']: raise ValueError('weights drift')
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    jobs=subprocess.check_output(['squeue','-u','yzyang4','-h','-o','%i'],env=env,text=True,timeout=20).split()
    if set(jobs)-{'12535'}: raise ValueError('unexpected allocation')
    with (ROOT/'capacity.tmp').open('xb') as f: os.posix_fallocate(f.fileno(),0,512*1024**2)
    (ROOT/'capacity.tmp').unlink()
    m.write(ROOT/'submit-intent.json',dict(utc=m.utc(),plan_sha256=m.sha(ROOT/'plan.json')))
    r=subprocess.run(['sbatch','--parsable','--chdir='+str(ROOT),'--output='+str(ROOT/'allocation-%j.out'),
        '--error='+str(ROOT/'allocation-%j.err'),str(ROOT/'run.sbatch')],env=env,text=True,capture_output=True,timeout=25)
    job=r.stdout.strip().split(';')[0]
    if r.returncode or not job.isdigit(): raise RuntimeError('ambiguous submit; do not retry')
    m.write(ROOT/'launch.json',dict(job=job,utc=m.utc(),plan_sha256=m.sha(ROOT/'plan.json')))
    print(json.dumps(dict(status='SUBMITTED',job=job,gpu_hours_cap=p['gpu_hours_cap'])))

def refresh_before_launch():
    # Pre-result repair of an observed legacy race, not a relaxed clock tolerance.
    # A receipt can appear AFTER the loop's timestamp and before the read.
    # Take the upper bound AFTER reading. Never alter the old experiment files.
    if (ROOT/'launch.json').exists() or (ROOT/'submit-intent.json').exists():
        raise ValueError('cannot revise a submitted experiment')
    p=m.read(ROOT/'plan.json'); prior=m.sha(ROOT/'plan.json')
    if prior!='6947e5d805ae5ae70db762bcfed1a64988cdfe66de2573514876617db17fe14a':
        raise ValueError('unexpected prelaunch plan')
    supervisor=ROOT/'root_trial_step_supervisor_20260927.py'
    for rel,h in p['files'].items():
        if rel not in ('root_trial_step_supervisor_20260927.py','task_feedback_real_20261001.py') and m.sha(ROOT/rel)!=h:
            raise ValueError('unrelated prelaunch drift')
    raw=supervisor.read_text()
    old='spawned=began, now=now)'
    if raw.count(old)==1:
        supervisor.write_text(raw.replace(old,'spawned=began, now=time.monotonic())'))
    elif raw.count('spawned=began, now=time.monotonic())')!=1:
        raise ValueError('supervisor patch mismatch')
    shutil.copyfile(__file__,ROOT/'task_feedback_real_20261001.py')
    archive=ROOT/'prelaunch-plan-v0.json'
    if archive.exists():
        if m.read(archive)!=p: raise ValueError('prelaunch archive mismatch')
    else: m.write(archive,p)
    p['prelaunch_revision']=dict(previous_plan_sha256=prior,reason='sample clock after reading receipt to avoid publication race',
        before_any_generation_or_allocation=True,utc=m.utc())
    for rel in ('root_trial_step_supervisor_20260927.py','task_feedback_real_20261001.py'):
        p['files'][rel]=m.sha(ROOT/rel)
    m.write(ROOT/'plan-v1.ready.json',p)
    os.replace(ROOT/'plan-v1.ready.json',ROOT/'plan.json')
    print(json.dumps(dict(status='PREFLIGHT_REVISED',plan_sha256=m.sha(ROOT/'plan.json'))))

if __name__=='__main__':
    os.umask(0o077); parser=argparse.ArgumentParser()
    parser.add_argument('mode',choices=['prepare','submit','refresh_before_launch','check','worker','controller','service']); parser.add_argument('--index',type=int)
    args=parser.parse_args()
    if args.mode in ('prepare','submit','refresh_before_launch'): globals()[args.mode]()
    elif args.mode=='worker': m.worker(args.index)
    elif args.mode=='check': m.check(); print('FROZEN_PLAN_VALID')
    else: getattr(m,args.mode)()
