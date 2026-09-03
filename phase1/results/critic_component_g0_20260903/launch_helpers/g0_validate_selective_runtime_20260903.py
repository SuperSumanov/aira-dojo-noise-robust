"""CPU-only dependency, trainer-import and backing-file verification for G0."""
import hashlib
import importlib.metadata as md
import json
import os
from pathlib import Path
import sys

SETUP = Path('/research/d7/spc/yzyang4/critic-component-g0/runtime-setup-20260903-r3')
TARGET = Path('/research/d7/spc/yzyang4/venvs/critic-blackwell-g0-20260903-selective')
SOURCE = Path('/research/d7/spc/yzyang4/aira-dojo-audit-9f25145')
assert Path(sys.prefix) == TARGET
assert os.environ.get('CUDA_VISIBLE_DEVICES') == ''
assert os.environ.get('PYTHONDONTWRITEBYTECODE') == '1'
payload = json.loads((SETUP / 'dependency_closure.json').read_text())
actual = {md.metadata(d.metadata['Name'])['Name'].lower().replace('_', '-'): d.version
          for d in md.distributions()}
expected = {k: v['version'] for k, v in payload['packages'].items()}
assert actual == expected, {'actual_only': sorted(actual.keys() - expected.keys()),
                            'expected_only': sorted(expected.keys() - actual.keys())}
for rel, backing in payload['links'].items():
    link = TARGET / 'lib/python3.11/site-packages' / rel
    assert link.is_symlink() and str(link.resolve()) == backing
import torch
assert torch.__version__ == '2.11.0+cu128'
assert torch.version.cuda == '12.8'
assert 'sm_120' in torch._C._cuda_getArchFlags().split()
sys.path.insert(0, str(SOURCE))
from src.mle_critic.src.train import bradley_terry
from deepspeed.ops.op_builder import CPUAdamBuilder
assert not torch.cuda.is_initialized()
assert CPUAdamBuilder().is_compatible()


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


critical = [Path(torch.__file__), Path(torch._C.__file__),
            Path(torch.__file__).parent / 'lib/libtorch_cuda.so',
            Path(torch.__file__).parent / 'lib/libtorch_cpu.so',
            SOURCE / 'src/mle_critic/src/train/bradley_terry.py']
hashes = {str(p.resolve()): digest(p) for p in critical}
result = {'status': 'CPU_IMPORT_AND_BLACKWELL_BINARY_PASS', 'python': sys.version.split()[0],
          'versions': actual, 'trainer_import': 'PASS', 'cpu_adam_builder_compatible': True,
          'torch_arch_flags': torch._C._cuda_getArchFlags(), 'cuda_build': torch.version.cuda,
          'gpu_context_created': False, 'gpu_execution_validated': False,
          'new_model_fits': 0, 'critical_file_sha256': hashes,
          'closure_sha256': digest(SETUP / 'dependency_closure.json')}
(SETUP / 'compatibility.json').write_text(json.dumps(result, sort_keys=True, indent=2) + '\n')
print(json.dumps({'status': result['status'], 'package_count': len(actual),
                  'gpu_execution_validated': False, 'trainer_import': 'PASS'}, sort_keys=True))
