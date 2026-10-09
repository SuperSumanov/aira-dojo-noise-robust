"""Four fresh 3000s native trajectories: exposure qualification, NOT A/B gain.

Same2 legal dev tasks, original root breadth5, model, image and width2. Four
new seeds fixed before outcomes. One allocation3GPUx65min <=3.25GPUh all-in.
No candidate selection/replacement; all4 retained. Prior gates stay closed.
"""
import argparse
import inspect
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import subprocess
import sys
import time

import live_27b_trial
from lifecycle_pilot import read,write,sha

t=live_27b_trial.trial
t.R=t.B/'scheduling-live-exposure-20261009-v1'
t.NAME='live_exposure_trial.py'
t.CAP=3900
t.FIXED_BLOCK_SECONDS=3900  # Enables identical physical-resource audits only.
t.GENERATOR_ELIGIBILITY_GATE=False
t.NODE_QUALIFICATION=False
t.PHYSICAL_CPU_BINDING=True
t.ADMISSION_LIMITS={'share2':2}
D=t.B/'scheduling-live-search-20261009-v7'
DONOR='86aa8f7a3d534ef1eaaa5475482a8838fe29c06f1ee30cb367cc05aae411c774'
SECONDS=3000


def schedule():
    return [dict(index=i,block=0,arm='share2',repeat=0,slot=i,task=t.TASKS[i%2],seed=174901+i) for i in range(4)]
t.schedule=schedule

source=inspect.getsource(t.host)
anchor='    source=inspect.getsource(m.worker)'
if source.count(anchor)!=1:raise ValueError('native worker assembly interface')
source=source.replace(anchor,anchor+"\n    source=replace_once(source,\"TIME_LIMIT='10 minutes',TIME_LIMIT_SECS='600'\",\"TIME_LIMIT='50 minutes',TIME_LIMIT_SECS='3000'\")")
if source.count('m.SECONDS=600')!=1:raise ValueError('native deadline assembly interface')
source=source.replace('m.SECONDS=600','m.SECONDS=3000')
exec(compile(source,'exposure-native-host','exec'),t.__dict__)
original_host=t.host
def host():
    m=original_host();m.SECONDS=SECONDS
    return m
t.host=host

# Preserve tested native lifecycle; only the explicit run/time metadata changes.
source=inspect.getsource(t.run_one)
if source.count('timeout=690')!=1:raise ValueError('worker deadline interface')
exec(compile(source.replace('timeout=690','timeout=3090'),'exposure-worker-supervisor','exec'),t.__dict__)
source=inspect.getsource(t.cpu)
if source.count('cfg.solver.time_limit_secs!=600')!=1:raise ValueError('CPU qualification interface')
source=source.replace('cfg.solver.time_limit_secs!=600','cfg.solver.time_limit_secs!=3000')
source=source.replace('configs=16,native_solvers_instantiated=16','configs=4,native_solvers_instantiated=4')
exec(compile(source,'exposure-config-preflight','exec'),t.__dict__)


