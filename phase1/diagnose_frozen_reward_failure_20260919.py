"""Read only credential-screened exception lines from the closed reward worker."""
import json,re,hashlib
from pathlib import Path
root=Path('/research/d7/spc/yzyang4/comparison-frozen-reward-20260919-72slmwzt')
path=root/'allocation-14168.private.err'
raw=path.read_bytes()
shapes=rb'(?i)(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{16,}|gh[pousr]_[a-z0-9]{16,}|github_pat_[a-z0-9_]{20,}|Bearer\s+[a-z0-9_.-]{20,}|AKIA[A-Z0-9]{16})'
if re.search(shapes,raw):raise RuntimeError('credential shape; raw output withheld')
lines=raw.decode(errors='replace').splitlines()
exceptions=[line for line in lines if re.match(r'^(?:ValueError|RuntimeError|KeyError|TypeError|ImportError|ModuleNotFoundError|AttributeError|FileNotFoundError|IndexError):',line)]
frames=[line.strip() for line in lines if re.match(r'^\s*File "[^"\n]+\.py", line \d+, in [\w<>]+$',line)]
warnings=[line[:1000] for line in lines if 'UserWarning:' in line and ('CUDA' in line or 'NVML' in line)]
print(json.dumps(dict(log_sha256=hashlib.sha256(raw).hexdigest(),exception_lines=exceptions,frames=frames,device_warnings=warnings,bytes=len(raw))))
