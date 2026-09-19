"""Source-only bounded transport/default limits; no keys or answers."""
import hashlib,json,re
from pathlib import Path
ROOT=Path('/research/d7/spc/yzyang4/local-qwen27b-20260914-zcx1k1dy/source/src/dojo/core/solvers/llm_helpers')
paths=[ROOT/'backends/lite_llm.py',ROOT/'generic_llm.py']
output=[]
for path in paths:
    raw=path.read_bytes()
    if re.search(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{16,}|Bearer\s+[a-z0-9_.-]{20,})',raw):raise ValueError('source security')
    lines=raw.decode().splitlines();indices=set()
    for i,line in enumerate(lines):
        if any(key in line for key in ('class ','max_tokens','max_completion_tokens','generation_kwargs','def _query','def query','request_timeout','deadline_limit','TIMEOUT =')):
            indices.update(range(max(0,i-2),min(len(lines),i+4)))
    output.append(dict(path=str(path.relative_to(ROOT)),sha256=hashlib.sha256(raw).hexdigest(),lines=[dict(line=i+1,text=lines[i]) for i in sorted(indices)]))
print(json.dumps(output,indent=2))
asset=ROOT.parents[5]
for path in (asset/'model/generation_config.json',asset/'model/config.json'):
    if not path.exists():
        print(json.dumps(dict(path=str(path),exists=False)));continue
    raw=path.read_bytes()
    if re.search(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{16,}|Bearer\s+[a-z0-9_.-]{20,})',raw):raise ValueError('model config security')
    value=json.loads(raw)
    keys=('max_new_tokens','max_length','max_position_embeddings','temperature','top_p','top_k','do_sample','eos_token_id','bos_token_id','pad_token_id')
    print(json.dumps(dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),values={k:value[k] for k in keys if k in value})))
