"""Narrow follow-up on the only task passing public-state exact replay.

The original two-task gate FAILED and its 16-run experiment stays unlaunched.
This separate exploratory 8-run pilot cannot support a cross-task conclusion.
"""
import argparse,ast,copy,hashlib,importlib.util,json,os,random,secrets,shutil,subprocess,sys
from pathlib import Path
B=Path('/research/d7/spc/yzyang4')
PARENT=B/'state-feedback-factorial-20261002-v1'
ROOT=B/'state-feedback-pizza-20261002-v1'
ENGINE_SHA='57b45de1d7afc9f9657c3667c583537db94cda9ee527d5999fe15fc23bb6397d'
engine=ROOT/'factorial_engine.py' if (ROOT/'factorial_engine.py').exists() else PARENT/'task_feedback_real_20261001.py'
if hashlib.sha256(engine.read_bytes()).hexdigest()!=ENGINE_SHA:raise ValueError('parent engine drift')
spec=importlib.util.spec_from_file_location('pizza_factorial_engine',engine)
d=importlib.util.module_from_spec(spec);sys.modules[spec.name]=d;spec.loader.exec_module(d)
m=d.m;d.ROOT=ROOT;m.ROOT=ROOT;m.PORT=19448;m.CAP=4800;m.infra.ROOT=ROOT;m.infra.SERVICE_PORT=m.PORT
decode=d.decode;execute=d.execute;episode=d.episode;prompt=d.prompt
TASKS=('random-acts-of-pizza',);ARMS=d.ARMS

def schedule():
    order=list('ABCD');random.Random(2026100216).shuffle(order)
    return [dict(index=2*w+j,start=0,task=TASKS[0],arm=arm,seed=103301+j,wave=w,
        retained=ARMS[arm][0],visible=ARMS[arm][1])
        for w in range(4) for j,arm in enumerate((order[w],order[::-1][w]))]
m.schedule=schedule;d.schedule=schedule
base=(PARENT/'v6_runtime.py').read_text()
node=next(n for n in ast.parse(base).body if isinstance(n,ast.FunctionDef) and n.name=='controller')
src=ast.get_source_segment(base,node)
for old,new in [('03:39:00','01:19:00'),('00:33:00','00:15:00'),('for wave in range(6):','for wave in range(4):'),('max_workers=3','max_workers=2'),('dict(attempts=18,','dict(attempts=8,')]:
    if src.count(old)!=1:raise ValueError('controller baseline mismatch')
    src=src.replace(old,new)
exec(compile(src,'pizza_controller','exec'),m.__dict__)

def qualified_task():
    q=B/'state-reuse-qualification-20261002-v1';v=m.read(q/'verification.json')
    if v['plan_sha256']!='e9926dcf48ea6385f542142e070faa811ab528a644bfa29970aa4bf750740af3' or v['gate'] is not False:raise ValueError('qualification history changed')
    t=next(t for t in v['tasks'] if t['task']==TASKS[0])
    if t['pairs']!=2 or t['exact_equal']!=2 or t['marginal_ratio_median']<=2:raise ValueError('task not qualified')
    return dict(root=str(q),verification_sha256=m.sha(q/'verification.json'),original_two_task_gate=False,qualified_task=t['task'],excluded='spooky: embedding OOF replay changed; final submission and TFIDF were identical')

