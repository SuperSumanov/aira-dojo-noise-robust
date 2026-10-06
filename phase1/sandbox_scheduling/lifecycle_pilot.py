"""Approved 1x3090/15min/6-call resource-lifecycle diagnostic, not a scheduler trial.

Controlled interpreter-level keep/close timings. Production task factory already
closes at step completion; this is NOT evidence of a production leak or speedup.
No task dataset, grading, model training, generator service or paid API is used.
"""
from __future__ import annotations
import argparse
import copy
import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import socket
import statistics
import subprocess
import sys
import time

B = Path('/research/d7/spc/yzyang4')
R = B/'scheduling-lifecycle-20261006-v1'
D = B/'matched-representation-20261005-v1'
PY = B/'venvs/aira/bin/python'
NAME = 'lifecycle_pilot.py'
BASE_COMMIT = 'e5e83b6e4eed842197f7de924ae4734003e8965a'
RUNTIME_SHA = 'b422a17094a6971218731054b53b56888505150b82f5309990b0b629577da4c9'
SECRET = re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,}|Bearer\s+[a-z0-9_.-]{20,})')
PROGRAM = '''import json
from pathlib import Path
import torch
assert torch.cuda.is_available() and torch.cuda.device_count() == 1
torch.manual_seed(130601)
x = torch.ones(16*1024*1024, dtype=torch.float32, device="cuda")
torch.cuda.synchronize()
Path("fixture.json").write_text(json.dumps({"elements":x.numel(), "sum":int(x.sum().item()), "dtype":str(x.dtype)}, sort_keys=True))
'''


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as file:
        for chunk in iter(lambda: file.read(8*1024**2), b''):
            h.update(chunk)
    return h.hexdigest()


def read(path):
    raw = Path(path).read_bytes()
    if SECRET.search(raw):
        raise ValueError('credential-shaped file refused')
    return json.loads(raw)


def write(path, value):
    raw = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False)+'\n').encode()
    if SECRET.search(raw):
        raise ValueError('credential-shaped output refused')
    with Path(path).open('xb') as file:
        file.write(raw)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def schedule():
    return [dict(index=2*repeat+j, repeat=repeat, arm=arm, seed=130601)
            for repeat in range(3)
            for j, arm in enumerate(('keep_10s','close_now') if repeat % 2 == 0 else ('close_now','keep_10s'))]


def runtime():
    if sha(R/'runtime.py') != RUNTIME_SHA:
        raise ValueError('runtime pin drift')
    module = load('lifecycle_runtime', R/'runtime.py')
    module.R = R
    module.setup()
    return module


def check():
    plan = read(R/'plan.json')
    if plan['schedule'] != schedule() or plan['gpu_hours_cap'] != .25:
        raise ValueError('plan drift')
    for name, expected in plan['files'].items():
        if sha(R/name) != expected:
            raise ValueError('file drift')
    return plan


