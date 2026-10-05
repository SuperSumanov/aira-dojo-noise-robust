"""Fixed-source equal-budget R11 repair. Requires real native preflight before submit.

Not a rescue/reanalysis of 16357, not full-search E2E, no automatic expansion.
"""
from __future__ import annotations
import argparse, ast, asyncio, copy, hashlib, importlib.util, inspect, json
import logging, math, os, random, secrets, shutil, subprocess, sys, time
from pathlib import Path
import implementation_reset_contract_v2_20261005 as contract
from implementation_reset_20261005 import read, write, sha, SECRET, DONOR_SHA

B=Path('/research/d7/spc/yzyang4')
OLD=B/'policy9b-paired-20261005-gpu27-v1'
R=B/'implementation-reset-20261005-v2'
PY=B/'venvs/aira/bin/python'
NAME=Path(__file__).name
FILES=(NAME,'implementation_reset_contract_v2_20261005.py','implementation_reset_20261005.py',
       'analyze_implementation_reset_20261005.py','analyze_implementation_reset_v2_20261005.py')
SECONDS,CAP=600,7200

def schedule():
    rows=[dict(index=t,wave=0,task=task,start=t,seed=111401+t,execution_seed=111401+t,arm='ROOT')
          for t,task in enumerate(contract.TASKS)]
    rows += [{**s,'index':s['index']+2,'wave':s['wave']+1} for s in contract.schedule()]
    return rows

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m

def host():
    p=OLD/'policy9b_paired_20261005.py';assert sha(p)==DONOR_SHA
    m=load('reset_v2_host',p)
    m.R,m.CAP,m.SECONDS,m.__file__=R,CAP,SECONDS,str(R/NAME)
    m.schedule,m.check,m.freeze_sources=schedule,check,freeze_sources
    changes={
        'task_runtime':[('episode-[0-7]','episode-[0-9]+')],
        'controller':[('range(4)','range(9)'),('01:29:00','01:59:00'),
                      ('<1200:','<600:'),('dict(attempts=8,','dict(attempts=18,'),
                      ("write(R/f'wave-{wave}.json',dict(indices=done,utc=utc()))",
                       "write(R/f'wave-{wave}.json',dict(indices=done,utc=utc()))\n                if wave == 0 and not freeze_sources(): return")]
    }
    for name,replacements in changes.items():
        text=inspect.getsource(getattr(m,name))
        for before,after in replacements:
            assert text.count(before)==1,(name,before)
            text=text.replace(before,after)
        exec(compile(text,NAME+':'+name,'exec'),m.__dict__)
    return m

def check():
    p=read(R/'plan.json');assert p['schedule']==schedule()
    for name,h in p['files'].items():assert sha(R/name)==h,name
    assert sha(OLD/'policy9b_paired_20261005.py')==DONOR_SHA
    return p