def prepare(commit):
    if not re.fullmatch('[a-f0-9]{40}',commit) or sha(D/'plan.json')!=DONOR or read(D/'closed.json')['complete']!=16:
        raise ValueError('closed exact donor')
    old=read(D/'plan.json');R=t.R;R.mkdir(mode=0o700,exist_ok=False)
    for name,pin in old['files'].items():
        if not (name.startswith(('source/','opencl-vendors/')) or ('/' not in name and name.endswith('.py'))):continue
        if sha(D/name)!=pin:raise ValueError('donor source drift')
        out=R/name;out.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(D/name,out)
    names=set(t.FILES)|{t.NAME,'live_27b_trial.py','live_identity.py'}
    for name in names:shutil.copyfile(Path(__file__).with_name(name),R/name)
    (R/'configs').mkdir();(R/'bin').mkdir();(R/'block-0/service-cache/tmp').mkdir(parents=True)
    (R/'service-cache/tmp').mkdir(parents=True)
    (R/'bin/singularity').write_text(f'#!{t.PY}\nimport sys\nsys.path.insert(0,{str(R)!r})\nfrom live_exposure_trial import host\nhost().task_runtime()\n')
    os.chmod(R/'bin/singularity',0o700)
    with (R/'.service.env').open('x') as f:f.write('PRIMARY_KEY_QWEN3_8_27B='+secrets.token_hex(32)+'\n')
    os.chmod(R/'.service.env',0o600)
    for row in schedule():
        ep=R/f'episode-{row["index"]}';ep.mkdir()
        name=f'configs/{row["index"]}.json'
        if sha(D/name)!=old['files'][name]:raise ValueError('donor config drift')
        cfg=read(D/name)
        if cfg['task']['name']!=row['task'] or cfg['solver']['num_children']!=5:raise ValueError('original search policy')
        cfg['id']='r14-exposure-'+str(row['index'])
        cfg['metadata'].update(seed=row['seed'],script_id='r14-exposure-20261009',base_path=str(R/'source'))
        cfg['logger'].update(output_dir=str(ep/'native-log'),write_env_vars=False,use_console=False,print_config=False,use_wandb=False)
        cfg['solver'].update(checkpoint_path=str(ep/'checkpoint'),time_limit_secs=SECONDS)
        cfg['task'].update(results_output_dir=str(ep/'native-task-results'),cache_dir=str(R/'no-official-data'))
        cfg['interpreter']['working_dir']=str(ep/'work');cfg['interpreter']['env']['PYTHONHASHSEED']=str(row['seed'])
        for op in cfg['solver']['operators'].values():op['llm']['generation_kwargs']['seed']=row['seed']
        write(R/f'configs/{row["index"]}.json',cfg)
    for paths in ('public_inputs','model_files'):
        for name,pin in old[paths].items():
            if sha(name)!=pin:raise ValueError('pinned input/model drift')
    batch=f'''#!/bin/bash
#SBATCH --job-name=r14-search-exposure
#SBATCH --partition=gpu_24h
#SBATCH --account=gpu
#SBATCH --qos=gpu
#SBATCH --nodelist=gpu27
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:3
#SBATCH --cpus-per-task=18
#SBATCH --hint=nomultithread
#SBATCH --time=01:05:00
#SBATCH --no-requeue
set -euo pipefail
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1
timeout --signal=TERM --kill-after=20s 3820s {t.PY} -B {R/t.NAME} controller
'''
    (R/'run.sbatch').write_text(batch)
    write(R/'plan.json',dict(source_commit=commit,source_dojo_commit=old['source_dojo_commit'],donor_plan_sha256=DONOR,
        schedule=schedule(),allocation_seconds=3900,gpus=3,gpu_hours_cap=3.25,node='gpu27',
        run_seconds=SECONDS,candidate_timeout_seconds=240,physical_cpu_binding=True,fixed_block_seconds=3900,
        generator_eligibility_gate=False,admission_limits=t.ADMISSION_LIMITS,prerequisite_receipts={},
        used_model=t.MODEL_ID,task_image_sha256=old['task_image_sha256'],service_image_sha256=old['service_image_sha256'],
        model_files=old['model_files'],public_inputs=old['public_inputs'],model_training=False,paid_api=False,
        question='At a fixed longer budget, does unmodified native root-breadth5 search reach completed Improve execution and use its feedback on both legal development tasks?',
        scope='Single-arm4-run exposure qualification, not a same-budget comparison with v7 and not a quality/scheduling improvement claim. Prompt time budget also changes; cannot treat long traces as counterfactual continuations of v7.',
        decision='Retain4 regardless of score; qualify only if all4 clean and each task has at least one completed Improve node with external feedback. No replacement seeds or automatic effect trial; all failures charged.',
        warmup='One common8-token service health request; all service startup/idle/cleanup charged. No repeated GPU/model acceptance.',
        boundary='Only current Pizza/Spooky legal dev adapters. No first960/Target300/Target522/D_val/officialtest. No base/critic training, no paid API, no candidate content export.',
        files={str(p.relative_to(R)):sha(p) for p in R.rglob('*') if p.is_file() and p.name!='.service.env'}))
    t.cpu();m=host()
    if m.SECONDS!=SECONDS or '50 minutes' not in m.worker.__code__.co_consts or '3000' not in m.worker.__code__.co_consts:
        raise ValueError('native prompt/deadline drift')
    if sha(m.TASK_IMAGE)!=old['task_image_sha256'] or sha(m.VLLM)!=old['service_image_sha256']:raise ValueError('image drift')
    write(R/'preflight.json',dict(plan_sha256=sha(R/'plan.json'),configs=4,native_seconds=m.SECONDS,
        model_calls=0,gpu_executions=0,images_verified=True,inputs_verified=True,training_items_not_applicable=True))
    print(json.dumps(dict(status='PREPARED',plan_sha256=sha(R/'plan.json'),assigned=4,seconds=SECONDS,gpu_hours_cap=3.25)))


