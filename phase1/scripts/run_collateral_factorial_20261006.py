"""Bounded AIRA execution of frozen numeric-transplant factorials, no LLM calls."""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

B=Path('/research/d7/spc/yzyang4');R=B/'collateral-factorial-20261006-v1'
DONOR=B/'matched-representation-20261005-v1';PY=B/'venvs/aira/bin/python'
NAME='run_collateral_factorial_20261006.py'
SELECTION='6610706263a4ed059f28d3e52e8172af9dddd9400095fdd9172626689960c295'
SECRET=re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,}|Bearer\s+[a-z0-9_.-]{20,})')

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for x in iter(lambda:f.read(8*1024**2),b''):h.update(x)
    return h.hexdigest()
def read(p):return json.loads(Path(p).read_bytes())
def write(p,x):
    raw=(json.dumps(x,sort_keys=True,indent=2,allow_nan=False)+'\n').encode();assert not SECRET.search(raw)
    with Path(p).open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
def load(name,p):
    sp=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(sp);sys.modules[name]=m;sp.loader.exec_module(m);return m
def schedule():
    assert sha(R/'selection.json')==SELECTION
    selected=read(R/'selection.json')['selected'];rows=[]
    # Latin ordering by case balances the four arms in their within-case positions.
    arms=('P','C','CP','PC')
    for c in selected:
        k=c['case']%4
        for arm in arms[k:]+arms[:k]:rows.append(dict(index=len(rows),case=c['case'],arm=arm,
            task=c['task'],seed=116001+c['case'],code_sha256=c['variant_sha256'][arm]))
    return rows
def runtime():
    m=load('collateral_native',R/'runtime.py');m.R=R;m.setup();return m
def check():
    p=read(R/'plan.json');assert p['schedule']==schedule()
    for f,h in p['files'].items():assert sha(R/f)==h,f
    return p
