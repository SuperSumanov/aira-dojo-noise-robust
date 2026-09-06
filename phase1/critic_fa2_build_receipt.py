"""Bind completed offline build artifacts; not a GPU or training authority."""
import json
import math
from pathlib import Path
import re
from phase1.critic_fa2_preflight import sha, verify_overlay


class BuildReceiptError(ValueError):
    pass


def require(ok,reason):
    if not ok:raise BuildReceiptError(reason)


def unique_object(pairs):
    result={}
    for k,v in pairs:
        require(k not in result,'duplicate_receipt_field');result[k]=v
    return result


def read(root,name):
    p=root/name
    require(p.is_file() and not any(x.is_symlink() for x in (p,*p.parents))
            and p.stat().st_nlink==1 and p.stat().st_size<=2*1024**2,'missing_or_unsafe_build_receipt')
    value=json.loads(p.read_bytes(),object_pairs_hook=unique_object)
    require(type(value) is dict,'build_receipt_object_required')
    return value


def regular_member(root,name):
    require(type(name) is str,'unsafe_evidence_member')
    p=Path(name)
    require(not p.is_absolute() and '..' not in p.parts
            and '\\' not in name and p.as_posix()==name,'unsafe_evidence_member')
    target=root/p
    require(target.is_file() and not any(x.is_symlink() for x in (target,*target.parents))
            and target.stat().st_nlink==1,'unsafe_evidence_file')
    return target


def bind_completed_build(root,*,expected_commit,expected_job,expected_script_sha):
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
    require(intent.get('torch')=='2.11.0+cu128' and intent.get('cuda')=='12.8' and intent.get('arch')=='120'
            and intent.get('cuda_context_created') is False and intent.get('automatic_retries')==0,'build_runtime_drift')
    require(built.get('original_fingerprints_unchanged') is True and built.get('gpu_used') is False,'build_scope_drift')
    stages={}
    for name,limit in ((f'compiler-job-{expected_job}',45),('build-dependency',60),('compile',2100),('overlay-install',90),('import',60)):
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
    return {'classification':'FA2_COMPLETED_ARTIFACT_BINDING_NOT_SLURM_OR_GPU_ACCEPTANCE',
            'build_root':str(root),'build_job':expected_job,'build_commit':expected_commit,
            'build_script_sha256':expected_script_sha,'build_receipt_sha256':digest,
            'wheel_sha256':built['wheel_sha256'],'stages':stages,'gpu_kernel_verified':False,
            'source_pre_receipt_sha256':sha(root/'SOURCE_PRE_VERIFIED.json'),
            'source_post_receipt_sha256':sha(root/'SOURCE_POST_VERIFIED.json')}