def prepare():
    assert not R.exists(),'new experiment root only'
    frozen=read(OLD/'plan.json')
    assert sha(OLD/'plan.json')=='12d1264457158c936e4f1eff8e9c844ce5044365e77056066c4ded2ecfe6cd79'
    R.mkdir(mode=0o700)
    helpers=('forets_gpu_binding_20260911.py','forets_native_cuda_identity_20260911.py',
             'forets_native_gpu_binding_20260911.py','forets_opencl_allowlist_20260911.py',
             'forets_opencl_readonly_ab.py','root_trial_step_supervisor_20260927.py','service_entry.py')
    for name,h in frozen['files'].items():
        if name.startswith('source/') or name in helpers:
            assert sha(OLD/name)==h
            target=R/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(OLD/name,target)
    for name in FILES:shutil.copyfile(Path(__file__).with_name(name),R/name)
    for folder in ('configs','starts','bin','opencl-vendors','service-cache/tmp'):
        (R/folder).mkdir(parents=True,exist_ok=True)
    (R/'opencl-vendors/nvidia.icd').write_text('libnvidia-opencl.so.1\n')
    (R/'bin/singularity').write_text(f'#!{PY}\nimport sys\nsys.path.insert(0,{str(R)!r})\nfrom implementation_reset_v2_20261005 import host\nhost().task_runtime()\n')
    os.chmod(R/'bin/singularity',0o700)
    with (R/'.service.env').open('x') as f:f.write('PRIMARY_KEY_QWEN3_8_27B='+secrets.token_hex(32)+'\n')
    os.chmod(R/'.service.env',0o600)
    for s in schedule():
        old='configs/'+str(s['start'])+'.json';assert sha(OLD/old)==frozen['files'][old]
        cfg=read(OLD/old);ep=R/f"episode-{s['index']}";ep.mkdir()
        cfg['id']='implementation-reset-v2-'+str(s['index'])
        cfg['metadata'].update(seed=s['seed'],script_id='implementation-reset-v2-20261005',base_path=str(R/'source'))
        cfg['logger'].update(output_dir=str(ep/'native-log'),write_env_vars=False,use_wandb=False,print_config=False,use_console=False)
        cfg['solver'].update(time_limit_secs=600,execution_timeout=240,step_limit=10000,checkpoint_path=str(ep/'checkpoint'))
        cfg['interpreter']['working_dir']=str(ep/'work')
        cfg['interpreter']['env']['PYTHONHASHSEED']=str(s['execution_seed'])
        cfg['task']['cache_dir']=str(R/'no-official-data')
        for kind,op in cfg['solver']['operators'].items():
            op['llm']['client']['model_id']='qwen3.5-9b'
            op['llm']['generation_kwargs']['seed']=s['seed']
            if s['arm'] not in ('ROOT','random_hpo') and kind in contract.USER:
                cfg['solver']['operators'][kind]=contract.operator_config(op,s['arm'],kind)
        write(R/'configs'/f"{s['index']}.json",cfg)
    batch=f'''#!/bin/bash
#SBATCH --job-name=idea-reset-v2-four-arm
#SBATCH --partition=gpu_24h
#SBATCH --account=gpu
#SBATCH --qos=gpu
#SBATCH --nodelist=gpu27
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:4
#SBATCH --cpus-per-task=24
#SBATCH --time=02:00:00
#SBATCH --no-requeue
set -euo pipefail
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1
timeout --signal=TERM --kill-after=20s 7120s {PY} -B {R/NAME} controller
'''
    (R/'run.sbatch').write_text(batch)
    files={str(p.relative_to(R)):sha(p) for p in R.rglob('*') if p.is_file() and p.name!='.service.env'}
    write(R/'plan.json',dict(protocol='fixed-human-source-implementation-reset-v2',utc=host().utc(),files=files,
        schedule=schedule(),source_commit=frozen['source_commit'],infra_sha256=DONOR_SHA,
        source_runs=2,comparison_runs=16,run_seconds=600,allocated_gpus=4,allocation_seconds=7200,gpu_hours_cap=8,
        task_image_sha256=frozen['task_image_sha256'],service_image_sha256=frozen['service_image_sha256'],
        base=frozen['base'],base_revision=frozen['base_revision'],context_tokens=32768,max_output_tokens=8192,
        no_thinking=True,model_training=False,paid_api=0,
        source_selection='One human-specified untuned word-TFIDF/LR per task, frozen before execution; no historical candidate selection. Two generation seeds share it, not independent source ideas.',
        source_program_sha256={s['task']:hashlib.sha256(contract.source_program(s['task'],s['execution_seed']).encode()).hexdigest() for s in schedule()[:2]},
        budget='600s whole episode including generation, execution and scorer; <=240s/program. Full common source cost charged to every strategy; full 4-GPU allocation including idle service reported. No free inference/HPO.',
        visibility='Continue sees old code; other generation arms do not. No runtime state inherited. Context removal and operator route are bundled; not pure context or idea causal identification.',
        intervention='Same-idea conditions get higher-priority conflict-free contract plus conservative family screen; rejected generations spend budget and get constraint feedback. New-idea has different contract. Random HPO is fixed external-code cheap strong control.',
        source_gate='Both fixed sources must execute and score validly; no replacement. Source execution is not evidence of method gain.',
        primary='Oriented paired final best development score, same incumbent fallback, all assigned trajectories. Per-task median and sample variance. Closed failures retained, missing infrastructure outcomes not imputed.',
        advance='No automatic expansion. All four seed-task reimplement contrasts against all three controls must be positive, plus independent blinded semantics, then fresh confirmation is needed.',
        limitations='Reused development tasks; manual simple family/source; only two tasks and two generation seeds. Not full MCTS, independent confirmation, semantic proof or a new learned selector.',
        approval='2026-10-05 user explicitly requests repair and continuation; 2 tasks x 2 seeds x 4 arms and <=8 GPUh announced before implementation.'))
    cpu()
    print(json.dumps({'status':'PREPARED','plan_sha256':sha(R/'plan.json'),'runs':18,'gpu_hours_cap':8}))

