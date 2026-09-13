"""Static exploration of the already public, old-development repair inventory.

No target selection, code execution, new outcome access or API request.
"""
import ast,collections,hashlib,json,re
from pathlib import Path
P=Path('/research/d7/spc/yzyang4/forets-repair-memory-inventory-20260913-vcg12_1y/observed-repair-code.private.json')
EXPECTED='4caeb8a6494705b7fd103bc66a015b1e8e63f38ffd086267b2bf0499d9884dcb'
raw=P.read_bytes()
if hashlib.sha256(raw).hexdigest()!=EXPECTED:raise ValueError('old inventory drift')
secret=re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{16,}|gh[pousr]_[a-z0-9]{16,}|github_pat_[a-z0-9_]{20,}|Bearer\s+[a-z0-9_.-]{20,})')
if secret.search(raw):raise ValueError('credential-shape; no content output')
rows=json.loads(raw)['rows'];out=[]
def shapes(code):
    t=ast.parse(code);calls=collections.Counter()
    for n in ast.walk(t):
        if isinstance(n,ast.Call):
            f=n.func;name=f.id if isinstance(f,ast.Name) else f.attr if isinstance(f,ast.Attribute) else type(f).__name__
            calls[name]+=1
    return calls
for r in rows:
    before=shapes(r['parent_code']);after=shapes(r['observed_successful_child_code'])
    out.append(dict(task=r['task'],parent_families=r['parent_families'],diff_sha256=r['diff_sha256'],
        removed_calls=dict(before-after),added_calls=dict(after-before),diff=r['observed_diff']))
print(json.dumps(dict(rows=out,api_calls=0,gpu_jobs=0,new_trials_read=False,scope='old observed repair shapes only')))
