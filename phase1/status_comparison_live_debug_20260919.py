"""Structural live generation status; no generated program or answer content."""
import json,sys
from pathlib import Path
root=Path(sys.argv[1]).resolve(strict=True)
if root.parent!=Path('/research/d7/spc/yzyang4') or not root.name.startswith('comparison-live-debug-20260919-'):raise ValueError('scope')
out=dict(root=str(root),claimed=(root/'execution.claim.json').exists(),service_identity=(root/'service-native.json').exists(),
         ready=(root/'ready.json').exists(),generation_records=len(list(root.glob('generation-[12].json'))),closed=(root/'closed.json').exists())
if out['closed']:out['closed_status']=json.loads((root/'closed.json').read_bytes())['status']
print(json.dumps(out))