def cpu():
    check();m=host();m.setup()
    from dojo.config_dataclasses.run import RunConfig
    from dojo.tasks.mlebench.task import MLEBenchTask
    from dojo.core.solvers.utils.journal import Journal,Node
    from dojo.core.solvers.llm_helpers.generic_llm import GenericLLM
    from dojo.core.solvers.operators.draft import draft_op
    from dojo.core.solvers.operators.improve import improve_op
    from dojo.core.solvers.operators.debug import debug_op
    from dojo.utils.logger import config_logger
    from omegaconf import OmegaConf
    os.environ['PRIMARY_KEY_QWEN3_5_9B']='offline-fixture'
    renders=0;normalized=[]
    for s in schedule():
        cfg=RunConfig.load_from_json(R/'configs'/f"{s['index']}.json");cfg.validate();config_logger(cfg)
        task=MLEBenchTask(cfg.task)
        assert task._search_only_score is not None and not task.private_dir.exists() and cfg.solver.use_test_score is False
        assert sha(Path(cfg.task.search_only_dev_scorer_path))==cfg.task.search_only_dev_scorer_sha256
        for kind,op in (('draft',draft_op),('improve',improve_op),('debug',debug_op)):
            if s['arm'] in ('ROOT','random_hpo'):continue
            llm=GenericLLM(OmegaConf.structured(cfg.solver.operators[kind]));j=Journal()
            parent=Node(code='parent_sentinel=12345',plan='family',_term_out=['prior'])
            async def mock(**kw):
                q=kw['query_data'];system=llm.system_message_prompt_template.format(**q);user=llm.init_user_message_prompt_template.format(**q)
                assert system==contract.system_prompt(s['arm'],kind)
                assert 'USE 5-FOLD' not in system+user and 'DIFFERENT ASPECT' not in system+user
                assert ('parent_sentinel' in user)==(kind!='draft')
                assert 'LogisticRegression' in system
                return '```python\npass\n```',{}
            args=[mock,OmegaConf.structured(cfg.solver),None,task.task_description,j]
            if kind!='draft':args.append(parent)
            asyncio.run(op(*args,1,600,data_preview='public-only'));renders+=1
        d=cfg.to_typed_dict()
        for k in ('id','metadata','logger'):d.pop(k,None)
        for k in ('exp_name','checkpoint_path'):d['solver'].pop(k,None)
        for op in d['solver']['operators'].values():
            for k in ('system_message_prompt_template','init_user_message_prompt_template'):op.pop(k,None)
            op['llm']['generation_kwargs'].pop('seed',None)
        d['interpreter'].pop('working_dir',None);d['task'].pop('results_output_dir',None)
        normalized.append((s,d))
    for t in range(2):
        group=[c for s,c in normalized if s['start']==t and s['arm']!='ROOT']
        assert len(group)==8 and all(c==group[0] for c in group)
    subprocess.run(['bash','-n',str(R/'run.sbatch')],check=True)
    write(R/'cpu.json',dict(status='PASS',configs=18,native_renders=renders,plan_sha256=sha(R/'plan.json'),model_calls=0))

def freeze_sources():
    rows=[]
    for s in schedule()[:2]:
        p=R/f"episode-{s['index']}"/'first-valid.private.json'
        if not p.exists():
            write(R/'source-gate.json',dict(passed=False,reason='fixed_source_failed',missing_start=s['start']));return False
        x=read(p);expected=contract.source_program(s['task'],s['execution_seed'])
        assert x['code']==expected and contract.family_screen(x['code'])['pass']
        write(R/'starts'/f"{s['start']}.private.json",x)
        rows.append(dict(start=s['start'],code_sha256=hashlib.sha256(expected.encode()).hexdigest(),source_sha256=sha(p)))
    write(R/'source-gate.json',dict(passed=True,roots=rows,human_source=True));return True

def worker(index):
    # Reuse accepted per-worker deadline, identity and GPU namespace setup verbatim.
    p=B/'implementation-reset-20261005-v1'/'implementation_reset_20261005.py'
    assert sha(p)=='ca58ba5f91ba58b5f527707fb1953f5ca52388402e7a35d95b227f00e7ed6a92'
    m=load('reset_v2_worker_host',p)
    m.R,m.NAME,m.check,m.schedule,m.native,m.episode=R,NAME,check,schedule,host,episode
    m.worker(index)

