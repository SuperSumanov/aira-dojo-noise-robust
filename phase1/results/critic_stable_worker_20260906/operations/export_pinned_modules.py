import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tarfile

p = argparse.ArgumentParser()
p.add_argument('--commit', required=True)
p.add_argument('--output', type=Path, required=True)
p.add_argument('modules', nargs='+')
a = p.parse_args()
assert re.fullmatch('[0-9a-f]{40}', a.commit)
assert a.output.parent == Path('tmp') and a.output.suffix == '.tar' and not a.output.exists()
pending = list(a.modules); seen = {}
while pending:
    path = pending.pop()
    assert path.startswith('phase1/') and '..' not in Path(path).parts
    if path in seen: continue
    raw = subprocess.check_output(['git', 'show', a.commit+':'+path]); seen[path] = raw
    if not path.endswith('.py'): continue
    for n in ast.walk(ast.parse(raw.decode())):
        if isinstance(n, ast.ImportFrom): names = [n.module]+[n.module+'.'+x.name for x in n.names] if n.module else []
        elif isinstance(n, ast.Import): names = [x.name for x in n.names]
        else: continue
        for name in names:
            q = name.replace('.', '/')+'.py'
            if name.startswith('phase1.') and Path(q).is_file(): pending.append(q)
secret = re.compile(rb'(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|Bearer[ \t]+[A-Za-z0-9._-]{20,})')
assert all(not secret.search(raw) for raw in seen.values())
subprocess.run(['git', '-c', 'core.autocrlf=false', 'archive', '--format=tar', '--output='+str(a.output), a.commit, *sorted(seen)], check=True)
with tarfile.open(a.output) as t:
    assert {m.name: t.extractfile(m).read() for m in t if m.isfile()} == seen
print(json.dumps({'commit': a.commit, 'source_files': len(seen), 'archive_sha256': hashlib.sha256(a.output.read_bytes()).hexdigest(),
    'archive_bytes': a.output.stat().st_size, 'matches_git_blobs': True}, sort_keys=True))
