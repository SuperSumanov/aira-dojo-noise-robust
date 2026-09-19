"""Allowlisted serving health counters, no request/response content or credentials."""
import json,re
from pathlib import Path
ROOT=Path('/research/d7/spc/yzyang4/comparison-depth2-debug-20260919-ffunn8gg')
path=ROOT/'service.private.log'
if ROOT.resolve(strict=True)!=ROOT or path.is_symlink():raise ValueError('scope')
with path.open('rb') as handle:
    handle.seek(0,2);size=handle.tell();handle.seek(max(0,size-2*1024**2));raw=handle.read()
shape=re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{16,}|gh[pousr]_[a-z0-9]{16,}|Bearer\s+[a-z0-9_.-]{20,})')
text=raw.decode(errors='replace')
requests=re.findall(r'POST /v1/chat/completions HTTP/1\.[01]"\s+(\d{3})',text)
load=re.findall(r'Running:\s*(\d+) reqs,\s*Waiting:\s*(\d+) reqs',text)
speed=re.findall(r'Avg generation throughput:\s*([\d.]+) tokens/s',text)
print(json.dumps(dict(role='structural_serving_counters_only',log_bytes=size,credential_shape_hits=len(shape.findall(raw)),
    completed_http_statuses=requests,last_running_waiting=list(map(int,load[-1])) if load else None,
    recent_generation_tokens_per_second=[float(x) for x in speed[-3:]])))
