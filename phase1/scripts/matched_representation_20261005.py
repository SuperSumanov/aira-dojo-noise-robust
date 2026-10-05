"""Matched finite-grid representation diagnostic; frozen before external dev scoring."""
import argparse,copy,csv,hashlib,importlib.util,json,os,re,shutil,statistics,subprocess,sys,time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
B=Path('/research/d7/spc/yzyang4');OLD=B/'implementation-reset-20261005-v2'
R=B/'matched-representation-20261005-v1';PY=B/'venvs/aira/bin/python'
NAME='matched_representation_20261005.py';PROGRAM='matched_representation_program_20261005.py'
TASKS=('random-acts-of-pizza','spooky-author-identification');SEEDS=(115001,115002)
DONOR=B/'policy9b-paired-20261005-gpu27-v1/policy9b_paired_20261005.py'
DONOR_SHA='b422a17094a6971218731054b53b56888505150b82f5309990b0b629577da4c9'
SECRET=re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,}|Bearer\s+[a-z0-9_.-]{20,})')
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
    return h.hexdigest()
def read(p):return json.loads(Path(p).read_bytes())
def write(p,x):
    b=(json.dumps(x,sort_keys=True,indent=2,allow_nan=False)+'\n').encode();assert not SECRET.search(b)
    with Path(p).open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
def load(name,p):
    s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
def schedule():
    rows=[]
    for j,seed in enumerate(SEEDS):
        for t,task in enumerate(TASKS):
            for arm in (('word','word_char') if j==0 else ('word_char','word')):
                rows.append(dict(index=len(rows),task=task,task_index=t,seed=seed,arm=arm))
    return rows
def runtime():
    assert sha(R/'runtime.py')==DONOR_SHA;m=load('matched_runtime',R/'runtime.py');m.R=R;m.setup();return m
def check():
    p=read(R/'plan.json');assert p['schedule']==schedule()
    for f,h in p['files'].items():assert sha(R/f)==h,f
    return p
