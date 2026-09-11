"""Bounded service/pool wiring for the fixed seed8/9 development blocks.

No submit command, credential loader, model acceptance or automatic retry.
This module's CLI remains inspection-only. The separate native entry binds the
fixed as-delivered exploratory release; unknown historical template is declared,
not silently assumed correct. CPU tests replace OS boundaries, not outcomes.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
import datetime as dt
import getpass
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

from forets_block_controller_20260911 import (ALLOCATION_SECONDS, CLEANUP_SECONDS,
    STARTUP_SECONDS, BlockPoolControl, inspect_draft)

POOL_SHA = '12fcf5fc727de820a208ca88ee1bd82c58f97842653c3ce463f8b171903d2b79'
PYTHON = '/research/d7/spc/yzyang4/venvs/aira/bin/python'
GPU_PYTHON = '/research/d7/spc/yzyang4/venvs/exp/bin/python'
# No boolean CLI switch or editable draft field can stand in for missing facts.
RELEASE_SHA = 'e7c64f43032901716f4f3d5abf75a3e7d15f6417bd44e7e6e37b5fc5f8983706'
SOURCE_FILES_SHA = 'e72e6f7ad5f500967e1ea243a05afc016a2ae7ad35c9262dedd80bd43d89b84f'


def require_release(raw):
    if RELEASE_SHA is None or hashlib.sha256(raw).hexdigest() != RELEASE_SHA:
        raise RuntimeError('hardware/input release absent; no GPU/API/model dispatch')


def write_once(path, value):
    raw = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False)+'\n').encode()
    with os.fdopen(os.open(path, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600), 'wb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())


def fields(text):
    return dict(re.findall(r'(?:^|\s)([A-Za-z][A-Za-z0-9_/]*)=(\S+)', text))


@dataclass(frozen=True)
class Budget:
    """Monotonic deadlines derived from observed allocation time, not import time."""
    start: float
    end: float
    now: object = time.monotonic

    def left(self, deadline, cap=15):
        remaining = min(cap, deadline-self.now())
        if not math.isfinite(remaining) or remaining <= 0:
            raise TimeoutError('fixed block deadline exhausted')
        return remaining

    @property
    def startup(self): return self.start+STARTUP_SECONDS

    @property
    def work(self): return self.end-CLEANUP_SECONDS


@contextmanager
def interrupt_at(budget, deadline):
    """Bound synchronous application calls on the Linux controller main thread.

    Slurm remains the outer bound; this is not a guarantee against uninterruptible
    kernel I/O. Refuse nesting/another application's alarm rather than erase it.
    """
    if not hasattr(signal, 'setitimer'):
        raise RuntimeError('Linux interval timer required')
    if signal.getitimer(signal.ITIMER_REAL) != (0.0, 0.0):
        raise RuntimeError('another interval timer is active')
    seconds = budget.left(deadline, ALLOCATION_SECONDS)
    def expired(*_): raise TimeoutError('fixed block deadline exhausted')
    previous = signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


@contextmanager
def lifecycle_signals():
    """Startup SIGTERM must unwind into the same cleanup as a running pool."""
    def stop(*_): raise InterruptedError('block controller interrupted')
    previous={s:signal.signal(s,stop) for s in (signal.SIGINT,signal.SIGTERM)}
    try:
        yield
    finally:
        for s,handler in previous.items(): signal.signal(s,handler)


class Scheduler:
    def __init__(self, budget, job, *, run=subprocess.run):
        if not re.fullmatch(r'[0-9]+', job): raise ValueError('exact allocation required')
        self.budget, self.job, self.run = budget, job, run

    def query(self, command, deadline):
        result = self.run(command, capture_output=True, text=True, check=False,
                          timeout=self.budget.left(deadline))
        if result.returncode: raise RuntimeError('scheduler query failed')
        return result.stdout

    def active_owned(self, names, deadline):
        """Only steps in this allocation AND with one of our fixed names."""
        text = self.query(['scontrol', 'show', 'step', self.job, '-o'], deadline)
        owned = []
        for line in text.splitlines():
            row = fields(line)
            step = row.get('StepId', '')
            if row.get('Name') in names and re.fullmatch(re.escape(self.job)+r'\.[0-9]+', step):
                owned.append(step)
        if len(set(owned)) != len(owned): raise RuntimeError('duplicate scheduler step')
        return owned

    def cancel(self, steps, deadline):
        for step in steps:
            if not re.fullmatch(re.escape(self.job)+r'\.[0-9]+', step):
                raise ValueError('refuse cancellation outside owned allocation step')
            self.query(['scancel', '--signal=TERM', step], deadline)


def allocation_from_observation(text, *, job, node, observed_wall, observed_mono):
    """Bind exact allocation dimensions and elapsed startup allowance."""
    value = fields(text)
    tres = dict(item.split('=',1) for item in value.get('TRES','').split(',') if '=' in item)
    if (value.get('JobId') != job or value.get('JobState') != 'RUNNING'
            or value.get('UserId','').split('(',1)[0] != getpass.getuser()
            or node not in ('gpu27','gpu28') or value.get('NodeList') != node
            or value.get('NumNodes') != '1' or value.get('NumCPUs') != '12'
            or tres.get('gres/gpu') != '2'):
        raise ValueError('requires owned single-node dual-3090 twelve-CPU allocation')
    start, end = (dt.datetime.fromisoformat(value[k]).timestamp() for k in ('StartTime','EndTime'))
    if end-start != ALLOCATION_SECONDS or not 0 <= observed_wall-start < STARTUP_SECONDS:
        raise ValueError('allocation duration or elapsed startup outside fixed block')
    return Budget(observed_mono-(observed_wall-start), observed_mono+(end-observed_wall))


def service_environment(environment):
    # No generator keys, proxy authentication or unrelated tokens to the service.
    allowed = {'PATH','HOME','USER','LOGNAME','LANG','LC_ALL','LD_LIBRARY_PATH','TMPDIR',
               'CUDA_VISIBLE_DEVICES','SLURM_CONF','SINGULARITY_CACHEDIR','SINGULARITY_TMPDIR'}
    result = {k:v for k,v in environment.items() if k in allowed or
              (k.startswith('SLURM_') and not re.search(r'JWT|TOKEN|KEY|SECRET|PASS|EXPORT_ENV',k))}
    result.update(PYTHON_DOTENV_DISABLED='1', PYTHONDONTWRITEBYTECODE='1',
                  HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_DATASETS_OFFLINE='1')
    return result


class Service:
    def __init__(self, scheduler, directory, block, source, *, popen=subprocess.Popen, sleep=time.sleep):
        self.scheduler, self.budget = scheduler, scheduler.budget
        self.directory, self.source = Path(directory), Path(source)
        if type(block) is not int or block not in (1,2): raise ValueError('fixed block required')
        self.name = f'forets-b{block}-critic'
        self.ready = self.directory/'critic.ready.json'
        self.popen, self.sleep = popen, sleep
        self.process, self.startup_seconds = None, None

    def start(self):
        if self.process is not None or self.ready.exists(): raise RuntimeError('no service replay')
        self.budget.left(self.budget.startup)
        command = ['srun', '--jobid='+self.scheduler.job, '--exclusive','--nodes=1',
            '--ntasks=1','--cpus-per-task=6','--gres=gpu:1', '--job-name='+self.name,
            '--time='+str(max(1, math.ceil((self.budget.end-self.budget.now())/60))),
            '--kill-on-bad-exit=1',GPU_PYTHON,str(self.source),'--ready',str(self.ready)]
        with os.fdopen(os.open(self.directory/'critic.private.log',os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),'wb') as log:
            self.process = self.popen(command, stdout=log, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL, env=service_environment(os.environ))
        while not self.ready.is_file():
            self.budget.left(self.budget.startup)
            if self.process.poll() is not None: raise RuntimeError('critic exited before ready')
            self.sleep(min(1, self.budget.left(self.budget.startup)))
        if self.ready.is_symlink() or self.ready.stat().st_size > 16384:
            raise ValueError('invalid service marker')
        identity = json.loads(self.ready.read_text())
        if (identity.get('allocation_id') != self.scheduler.job
                or not re.fullmatch(r'[0-9]+',str(identity.get('step_id','')))
                or identity.get('host') != '127.0.0.1' or identity.get('port') != 8765
                or identity.get('runtime_check',{}).get('all_parameters_cuda_bf16') is not True):
            raise ValueError('service ownership/runtime marker mismatch')
        step = self.scheduler.job+'.'+identity['step_id']
        if step not in self.scheduler.active_owned({self.name},self.budget.startup):
            raise RuntimeError('service marker has no matching live scheduler step')
        self.budget.left(self.budget.startup)
        self.startup_seconds = self.budget.now()-self.budget.start

    def alive(self): return self.process is not None and self.process.poll() is None


class RuntimePoolControl(BlockPoolControl):
    """Actual pool integration; synchronous calls and shared teardown are bounded."""
    def _load_or_create_manifest(self):
        if self.manifest_path.exists(): raise RuntimeError('prior pool exists; no automatic replay')
        return super()._load_or_create_manifest()

    def _validate_paths_on_node(self):
        # sbatch controller and tasks share this single node. Check the exact
        # same required paths locally; no resource-bearing path-check srun.
        import shutil
        paths, executables = self._required_paths()
        self.runtime_budget.left(self.runtime_budget.startup)
        if any(not p.exists() for p in paths) or any(shutil.which(p) is None for p in executables):
            raise RuntimeError('required compute-node path/executable unavailable')
        self.runtime_budget.left(self.runtime_budget.startup)

    def _remaining_seconds(self): return self.runtime_budget.end-self.runtime_budget.now()

    def _accounting_for_task(self, task):
        # Outer collector independently queries sacct after allocation closure.
        # Do not add synchronous SlurmDBD queries to every worker completion.
        return None

    def _cancel_running(self, running, external_running):
        if external_running: raise RuntimeError('unexpected resumed external step')
        # The outer lifecycle owns ONE cleanup deadline for worker and service.
        # Store handles, don't spend another 30s here before its 30s cleanup.
        self.runtime_cancelled = list(running.values())
        for item in running.values():
            self._finish_task(item.run_id,status='cancelled',exit_code=None,
                              reason='controller stopped; remote cleanup not yet confirmed')


def cleanup_owned(pool, service, *, sleep=time.sleep):
    scheduler, budget = service.scheduler, service.budget
    # Early failure has a 30s cleanup bound too, rather than waiting hours.
    deadline = min(budget.end, budget.now()+CLEANUP_SECONDS)
    names = {service.name}
    for task in pool.manifest['tasks'].values():
        names.update(a['job_name'] for a in task['attempts'])
    processes = [x.process for x in getattr(pool,'runtime_cancelled',[])]
    if service.process is not None: processes.append(service.process)
    issues = []
    try:
        scheduler.cancel(scheduler.active_owned(names,deadline),deadline)
    except (TimeoutError,RuntimeError,subprocess.SubprocessError):
        issues.append('scheduler_cancel_unconfirmed')
    for process in processes:
        try:
            if process.poll() is None: process.terminate()
        except OSError: issues.append('local_signal_failed')
    # Reserve the last five seconds for terminating local srun clients. Their
    # exit is NEVER proof that remote GPU work has ended.
    while budget.now() < deadline-5:
        if all(p.poll() is not None for p in processes): break
        sleep(min(0.25,deadline-5-budget.now()))
    for process in processes:
        try:
            if process.poll() is None: process.kill()
            process.wait(timeout=budget.left(deadline,2))
        except (OSError,TimeoutError,subprocess.TimeoutExpired): issues.append('local_srun_exit_unconfirmed')
    remote_empty = False
    try:
        while True:
            if not scheduler.active_owned(names,deadline):
                remote_empty=True; break
            sleep(min(0.5,budget.left(deadline)))
    except (TimeoutError,RuntimeError,subprocess.SubprocessError):
        issues.append('remote_step_cleanup_unconfirmed')
    return dict(remote_step_cleanup_confirmed=remote_empty,
                local_srun_exited=all(p.poll() is not None for p in processes),issues=issues)


def run_lifecycle(pool, service, *, interrupt=interrupt_at, cleanup=cleanup_owned):
    """One already qualified four-run pool; no credentials, outcomes or retry.

    Caller must run in its own batch allocation and enforce the release BEFORE
    pool construction. Used directly only with substituted OS boundaries in tests.
    """
    budget = service.budget
    result = dict(status='failed',service_startup_seconds=None, error_type=None)
    with lifecycle_signals():
        try:
            with interrupt(budget,budget.startup):
                pool._recover()  # pristine validation BEFORE loading service
                pool._validate_paths_on_node(); pool._paths_validated=True
                service.start()
            result['service_startup_seconds']=service.startup_seconds
            with interrupt(budget,budget.work): result['pool']=pool.run()
            result['status']='completed' if result['pool']['successful'] else 'incomplete'
        except (Exception,KeyboardInterrupt) as exc:
            result['error_type']=type(exc).__name__
        finally:
            # A second TERM must not interrupt a partly completed teardown.
            for sig in (signal.SIGINT,signal.SIGTERM): signal.signal(sig,signal.SIG_IGN)
            result['cleanup']=cleanup(pool,service)
            if not result['cleanup']['remote_step_cleanup_confirmed']:
                result['status']='cleanup_unconfirmed'
    return result


def execute_block(root, block, release_raw, *, node, controller_commit):
    """Production front door bound to the exact exploratory release FIRST.

    Exposed only by forets_native_run_20260911, not the old campaign. Merely
    changing PACKAGE_STATE or passing a boolean does not release another plan.
    """
    require_release(release_raw)
    from forets_native_context_20260911 import NativeWorkerEnvironment, release
    spec_release=release(release_raw)
    if node!=spec_release['node']:raise ValueError('only native-qualified gpu28 is released')
    from forets_block_readout_20260911 import ROOT, _inside, _load, _canonical
    from forets_stage_gate import validate_route_receipt
    from types import SimpleNamespace
    root=Path(root).resolve(strict=True)
    if root!=ROOT.resolve(strict=True): raise ValueError('only fixed development package')
    if not re.fullmatch(r'[0-9a-f]{40}',controller_commit): raise ValueError('exact controller commit required')
    spec,typed=inspect_draft(root,block)
    job=os.environ.get('SLURM_JOB_ID','')
    if not job.isdigit() or os.environ.get('SLURM_STEP_ID','') not in ('','batch'):
        raise RuntimeError('requires dedicated batch allocation')
    source=root/'source'
    inventory=_load(root/'source-files.json',digest=SOURCE_FILES_SHA)
    for relative,digest in inventory.items():
        path=_inside(source,relative)
        if hashlib.sha256(path.read_bytes()).hexdigest()!=digest: raise ValueError('source drift')
    # Each allocation has its own fresh receipt. The second four-hour block
    # cannot reuse the first block's now-stale endpoint check or overwrite it.
    validate_route_receipt(_inside(root,f'block-{block}.route.json'),source)
    query=subprocess.run(['scontrol','show','job',job,'-o'],capture_output=True,text=True,timeout=15,check=True)
    budget=allocation_from_observation(query.stdout,job=job,node=node,
        observed_wall=time.time(),observed_mono=time.monotonic())
    record_dir=root/f'block-{block}.runtime'
    record_dir.mkdir(mode=0o700,exist_ok=False)
    # Never load .env implicitly during source imports; worker credential must
    # already have been explicitly installed in the remote process environment.
    if not os.environ.get('OPENROUTER_API_KEY'): raise RuntimeError('known remote credential absent')
    os.environ.update(PYTHON_DOTENV_DISABLED='1',PYTHONDONTWRITEBYTECODE='1',
        LITELLM_LOCAL_MODEL_COST_MAP='True',DEFAULT_SLURM_PARTITION='gpu_24h',
        DEFAULT_SLURM_ACCOUNT='gpu',DEFAULT_SLURM_QOS='gpu',LOGGING_DIR=str(root),
        MLE_BENCH_DATA_DIR='/research/d7/spc/yzyang4/mle-bench-data',
        SUPERIMAGE_DIR='/research/d7/spc/yzyang4/aira-dojo/build/superimage',
        PRIMARY_KEY=os.environ['OPENROUTER_API_KEY'])
    sys.path.insert(0,str(source/'src'))
    from dojo.config_dataclasses.run import RunConfig
    from dojo.config_dataclasses.launcher.srun_pool import SrunPoolConfig
    from dojo.core.runners.slurm.srun_pool import SrunPoolLauncher
    import inspect
    imported_pool=Path(inspect.getfile(SrunPoolLauncher)).resolve()
    if (imported_pool != source/'src/dojo/core/runners/slurm/srun_pool.py'
            or hashlib.sha256(imported_pool.read_bytes()).hexdigest()!=POOL_SHA):
        raise RuntimeError('pool imported from another checkout')
    class Pool(NativeWorkerEnvironment,RuntimePoolControl,SrunPoolLauncher):
        runtime_budget=budget
        native_code_dir=Path(__file__).resolve().parent
        native_release_path=native_code_dir/'forets_native_e2e_release_20260911.json'
        native_controller_commit=controller_commit
        def _discover_allocation(self):
            return SimpleNamespace(job_id=job,node_list=node,num_nodes=1,num_cpus=12,
                num_gpus=2,end_time=dt.datetime.fromtimestamp(time.time()+budget.end-budget.now()))
    configs=[RunConfig.from_dict(c) for c in typed]
    for config in configs: config.validate()
    scheduler=Scheduler(budget,job)
    service=Service(scheduler,record_dir,block,Path(__file__).with_name('forets_e2e_critic_service.py'))
    with interrupt_at(budget,budget.startup):
        pool=Pool(configs,SrunPoolConfig(**spec.launcher),source,python_executable=PYTHON)
        pool.configure_block(spec,service.alive)
        # Config bytes in the pool may serialize differently, but no values change.
        for run_id,expected in zip(spec.run_ids,typed):
            path=Path(pool.manifest['tasks'][run_id]['config_path'])
            if _canonical(_load(path))!=_canonical(expected): raise ValueError('pool config drift')
    write_once(record_dir/'started.json',dict(block=block,allocation_id=job,node=node,
        controller_commit=controller_commit,pool_manifest=str(pool.manifest_path.relative_to(root)),
        service_name=service.name,observed_utc=dt.datetime.now(dt.timezone.utc).isoformat()))
    status=run_lifecycle(pool,service)
    # This is a controller result, NEVER an allocation terminal receipt.
    write_once(record_dir/'finished.json',status)
    return status


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--draft',type=Path,required=True)
    p.add_argument('--block',type=int,choices=(1,2),required=True)
    a=p.parse_args()
    spec,configs=inspect_draft(a.draft,a.block)
    print(json.dumps(dict(status='RUNTIME_WIRING_PREPARED_RELEASE_ABSENT',
        block=spec.block,actual_configs_bound=len(configs),execution_allowed=False,
        slurm_dispatches=0,api_requests=0,model_loads=0)))


if __name__=='__main__': main()
