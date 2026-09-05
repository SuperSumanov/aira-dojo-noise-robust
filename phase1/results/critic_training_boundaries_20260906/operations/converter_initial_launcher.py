import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile

archive = Path('/tmp/critic_zero3_readout_8f96819.tar')
code = Path('/tmp/critic-zero3-readout-code-8f96819')
assert hashlib.sha256(archive.read_bytes()).hexdigest() == '0538e582a7359edc4b750575d975e159e4caab88fd8bfa765868e0747a107a9d'
os.umask(0o077)
assert not code.exists(); code.mkdir()
with tarfile.open(archive) as tar:
    members = tar.getmembers()
    assert len({m.name for m in members}) == len(members)
    for m in members:
        assert m.isdir() or m.isfile()
        assert not Path(m.name).is_absolute() and '..' not in Path(m.name).parts
        assert m.name.startswith('phase1/') or (m.isdir() and m.name == 'phase1')
    tar.extractall(code, filter='data')
env = dict(os.environ, CUDA_VISIBLE_DEVICES='', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
    PYTHONHASHSEED='0', PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=str(code),
    OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
runtime = '/research/d7/spc/yzyang4/venvs/critic-blackwell-g0-20260905-r5/bin/python'
with (code/'tests.txt').open('xb') as log:
    run = subprocess.run(['timeout', '--signal=TERM', '--kill-after=5s', '180s', runtime, '-m', 'pytest', '-q',
        'phase1/tests/test_critic_zero3_final_state.py', '--basetemp='+str(code/'self-generated-fixtures')],
        cwd=code, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=195)
raw = (code/'tests.txt').read_bytes()
receipt = {'code_commit': '8f96819c2361fe752c3c25063fdaa6e57fde9ac7', 'returncode': run.returncode,
    'test_log_sha256': hashlib.sha256(raw).hexdigest(), 'test_log_bytes': len(raw),
    'actual_deepspeed_converter': True, 'actual_deepspeed_engine': False, 'GPU_used': False}
(code/'receipt.json').write_text(json.dumps(receipt, sort_keys=True, indent=2))
print(json.dumps(receipt, sort_keys=True))
assert run.returncode == 0, 'zero3_readout_tests_failed'
