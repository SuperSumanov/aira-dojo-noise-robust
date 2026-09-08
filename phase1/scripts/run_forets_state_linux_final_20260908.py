"""Single bounded CPU validation in an explicitly new private directory."""
import hashlib
import json
import os
import subprocess
import sys
import tarfile
from pathlib import Path, PurePosixPath

ROOT = Path('/research/d7/spc/yzyang4/forets-state-final-20260908-2sFlhEkg')
ARCHIVE_SHA256 = 'bcd7b6333c703dcaf37248265700b733c3cc4a197fc968cf0c1950a4f23cf7a9'
SOURCE_COMMIT = 'ed14932b740b6ac9790ccaf5ebe000dd80989b0b'
FILES = {
    'phase1/forets_candidate_ledger_20260908.py',
    'phase1/forets_batch_runtime_20260908.py',
    'phase1/forets_state_patch_20260908.py',
    'phase1/forets_linux_validation_20260908.py',
    'phase1/forets_upstream_hotfix_20260908.py',
    'phase1/tests/test_forets_candidate_state_20260908.py',
    'phase1/tests/test_forets_upstream_hotfix_20260908.py',
    'codex_tmp/forets-state-20260908/source_cache.json',
}

def main():
    os.umask(0o077)
    assert ROOT.resolve() == ROOT and ROOT.is_dir() and ROOT.stat().st_mode & 0o077 == 0
    assert {p.name for p in ROOT.iterdir()} == {'payload.tar'}, 'directory not fresh; no retry'
    archive = ROOT / 'payload.tar'
    assert archive.stat().st_size == 139264
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == ARCHIVE_SHA256
    # Exclusive intent: interrupted validation is inspected, not restarted in place.
    fd = os.open(ROOT / 'RUN_STARTED', os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    with tarfile.open(archive, 'r:') as tar:
        members = tar.getmembers()
        actual_files = [m.name for m in members if m.isfile()]
        assert set(actual_files) == FILES and len(actual_files) == len(FILES)
        parents = {str(p) for name in FILES for p in PurePosixPath(name).parents}
        for m in members:
            assert (m.isfile() and m.name in FILES or m.isdir() and m.name.rstrip('/') in parents)
            assert not m.name.startswith('/') and '..' not in PurePosixPath(m.name).parts
        tar.extractall(ROOT, filter='data')
    before = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in sorted(FILES)}
    env = os.environ.copy()
    env.update(FORETS_SOURCE_CACHE=str(ROOT / 'codex_tmp/forets-state-20260908/source_cache.json'),
               PYTHONDONTWRITEBYTECODE='1', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',
               PYTHONPATH=str(ROOT))
    env.pop('FORETS_STATE_TREE', None)
    env.pop('FORETS_PATCHED_TREE', None)
    try:
        result = subprocess.run([sys.executable, '-B', '-m', 'phase1.forets_linux_validation_20260908'],
                                cwd=ROOT, env=env, capture_output=True, text=True, timeout=300)
        (ROOT / 'test_stdout.txt').write_text(result.stdout, encoding='utf-8')
        (ROOT / 'test_stderr.txt').write_text(result.stderr, encoding='utf-8')
        print(result.stdout, end='')
        if result.stderr:
            print(result.stderr, file=sys.stderr, end='')
        rc = result.returncode
    except subprocess.TimeoutExpired as exc:
        rc = 124
        (ROOT / 'TIMEOUT').write_text('CPU validation exceeded 300 seconds; no automatic retry\n')
    after = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in sorted(FILES)}
    receipt = dict(source_commit=SOURCE_COMMIT, archive_sha256=ARCHIVE_SHA256,
                   file_sha256=after, unchanged_inputs=(before == after), exit_code=rc)
    (ROOT / 'validation_receipt.json').write_text(json.dumps(receipt, sort_keys=True), encoding='utf-8')
    print(json.dumps(receipt, sort_keys=True))
    assert before == after, 'input hash drift'
    return rc

if __name__ == '__main__':
    sys.exit(main())
