"""Thin derivative of the completed v6 runtime, with frozen scoped interventions."""
import argparse,copy,hashlib,importlib.util,inspect,json,os,random,secrets,shutil,sys
from pathlib import Path
OLD=Path('/research/d7/spc/yzyang4/task-feedback-real-20261001-v6')
ROOT=Path('/research/d7/spc/yzyang4/task-feedback-upper-20261002-v1')
BASE_SHA='4b155d927c12f063e0838b5708085fe1bc55c4983197a3d8d2453696d73c55ad'
base=ROOT/'v6_runtime.py' if (ROOT/'v6_runtime.py').exists() else OLD/'task_feedback_real_20261001.py'
if hashlib.sha256(base.read_bytes()).hexdigest()!=BASE_SHA:raise ValueError('v6 runtime drift')
spec=importlib.util.spec_from_file_location('upper_v6',base);m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
m.ROOT=ROOT;m.PORT=19442;m.SECONDS=1200;m.CAP=11400;m.COMMIT='4af5723c7a98b25a75c7771695a19ac96f90935d'
m.infra.ROOT=ROOT;m.infra.SERVICE_PORT=m.PORT
def schedule():
    starts=[('random-acts-of-pizza',102001),('tweet-sentiment-extraction',102002),('random-acts-of-pizza',102003),('tweet-sentiment-extraction',102004),('random-acts-of-pizza',102005),('tweet-sentiment-extraction',102006)]
    order=list('ABC');random.Random(20261002).shuffle(order);out=[]
    for block in range(2):
        for j,arm in enumerate(order if block==0 else order[::-1]):
            for t in range(3):
                start=block*3+t;task,seed=starts[start]
                out.append(dict(index=len(out),start=start,task=task,seed=seed,arm=arm,wave=block*3+j))
    return out
m.schedule=schedule
def accounting():return {'job':None,'gpu_seconds':0,'combined_gpu_hours_cap':5*m.CAP/3600,'scope':'this new experiment; prior completed pilot reported separately'}
m.prior_accounting=accounting
# Only time strings differ; worker identity/deadline/cleanup paths stay v6-identical.
for name,replacements in [('worker',{"TIME_LIMIT='30 minutes'":"TIME_LIMIT='20 minutes'"}),('controller',{'03:39:00':'03:09:00','00:33:00':'00:23:00'})]:
    src=inspect.getsource(getattr(m,name))
    for a,b in replacements.items():
        if src.count(a)!=1:raise ValueError('runtime adaptation mismatch')
        src=src.replace(a,b)
    exec(compile(src,'upper_'+name,'exec'),m.__dict__)
