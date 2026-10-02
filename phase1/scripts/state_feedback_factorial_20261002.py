"""Bounded exploratory state x public-output factorial, not a new method claim.

The ordinary persistent coding agent (D) is the strong reference. A/B mask initial
stdout only, not future tool returns or the external development score. Cold arms reconstruct the successful
cell ledger before the next action; they have the same variables and tools but
pay that reconstruction cost. No agent-base training or final evaluation.
"""
import argparse, ast, asyncio, copy, hashlib, importlib.util, inspect, json
import logging, os, random, re, secrets, shutil, subprocess, sys, time
from pathlib import Path

B=Path('/research/d7/spc/yzyang4');OLD=B/'decision-diagnosis-20261002-v1'
ROOT=B/'state-feedback-factorial-20261002-v1'
spec=importlib.util.spec_from_file_location('state_factorial_base',ROOT/'v6_runtime.py' if (ROOT/'v6_runtime.py').exists() else OLD/'v6_runtime.py')
if hashlib.sha256(Path(spec.origin).read_bytes()).hexdigest()!='4b155d927c12f063e0838b5708085fe1bc55c4983197a3d8d2453696d73c55ad': raise ValueError('runtime drift')
m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
m.ROOT=ROOT;m.PORT=19447;m.SECONDS=720;m.CAP=8100
m.COMMIT='f0d18a56ea8ebd2dbb2836d4037602e022fca7a8';m.infra.ROOT=ROOT;m.infra.SERVICE_PORT=m.PORT
TASKS=('random-acts-of-pizza','spooky-author-identification')
ARMS={'A':(False,False),'B':(True,False),'C':(False,True),'D':(True,True)}

def schedule():
    order=list('ABCD');random.Random(2026100215).shuffle(order);rows=[]
    for block in range(2):
        for a,arm in enumerate(order if block==0 else order[::-1]):
            for task,name in enumerate(TASKS):
                rows.append(dict(index=len(rows),start=task,task=name,arm=arm,
                    seed=103201+2*block+task,wave=4*block+a,
                    retained=ARMS[arm][0],visible=ARMS[arm][1]))
    return rows
m.schedule=schedule

COMMON='''You are improving a working ML task program in an ordinary coding workspace.
You have at most FOUR model calls within a shared 720 second total budget, including
initial execution, generation, tool use, state reconstruction and external grading.
Respond with CHECK or SOLUTION on the first line, brief reasoning, then exactly one
fenced python block. Python executes as a notebook cell with the successful prior
cells available. A cell may reuse any public-data model, feature array or OOF prediction
already computed. It may instead run a complete new program. No mandatory diagnosis.
CHECK prints evidence but is not graded. SOLUTION must WRITE a NEW submission.csv;
the old submission is deleted before each cell. The external development score is
returned after each valid SOLUTION. It is exploratory, not final test performance.
All successful cells are kept even if they do not improve the incumbent. The best
valid submission is retained separately by the evaluator. A failed/timed-out cell
is rolled back: the next action reconstructs the last successful ledger. Do not
assume variables created only by a failed cell remain available.
Same public data, six CPU cores and one RTX3090 for every condition. Use /workspace/data
and your workspace only; hidden labels are unavailable. No downloads or dependencies.
The original code is /workspace/parent.py. The code ledger below is the actual history.
Known ordinary references include word/character TFIDF linear models, numeric boosting,
Naive Bayes, blending, and using train-fitted transformations consistently. They are
not new discoveries. The starting program is already a strong historical development
incumbent. Improvement is not guaranteed. Choose focused justified work; do not invent
observations. Budget per code call is at most 300 seconds, additionally limited by the
total remaining time. Last model call must be SOLUTION; keeping the incumbent is allowed.
'''

def prompt(task,s,step,ledger,history,remaining):
    state=('Previously computed variables remain live without replay.' if s['retained'] else
           'Before each new cell, all successful prior cells are replayed in a fresh workspace. This costs real budget; do not assume free cached computation.')
    output=('Actual initial and future tool stdout is returned.' if s['visible'] else
            'Only the initial program stdout was withheld. Future tool stdout WILL return normally; you may inspect/recompute any allowed public evidence at its actual cost. Do not invent the missing initial observations.')
    final='This is the final model call: choose SOLUTION.' if step==4 else 'Choose the next useful CHECK or SOLUTION freely.'
    return COMMON+'\n'+state+'\n'+output+'\n'+final+'\nTASK:\n'+task+'\nSUCCESSFUL CODE LEDGER:\n'+'\n\n'.join(f'CELL {i}:\n{c}' for i,c in enumerate(ledger))+'\nOBSERVED HISTORY:\n'+history+f'\nTOTAL SECONDS REMAINING: {int(remaining)}\n'

