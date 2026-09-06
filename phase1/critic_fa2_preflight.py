"""Pinned FA2 overlay checks and synthetic math checks; no dataset/model loader."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1024**2), b''):
            h.update(b)
    return h.hexdigest()


def verify_overlay(overlay, manifest, expected_sha):
    overlay, manifest = Path(overlay), Path(manifest)
    if not re.fullmatch('[0-9a-f]{64}', expected_sha or ''):
        raise ValueError('expected_build_digest_required')
    for path in (overlay, manifest):
        if not path.is_absolute() or path.resolve() != path or any(p.is_symlink() for p in (path,*path.parents)):
            raise ValueError('unsafe_overlay_path')
    if sha(manifest) != expected_sha:
        raise ValueError('build_receipt_drift')
    value = json.loads(manifest.read_bytes())
    # This is byte/ABI binding, not authority to accept a build. The separate
    # build-receipt checker distinguishes fresh and explicitly resumed chains.
    if value.get('classification') not in ('ISOLATED_FA2_CPU_BUILD_NOT_GPU_ACCEPTANCE',
                                         'ISOLATED_FA2_RESUMED_BUILD_NOT_GPU_ACCEPTANCE'):
        raise ValueError('wrong_build_classification')
    files = value.get('overlay_files')
    if not isinstance(files, dict) or not files:
        raise ValueError('empty_build_inventory')
    for name, digest in files.items():
        p = PurePosixPath(name)
        if p.is_absolute() or '..' in p.parts or '\\' in name or p.as_posix() != name:
            raise ValueError('unsafe_build_member')
        path = overlay/name
        if any(x.is_symlink() for x in (path,*path.parents)) or not path.is_file() or sha(path) != digest:
            raise ValueError('overlay_file_drift')
    actual = {p.relative_to(overlay).as_posix() for p in overlay.rglob('*') if p.is_file()}
    if actual != set(files):
        raise ValueError('overlay_inventory_drift')
    return value


def cpu_binding(overlay, manifest, expected_sha):
    value = verify_overlay(overlay, manifest, expected_sha)
    import torch
    import flash_attn
    import flash_attn_2_cuda
    if torch.cuda.is_initialized():
        raise ValueError('cpu_binding_already_has_cuda_context')
    if torch.__version__ != '2.11.0+cu128' or torch.version.cuda != '12.8' or not torch._C._GLIBCXX_USE_CXX11_ABI:
        raise ValueError('fa2_build_torch_abi_mismatch')
    if flash_attn.__version__ != '2.8.3':
        raise ValueError('unexpected_flash_attn_version')
    for module in (flash_attn, flash_attn_2_cuda):
        path = Path(module.__file__).resolve()
        if not path.is_relative_to(Path(overlay)) or sha(path) != value['overlay_files'].get(path.relative_to(overlay).as_posix()):
            raise ValueError('imported_unbound_fa2')
    return {'build_sha256':expected_sha,'flash_attn':'2.8.3','torch':torch.__version__,
            'cuda_context_created':False,'extension_sha256':sha(flash_attn_2_cuda.__file__)}


def math_reference(q, k, v):
    """FP32 causal grouped-query attention, tensors shaped [B,S,H,D]."""
    import torch
    group = q.shape[2]//k.shape[2]
    assert q.shape[2] % k.shape[2] == 0 and k.shape == v.shape and q.shape[1] == k.shape[1]
    qh = q.float().transpose(1,2)
    kh = k.float().repeat_interleave(group,dim=2).transpose(1,2)
    vh = v.float().repeat_interleave(group,dim=2).transpose(1,2)
    scores = qh @ kh.transpose(-1,-2) / q.shape[-1]**0.5
    mask = torch.ones(q.shape[1],q.shape[1],dtype=torch.bool,device=q.device).triu(1)
    return (scores.masked_fill(mask,float('-inf')).softmax(-1) @ vh).transpose(1,2)


def numerical_check(actual, expected):
    import torch
    if actual.shape != expected.shape or not torch.isfinite(actual).all() or not torch.isfinite(expected).all():
        raise ValueError('fa2_shape_or_nonfinite')
    delta = actual.float()-expected.float()
    relative = float(delta.norm()/expected.float().norm().clamp_min(1e-12))
    maximum = float(delta.abs().max())
    # Frozen before GPU results; both criteria required, no after-the-fact tuning.
    if relative > 0.02 or maximum > 0.05:
        raise ValueError('fa2_forward_or_gradient_reference_mismatch')
    return {'relative_l2':relative,'maximum_absolute':maximum}


def check_device(index):
    import torch
    from flash_attn import flash_attn_func, flash_attn_varlen_func
    torch.cuda.set_device(index)
    if 'PRO 6000' not in torch.cuda.get_device_name(index).upper() or torch.cuda.get_device_capability(index) != (12,0):
        raise ValueError('expected_pro6000_sm120')
    torch.manual_seed(6)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    results=[]
    for mode in ('dense','varlen'):
        lengths=[129] if mode=='dense' else [31,97]
        total=sum(lengths)
        xyz=[torch.randn(1,total,h,128,device=index,dtype=torch.bfloat16).requires_grad_() for h in (16,8,8)]
        refs=[t.detach().float().requires_grad_() for t in xyz]
        if mode=='dense':
            out=flash_attn_func(*xyz,dropout_p=0.0,causal=True)
            ref=math_reference(*refs)
        else:
            cu=torch.tensor([0,31,128],device=index,dtype=torch.int32)
            out=flash_attn_varlen_func(*(t[0] for t in xyz),cu,cu,97,97,dropout_p=0.0,causal=True).unsqueeze(0)
            ref=torch.cat([math_reference(*(r[:,a:b] for r in refs)) for a,b in ((0,31),(31,128))],dim=1)
        upstream=torch.randn_like(out)
        (out.float()*upstream.float()).sum().backward()
        (ref*upstream.float()).sum().backward()
        errors={'output':numerical_check(out,ref)}
        errors.update({name:numerical_check(t.grad,r.grad) for name,t,r in zip(('dq','dk','dv'),xyz,refs)})
        results.append({'mode':mode,'lengths':lengths,'errors':errors})
    # Real long-sequence kernel dispatch, not an O(S^2) reference allocation.
    xyz=[torch.randn(1,16384,h,128,device=index,dtype=torch.bfloat16).requires_grad_() for h in (16,8,8)]
    out=flash_attn_func(*xyz,dropout_p=0.0,causal=True)
    out.float().square().mean().backward()
    if not torch.isfinite(out).all() or not all(t.grad is not None and torch.isfinite(t.grad).all() for t in xyz):
        raise ValueError('fa2_16k_forward_backward_nonfinite')
    torch.cuda.synchronize(index)
    return {'device':index,'name':torch.cuda.get_device_name(index),'short_reference_cases':results,
            'long_length':16384,'long_forward_backward_finite':True,'long_full_reference_compared':False}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--overlay',required=True);p.add_argument('--manifest',required=True)
    p.add_argument('--expected-sha256',required=True);p.add_argument('--output',required=True)
    p.add_argument('--gpu',action='store_true');a=p.parse_args()
    binding=cpu_binding(a.overlay,a.manifest,a.expected_sha256)
    result={'classification':'FA2_CPU_BINDING_NOT_GPU_ACCEPTANCE','binding':binding}
    if a.gpu:
        from phase1.scripts.validate_zero3_session_gpu_20260905 import allocation_gate
        allocation_gate(os.environ)
        import torch
        if torch.cuda.device_count()!=2:raise ValueError('two_gpus_required')
        result.update(classification='FA2_TWO_GPU_SYNTHETIC_KERNEL_CHECK_NOT_MODEL_EFFECT',devices=[check_device(i) for i in (0,1)],
                      job_id=os.environ['SLURM_JOB_ID'],code_commit=os.environ['ZERO3_CODE_COMMIT'])
    verify_overlay(a.overlay,a.manifest,a.expected_sha256)
    with Path(a.output).open('x') as f:json.dump(result,f,sort_keys=True,indent=2)
    print(result['classification'])


if __name__=='__main__':main()