def prepare():
    if ROOT.exists():raise FileExistsError(ROOT)
    if (PARENT/'launch.json').exists():raise ValueError('original factorial unexpectedly launched')
    q=qualified_task();p=m.read(PARENT/'plan.json')
    if m.sha(PARENT/'plan.json')!='2820d6cc64d9d1045179f2290383340c38605b6ba604364d8fd6307be2a0b237':raise ValueError('parent plan drift')
    ROOT.mkdir(mode=0o700)
    for rel,h in p['files'].items():
        if not (rel.startswith(('source/','forets_','opencl-vendors/')) or rel in ('root_trial_step_supervisor_20260927.py','v6_runtime.py','starts/0.private.json')):continue
        if m.sha(PARENT/rel)!=h:raise ValueError('parent file drift')
        dst=ROOT/rel;dst.parent.mkdir(exist_ok=True,parents=True);shutil.copyfile(PARENT/rel,dst)
    code=m.read(ROOT/'starts/0.private.json')['code']
    if hashlib.sha256(code.encode()).hexdigest()!=p['starts'][0]['code_sha256']:raise ValueError('initial code provenance')
    shutil.copyfile(engine,ROOT/'factorial_engine.py');shutil.copyfile(__file__,ROOT/'task_feedback_real_20261001.py')
    for rel in ('configs','bin','service-cache/tmp'):(ROOT/rel).mkdir(exist_ok=True,parents=True)
    (ROOT/'bin/singularity').write_text((PARENT/'bin/singularity').read_text().replace(str(PARENT),str(ROOT)));os.chmod(ROOT/'bin/singularity',0o700)
    entry=(PARENT/'service_entry.py').read_text();assert entry.count("'19447'")==1
    (ROOT/'service_entry.py').write_text(entry.replace("'19447'","'19448'"))
    with (ROOT/'.service.env').open('x') as f:f.write('PRIMARY_KEY_QWEN3_8_27B='+secrets.token_hex(32)+'\n')
    os.chmod(ROOT/'.service.env',0o600)
    for s in schedule():
        cfg=m.read(PARENT/'configs/0.json');ep=ROOT/f'episode-{s["index"]}';ep.mkdir()
        cfg['id']=f'state-pizza-{s["index"]}';cfg['logger']['output_dir']=str(ep/'native-log')
        cfg['metadata'].update(seed=s['seed'],script_id='state-feedback-pizza-20261002',base_path=str(ROOT/'source'))
        cfg['solver']['checkpoint_path']=str(ep/'unused-checkpoint');cfg['interpreter']['working_dir']=str(ep/'unused-work')
        cfg['interpreter']['env']['PYTHONHASHSEED']=str(s['seed']);cfg['task']['cache_dir']=str(ROOT/'no-official-data')
        for op in cfg['solver']['operators'].values():
            op['llm']['client']['base_url']=f'http://127.0.0.1:{m.PORT}/v1';op['llm']['generation_kwargs']['seed']=s['seed']
        m.write(ROOT/'configs'/f'{s["index"]}.json',cfg)
    batch=(PARENT/'run.sbatch').read_text().replace(str(PARENT),str(ROOT)).replace('state-feedback-factorial','state-feedback-pizza').replace('02:15:00','01:20:00').replace('8040s','4740s')
    (ROOT/'run.sbatch').write_text(batch)
    files={str(f.relative_to(ROOT)):m.sha(f) for f in ROOT.rglob('*') if f.is_file() and f.name!='.service.env'}
    plan={**p,'protocol':'state-feedback-pizza-v1','utc':m.utc(),'schedule':schedule(),'starts':p['starts'][:1],
        'files':files,'allocation_seconds':4800,'gpu_hours_cap':4*4800/3600,'qualification':q,
        'gate':'single-task exploration only: median interaction >0, D-C>0, D-B>0 plus trace evidence; no cross-task upgrade',
        'limitations':'Pizza selected only for passing pre-outcome execution identity, not for score gains; 2 combined initialization/generation run seeds, one historical development start, repeated D_search; not independent final evaluation'}
    m.write(ROOT/'plan.json',plan)
    print(json.dumps(dict(status='PREPARED',plan_sha256=m.sha(ROOT/'plan.json'),runs=8,gpu_hours_cap=plan['gpu_hours_cap'])))

def submit():
    p=m.check();assert p['qualification']==qualified_task()
    for name in ('cpu.json','transport-cpu.json'):
        r=m.read(ROOT/name)
        if r['status']!='PASS' or r['plan_sha256']!=m.sha(ROOT/'plan.json'):raise ValueError('preflight stale')
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
    if r.returncode or not job.isdigit():raise RuntimeError('ambiguous submission; no retry')
    m.write(ROOT/'launch.json',dict(job=job,utc=m.utc(),plan_sha256=m.sha(ROOT/'plan.json')))
    print(json.dumps(dict(status='SUBMITTED',job=job,gpu_hours_cap=p['gpu_hours_cap'])))

if __name__=='__main__':
    os.umask(0o077);a=argparse.ArgumentParser();a.add_argument('mode',choices=['prepare','submit','check','worker','controller','service']);a.add_argument('--index',type=int);x=a.parse_args()
    if x.mode in ('prepare','submit'):globals()[x.mode]()
    elif x.mode=='worker':m.worker(x.index)
    elif x.mode=='check':m.check();print('FROZEN_PLAN_VALID')
    else:getattr(m,x.mode)()
