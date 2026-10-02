"""Equal-budget public counterexample observation pilot, not a novelty claim.

Only the initial automatically displayed public-training example selector differs.
Both arms retain ordinary tool access and can reacquire other public evidence.
"""
import argparse,ast,copy,hashlib,importlib.util,inspect,json,os,random,re,secrets,shutil,subprocess,sys
from pathlib import Path
B=Path('/research/d7/spc/yzyang4');PARENT=B/'state-feedback-factorial-20261002-v1'
ROOT=B/'public-example-feedback-20261003-v1'
ENGINE_SHA='57b45de1d7afc9f9657c3667c583537db94cda9ee527d5999fe15fc23bb6397d'
engine=ROOT/'factorial_engine.py' if (ROOT/'factorial_engine.py').exists() else PARENT/'task_feedback_real_20261001.py'
assert hashlib.sha256(engine.read_bytes()).hexdigest()==ENGINE_SHA
spec=importlib.util.spec_from_file_location('public_example_engine',engine)
d=importlib.util.module_from_spec(spec);sys.modules[spec.name]=d;spec.loader.exec_module(d)
m=d.m;d.ROOT=ROOT;m.ROOT=ROOT;m.PORT=19449;m.CAP=6000;m.SECONDS=900
m.COMMIT='93c9246970865d0fe48a85e2b564ad62ca837947';m.infra.ROOT=ROOT;m.infra.SERVICE_PORT=m.PORT
TASKS=('random-acts-of-pizza','spooky-author-identification')