def decode(raw,step):
    if m.SECRET.search(raw.encode()): raise ValueError('credential-shaped output')
    lines=raw.strip().splitlines();mode=lines[0].strip() if lines else ''
    if mode not in ('CHECK','SOLUTION') or (step==4 and mode!='SOLUTION'): raise ValueError('action mode')
    parts=re.findall(r'```python\s*\n(.*?)```',raw,re.S)
    if len(parts)!=1 or raw.count('```')!=2: raise ValueError('one Python block')
    ast.parse(parts[0]);return mode,parts[0],raw.split('```',1)[0]

def wrapper(code,seed,remove_submission=True):
    # Explicitly set the same RNG state on cold replay and on live first execution.
    return (f'import random as _state_r, numpy as _state_n\n_state_r.seed({seed})\n_state_n.random.seed({seed})\n'
        +("from pathlib import Path as _state_Path\n_state_Path('submission.csv').unlink(missing_ok=True)\n" if remove_submission else '')
        +f'exec(compile({code!r},"cell.py","exec"))\n')

def execute(interp,code,timeout):
    # Factory cfg governs first instantiation; executor timeout governs later cells.
    interp.cfg.timeout=timeout;interp.timeout=timeout
    if interp._instance is not None:
        interp._instance.timeout=timeout
        if interp._instance.code_executor is not None: interp._instance.code_executor._timeout=timeout
    return interp.run(code,reset_session=False,file_name='cell.py')

