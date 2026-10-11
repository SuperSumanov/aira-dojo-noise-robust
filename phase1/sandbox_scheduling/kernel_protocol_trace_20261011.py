"""48 fixed CPU-only kernels; restore gateway observability, not a fix claim.

Six persistent hosts x8 rounds. Keep single-query original client handshake.
No execute retry. Readiness failures are observations; resource failure stops.
"""
import ast
from collections import Counter
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import threading
import time
import resource_diag_20261011 as d

ROOT=d.BASE/'resource-kernel-protocol-20261011-v1'
DONOR=d.BASE/'resource-persistent-hosts-20261011-v1'
PIN='8435e7595bc316fc4ee08b8e48a710adc5b5bcc5529dcad1bb88336f607d62cb'
NAME=Path(__file__).name
d.ROOT=ROOT;d.NAME=NAME
WIDTH=6;ROUNDS=8;CAP=1800


def observer_class(source):
    node=next(n for n in ast.parse(source).body if isinstance(n,ast.ClassDef) and n.name=='Observer')
    scope=dict(Counter=Counter,time=time)
    exec(compile(ast.Module(body=[node],type_ignores=[]),'existing-enum-observer','exec'),scope)
    return scope['Observer']


def direct_counter(source):
    before="if __name__=='__main__':runpy.run_module('jupyter',run_name='__main__')"
    after="if __name__=='__main__':\n    from kernel_gateway.gatewayapp import KernelGatewayApp\n    KernelGatewayApp.launch_instance(argv=__import__('sys').argv[2:])"
    assert source.count(before)==1
    return source.replace(before,after)