def schedule():
    order=['uniform','contrast'];random.Random(20261003).shuffle(order)
    rows=[]
    for block in range(2):
        for arm in (order if block==0 else order[::-1]):
            for task,name in enumerate(TASKS):
                rows.append(dict(index=len(rows),start=task,task=name,arm=arm,seed=103501+10*block+task,
                                 wave=len(rows)//2,retained=True,visible=True))
    return rows
m.schedule=schedule;d.schedule=schedule

COMMON='''Improve the supplied ML task program in an ordinary persistent coding workspace.
Use actual observations to choose any justified improvement; no mandatory diagnosis,
feature engineering, error correction or model family is prescribed. A historical
strong development incumbent is the start, not a fresh random baseline. Keeping it
is allowed. Known ordinary references include word/character TFIDF linear models,
numeric boosting, Naive Bayes, blending and consistent train-fitted transforms.
They are available baselines, not new discoveries.
Six model calls maximum within 900 TOTAL seconds, including initial execution,
generation, tools, rollback/reconstruction and external development grading.
Respond with one standalone CHECK or SOLUTION line, brief rationale, and exactly one
fenced python block. The final call must be SOLUTION. CHECK prints evidence without
grading. SOLUTION must write a NEW submission.csv (the old file is removed first).
Successful cells remain live even if worse; the evaluator separately retains the
best valid submission. Failed/timed-out cells are rolled back; next action replays
only successful code. Both arms receive all future tool output and development
scores and may freely inspect any PUBLIC training data, models, features or OOF.
You may reuse existing variables or run a full program. The initial public example
packet is merely an observation, not a prescription, causal explanation or final
evaluation. Its row indices must not become rules for identifying future inputs.
Use /workspace/data and your workspace only. Hidden labels are unavailable. No
downloads or dependencies. Six CPU cores and one RTX3090; each code call <=300s,
also limited by remaining total time. Original program: /workspace/parent.py.
'''

def prompt(task,s,step,ledger,history,remaining):
    last='FINAL CALL: SOLUTION required.' if step==6 else 'Choose CHECK or SOLUTION.'
    return COMMON+'\n'+last+'\nTASK:\n'+task+'\nSUCCESSFUL CODE LEDGER:\n'+'\n\n'.join(f'CELL {i}:\n{c}' for i,c in enumerate(ledger))+'\nOBSERVED HISTORY:\n'+history+f'\nTOTAL SECONDS REMAINING: {int(remaining)}\n'

def decode(raw,step):
    if m.SECRET.search(raw.encode()): raise ValueError('credential-shaped output')
    parts=re.findall(r'```python\s*\n(.*?)```',raw,re.S)
    if len(parts)!=1 or raw.count('```')!=2: raise ValueError('one Python block')
    outside=re.sub(r'```python\s*\n.*?```','',raw,flags=re.S)
    modes=re.findall(r'^\s*(CHECK|SOLUTION)\s*$',outside,re.M)
    if len(modes)!=1 or (step==6 and modes[0]!='SOLUTION'): raise ValueError('unique action mode')
    ast.parse(parts[0]);return modes[0],parts[0],outside.strip()
d.prompt=prompt;d.decode=decode

def evidence_code(s):
    source=(ROOT/'public_error_examples_20261003.py').read_text()
    return '\n'+source+f'\nfrom_namespace(globals(),{s["task"]!r},{s["seed"]!r},{s["arm"]!r})\n'

def record_packet(action,terminal):
    prefix='PUBLIC_EXAMPLE_PACKET '
    lines=[line for line in terminal.splitlines() if line.startswith(prefix)]
    if len(lines)!=1: raise ValueError('missing/ambiguous public packet')
    obj=json.loads(lines[0][len(prefix):]);shown=obj['shown'];meta=obj['metadata']
    if hashlib.sha256(json.dumps(shown,sort_keys=True,ensure_ascii=False).encode()).hexdigest()!=meta['shown_sha256']: raise ValueError('packet hash')
    if len(shown['examples'])!=12: raise ValueError('packet size')
    m.write(action/'public-packet.private.json',obj)
    # Remove sampling metadata from the model observation; both get the same schema.
    return terminal.replace(lines[0], 'PUBLIC TRAINING EXAMPLES\n'+json.dumps(shown,sort_keys=True,ensure_ascii=False))
d.evidence_code=evidence_code;d.record_packet=record_packet

# Reuse the proven closed-loop executor, with explicit counted replacements.
src=inspect.getsource(d.episode)
changes=[('range(5)','range(7)'),
 ('began=time.monotonic();out=execute(interp,wrapper(code,s[\'seed\']),',
  "executed=code+evidence_code(s) if step==0 else code\n            m.write(action/'executed.json',dict(code_sha256=hashlib.sha256(executed.encode()).hexdigest()))\n            began=time.monotonic();out=execute(interp,wrapper(executed,s['seed']),"),
 ("if m.SECRET.search(terminal.encode()):raise ValueError('credential terminal')",
  "if m.SECRET.search(terminal.encode()):raise ValueError('credential terminal')\n            if step==0 and ok:terminal=record_packet(action,terminal)"),
 ("terminal[-12000:] if step>0 or s['visible']", "terminal[-18000:] if step>0 or s['visible']")]
for old,new in changes:
    assert src.count(old)==1,(old,src.count(old));src=src.replace(old,new)
exec(compile(src,'public_example_episode','exec'),d.__dict__)
m.episode=d.episode;episode=d.episode;execute=d.execute

base=(PARENT/'v6_runtime.py').read_text()
for name,changes in {
 'worker':[("TIME_LIMIT='30 minutes'","TIME_LIMIT='15 minutes'"),("STEP_LIMIT='5'","STEP_LIMIT='7'")],
 'task_runtime':[("action-[0-4]","action-[0-6]")],
 'controller':[('03:39:00','01:39:00'),('00:33:00','00:18:00'),('for wave in range(6):','for wave in range(4):'),('max_workers=3','max_workers=2'),('dict(attempts=18,','dict(attempts=8,')]
}.items():
    node=next(n for n in ast.parse(base).body if isinstance(n,ast.FunctionDef) and n.name==name)
    src=ast.get_source_segment(base,node)
    for old,new in changes:
        assert src.count(old)==1,(name,old);src=src.replace(old,new)
    exec(compile(src,'public_example_'+name,'exec'),m.__dict__)

def prepare():
    if ROOT.exists(): raise FileExistsError(ROOT)
    p=m.read(PARENT/'plan.json')
    assert m.sha(PARENT/'plan.json')=='2820d6cc64d9d1045179f2290383340c38605b6ba604364d8fd6307be2a0b237'
    ROOT.mkdir(mode=0o700)
    for rel,h in p['files'].items():
        if not (rel.startswith(('source/','forets_','opencl-vendors/','starts/')) or rel in ('root_trial_step_supervisor_20260927.py','v6_runtime.py')):continue
        assert m.sha(PARENT/rel)==h,rel
        dst=ROOT/rel;dst.parent.mkdir(exist_ok=True,parents=True);shutil.copyfile(PARENT/rel,dst)
    shutil.copyfile(engine,ROOT/'factorial_engine.py');shutil.copyfile(__file__,ROOT/'task_feedback_real_20261001.py')
    shutil.copyfile(Path(__file__).parent/'public_error_examples_20261003.py',ROOT/'public_error_examples_20261003.py')
    for rel in ('configs','bin','service-cache/tmp'):(ROOT/rel).mkdir(exist_ok=True,parents=True)
    (ROOT/'bin/singularity').write_text((PARENT/'bin/singularity').read_text().replace(str(PARENT),str(ROOT)));os.chmod(ROOT/'bin/singularity',0o700)
    entry=(PARENT/'service_entry.py').read_text();assert entry.count("'19447'")==1
    (ROOT/'service_entry.py').write_text(entry.replace("'19447'","'19449'"))
    with (ROOT/'.service.env').open('x') as f:f.write('PRIMARY_KEY_QWEN3_8_27B='+secrets.token_hex(32)+'\n')
    os.chmod(ROOT/'.service.env',0o600)
    for s in schedule():
        cfg=m.read(PARENT/'configs'/f'{s["start"]}.json');ep=ROOT/f'episode-{s["index"]}';ep.mkdir()
        cfg['id']=f'public-examples-{s["index"]}';cfg['logger']['output_dir']=str(ep/'native-log')
        cfg['metadata'].update(seed=s['seed'],script_id='public-example-feedback-20261003',base_path=str(ROOT/'source'),git_commit_id=m.COMMIT)
        cfg['solver'].update(time_limit_secs=900,step_limit=7,checkpoint_path=str(ep/'unused-checkpoint'))
        cfg['interpreter']['working_dir']=str(ep/'unused-work');cfg['interpreter']['env']['PYTHONHASHSEED']=str(s['seed'])
        cfg['task']['cache_dir']=str(ROOT/'no-official-data')
        for op in cfg['solver']['operators'].values():
            op['llm']['client']['base_url']=f'http://127.0.0.1:{m.PORT}/v1';op['llm']['generation_kwargs']['seed']=s['seed']
        m.write(ROOT/'configs'/f'{s["index"]}.json',cfg)
    batch=(PARENT/'run.sbatch').read_text().replace(str(PARENT),str(ROOT)).replace('state-feedback-factorial','public-example-feedback').replace('02:15:00','01:40:00').replace('8040s','5940s')
    (ROOT/'run.sbatch').write_text(batch)
    files={str(f.relative_to(ROOT)):m.sha(f) for f in ROOT.rglob('*') if f.is_file() and f.name!='.service.env'}
    plan=dict(protocol='public-example-feedback-v1',utc=m.utc(),base_commit=m.COMMIT,files=files,starts=p['starts'],schedule=schedule(),run_seconds=900,allocation_seconds=6000,gpu_hours_cap=4*6000/3600,gpus=4,max_calls=6,max_tokens_per_call=4096,execution_cap=300,paid_api=0,agent_training=False,protected_opened=False,
        treatment='12 public OOF examples: class-balanced uniform vs per-class equal samples from lower/upper loss quartiles; all future tools/evidence freely available in both arms',
        primary='paired oriented incumbent gain contrast minus uniform, every assigned run, separately by task; initial score and deterministic evidence prediction hashes must agree within pair',
        gate='all four paired starts valid/comparable; median contrast-minus-uniform >0 in BOTH tasks, no seed negative, and at least one better new valid candidate in each task; mechanism traces independently inspected',
        common_changes='ordinary retained workspace in both; 900s/6 calls; unique standalone mode accepted anywhere outside one code block; no retrospective rescue of old failures',
        limitations='two combined run seeds and one historical development-selected incumbent/task; public OOF used for earlier selection; Spooky diagnostic uses TFIDF component, not stochastic embedding; not final generalization or novelty confirmation; prompt token lengths may differ but examples/text cap same')
    m.write(ROOT/'plan.json',plan);print(json.dumps(dict(status='PREPARED',plan_sha256=m.sha(ROOT/'plan.json'),runs=8,gpu_hours_cap=plan['gpu_hours_cap'])))

def submit():
    p=m.check()
    if (ROOT/'submit-intent.json').exists(): raise ValueError('already attempted submit; inspect not retry')
    for name in ('cpu.json','transport-cpu.json'):
        r=m.read(ROOT/name);assert r['status']=='PASS' and r['plan_sha256']==m.sha(ROOT/'plan.json')
    assert m.sha(m.infra.TASK_IMAGE)==m.infra.IMAGE_SHA and m.sha(m.ASSETS/'vllm.sif')==m.infra.VLLM_SHA
    for r in m.read(m.ASSETS/'complete.json')['files']:
        if r['path'].endswith('.safetensors'):assert m.sha(m.ASSETS/r['path'])==r['digest']
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    jobs=subprocess.check_output(['squeue','-u','yzyang4','-h','-o','%i'],env=env,text=True,timeout=20).split();assert not set(jobs)-{'12535'}
    with (ROOT/'capacity.tmp').open('xb') as f:os.posix_fallocate(f.fileno(),0,512*1024**2)
    (ROOT/'capacity.tmp').unlink()
    m.write(ROOT/'submit-intent.json',dict(utc=m.utc(),plan_sha256=m.sha(ROOT/'plan.json')))
    r=subprocess.run(['sbatch','--parsable','--chdir='+str(ROOT),'--output='+str(ROOT/'allocation-%j.out'),'--error='+str(ROOT/'allocation-%j.err'),str(ROOT/'run.sbatch')],env=env,text=True,capture_output=True,timeout=25)
    job=r.stdout.strip().split(';')[0]
    if r.returncode or not job.isdigit():raise RuntimeError('ambiguous submission; no retry')
    m.write(ROOT/'launch.json',dict(job=job,utc=m.utc(),plan_sha256=m.sha(ROOT/'plan.json')));print(json.dumps(dict(status='SUBMITTED',job=job,gpu_hours_cap=p['gpu_hours_cap'])))

if __name__=='__main__':
    os.umask(0o077);a=argparse.ArgumentParser();a.add_argument('mode',choices=['prepare','submit','check','worker','controller','service']);a.add_argument('--index',type=int);x=a.parse_args()
    if x.mode in ('prepare','submit'):globals()[x.mode]()
    elif x.mode=='worker':m.worker(x.index)
    elif x.mode=='check':m.check();print('FROZEN_PLAN_VALID')
    else:getattr(m,x.mode)()