def episode(s,ep,deadline):
    from dojo.config_dataclasses.run import RunConfig
    from dojo.config_dataclasses.interpreter import INTERPRETER_MAP
    from dojo.tasks.mlebench.task import MLEBenchTask
    from dojo.utils.config import build
    from dojo.utils.logger import config_logger
    from dojo.core.tasks.constants import EXECUTION_OUTPUT,VALID_SOLUTION,VALIDATION_FITNESS,VALID_SOLUTION_FEEDBACK
    from dojo.core.solvers.utils.journal import Journal,Node
    from dojo.core.solvers.utils.metric import MetricValue,WorstMetricValue
    from dojo.utils.code_parsing import extract_code
    from dojo.core.solvers.operators.draft import draft_op
    from dojo.core.solvers.operators.improve import improve_op
    from dojo.core.solvers.operators.debug import debug_op
    from dojo.core.solvers.llm_helpers.generic_llm import GenericLLM
    from omegaconf import OmegaConf
    import numpy as np
    cfg=RunConfig.load_from_json(R/'configs'/f"{s['index']}.json");config_logger(cfg)
    for name in ('openai','httpx','httpcore','LiteLLM'):logging.getLogger(name).setLevel(logging.ERROR)
    desc=MLEBenchTask(cfg.task).task_description
    score=None;node=None;best_node=None;journal=Journal();lower=s['task']==contract.TASKS[1]
    if s['arm']!='ROOT':
        assert read(R/'source-gate.json')['passed']
        source=read(R/'starts'/f"{s['start']}.private.json");score=source['metric']
        if s['arm']=='continue':
            best_node=Node(code=source['code'],plan=contract.IDEA,_term_out=[source['terminal']],is_buggy=False,metric=MetricValue(score,maximize=not lower))
    best=score
    write(ep/'condition.json',dict(arm=s['arm'],old_code_visible=s['arm']=='continue',inherited_runtime_state=False,execution_seed=s['execution_seed']))
    for step in range(64):
        deadline.check()
        if deadline.remaining()<15:break
        action=ep/f'action-{step}';action.mkdir()
        kind='fixed_source' if s['arm']=='ROOT' else 'random_hpo'
        if s['arm'] in ('ROOT','random_hpo'):
            params=None if s['arm']=='ROOT' else contract.hpo_configs(s['seed'])[step]
            code=contract.source_program(s['task'],s['execution_seed'],params)
        else:
            selected=node if node is not None and node.is_buggy else best_node
            kind='draft' if selected is None else ('debug' if selected.is_buggy else 'improve')
            opc=copy.deepcopy(cfg.solver.operators[kind]);kw=opc.llm.generation_kwargs
            call_seed=s['seed']*1000+step;kw['seed']=call_seed
            kw['bounded_request_timeout_seconds']=max(1,min(180,int(deadline.remaining())))
            random.seed(call_seed);np.random.seed(call_seed)
            llm=GenericLLM(OmegaConf.structured(opc));op={'draft':draft_op,'debug':debug_op,'improve':improve_op}[kind]
            args=[llm,OmegaConf.structured(cfg.solver),None,desc+f'\nCommon incumbent development score: {score}',journal]
            if selected is not None:args.append(selected)
            start=time.monotonic()
            try:
                response,info=asyncio.run(asyncio.wait_for(op(*args,step,int(deadline.remaining()),data_preview='Use task-described files in ./data.'),timeout=max(1,min(185,deadline.remaining()))))
            except Exception as exc:
                reason=contract.generation_failure(exc)
                if reason is None:raise
                write(action/'generation-failure.json',dict(reason=reason,elapsed_seconds=deadline.elapsed(),retry=False));break
            raw=str(response);assert not SECRET.search(raw.encode())
            messages=info['prompt_messages'];assert messages[0]['content']==contract.system_prompt(s['arm'],kind)
            write(action/'generation.private.json',dict(response=raw,info=info,generation_seconds=time.monotonic()-start,call_seed=call_seed,kind=kind))
            try:
                code=extract_code(raw);assert code.strip();ast.parse(code)
            except (SyntaxError,ValueError,AssertionError):
                write(action/'parse-failure.json',dict(elapsed_seconds=deadline.elapsed()));break
        write(action/'code.private.json',dict(code=code))
        node=Node(code=code,plan=contract.IDEA if s['arm']!='new_idea' else 'alternative family',_term_out=[],is_buggy=True,metric=WorstMetricValue())
        screen=contract.family_screen(code)
        reasons=screen['reasons'] if s['arm']!='new_idea' else (['still_same_modeling_family'] if screen['pass'] else [])
        if reasons:
            node._term_out=['Experiment contract rejected: '+', '.join(reasons)];journal.append(node)
            write(action/'contract-rejection.json',dict(screen=screen,elapsed_seconds=deadline.elapsed(),executed=False))
            continue
        task=MLEBenchTask(cfg.task);original=task._search_only_score
        def capture(name,submission):
            receipt=original(name,submission);shutil.copyfile(submission,action/'submission.private.csv')
            write(action/'score.private.json',dict(receipt=receipt,elapsed_seconds=deadline.elapsed()));return receipt
        task._search_only_score=capture
        icfg=copy.deepcopy(cfg.interpreter);icfg.working_dir=str(action/'work');icfg.timeout=max(1,min(240,int(deadline.remaining())))
        Path(icfg.working_dir).mkdir();interp=build(icfg,INTERPRETER_MAP,data_dir=cfg.task.data_dir)
        try:
            state,_=task.prepare(solver_interpreter=interp,eval_interpreter=None)
            executable=f'import random as _r, numpy as _n\n_r.seed({s["execution_seed"]})\n_n.random.seed({s["execution_seed"]})\n'+f'exec(compile({code!r},"solution.py","exec"))\n'
            state,result=task.step_task(state,executable);deadline.check()
        finally:
            interp.close()
            if hasattr(interp,'cleanup_session'):interp.cleanup_session()
        out=result[EXECUTION_OUTPUT];node.absorb_exec_result(out)
        value=result.get(VALIDATION_FITNESS)
        valid=bool(result.get(VALID_SOLUTION)) and out.exit_code==0 and not out.timed_out and isinstance(value,(int,float)) and math.isfinite(value)
        node.is_buggy=not valid
        if valid:node.metric=MetricValue(value,maximize=not lower)
        node._term_out=list(node._term_out or [])+['\nTrusted DEVELOPMENT feedback: '+str(result.get(VALID_SOLUTION_FEEDBACK,''))]
        write(action/'terminal.private.json',dict(terminal=node.term_out))
        journal.append(node)
        if valid and (best_node is None or node.metric>best_node.metric):best_node=node
        improves=valid and (best is None or (value<best if lower else value>best))
        if improves:best=value
        write(action/'result.json',dict(valid=valid,metric=value if valid else None,selected_metric=best,improves=improves,
            elapsed_seconds=deadline.elapsed(),exec_seconds=out.exec_time,exit_code=out.exit_code,timed_out=out.timed_out,kind=kind,
            code_sha256=hashlib.sha256(code.encode()).hexdigest(),idea_screen=screen))
        if s['arm']=='ROOT':
            if valid:write(ep/'first-valid.private.json',dict(code=code,metric=value,terminal=node.term_out,elapsed_seconds=deadline.elapsed(),step=step,task=s['task'],seed=s['execution_seed']))
            break