def prepare():
    if sha(D/'plan.json') != 'fed6f8c812fc49db8acc459b460a10bbe962cbe10b8a2172f5dff06c7686a624':
        raise ValueError('donor plan mismatch')
    donor = read(D/'plan.json')
    if sha(D/'runtime.py') != RUNTIME_SHA:
        raise ValueError('donor runtime mismatch')
    R.mkdir(mode=0o700, exist_ok=False)
    for name, expected in donor['files'].items():
        if not name.startswith(('source/','forets_','opencl-vendors/')):
            continue
        if sha(D/name) != expected:
            raise ValueError('donor source mismatch')
        dest = R/name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(D/name, dest)
    shutil.copyfile(D/'runtime.py', R/'runtime.py')
    shutil.copyfile(__file__, R/NAME)
    shutil.copyfile(Path(__file__).with_name('observe.py'), R/'observe.py')
    for name in ('bin','empty-data'):
        (R/name).mkdir()
    (R/'bin/singularity').write_text(f'#!{PY}\nimport sys\nsys.path.insert(0,{str(R)!r})\nfrom lifecycle_pilot import runtime\nruntime().task_runtime()\n')
    os.chmod(R/'bin/singularity', 0o700)
    for row in schedule():
        ep = R/f'episode-{row["index"]}'
        (ep/'work').mkdir(parents=True)
    batch = f'''#!/bin/bash
#SBATCH --job-name=scheduling-lifecycle
#SBATCH --partition=gpu_24h
#SBATCH --account=gpu
#SBATCH --qos=gpu
#SBATCH --nodelist=gpu27
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=6
#SBATCH --time=00:15:00
#SBATCH --no-requeue
set -euo pipefail
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1
timeout --signal=TERM --kill-after=20s 850s {PY} -B {R}/{NAME} controller
'''
    (R/'run.sbatch').write_text(batch)
    plan = dict(source_commit=BASE_COMMIT, schedule=schedule(), gpu_hours_cap=.25,
                gpus=1, allocation_seconds=900, worker_hard_seconds=100, cleanup_grace_seconds=10,
                observation_window_seconds=10, source_executions=6, fixture_bytes=64*1024**2,
                no_training=True, no_data=True, no_api=True, program_sha256=hashlib.sha256(PROGRAM.encode()).hexdigest(),
                purpose='interpreter resource lifecycle primitive, NOT default production leak or throughput test',
                files={str(p.relative_to(R)):sha(p) for p in R.rglob('*') if p.is_file()})
    write(R/'plan.json', plan)
    module = runtime()
    from dojo.config_dataclasses.interpreter.jupyter import JupyterInterpreterConfig
    from dojo.config_dataclasses.interpreter import INTERPRETER_MAP
    from dojo.utils.config import build
    cfg = JupyterInterpreterConfig(working_dir=str(R/'episode-0/work'), timeout=30,
        container_runtime='singularity', superimage_directory=str(module.TASK_IMAGE.parent),
        superimage_version='2026-07-macos-v1', env={'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1'})
    cfg.validate()
    interp = build(cfg, INTERPRETER_MAP, data_dir=R/'empty-data')
    if not interp.factory or interp._instance is not None:
        raise ValueError('unexpected eager launch/backend')
    compile(PROGRAM, 'fixture.py', 'exec')
    subprocess.run(['bash','-n',str(R/'run.sbatch')], check=True)
    image_sha = sha(module.TASK_IMAGE)
    if image_sha != read(D/'preflight.json')['task_image_sha256']:
        raise ValueError('unchanged task image mismatch')
    write(R/'preflight.json', dict(plan_sha256=sha(R/'plan.json'), task_image_sha256=image_sha,
        original_image=True, factory_lazy_no_gpu_launched=True, program_compiles=True,
        empty_data_only=True, no_official_grading=True, no_model_or_api=True, shell_syntax=True))
    print(json.dumps(dict(status='PREPARED', plan_sha256=sha(R/'plan.json'), root=str(R), gpu_hours_cap=.25)))


def submit():
    check()
    if read(R/'preflight.json')['plan_sha256'] != sha(R/'plan.json'):
        raise ValueError('preflight drift')
    env = runtime().infra().clean_env()
    jobs = subprocess.check_output(['squeue','-u','yzyang4','-h','-o','%i'], env=env, text=True, timeout=15).split()
    if set(jobs)-{'12535'}:
        raise ValueError('unexpected active allocation')
    write(R/'submit-intent.json', dict(plan_sha256=sha(R/'plan.json'), approved_gpu_hours=.25))
    result = subprocess.run(['sbatch','--parsable','--chdir='+str(R),'--output='+str(R/'allocation-%j.out'),
        '--error='+str(R/'allocation-%j.err'),str(R/'run.sbatch')], env=env,capture_output=True,text=True,timeout=20)
    job = result.stdout.strip().split(';')[0]
    if result.returncode or not job.isdigit():
        raise RuntimeError('ambiguous submission, do not retry')
    write(R/'launch.json', dict(job=job, plan_sha256=sha(R/'plan.json')))
    print(json.dumps(dict(status='SUBMITTED',job=job,gpu_hours_cap=.25)))


def applications(gpu_uuid):
    text = subprocess.check_output(['nvidia-smi','-i',gpu_uuid,'--query-compute-apps=gpu_uuid,pid',
        '--format=csv,noheader,nounits'], text=True, timeout=3)
    rows = [row for row in csv.reader(text.splitlines()) if row]
    if any(len(row)!=2 or row[0].strip()!=gpu_uuid for row in rows):
        raise ValueError('GPU query scope mismatch')
    return [int(row[1]) for row in rows]


