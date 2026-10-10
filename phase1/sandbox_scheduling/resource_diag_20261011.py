"""Bounded CPU-only, six-kernel resource diagnosis in the original task image.

No task data, scores, GPU execution, model service or base-model updates.
CPU visibility is explicitly diagnostic, not an MLE CPU-fallback experiment.
"""
import argparse
import concurrent.futures
import hashlib
import io
import json
import logging
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tarfile
import time

import resource_pressure

BASE = Path('/research/d7/spc/yzyang4')
ROOT = BASE / 'resource-diag-20261011-v5'
REPO = BASE / 'aira-dojo'
PY = BASE / 'venvs/aira/bin/python'
IMAGE = REPO / 'build/superimage/superimage.root.2026-07-macos-v1.sif'
IMAGE_SHA = '801f646bed3cae6e74e10d793e71b0086658d4303d54552333c58125ddf9beda'
SOURCE = 'f7ccd79323112b10ccc82d8e9ec9d6cf089df607'
NAME = Path(__file__).name
CAP = 1200


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(8 * 1024**2), b''):
            h.update(block)
    return h.hexdigest()


def write(path, value):
    with Path(path).open('x') as f:
        json.dump(value, f, indent=2, sort_keys=True, allow_nan=False)


def schedule():
    return [dict(block=b, width=w, index=i) for b, w in enumerate((1, 6, 6, 1)) for i in range(w)]


def prepare():
    if ROOT.exists():
        raise FileExistsError('diagnostic root already exists')
    if sha(IMAGE) != IMAGE_SHA:
        raise ValueError('image hash mismatch')
    raw = subprocess.check_output(['git', '-C', str(REPO), 'archive', SOURCE, 'src/dojo'])
    secret = re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,})')
    files = {}
    with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
        for member in archive:
            if member.isdir():
                continue
            rel = Path(member.name)
            if not member.isfile() or '..' in rel.parts or not rel.is_relative_to('src/dojo'):
                raise ValueError('archive shape')
            payload = archive.extractfile(member).read()
            if secret.search(payload):
                raise ValueError('credential shape in source; no source written')
            files[str(rel)] = payload
    ROOT.mkdir(mode=0o700)
    for rel, data in files.items():
        target = ROOT / 'source' / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    for name in (NAME, 'resource_pressure.py'):
        (ROOT / name).write_bytes(Path(__file__).with_name(name).read_bytes())
    for row in schedule():
        (ROOT / f"block-{row['block']}-worker-{row['index']}").mkdir()
    batch = f'''#!/bin/bash
#SBATCH --job-name=resource-diag-v5
#SBATCH --partition=gpu_24h
#SBATCH --account=gpu
#SBATCH --qos=gpu
#SBATCH --nodelist=gpu27
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=6
#SBATCH --time=00:20:00
#SBATCH --no-requeue
set -euo pipefail
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1
{PY} {ROOT}/{NAME} allocation
timeout --signal=TERM --kill-after=10s 1140s srun --exclusive --ntasks=1 --gres=gpu:1 --cpus-per-task=6 --cpu-bind=cores {PY} {ROOT}/{NAME} controller
'''
    (ROOT / 'run.sbatch').write_text(batch)
    subprocess.run(['bash', '-n', str(ROOT / 'run.sbatch')], check=True)
    configure()
    import inspect
    from dojo.core.interpreters.jupyter.singularity_jupyter_server import SingularityJupyterServer
    from dojo.core.interpreters.jupyter.jupyter_code_executor import JupyterCodeExecutor
    write(ROOT / 'preflight.json', dict(imports_pass=True, no_kernel_started=True,
           executor_signature=str(inspect.signature(JupyterCodeExecutor.execute_code)),
           fetch_signature=str(inspect.signature(JupyterCodeExecutor.fetch_file))))
    write(ROOT / 'plan.json', dict(source_commit=SOURCE, image_sha256=IMAGE_SHA,
          schedule=schedule(), planned_kernels=14, widths=[1, 6, 6, 1],
          gpus=1, gpu_seconds_cap=CAP, allocation_seconds_cap=CAP, cpus=6,
          gpu_reservation_reason='QOSMinGRES rejected v3 CPU-only submission; no job allocated. Count the entire reserved GPU while CPU-only diagnosis executes.',
          worker_timeout=210, libraries_threads=3, workload='fixed CPU matmul, no dataset',
          only_sweep='concurrent independent sandbox count; unchanged per-kernel settings',
          stop='worker timeout or resource failure stops enlargement; no replacement',
          acceptance='14 terminal receipts, two six-way blocks, no new lingering owned processes, no thread error',
          boundary='mechanism diagnostic, not GPU training, six-GPU capacity, speedup or quality evidence',
          unsubmitted_v1='preserved: import preflight failed because source archive excluded config_dataclasses; no kernel/job execution',
          unsubmitted_v2='preserved: import preflight lacked nonsecret SUPERIMAGE_DIR; explicit-path recheck passed, no kernel/job execution',
          rejected_v4='12 CPU per 1 GPU rejected by site ratio <=10; no allocation. v5 uses6 CPU in both widths; no performance claim.',
          files={str(p.relative_to(ROOT)): sha(p) for p in ROOT.rglob('*') if p.is_file()}))
    print(json.dumps(dict(prepared=True, root=str(ROOT), plan_sha256=sha(ROOT / 'plan.json'))))


