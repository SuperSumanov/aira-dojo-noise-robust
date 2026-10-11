"""Six persistent hosts x32 kernel lifetimes, not192 independent ML trials.

Reuse the already measured CPU-only task-image arithmetic diagnostic. No task
data, CUDA, model, API or quality. One unused GPU is required by site QOS.
Do not infer historical cause merely from an observed long-run trend.
"""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
import resource_diag_20261011 as d

ROOT=d.BASE/'resource-persistent-hosts-20261011-v1'
DONOR=d.BASE/'resource-diag-readiness-fixed-20261011-v1'
PIN='21a063ca6ca7b4d25822b963cd55533ed1ea276caabdc6e4b0cb958fbae30858'
NAME=Path(__file__).name
d.ROOT=ROOT;d.NAME=NAME
ROUNDS=32;WIDTH=6;CAP=1800


def schedule():return [dict(round=r,slot=s) for r in range(ROUNDS) for s in range(WIDTH)]


def premature_exit(returncodes, receipts):
    # A fast host may finish its final round while peers are still completing.
    return any(rc is not None and (rc != 0 or not receipt)
               for rc, receipt in zip(returncodes, receipts, strict=True))


def prepare():
    assert d.sha(DONOR/'plan.json')==PIN
    old=json.loads((DONOR/'plan.json').read_text())
    assert json.loads((DONOR/'closed.json').read_text())['complete']==14
    ROOT.mkdir(mode=0o700)
    for name,pin in old['files'].items():
        if not(name.startswith('source/') or name in ('resource_diag_20261011.py','resource_pressure.py')):continue
        assert d.sha(DONOR/name)==pin
        target=ROOT/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(DONOR/name,target)
    shutil.copyfile(__file__,ROOT/NAME)
    for r in schedule():(ROOT/f"block-{r['round']}-worker-{r['slot']}").mkdir()
    batch=f'''#!/bin/bash
#SBATCH --job-name=resource-persistent-hosts
#SBATCH --partition=gpu_24h
#SBATCH --account=gpu
#SBATCH --qos=gpu
#SBATCH --nodelist=gpu1
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=6
#SBATCH --hint=nomultithread
#SBATCH --time=00:30:00
#SBATCH --no-requeue
set -euo pipefail
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1
timeout --signal=TERM --kill-after=15s 1760s srun --exclusive --ntasks=1 --gres=gpu:1 --cpus-per-task=6 --hint=nomultithread {d.PY} -B {ROOT}/{NAME} controller
'''
    (ROOT/'run.sbatch').write_text(batch);subprocess.run(['bash','-n',str(ROOT/'run.sbatch')],check=True)
    d.write(ROOT/'plan.json',dict(source_commit=d.SOURCE,donor_plan_sha256=PIN,
        question='Do six persistent host processes accumulate threads or descriptors across32 normal kernel lifetimes?',
        schedule=schedule(),planned=ROUNDS*WIDTH,rounds=ROUNDS,width=WIDTH,gpus=1,cpus=6,node='gpu1',
        gpu_seconds_cap=CAP,allocation_seconds_cap=CAP,actual_gpu_computation=False,site_qos_requires_reserved_gpu=True,
        original_task_image_sha256=d.IMAGE_SHA,source_seed=101101,threads_per_library=3,
        source_changes='Readiness fix only in exact f7; cleanup-exception patch excluded. Restore test-only command shim after each call; no forced GC.',
        matrix='Six fixed host processes, each32 consecutive original diagnostic kernels; all-worker barrier before every round.',
        primary='Full192 denominator, per-host steady threads/FD before and after every lifetime, group UID counts after each all-worker barrier; report trends, not a binary universal leak claim.',
        stop='Any worker/cycle failure or210s round deadline closes remaining rounds; no retries/replacements or extra rounds.',
        no_paid_api=True,no_task_data=True,no_quality=True,no_base_update=True,no_model_service=True,
        limitations=['CPU-only arithmetic, not DataLoader/candidate/error-path stress','absence of growth does not exclude production-specific leaks','no model-serving baseline pressure','restarts are same fixed synthetic code/seed'],
        image_reuse='Pinned existing read-only image already fully hashed this window; no concurrent large-file hashing while17554 measures.',
        files={str(p.relative_to(ROOT)):d.sha(p) for p in ROOT.rglob('*') if p.is_file() and '__pycache__' not in p.parts}))
    print(json.dumps(dict(prepared=True,plan_sha256=d.sha(ROOT/'plan.json'),planned=ROUNDS*WIDTH,gpu_seconds_cap=CAP)))


