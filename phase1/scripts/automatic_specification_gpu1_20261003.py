"""Fresh-root, bounded automatic-specification qualification; not novelty proof.

Prepare and CPU tests do not submit or call a model. Submission requires the
current plan's explicit eight-GPU-hour approval receipt. No old scores are used
to choose roots, edits or prompts. The first valid fresh-root program is frozen.
"""
import argparse, ast, hashlib, importlib.util, json, os, random, re, secrets, shutil, subprocess, sys
from pathlib import Path

B=Path('/research/d7/spc/yzyang4')
P=B/'opportunity-information-20261003-v2'
R=B/'automatic-specification-20261003-gpu1-v2'
ENGINE_SHA='57b45de1d7afc9f9657c3667c583537db94cda9ee527d5999fe15fc23bb6397d'
PRIOR_PLAN='6b91aba97ee53f6da2335064f1dbe4277020b8744fd95a3575e4c99329936d2f'
COMMIT='9edd4998a3098353c717a21abcbcc069376548aa'
engine=R/'factorial_engine.py' if (R/'factorial_engine.py').exists() else P/'factorial_engine.py'
assert hashlib.sha256(engine.read_bytes()).hexdigest()==ENGINE_SHA
sp=importlib.util.spec_from_file_location('automatic_specification_base',engine)
d=importlib.util.module_from_spec(sp);sys.modules[sp.name]=d;sp.loader.exec_module(d)
m=d.m;d.ROOT=R;m.ROOT=R;m.PORT=19455;m.CAP=7200;m.SECONDS=600;m.COMMIT=COMMIT
m.infra.ROOT=R;m.infra.SERVICE_PORT=m.PORT
TASKS=('random-acts-of-pizza','spooky-author-identification')
RULES='''Known ML reference checklist (not new discoveries):
1. Use task-appropriate training objective and validation metric.
2. When a validation fold already exists, consider supported early stopping.
3. Choose an existing model or blend using public CV, not arbitrary weights.
4. Fit preprocessing on training data and reuse the same fitted transform.
5. Consider standard word/character TFIDF views for text and regularized linear
   models or numerical boosting, when an existing public comparison supports it.
No checklist item guarantees an external gain; preserving the program is allowed.
'''
COMMON='''Work in an ordinary persistent ML coding workspace. All conditions have
the same tools and may inspect public evidence, preserve state or fit new models.
FOUR model calls and 600 TOTAL seconds include initial execution, planning,
generation, tools, failed attempts, reconstruction and grading. A code call is
at most 300 seconds and also bounded by remaining time. One RTX3090, six CPUs.
Respond using exactly one standalone mode line: PLAN, CHECK or SOLUTION.
PLAN has no code fence: provide a concise proposed change with evidence, target,
what to preserve, and a check. It consumes a model call/time but executes nothing.
CHECK or SOLUTION has a short rationale and exactly one fenced python block.
CHECK inspects evidence without grading. SOLUTION writes a NEW submission.csv.
The final call must be SOLUTION. Successful cells remain live. Failed cells roll
back to the successful ledger and reconstruction costs budget. The evaluator
separately retains the best valid submission. No forced rewrite or new model.
Use only /workspace/data and your workspace; no downloads or hidden labels.
The original program is /workspace/parent.py. External scores are DEVELOPMENT
observations, not final test. Lower log-loss is better; higher AUC is better.
'''+RULES

def schedule():
    rows=[dict(index=k,start=k,task=t,role='root',arm='ROOT',seed=104401+k,wave=0,retained=True,visible=True) for k,t in enumerate(TASKS)]
    order=list('ABC');random.Random(104400).shuffle(order)
    for block in range(2):
        for j,arm in enumerate(order if block==0 else order[::-1]):
            for k,t in enumerate(TASKS):
                rows.append(dict(index=len(rows),start=k,task=t,role='comparison',arm=arm,seed=104501+10*block+k,wave=1+3*block+j,retained=True,visible=True))
    return rows
m.schedule=schedule;d.schedule=schedule