def configure():
    os.environ.update(PYTHON_DOTENV_DISABLED='1', PYTHONDONTWRITEBYTECODE='1',
                      OMP_NUM_THREADS='3', OPENBLAS_NUM_THREADS='3', MKL_NUM_THREADS='3',
                      CUDA_VISIBLE_DEVICES='', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
                      SUPERIMAGE_DIR=str(IMAGE.parent), LOGGING_DIR=str(ROOT),
                      MLE_BENCH_DATA_DIR=str(ROOT / 'no-task-data'))
    sys.path.insert(0, str(ROOT / 'source/src'))


def worker(block, index):
    configure()
    ep = ROOT / f'block-{block}-worker-{index}'
    write(ep / 'host-before.json', resource_pressure.snapshot())
    from dojo.core.interpreters.jupyter import singularity_jupyter_server as server
    from dojo.core.interpreters.jupyter.jupyter_code_executor import JupyterCodeExecutor
    build = server._build_singularity_command

    def cpu_command(**kw):
        args = build(**kw)
        args.remove('--nv')
        # No host data mounts or GPU exposure in this thread-only diagnosis.
        args[2:2] = ['--no-mount', 'hostfs,bind-paths']
        return args

    server._build_singularity_command = cpu_command
    obj = executor = None
    start = time.time()
    error = None
    try:
        obj = server.SingularityJupyterServer(working_dir=ep, superimage_directory=str(IMAGE.parent),
              superimage_version='2026-07-macos-v1', startup_timeout=90,
              read_only_binds={str(ROOT / 'resource_pressure.py'): '/resource_pressure.py'},
              env=dict(OMP_NUM_THREADS='3', OPENBLAS_NUM_THREADS='3', MKL_NUM_THREADS='3',
                       CUDA_VISIBLE_DEVICES='', PYTHONHASHSEED='101101'))
        executor = JupyterCodeExecutor(obj, timeout=45)
        code = '''import sys,json,time
sys.path.insert(0,'/')
from pathlib import Path
import resource_pressure
before=resource_pressure.snapshot()
import numpy as np, torch
assert not torch.cuda.is_available()
np.random.seed(101101);torch.manual_seed(101101)
x=np.ones((256,256));y=x@x
z=torch.ones((256,256))@torch.ones((256,256))
assert float(y[0,0])==256.0 and float(z[0,0])==256.0
during=resource_pressure.snapshot()
time.sleep(10)
Path('kernel-receipt.json').write_text(json.dumps(dict(before=before,during=during,numpy=np.__version__,torch=torch.__version__,check=True)))
'''
        out = executor.execute_code(code)
        write(ep / 'execution.json', dict(exit_code=out.exit_code, timed_out=out.timed_out,
                                         seconds=out.exec_time))
        if out.exit_code or out.timed_out:
            # Keep only error categories, never arbitrary notebook text.
            text = '\n'.join(map(str, out.term_out)).lower()
            write(ep / 'error-categories.json', {k: k in text for k in
                  ('resource temporarily unavailable', 'cannot allocate memory', "can't start new thread", 'pthread_create', 'importerror', 'modulenotfounderror')})
            raise RuntimeError('kernel execution failed')
        raw = executor.fetch_file(Path('kernel-receipt.json'))
        write(ep / 'kernel.json', json.loads(raw))
    except Exception as exc:
        error = type(exc).__name__
    finally:
        if executor is not None:
            try:
                executor.stop()
            except Exception as exc:
                error = error or type(exc).__name__
        if obj is not None:
            obj.stop()
        write(ep / 'host-after.json', resource_pressure.snapshot())
        write(ep / 'complete.json', dict(block=block, index=index, error_type=error,
                                         start=start, end=time.time(), complete=error is None))
    return int(error is not None)


def run_one(block, index):
    ep = ROOT / f'block-{block}-worker-{index}'
    with (ep / 'worker.private.log').open('x') as log:
        proc = subprocess.Popen([str(PY), str(ROOT / NAME), 'worker', str(block), str(index)],
                                 stdout=log, stderr=log, start_new_session=True)
        try:
            rc = proc.wait(timeout=210)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
            rc = 124
    write(ep / 'terminal.json', dict(returncode=rc))
    return dict(block=block, index=index, returncode=rc)


def controller():
    plan = json.loads((ROOT / 'plan.json').read_text())
    for name, digest in plan['files'].items():
        if sha(ROOT / name) != digest:
            raise ValueError('pinned file drift')
    write(ROOT / 'step.json', resource_pressure.snapshot())
    results = []
    for block, width in enumerate((1, 6, 6, 1)):
        write(ROOT / f'block-{block}-before.json', resource_pressure.snapshot())
        with concurrent.futures.ThreadPoolExecutor(max_workers=width) as pool:
            rows = list(pool.map(lambda i: run_one(block, i), range(width)))
        results.extend(rows)
        time.sleep(3)
        write(ROOT / f'block-{block}-after.json', resource_pressure.snapshot())
        if any(r['returncode'] for r in rows):
            break
    write(ROOT / 'closed.json', dict(planned=14, attempted=len(results),
              complete=sum(r['returncode'] == 0 for r in results), rows=results,
              no_effect_claim=True))
    print(json.dumps(dict(closed=True, attempted=len(results), complete=sum(r['returncode'] == 0 for r in results))))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('prepare', 'allocation', 'controller', 'worker'))
    parser.add_argument('coordinates', nargs='*', type=int)
    args = parser.parse_args()
    if args.mode == 'prepare':
        prepare()
    elif args.mode == 'allocation':
        write(ROOT / 'allocation.json', resource_pressure.snapshot())
    elif args.mode == 'controller':
        controller()
    else:
        sys.exit(worker(*args.coordinates))
