"""Closed startup error only; redact remotely, export no candidate or env."""
import hashlib
import json
from pathlib import Path
import re
from safe_senior_reader import redact

R=Path('/research/d7/spc/yzyang4/clock-rank-confirmation-20261016-v1')
assert json.loads((R/'launch.json').read_text())['job']=='18844'
paths=[R/'episode-0/worker.private.log']
paths+=list((R/'episode-0').rglob('*stderr*'))
out=[]
for p in paths:
    if not p.is_file():continue
    safe,counts=redact(p.read_text(errors='replace'))
    frames=re.findall(r'File "([^"\n]+)", line (\d+), in ([^\n]+)',safe)
    errors=[line[:1000] for line in safe.splitlines() if re.search(r'(?:Error|Exception|AssertionError|SystemExit):',line)]
    out.append(dict(path=str(p.relative_to(R)),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
        redaction_counts=counts,frames=frames[-20:],redacted_error_lines=errors[-12:]))
print(json.dumps(out))
