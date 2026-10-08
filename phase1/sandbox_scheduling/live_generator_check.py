"""Credential-first inspection of the already deployed local 27B entry only."""
import hashlib
import json
from pathlib import Path
import re

B=Path('/research/d7/spc/yzyang4')
D=B/'task-feedback-real-20261001-v6'
SECRET=re.compile(rb'(?i)(?<![a-z0-9_-])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,}|Bearer\s+[a-z0-9_.-]{20,})')

def safe(p):
    raw=p.read_bytes()
    if SECRET.search(raw):raise ValueError('credential shape; withheld')
    return raw

def main():
    plan=json.loads(safe(D/'plan.json'))
    entry=safe(D/'service_entry.py');pin=hashlib.sha256(entry).hexdigest()
    if plan['files']['service_entry.py']!=pin:raise ValueError('entry pin drift')
    print(json.dumps({'donor':str(D),'plan_sha256':hashlib.sha256(safe(D/'plan.json')).hexdigest(),
        'entry_sha256':pin,'model_exists':(B/'local-qwen27b-20260914-zcx1k1dy/model').is_dir(),
        'plan_keys':sorted(plan),'model_files':[p.name for p in (B/'local-qwen27b-20260914-zcx1k1dy/model').glob('*.json')]}))
    print(entry.decode())
    config=json.loads(safe(B/'local-qwen27b-20260914-zcx1k1dy/model/config.json'))
    print(json.dumps({k:config[k] for k in ('model_type','architectures','quantization_config','torch_dtype') if k in config}))

if __name__=='__main__':main()