def slot(index):
    d.configure()
    from dojo.core.interpreters.jupyter import singularity_jupyter_server as server
    from dojo.core.interpreters.jupyter.jupyter_code_executor import JupyterCodeExecutor
    build=server._build_singularity_command
    d.write(ROOT/f'host-{index}-baseline.json',d.resource_pressure.snapshot())
    for r in range(ROUNDS):
        deadline=time.monotonic()+230
        while not (ROOT/f'round-{r}-go.json').exists():
            if (ROOT/'STOP').exists():return 2
            if time.monotonic()>deadline:raise TimeoutError('round start')
            time.sleep(.1)
        try:rc=d.worker(r,index)
        finally:
            # Original helper is designed for a fresh process; without restore,
            # its test-only wrapper would stack and try to remove --nv twice.
            server._build_singularity_command=build
        time.sleep(.5)
        d.write(ROOT/f'round-{r}-slot-{index}.json',dict(round=r,slot=index,returncode=rc,
            snapshot=d.resource_pressure.snapshot()))
        if rc:return rc
    return 0


def controller():
    p=json.loads((ROOT/'plan.json').read_text())
    for name,pin in p['files'].items():assert d.sha(ROOT/name)==pin
    started=time.monotonic();processes=[];logs=[];error=None;rounds=0
    d.write(ROOT/'controller-before.json',d.resource_pressure.snapshot())
    try:
        for i in range(WIDTH):
            log=(ROOT/f'host-{i}.private.log').open('x');logs.append(log)
            proc=subprocess.Popen([str(d.PY),'-B',str(ROOT/NAME),'slot',str(i)],stdout=log,stderr=log,start_new_session=True)
            processes.append(proc)
        for r in range(ROUNDS):
            if time.monotonic()-started>CAP-250:raise TimeoutError('remaining whole budget')
            d.write(ROOT/f'round-{r}-go.json',dict(time=time.time()))
            deadline=time.monotonic()+210
            while not all((ROOT/f'round-{r}-slot-{i}.json').exists() for i in range(WIDTH)):
                if premature_exit([x.poll() for x in processes],
                                  [(ROOT/f'round-{r}-slot-{i}.json').exists() for i in range(WIDTH)]):
                    raise RuntimeError('host exited before receipt or with error')
                if time.monotonic()>deadline:raise TimeoutError('round completion')
                time.sleep(.3)
            rows=[json.loads((ROOT/f'round-{r}-slot-{i}.json').read_text()) for i in range(WIDTH)]
            time.sleep(.5);d.write(ROOT/f'round-{r}-after.json',d.resource_pressure.snapshot());rounds+=1
            if any(x['returncode'] for x in rows):raise RuntimeError('kernel failure')
        for process in processes:assert process.wait(timeout=10)==0
    except Exception as exc:error=type(exc).__name__
    finally:
        (ROOT/'STOP').touch(exist_ok=False)
        for process in processes:
            try:process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGTERM)
                try:process.wait(timeout=5)
                except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait(timeout=5)
        for log in logs:log.close()
        complete=[json.loads(x.read_text()) for x in ROOT.glob('block-*-worker-*/complete.json')]
        d.write(ROOT/'controller-after.json',d.resource_pressure.snapshot())
        d.write(ROOT/'closed.json',dict(planned=ROUNDS*WIDTH,attempted=len(list(ROOT.glob('block-*-worker-*/host-before.json'))),
            complete=sum(x['complete'] for x in complete),closed_workers=len(complete),complete_rounds=rounds,
            error_type=error,host_returncodes=[x.returncode for x in processes]))
    return int(error is not None)


if __name__=='__main__':
    os.umask(0o077)
    if sys.argv[1]=='prepare':prepare()
    elif sys.argv[1]=='controller':sys.exit(controller())
    elif sys.argv[1]=='slot':sys.exit(slot(int(sys.argv[2])))
    else:raise ValueError('mode')