def submit():
    p=check();assert read(R/'cpu.json')['plan_sha256']==sha(R/'plan.json')
    m=host();assert sha(m.TASK_IMAGE)==p['task_image_sha256'] and sha(m.VLLM)==p['service_image_sha256']
    assert m.MODEL.is_dir() and m.ADAPTER.is_dir()
    env=m.infra().clean_env()
    jobs=subprocess.check_output(['squeue','-u','yzyang4','-h','-o','%i'],env=env,text=True,timeout=20).split()
    assert not set(jobs)-{'12535'}
    write(R/'submit-intent.json',dict(utc=m.utc(),plan_sha256=sha(R/'plan.json')))
    res=subprocess.run(['sbatch','--parsable','--chdir='+str(R),'--output='+str(R/'allocation-%j.out'),'--error='+str(R/'allocation-%j.err'),str(R/'run.sbatch')],env=env,capture_output=True,text=True,timeout=25)
    job=res.stdout.strip().split(';')[0];assert res.returncode==0 and job.isdigit(),'ambiguous submit; do not retry'
    write(R/'launch.json',dict(job=job,utc=m.utc(),plan_sha256=sha(R/'plan.json')))
    print(json.dumps(dict(status='SUBMITTED',job=job,runs=18,gpu_hours_cap=8)))

if __name__=='__main__':
    os.umask(0o077)
    p=argparse.ArgumentParser();p.add_argument('mode',choices=('prepare','cpu','submit','worker','controller','service'));p.add_argument('--index',type=int);a=p.parse_args()
    if a.mode=='worker':worker(a.index)
    elif a.mode in ('controller','service'):getattr(host(),a.mode)()
    else:globals()[a.mode]()
