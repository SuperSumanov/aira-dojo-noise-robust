"""Fixed one-line causal implementation check, scheduled AFTER the main trial.

Two seeds x original/fixed program; no generator/critic. Not an agent arm.
"""
import argparse,ast,copy,hashlib,importlib.util,inspect,json,os,shutil,subprocess,sys,time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
B=Path('/research/d7/spc/yzyang4');OLD=B/'task-feedback-real-20261001-v6';ROOT=B/'task-feedback-pizza-control-20261002-v1'
BASE_SHA='4b155d927c12f063e0838b5708085fe1bc55c4983197a3d8d2453696d73c55ad'
source=ROOT/'v6_runtime.py' if (ROOT/'v6_runtime.py').exists() else OLD/'task_feedback_real_20261001.py'
assert hashlib.sha256(source.read_bytes()).hexdigest()==BASE_SHA
spec=importlib.util.spec_from_file_location('pizza_v6',source);m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
m.ROOT=ROOT;m.SECONDS=600;m.CAP=1800;m.infra.ROOT=ROOT;m.infra.local_key=lambda:'no-generator-in-this-control'
def schedule():
    return [dict(index=i,start=i,task='random-acts-of-pizza',arm='A',variant=('original','fixed')[i%2],seed=(102101,102102)[i//2],wave=i//2) for i in range(4)]
m.schedule=schedule
worker=inspect.getsource(m.worker).replace("TIME_LIMIT='30 minutes'","TIME_LIMIT='10 minutes'")
episode=inspect.getsource(m.episode);assert episode.count('range(5)')==1
exec(compile(worker,'pizza_worker','exec'),m.__dict__);exec(compile(episode.replace('range(5)','range(1)'),'pizza_single_execution','exec'),m.__dict__)
def prepare():
    ROOT.mkdir(mode=0o700,exist_ok=False);plan=m.read(OLD/'plan.json')
    assert m.sha(OLD/'plan.json')=='15751d3b52bdc42617df02006ce724635f4bf49df6e477686769fd1979d53403'
    for rel,h in plan['files'].items():
        if not (rel.startswith('source/') or rel.startswith('forets_') or rel.startswith('opencl-vendors/') or rel in ('root_trial_step_supervisor_20260927.py','task_feedback_facts_20261001.py')):continue
        src=OLD/rel;assert m.sha(src)==h
        dst=ROOT/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst)
    shutil.copyfile(source,ROOT/'v6_runtime.py');shutil.copyfile(Path(__file__),ROOT/Path(__file__).name)
    for p in ('starts','configs','bin'):(ROOT/p).mkdir()
    (ROOT/'bin/singularity').write_text(f'#!{m.PY}\nimport sys\nsys.path.insert(0,{str(ROOT)!r})\nfrom task_feedback_pizza_control_20261002 import m\nm.task_runtime()\n');os.chmod(ROOT/'bin/singularity',0o700)
    nodepath=OLD/'episode-7/action-4/node.private.json';assert m.sha(nodepath)=='d69ce4eb64e3e5bde58e0b68d65cfb82aa98daf93e91cc5ce453876ba357c273'
    node=m.read(nodepath);old='F["days_since_start"] = (ts - ts.min()).dt.days'
    new='F["days_since_start"] = (ts - pd.to_datetime(train["unix_timestamp_of_request_utc"].astype(float), unit="s", utc=True).min()).dt.days'
    assert node['code'].count(old)==1
    fixed=node['code'].replace(old,new);ast.parse(fixed.split('```python\n',1)[1].rsplit('```',1)[0])
    for s in schedule():
        ep=ROOT/f'episode-{s["index"]}';ep.mkdir();code=node['code'] if s['variant']=='original' else fixed
        m.write(ROOT/'starts'/f'{s["start"]}.private.json',{'code':code,'plan':node['plan']})
        cfg=m.read(OLD/'configs/7.json');cfg['id']=f'pizza-control-20261002-{s["index"]}'
        cfg['logger'].update(output_dir=str(ep/'native-log'),write_env_vars=False,use_wandb=False,print_config=False,use_console=False)
        cfg['metadata'].update(seed=s['seed'],script_id='pizza-one-line-control',base_path=str(ROOT/'source'))
        cfg['solver'].update(time_limit_secs=600,step_limit=1,checkpoint_path=str(ep/'unused-checkpoint'))
        cfg['interpreter']['working_dir']=str(ep/'unused-work');cfg['interpreter']['env']['PYTHONHASHSEED']=str(s['seed'])
        cfg['task']['cache_dir']=str(ROOT/'no-official-data')
        m.write(ROOT/'configs'/f'{s["index"]}.json',cfg)
    batch=f'''#!/bin/bash
#SBATCH --job-name=pizza-fixed-origin
#SBATCH --partition=gpu_24h
#SBATCH --account=gpu
#SBATCH --qos=gpu
#SBATCH --nodelist=gpu28
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:2
#SBATCH --cpus-per-task=12
#SBATCH --time=00:30:00
#SBATCH --no-requeue
set -euo pipefail
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1
timeout --signal=TERM --kill-after=20s 1740s {m.PY} -B {ROOT}/task_feedback_pizza_control_20261002.py controller
'''
    (ROOT/'run.sbatch').write_text(batch)
    files={str(p.relative_to(ROOT)):m.sha(p) for p in ROOT.rglob('*') if p.is_file()}
    m.write(ROOT/'plan.json',{'schedule':schedule(),'files':files,'base_commit':'ca65a10641e469846576e354d0ea512abea3498d','utc':m.utc(),'run_seconds':600,'gpu_hours_cap':1.0,'dependency':'afterok:15204','rule':'only training-fixed date origin replaces batch-relative origin','generations':0,'reads_only_existing_unprotected_development':True,'not_e2e_or_method_effect':True})
    m.setup()
    from dojo.config_dataclasses.run import RunConfig
    from dojo.tasks.mlebench.task import MLEBenchTask
    for s in schedule():
        c=RunConfig.load_from_json(ROOT/'configs'/f'{s["index"]}.json');c.validate();t=MLEBenchTask(c.task);assert t._search_only_score is not None and not t.private_dir.exists()
    subprocess.run(['bash','-n',str(ROOT/'run.sbatch')],check=True)
    m.write(ROOT/'cpu.json',{'status':'PASS','plan_sha256':m.sha(ROOT/'plan.json'),'configs':4,'single_code_line_replaced':True})
    print(json.dumps({'status':'PREPARED','plan_sha256':m.sha(ROOT/'plan.json'),'runs':4,'gpu_hours_cap':1.0}))
def submit():
    p=m.check();assert m.read(ROOT/'cpu.json')['plan_sha256']==m.sha(ROOT/'plan.json')
    assert m.read(B/'task-feedback-upper-20261002-v1/launch.json')['job']=='15204'
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    m.write(ROOT/'submit-intent.json',{'utc':m.utc(),'dependency':'afterok:15204','plan_sha256':m.sha(ROOT/'plan.json')})
    r=subprocess.run(['sbatch','--parsable','--dependency=afterok:15204','--chdir='+str(ROOT),'--output='+str(ROOT/'allocation-%j.out'),'--error='+str(ROOT/'allocation-%j.err'),str(ROOT/'run.sbatch')],env=env,capture_output=True,text=True,timeout=25)
    job=r.stdout.strip().split(';')[0]
    if r.returncode or not job.isdigit():raise RuntimeError('submission ambiguous; do not retry')
    m.write(ROOT/'launch.json',{'job':job,'utc':m.utc(),'plan_sha256':m.sha(ROOT/'plan.json')});print(json.dumps({'job':job,'dependency':'afterok:15204','gpu_hours_cap':1.0}))
def controller():
    m.check();m.setup();job=os.environ['SLURM_JOB_ID'];assert m.read(ROOT/'launch.json')['job']==job
    assert m.socket.gethostname().split('.')[0]=='gpu28'
    m.write(ROOT/'claim.json',{'job':job,'utc':m.utc()});m.write(ROOT/'service-native.json',{'job':job,'gpu_uuids':[],'role':'NO_GENERATOR_SERVICE'})
    from root_trial_step_supervisor_20260927 import supervise
    env=m.infra.clean_env();began=time.monotonic()
    def one(s):
        ep=ROOT/f'episode-{s["index"]}';m.write(ep/'launch.json',dict(utc=m.utc(),**s))
        cmd=['srun','--exclusive','--nodes=1','--ntasks=1','--cpus-per-task=6','--gres=gpu:1','--time=00:12:00',str(m.PY),'-B',str(ROOT/'task_feedback_pizza_control_20261002.py'),'worker','--index',str(s['index'])]
        r=supervise(cmd,env=env,log_path=ep/'worker.private.log',native_path=ep/'native.json',deadline_path=ep/'deadline.json',job_id=job,config_sha256=m.sha(ROOT/'configs'/f'{s["index"]}.json'),index=s['index'],seconds=600,startup_seconds=120,cleanup_seconds=60)
        m.cleanup(s['index']);m.write(ep/'closed.json',r)
        if not r['worker_deadline_reached'] and (not (ep/'finished.json').exists() or m.read(ep/'finished.json')['status'] not in ('completed','budget_exhausted')):raise RuntimeError('early worker failure')
    try:
        for wave in range(2):
            if time.monotonic()-began>1000:raise TimeoutError('no whole next wave')
            with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(one,[s for s in schedule() if s['wave']==wave]))
        m.write(ROOT/'all-closed.json',{'attempts':4,'utc':m.utc(),'generator_calls':0})
    except Exception as e:
        m.write(ROOT/'controller-error.json',{'error_type':type(e).__name__,'utc':m.utc()});raise
    finally:m.write(ROOT/'closed.json',{'utc':m.utc(),'elapsed_seconds':time.monotonic()-began,'service_closed':True})
if __name__=='__main__':
    os.umask(0o077);p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','submit','controller','worker','check']);p.add_argument('--index',type=int);a=p.parse_args()
    if a.mode=='worker':m.worker(a.index)
    elif a.mode=='check':m.check();print('FROZEN_PLAN_VALID')
    else:globals()[a.mode]()
