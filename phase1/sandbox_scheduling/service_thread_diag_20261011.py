"""Bounded 2-GPU serving + six CPU sandbox thread-pressure diagnosis.

Not six-GPU MLE execution, training, throughput, or quality evidence.
Only the already validated readiness overlay is used; no limit is raised.
"""
import concurrent.futures
import ctypes
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import uuid

import resource_diag_20261011 as d

ROOT = d.BASE / 'resource-service-diag-20261011-v1'
DONOR = d.BASE / 'resource-diag-readiness-fixed-20261011-v1'
DONOR_SHA = '21a063ca6ca7b4d25822b963cd55533ed1ea276caabdc6e4b0cb958fbae30858'
MODEL_DONOR = d.BASE / 'scheduling-live-twochild-20261010-v1'
MODEL = d.BASE / 'local-qwen27b-20260914-zcx1k1dy/model'
VLLM = MODEL.parent / 'vllm.sif'
ENTRY = d.BASE / 'task-feedback-real-20261001-v6/service_entry.py'
ENTRY_SHA = 'cd9e143abe79cdc71c97db3dba07930e0642b28faf52ac4f6b2ca5ba36a8379a'
NAME = Path(__file__).name
PORT = 19481
d.ROOT = ROOT
d.NAME = NAME


def prepare():
    assert d.sha(DONOR / 'plan.json') == DONOR_SHA
    old = json.loads((DONOR / 'plan.json').read_text())
    closed = json.loads((DONOR / 'closed.json').read_text())
    assert (closed['planned'], closed['attempted'], closed['complete']) == (14, 14, 14)
    models = json.loads((MODEL_DONOR / 'plan.json').read_text())
    assert d.sha(ENTRY) == ENTRY_SHA
    assert d.sha(VLLM) == models['service_image_sha256']
    for name, digest in models['model_files'].items():
        assert d.sha(Path(name)) == digest, 'model asset drift'
    ROOT.mkdir(mode=0o700)
    for name, digest in old['files'].items():
        if not (name.startswith('source/') or name in ('resource_diag_20261011.py', 'resource_pressure.py')):
            continue
        assert d.sha(DONOR / name) == digest
        target = ROOT / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(DONOR / name, target)
    shutil.copyfile(__file__, ROOT / NAME)
    entry = ENTRY.read_text()
    assert entry.count("'--port','19441'") == 1
    (ROOT / 'service_entry.py').write_text(entry.replace("'--port','19441'", f"'--port','{PORT}'"))
    for row in d.schedule():
        (ROOT / f"block-{row['block']}-worker-{row['index']}").mkdir()
    (ROOT / 'service-cache/tmp').mkdir(parents=True)
    # A local-only random service credential; never exported or added to manifest.
    with (ROOT / '.service.env').open('x') as f:
        f.write('VLLM_API_KEY=' + secrets.token_hex(32) + '\n')
    os.chmod(ROOT / '.service.env', 0o600)
    batch = f'''#!/bin/bash
#SBATCH --job-name=resource-service-diag
#SBATCH --partition=gpu_24h
#SBATCH --account=gpu
#SBATCH --qos=gpu
#SBATCH --nodelist=gpu27
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:2
#SBATCH --cpus-per-task=18
#SBATCH --time=00:40:00
#SBATCH --no-requeue
set -euo pipefail
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1
timeout --signal=TERM --kill-after=30s 2310s {d.PY} {ROOT}/{NAME} allocation
'''
    (ROOT / 'run.sbatch').write_text(batch)
    subprocess.run(['bash', '-n', str(ROOT / 'run.sbatch')], check=True)
    d.configure()
    from dojo.core.interpreters.jupyter.jupyter_code_executor import JupyterCodeExecutor
    d.write(ROOT / 'plan.json', dict(source_commit=d.SOURCE, donor_plan_sha256=DONOR_SHA,
        question='Does the unchanged local 27B service plus six task-image kernels reproduce thread exhaustion?',
        schedule=d.schedule(), planned_kernels=14, planned_local_requests=14,
        widths=[1, 6, 6, 1], threads_per_library=3, service_gpus=2, execution_gpus=0,
        cpus=18, service_cpus=12, execution_cpus=6, gpus=2, gpu_seconds_cap=4800,
        allocation_seconds_cap=2400, service_startup_seconds=900, request_timeout_seconds=90,
        service_model='qwen3.8-27b', reasoning_effort='medium', max_tokens=128, seed=49,
        service_max_num_seqs=6, task_image_sha256=old['image_sha256'],
        service_image_sha256=models['service_image_sha256'], model_files=models['model_files'],
        service_entry_original_sha256=ENTRY_SHA, limit_changes=False, cleanup_exception_patch=False,
        stop='No request/kernel replacement; any block failure closes remaining blocks; startup timeout closes allocation.',
        acceptance='14/14 kernels and requests; before/during/after host-UID and cgroup counters; full cost and cleanup.',
        boundary='CPU-only task kernels explicitly, not six-GPU MLE capacity, agent quality or scheduling gains.',
        preflight=dict(readiness_14_of_14=True, original_images=True, model_hashes=True,
            input_data_none=True, protected_data_none=True, local_service_only=True,
            agent_base_updates=False, full_denominator=14, cost_includes_failure=True,
            same_seed=True, no_retry=True, gpu_identity_required=True, resume='closed attempts immutable; interrupted attempts are failures, not retried'),
        files={str(p.relative_to(ROOT)): d.sha(p) for p in ROOT.rglob('*')
               if p.is_file() and p.name != '.service.env' and '__pycache__' not in p.parts}))
    print(json.dumps(dict(prepared=True, plan_sha256=d.sha(ROOT / 'plan.json'), root=str(ROOT))))