def prompt(task,s,step,ledger,history,remaining):
    if s['role']=='root':
        note='No solution exists yet. Produce a good valid ML solution for the task, using the permitted resources. You may inspect data or debug. Collection stops at the FIRST valid submission, without score ranking.'
    elif s['arm']=='A':
        note='Choose useful next work freely: PLAN, CHECK or SOLUTION. Planning is optional.'
    elif s['arm']=='B':
        note='On call 1, use PLAN only. Derive ONE concrete modification specification from the actual code and observations. Separate observed evidence from a hypothesis; name exact existing variables/components, the intended behavioral change, and non-target behavior to preserve. Prefer the smallest justified change, but no fixed edit type is prescribed. A hypothesis is not proof of better prediction. On later calls implement or test your own plan; revise only in light of actual new observations, explaining why. No human target or answer is provided.'
    else:
        note='On call 1, use PLAN only. Select ONE applicable item from the known ML reference checklist above using actual code and observations; name its existing variables/components, the exact change and what to preserve. On later calls implement or test this checklist-based plan. If no item is supported, inspect evidence or retain the program. Remain within the checklist rather than invent a new model family. No human task-specific target is provided.'
    final='Final call: SOLUTION.' if step==4 else 'Use the permitted next action.'
    return COMMON+'\n'+note+'\n'+final+'\nTASK:\n'+task+'\nSUCCESSFUL CODE LEDGER:\n'+'\n\n'.join(f'CELL {i}:\n{c}' for i,c in enumerate(ledger))+'\nOBSERVED HISTORY:\n'+history+f'\nTOTAL SECONDS REMAINING: {int(remaining)}\n'
d.prompt=prompt

def decode(raw,step):
    assert not m.SECRET.search(raw.encode())
    before=raw.split('```',1)[0];modes=re.findall(r'(?m)^\s*(PLAN|CHECK|SOLUTION)\s*$',before)
    if len(modes)!=1 or (step==4 and modes[0]!='SOLUTION'):raise ValueError('action mode')
    if modes[0]=='PLAN':
        if '```' in raw or len(raw.strip())<20:raise ValueError('invalid plan')
        return 'PLAN','',raw
    parts=re.findall(r'```python\s*\n(.*?)```',raw,re.S)
    if len(parts)!=1 or raw.count('```')!=2:raise ValueError('code format')
    ast.parse(parts[0]);return modes[0],parts[0],before
d.decode=decode

def wrapper(code,seed,remove_submission=True):
    return ('import random as _r, numpy as _n\n_r.seed(42)\n_n.random.seed(42)\n'
        +("from pathlib import Path as _P\n_P('submission.csv').unlink(missing_ok=True)\n" if remove_submission else '')
        +f'globals()["__name__"]="__main__"\nexec(compile({code!r},"cell.py","exec"))\n')
d.wrapper=wrapper

def freeze_roots():
    records=[]
    for k in range(2):
        ep=R/f'episode-{k}';fp=ep/'first-valid.json'
        if not fp.exists():
            m.write(R/'roots-unavailable.json',dict(status='STOP_NO_REPLACEMENT',missing_root=k,utc=m.utc()))
            return False
        rec=m.read(fp);program=m.read(ep/'seed-program.private.json')
        assert hashlib.sha256(program['code'].encode()).hexdigest()==rec['code_sha256']
        ast.parse(program['code']);m.write(R/'starts'/f'{k}.private.json',program)
        records.append(dict(start=k,root_index=k,first_valid_step=rec['step'],code_sha256=rec['code_sha256'],source_sha256=m.sha(ep/'seed-program.private.json')))
    m.write(R/'roots-ready.json',dict(status='FIRST_VALID_SOURCES_FROZEN',starts=records,utc=m.utc(),selection='first valid, not best score; availability gate only, no gain qualification'))
    return True
m.freeze_roots=freeze_roots

