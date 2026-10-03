"""Bounded hypothesis-check policy qualification, not a new-method claim.

Reuse qualified developer states and the frozen AIRA persistent-cell runner.
The only randomized arm difference is the investigation policy in the prompt.
No task-specific repair hint, new root selection, paid API or base training.
"""
import argparse, ast, hashlib, importlib.util, json, os, secrets, shutil, subprocess, sys
from pathlib import Path

B=Path('/research/d7/spc/yzyang4')
P=B/'opportunity-information-20261003-v2'
R=B/'executable-evidence-20261004-v1'
COMMIT='9cdc4cc897b906e4e38e0653bb58a1503121e0c7'
DONOR_SHA='c8d67b9cce9109425324f5877797ad0448ec5f97beb89572383dce3fa1697448'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
donor=P/'task_feedback_real_20261001.py'
assert sha(donor)==DONOR_SHA
spec=importlib.util.spec_from_file_location('frozen_information_donor',donor)
x=importlib.util.module_from_spec(spec);sys.modules[spec.name]=x;spec.loader.exec_module(x)
d=x.d;m=x.m
d.ROOT=R;m.ROOT=R;m.PORT=19461;m.CAP=9000;m.SECONDS=720;m.COMMIT=COMMIT
m.infra.ROOT=R;m.infra.SERVICE_PORT=m.PORT
TASKS=x.TASKS

