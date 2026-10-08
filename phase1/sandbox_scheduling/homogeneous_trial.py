"""R14: homogeneous ready-pair contention, not new models or independent seeds.

Reuses the exact successful neural worker and public fixtures. Two tasks x
serial/share2 x three restarts x two replicas = 24 executions. <=1.5GPUh.
"""
import argparse
import concurrent.futures as cf
import csv
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import threading
import time

import neural_pool_trial as n
from lifecycle_pilot import read,write,sha

B=Path('/research/d7/spc/yzyang4')
D=B/'scheduling-neural-20261008-v1'
R=B/'scheduling-homogeneous-20261008-v1'
PY=B/'venvs/aira/bin/python'
NAME='homogeneous_trial.py'
DONOR='8da0e849c3203efc2c47c13f134fe9d841ede0f9c3d667789e41ab2aefb95edc'


def schedule():
    rows=[]
    for repeat in range(3):
        for program in ((0,1) if repeat%2==0 else (1,0)):
            for arm in (('serial','share2') if repeat%2==0 else ('share2','serial')):
                for replica in (0,1):
                    rows.append(dict(index=len(rows),program=program,arm=arm,repeat=repeat,
                                     replica=replica,source_seed=42,harness_seed=130701))
    return rows


def configure():
    n.R=R;n.NAME=NAME;n.schedule=schedule
    return n.pilot()


def check():
    p=read(R/'plan.json')
    if p['schedule']!=schedule() or p['gpu_hours_cap']!=1.5:raise ValueError('plan')
    for name,pin in p['files'].items():
        if sha(R/name)!=pin:raise ValueError('frozen source drift')
    for path,pin in p['input_files'].items():
        if sha(path)!=pin:raise ValueError('fixed input drift')
    if os.readlink(Path(p['programs'][0]['data'])/'workspace_cache')!='/workspace/input_cache':raise ValueError('cache contract')
    return p


def prepare(commit):
    if not re.fullmatch('[a-f0-9]{40}',commit) or sha(D/'plan.json')!=DONOR:raise ValueError('donor/source pin')
    old=read(D/'plan.json');closed=read(D/'closed.json')
    if closed['completed']!=12:raise ValueError('donor qualification')
    R.mkdir(mode=0o700,exist_ok=False);inputs={}
    for name,pin in old['files'].items():
        if name.startswith(('data-0/','data-1/')):
            if sha(D/name)!=pin:raise ValueError('donor input drift')
            inputs[str(D/name)]=pin
        elif name not in ('run.sbatch','bin/singularity') and not name.startswith('episode-'):
            if sha(D/name)!=pin:raise ValueError('donor file drift')
            dest=R/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(D/name,dest)
    for name in (NAME,'homogeneous_readout.py','verify_pool_outputs.py'):
        shutil.copyfile(Path(__file__).with_name(name),R/name)
    for i in list(range(24))+[36]:(R/f'episode-{i}/work/input_cache').mkdir(parents=True)
    (R/'empty-data').mkdir();(R/'bin').mkdir()
    (R/'bin/singularity').write_text(f'#!{PY}\nimport sys\nsys.path.insert(0,{str(R)!r})\nfrom homogeneous_trial import configure\nconfigure().task_runtime()\n')
    os.chmod(R/'bin/singularity',0o700)
    batch=(D/'run.sbatch').read_text().replace('r14-neural-v1','r14-homogeneous-v1').replace(str(D),str(R)).replace('neural_pool_trial.py controller',f'{NAME} controller')
    (R/'run.sbatch').write_text(batch)
    plan=dict(source_commit=commit,donor_plan_sha256=DONOR,schedule=schedule(),programs=old['programs'],
              gpu_hours_cap=1.5,gpus=1,total_cpu=6,node='gpu27',allocation_seconds=5400,planned_executions=24,
              candidate_timeout_seconds=450,worker_hard_seconds=550,source_seed=42,harness_seed=130701,
              question='Does fixed concurrency remain beneficial for two identical ready programs, with independent private workspaces?',
              unchanged_source_worker_image_and_inputs=True,shared_candidate_cache=False,
              first_serial_gate='both replicas of each task complete with real CUDA steps, otherwise close batch without replacement',
              decision='Per-task three complete pairs and all twelve outputs; median speedup >=1.05, identical steps, cross-arm maxdiff<=within-arm maxdiff+1e-6 and <=1e-5. Report every task, no pooling or rescued failures.',
              repeat_unit='same-source-seed restart; replicas are deliberate contention load, not independent tasks or training seeds',
              no_api=True,no_base_model_update=True,no_quality_scoring=True,input_files=inputs,
              files={str(p.relative_to(R)):sha(p) for p in R.rglob('*') if p.is_file()})
    write(R/'plan.json',plan)
    m=configure().runtime();image=sha(m.TASK_IMAGE)
    if image!='801f646bed3cae6e74e10d793e71b0086658d4303d54552333c58125ddf9beda':raise ValueError('image drift')
    subprocess.run(['bash','-n',str(R/'run.sbatch')],check=True)
    write(R/'preflight.json',dict(plan_sha256=sha(R/'plan.json'),image_sha256=image,
                                unchanged_neural_worker_sha256=sha(R/'neural_pool_trial.py'),candidate_executions=0))
    print(json.dumps(dict(status='PREPARED',plan_sha256=sha(R/'plan.json'))))