def prepare(commit):
    assert re.fullmatch('[a-f0-9]{40}',commit) and not (R/'plan.json').exists()
    assert sha(DONOR/'plan.json')=='fed6f8c812fc49db8acc459b460a10bbe962cbe10b8a2172f5dff06c7686a624'
    old=read(DONOR/'plan.json')
    for rel,h in old['files'].items():
        if not rel.startswith(('source/','forets_','opencl-vendors/')):continue
        assert sha(DONOR/rel)==h;dst=R/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(DONOR/rel,dst)
    original=(DONOR/'runtime.py').read_bytes()
    assert hashlib.sha256(original).hexdigest()=='b422a17094a6971218731054b53b56888505150b82f5309990b0b629577da4c9'
    old_pattern=b"re.fullmatch('episode-[0-7]',ep.name)"
    new_pattern=b"re.fullmatch('episode-(?:[0-9]|[12][0-9]|3[01])',ep.name)"
    assert original.count(old_pattern)==1
    with (R/'runtime.py').open('xb') as f:f.write(original.replace(old_pattern,new_pattern))
    shutil.copyfile(__file__,R/NAME)
    (R/'configs').mkdir();(R/'bin').mkdir()
    with (R/'bin/singularity').open('x') as f:
        f.write(f'#!{PY}\nimport sys\nsys.path.insert(0,{str(R)!r})\nfrom run_collateral_factorial_20261006 import runtime\nruntime().task_runtime()\n')
    os.chmod(R/'bin/singularity',0o700)
    source=read(R/'selection.json')['selected']
    for s in schedule():
        c=source[s['case']];assert c['case']==s['case']
        cfg=read(B/c['batch']/'configs'/f"{c['episode']}.json")
        ep=R/f"episode-{s['index']}";ep.mkdir()
        cfg['id']=f"collateral-{s['index']}";cfg['logger'].update(output_dir=str(ep/'native-log'),write_env_vars=False,use_wandb=False,print_config=False,use_console=False)
        cfg['metadata'].update(seed=s['seed'],base_path=str(R/'source'),git_commit_id=commit,script_id='collateral-factorial-20261006')
        cfg['task'].update(cache_dir=str(R/'no-official-data'),results_output_dir=str(ep/'native-log/results'))
        cfg['interpreter'].update(timeout=240,working_dir=str(ep/'action-0/work'))
        cfg['interpreter']['env'].update(PYTHONHASHSEED=str(s['seed']),HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
        write(R/'configs'/f"{s['index']}.json",cfg)
    batch=f'''#!/bin/bash
#SBATCH --job-name=collateral-factorial
#SBATCH --partition=gpu_24h
#SBATCH --account=gpu
#SBATCH --qos=gpu
#SBATCH --nodelist=gpu27
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:2
#SBATCH --cpus-per-task=12
#SBATCH --time=02:00:00
#SBATCH --no-requeue
set -euo pipefail
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1
timeout --signal=TERM --kill-after=20s 7120s {PY} -B {R}/{NAME} controller
'''
    with (R/'run.sbatch').open('x') as f:f.write(batch)
    write(R/'plan.json',dict(protocol='numeric-bundle-four-vertex-v1',source_commit=commit,selection_sha256=SELECTION,
        schedule=schedule(),files={str(p.relative_to(R)):sha(p) for p in R.rglob('*') if p.is_file()},
        task_image_sha256=read(DONOR/'preflight.json')['task_image_sha256'],program_seconds=240,worker_seconds=390,
        step_seconds=420,allocation_seconds=7200,gpus=2,gpu_hours_cap=4,paid_api=0,generator_calls=0,base_training=False,
        primary='For each full P/C/CP/PC quartet: CP-P, C-P, CP-C, PC-P and C-CP-PC+P, all in higher-is-better units. Rescue=CP>P and C<=P; report all paired values and failure denominators, not only rescues.',
        cost='All 32 executions and failures counted. Diagnostic spends four executions/edge, not a same-budget search comparison.',
        limitation='Old examined development data; 4 edits per task are not 4 independent tasks/parents. Remainder includes all untransplanted code, not proven semantic idea. No novelty, generalization or automatic expansion claim.',
        outcome_timing='No external dev scoring until all assigned workers close and prediction hashes freeze. No protected/final test.',
        resume='Immutable per-program completion. No automatic retries or changed caps; never overwrite original results.'))
    m=runtime();from dojo.config_dataclasses.run import RunConfig
    fairness={}
    for s in schedule():
        cfg=RunConfig.load_from_json(R/'configs'/f"{s['index']}.json");cfg.validate()
        assert cfg.task.name==s['task'] and not Path(cfg.task.private_dir).exists()
        assert cfg.task.data_dir==cfg.task.public_dir and '/search-only-dev-' in cfg.task.data_dir
        assert not cfg.interpreter.read_only_binds
        assert sha(cfg.task.search_only_dev_scorer_path)==cfg.task.search_only_dev_scorer_sha256
        # All task data, isolation and interpreter scientific settings identical within a quartet.
        x=read(R/'configs'/f"{s['index']}.json");t=copy.deepcopy(x['task']);t.pop('results_output_dir',None)
        it=copy.deepcopy(x['interpreter']);it.pop('working_dir',None)
        sig=json.dumps([t,it],sort_keys=True)
        assert s['case'] not in fairness or fairness[s['case']]==sig;fairness[s['case']]=sig
    for i in range(32):assert re.fullmatch('episode-(?:[0-9]|[12][0-9]|3[01])',f'episode-{i}')
    assert not re.fullmatch('episode-(?:[0-9]|[12][0-9]|3[01])','episode-32')
    subprocess.run(['bash','-n',str(R/'run.sbatch')],check=True)
    write(R/'preflight.json',dict(status='PASS',typed_configs=len(schedule()),matched_quartets=len(fairness),
        plan_sha256=sha(R/'plan.json'),source_variants_frozen=True,program_cap_matches_historical_cost_screen=True,
        notes='Existing verified task runtime/image reused; expanded episode allowlist only. No repeated G0 or generator/model acceptance.'))
    print(json.dumps(dict(status='PREPARED',programs=len(schedule()),plan_sha256=sha(R/'plan.json'),gpu_hours_cap=4)))
def submit():
    p=check();m=runtime();assert read(R/'preflight.json')['plan_sha256']==sha(R/'plan.json')
    assert sha(m.TASK_IMAGE)==p['task_image_sha256']
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    jobs=subprocess.check_output(['squeue','-u','yzyang4','-h','-o','%i'],env=env,text=True,timeout=25).split();assert not set(jobs)-{'12535'}
    with (R/'capacity.tmp').open('xb') as f:os.posix_fallocate(f.fileno(),0,64*1024**2)
    (R/'capacity.tmp').unlink();write(R/'submit-intent.json',dict(plan_sha256=sha(R/'plan.json')))
    q=subprocess.run(['sbatch','--parsable','--chdir='+str(R),'--output='+str(R/'allocation-%j.out'),'--error='+str(R/'allocation-%j.err'),str(R/'run.sbatch')],env=env,capture_output=True,text=True,timeout=25)
    job=q.stdout.strip().split(';')[0];assert q.returncode==0 and job.isdigit(),'ambiguous submission: no retry'
    write(R/'launch.json',dict(job=job,plan_sha256=sha(R/'plan.json')));print(json.dumps(dict(job=job,status='SUBMITTED',gpu_hours_cap=4)))
def worker(i):
    p=check();m=runtime();x=m.infra();s=schedule()[i];ep=R/f'episode-{i}';own=x.native_uuids(1)
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
    action=ep/'action-0';(action/'work').mkdir(parents=True);start=time.monotonic();interp=None;out=None;error=None;valid=False
    source=R/f"case-{s['case']}.private"/(s['arm']+'.py');assert sha(source)==s['code_sha256']
    code=source.read_text();seed=s['seed']
    executable=f'import random as _r\nimport numpy as _np\n_r.seed({seed})\n_np.random.seed({seed})\n'+f'exec(compile({code!r},"solution.py","exec"))\n'
    try:
        with ExperimentDeadline(390).activate():
            interp=build(copy.deepcopy(cfg.interpreter),INTERPRETER_MAP,data_dir=cfg.task.data_dir)
            out=interp.run(executable,reset_session=False)
            terminal='\n'.join(out.term_out or []);assert not SECRET.search(terminal.encode())
            write(action/'terminal.private.json',dict(terminal=terminal))
            path=action/'work/submission.csv'
            try:
                interp.fetch_file(path)
                if path.is_file() and not path.is_symlink():shutil.copyfile(path,action/'submission.private.csv')
            except FileNotFoundError:pass
            valid=out.exit_code==0 and not out.timed_out and (action/'submission.private.csv').is_file()
    except Exception as exc:error=type(exc).__name__
    finally:
        if interp is not None:
            try:interp.close()
            except Exception as exc:error='cleanup_'+type(exc).__name__;valid=False
    write(ep/'completed.json',dict(**s,valid_execution=valid,error_type=error,exit_code=out.exit_code if out else None,
        timed_out=out.timed_out if out else None,exec_seconds=out.exec_time if out else None,
        seconds=time.monotonic()-start,source_commit=p['source_commit'],
        prediction_sha256=sha(action/'submission.private.csv') if (action/'submission.private.csv').exists() else None))
def controller():
    check();m=runtime();assert read(R/'launch.json')['job']==os.environ['SLURM_JOB_ID']
    def one(i):
        ep=R/f'episode-{i}';assert not (ep/'native.json').exists()
        cmd=['srun','--exclusive','--nodes=1','--ntasks=1','--cpus-per-task=6','--gres=gpu:1','--time=00:07:00',str(PY),'-B',str(R/NAME),'worker','--index',str(i)]
        with (ep/'worker.private.log').open('xb') as f:q=subprocess.run(cmd,env=m.infra().clean_env(),stdout=f,stderr=f)
        write(ep/'closed.json',dict(returncode=q.returncode));return q.returncode
    with ThreadPoolExecutor(max_workers=2) as pool:codes=list(pool.map(one,range(len(schedule()))))
    write(R/'closed.json',dict(returncodes=codes,assigned=len(schedule())))
def status():
    check();print(json.dumps(dict(launch=read(R/'launch.json') if (R/'launch.json').exists() else None,closed=(R/'closed.json').exists(),
        assigned=len(schedule()),started=sum((R/f"episode-{s['index']}/native.json").exists() for s in schedule()),
        completed=sum((R/f"episode-{s['index']}/completed.json").exists() for s in schedule()),
        workers_closed=sum((R/f"episode-{s['index']}/closed.json").exists() for s in schedule()))))
if __name__=='__main__':
    os.umask(0o077);p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','submit','worker','controller','check','status']);p.add_argument('--commit');p.add_argument('--index',type=int);a=p.parse_args()
    if a.mode=='prepare':prepare(a.commit)
    elif a.mode=='worker':worker(a.index)
    else:globals()[a.mode]()