def prepare():
    if ROOT.exists():raise FileExistsError('new one-shot root already exists')
    oldplan=m.read(OLD/'plan.json')
    if m.sha(OLD/'plan.json')!='15751d3b52bdc42617df02006ce724635f4bf49df6e477686769fd1979d53403':raise ValueError('old plan')
    ROOT.mkdir(mode=0o700);here=Path(__file__).parent
    for rel,h in oldplan['files'].items():
        if rel.startswith(('configs/','starts/','bin/','service-cache/')) or rel in ('task_feedback_real_20261001.py','task_feedback_facts_20261001.py','FEEDBACK_REAL_PILOT_20261001.md','run.sbatch','service_entry.py'):continue
        src=OLD/rel
        if m.sha(src)!=h:raise ValueError('frozen support drift: '+rel)
        dst=ROOT/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst)
    shutil.copyfile(base,ROOT/'v6_runtime.py')
    shutil.copyfile(here/'task_feedback_upper_20261002.py',ROOT/'task_feedback_real_20261001.py')
    shutil.copyfile(here/'task_feedback_upper_facts_20261002.py',ROOT/'task_feedback_facts_20261001.py')
    shutil.copyfile(here/'FEEDBACK_UPPER_BOUND_20261002.md',ROOT/'protocol.md')
    shutil.copyfile('/tmp/task-feedback-upper-evidence-20261002-v2/checks.json',ROOT/'evidence.json')
    for rel in ('starts','configs','bin','service-cache/tmp'): (ROOT/rel).mkdir(parents=True,exist_ok=True)
    (ROOT/'bin/singularity').write_text(f'#!{m.PY}\nimport sys\nsys.path.insert(0,{str(ROOT)!r})\nfrom task_feedback_real_20261001 import m\nm.task_runtime()\n');os.chmod(ROOT/'bin/singularity',0o700)
    entry=(OLD/'service_entry.py').read_text();assert entry.count("'19441'")==1
    (ROOT/'service_entry.py').write_text(entry.replace("'19441'","'19442'"))
    with (ROOT/'.service.env').open('x') as f:f.write('PRIMARY_KEY_QWEN3_8_27B='+secrets.token_hex(32)+'\n')
    os.chmod(ROOT/'.service.env',0o600)
    evidence=m.read(ROOT/'evidence.json');starts=[];cfgs=[]
    for start in range(6):
        donor=7 if start%2==0 else 11
        fact=next(x for x in evidence['checks'] if x['episode']==donor)
        nodefile=OLD/f'episode-{donor}'/fact['action']/'node.private.json'
        if m.sha(nodefile)!=fact['node_sha256']:raise ValueError('selected code drift')
        node=m.read(nodefile)
        if hashlib.sha256(node['code'].encode()).hexdigest()!=fact['raw_code_sha256']:raise ValueError('source code binding')
        m.write(ROOT/'starts'/f'{start}.private.json',{'code':node['code'],'plan':node['plan']})
        starts.append({'task':fact['task'],'code_sha256':fact['raw_code_sha256'],'donor_episode':donor,'donor_action':fact['action'],'selection':fact['valid_source_rule']})
        cfgs.append(m.read(OLD/f'configs/{donor}.json'))
    for s in schedule():
        cfg=copy.deepcopy(cfgs[s['start']]);ep=ROOT/f'episode-{s["index"]}';ep.mkdir()
        assert cfg['task']['name']==s['task']
        cfg['id']=f'feedback-upper-20261002-{s["index"]}'
        cfg['logger'].update(output_dir=str(ep/'native-log'),write_env_vars=False,use_wandb=False,print_config=False,use_console=False)
        cfg['metadata'].update(seed=s['seed'],script_id='task-feedback-upper-20261002',git_commit_id=m.COMMIT,base_path=str(ROOT/'source'))
        cfg['solver'].update(time_limit_secs=m.SECONDS,step_limit=5,checkpoint_path=str(ep/'unused-checkpoint'))
        cfg['interpreter']['working_dir']=str(ep/'unused-work');cfg['interpreter']['env']['PYTHONHASHSEED']=str(s['seed'])
        cfg['task']['cache_dir']=str(ROOT/'no-official-data')
        for op in cfg['solver']['operators'].values():
            op['llm']['client']['base_url']=f'http://127.0.0.1:{m.PORT}/v1';op['llm']['generation_kwargs']['seed']=s['seed']
        m.write(ROOT/'configs'/f'{s["index"]}.json',cfg)
    batch=(OLD/'run.sbatch').read_text().replace(str(OLD),str(ROOT)).replace('task-feedback-ABC','feedback-upper-ABC').replace('03:40:00','03:10:00').replace('13140s','11340s')
    (ROOT/'run.sbatch').write_text(batch)
    files={str(p.relative_to(ROOT)):m.sha(p) for p in ROOT.rglob('*') if p.is_file() and p.name!='.service.env'}
    m.write(ROOT/'plan.json',dict(protocol='curated-evidence-feasibility-v1',base_commit=m.COMMIT,utc=m.utc(),schedule=schedule(),starts=starts,files=files,run_seconds=m.SECONDS,allocation_seconds=m.CAP,gpu_hours_cap=5*m.CAP/3600,prior_failed_allocation=accounting(),paid_api=0,agent_training=False,renewal='confirmed',protected_opened=False,final_evaluation=False))
    print(json.dumps({'status':'PREPARED','plan_sha256':m.sha(ROOT/'plan.json'),'planned':len(schedule()),'gpu_hours_cap':5*m.CAP/3600}))
def cpu():
    p=m.check();m.setup()
    from dojo.config_dataclasses.run import RunConfig
    from dojo.tasks.mlebench.task import MLEBenchTask
    from task_feedback_facts_20261001 import packet,feedback
    for s in schedule():
        cfg=RunConfig.load_from_json(ROOT/'configs'/f'{s["index"]}.json');cfg.validate();t=MLEBenchTask(cfg.task)
        assert t._search_only_score and not t.private_dir.exists()
        assert cfg.solver.time_limit_secs==1200 and cfg.solver.step_limit==5
        f=packet(s['task']);a,fa=feedback('A',{'valid':True},f,'test');b,fb=feedback('B',{'valid':True},f,'test');c,fc=feedback('C',{'valid':True},f,'test')
        assert fb==fc and b!=c and 'behavioral_evidence' not in a and 'Human-curated' not in b and 'Human-curated' in c
    assert len({(s['task'],s['seed'],s['arm']) for s in schedule()})==18
    assert all(len({s['arm'] for s in schedule() if s['wave']==w})==1 for w in range(6))
    m.subprocess.run(['bash','-n',str(ROOT/'run.sbatch')],check=True)
    m.write(ROOT/'cpu.json',dict(status='PASS',typed_configs=18,plan_sha256=m.sha(ROOT/'plan.json'),protected_reads=0,real_calls=0))
    print('PASS_TYPED_CONFIG_SCHEDULE_EVIDENCE')
if __name__=='__main__':
    os.umask(0o077);p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','cpu','submit','worker','controller','service','check']);p.add_argument('--index',type=int);a=p.parse_args()
    if a.mode=='prepare':prepare()
    elif a.mode=='cpu':cpu()
    elif a.mode=='worker':m.worker(a.index)
    elif a.mode=='check':m.check();print('FROZEN_PLAN_VALID')
    else:getattr(m,a.mode)()