def prepare(commit):
    assert re.fullmatch('[a-f0-9]{40}',commit) and not R.exists()
    old=read(OLD/'plan.json');assert sha(OLD/'plan.json')=='c1aba6663872c01c656f4da45667f5d0dc60e589fec6fe5f87fc00dcbc9a2d6a'
    R.mkdir(mode=0o700)
    for rel,h in old['files'].items():
        if not rel.startswith(('source/','forets_','opencl-vendors/')):continue
        assert sha(OLD/rel)==h;p=R/rel;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(OLD/rel,p)
    assert sha(DONOR)==DONOR_SHA;shutil.copyfile(DONOR,R/'runtime.py')
    for n in (NAME,PROGRAM):shutil.copyfile(Path(__file__).parent/n,R/n)
    (R/'configs').mkdir();(R/'bin').mkdir()
    wrapper=f'#!{PY}\nimport sys\nsys.path.insert(0,{str(R)!r})\nfrom matched_representation_20261005 import runtime\nruntime().task_runtime()\n'
    (R/'bin/singularity').write_text(wrapper);os.chmod(R/'bin/singularity',0o700)
    for row in schedule():
        i=row['index'];ep=R/f'episode-{i}';ep.mkdir();c=read(OLD/'configs'/f"{row['task_index']}.json")
        c['id']=f'matched-representation-{i}';c['logger']['output_dir']=str(ep/'native-log')
        c['metadata'].update(seed=row['seed'],base_path=str(R/'source'),git_commit_id=commit,script_id='matched-representation-20261005')
        c['task']['cache_dir']=str(R/'no-official-data');c['task']['results_output_dir']=str(ep/'native-log/results')
        c['interpreter'].update(timeout=360,working_dir=str(ep/'action-0/work'))
        c['interpreter']['env']['PYTHONHASHSEED']=str(row['seed']);write(R/'configs'/f'{i}.json',c)
    batch=f'''#!/bin/bash
#SBATCH --job-name=matched-representation
#SBATCH --partition=gpu_24h
#SBATCH --account=gpu
#SBATCH --qos=gpu
#SBATCH --nodelist=gpu27
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:2
#SBATCH --cpus-per-task=12
#SBATCH --time=00:35:00
#SBATCH --no-requeue
set -euo pipefail
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1
timeout --signal=TERM --kill-after=20s 2030s {PY} -B {R}/{NAME} controller
'''
    (R/'run.sbatch').write_text(batch)
    write(R/'plan.json',dict(protocol='matched-representation-inner-selection-v1',source_commit=commit,
        files={str(f.relative_to(R)):sha(f) for f in R.rglob('*') if f.is_file()},schedule=schedule(),
        grid=[dict(C=c,ngram=n,min_df=d) for n in (1,2) for d in (1,2) for c in (.1,.3,1.,3.,10.,30.,100.)],
        classifier='OneVsRest(liblinear L2 logistic regression),tol1e-4,max_iter1000',
        feature_budget=50000,word_budget=50000,union_budgets=[25000,25000],char_ngrams=[3,5],
        normalization='each TFIDF block L2, then union row L2; zero rows remain zero',
        selection='stratified inner 80/20; vocabulary/IDF inner train only; AUC or negative logloss; fixed grid tie order',
        deployment='full allowed public train refit once; external dev labels read only after batch closes and all predictions frozen',
        executions=8,classifier_fits_planned=232,binary_fits_planned=464,
        program_seconds=360,allocation_seconds=2100,gpus=2,gpu_hours_cap=4200/3600,
        primary='paired word_char minus word, oriented higher better; per task median and sample variance',
        diagnostic_gate='all8 complete, all selected/final fits converged, all4 paired differences positive; exploratory signal only, no automatic expansion',
        budget='equal grid opportunities and equal per-episode cap, NOT equal actual time; runtime/fit counts reported',
        no_paid_api=True,no_generator=True,no_base_training=True,protected_opened=False,
        limitations='Known representations, not novel algorithm or LLM discovery. Two reused dev tasks and two overlapping inner splits, not independent task replication. Finite grid not global HPO optimum. Solver fixed within this batch, differs from earlier lbfgs trials.'))
    m=runtime();from dojo.config_dataclasses.run import RunConfig
    for row in schedule():
        c=RunConfig.load_from_json(R/'configs'/f"{row['index']}.json");c.validate()
        assert not Path(c.task.private_dir).exists() and not c.interpreter.read_only_binds
        assert sha(c.task.search_only_dev_scorer_path)==c.task.search_only_dev_scorer_sha256
        assert c.task.data_dir==c.task.public_dir and '/search-only-dev-' in c.task.data_dir
    test=load('matched_program_test',R/PROGRAM).synthetic();subprocess.run(['bash','-n',str(R/'run.sbatch')],check=True)
    write(R/'preflight.json',dict(**test,typed_configs=8,plan_sha256=sha(R/'plan.json'),task_image_sha256=old['task_image_sha256']))
    print(json.dumps(dict(status='PREPARED',plan_sha256=sha(R/'plan.json'),root=str(R),test=test)))
def submit():
    p=check();m=runtime();assert read(R/'preflight.json')['plan_sha256']==sha(R/'plan.json')
    assert sha(m.TASK_IMAGE)==read(R/'preflight.json')['task_image_sha256']
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    jobs=subprocess.check_output(['squeue','-u','yzyang4','-h','-o','%i'],env=env,text=True,timeout=25).split();assert not set(jobs)-{'12535'}
    with (R/'capacity.tmp').open('xb') as f:os.posix_fallocate(f.fileno(),0,64*1024**2)
    (R/'capacity.tmp').unlink();write(R/'submit-intent.json',dict(plan_sha256=sha(R/'plan.json')))
    q=subprocess.run(['sbatch','--parsable','--chdir='+str(R),'--output='+str(R/'allocation-%j.out'),'--error='+str(R/'allocation-%j.err'),str(R/'run.sbatch')],env=env,capture_output=True,text=True,timeout=25)
    job=q.stdout.strip().split(';')[0];assert q.returncode==0 and job.isdigit(),'ambiguous submit: no retry'
    write(R/'launch.json',dict(job=job,plan_sha256=sha(R/'plan.json')));print(json.dumps(dict(job=job,status='SUBMITTED',gpu_hours_cap=p['gpu_hours_cap'])))
