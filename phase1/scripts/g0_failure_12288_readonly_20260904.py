"""Read exact failed-job operational files; redact before any text output."""
import hashlib
import json
from pathlib import Path
import re

root = Path('/research/d7/spc/yzyang4/critic-component-g0')
paths = [root/'submissions/20260903-g0-r2/slurm-12288.out']
paths += [root/'runs/job-12288'/n for n in ('worker.log', 'FAILED', 'training_exit_status.txt', 'resource_usage.txt')]
shape = re.compile(r'(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16}|AIza[0-9A-Za-z_-]{30,})(?![A-Za-z0-9])|(?:api[_-]?key|access[_-]?token|auth[_-]?token|secret[_-]?key|password)\s*[=:]\s*\S+|Bearer\s+\S+')
out = []
for p in paths:
    if not p.exists():
        out.append(dict(file=str(p.relative_to(root)), exists=False)); continue
    if not p.is_file() or p.is_symlink() or p.stat().st_size > 4*1024*1024:
        raise RuntimeError('unsafe_or_oversize_operational_input')
    raw = p.read_bytes()
    safe, hits = shape.subn('[REDACTED_CREDENTIAL]', raw.decode('utf-8', errors='replace'))
    lines = [line for line in safe.splitlines() if not re.search(r'(?i)eval_pair_accuracy|eval_loss|prediction_values|label_vault', line)]
    out.append(dict(file=str(p.relative_to(root)), exists=True, bytes=len(raw),
                    sha256=hashlib.sha256(raw).hexdigest(), credential_shape_hits=hits,
                    safe_operational_tail=lines[-100:]))
print(json.dumps(dict(job_id=12288, status='READ_ONLY_OPERATIONAL_DIAGNOSTIC', files=out), sort_keys=True))