def schedule():
    # Latin rotation: each policy occurs first/middle/last exactly once per task.
    rows=[]
    for block,order in enumerate(('BCA','CAB','ABC')):
        for arm in order:
            for k,task in enumerate(TASKS):
                rows.append(dict(index=len(rows),start=k,source_state=(4,0)[k],task=task,arm=arm,seed=106101+10*block+k,wave=len(rows)//2,retained=True,visible=True))
    return rows
m.schedule=schedule;d.schedule=schedule

COMMON='''Improve this working natural ML program in a persistent coding workspace.
All arms have the same code, observed history, tools, public data and model.
SIX model calls and 720 TOTAL seconds include initial execution, generation,
checks, fitting, failures, reconstruction and grading. Each code call is at most
300 seconds and bounded by remaining time. One RTX3090 and six CPU cores.
Use exactly one standalone CHECK or SOLUTION line, brief rationale, then exactly
one fenced python block. CHECK executes code to gather evidence, without grading.
SOLUTION writes a NEW submission.csv. No PLAN action or native tool-call XML.
The final call must be SOLUTION. Successful cells stay live; failed cells roll
back to the successful ledger and reconstruction consumes the same budget.
The evaluator retains the best valid submission; retaining it is allowed.
Use only /workspace/data and your workspace. No downloads or hidden labels.
The original program is /workspace/parent.py. Lower log-loss is better, higher
AUC is better. External scores are DEVELOPMENT observations, not final test.
Known ordinary references available to EVERY arm: word/character TFIDF,
regularized linear models, numerical boosting, train-only transformations,
task-appropriate objectives, public CV selection, early stopping and blending.
These are possible tools, not guaranteed improvements. Do not claim a file,
variable, fitted state or quality improvement exists without checking evidence.
'''
NOTES={
 'A':'Choose the most useful next action freely: inspect, test, reuse, modify or fit. No mandatory diagnostic stage. Optimize the retained submission within the total budget.',
 'B':'On this first call use CHECK. Select ONE consequential, uncertain premise of the current program whose being false would change your next edit. State the premise and what opposite observations would imply. Execute the cheapest public-data or fitted-state test capable of DISCONFIRMING it, printing actual evidence. Do not merely print a planned fix, inspect arbitrary summaries, or assume the premise is false. No task-specific issue or answer is supplied.',
 'C':'On this first call use CHECK. Run a cheap standard ML audit of the current program: identify actual training/query files and compatible schema; inspect available public-validation results, objective/metric alignment, train-only preprocessing, fit/early-stopping settings, and consistency between public model comparison and final predictions. Use available code and live fitted objects; avoid expensive new fitting. Print evidence and flag only supported issues. This is a known-checklist baseline, not a new discovery.',
}
FOLLOW={
 'B':'The first-call check phase is OVER. Read its returned evidence. Explicitly state whether your tested premise was supported, contradicted, or left unresolved; do not assume the test succeeded. Now use that evidence for a concrete justified modification and valid submission, or retain the program. More checking is allowed but costs remaining calls/time. No repeating the first-call instruction as if this were call1.',
 'C':'The first-call check phase is OVER. Read its returned evidence. Implement a supported ordinary ML correction and produce a valid submission, or retain the program. More checking is allowed but costs remaining calls/time. Do not invent findings if the audit failed. No repeating the first-call instruction as if this were call1.',
}
def note(s,step):return NOTES[s['arm']] if step==1 or s['arm']=='A' else FOLLOW[s['arm']]
def prompt(task,s,step,ledger,history,remaining):
    return COMMON+f'\nCURRENT MODEL CALL: {step} of 6.\n'+note(s,step)+'\n'+('Final call: SOLUTION.' if step==6 else 'Choose the permitted next executable action.')+'\nTASK:\n'+task+'\nSUCCESSFUL CODE LEDGER:\n'+'\n\n'.join(f'CELL {i}:\n{c}' for i,c in enumerate(ledger))+'\nOBSERVED HISTORY:\n'+history+f'\nTOTAL SECONDS REMAINING: {int(remaining)}\n'
d.prompt=prompt
def decode(raw,step):
    assert not m.SECRET.search(raw.encode())
    modes=__import__('re').findall(r'(?m)^\s*(CHECK|SOLUTION)\s*$',raw.split('```',1)[0])
    parts=__import__('re').findall(r'```python\s*\n(.*?)```',raw,__import__('re').S)
    if len(modes)!=1 or len(parts)!=1 or raw.count('```')!=2 or step==6 and modes[0]!='SOLUTION':raise ValueError('action format')
    ast.parse(parts[0]);return modes[0],parts[0],raw.split('```',1)[0]
d.decode=decode
def wrapper(code,seed,remove_submission=True):
    return ('import random as _r, numpy as _n\n_r.seed(42)\n_n.random.seed(42)\n'+("from pathlib import Path as _P\n_P('submission.csv').unlink(missing_ok=True)\n" if remove_submission else '')+f'globals()["__name__"]="__main__"\nexec(compile({code!r},"cell.py","exec"))\n')
d.wrapper=wrapper

def adapt(source,name,pairs,module):
    tree=ast.parse(source);node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
    body=ast.get_source_segment(source,node)
    for a,b in pairs:
        assert body.count(a)==1,(name,a);body=body.replace(a,b)
    ast.parse(body);exec(compile(body,'evidence_'+name,'exec'),module.__dict__)
adapt((P/'factorial_engine.py').read_text(),'episode',[
    ('range(5)','range(7)'),
    ('try:mode,code,reason=decode(raw,step)',"try:\n                    mode,code,reason=decode(raw,step)\n                    if step==1 and s['arm'] in ('B','C') and mode!='CHECK':raise ValueError('first call must execute a check')")],d)
m.episode=d.episode
base=Path(m.__file__).read_text()
adapt(base,'worker',[("TIME_LIMIT='30 minutes'","TIME_LIMIT='12 minutes'"),("STEP_LIMIT='5'","STEP_LIMIT='7'")],m)
adapt(base,'task_runtime',[("action-[0-4]","action-[0-6]")],m)
adapt(base,'service',[("!='gpu28'","!='gpu3'")],m)
adapt(base,'controller',[("!='gpu28'","!='gpu3'"),('03:39:00','02:29:00'),('00:33:00','00:15:00'),('range(6)','range(9)'),('max_workers=3','max_workers=2'),
    ("        try:\n            while time.monotonic()-began<900:","        try:\n            subprocess.run(base+['--cpus-per-task=6','--gres=gpu:1','--time=00:02:00',str(PY),'-B',str(ROOT/'task_feedback_real_20261001.py'),'compat'],env=env,check=True,timeout=120)\n            while time.monotonic()-began<900:")],m)

def compatibility():
    # Identical reviewed image/device computation; rebound module globals only.
    p=B/'automatic_specification_v6_20261003.py'
    assert sha(p)=='1c5c7551d43392ab5d8c442d56e0dbc6fadbadababb463b35e0ca0dd795813f0'
    tree=ast.parse(p.read_text());n=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='compatibility')
    ns=dict(globals());exec(compile(ast.get_source_segment(p.read_text(),n),'compat','exec'),ns);ns['compatibility']()

def prepare():
    assert not R.exists() and sha(P/'plan.json')=='6b91aba97ee53f6da2335064f1dbe4277020b8744fd95a3575e4c99329936d2f'
    R.mkdir(mode=0o700);old=m.read(P/'plan.json')
    for rel,h in old['files'].items():
        if not(rel.startswith(('source/','forets_','opencl-vendors/')) or rel in ('v6_runtime.py','root_trial_step_supervisor_20260927.py','factorial_engine.py')):continue
        assert sha(P/rel)==h;q=R/rel;q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(P/rel,q)
    ident=R/'forets_native_cuda_identity_20260911.py';raw=ident.read_text();assert raw.count("!='gpu28'")==1;ident.write_text(raw.replace("!='gpu28'","!='gpu3'"))
    shutil.copyfile(__file__,R/'task_feedback_real_20261001.py')
    for n in ('configs','starts','bin','service-cache/tmp'):(R/n).mkdir(parents=True,exist_ok=True)
    for k in (0,1):shutil.copyfile(P/'starts'/f'{k}.private.json',R/'starts'/f'{k}.private.json')
    entry=(P/'service_entry.py').read_text();assert entry.count("'19453'")==1;(R/'service_entry.py').write_text(entry.replace("'19453'","'19461'"))
    with (R/'.service.env').open('x') as f:f.write('PRIMARY_KEY_QWEN3_8_27B='+secrets.token_hex(32)+'\n')
    os.chmod(R/'.service.env',0o600)
    (R/'bin/singularity').write_text(f'#!{m.PY}\nimport sys\nsys.path.insert(0,{str(R)!r})\nfrom task_feedback_real_20261001 import m\nm.task_runtime()\n');os.chmod(R/'bin/singularity',0o700)
    for s in schedule():
        cfg=m.read(P/'configs'/f'{s["start"]}.json');ep=R/f'episode-{s["index"]}';ep.mkdir()
        cfg['id']=f'executable-evidence-{s["index"]}';cfg['logger'].update(output_dir=str(ep/'native-log'),write_env_vars=False,use_wandb=False,print_config=False,use_console=False)
        cfg['metadata'].update(seed=s['seed'],script_id='executable-evidence-20261004',base_path=str(R/'source'),git_commit_id=COMMIT)
        cfg['solver'].update(time_limit_secs=720,step_limit=7,checkpoint_path=str(ep/'unused-checkpoint'))
        cfg['interpreter']['working_dir']=str(ep/'unused-work');cfg['interpreter']['timeout']=300;cfg['task']['cache_dir']=str(R/'no-official-data')
        for op in cfg['solver']['operators'].values():
            op['llm']['client']['base_url']='http://127.0.0.1:19461/v1';op['llm']['generation_kwargs']['seed']=s['seed']
        m.write(R/'configs'/f'{s["index"]}.json',cfg)
    batch=(P/'run.sbatch').read_text().replace(str(P),str(R)).replace('opportunity-information','executable-evidence').replace('01:30:00','02:30:00').replace('5340s','8940s').replace('--nodelist=gpu28','--nodelist=gpu3');(R/'run.sbatch').write_text(batch)
    m.write(R/'plan.json',dict(protocol='executable-evidence-qualification-v1',base_commit=COMMIT,utc=m.utc(),schedule=schedule(),starts=old['starts'],donor_sha256=DONOR_SHA,
        files={str(p.relative_to(R)):sha(p) for p in R.rglob('*') if p.is_file() and p.name!='.service.env'},run_seconds=720,allocation_seconds=9000,gpus=4,gpu_hours_cap=10,runs=18,max_calls=6,max_tokens=4096,code_seconds=300,paid_api=0,base_updates=0,
        primary='Oriented retained-incumbent gain B-A and B-C within each task/generation seed; all18 assigned trajectories, including failures. Identical initial prediction bytes required per triple. Missing initial means null, never zero.',
        gate='Both tasks: all3 triples comparable; median B-A>=0.002 and median B-C>=0.002; no seed negative in either contrast; B must generate an improved valid submission. This is a small developer go/no-go gate, not significance or independent confirmation.',
        mechanism='Before outcome read, inspect all accepted action code/reasons: B tests a falsifiable premise, obtains actual discriminating evidence, then implements evidence-linked change. Mere summary prints/plans/standard refits are insufficient. Independent score and chronology checks required.',
        information='A ordinary full-tool continuation; B self-chosen executable premise falsification; C fixed ordinary ML audit. First CHECK required only B/C, costs their budget. Same access and action set; do not claim isolated information-only effect or Iris reproduction.',
        cost='Initial rerun, model generation, all CHECK/SOLUTION attempts, reconstruction, grading and idle allocated GPUs count. Historical qualification/witness acquisition is disclosed sunk cost; no claim of from-scratch E2E superiority.',
        selection='Same two developer parents as prior information pilot, smallest qualified source state per task. They were chosen using old development outcomes; repeated development use. Generation seeds vary, parent/task training RNG42 fixed. No heldout/generalization claim. No replacement roots, new seed rescue or prompt sweep after results.',
        fairness='Single policy knob. Same base model, task image, data/splits, hardware, scorer, six calls/720sec, parser, checkpoint/replay and keep-best. Historic600sec/fourcall batches are NOT causal controls.',
        stopping='One18-trajectory batch only. On integrity/runtime failure, stop and preserve; do not impute missing trials. All numeric outcomes withheld from analyst until closure. No extra GPU batch this window.',protected_opened=False))
    cpu();print(json.dumps(dict(status='PREPARED',plan_sha256=sha(R/'plan.json'),runs=18,gpu_hours_cap=10)))

def cpu():
    m.check();m.setup();os.environ['PRIMARY_KEY_QWEN3_8_27B']='synthetic-test-only'
    from dojo.config_dataclasses.run import RunConfig
    from dojo.tasks.mlebench.task import MLEBenchTask
    for s in schedule():
        c=RunConfig.load_from_json(R/'configs'/f'{s["index"]}.json');c.validate();t=MLEBenchTask(c.task);assert t._search_only_score and not t.private_dir.exists()
        for step in range(1,7):
            p=prompt(t.task_description,s,step,['x=1'],'observed',500)
            assert note(s,step) in p and f'CURRENT MODEL CALL: {step} of 6.' in p
            assert ('On this first call use CHECK.' in p)==(step==1 and s['arm'] in 'BC')
    subprocess.run(['bash','-n',str(R/'run.sbatch')],check=True)
    m.write(R/'cpu.json',dict(status='PASS',configs=18,prompt_checks=108,plan_sha256=sha(R/'plan.json')))

def submit():
    m.check();plan=sha(R/'plan.json')
    for n in ('transport-loop-cpu.json','analysis-freeze.json'):assert m.read(R/n)['plan_sha256']==plan
    assert m.read(R/'budget-approval.json')['gpu_hours_cap']==10
    assert sha(m.infra.TASK_IMAGE)==m.infra.IMAGE_SHA and sha(m.ASSETS/'vllm.sif')==m.infra.VLLM_SHA
    for q in m.read(m.ASSETS/'complete.json')['files']:
        if q['path'].endswith('.safetensors'):assert sha(m.ASSETS/q['path'])==q['digest']
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    jobs=subprocess.check_output(['squeue','-u','yzyang4','-h','-o','%i'],env=env,text=True,timeout=25).split();assert not set(jobs)-{'12535'}
    assert not (R/'launch.json').exists();m.write(R/'submit-intent.json',dict(utc=m.utc(),plan_sha256=plan))
    r=subprocess.run(['sbatch','--parsable','--chdir='+str(R),'--output='+str(R/'allocation-%j.out'),'--error='+str(R/'allocation-%j.err'),str(R/'run.sbatch')],env=env,capture_output=True,text=True,timeout=25)
    job=r.stdout.strip().split(';')[0];assert r.returncode==0 and job.isdigit(),'ambiguous submission: do not retry'
    m.write(R/'launch.json',dict(job=job,utc=m.utc(),plan_sha256=plan));print(json.dumps(dict(status='SUBMITTED',job=job,plan_sha256=plan,gpu_hours_cap=10)))

if __name__=='__main__':
    os.umask(0o077);a=argparse.ArgumentParser();a.add_argument('mode',choices=['prepare','cpu','submit','worker','controller','service','compat']);a.add_argument('--index',type=int);v=a.parse_args()
    if v.mode in ('prepare','cpu','submit'):globals()[v.mode]()
    elif v.mode=='compat':compatibility()
    elif v.mode=='worker':m.worker(v.index)
    else:getattr(m,v.mode)()