def episode(s,ep,deadline):
    from dojo.config_dataclasses.run import RunConfig
    from dojo.config_dataclasses.interpreter import INTERPRETER_MAP
    from dojo.tasks.mlebench.task import MLEBenchTask
    from dojo.utils.config import build
    from dojo.utils.logger import config_logger
    from dojo.core.solvers.llm_helpers.generic_llm import GenericLLM
    from omegaconf import OmegaConf
    cfg=RunConfig.load_from_json(ROOT/'configs'/f'{s["index"]}.json')
    Path(cfg.logger.output_dir).mkdir();config_logger(cfg)
    for name in ('openai','httpx','httpcore','LiteLLM','Backend'):logging.getLogger(name).setLevel(logging.ERROR)
    task=MLEBenchTask(cfg.task)
    if task._search_only_score is None or task.private_dir.exists():raise ValueError('development-only scoring required')
    parent=m.read(ROOT/'starts'/f'{s["start"]}.private.json')['code']
    ledger=[];history='';best=None;best_step=None;interp=None;generations=0;workspace=None
    def new_interpreter(action):
        nonlocal workspace
        icfg=copy.deepcopy(cfg.interpreter);icfg.working_dir=str(action/'work');icfg.timeout=300
        workspace=Path(icfg.working_dir);workspace.mkdir();(workspace/'parent.py').write_text(parent)
        os.environ['FEEDBACK_ACTION_ROOT']=str(action)
        return build(icfg,INTERPRETER_MAP,data_dir=cfg.task.data_dir)
    try:
        for step in range(5):
            deadline.check();action=ep/f'action-{step}';action.mkdir();mode='SOLUTION';code=parent;reason='initial execution'
            if step:
                opc=copy.deepcopy(cfg.solver.operators['improve']);kw=opc.llm.generation_kwargs
                kw.update(seed=s['seed']*10+step,max_tokens=4096,bounded_request_timeout_seconds=max(1,min(180,int(deadline.remaining()))))
                message=prompt(task.task_description,s,step,ledger,history,deadline.remaining())
                m.write(action/'request.private.json',dict(prompt=message,seed=kw['seed'],step=step))
                llm=GenericLLM(OmegaConf.structured(opc));began=time.monotonic();generations+=1
                try:
                    response,info=asyncio.run(asyncio.wait_for(llm(messages=[{'role':'user','content':message}]),timeout=max(1,min(190,deadline.remaining()))))
                except (TimeoutError,asyncio.TimeoutError):
                    m.write(action/'generation_failed.json',dict(status='timeout',elapsed_seconds=deadline.elapsed()))
                    history+='\nGeneration timed out: no cell was run.';continue
                raw=str(response)
                if m.SECRET.search(raw.encode()):raise ValueError('credential output')
                m.write(action/'generation.private.json',dict(response=raw,usage=info.get('usage',{}),generation_seconds=time.monotonic()-began))
                try:mode,code,reason=decode(raw,step)
                except (ValueError,SyntaxError) as exc:
                    m.write(action/'format.json',dict(status='REJECT',error_type=type(exc).__name__))
                    history+='\nInvalid response format: no cell was run.';continue
                m.write(action/'format.json',dict(status='PASS',mode=mode))
            if interp is not None and not s['retained']:interp.close();interp=None
            replay_seconds=0;replay_ok=True
            if interp is None:
                interp=new_interpreter(action)
                if ledger:
                    began=time.monotonic()
                    replay='\n'.join(wrapper(c,s['seed']) for c in ledger)
                    ro=execute(interp,replay,max(1,min(300,int(deadline.remaining()))))
                    replay_seconds=time.monotonic()-began;replay_ok=ro.exit_code==0 and not ro.timed_out
                    m.write(action/'replay.json',dict(success=replay_ok,seconds=replay_seconds,cells=len(ledger),timed_out=ro.timed_out))
            if not replay_ok:
                history+='\nState reconstruction failed/timed out; no new cell ran.'
                interp.close();interp=None;continue
            code_sha=hashlib.sha256(code.encode()).hexdigest()
            m.write(action/'started.json',dict(step=step,kind=mode,elapsed=deadline.elapsed(),code_sha256=code_sha,retained=s['retained'],visible=s['visible'],replay_seconds=replay_seconds))
            began=time.monotonic();out=execute(interp,wrapper(code,s['seed']),max(1,min(300,int(deadline.remaining()))))
            wall=time.monotonic()-began;deadline.check()
            ok=out.exit_code==0 and not out.timed_out;terminal='\n'.join(out.term_out or [])
            if m.SECRET.search(terminal.encode()):raise ValueError('credential terminal')
            value=None;valid=False;receipt=None
            if ok:
                ledger.append(code)
                if mode=='SOLUTION':
                    path=workspace/'submission.csv'
                    interp.fetch_file(path)
                    if path.is_symlink():raise ValueError('symlink submission')
                    if path.is_file():
                        try:receipt=task._search_only_score(s['task'],path)
                        except task._search_only_invalid:receipt=None
                        if receipt is not None:
                            value=receipt[task._search_only_metric_name];valid=True
                            shutil.copyfile(path,action/'submission.private.csv')
                            m.write(action/'score-receipt.private.json',receipt)
                    path.unlink(missing_ok=True)
            else:
                interp.close();interp=None
            deadline.check()
            improved=valid and (best is None or (value<best if s['start']==1 else value>best))
            if improved:best=value;best_step=step
            m.write(action/'node.private.json',dict(code=code,plan=reason,terminal=terminal))
            m.write(action/'result.json',dict(step=step,kind=mode,valid=valid,metric=value,
                execution_success=ok,exit_code=out.exit_code,timed_out=out.timed_out,
                exec_seconds=out.exec_time,execution_wall_seconds=wall,replay_seconds=replay_seconds,
                elapsed_seconds=deadline.elapsed(),code_sha256=code_sha,selected_metric=best,selected_step=best_step,
                retained=s['retained'],visible=s['visible'],successful_ledger_cells=len(ledger)))
            returned=terminal[-12000:] if step>0 or s['visible'] else '[initial program stdout withheld; future tool returns remain available]'
            history+=f'\nACTION {step} {mode}\nDECLARED REASON:\n{reason}\nRETURNED OUTPUT:\n{returned}\nExit={out.exit_code}; timed_out={out.timed_out}; valid_submission={valid}; external_development_score={value}; incumbent={best}\n'
            if improved:m.write(action/'selected.json',dict(step=step,metric=best,elapsed=deadline.elapsed()))
        m.write(ep/'completed.json',dict(selected_metric=best,selected_step=best_step,valid=best is not None,elapsed_seconds=deadline.elapsed(),generations=generations))
    finally:
        if interp is not None:interp.close()