def worker(index):
    plan = check()
    module = runtime()
    row = schedule()[index]
    ep = R/f'episode-{index}'
    gpu = module.infra().native_uuids(1)[0]
    if applications(gpu):
        raise ValueError('assigned GPU already has compute clients')
    os.environ.update(DOJO_GPU_UUIDS=gpu,POLICY9B_EPISODE=str(ep),DOJO_WORKER_IDENTITY_PATH=str(ep/'identity.json'),
                      PATH=str(R/'bin')+':'+os.environ['PATH'])
    from dojo.main_local_worker import _process_start_ticks, _host_boot_id
    from dojo.config_dataclasses.interpreter.jupyter import JupyterInterpreterConfig
    from dojo.config_dataclasses.interpreter import INTERPRETER_MAP
    from dojo.utils.config import build
    from dojo.utils.experiment_deadline import ExperimentDeadline
    from observe import sample_gpu
    write(ep/'native.json', dict(job=os.environ['SLURM_JOB_ID'],step=os.environ['SLURM_STEP_ID'],gpu_uuids=[gpu]))
    write(ep/'identity.json', dict(pid=os.getpid(),pgid=os.getpgid(0),process_start_ticks=_process_start_ticks(os.getpid()),
         host_boot_id=_host_boot_id(),gpu_uuids=[gpu],container_pid=None,container_process_start_ticks=None))
    cfg = JupyterInterpreterConfig(working_dir=str(ep/'work'),timeout=30,container_runtime='singularity',
        superimage_directory=str(module.TASK_IMAGE.parent),superimage_version='2026-07-macos-v1',
        env={'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','OMP_NUM_THREADS':'6','PYTHONHASHSEED':'130601'})
    interp, samples, metrics, error = None, [], {}, None
    started = time.monotonic()
    def sample(phase):
        value = sample_gpu(gpu)
        if value['status'] != 'ok' or value['data']['metrics']['memory_used_mib'] is None:
            raise ValueError('GPU memory measurement unavailable')
        samples.append(dict(phase=phase,elapsed_seconds=time.monotonic()-started,**value))
    def close_and_verify():
        close_started = time.monotonic()
        metrics['close_started_elapsed_seconds'] = close_started-started
        interp.close()
        metrics['close_call_seconds'] = time.monotonic()-close_started
        while applications(gpu):
            if time.monotonic()-close_started > 15:
                raise TimeoutError('GPU client not released')
            time.sleep(.5)
        metrics['close_start_to_no_client_seconds'] = time.monotonic()-close_started
        sample('release_verified')
    try:
        with ExperimentDeadline(75).activate():
            sample('before_container')
            interp = build(cfg,INTERPRETER_MAP,data_dir=R/'empty-data')
            out = interp.run(PROGRAM)
            if out.exit_code != 0 or out.timed_out:
                raise RuntimeError('fixture failed; no CPU fallback or retry')
            interp.fetch_file(ep/'work/fixture.json')
            fixture = read(ep/'work/fixture.json')
            if fixture != {'elements':16777216,'sum':16777216,'dtype':'torch.float32'}:
                raise ValueError('fixture output mismatch')
            metrics['fixture_sha256'] = sha(ep/'work/fixture.json')
            metrics['exec_seconds'] = out.exec_time
            sample('after_fetch_before_close')
            window_started = time.monotonic()
            if row['arm']=='close_now':
                close_and_verify()
            while time.monotonic()-window_started < 10:
                sample('window')
                time.sleep(1)
            if row['arm']=='keep_10s':
                close_and_verify()
            if applications(gpu):
                raise ValueError('new or residual GPU client after close')
            sample('after_close_no_clients')
    except Exception as exc:
        error = type(exc).__name__
    finally:
        if interp is not None:
            try:
                interp.close()
            except Exception as exc:
                metrics['cleanup_error_type'] = type(exc).__name__
                error = error or 'CleanupFailed'
        write(ep/'samples.json',samples)
        write(ep/'completed.json',dict(**row,**metrics,error_type=error,elapsed_seconds=time.monotonic()-started,
             complete=error is None,source_commit=plan['source_commit'],gpu_uuid=gpu))
    if error:
        raise RuntimeError('lifecycle trial incomplete')


def controller():
    check()
    for _ in range(20):
        if (R/'launch.json').exists():
            break
        time.sleep(.25)
    if read(R/'launch.json')['job'] != os.environ['SLURM_JOB_ID'] or socket.gethostname().split('.')[0]!='gpu27':
        raise ValueError('allocation identity mismatch')
    env = runtime().infra().clean_env()
    codes = []
    for row in schedule():
        ep = R/f'episode-{row["index"]}'
        cmd = ['srun','--exclusive','--nodes=1','--ntasks=1','--cpus-per-task=6','--gres=gpu:1','--time=00:02:00',
               'timeout','--signal=TERM','--kill-after=10s','100s',str(PY),'-B',str(R/NAME),'worker','--index',str(row['index'])]
        with (ep/'worker.private.log').open('xb') as file:
            result = subprocess.run(cmd,env=env,stdout=file,stderr=file)
        codes.append(result.returncode)
        write(ep/'closed.json',dict(returncode=result.returncode))
        if result.returncode or not (ep/'completed.json').exists() or not read(ep/'completed.json')['complete']:
            break
    write(R/'closed.json',dict(returncodes=codes,planned=6,attempted=len(codes),complete=len(codes)==6 and not any(codes)))


if __name__=='__main__':
    os.umask(0o077)
    os.environ.update(PYTHON_DOTENV_DISABLED='1',PYTHONDONTWRITEBYTECODE='1')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('prepare','submit','worker','controller','runtime'))
    parser.add_argument('--index',type=int)
    args=parser.parse_args()
    if args.mode=='worker':worker(args.index)
    elif args.mode=='runtime':runtime().task_runtime()
    else:globals()[args.mode]()
