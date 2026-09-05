"""Rebind the existing CPU save regression to R5 version-identical dependencies."""
import contextlib
import hashlib
import importlib.metadata as md
import json
import os
from pathlib import Path
import sys

def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()

base = Path('/research/d7/spc/yzyang4/critic-component-g0')
cpu = base / 'recovery-20260903-r2/cpu_regression'
setup = base / 'runtime-setup-20260903-r3'
source = Path('/research/d7/spc/yzyang4/worktrees/critic-g0-final-only-20260903-b')
runtime = Path('/research/d7/spc/yzyang4/venvs/critic-blackwell-g0-20260905-r5')
assert os.environ['CUDA_VISIBLE_DEVICES'] == '' and os.environ['PYTHONDONTWRITEBYTECODE'] == '1'
assert Path(sys.prefix) == runtime
assert sha(cpu / 'receipt.json') == 'c3c0a2275f10806028283a876d7b8cf16e57ffc710cf1d6d34a3580f57e885a2'
receipt = json.loads((cpu / 'receipt.json').read_text())
assert receipt['checkpoint_roundtrip_equal'] and receipt['metadata_overwrite_rejected']
assert sha(source / 'src/mle_critic/scripts/train/pro6000/train_rm_confirmatory_one.sh') == receipt['launcher_sha256']
assert sha(cpu / 'resolved_cli.json') == receipt['resolved_cli_sha256']
closure = json.loads((setup / 'dependency_closure.json').read_text())
compat = json.loads((setup / 'compatibility.json').read_text())
assert sha(setup / 'dependency_closure.json') == compat['closure_sha256']
actual = {md.metadata(d.metadata['Name'])['Name'].lower().replace('_', '-'): d.version for d in md.distributions()}
assert actual == {k: v['version'] for k, v in closure['packages'].items()}
for relative, backing in closure['links'].items():
    p = runtime / 'lib/python3.11/site-packages' / relative
    assert p.is_symlink() and str(p.resolve(strict=True)) == backing
for p, expected in compat['critical_file_sha256'].items():
    assert sha(p) == expected
with contextlib.redirect_stdout(sys.stderr):
    import torch
    from transformers import Trainer
    assert sha(sys.modules[Trainer.__module__].__file__) == receipt['framework_sha256']
    assert not torch.cuda.is_initialized()
    assert torch.__version__ == '2.11.0+cu128' and 'sm_120' in torch._C._cuda_getArchFlags().split()
cfg = json.loads((cpu / 'resolved_cli.json').read_text())
for key, value in {'max_steps':10, 'eval_steps':10, 'max_len':16384, 'seed':6,
                   'save_only_model':True, 'load_best_model_at_end':False,
                   'save_strategy':'best', 'gradient_accumulation_steps':8,
                   'per_device_train_batch_size':8, 'per_device_eval_batch_size':8}.items():
    assert cfg[key] == value, key
print(json.dumps({'status':'UNCHANGED_RUNTIME_SOURCE_AND_CPU_SAVE_REGRESSION_BOUND',
                  'source_commit':receipt['source_commit'], 'launcher_sha256':receipt['launcher_sha256'],
                  'framework_sha256':receipt['framework_sha256'], 'resolved_cli_sha256':receipt['resolved_cli_sha256'],
                  'runtime_critical_hashes_rechecked':len(compat['critical_file_sha256']),
                  'package_versions_rechecked':len(actual), 'gpu_context_created':False,
                  'model_fits':0, 'distributed_save_validated':False}, sort_keys=True))
