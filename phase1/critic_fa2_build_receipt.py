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
    require(p.is_file() and not p.is_symlink() and p.stat().st_size<=2*1024**2,'missing_or_unsafe_build_receipt')
    value=json.loads(p.read_bytes(),object_pairs_hook=unique_object)
    require(type(value) is dict,'build_receipt_object_required')
    return value


def bind_completed_build(root,*,expected_commit,expected_job,expected_script_sha):
    """Consumer preparation must separately verify Slurm and numerical results."""
    root=Path(root)
    require(root.is_absolute() and root.resolve()==root and not any(p.is_symlink() for p in (root,*root.parents)),
            'unsafe_build_root')
    require(re.fullmatch('[0-9a-f]{40}',expected_commit or '') is not None
            and re.fullmatch('[0-9a-f]{64}',expected_script_sha or '') is not None
            and re.fullmatch('[0-9]+',expected_job or '') is not None,'expected_build_identity_required')
    intent=read(root,'BUILD_INTENT.json');built=read(root,'BUILT.json')
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