m.episode=episode

def adapt(name,pairs):
    src=inspect.getsource(getattr(m,name))
    for old,new in pairs:
        if src.count(old)!=1:raise ValueError('adaptation mismatch '+name)
        src=src.replace(old,new)
    exec(compile(src,'state_factorial_'+name,'exec'),m.__dict__)
adapt('worker',[("TIME_LIMIT='30 minutes'","TIME_LIMIT='12 minutes'")])
adapt('controller',[('03:39:00','02:14:00'),('00:33:00','00:15:00'),('for wave in range(6):','for wave in range(8):'),('max_workers=3','max_workers=2'),('dict(attempts=18,','dict(attempts=16,')])

def prepare():
    if ROOT.exists():raise FileExistsError(ROOT)
    if m.sha(OLD/'plan.json')!='939f9470529ad6c14f5b6670bb1bec4cd99398026f6fbdbea662c8d29e32c48e':raise ValueError('source plan drift')
    p=m.read(OLD/'plan.json');ROOT.mkdir(mode=0o700)
    for rel,h in p['files'].items():
        if not (rel.startswith(('source/','forets_','opencl-vendors/')) or rel in ('root_trial_step_supervisor_20260927.py','v6_runtime.py')):continue
        if m.sha(OLD/rel)!=h:raise ValueError('source drift '+rel)
        dest=ROOT/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(OLD/rel,dest)
    shutil.copyfile(__file__,ROOT/'task_feedback_real_20261001.py')
    # Common future-only partial-output correction, already independently unit tested.
    src=Path(__file__).parent/'jupyter_client.py';dest=ROOT/'source/src/dojo/core/interpreters/jupyter/jupyter_client.py'
    if m.sha(dest)!='a6c6abdca37745ce8d5137f48595a3c0e6332c113e8133b0782425b7bbb291bf':raise ValueError('client baseline drift')
    if m.sha(src)!='1e0ee6147b07b60a8aedebbe68f324daf04f4903100ea1dbc34e6bdd5a7fb780':raise ValueError('common client fix drift')
    shutil.copyfile(src,dest)
    for rel in ('starts','configs','bin','service-cache/tmp'):(ROOT/rel).mkdir(parents=True,exist_ok=True)
    (ROOT/'bin/singularity').write_text(f'#!{m.PY}\nimport sys\nsys.path.insert(0,{str(ROOT)!r})\nfrom task_feedback_real_20261001 import m\nm.task_runtime()\n');os.chmod(ROOT/'bin/singularity',0o700)
    entry=(OLD/'service_entry.py').read_text();assert entry.count("'19445'")==1
    (ROOT/'service_entry.py').write_text(entry.replace("'19445'","'19447'"))
    with (ROOT/'.service.env').open('x') as f:f.write('PRIMARY_KEY_QWEN3_8_27B='+secrets.token_hex(32)+'\n')
    os.chmod(ROOT/'.service.env',0o600)
    for i in range(2):shutil.copyfile(OLD/'starts'/f'{i}.private.json',ROOT/'starts'/f'{i}.private.json')
    for s in schedule():
        cfg=m.read(OLD/'configs'/f'{s["start"]}.json');ep=ROOT/f'episode-{s["index"]}';ep.mkdir()
        cfg['id']=f'state-factorial-{s["index"]}'
        cfg['logger'].update(output_dir=str(ep/'native-log'),write_env_vars=False,use_wandb=False,print_config=False,use_console=False)
        cfg['metadata'].update(seed=s['seed'],script_id='state-feedback-factorial-20261002',git_commit_id=m.COMMIT,base_path=str(ROOT/'source'))
        cfg['solver'].update(time_limit_secs=720,step_limit=5,checkpoint_path=str(ep/'unused-checkpoint'))
        cfg['interpreter']['working_dir']=str(ep/'unused-work');cfg['interpreter']['env']['PYTHONHASHSEED']=str(s['seed'])
        cfg['task']['cache_dir']=str(ROOT/'no-official-data')
        for op in cfg['solver']['operators'].values():
            op['llm']['client']['base_url']=f'http://127.0.0.1:{m.PORT}/v1'
            op['llm']['generation_kwargs'].update(max_tokens=4096,seed=s['seed'],bounded_request_timeout_seconds=180)
        m.write(ROOT/'configs'/f'{s["index"]}.json',cfg)
    batch=(OLD/'run.sbatch').read_text().replace(str(OLD),str(ROOT)).replace('decision-diagnosis','state-feedback-factorial').replace('01:40:00','02:15:00').replace('5940s','8040s')
    (ROOT/'run.sbatch').write_text(batch)
    files={str(f.relative_to(ROOT)):m.sha(f) for f in ROOT.rglob('*') if f.is_file() and f.name!='.service.env'}
    m.write(ROOT/'plan.json',dict(protocol='state-feedback-factorial-v1',base_commit=m.COMMIT,utc=m.utc(),schedule=schedule(),files=files,starts=p['starts'],run_seconds=720,allocation_seconds=8100,gpus=4,gpu_hours_cap=9,
        max_calls=4,max_tokens_per_call=4096,execution_cap=300,paid_api=0,agent_training=False,
        arms=ARMS,observation_intervention='initial public stdout only; all future observations and external development scores return normally',primary='all assigned trajectories; oriented incumbent gain; interaction (D-B)-(C-A) by seed/task',
        gate='both tasks median interaction >0 and median D-C >0 and D-B >0; plus actual evidence-to-edit trace; this is mechanism qualification not new method superiority',
        limitations='2 generation seeds/task, one historically selected start; repeated development scores; no final evaluation; masking ablation deliberately not a strong baseline',
        common_changes_from_old='720s and 4 calls; executable cells and retained code ledger; partial-output fix shared by all arms; never compare old/new as state-only effect',protected_opened=False))
    print(json.dumps(dict(status='PREPARED',plan_sha256=m.sha(ROOT/'plan.json'),runs=16,gpu_hours_cap=9)))