def key():
    line = (ROOT / '.service.env').read_text().strip()
    assert line.startswith('VLLM_API_KEY=')
    return line.split('=', 1)[1]


def api(path, payload=None, timeout=10):
    request = urllib.request.Request('http://127.0.0.1:' + str(PORT) + path,
        data=None if payload is None else json.dumps(payload).encode(),
        headers={'Authorization': 'Bearer ' + key(), 'Content-Type': 'application/json'})
    # Explicitly bypass external proxy: only our loopback service may be used.
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=timeout) as response:
        return json.load(response)


def service():
    assert socket.gethostname().split('.')[0] == 'gpu27'
    lib = ctypes.CDLL('libcuda.so.1')
    assert lib.cuInit(0) == 0
    count = ctypes.c_int()
    assert lib.cuDeviceGetCount(ctypes.byref(count)) == 0 and count.value == 2
    devices = []
    for index in range(2):
        device = ctypes.c_int()
        assert lib.cuDeviceGet(ctypes.byref(device), index) == 0
        value = (ctypes.c_ubyte * 16)()
        assert lib.cuDeviceGetUuid(ctypes.byref(value), device) == 0
        devices.append('GPU-' + str(uuid.UUID(bytes=bytes(value))))
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', PORT))
    d.write(ROOT / 'service-identity.json', dict(uuids=devices, step=os.environ['SLURM_STEP_ID'],
        limits=d.resource_pressure.snapshot()['limits']))
    cmd = ['/usr/bin/singularity', 'exec', '--containall', '--cleanenv', '--no-home', '--nv',
        '--no-mount', 'bind-paths,cwd', '--bind', str(MODEL)+':/model:ro',
        '--bind', str(ROOT/'service-cache')+':/cache:rw', '--bind', str(ROOT/'service-cache/tmp')+':/tmp:rw',
        '--bind', str(ROOT/'service_entry.py')+':/run/service_entry.py:ro', '--pwd', '/cache',
        str(VLLM), '/usr/bin/python3', '/run/service_entry.py']
    values = dict(CUDA_VISIBLE_DEVICES=','.join(devices), EXPECTED_GPU_UUIDS=','.join(devices),
        VLLM_API_KEY=key(), VLLM_WORKER_MULTIPROC_METHOD='spawn', VLLM_CACHE_ROOT='/cache/vllm',
        TRITON_HOME='/cache/triton', TORCH_HOME='/cache/torch', HF_HOME='/cache/hf',
        HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', FLASHINFER_WORKSPACE_BASE='/cache/flashinfer',
        XDG_CACHE_HOME='/cache/xdg', TMPDIR='/tmp', MAX_JOBS='2', VLLM_NO_USAGE_STATS='1',
        VLLM_CONFIG_ROOT='/cache/vllm-config')
    env = {k:os.environ[k] for k in ('PATH','HOME','USER','LOGNAME') if k in os.environ}
    env.update({'SINGULARITYENV_'+k:v for k,v in values.items()})
    os.execve(cmd[0], cmd, env)