# Minimal future-only modifications to the already tested persistent loop.
source=engine.read_text();tree=ast.parse(source)
node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='episode')
body=ast.get_source_segment(source,node)
changes=[
 ("parent=m.read(ROOT/'starts'/f'{s[\"start\"]}.private.json')['code']", "parent='pass' if s['role']=='root' else m.read(ROOT/'starts'/f'{s[\"start\"]}.private.json')['code']\n    if s['role']!='root':\n        frozen=next(x for x in m.read(ROOT/'roots-ready.json')['starts'] if x['start']==s['start'])\n        assert hashlib.sha256(parent.encode()).hexdigest()==frozen['code_sha256']"),
 ('for step in range(5):\n            deadline.check();', "for step in range(5):\n            if step==0 and s['role']=='root':continue\n            deadline.check();"),
 ('try:mode,code,reason=decode(raw,step)', "try:\n                    mode,code,reason=decode(raw,step)\n                    if step==1 and s['role']=='comparison' and s['arm'] in ('B','C') and mode!='PLAN':raise ValueError('first call must plan')"),
 ("            if interp is not None and not s['retained']:", "            if mode=='PLAN':\n                m.write(action/'plan.private.json',dict(text=reason,elapsed_seconds=deadline.elapsed()))\n                history+='\\nAUTOMATIC PLAN (unexecuted, not verified):\\n'+reason\n                continue\n            if interp is not None and not s['retained']:"),
 ("            if improved:m.write(action/'selected.json',dict(step=step,metric=best,elapsed=deadline.elapsed()))", "            if improved:m.write(action/'selected.json',dict(step=step,metric=best,elapsed=deadline.elapsed()))\n            if s['role']=='root' and valid:\n                frozen_code='\\n\\n'.join(wrapper(c,42) for c in ledger)\n                m.write(ep/'seed-program.private.json',dict(code=frozen_code))\n                m.write(ep/'first-valid.json',dict(step=step,code_sha256=hashlib.sha256(frozen_code.encode()).hexdigest(),utc=m.utc()))\n                break"),
]
for old,new in changes:assert body.count(old)==1,old;body=body.replace(old,new)
exec(compile(body,'automatic_specification_episode','exec'),d.__dict__);m.episode=d.episode
source=Path(m.__file__).read_text();tree=ast.parse(source)
for name,changes in {
 'worker':[("TIME_LIMIT='30 minutes'","TIME_LIMIT='10 minutes'")],
 'service':[("!='gpu28'","!='gpu1'")],
 'controller':[("!='gpu28'","!='gpu1'"),
     ("        try:\n            while time.monotonic()-began<900:", "        try:\n            subprocess.run(base+['--cpus-per-task=6','--gres=gpu:1','--time=00:02:00',str(PY),'-B',str(ROOT/'task_feedback_real_20261001.py'),'compat'],env=env,check=True,timeout=120)\n            while time.monotonic()-began<900:"),('03:39:00','01:59:00'),('00:33:00','00:13:00'),('for wave in range(6):','for wave in range(7):'),('max_workers=3','max_workers=2'),('dict(attempts=18,','dict(attempts=14,'),
     ("                write(ROOT/f'wave-{wave}.json',dict(indices=done,utc=utc()))", "                write(ROOT/f'wave-{wave}.json',dict(indices=done,utc=utc()))\n                if wave==0 and not freeze_roots():return")]
}.items():
    node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name);body=ast.get_source_segment(source,node)
    for old,new in changes:assert body.count(old)==1,old;body=body.replace(old,new)
    exec(compile(body,'automatic_specification_'+name,'exec'),m.__dict__)

def compatibility():
    from forets_gpu_binding_20260911 import rewrite
    from forets_native_gpu_binding_20260911 import native_identity,resolve_native
    from forets_opencl_allowlist_20260911 import driver_binds
    import socket
    assert socket.gethostname().split('.')[0]=='gpu1'
    uid=m.infra.native_uuids(1)[0];minor,observed=resolve_native(native_identity());assert observed==uid
    work=R/'compat-work';work.mkdir()
    code="import json,torch; assert torch.cuda.is_available() and torch.cuda.device_count()==1; a=torch.ones((32,32),device='cuda'); b=a@a; torch.cuda.synchronize(); assert b.sum().item()==32768; print('COMPAT '+json.dumps(dict(torch=torch.__version__,cuda=torch.version.cuda,name=torch.cuda.get_device_name(0),capability=torch.cuda.get_device_capability(0),matmul=True)))"
    args=['exec','--containall','--cleanenv','--no-home','--nv','--bind',str(work)+':/workspace:rw','--pwd','/workspace',str(m.infra.TASK_IMAGE),'env','HOME=/workspace/.home','python','-c',code]
    libs=driver_binds(subprocess.check_output(['/sbin/ldconfig','-p'],text=True,timeout=10))
    final,gate=rewrite(args,minor=minor,uuid=uid,libraries=libs,vendors=R/'opencl-vendors')
    env={k:os.environ[k] for k in ('PATH','HOME','USER','LOGNAME') if k in os.environ}
    check=subprocess.run(gate,env=env,capture_output=True,text=True,timeout=30)
    gates=[json.loads(v.removeprefix('ALLOWLIST_GATE ')) for v in check.stdout.splitlines() if v.startswith('ALLOWLIST_GATE ')]
    assert check.returncode==0 and len(gates)==1 and gates[0]['exact_device_namespace']
    result=subprocess.run(final,env=env,capture_output=True,text=True,timeout=60)
    records=[json.loads(v.removeprefix('COMPAT ')) for v in result.stdout.splitlines() if v.startswith('COMPAT ')]
    if result.returncode or len(records)!=1:
        m.write(R/'compatibility-failed.json',dict(returncode=result.returncode,output_sha256=hashlib.sha256((result.stdout+result.stderr).encode()).hexdigest()));raise RuntimeError('task image GPU computation failed')
    assert records[0]['name']=='NVIDIA GeForce RTX 3090' and records[0]['capability']==[8,6]
    m.write(R/'compatibility.json',dict(status='PASS',node='gpu1',job=os.environ['SLURM_JOB_ID'],step=os.environ['SLURM_STEP_ID'],gpu_uuid=uid,image_sha256=m.infra.IMAGE_SHA,namespace=gates[0],compute=records[0],utc=m.utc()))

