"""Copy only verified executor dependencies into a new prepared diagnostic root."""
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import shutil

OLD=Path('/research/d7/spc/yzyang4/forets-current-pool-20260912-wnm9cxd0')
ROOT=Path('/research/d7/spc/yzyang4/forets-current-pool-20260912-0hz06xtj')
PLAN='6bbe805e1113bbd7d899914178da79ef773ae8ae5f1306ba645066c397c0f02c'
SECRET=re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{16,}|gh[pousr]_[a-z0-9]{16,}|github_pat_[a-z0-9_]{20,}|Bearer\s+[a-z0-9_.-]{20,})')


def main():
    if ROOT.resolve().parent!=OLD.parent or (ROOT/'deployment.json').exists():raise ValueError('not a fresh explicit root')
    if hashlib.sha256((ROOT/'plan.private.json').read_bytes()).hexdigest()!=PLAN:raise ValueError('prepared plan changed')
    frozen=json.loads((OLD/'submit-intent.json').read_bytes())['code_sha256']
    names=['forets_current_pool_native_20260912.py','forets_closed_pool_20260911.py',
        'forets_closed_pool_native_20260911.py','verify_forets_current_pool_20260912.py',
        'forets_opencl_readonly_ab.py','forets_opencl_allowlist_20260911.py',
        'forets_native_cuda_identity_20260911.py','forets_gpu_binding_20260911.py',
        'forets_native_gpu_binding_20260911.py','bin/singularity']
    checked={}
    for name in names:
        source=OLD/name;raw=source.read_bytes()
        if source.is_symlink() or hashlib.sha256(raw).hexdigest()!=frozen[name] or SECRET.search(raw):
            raise ValueError('old dependency drift/security')
        if (ROOT/name).exists():raise ValueError('dependency already deployed')
        checked[name]=hashlib.sha256(raw).hexdigest()
    script='forets_current_pool_20260912.sbatch';raw=(OLD/script).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=frozen[script]:raise ValueError('old launcher changed')
    if raw.count(b'forets-first-pools-s11')!=1:raise ValueError('launcher anchor')
    launcher=raw.replace(b'forets-first-pools-s11',b'forets-context-pools-s14')
    for name in names:
        target=ROOT/name;target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        shutil.copyfile(OLD/name,target);os.chmod(target,0o700 if name=='bin/singularity' else 0o600)
    with (ROOT/script).open('xb') as f:f.write(launcher)
    vendors=ROOT/'opencl-vendors';vendors.mkdir(mode=0o700)
    icd=(OLD/'opencl-vendors/nvidia.icd').read_bytes()
    if icd.strip()!=b'libnvidia-opencl.so.1':raise ValueError('ICD changed')
    with (vendors/'nvidia.icd').open('xb') as f:f.write(icd)
    for path in ROOT.glob('*.py'):ast.parse(path.read_text())
    import sys
    sys.path.insert(0,str(ROOT))
    from forets_current_pool_20260912 import plan
    plan(ROOT)
    receipt=dict(status='PREPARED_NOT_SUBMITTED',root=str(ROOT),plan_sha256=PLAN,
        copied_dependencies=checked,launcher_sha256=hashlib.sha256(launcher).hexdigest(),
        programs=8,api_calls=0,gpu_jobs=0,source_script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    with (ROOT/'deployment.json').open('x') as f:json.dump(receipt,f,indent=2)
    print(json.dumps(receipt))


if __name__=='__main__':main()