def request_one(block, index):
    start = time.time()
    result = dict(block=block, index=index, start=start, complete=False)
    try:
        value = api('/v1/chat/completions', dict(model='qwen3.8-27b',
            messages=[dict(role='user', content='Return only the integer result of 17 multiplied by 23.')],
            reasoning_effort='medium', temperature=0, seed=49, max_tokens=128), timeout=90)
        choice = value['choices'][0]
        result.update(complete=True, finish_reason=choice['finish_reason'],
            completion_tokens=value.get('usage', {}).get('completion_tokens'),
            prompt_tokens=value.get('usage', {}).get('prompt_tokens'))
    except Exception as exc:
        result['error_type'] = type(exc).__name__
    result['end'] = time.time()
    d.write(ROOT/f'request-{block}-{index}.json', result)
    return result


def controller():
    d.write(ROOT/'controller-before.json', d.resource_pressure.snapshot())
    rows, requests = [], []
    for block, width in enumerate((1,6,6,1)):
        d.write(ROOT/f'block-{block}-before.json', d.resource_pressure.snapshot())
        with concurrent.futures.ThreadPoolExecutor(max_workers=width*2) as pool:
            kernel = [pool.submit(d.run_one, block, i) for i in range(width)]
            local = [pool.submit(request_one, block, i) for i in range(width)]
            new = [f.result() for f in kernel]
            req = [f.result() for f in local]
        rows += new; requests += req
        time.sleep(3)
        d.write(ROOT/f'block-{block}-after.json', d.resource_pressure.snapshot())
        if any(x['returncode'] for x in new) or any(not x['complete'] for x in req):
            break
    complete = sum(x['returncode']==0 for x in rows)
    requests_complete = sum(x['complete'] for x in requests)
    d.write(ROOT/'closed.json',dict(planned=14, attempted=len(rows), complete=complete,
        requests_planned=14, requests_attempted=len(requests), requests_complete=requests_complete,
        rows=rows, no_effect_claim=True))
    return int(complete!=14 or requests_complete!=14)


def stop_owned(process):
    if process is None or process.poll() is not None:
        return
    os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=25)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)


def allocation():
    p=json.loads((ROOT/'plan.json').read_text())
    for name,digest in p['files'].items():
        assert d.sha(ROOT/name)==digest
    d.write(ROOT/'allocation-before.json', d.resource_pressure.snapshot())
    end=threading.Event()
    def sample():
        with (ROOT/'pressure.jsonl').open('x') as f:
            while not end.is_set():
                f.write(json.dumps(d.resource_pressure.snapshot())+'\n');f.flush()
                end.wait(1)
    observer=threading.Thread(target=sample,daemon=True);observer.start()
    service_proc=control=None
    error=None;rc=1
    try:
        with (ROOT/'service.private.log').open('x') as service_log, (ROOT/'controller.private.log').open('x') as controller_log:
            service_proc=subprocess.Popen(['srun','--exclusive','--exact','--ntasks=1','--gres=gpu:2',
                '--cpus-per-task=12','--cpu-bind=cores',str(d.PY),str(ROOT/NAME),'service'],
                stdout=service_log,stderr=service_log,start_new_session=True)
            deadline=time.monotonic()+900
            while time.monotonic()<deadline:
                if service_proc.poll() is not None: raise RuntimeError('service exited')
                try:
                    healthy={v['id'] for v in api('/v1/models')['data']}=={'qwen3.8-27b'}
                except Exception:
                    healthy=False
                if healthy: break
                time.sleep(2)
            else: raise TimeoutError('service readiness')
            d.write(ROOT/'service-ready.json', d.resource_pressure.snapshot())
            control=subprocess.Popen(['srun','--exclusive','--exact','--ntasks=1','--gres=gpu:0',
                '--cpus-per-task=6','--cpu-bind=cores',str(d.PY),str(ROOT/NAME),'controller'],
                stdout=controller_log,stderr=controller_log,start_new_session=True)
            rc=control.wait(timeout=1200)
    except Exception as exc:
        error=type(exc).__name__
    finally:
        stop_owned(control);stop_owned(service_proc)
        end.set();observer.join(timeout=10)
        d.write(ROOT/'allocation-after.json',d.resource_pressure.snapshot())
        d.write(ROOT/'allocation-closed.json',dict(returncode=rc,error_type=error,
            service_stopped=service_proc is None or service_proc.poll() is not None,
            controller_stopped=control is None or control.poll() is not None))
    return rc


if __name__=='__main__':
    os.umask(0o077)
    mode=sys.argv[1]
    if mode=='worker': sys.exit(d.worker(*map(int,sys.argv[2:])))
    if mode not in ('prepare','service','controller','allocation'):raise ValueError('mode')
    sys.exit(globals()[mode]())