def worker(i):
    plan=check();m=runtime();x=m.infra();row=schedule()[i];ep=R/f'episode-{i}';own=x.native_uuids(1)
    os.environ.update(DOJO_GPU_UUIDS=own[0],POLICY9B_EPISODE=str(ep),DOJO_WORKER_IDENTITY_PATH=str(ep/'identity.json'),
        DOJO_EXECUTION_ID=f'{os.environ["SLURM_JOB_ID"]}.{os.environ["SLURM_STEP_ID"]}:{i}',PATH=str(R/'bin')+':'+os.environ['PATH'])
    from dojo.main_local_worker import _process_start_ticks,_host_boot_id
    from dojo.config_dataclasses.run import RunConfig
    from dojo.config_dataclasses.interpreter import INTERPRETER_MAP
    from dojo.utils.config import build
    from dojo.utils.logger import config_logger
    from dojo.utils.experiment_deadline import ExperimentDeadline
    write(ep/'identity.json',dict(pid=os.getpid(),pgid=os.getpgid(0),process_start_ticks=_process_start_ticks(os.getpid()),host_boot_id=_host_boot_id(),gpu_uuids=own,container_pid=None,container_process_start_ticks=None))
    write(ep/'native.json',dict(job=os.environ['SLURM_JOB_ID'],step=os.environ['SLURM_STEP_ID'],gpu_uuids=own))
    cfg=RunConfig.load_from_json(R/'configs'/f'{i}.json');Path(cfg.logger.output_dir).mkdir();config_logger(cfg)
    action=ep/'action-0';(action/'work').mkdir(parents=True);began=time.monotonic();valid=False;err=None;out=None;interp=None
    code=(R/PROGRAM).read_text()+f'\nmain({row["task"]!r},{row["arm"]!r},{row["seed"]})\n'
    try:
        with ExperimentDeadline(440).activate():
            interp=build(copy.deepcopy(cfg.interpreter),INTERPRETER_MAP,data_dir=cfg.task.data_dir)
            out=interp.run(f'exec(compile({code!r},"matched_representation_program.py","exec"))',reset_session=False)
            terminal='\n'.join(out.term_out or []);assert not SECRET.search(terminal.encode())
            write(action/'terminal.private.json',dict(terminal=terminal))
            for name in ('progress.json','receipt.json','submission.csv'):
                path=action/'work'/name
                try:
                    interp.fetch_file(path)
                    if path.is_file() and not path.is_symlink():shutil.copyfile(path,action/name)
                except FileNotFoundError:pass
            if out.exit_code==0 and not out.timed_out:
                rec=read(action/'receipt.json');assert rec['grid_complete'] and sha(action/'submission.csv')==rec['submission_sha256']
                valid=True
    except Exception as e:err=type(e).__name__
    finally:
        if interp is not None:interp.close()
    write(ep/'completed.json',dict(**row,valid=valid,error_type=err,exit_code=out.exit_code if out else None,
        timed_out=out.timed_out if out else None,seconds=time.monotonic()-began,source_commit=plan['source_commit']))
def controller():
    check();m=runtime();assert read(R/'launch.json')['job']==os.environ['SLURM_JOB_ID']
    def one(i):
        ep=R/f'episode-{i}';cmd=['srun','--exclusive','--nodes=1','--ntasks=1','--cpus-per-task=6','--gres=gpu:1','--time=00:08:00',str(PY),'-B',str(R/NAME),'worker','--index',str(i)]
        with (ep/'worker.private.log').open('xb') as f:q=subprocess.run(cmd,env=m.infra().clean_env(),stdout=f,stderr=f)
        write(ep/'closed.json',dict(returncode=q.returncode));return q.returncode
    with ThreadPoolExecutor(max_workers=2) as pool:codes=list(pool.map(one,range(8)))
    write(R/'closed.json',dict(returncodes=codes))
def status():
    check();print(json.dumps(dict(launch=read(R/'launch.json') if (R/'launch.json').exists() else None,closed=(R/'closed.json').exists(),
        episodes=[dict(index=i,started=(R/f'episode-{i}/native.json').exists(),completed=read(R/f'episode-{i}/completed.json') if (R/f'episode-{i}/completed.json').exists() else None) for i in range(8)])))
if __name__=='__main__':
    os.umask(0o077);p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','submit','worker','controller','check','status']);p.add_argument('--commit');p.add_argument('--index',type=int);a=p.parse_args()
    if a.mode=='prepare':prepare(a.commit)
    elif a.mode=='worker':worker(a.index)
    else:globals()[a.mode]()