def prepare():
    assert not R.exists() and m.sha(P/'plan.json')==PRIOR_PLAN
    R.mkdir(mode=0o700)
    for rel,h in m.read(P/'plan.json')['files'].items():
        if not(rel.startswith(('source/','forets_','opencl-vendors/')) or rel in ('v6_runtime.py','root_trial_step_supervisor_20260927.py')):continue
        assert m.sha(P/rel)==h;q=R/rel;q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(P/rel,q)
    shutil.copyfile(engine,R/'factorial_engine.py');shutil.copyfile(__file__,R/'task_feedback_real_20261001.py')
    for n in ('configs','starts','bin','service-cache/tmp'):(R/n).mkdir(parents=True,exist_ok=True)
    entry=(P/'service_entry.py').read_text();assert entry.count("'19453'")==1;(R/'service_entry.py').write_text(entry.replace("'19453'","'19455'"))
    with (R/'.service.env').open('x') as f:f.write('PRIMARY_KEY_QWEN3_8_27B='+secrets.token_hex(32)+'\n')
    os.chmod(R/'.service.env',0o600)
    (R/'bin/singularity').write_text(f'#!{m.PY}\nimport sys\nsys.path.insert(0,{str(R)!r})\nfrom task_feedback_real_20261001 import m\nm.task_runtime()\n');os.chmod(R/'bin/singularity',0o700)
    for s in schedule():
        cfg=m.read(P/'configs'/f'{s["start"]}.json');ep=R/f'episode-{s["index"]}';ep.mkdir()
        cfg['id']=f'automatic-specification-{s["index"]}';cfg['logger'].update(output_dir=str(ep/'native-log'),write_env_vars=False,use_wandb=False,print_config=False,use_console=False)
        cfg['metadata'].update(seed=s['seed'],script_id='automatic-specification-20261003',base_path=str(R/'source'),git_commit_id=COMMIT)
        cfg['solver'].update(root_failure_randomization=False,acquisition_first_slot=False,record_slate_hashes=False,use_test_score=False,time_limit_secs=600,step_limit=5,checkpoint_path=str(ep/'unused-checkpoint'))
        cfg['interpreter']['working_dir']=str(ep/'unused-work');cfg['interpreter']['timeout']=300
        cfg['interpreter']['env'].update(PYTHONHASHSEED='42',OMP_NUM_THREADS='6',OPENBLAS_NUM_THREADS='6',MKL_NUM_THREADS='6',NUMEXPR_NUM_THREADS='6');cfg['task']['cache_dir']=str(R/'no-official-data')
        for op in cfg['solver']['operators'].values():
            op['llm']['client']['base_url']=f'http://127.0.0.1:{m.PORT}/v1'
            op['llm']['generation_kwargs'].update(max_tokens=4096,seed=s['seed'],bounded_request_timeout_seconds=180,bounded_transport=True,bounded_max_attempts=1,structured_output_retries=0,extra_body={'chat_template_kwargs':{'enable_thinking':False}})
        m.write(R/'configs'/f'{s["index"]}.json',cfg)
    batch=(P/'run.sbatch').read_text().replace(str(P),str(R)).replace('opportunity-information','automatic-specification').replace('01:30:00','02:00:00').replace('5340s','7140s').replace('--nodelist=gpu28','--nodelist=gpu1');(R/'run.sbatch').write_text(batch)
    m.write(R/'plan.json',dict(protocol='fresh-root-automatic-specification-gpu1-v2',prior_plan_sha256='2d898d1cdf9751cd505a3b11af91cf0032be8af2f81a73cc1ae1e9a125259a15',migration='gpu28 queue unavailable until October 6; common host gpu1, same RTX3090 count/task image/software/treatments/seeds/budgets. GPU compatibility warmup included in allocation; old pending allocation must be cancelled without execution.',base_commit=COMMIT,utc=m.utc(),schedule=schedule(),files={str(q.relative_to(R)):m.sha(q) for q in R.rglob('*') if q.is_file() and q.name!='.service.env'},
        run_seconds=600,allocation_seconds=7200,gpus=4,gpu_hours_cap=8,root_runs=2,comparison_runs=12,max_calls=4,max_tokens=4096,code_seconds=300,paid_api=0,base_updates=0,
        treatment='A ordinary unrestricted same-tool agent; B mandatory automatic open-ended change specification on call1; C mandatory checklist-guided change specification on call1. PLAN is available to all. Planning costs one of four calls and measured time; only scheduling/advice differs.',
        selection='Two fresh root trajectories; freeze the first valid successful-cell ledger, never score-rank or manually patch. If either unavailable, do not start comparisons. Root availability is not witnessed gain qualification. No prior successful Spooky/Pizza code or human task-specific hint is inserted.',
        primary='All twelve assigned comparisons. Per task/paired generation seed oriented retained gain, B-A and B-C. Invalid initial or mismatched initial predictions => incomparable, not zero. Failure after valid initial retains parent.',
        gate='Exploratory continuation only if all four seed/task triples comparable, both tasks median B-A and B-C >0, neither contrast negative in any paired seed, and B has actual new valid improvements with code-grounded plan implementation. A gain that only rediscovers checklist rules is not a new-method claim.',
        cost='All root acquisition, initialization, planning, generation, execution, failures, replay, scoring, service startup and idle allocation included. Root cost shared experimental infrastructure: compare conditional continuation, not full-search e2e or free root acquisition.',
        limitations='Two new source programs but same previously used developer data and frozen task subset; two generation seeds and fixed wrapper RNG42, explicit program seeds may override. Not untouched confirmation. C is checklist-guided agent, not optimal automated rule implementation. Generic plan-first and specification repair have strong prior work; no novelty claim.',
        protected_opened=False))
    m.check();m.setup();subprocess.run(['bash','-n',str(R/'run.sbatch')],check=True)
    print(json.dumps(dict(status='PREPARED_NOT_SUBMITTED',plan_sha256=m.sha(R/'plan.json'),root_runs=2,comparison_runs=12,gpu_hours_cap=8)))

