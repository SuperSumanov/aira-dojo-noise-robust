import ast
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import tarfile

commit = subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode().strip()
assert commit == '95e72f37c1b745ca101390c887c41eed6e9b6f28'
pending = ['phase1/scripts/validate_critic_entry_cpu_20260906.py', 'phase1/scripts/verify_critic_entry_cpu_20260906.py']
seen = {}
while pending:
    path = pending.pop()
    if path in seen: continue
    raw = subprocess.check_output(['git', 'show', commit+':'+path]); seen[path] = raw
    for node in ast.walk(ast.parse(raw.decode())):
        if isinstance(node, ast.ImportFrom):
            names = [node.module]+[node.module+'.'+x.name for x in node.names] if node.module else []
        elif isinstance(node, ast.Import): names = [x.name for x in node.names]
        else: continue
        for name in names:
            candidate = name.replace('.', '/')+'.py'
            if name.startswith('phase1.') and Path(candidate).is_file(): pending.append(candidate)
for path in ('phase1/g_reuse_development_screen_v1.json',):
    seen[path] = subprocess.check_output(['git', 'show', commit+':'+path])
for path, raw in seen.items():
    assert not re.search(rb'(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|Bearer[ \t]+[A-Za-z0-9._-]{20,})', raw), path
target = 'tmp/critic_entry_95e72f3.tar'
subprocess.run(['git', '-c', 'core.autocrlf=false', 'archive', '--format=tar', '--output='+target, commit, *sorted(seen)], check=True)
with tarfile.open(target) as tar:
    exported = {m.name: tar.extractfile(m).read() for m in tar if m.isfile()}
assert exported == seen
print(json.dumps({'commit': commit, 'files': len(seen), 'archive_sha256': hashlib.sha256(Path(target).read_bytes()).hexdigest(),
    'members_match_git_blobs': True, 'archive_bytes': Path(target).stat().st_size}, sort_keys=True))