def bind_resumed_build(root,*,expected_commit,expected_job,expected_script_sha,expected_prior_sha):
    """Explicit continuation identity; Slurm and GPU math remain external gates."""
    root=Path(root)
    require(root.is_absolute() and root.resolve()==root and not any(p.is_symlink() for p in (root,*root.parents)),
            'unsafe_build_root')
    require(re.fullmatch('[0-9a-f]{40}',expected_commit or '') is not None
            and re.fullmatch('[0-9a-f]{64}',expected_script_sha or '') is not None
            and re.fullmatch('[0-9a-f]{64}',expected_prior_sha or '') is not None
            and re.fullmatch('[0-9]+',expected_job or '') is not None,'expected_build_identity_required')
    intent=read(root,'BUILD_INTENT.json');built=read(root,'BUILT.json');prior=read(root,'PRIOR_VERIFIED.json')
    require(built.get('classification')=='ISOLATED_FA2_RESUMED_BUILD_NOT_GPU_ACCEPTANCE','resume_classification')
    require(intent.get('job_id')==built.get('job_id')==expected_job
            and intent.get('source_commit')==built.get('source_commit')==expected_commit
            and intent.get('source_script_sha256')==expected_script_sha,'build_identity_drift')
    require(sha(root/'PRIOR_VERIFIED.json')==expected_prior_sha==intent.get('prior_receipt_sha256')==built.get('prior_receipt_sha256'),
            'resume_prior_binding')
    require(intent.get('torch')=='2.11.0+cu128' and intent.get('cuda')=='12.8' and intent.get('arch')=='120'
            and intent.get('cuda_context_created') is False and intent.get('automatic_retries')==0
            and intent.get('explicit_prior_job')=='12641' and intent.get('new_compile_seconds')==4800,'resume_runtime_drift')
    require(prior.get('prior_job')=='12641' and prior.get('prior_state')=='FAILED'
            and prior.get('prior_elapsed_seconds')==2126 and prior.get('prior_gpu_seconds_total')==9423
            and prior.get('original_log_version')==7 and prior.get('new_compile_seconds')==4800
            and prior.get('new_gpu_seconds_upper_bound')==5760 and prior.get('combined_gpu_seconds_upper_bound')==19023,
            'resume_prior_scope')
    require(built.get('original_fingerprints_unchanged') is True and built.get('gpu_used') is False
            and built.get('prior_completed_objects_unchanged') is True
            and built.get('reused_objects')==len(prior.get('objects',{}))==32,'resume_scope_drift')
    stages={}
    for name,limit in (('compile',4800),('overlay-install',90),('import',60)):
        status=read(root,name+'-status.json');elapsed=status.get('elapsed_seconds')
        require(type(status.get('returncode')) is int and status['returncode']==0,'build_stage_failed')
        require(type(elapsed) in (float,int) and math.isfinite(elapsed) and elapsed>=0,'invalid_build_timing')
        require(not (root/(name+'-timeout.json')).exists(),'build_stage_timed_out')
        require(status.get('log_sha256')==sha(root/(name+'.log')),'build_log_drift')
        stages[name]={'status_sha256':sha(root/(name+'-status.json')),'elapsed_seconds':elapsed,'configured_timeout_seconds':limit}
    post=read(root,'SOURCE_POST_VERIFIED.json')
    require(type(post.get('original_files_verified')) is int and post['original_files_verified']>0
            and re.fullmatch('[0-9a-f]{64}',post.get('inventory_sha256','')) is not None,'source_verification_missing')
    release=read(root,'submission-v7/RELEASED.json');independent=read(root,'submission-v7/INDEPENDENT_PRE_RELEASE.json')
    require(release=={'job_id':expected_job,'commit':expected_commit}
            and independent.get('job_id')==expected_job and independent.get('commit')==expected_commit
            and independent.get('prior_receipt_sha256')==expected_prior_sha and independent.get('objects_checked')==32
            and independent.get('source_files_independently_checked')==post['original_files_verified'],
            'independent_resume_binding')
    old=root.parent/'flash-attn-build-20260907-r3'
    require(not (old/'BUILT.json').exists(),'prior_already_completed')
    require(type(prior.get('preserved_receipts')) is dict and len(prior['preserved_receipts'])==13
            and type(prior.get('copied_evidence')) is dict and len(prior['copied_evidence'])==15,
            'prior_evidence_inventory')
    for n,h in prior['preserved_receipts'].items():
        p=regular_member(old,n)
        require(sha(p)==h,'preserved_failure_drift')
    for n,h in prior['copied_evidence'].items():
        p=regular_member(root/'previous',n)
        require(sha(p)==h,'prior_copy_drift')
    compiler=old/'source/flash_attn-2.8.3/build/temp.linux-x86_64-cpython-311'
    require(sha(regular_member(compiler,'build.ninja'))==prior['ninja_graph_sha256'],'resumed_command_graph_drift')
    for n,h in prior['objects'].items():
        p=regular_member(compiler,n);require(p.suffix=='.o','prior_object_path')
        require(p.stat().st_size==h['bytes'] and sha(p)==h['sha256'],'resumed_object_drift')
    name=built.get('wheel','')
    require(type(name) is str and re.fullmatch(r'flash_attn-2\.8\.3[^/\\]*cp311[^/\\]*linux_x86_64\.whl',name) is not None,'invalid_built_wheel_name')
    require(sha(root/'wheels'/name)==built.get('wheel_sha256'),'built_wheel_drift')
    digest=sha(root/'BUILT.json');verify_overlay(root/'overlay',root/'BUILT.json',digest)
    return {'classification':'FA2_RESUMED_ARTIFACT_BINDING_NOT_SLURM_OR_GPU_ACCEPTANCE',
            'build_root':str(root),'build_job':expected_job,'build_commit':expected_commit,
            'build_script_sha256':expected_script_sha,'build_receipt_sha256':digest,
            'prior_receipt_sha256':expected_prior_sha,'wheel_sha256':built['wheel_sha256'],'stages':stages,
            'source_post_receipt_sha256':sha(root/'SOURCE_POST_VERIFIED.json'),'gpu_kernel_verified':False}
