import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tarfile

commit = '8f96819c2361fe752c3c25063fdaa6e57fde9ac7'
assert subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode().strip() == commit
pending = ['phase1/tests/test_critic_zero3_final_state.py']
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
for path, raw in seen.items():
    assert not re.search(rb'(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|Bearer[ \t]+[A-Za-z0-9._-]{20,})', raw), path
target = Path('tmp/critic_zero3_readout_8f96819.tar')
assert not target.exists()
subprocess.run(['git', '-c', 'core.autocrlf=false', 'archive', '--format=tar', '--output='+str(target), commit, *sorted(seen)], check=True)
with tarfile.open(target) as tar:
    assert {m.name: tar.extractfile(m).read() for m in tar if m.isfile()} == seen
print(json.dumps({'commit': commit, 'files': len(seen), 'archive_sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
    'members_match_git_blobs': True, 'archive_bytes': target.stat().st_size}, sort_keys=True))
