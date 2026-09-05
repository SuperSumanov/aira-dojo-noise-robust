import ast
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import tarfile

commit = '0d0bcb70a6ae688f263b0224f945cd4d543f4f8e'
pending = ['phase1/scripts/validate_development_final_pipeline_cpu_20260906.py',
    'phase1/scripts/session_0904_maturity_intake_once_20260906.py',
    'phase1/tests/test_session_0904_maturity_intake_once.py']
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
target = 'tmp/development_pipeline_0d0bcb7.tar'
subprocess.run(['git', '-c', 'core.autocrlf=false', 'archive', '--format=tar', '--output='+target, commit, *sorted(seen)], check=True)
with tarfile.open(target) as tar:
    exported = {m.name: tar.extractfile(m).read() for m in tar if m.isfile()}
assert exported == seen
shell_path = 'phase1/scripts/run_prospective_continuous_intake_monitor_20260821.sh'
original = subprocess.check_output(['git', 'show', 'b20dd2682d609c0236c138c08797678cf31a2fc0:'+shell_path])
assert hashlib.sha256(original).hexdigest() == 'ef6584493de0f5e14a08bde4cc9501f268e43fb04bfd889af438666b1948eead'
insert = (b'if [[ "${mode}" == --run-once ]]; then\n'
    b'  # Foreground transaction for an active session; no PID file or background loop.\n'
    b'  verify_contracts\n  runner --require-strace\n  exit 0\nfi\n\n')
anchor = b'if [[ "${mode}" == --initialize ]]; then\n'
assert original.count(anchor) == 1
derived = original.replace(anchor, insert+anchor)
assert hashlib.sha256(derived).hexdigest() == 'f7af6bbbd3d253f3b8608a38293c7e750487f2ae72571db0b2ef07b3d1d3e599'
seen[shell_path] = derived
manifest = {'code_commit': commit, 'files': {p: {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)} for p, raw in seen.items()},
    'derived_shell': {'path': shell_path, 'original_commit': 'b20dd2682d609c0236c138c08797678cf31a2fc0',
                      'method': 'previously approved --run-once dispatch insertion only'}}
for raw in seen.values():
    assert not re.search(rb'(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|Bearer[ \t]+[A-Za-z0-9._-]{20,})', raw)
with tarfile.open(target, 'a') as tar:
    for name, raw in ((shell_path, derived), ('source_manifest.json', (json.dumps(manifest, sort_keys=True, indent=2)+'\n').encode())):
        member = tarfile.TarInfo(name); member.size = len(raw); member.mode = 0o600
        tar.addfile(member, io.BytesIO(raw))
print(json.dumps({'commit': commit, 'files': len(seen), 'archive_sha256': hashlib.sha256(Path(target).read_bytes()).hexdigest(),
    'archive_bytes': Path(target).stat().st_size, 'git_blobs_or_exact_approved_derivation': True}, sort_keys=True))
