import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

ARCHIVE = Path('/tmp/critic_accum8_064da23.tar')
CODE = Path('/tmp/critic-accum8-code-064da23')
RUNTIME = '/research/d7/spc/yzyang4/venvs/critic-blackwell-g0-20260905-r5/bin/python'
SOURCE = '/research/d7/spc/yzyang4/worktrees/critic-g0-final-only-20260903-b'
COMMIT = '064da23b6643437d8f7aca4dc393e7b58989c456'
os.umask(0o077)
assert hashlib.sha256(ARCHIVE.read_bytes()).hexdigest() == '62c29b95b37dbba6d76b9a9786265f02fc2437dce6ee61bfc9f99f0b51c5cdf3'
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
    out = '/tmp/critic-entry-cpu-accum8-064da23-'+repeat
    argv = ['timeout', '--signal=TERM', '--kill-after=10s', '930s', 'strace', '-f', '-qq', '-e', 'trace=%file,%process',
        '-o', str(CODE/('trace-'+repeat+'.private')), RUNTIME, '-m', 'phase1.scripts.validate_critic_entry_cpu_20260906',
        '--root', out, '--source-root', SOURCE, '--layout', 'accum8']
    print(json.dumps({'starting_repeat': repeat, 'code_commit': COMMIT}), flush=True)
    subprocess.run(argv, cwd=CODE, env=env, check=True, timeout=955)
subprocess.run([RUNTIME, '-m', 'phase1.scripts.verify_critic_entry_cpu_20260906',
    '--a', '/tmp/critic-entry-cpu-accum8-064da23-a', '--b', '/tmp/critic-entry-cpu-accum8-064da23-b', '--layout', 'accum8'],
    cwd=CODE, env=env, check=True, timeout=120)
