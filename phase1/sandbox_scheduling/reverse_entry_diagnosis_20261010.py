"""Read-only allowlisted startup diagnosis for exactly failed job17376."""
import json
from pathlib import Path
from lifecycle_pilot import read,sha
from live_status import log_shape

R=Path('/research/d7/spc/yzyang4/scheduling-neural-reverse-independent-20261010-v1')
PIN='88fd90528961d58e49ff79518d186b79048be5a8f9729f3a85aa80ce9f78b7cd'
if __name__=='__main__':
    if sha(R/'plan.json')!=PIN or str(read(R/'launch.json')['job'])!='17376':
        raise ValueError('exact failed scope only')
    result={}
    for name in ('allocation-17376.out','allocation-17376.err','episode-36/worker.private.log'):
        p=R/name
        raw=p.read_text(errors='replace') if p.exists() else ''
        result[name]=dict(shape=log_shape(p),missing_configure_import=("cannot import name 'configure'" in raw),
            recursion_error=('RecursionError' in raw),cuda_initialization_failure=('CUDA initialization' in raw or 'cuInit failed' in raw))
    print(json.dumps(dict(closed=read(R/'closed.json'),logs=result),sort_keys=True))
