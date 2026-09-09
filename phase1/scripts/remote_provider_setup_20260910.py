"""Receive a user-authorized credential on SSH stdin; persist only remotely.

Never place the credential in argv, logs, a local file, or a Git artifact.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile


def main():
    root = Path('/research/d7/spc/yzyang4/aira-dojo')
    target = root/'.env'
    if os.name != 'posix' or target.is_symlink() or not target.is_file():
        raise RuntimeError('expected existing remote environment file')
    tracked = subprocess.run(['git', '-C', str(root), 'ls-files', '--error-unmatch', '.env'],
                             capture_output=True, check=False)
    if tracked.returncode != 1:
        raise RuntimeError('environment file is tracked or Git state is unknown')
    print('READY_FOR_PRIVATE_INPUT', flush=True)
    value = sys.stdin.buffer.readline(256).strip()
    if not re.fullmatch(rb'sk-or-v1-[A-Za-z0-9_-]{32,200}', value):
        raise RuntimeError('invalid credential shape')
    before = target.read_bytes()
    pattern = re.compile(rb'(?m)^(?:export[ \t]+)?OPENROUTER_API_KEY[ \t]*=.*(?:\r?\n|$)')
    matches = list(pattern.finditer(before))
    if len(matches) > 1:
        raise RuntimeError('duplicate provider entries; no change made')
    if matches:
        existing = matches[0].group().split(b'=', 1)[1].strip().strip(b'\"\'')
        if existing and existing != value:
            raise RuntimeError('existing credential differs; no change made')
        after = pattern.sub(lambda m: b'OPENROUTER_API_KEY=' + value + b'\n', before, count=1)
    else:
        after = before + (b'' if before.endswith(b'\n') else b'\n') + b'OPENROUTER_API_KEY=' + value + b'\n'
    fd, temporary = tempfile.mkstemp(prefix='.provider-install-', dir=root)
    try:
        with os.fdopen(fd, 'wb') as f:
            os.fchmod(f.fileno(), 0o600)
            f.write(after); f.flush(); os.fsync(f.fileno())
        if target.read_bytes() != before:
            raise RuntimeError('environment changed concurrently; no replacement made')
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    print(json.dumps(dict(installed=True, mode=oct(target.stat().st_mode & 0o777),
                          credential_echoed=False, existing_primary_unchanged=True)))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(json.dumps(dict(installed=False, error_type=type(exc).__name__)))
        raise SystemExit(1)
