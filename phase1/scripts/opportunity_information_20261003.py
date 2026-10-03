"""Conditional information intervention; human hints are not a deployable method."""
import argparse,ast,hashlib,importlib.util,json,os,random,re,secrets,shutil,subprocess,sys
from pathlib import Path
B=Path('/research/d7/spc/yzyang4');P=B/'state-feedback-factorial-20261002-v1';Q=B/'natural-opportunity-20261003-v1';R=B/'opportunity-information-20261003-v2'
ENGINE_SHA='57b45de1d7afc9f9657c3667c583537db94cda9ee527d5999fe15fc23bb6397d'
engine=R/'factorial_engine.py' if (R/'factorial_engine.py').exists() else P/'task_feedback_real_20261001.py'
assert hashlib.sha256(engine.read_bytes()).hexdigest()==ENGINE_SHA
sp=importlib.util.spec_from_file_location('opportunity_factorial_base',engine);d=importlib.util.module_from_spec(sp);sys.modules[sp.name]=d;sp.loader.exec_module(d)
m=d.m;d.ROOT=R;m.ROOT=R;m.PORT=19453;m.CAP=5400;m.SECONDS=600;m.COMMIT='a284f3df7e8239a042765a329c81282643a4d5a1';m.infra.ROOT=R;m.infra.SERVICE_PORT=m.PORT
TASKS=('random-acts-of-pizza','spooky-author-identification');STATES=(4,0)
FACTS={0:'The XGBoost member receives a validation fold via eval_set and is configured for 1000 trees. Its constructor and fit call do not enable early stopping. In the same program the LightGBM member uses early stopping. These are code facts, not evidence that either model generalizes better.',
       1:'The program measures separate five-fold CV log losses for word, character and combined representations. The final test prediction instead uses fixed weights 0.3 word, 0.3 character, 0.4 combined, not selected using those losses. This is a code fact; blending is not inherently wrong and CV selection can overfit.'}
SPECS={0:'For the existing XGBoost member, enable early_stopping_rounds=50 using its already provided validation fold and AUC metric. Preserve the data, fold partition, features, all other estimators, stacking, and remaining XGBoost parameters. Use the fitted best iteration for predictions. Do not add training data or replace the pipeline.',
       1:'Select exactly one existing representation by minimum mean five-fold CV log loss among word, character, and combined; resolve an exact tie in that order. Use that member\'s already fitted full-training test probabilities instead of the fixed weighted blend. Preserve all fits, data, parameters, and submission format.'}
