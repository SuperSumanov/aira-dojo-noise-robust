"""Coarse model startup progress only; never print service arguments or keys."""
import json,re,sys
from pathlib import Path
root=Path(sys.argv[1]).resolve(strict=True)
if root.parent!=Path('/research/d7/spc/yzyang4') or not root.name.startswith('comparison-live-debug-20260919-'):raise ValueError('scope')
path=root/'service.private.log'
with path.open('rb') as handle:
    handle.seek(0,2);size=handle.tell();handle.seek(max(0,size-262144));log=handle.read().decode(errors='replace')
cache=root/'service-cache'
print(json.dumps(dict(log_bytes=size,log_mtime=path.stat().st_mtime,
    cuda_identity_logged='LOCAL_SERVICE_CUDA' in log,
    weight_loading_logged=bool(re.search(r'Loading.*(?:weights|checkpoint)|Loading model',log,re.I)),
    weights_loaded=bool(re.search(r'Loading weights took|Model loading took',log,re.I)),
    compilation_logged=bool(re.search(r'compil|flashinfer|CUDA graph',log,re.I)),
    error_marker=bool(re.search(r'Traceback|ERROR|RuntimeError',log)),
    cached_objects=sum(1 for p in cache.rglob('*.o')),ready=(root/'ready.json').exists(),
    closed=(root/'closed.json').exists())))
