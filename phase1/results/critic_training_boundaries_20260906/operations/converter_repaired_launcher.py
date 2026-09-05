import hashlib
import json
import os
from pathlib import Path
import subprocess

code = Path('/tmp/critic-zero3-readout-code-8f96819')
archive = Path('/tmp/critic_zero3_readout_8f96819.tar')
assert hashlib.sha256(archive.read_bytes()).hexdigest() == '0538e582a7359edc4b750575d975e159e4caab88fd8bfa765868e0747a107a9d'
import tarfile
with tarfile.open(archive) as tar:
    for m in tar:
        if m.isfile(): assert (code/m.name).read_bytes() == tar.extractfile(m).read()
result = code/'retry-tests-with-pytest'
os.umask(0o077)
assert not result.exists(); result.mkdir()
env = dict(os.environ, CUDA_VISIBLE_DEVICES='', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
    PYTHONHASHSEED='0', PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=str(code), PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',
    OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
runtime = '/research/d7/spc/yzyang4/venvs/critic-blackwell-g0-20260905-r5/bin/python'
# Append, do not prepend: the qualified runtime's Torch/DS/etc retain priority.
program = """import sys,json
sys.path.append('/research/d7/spc/yzyang4/venvs/exp/lib/python3.11/site-packages')
import torch,pytest
assert torch.__version__ == '2.11.0+cu128'
assert pytest.__version__ == '7.4.3'
print(json.dumps({'torch':torch.__version__,'pytest':pytest.__version__,'pytest_appended_for_test_only':True}),flush=True)
raise SystemExit(pytest.main(['-q','-p','no:cacheprovider','phase1/tests/test_critic_zero3_final_state.py',
    '--basetemp=/tmp/critic-zero3-readout-code-8f96819/retry-tests-with-pytest/self-generated-fixtures']))
"""
with (result/'tests.txt').open('xb') as log:
    run = subprocess.run(['timeout', '--signal=TERM', '--kill-after=5s', '180s', runtime, '-c', program],
        cwd=code, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=195)
raw = (result/'tests.txt').read_bytes()
receipt = {'code_commit': '8f96819c2361fe752c3c25063fdaa6e57fde9ac7', 'returncode': run.returncode,
    'test_log_sha256': hashlib.sha256(raw).hexdigest(), 'test_log_bytes': len(raw),
    'pinned_converter_tests_passed': run.returncode == 0 and b'9 passed' in raw,
    'actual_deepspeed_engine': False, 'GPU_used': False,
    'prior_failure_did_not_execute_converter': True, 'installed_environments_modified': False}
(result/'receipt.json').write_text(json.dumps(receipt, sort_keys=True, indent=2))
print(json.dumps(receipt, sort_keys=True))
assert receipt['pinned_converter_tests_passed'], 'zero3_readout_tests_failed'