def submit():
    m.check()
    q=B/'state-reuse-qualification-20261002-v1'
    if not m.read(q/'verification.json')['gate']:raise ValueError('cost qualification not passed')
    for name in ('cpu.json','transport-cpu.json'):
        r=m.read(ROOT/name)
        if r['status']!='PASS' or r['plan_sha256']!=m.sha(ROOT/'plan.json'):raise ValueError('CPU preflight stale')
    # The submit gate verifies actual images/weights, same as the prior bounded pilot.
    if m.sha(m.infra.TASK_IMAGE)!=m.infra.IMAGE_SHA or m.sha(m.ASSETS/'vllm.sif')!=m.infra.VLLM_SHA:raise ValueError('image drift')
    for r in m.read(m.ASSETS/'complete.json')['files']:
        if r['path'].endswith('.safetensors') and m.sha(m.ASSETS/r['path'])!=r['digest']:raise ValueError('weights drift')
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    jobs=subprocess.check_output(['squeue','-u','yzyang4','-h','-o','%i'],env=env,text=True,timeout=20).split()
    if set(jobs)-{'12535'}:raise ValueError('unexpected allocation')
    with (ROOT/'capacity.tmp').open('xb') as f:os.posix_fallocate(f.fileno(),0,512*1024**2)
    (ROOT/'capacity.tmp').unlink()
    m.write(ROOT/'submit-intent.json',dict(utc=m.utc(),plan_sha256=m.sha(ROOT/'plan.json')))
    r=subprocess.run(['sbatch','--parsable','--chdir='+str(ROOT),'--output='+str(ROOT/'allocation-%j.out'),'--error='+str(ROOT/'allocation-%j.err'),str(ROOT/'run.sbatch')],env=env,text=True,capture_output=True,timeout=25)
    job=r.stdout.strip().split(';')[0]
    if r.returncode or not job.isdigit():raise RuntimeError('ambiguous submit; no retry')
    m.write(ROOT/'launch.json',dict(job=job,utc=m.utc(),plan_sha256=m.sha(ROOT/'plan.json')));print(json.dumps(dict(job=job,status='SUBMITTED',gpu_hours_cap=9)))

if __name__=='__main__':
    os.umask(0o077);a=argparse.ArgumentParser();a.add_argument('mode',choices=['prepare','submit','check','worker','controller','service']);a.add_argument('--index',type=int);x=a.parse_args()
    if x.mode in ('prepare','submit'):globals()[x.mode]()
    elif x.mode=='worker':m.worker(x.index)
    elif x.mode=='check':m.check();print('FROZEN_PLAN_VALID')
    else:getattr(m,x.mode)()
