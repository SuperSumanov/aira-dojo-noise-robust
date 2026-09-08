"""One new bounded CPU transaction; never restart an interrupted directory."""
import hashlib
import json
import os
import signal
import subprocess
import sys
import tarfile
from pathlib import Path, PurePosixPath

ROOT = Path('/research/d7/spc/yzyang4/forets-selection-20260908-YyGg83UH')
ARCHIVE_SHA256 = 'cc53a41c407d005f4b8239d145bee53705449fb564a5ffc2436d8a6446500e97'
SOURCE_COMMIT = '82242e68e6d5f5584972ae7f892236d0454e64b1'
FILES = {'phase1/forets_execution_witness_20260908.py',
         'phase1/forets_execution_patch_20260908.py',
         'phase1/tests/test_forets_execution_witness_20260908.py',
         'phase1/forets_selection_20260908.py',
         'phase1/forets_selection_patch_20260908.py',
         'phase1/forets_selection_linux_validation_20260908.py',
         'phase1/tests/test_forets_selection_20260908.py', 'source_cache.json'}


def main():
    os.umask(0o077)
    assert ROOT.resolve() == ROOT and ROOT.stat().st_mode & 0o077 == 0
    assert {p.name for p in ROOT.iterdir()} == {'payload.tar'}, 'not fresh; inspect instead of retry'
    archive = ROOT / 'payload.tar'
    assert archive.stat().st_size == 92160
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == ARCHIVE_SHA256
    fd = os.open(ROOT / 'RUN_STARTED', os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    with tarfile.open(archive, 'r:') as tar:
        members = tar.getmembers()
        files = [m.name for m in members if m.isfile()]
        assert len(files) == len(FILES) and set(files) == FILES
        parents = {str(p) for name in FILES for p in PurePosixPath(name).parents}
        for m in members:
            assert m.isfile() and m.name in FILES or m.isdir() and m.name.rstrip('/') in parents
            assert not m.name.startswith('/') and '..' not in PurePosixPath(m.name).parts
        tar.extractall(ROOT, filter='data')
    before = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in sorted(FILES)}
    env = os.environ.copy()
    env.update(FORETS_SELECTION_CACHE=str(ROOT / 'source_cache.json'),
               PYTHONDONTWRITEBYTECODE='1', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',
               PYTHONPATH=str(ROOT), CUDA_VISIBLE_DEVICES='')
    env.pop('FORETS_SELECTION_TREE', None)
    process = subprocess.Popen([sys.executable, '-B', '-m', 'phase1.forets_selection_linux_validation_20260908'],
        cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=270)
    except subprocess.TimeoutExpired:
        timed_out = True
        # Only the process group created immediately above, never a discovered PID.
        os.killpg(process.pid, signal.SIGTERM)
        try:
            stdout, stderr = process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            stdout, stderr = process.communicate(timeout=10)
    (ROOT / 'test_stdout.txt').write_text(stdout, encoding='utf-8')
    (ROOT / 'test_stderr.txt').write_text(stderr, encoding='utf-8')
    after = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in sorted(FILES)}
    receipt = dict(source_commit=SOURCE_COMMIT, archive_sha256=ARCHIVE_SHA256,
                   file_sha256=after, unchanged_inputs=(before == after),
                   exit_code=process.returncode, timed_out=timed_out)
    (ROOT / 'validation_receipt.json').write_text(json.dumps(receipt, sort_keys=True), encoding='utf-8')
    print(stdout, end='')
    print(json.dumps(receipt, sort_keys=True))
    assert before == after and not timed_out, 'input drift or timeout; do not retry'
    return process.returncode


if __name__ == '__main__':
    sys.exit(main())
