"""Explicit Ampere build/math profile; Blackwell acceptance remains unchanged."""
import math
from pathlib import Path
import re
from phase1.critic_fa2_build_receipt import require,read,BuildReceiptError
from phase1.critic_fa2_preflight import sha,verify_overlay,cpu_binding,math_reference,numerical_check

def bind_completed_ampere(root,*,expected_commit,expected_job,expected_script_sha):
    """Consumer preparation must separately verify Slurm and numerical results."""
    root=Path(root)
    require(root.is_absolute() and root.resolve()==root and not any(p.is_symlink() for p in (root,*root.parents)),
            'unsafe_build_root')
    require(re.fullmatch('[0-9a-f]{40}',expected_commit or '') is not None
            and re.fullmatch('[0-9a-f]{64}',expected_script_sha or '') is not None
            and re.fullmatch('[0-9]+',expected_job or '') is not None,'expected_build_identity_required')
    intent=read(root,'BUILD_INTENT.json');built=read(root,'BUILT.json')
    require(built.get('classification')=='ISOLATED_FA2_CPU_BUILD_NOT_GPU_ACCEPTANCE','fresh_build_classification')
    require(intent.get('job_id')==built.get('job_id')==expected_job
            and intent.get('source_commit')==expected_commit
            and intent.get('source_script_sha256')==expected_script_sha,'build_identity_drift')
    require(intent.get('torch')=='2.11.0+cu128' and intent.get('cuda')=='12.8' and intent.get('arch')=='80'
            and intent.get('cuda_context_created') is False and intent.get('automatic_retries')==0,'build_runtime_drift')
    require(built.get('original_fingerprints_unchanged') is True and built.get('gpu_used') is False,'build_scope_drift')
    stages={}
    for name,limit in ((f'compiler-job-{expected_job}',45),('build-dependency',60),('compile',4800),('overlay-install',90),('import',60)):
        status=read(root,name+'-status.json')
        require(type(status.get('returncode')) is int and status['returncode']==0,'build_stage_failed')
        elapsed=status.get('elapsed_seconds')
        require(type(elapsed) in (float,int) and math.isfinite(elapsed) and elapsed>=0,'invalid_build_timing')
        require(not (root/(name+'-timeout.json')).exists(),'build_stage_timed_out')
        require(status.get('log_sha256')==sha(root/(name+'.log')),'build_log_drift')
        # The stage controller's completed receipt is authoritative for timeout;
        # process reaping and filesystem latency can extend the measured wall.
        stages[name]={'status_sha256':sha(root/(name+'-status.json')),'elapsed_seconds':elapsed,'configured_timeout_seconds':limit}
    for name in ('SOURCE_PRE_VERIFIED.json','SOURCE_POST_VERIFIED.json'):
        row=read(root,name)
        require(type(row.get('original_files_verified')) is int and row['original_files_verified']>0
                and re.fullmatch('[0-9a-f]{64}',row.get('inventory_sha256','')) is not None,'source_verification_missing')
    name=built.get('wheel','')
    require(type(name) is str and re.fullmatch(r'flash_attn-2\.8\.3[^/\\]*cp311[^/\\]*linux_x86_64\.whl',name) is not None,'invalid_built_wheel_name')
    require(sha(root/'wheels'/name)==built.get('wheel_sha256'),'built_wheel_drift')
    digest=sha(root/'BUILT.json')
    verify_overlay(root/'overlay',root/'BUILT.json',digest)
    return {'classification':'FA2_AMPERE_ARTIFACT_BINDING_NOT_SLURM_OR_GPU_ACCEPTANCE',
            'build_root':str(root),'build_job':expected_job,'build_commit':expected_commit,
            'build_script_sha256':expected_script_sha,'build_receipt_sha256':digest,
            'wheel_sha256':built['wheel_sha256'],'stages':stages,'gpu_kernel_verified':False,
            'source_pre_receipt_sha256':sha(root/'SOURCE_PRE_VERIFIED.json'),
            'source_post_receipt_sha256':sha(root/'SOURCE_POST_VERIFIED.json')}


def check_device(index):
    import torch
    from flash_attn import flash_attn_func, flash_attn_varlen_func
    torch.cuda.set_device(index)
    if 'RTX 3090' not in torch.cuda.get_device_name(index).upper() or torch.cuda.get_device_capability(index) != (8,6):
        raise ValueError('expected_rtx3090_sm86')
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


def kernel_receipt_valid(value,*,job,commit,build_sha):
    """Independent shape/threshold check of the GPU-kernel receipt fields."""
    import math
    if not (value.get('classification')=='FA2_AMPERE_TWO_GPU_SYNTHETIC_KERNEL_CHECK_NOT_MODEL_EFFECT'
            and value.get('job_id')==job and value.get('code_commit')==commit
            and value.get('binding',{}).get('build_sha256')==build_sha):return False
    rows=value.get('devices',[])
    if len(rows)!=2 or [r.get('device') for r in rows]!=[0,1]:return False
    for row in rows:
        if not ('RTX 3090' in row.get('name','').upper() and row.get('long_length')==16384
                and row.get('long_forward_backward_finite') is True and row.get('long_full_reference_compared') is False):return False
        cases=row.get('short_reference_cases',[])
        if [r.get('mode') for r in cases]!=['dense','varlen']:return False
        if [r.get('lengths') for r in cases]!=[[129],[31,97]]:return False
        for case in cases:
            errors=case.get('errors',{})
            if set(errors)!={'output','dq','dk','dv'}:return False
            for err in errors.values():
                for key,limit in [('relative_l2',.02),('maximum_absolute',.05)]:
                    v=err.get(key)
                    if type(v) not in (float,int) or not math.isfinite(v) or not 0<=v<=limit:return False
    return True
