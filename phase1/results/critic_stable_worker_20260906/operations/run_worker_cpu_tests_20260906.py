import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tarfile
import time

archive = Path('/tmp/critic_worker_b361b5b.tar')
code = Path('/tmp/critic-worker-code-b361b5b')
expected = '1e79cbb400711a0db5514e695e293a343ac64a9572326dd19f72651c3d3da15e'
os.umask(0o077)
assert hashlib.sha256(archive.read_bytes()).hexdigest() == expected and not code.exists()
code.mkdir(mode=0o700)
with tarfile.open(archive) as tar:
    members = tar.getmembers()
    assert len({m.name for m in members}) == len(members)
    assert all((m.isdir() or m.isfile()) and not Path(m.name).is_absolute() and '..' not in Path(m.name).parts for m in members)
    tar.extractall(code, filter='data')
env = dict(os.environ, PYTHONPATH=str(code), CUDA_VISIBLE_DEVICES='', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
    PYTHONDONTWRITEBYTECODE='1', OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
argv = ['/research/d7/spc/yzyang4/venvs/exp/bin/python', '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
    'phase1/tests/test_critic_training_worker.py', 'phase1/tests/test_critic_training_definition.py',
    'phase1/tests/test_critic_training_entry.py']
started = time.monotonic()
with (code/'tests.txt').open('xb') as log:
    proc = subprocess.run(argv, cwd=code, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=120)
raw = (code/'tests.txt').read_bytes()
hits = re.search(rb'(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|Bearer[ \t]+[A-Za-z0-9._-]{20,})', raw)
receipt = {'code_commit': 'b361b5b988d72556f15eb0ceb9efda4080bf8c24', 'source_archive_sha256': expected,
    'command': argv, 'returncode': proc.returncode, 'elapsed_seconds': time.monotonic()-started,
    'log_sha256': hashlib.sha256(raw).hexdigest(), 'credential_shape_hits': int(bool(hits)),
    'classification': 'CPU_WORKER_GUARDS_NOT_SLURM_OR_GPU_QUALIFICATION',
    'actual_Slurm_allocation_started': False, 'actual_model_fit_started': False}
with (code/'receipt.json').open('x') as f: json.dump(receipt, f, sort_keys=True, indent=2)
print(json.dumps(receipt, sort_keys=True), flush=True)
assert not hits
print(raw.decode(), flush=True)
assert proc.returncode == 0 and b'skipped' not in raw
