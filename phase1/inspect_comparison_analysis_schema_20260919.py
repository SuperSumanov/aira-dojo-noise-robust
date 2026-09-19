"""Credential-first structural diagnosis of all eight closed analysis replies."""
import hashlib,json,math,re
from pathlib import Path
ROOT=Path('/research/d7/spc/yzyang4/comparison-cache-acceptance-20260919-tsefctlz')
SECRET=re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{16,}|gh[pousr]_[a-z0-9]{16,}|Bearer\s+[a-z0-9_.-]{20,})')
if json.loads((ROOT/'closed.json').read_bytes())['status']!='eight_analyses_closed':raise ValueError('not closed')
rows=[]
for i in range(8):
    receipt=json.loads((ROOT/f'analysis-{i}.json').read_bytes())
    row=dict(index=i,status=receipt['status'],error_type=receipt.get('error_type'))
    path=ROOT/f'answer-{i}.private.json'
    if path.exists():
        raw=path.read_bytes()
        if SECRET.search(raw):raise ValueError('private answer credential hit; withheld')
        answer=json.loads(raw);response=answer['response'];row['response_type']=type(response).__name__
        row['answer_sha256']=hashlib.sha256(raw).hexdigest()
        if isinstance(response,dict):
            row['required_fields']={k:dict(present=k in response,type=type(response.get(k)).__name__) for k in ('is_bug','metric','summary')}
            metric=response.get('metric')
            row['finite_numeric_metric']=type(metric) in (float,int) and math.isfinite(metric)
        row['finish_reason']=answer['info']['usage'].get('finish_reason')
    rows.append(row)
print(json.dumps(dict(rows=rows,credential_hits=0,model_calls=0),indent=2))