def controller():
    plan=check();p=configure();m=p.runtime();start=time.time();error=None;all_outcomes=[]
    for _ in range(40):
        if (R/'launch.json').exists():break
        time.sleep(.25)
    if read(R/'launch.json')['job']!=os.environ['SLURM_JOB_ID'] or socket.gethostname().split('.')[0]!='gpu27':raise ValueError('allocation identity')
    gpu=m.infra().native_uuids(1)[0]
    write(R/'allocation.json',dict(job=os.environ['SLURM_JOB_ID'],gpu_uuid=gpu,start=start,affinity=sorted(os.sched_getaffinity(0))))
    try:
        if p.gpu_sample(gpu)['apps']:raise ValueError('baseline GPU client')
        if not n.run_one(36)['complete'] or p.gpu_sample(gpu)['apps']:raise ValueError('warmup/release')
        for b in range(12):
            rows=schedule()[2*b:2*b+2];arm=rows[0]['arm'];width=1 if arm=='serial' else 2
            if time.time()-start+(2 if width==1 else 1)*555>5290:raise TimeoutError('whole block budget')
            if p.gpu_sample(gpu)['apps']:raise ValueError('preblock release')
            stop=threading.Event();samples=[];errors=[]
            def observe():
                while not stop.is_set():
                    try:samples.append(p.gpu_sample(gpu))
                    except Exception as exc:errors.append(type(exc).__name__);break
                    stop.wait(.5)
            observer=threading.Thread(target=observe,daemon=True);begin=time.time();observer.start()
            try:
                with cf.ThreadPoolExecutor(max_workers=width) as pool:outcomes=list(pool.map(n.run_one,[r['index'] for r in rows]))
            finally:stop.set();observer.join(timeout=10)
            all_outcomes.extend(outcomes)
            write(R/f'block-{b}.json',dict(block=b,program=rows[0]['program'],arm=arm,repeat=rows[0]['repeat'],start=begin,end=time.time(),outcomes=outcomes,telemetry_errors=errors))
            write(R/f'telemetry-{b}.json',samples)
            if errors or observer.is_alive() or p.gpu_sample(gpu)['apps']:raise ValueError('telemetry/release')
            if rows[0]['repeat']==0 and arm=='serial' and not all(o['complete'] for o in outcomes):raise ValueError('first serial qualification')
    except Exception as exc:error=type(exc).__name__
    finally:
        write(R/'closed.json',dict(planned=24,attempted=len(all_outcomes),completed=sum(o['complete'] for o in all_outcomes),error_type=error,elapsed_seconds=time.time()-start))
    return 1 if error or len(all_outcomes)!=24 or not all(o['complete'] for o in all_outcomes) else 0


def submit():
    check()
    if read(R/'preflight.json')['plan_sha256']!=sha(R/'plan.json'):raise ValueError('preflight drift')
    env=configure().runtime().infra().clean_env()
    jobs=subprocess.check_output(['squeue','-u','yzyang4','-h','-o','%i'],env=env,text=True,timeout=15).split()
    if set(jobs)-{'12535'}:raise ValueError('unexpected active job')
    write(R/'submit-intent.json',dict(plan_sha256=sha(R/'plan.json'),gpu_hours_cap=1.5))
    result=subprocess.run(['sbatch','--parsable','--chdir='+str(R),'--output='+str(R/'allocation-%j.out'),'--error='+str(R/'allocation-%j.err'),str(R/'run.sbatch')],env=env,capture_output=True,text=True,timeout=20)
    job=result.stdout.strip().split(';')[0]
    if result.returncode or not job.isdigit():raise RuntimeError('ambiguous submission; no retry')
    write(R/'launch.json',dict(job=job,plan_sha256=sha(R/'plan.json')))
    print(json.dumps(dict(status='SUBMITTED',job=job,gpu_hours_cap=1.5)))


if __name__=='__main__':
    os.umask(0o077);os.environ.update(PYTHON_DOTENV_DISABLED='1',PYTHONDONTWRITEBYTECODE='1')
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['prepare','submit','controller','worker']);ap.add_argument('--commit');ap.add_argument('--index',type=int);args=ap.parse_args()
    if args.mode=='prepare':prepare(args.commit)
    elif args.mode=='worker':configure();sys.exit(n.worker(args.index))
    else:sys.exit(globals()[args.mode]())