def prepare():
    assert d.sha(DONOR/'plan.json')==PIN and (DONOR/'closed.json').exists()
    old=json.loads((DONOR/'plan.json').read_text());ROOT.mkdir(mode=0o700)
    for name,pin in old['files'].items():
        if not(name.startswith('source/') or name in ('resource_diag_20261011.py','resource_pressure.py')):continue
        assert d.sha(DONOR/name)==pin
        target=ROOT/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(DONOR/name,target)
    for name in (NAME,'readiness_transport_trial.py','gateway_counter.py'):
        shutil.copyfile(Path(__file__).with_name(name),ROOT/name)
    counter=direct_counter((ROOT/'gateway_counter.py').read_text())
    (ROOT/'gateway_counter_direct.py').write_text(counter)
    for r in range(ROUNDS):
        for s in range(WIDTH):
            ep=ROOT/f'block-{r}-worker-{s}';ep.mkdir();(ep/'gateway_counter.py').write_text(counter)
    d.configure()
    from dojo.core.interpreters.jupyter.jupyter_client import JupyterKernelClient
    assert callable(JupyterKernelClient.wait_for_ready)
    batch=f'''#!/bin/bash
#SBATCH --job-name=resource-kernel-protocol
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
    d.write(ROOT/'plan.json',dict(source_commit=d.SOURCE,donor_plan_sha256=PIN,planned=48,width=6,rounds=8,
        schedule=[dict(round=r,slot=s) for r in range(8) for s in range(6)],gpus=1,gpu_seconds_cap=CAP,
        node='gpu1',physical_cpu_budget=6,task_image_sha256=d.IMAGE_SHA,seed=101101,
        question='Where does a missing kernel-info reply stop: client, gateway incoming, gateway outgoing, nudge or resource exhaustion?',
        changes='Gateway direct entry retains existing diagnostic counter; original single-query client retained; enum-only observation. No timeout or candidate retry.',
        stop='Fixed48; record readiness failures without replacement; stop on resource markers, worker crash,210s round or whole budget. No performance/quality gate.',
        no_task_data=True,no_model=True,no_cuda=True,no_paid_api=True,no_base_update=True,
        prerequisite='Original/direct --help identical in prior exact-image probe; actual forwarding counters must exist before claiming observer success.',
        limits=['instrumented entry is not unchanged production','no model baseline pressure','48 same arithmetic kernels not independent ML trials'],
        files={str(p.relative_to(ROOT)):d.sha(p) for p in ROOT.rglob('*') if p.is_file() and '__pycache__' not in p.parts}))
    print(json.dumps(dict(prepared=True,plan_sha256=d.sha(ROOT/'plan.json'),planned=48,gpu_seconds_cap=CAP)))


def slot(index):
    d.configure()
    from dojo.core.interpreters.jupyter import singularity_jupyter_server as server
    from dojo.core.interpreters.jupyter.jupyter_client import JupyterKernelClient
    build=server._build_singularity_command
    server._JUPYTER_BOOTSTRAP="import runpy;runpy.run_path('/workspace/gateway_counter.py',run_name='__main__')"
    original=JupyterKernelClient.wait_for_ready
    Observer=observer_class((ROOT/'readiness_transport_trial.py').read_text())
    calls=[]
    def observed(self,timeout_seconds=None):
        proxy=Observer(self);begin=time.monotonic();ok=None;error=None
        try:ok=original(proxy,timeout_seconds);return ok
        except Exception as exc:error=type(exc).__name__;raise
        finally:calls.append(dict(ready=ok,error_type=error,seconds=time.monotonic()-begin,**proxy.state()))
    JupyterKernelClient.wait_for_ready=observed
    d.write(ROOT/f'host-{index}-baseline.json',d.resource_pressure.snapshot())
    for r in range(ROUNDS):
        end=time.monotonic()+230
        while not (ROOT/f'round-{r}-go.json').exists():
            if (ROOT/'STOP').exists():return 2
            if time.monotonic()>end:raise TimeoutError('round start')
            time.sleep(.1)
        calls.clear()
        try:rc=d.worker(r,index)
        finally:server._build_singularity_command=build
        ep=ROOT/f'block-{r}-worker-{index}'
        flags=json.loads((ep/'error-categories.json').read_text()) if (ep/'error-categories.json').exists() else {}
        resource_failure=any(flags.get(k,False) for k in ('resource temporarily unavailable','cannot allocate memory',"can't start new thread",'pthread_create'))
        time.sleep(.5)
        target=ROOT/f'round-{r}-slot-{index}.json';tmp=target.with_suffix('.tmp')
        d.write(tmp,dict(round=r,slot=index,returncode=rc,calls=list(calls),resource_failure=resource_failure,
            gateway_counts_present=(ep/'gateway-counts.json').exists(),snapshot=d.resource_pressure.snapshot()))
        os.replace(tmp,target)
        if resource_failure:return 3
    return 0


def controller():
    p=json.loads((ROOT/'plan.json').read_text())
    for n,h in p['files'].items():assert d.sha(ROOT/n)==h
    begin=time.monotonic();procs=[];logs=[];error=None;rounds=0;stop=threading.Event()
    def sample():
        with (ROOT/'pressure.jsonl').open('x') as f:
            while not stop.is_set():f.write(json.dumps(d.resource_pressure.snapshot())+'\n');f.flush();stop.wait(1)
    monitor=threading.Thread(target=sample,daemon=True);monitor.start()
    try:
        for s in range(WIDTH):
            log=(ROOT/f'host-{s}.private.log').open('x');logs.append(log)
            procs.append(subprocess.Popen([str(d.PY),'-B',str(ROOT/NAME),'slot',str(s)],stdout=log,stderr=log,start_new_session=True))
        for r in range(ROUNDS):
            if time.monotonic()-begin>CAP-250:raise TimeoutError('whole budget reserve')
            d.write(ROOT/f'round-{r}-go.json',dict(time=time.time()));end=time.monotonic()+210
            paths=[ROOT/f'round-{r}-slot-{s}.json' for s in range(WIDTH)]
            while not all(x.exists() for x in paths):
                if any(proc.poll() is not None and (proc.returncode!=0 or not paths[s].exists()) for s,proc in enumerate(procs)):raise RuntimeError('host exited')
                if time.monotonic()>end:raise TimeoutError('round')
                time.sleep(.3)
            values=[json.loads(x.read_text()) for x in paths];rounds+=1
            d.write(ROOT/f'round-{r}-after.json',d.resource_pressure.snapshot())
            if any(v['resource_failure'] for v in values):raise RuntimeError('resource failure')
            if not all(v['gateway_counts_present'] for v in values):raise RuntimeError('observer missing')
        for proc in procs:assert proc.wait(timeout=10)==0
    except Exception as exc:error=type(exc).__name__
    finally:
        (ROOT/'STOP').touch()
        for proc in procs:
            try:proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid,signal.SIGTERM)
                try:proc.wait(timeout=5)
                except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait(timeout=5)
        for log in logs:log.close()
        stop.set();monitor.join(timeout=5)
        done=[json.loads(x.read_text()) for x in ROOT.glob('block-*-worker-*/complete.json')]
        d.write(ROOT/'controller-after.json',d.resource_pressure.snapshot())
        d.write(ROOT/'closed.json',dict(planned=48,attempted=len(list(ROOT.glob('block-*-worker-*/host-before.json'))),
            complete=sum(v['complete'] for v in done),observed=len(done),rounds=rounds,error_type=error,host_returncodes=[p.returncode for p in procs]))
    return int(error is not None)


if __name__=='__main__':
    os.umask(0o077)
    if sys.argv[1]=='prepare':prepare()
    elif sys.argv[1]=='controller':sys.exit(controller())
    elif sys.argv[1]=='slot':sys.exit(slot(int(sys.argv[2])))
    else:raise ValueError('mode')
