"""Structural status only; never reveal new program grades or stdout."""
import json,sys
from pathlib import Path
root=Path(sys.argv[1]).resolve(strict=True)
if root.parent!=Path('/research/d7/spc/yzyang4') or not root.name.startswith('comparison-pool-20260919-'):
    raise ValueError('scope')
bindings=[]
for p in sorted(root.glob('identity-*.native-binding.json')):
    record=json.loads(p.read_bytes())
    bindings.append(dict(index=int(p.name.split('-')[1].split('.')[0]),
        uuid=record['native_identity']['selected_uuid'],exact=record['namespace']['exact_device_namespace']))
print(json.dumps(dict(root=str(root),result_files=len(list(root.glob('result-*.json'))),
    pools_started=sorted(p.name for p in root.glob('pool-start-*.json')),
    pools_closed=sorted(p.name for p in root.glob('pool-finished-*.json')),finished=(root/'finished.json').exists(),
    gpu_bindings=len(bindings),first_pool_unique_gpu=len({b['uuid'] for b in bindings if b['index']<6}),
    exact_namespace_all=all(b['exact'] for b in bindings))))