def submit():
    m.check();approval=m.read(R/'budget-approval.json')
    assert approval['approved'] is True and approval['gpu_hours_cap']==8 and approval['plan_sha256']==m.sha(R/'plan.json')
    assert m.read(R/'transport-loop-cpu.json')['status']=='PASS' and m.read(R/'transport-loop-cpu.json')['plan_sha256']==m.sha(R/'plan.json')
    assert m.sha(m.infra.TASK_IMAGE)==m.infra.IMAGE_SHA and m.sha(m.ASSETS/'vllm.sif')==m.infra.VLLM_SHA
    for a in m.read(m.ASSETS/'complete.json')['files']:
        if a['path'].endswith('.safetensors'):assert m.sha(m.ASSETS/a['path'])==a['digest']
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf');jobs=subprocess.check_output(['squeue','-u','yzyang4','-h','-o','%i'],env=env,text=True,timeout=25).split();assert not set(jobs)-{'12535'}
    with (R/'capacity.tmp').open('xb') as f:os.posix_fallocate(f.fileno(),0,512*1024**2)
    (R/'capacity.tmp').unlink()
    m.write(R/'submit-intent.json',dict(utc=m.utc(),plan_sha256=m.sha(R/'plan.json')))
    r=subprocess.run(['sbatch','--parsable','--chdir='+str(R),'--output='+str(R/'allocation-%j.out'),'--error='+str(R/'allocation-%j.err'),str(R/'run.sbatch')],env=env,capture_output=True,text=True,timeout=25)
    job=r.stdout.strip().split(';')[0];assert r.returncode==0 and job.isdigit(),'ambiguous: do not retry blindly'
    m.write(R/'launch.json',dict(job=job,utc=m.utc(),plan_sha256=m.sha(R/'plan.json')));print(json.dumps(dict(job=job,status='SUBMITTED',gpu_hours_cap=8)))

if __name__=='__main__':
    os.umask(0o077);a=argparse.ArgumentParser();a.add_argument('mode',choices=['prepare','submit','check','worker','controller','service','compat']);a.add_argument('--index',type=int);x=a.parse_args()
    if x.mode in ('prepare','submit'):globals()[x.mode]()
    elif x.mode=='check':m.check();print('FROZEN_PLAN_VALID')
    elif x.mode=='compat':compatibility()
    elif x.mode=='worker':m.worker(x.index)
    else:getattr(m,x.mode)()