def submit():
    t.check();R=t.R
    if read(R/'preflight.json')['plan_sha256']!=sha(R/'plan.json'):raise ValueError('preflight drift')
    env=host().infra().clean_env()
    jobs=subprocess.check_output(['squeue','-u','yzyang4','-h','-o','%i'],env=env,text=True,timeout=20).split()
    if set(jobs)-{'12535'}:raise ValueError('unexpected active job; no overlap')
    write(R/'submit-intent.json',dict(plan_sha256=sha(R/'plan.json'),gpu_hours_cap=3.25))
    p=subprocess.run(['sbatch','--parsable','--chdir='+str(R),'--output='+str(R/'allocation-%j.out'),
        '--error='+str(R/'allocation-%j.err'),str(R/'run.sbatch')],env=env,capture_output=True,text=True,timeout=25)
    job=p.stdout.strip().split(';')[0]
    if p.returncode or not job.isdigit():raise RuntimeError('ambiguous submit; do not retry')
    write(R/'launch.json',dict(job=job,plan_sha256=sha(R/'plan.json')))
    print(json.dumps(dict(status='SUBMITTED',job=job,gpu_hours_cap=3.25)))


def controller():
    t.check();m=host();m.setup();R=t.R;start=time.monotonic();job=os.environ['SLURM_JOB_ID']
    if socket.gethostname().split('.')[0]!='gpu27':raise ValueError('node')
    for _ in range(40):
        if (R/'launch.json').exists():break
        time.sleep(.25)
    if read(R/'launch.json')['job']!=job:raise ValueError('job identity')
    env=m.infra().clean_env();base=['srun','--exclusive','--nodes=1','--ntasks=1','--hint=nomultithread']
    error=None;attempted=[];server=None
    try:
        with (R/'block-0/service.private.log').open('xb') as log:
            server=subprocess.Popen(base+['--cpus-per-task=12','--gres=gpu:2','--time=01:04:00',str(t.PY),'-B',str(R/t.NAME),'service'],
                env=dict(env,R14_BLOCK='0'),stdout=log,stderr=log,start_new_session=True)
            try:
                ready=time.monotonic()
                while time.monotonic()-ready<600:
                    if server.poll() is not None:raise RuntimeError('service exited')
                    try:
                        if m.health():break
                    except Exception:pass
                    time.sleep(2)
                else:raise TimeoutError('service startup')
                out=m.api('/v1/chat/completions',dict(model=t.MODEL_ID,messages=[dict(role='user',content='Reply with OK only.')],
                    max_tokens=8,temperature=0,seed=174900,chat_template_kwargs={'enable_thinking':False}),timeout=40)
                if out.get('model')!=t.MODEL_ID or not out.get('choices'):raise ValueError('service identity')
                write(R/'block-0/service-ready.json',dict(startup_seconds=time.monotonic()-ready,model=t.MODEL_ID))
                if 3900-(time.monotonic()-start)<3300:raise TimeoutError('full search + cleanup reserve')
                attempted=[0]
                with (R/'block-0/block.private.log').open('xb') as log2:
                    result=subprocess.run(base+['--cpus-per-task=6','--gres=gpu:1','--time=00:54:00',str(t.PY),'-B',str(R/t.NAME),'block'],
                        env=env,stdout=log2,stderr=log2,timeout=3210)
                if result.returncode:raise ValueError('block infrastructure failure')
            finally:t.stop_service(server,0,job)
    except Exception as exc:error=type(exc).__name__
    finally:
        rows=[]
        for row in schedule():
            ep=R/f'episode-{row["index"]}';v=dict(**row,status='not_started')
            if (ep/'closed.json').exists():v.update(read(ep/'closed.json'));v['status']='failed'
            if (ep/'finished.json').exists():
                end=read(ep/'finished.json');v.update(end)
                v['status']='complete' if v.get('returncode')==0 and v.get('cleanup_verified') and end['status'] in ('completed','budget_exhausted') else 'incomplete'
            rows.append(v)
        write(R/'runs.json',rows)
        write(R/'closed.json',dict(planned=4,attempted_blocks=attempted,complete=sum(r['status']=='complete' for r in rows),
            controller_error=error,elapsed_seconds=time.monotonic()-start,service_closed=server is None or server.poll() is not None))
    return 0 if error is None else 1


if __name__=='__main__':
    os.umask(0o077);os.environ.update(PYTHON_DOTENV_DISABLED='1',PYTHONDONTWRITEBYTECODE='1')
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','submit','controller','service','block','worker'])
    p.add_argument('--commit');p.add_argument('--index',type=int);a=p.parse_args()
    if a.mode=='prepare':prepare(a.commit)
    elif a.mode=='worker':
        if a.index not in range(4):raise ValueError('fixed4 index')
        sys.exit(host().worker(a.index))
    elif a.mode=='service':host().service()
    elif a.mode=='block':sys.exit(t.block_run(0))
    else:sys.exit(globals()[a.mode]())
