"""Rehash fixed inputs/base and scan own saved weights for nonfinite values."""
import hashlib
import json
import os
from pathlib import Path
os.environ.update(CUDA_VISIBLE_DEVICES='',HF_HUB_OFFLINE='1',OMP_NUM_THREADS='1')
import torch
from safetensors import safe_open
torch.set_num_threads(1)

ROOT=Path('/research/d7/spc/yzyang4/critic-component-g0/runs/job-12499')
def sha(path):
    before=path.stat()
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    after=path.stat()
    assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns),'hash_drift'
    return h.hexdigest()

p=json.loads((ROOT/'preflight.json').read_text())
assert sha(ROOT/'preflight.json')=='0f5c83cb3dcd8ec73e5d6aefc0c42fa34619d73bcc0e6f1464861e1a4b6347ad'
inputs={}
for name in ('train','dev','cards'):
    entry=p['inputs'][name]
    path=Path(entry['path'])
    got=sha(path)
    assert got==entry['sha256']
    inputs[name]={'sha256':got,'bytes':path.stat().st_size}
manifest=Path(p['model']['manifest'])
assert sha(manifest)=='ceb388235719297e3647478ad2d96486a41d1f84e4c3fd8301c4772d6840e148'
snapshot=Path(p['model']['snapshot'])
base_files=0
for line in manifest.read_text().splitlines():
    if not line.strip(): continue
    digest,relative=line.split(maxsplit=1)
    path=snapshot/relative.lstrip('*')
    assert path.is_relative_to(snapshot)
    assert sha(path)==digest
    base_files+=1
assert base_files==10
v=json.loads((ROOT/'verification.json').read_text())
weights=Path(v['result']['checkpoint'])/'model.safetensors'
assert weights.is_relative_to(ROOT)
before=sha(weights)
assert before=='c66dea53f96795438f82a0950027fee996054bacb431216a50d3e184ef74daad'
count=0
parameters=0
with safe_open(weights,framework='pt',device='cpu') as f:
    for key in f.keys():
        tensor=f.get_tensor(key)
        # Bounded scan avoids a full embedding-sized temporary bool allocation.
        flat=tensor.reshape(-1)
        for part in flat.split(1024*1024):
            assert bool(torch.isfinite(part).all()),'nonfinite_saved_tensor'
        count+=1
        parameters+=tensor.numel()
        del tensor,flat
assert count==312 and parameters==1720577025
assert sha(weights)==before
assert not torch.cuda.is_initialized()
out={'status':'G0_INPUT_BASE_REHASH_AND_SAVED_TENSOR_FINITE_PASS','job_id':12499,
     'inputs':inputs,'base_model_files':base_files,'base_manifest_sha256':sha(manifest),
     'checkpoint_sha256':before,'tensor_count':count,'parameter_count':parameters,
     'all_saved_tensors_finite':True,'trace_sha256':sha(ROOT/'file_access.strace'),
     'gpu_used':False,'data_payloads_parsed':False,'protected_outcomes_read':False,
     'model_effect_claim':False,'audit_script_sha256':sha(Path(__file__))}
with Path('/tmp/g0-12499-final-integrity-20260905.json').open('x') as f:
    json.dump(out,f,sort_keys=True,indent=2)
print(json.dumps(out,sort_keys=True,indent=2))
