"""Only model/path/config identity from the already redacted structural receipt."""
import hashlib,json,re
from collections import Counter
from pathlib import Path
from discover_comparison_20260919 import SECRET

root=Path('/research/d7/spc/yzyang4/comparison-quarantine-20260919-_tda9fh6')
raw=(root/'structure.redacted.json').read_bytes()
if hashlib.sha256(raw).hexdigest()!='2d87541d73a597b0d487285949b1c8f306e756ae97dc9fde7c175f83783d7d94':raise ValueError('identity')
found=Counter()
for archive in json.loads(raw)['archives']:
    for config in archive['configs']:
        fields=config['fields']
        if fields.get('solver.operators.draft.llm.client.model_id')!='qwen3.8-27b':continue
        selected={k:v for k,v in fields.items() if re.search(r'critic|reward',k,re.I)}
        found[json.dumps(selected,sort_keys=True)]+=1
print(json.dumps([dict(config=json.loads(k),runs=v) for k,v in found.items()],indent=2))
source=json.loads((root/'source-semantics.redacted.json').read_bytes())
entry=next(x for x in source if x['path']=='src/dojo/solvers/fore_ts/fore_ts.py')
if entry['commit']!='be9335348b569086ef9b0af36a15b13e61fec45c':raise ValueError('source commit')
print(json.dumps(dict(path=entry['path'],commit=entry['commit'],sha256=entry['sha256'])))
print('\n'.join(f'{i+1}: {line}' for i,line in enumerate(entry['text'].splitlines()) if i<225))
