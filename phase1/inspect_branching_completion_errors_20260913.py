"""Closed development only: export bounded redacted error signatures, not code."""
import collections
import hashlib
import json
from pathlib import Path
import re

ROOT=Path('/research/d7/spc/yzyang4/forets-pool-completion-20260912-cwhdnjnp')
SECRET=re.compile(r'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{16,}|gh[pousr]_[a-z0-9]{16,}|github_pat_[a-z0-9_]{20,}|Bearer\s+[a-z0-9_.-]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')
ANSI=re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')
def sha(b):return hashlib.sha256(b).hexdigest()
def run():
    s=json.loads((ROOT/'completion-summary.json').read_bytes())
    if s['planned']!=8 or s['attempted']!=8:raise ValueError('closure')
    rows=[]
    for i in range(8):
        result=json.loads((ROOT/f'result-{i}.json').read_bytes())
        raw=(ROOT/f'program-{i}.txt').read_bytes()
        if sha(raw)!=result['output_sha256']:raise ValueError('output drift')
        txt=ANSI.sub('',SECRET.sub('[REDACTED]',raw.decode()))
        errors=[x.strip()[:800] for x in txt.splitlines() if re.match(r'^\w+(?:Error|Exception):',x.strip())]
        code=(ROOT/'codes'/f'{i}.py').read_bytes()
        if sha(code)!=result['code_sha256']:raise ValueError('code drift')
        text=SECRET.sub('[REDACTED]',code.decode())
        rows.append(dict(index=i,task=result['task'],seed=result['original_search_seed'],
            status=result['status'],errors=errors,output_sha256=sha(raw),
            code_mentions_input='input/' in text or '/input' in text,
            code_mentions_workspace='/workspace' in text,
            code_mentions_parent_file=any(x in text for x in ('joblib.load','pickle.load','load_model','torch.load')),
            credential_shape_hits=len(SECRET.findall(raw.decode()))))
    out=dict(role='posthoc_error_signatures_no_new_execution',summary_sha256=sha((ROOT/'completion-summary.json').read_bytes()),rows=rows,
        inspector_sha256=sha(Path(__file__).read_bytes()))
    with (ROOT/'completion-error-signatures.json').open('x') as f:json.dump(out,f,indent=2)
    print(json.dumps(out))
if __name__=='__main__':run()
