import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

ARCHIVE = Path('/tmp/critic_stable_resume_e5c9b69.tar')
CODE = Path('/tmp/critic-stable-resume-code-e5c9b69')
RUNTIME = '/research/d7/spc/yzyang4/venvs/critic-blackwell-g0-20260905-r5/bin/python'
SOURCE = '/research/d7/spc/yzyang4/worktrees/critic-g0-final-only-20260903-b'
COMMIT = 'e5c9b6935cde07849ab4a9067a9fb0ad16c3a038'
os.umask(0o077)
assert hashlib.sha256(ARCHIVE.read_bytes()).hexdigest() == 'd78cbdecc4c6535aa00b5c2aca64fc2a0bd1b0ff900c15783a62cda333bbe841'
assert shutil.which('strace') and not CODE.exists()
CODE.mkdir(mode=0o700)
with tarfile.open(ARCHIVE) as tar:
    members = tar.getmembers()
    assert len({m.name for m in members}) == len(members)
    for m in members:
        assert m.isdir() or m.isfile()
        assert not Path(m.name).is_absolute() and '..' not in Path(m.name).parts
        assert m.name.startswith('phase1/') or (m.isdir() and m.name == 'phase1')
    tar.extractall(CODE, filter='data')
env = dict(os.environ, CUDA_VISIBLE_DEVICES='', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
    TOKENIZERS_PARALLELISM='false', PYTHONHASHSEED='0', PYTHONPATH=str(CODE), PYTHONDONTWRITEBYTECODE='1',
    CRITIC_ENTRY_COMMIT=COMMIT, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
for repeat in ('a', 'b'):
    out = '/tmp/critic-entry-cpu-stable-e5c9b69-'+repeat
    argv = ['timeout', '--signal=TERM', '--kill-after=10s', '930s', 'strace', '-f', '-qq', '-e', 'trace=%file,%process',
        '-o', str(CODE/('trace-'+repeat+'.private')), RUNTIME, '-m', 'phase1.scripts.validate_critic_entry_cpu_20260906',
        '--root', out, '--source-root', SOURCE, '--layout', 'accum8', '--contract-mode', 'split']
    print(json.dumps({'starting_repeat': repeat, 'code_commit': COMMIT}), flush=True)
    subprocess.run(argv, cwd=CODE, env=env, check=True, timeout=955)
subprocess.run([RUNTIME, '-m', 'phase1.scripts.verify_critic_entry_cpu_20260906',
    '--a', '/tmp/critic-entry-cpu-stable-e5c9b69-a', '--b', '/tmp/critic-entry-cpu-stable-e5c9b69-b',
    '--layout', 'accum8', '--contract-mode', 'split'], cwd=CODE, env=env, check=True, timeout=120)
