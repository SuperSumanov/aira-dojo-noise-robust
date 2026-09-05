import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tarfile

archive = Path('/tmp/accum8_gradient_decfcb4.tar')
code = Path('/tmp/accum8-gradient-code-decfcb4')
expected = '3e788d9d169588e4f9d221f8480a98cc16812c5146ae9f8f8395838e3d2b6fa5'
assert hashlib.sha256(archive.read_bytes()).hexdigest() == expected
os.umask(0o077)
assert not code.exists(); code.mkdir()
with tarfile.open(archive) as t:
    ms = t.getmembers()
    assert len({m.name for m in ms}) == len(ms)
    for m in ms:
        assert m.isfile() or m.isdir()
        assert not Path(m.name).is_absolute() and '..' not in Path(m.name).parts
        assert m.name.startswith('phase1/') or (m.isdir() and m.name == 'phase1')
    t.extractall(code, filter='data')
env = dict(os.environ, CUDA_VISIBLE_DEVICES='', OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1',
    HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', PYTHONHASHSEED='0', PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=str(code),
    CONSUMER_CODE_COMMIT='decfcb4f571f81134fcef0f9208f9fad8edd1ac4')
runtime = '/research/d7/spc/yzyang4/venvs/critic-blackwell-g0-20260905-r5/bin/python'
secret = re.compile(rb'(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|Bearer[ \t]+[A-Za-z0-9._-]{20,})')
for repeat in ('a', 'b'):
    with (code/f'{repeat}.log').open('xb') as log:
        run = subprocess.run(['timeout', '--signal=TERM', '--kill-after=10s', '600s', runtime, '-m',
            'phase1.scripts.validate_global_local_critic_consumer_20260905', '--layout', 'accum8',
            '--source-root', '/research/d7/spc/yzyang4/worktrees/critic-g0-final-only-20260903-b',
            '--output', str(code/repeat)], cwd=code, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=620)
    assert run.returncode == 0, 'accum8_gradient_validation_failed'
    raw = (code/repeat/'summary.json').read_bytes()
    assert not secret.search(raw)
    summary = json.loads(raw)
    print(json.dumps({'repeat': repeat, 'cases': summary['cases'], 'max_abs_gradient_error': summary['max_abs_gradient_error'],
        'max_abs_parameter_error': summary['max_abs_parameter_error'], 'summary_sha256': hashlib.sha256(raw).hexdigest()}), flush=True)
for name in ('summary.json', 'cases.csv'):
    assert (code/'a'/name).read_bytes() == (code/'b'/name).read_bytes()
with tarfile.open(archive) as t:
    for m in t:
        if m.isfile(): assert (code/m.name).read_bytes() == t.extractfile(m).read()
print(json.dumps({'AB_summary_and_cases_equal': True, 'source_unchanged': True, 'production_or_effect_fit': False}))
