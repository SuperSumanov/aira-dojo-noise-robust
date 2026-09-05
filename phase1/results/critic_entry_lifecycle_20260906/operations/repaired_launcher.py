"""Same pinned CPU test; accept tar's explicit top-level directory record."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

ARCHIVE = Path('/tmp/critic_entry_95e72f3.tar')
SHA = 'e54c299dbe7e3c85b1d2ab99f3327fe7eb68366e0b80f092774271fc5700de71'
CODE = Path('/tmp/critic-entry-code-95e72f3-r2')
RUNTIME = '/research/d7/spc/yzyang4/venvs/critic-blackwell-g0-20260905-r5/bin/python'
SOURCE = '/research/d7/spc/yzyang4/worktrees/critic-g0-final-only-20260903-b'
os.umask(0o077)
assert hashlib.sha256(ARCHIVE.read_bytes()).hexdigest() == SHA
assert shutil.which('strace') and not CODE.exists()
CODE.mkdir(mode=0o700)
with tarfile.open(ARCHIVE) as tar:
    for m in tar:
        assert m.isdir() or m.isfile()
        assert not Path(m.name).is_absolute() and '..' not in Path(m.name).parts
        assert m.name.startswith('phase1/') or (m.isdir() and m.name == 'phase1')
    tar.extractall(CODE, filter='data')
env = dict(os.environ, CUDA_VISIBLE_DEVICES='', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
    TOKENIZERS_PARALLELISM='false', PYTHONHASHSEED='0', PYTHONPATH=str(CODE),
    CRITIC_ENTRY_COMMIT='95e72f37c1b745ca101390c887c41eed6e9b6f28', OMP_NUM_THREADS='1')
for repeat in ('a', 'b'):
    out = '/tmp/critic-entry-cpu-95e72f3-'+repeat
    argv = ['timeout', '--signal=TERM', '--kill-after=10s', '930s', 'strace', '-f', '-qq', '-e', 'trace=%file,%process',
        '-o', str(CODE/('trace-'+repeat+'.private')), RUNTIME, '-m', 'phase1.scripts.validate_critic_entry_cpu_20260906',
        '--root', out, '--source-root', SOURCE]
    print(json.dumps({'starting_repeat': repeat, 'code_commit': env['CRITIC_ENTRY_COMMIT']}), flush=True)
    subprocess.run(argv, cwd=CODE, env=env, check=True, timeout=955)
subprocess.run([RUNTIME, '-m', 'phase1.scripts.verify_critic_entry_cpu_20260906',
    '--a', '/tmp/critic-entry-cpu-95e72f3-a', '--b', '/tmp/critic-entry-cpu-95e72f3-b'],
    cwd=CODE, env=env, check=True, timeout=120)
