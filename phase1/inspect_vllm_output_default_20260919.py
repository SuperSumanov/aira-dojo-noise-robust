"""Run inside existing image on CPU; inspect default generation code, no model load."""
import hashlib,json,re,sys
from pathlib import Path
roots=[Path(p)/'vllm' for p in sys.path if p and (Path(p)/'vllm').is_dir()]
root,=list(dict.fromkeys(p.resolve() for p in roots))
rows=[]
for path in (root/'entrypoints').rglob('*.py'):
    raw=path.read_bytes()
    if b'def get_max_tokens' not in raw and b'def get_max_model_len' not in raw:continue
    if re.search(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{16,})',raw):raise ValueError('source security')
    lines=raw.decode().splitlines();indices=set()
    for i,line in enumerate(lines):
        if 'def get_max_tokens' in line:indices.update(range(max(0,i-1),min(len(lines),i+70)))
    rows.append(dict(path=str(path.relative_to(root)),sha256=hashlib.sha256(raw).hexdigest(),source=[dict(line=i+1,text=lines[i]) for i in sorted(indices)]))
print(json.dumps(dict(source_only=True,rows=rows),indent=2))