def schedule():
    order=list('ABC');random.Random(104040).shuffle(order);out=[]
    for block in range(2):
        for arm in order if block==0 else order[::-1]:
            for k,name in enumerate(TASKS):out.append(dict(index=len(out),start=k,source_state=STATES[k],task=name,arm=arm,seed=104101+10*block+k,wave=len(out)//2,retained=True,visible=True))
    return out
m.schedule=schedule;d.schedule=schedule
COMMON='''Improve this working natural ML program in an ordinary persistent coding workspace.
You may inspect data, test hypotheses, keep existing models, or train new ones. No mandatory
diagnosis, model family or target edit is required. Known references include word/character
TFIDF, numerical boosting, early stopping, public CV model selection, and blending.
You have FOUR model calls and 600 TOTAL seconds including initial execution, generation,
tools, failed attempts, reconstruction and grading. Each code call is at most 300 seconds.
Use one standalone CHECK or SOLUTION line, brief rationale, then one fenced python block.
CHECK inspects allowed evidence without grading; SOLUTION writes a NEW submission.csv.
The final call must be SOLUTION. Prior successful cells remain live. Failed cells roll
back to the successful ledger, whose reconstruction costs budget. The evaluator separately
keeps the best valid submission, so retaining the original is allowed.
All arms use one RTX3090 and six CPU cores, the same model, tools and task image. Use only
/workspace/data and your workspace, with no downloads or hidden labels. /workspace/parent.py
is the original program. Returned external scores are reused DEVELOPMENT observations,
not final test results. Lower log-loss is better; higher AUC is better.
'''
def prompt(task,s,step,ledger,history,remaining):
    note='No extra advisory facts supplied; all code, public evidence and tools remain available.'
    if s['arm']=='B':note='Human-supplied, code-verifiable facts (no proven quality gain):\n'+FACTS[s['start']]
    if s['arm']=='C':note='Human-supplied modification specification; verify and implement it without unrelated changes:\n'+SPECS[s['start']]
    return COMMON+'\n'+note+'\n'+('Final call: SOLUTION.' if step==4 else 'Choose any useful next CHECK or SOLUTION.')+'\nTASK:\n'+task+'\nSUCCESSFUL CODE LEDGER:\n'+'\n\n'.join(f'CELL {i}:\n{c}' for i,c in enumerate(ledger))+'\nOBSERVED HISTORY:\n'+history+f'\nTOTAL SECONDS REMAINING: {int(remaining)}\n'
d.prompt=prompt
def wrapper(code,seed,remove_submission=True):
    return (f'import random as _r, numpy as _n\n_r.seed({seed})\n_n.random.seed({seed})\n'
        +("from pathlib import Path as _P\n_P('submission.csv').unlink(missing_ok=True)\n" if remove_submission else '')
        +f'globals()["__name__"]="__main__"\nexec(compile({code!r},"cell.py","exec"))\n')
d.wrapper=wrapper
def decode(raw,step):
    assert not m.SECRET.search(raw.encode())
    modes=re.findall(r'(?m)^\s*(CHECK|SOLUTION)\s*$',raw.split('```',1)[0]);parts=re.findall(r'```python\s*\n(.*?)```',raw,re.S)
    if len(modes)!=1 or len(parts)!=1 or raw.count('```')!=2 or step==4 and modes[0]!='SOLUTION':raise ValueError('action format')
    ast.parse(parts[0]);return modes[0],parts[0],raw.split('```',1)[0]
d.decode=decode
# Recompile only known frozen orchestration definitions, not experiment logic.
source=Path(m.__file__).read_text();tree=ast.parse(source)
for name,changes in {'worker':[("TIME_LIMIT='30 minutes'","TIME_LIMIT='10 minutes'")],
 'controller':[('03:39:00','01:29:00'),('00:33:00','00:13:00'),('max_workers=3','max_workers=2'),('dict(attempts=18,','dict(attempts=12,')]}.items():
    node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name);text=ast.get_source_segment(source,node)
    for old,new in changes:assert text.count(old)==1;text=text.replace(old,new)
    exec(compile(text,'information_'+name,'exec'),m.__dict__)

def prepare():
    assert not R.exists() and m.read(Q/'verification.json')['cross_task_gate']
    summary=m.read(Q/'readout.json');assert {s['task'] for s in summary['states'] if s['qualifies']}>=set(TASKS)
    # Fixed smallest qualified state index per task, never largest observed effect.
    assert tuple(min(s['state'] for s in summary['states'] if s['qualifies'] and s['task']==t) for t in TASKS)==STATES
    R.mkdir(mode=0o700)
    for rel,h in m.read(P/'plan.json')['files'].items():
        if not(rel.startswith(('source/','forets_','opencl-vendors/')) or rel in ('v6_runtime.py','root_trial_step_supervisor_20260927.py')):continue
        assert m.sha(P/rel)==h;p=R/rel;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(P/rel,p)
    shutil.copyfile(engine,R/'factorial_engine.py');shutil.copyfile(__file__,R/'task_feedback_real_20261001.py')
    for name in ('configs','starts','bin','service-cache/tmp'):(R/name).mkdir(parents=True,exist_ok=True)
    entry=(P/'service_entry.py').read_text();assert entry.count("'19447'")==1;(R/'service_entry.py').write_text(entry.replace("'19447'","'19453'"))
    with (R/'.service.env').open('x') as f:f.write('PRIMARY_KEY_QWEN3_8_27B='+secrets.token_hex(32)+'\n')
    os.chmod(R/'.service.env',0o600)
    (R/'bin/singularity').write_text(f'#!{m.PY}\nimport sys\nsys.path.insert(0,{str(R)!r})\nfrom task_feedback_real_20261001 import m\nm.task_runtime()\n');os.chmod(R/'bin/singularity',0o700)
    parents=[]
    for k,state in enumerate(STATES):
        row=next(s for s in m.read(Q/'plan.json')['schedule'] if s['state']==state and s['seed']==42 and s['arm']=='original')
        code=(Q/'programs'/f'{row["index"]}.private.py').read_text();m.write(R/'starts'/f'{k}.private.json',dict(code=code))
        parents.append(dict(start=k,source_state=state,code_sha256=hashlib.sha256(code.encode()).hexdigest(),source_plan_sha256=m.sha(Q/'plan.json'),program_seed=42))
    for s in schedule():
        cfg=m.read(Q/'starts'/f'{s["source_state"]}.config.private.json');ep=R/f'episode-{s["index"]}';ep.mkdir()
        cfg['id']=f'opportunity-information-{s["index"]}';cfg['logger'].update(output_dir=str(ep/'native-log'),write_env_vars=False,use_wandb=False,print_config=False,use_console=False)
        cfg['metadata'].update(seed=s['seed'],script_id='opportunity-information-20261003',base_path=str(R/'source'),git_commit_id=m.COMMIT)
        cfg['solver'].update(root_failure_randomization=False,acquisition_first_slot=False,record_slate_hashes=False,use_test_score=False,time_limit_secs=600,step_limit=5,checkpoint_path=str(ep/'unused-checkpoint'))
        cfg['interpreter']['working_dir']=str(ep/'unused-work');cfg['interpreter']['timeout']=300
        cfg['interpreter']['env'].update(PYTHONHASHSEED='42',OMP_NUM_THREADS='6',OPENBLAS_NUM_THREADS='6',MKL_NUM_THREADS='6',NUMEXPR_NUM_THREADS='6');cfg['task']['cache_dir']=str(R/'no-official-data')
        for op in cfg['solver']['operators'].values():
            op['llm']['client']['base_url']=f'http://127.0.0.1:{m.PORT}/v1'
            op['llm']['generation_kwargs'].update(max_tokens=4096,seed=s['seed'],bounded_request_timeout_seconds=180,bounded_transport=True,bounded_max_attempts=1,structured_output_retries=0,extra_body={'chat_template_kwargs':{'enable_thinking':False}})
        m.write(R/'configs'/f'{s["index"]}.json',cfg)
    batch=(P/'run.sbatch').read_text().replace(str(P),str(R)).replace('state-feedback-factorial','opportunity-information').replace('02:15:00','01:30:00').replace('8040s','5340s');(R/'run.sbatch').write_text(batch)
    m.write(R/'plan.json',dict(protocol='qualified-natural-opportunity-information-v1',base_commit=m.COMMIT,utc=m.utc(),schedule=schedule(),starts=parents,
        files={str(p.relative_to(R)):m.sha(p) for p in R.rglob('*') if p.is_file() and p.name!='.service.env'},run_seconds=600,allocation_seconds=5400,gpus=4,gpu_hours_cap=6,
        runs=12,max_calls=4,max_tokens=4096,code_seconds=300,paid_api=0,base_updates=0,
        qualification_summary_sha256=m.sha(Q/'readout.json'),qualification_verifier_sha256=m.sha(Q/'verification.json'),
        primary='All assigned trajectories: B-A and C-A oriented retained-incumbent gains by task/paired generation seed; C-B as secondary contrast. Invalid initial states unknown, not zero. Failure after valid initial keeps incumbent.',
        mechanism='Verify actual target implementation, unrelated changes, observed evidence and all failed attempts. Candidate code text/quoted hints alone are not causal evidence.',
        gate='Only exploratory diagnostic leverage if both tasks have median B-A>0, neither paired seed B-A<0, and B generates actual improved valid submissions; C-A separately tests specification assistance. No new-method or heldout claim.',
        information='A ordinary full-tool agent, B code-verifiable localized facts without target patch, C explicit change specification. Human information is an oracle capability intervention; selection uses earlier development outcomes. Information amount/attention confounded, not pure modular capability isolation.',
        cost='All new initialization/generation/repair/scoring/idle GPU time included. Earlier manual witness discovery is extra sunk cost, not free deployed inference. Additional 6GPUh requires user approval.',
        selection='Only minimum qualified state per task, not largest effect; conditional subset 2 of original6 roster. Parent program seed42 fixed, paired generation seeds vary. No untouched confirmation.',protected_opened=False))
    cpu();print(json.dumps(dict(status='PREPARED_NOT_SUBMITTED',runs=12,plan_sha256=m.sha(R/'plan.json'),gpu_hours_cap=6)))

def cpu():
    m.check();m.setup()
    os.environ['PRIMARY_KEY_QWEN3_8_27B']='synthetic-test-only'
    from dojo.config_dataclasses.run import RunConfig
    from dojo.tasks.mlebench.task import MLEBenchTask
    from dojo.core.solvers.llm_helpers.generic_llm import GenericLLM
    from omegaconf import OmegaConf
    for s in schedule():
        c=RunConfig.load_from_json(R/'configs'/f'{s["index"]}.json');c.validate();t=MLEBenchTask(c.task);assert t._search_only_score and not t.private_dir.exists()
        llm=GenericLLM(OmegaConf.structured(c.solver.operators['improve']));json.dumps(llm.generation_kwargs)
        msg=prompt(t.task_description,s,1,['x=1'],'log',500)
        assert (FACTS[s['start']] in msg)==(s['arm']=='B') and (SPECS[s['start']] in msg)==(s['arm']=='C')
        assert len(m.read(R/'starts'/f'{s["start"]}.private.json')['code'])>100
    for mode in ('CHECK','SOLUTION'):assert decode('Reason\n'+mode+'\n```python\nx=1\n```',1)[0]==mode
    env={};exec(wrapper('assert __name__=="__main__"\nz=7',42,False),env);assert env['z']==7
    subprocess.run(['bash','-n',str(R/'run.sbatch')],check=True)
    m.write(R/'cpu.json',dict(status='PASS',configs=12,sdk_configs=12,prompt_checks=12,parser_cases=2,main_guard=True,plan_sha256=m.sha(R/'plan.json')))

def submit():
    m.check();approval=m.read(R/'budget-approval.json');assert approval['approved'] is True and approval['gpu_hours_cap']==6
    assert m.read(R/'cpu.json')['plan_sha256']==m.sha(R/'plan.json')
    assert m.sha(m.infra.TASK_IMAGE)==m.infra.IMAGE_SHA and m.sha(m.ASSETS/'vllm.sif')==m.infra.VLLM_SHA
    for x in m.read(m.ASSETS/'complete.json')['files']:
        if x['path'].endswith('.safetensors'):assert m.sha(m.ASSETS/x['path'])==x['digest']
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf');jobs=subprocess.check_output(['squeue','-u','yzyang4','-h','-o','%i'],env=env,text=True,timeout=25).split();assert not set(jobs)-{'12535'}
    m.write(R/'submit-intent.json',dict(utc=m.utc(),plan_sha256=m.sha(R/'plan.json')))
    r=subprocess.run(['sbatch','--parsable','--chdir='+str(R),'--output='+str(R/'allocation-%j.out'),'--error='+str(R/'allocation-%j.err'),str(R/'run.sbatch')],env=env,capture_output=True,text=True,timeout=25)
    job=r.stdout.strip().split(';')[0];assert r.returncode==0 and job.isdigit(),'ambiguous: no blind retry'
    m.write(R/'launch.json',dict(job=job,utc=m.utc(),plan_sha256=m.sha(R/'plan.json')));print(json.dumps(dict(job=job,status='SUBMITTED',gpu_hours_cap=6)))
if __name__=='__main__':
    os.umask(0o077);a=argparse.ArgumentParser();a.add_argument('mode',choices=['prepare','cpu','submit','worker','controller','service']);a.add_argument('--index',type=int);x=a.parse_args()
    if x.mode in ('prepare','cpu','submit'):globals()[x.mode]()
    elif x.mode=='worker':m.worker(x.index)
    else:getattr(m,x.mode)()
