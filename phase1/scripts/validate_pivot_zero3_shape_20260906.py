"""New consumer at actual pivot size, synthetic maximum-length tokens only.

One G update/save then a fresh-process restore/L update/save. This is NOT an
uninterrupted-vs-resumed final parity test at pivot size, nor a model-effect fit.
No production release is registered or read. Caller must approve/pin resources,
source, official base-model files and prior tiny independent acceptance.
"""
import argparse,json,os,socket
from pathlib import Path
from phase1.pivot_zero3_shape_fixture import fixture,summary
from phase1.scripts.validate_zero3_session_gpu_20260905 import allocation_gate

BASE=Path('/research/d7/spc/yzyang4')
SNAPSHOT=BASE/'cache/huggingface/hub/models--Qwen--Qwen3-1.7B-Base/snapshots/ea980cb0a6c2ae4b936e82123acc929f1cec04c1'
SOURCE=BASE/'worktrees/critic-g0-final-only-20260903-b'
MANIFEST='phase1/manifests/qwen3-1.7b-base-ea980cb0a6c2ae4b936e82123acc929f1cec04c1.sha256'
MANIFEST_SHA='ceb388235719297e3647478ad2d96486a41d1f84e4c3fd8301c4772d6840e148'


def worker(rank,port,output,stop,resume):
    allocation_gate(os.environ)
    os.environ.update(RANK=str(rank),LOCAL_RANK=str(rank),WORLD_SIZE='2',MASTER_ADDR='127.0.0.1',MASTER_PORT=str(port))
    import random,numpy as np,torch,torch.distributed as dist
    from phase1.critic_offline_setup import create_zero3_setup
    from phase1.critic_training_run import run_session,atomic_json
    from phase1.g_reuse_development_screen_plan import ScreenFit
    from phase1.global_local_zero3_session import file_sha,current_state,counters
    torch.set_num_threads(1);torch.set_num_interop_threads(1)
    plan,pools,encode,truth=fixture()
    session=create_zero3_setup(source_root=SOURCE,model_snapshot=SNAPSHOT,pad_id=0)(
        plan,pools,encode,lambda key:truth[key],training_contract_sha256=os.environ['ZERO3_GPU_APPROVAL_RECEIPT_SHA'])
    allocation_gate(os.environ)
    assert sum(p.ds_numel if hasattr(p,'ds_numel') else p.numel() for p in session.consumer.model.module.parameters())==1720577025
    if resume is not None:
        # Intentionally wrong fresh RNG streams: actual restore must replace all.
        random.seed(9600+rank);np.random.seed(9600+rank);torch.manual_seed(9600+rank);torch.cuda.manual_seed_all(9600+rank)
    fit=ScreenFit(2,'ENGINEERING_SYNTHETIC_G_TO_L_NOT_DEVELOPMENT',plan)
    result=run_session(session,fit,Path(output),stop_after=stop,checkpoint_steps=[stop],
        resume=resume,resume_manifest_sha256=None if resume is None else file_sha(Path(resume)/'manifest.json'))
    atomic_json(Path(output)/f'rank_{rank}_engineering.json',{'classification':'PIVOT_SIZE_SYNTHETIC_ENGINEERING_ONLY',
        'rank':rank,'state':current_state(session.consumer),'counters':counters(session.consumer.model),
        'parameters':1720577025,'gpu':torch.cuda.get_device_name(rank),'runtime':session.runtime,
        'actual_attention_backend':session.consumer.model.module.backbone.config._attn_implementation,
        'actual_parameter_dtypes':sorted({str(p.dtype) for p in session.consumer.model.module.parameters()}),
        'deterministic_algorithms_enabled':torch.are_deterministic_algorithms_enabled(),
        'matmul_tf32':torch.backends.cuda.matmul.allow_tf32,'cudnn_tf32':torch.backends.cudnn.allow_tf32,
        'source_admission':False,'no_uninterrupted_pivot_comparison':True})
    session.consumer.accelerator.wait_for_everyone();dist.destroy_process_group()


def main():
    allocation_gate(os.environ)
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    root=a.output
    assert root.is_absolute() and not root.exists() and '..' not in root.parts and not any(x.is_symlink() for x in root.parents)
    from phase1.verify_critic_component_g0 import validate_model_snapshot,sha256_file
    manifest=Path(os.environ['ZERO3_CONTROL_ROOT'])/MANIFEST
    assert sha256_file(manifest)==MANIFEST_SHA
    validate_model_snapshot(SNAPSHOT,manifest)
    allocation_gate(os.environ)
    root.mkdir(mode=0o700)
    from phase1.critic_training_run import atomic_json
    atomic_json(root/'plan.json',summary())
    import torch.multiprocessing as mp
    for name,stop,cut in [('prefix1',1,None),('resume2',2,1)]:
        resume=None if cut is None else str(root/'prefix1/checkpoint-1')
        with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
        mp.spawn(worker,args=(port,str(root/name),stop,resume),nprocs=2,join=True)
        result=json.loads((root/name/'run_receipt.json').read_text())
        assert result['stop_step']==stop
        for rank in (0,1):
            ctx=json.loads((root/name/f'rank_{rank}_context.json').read_text())
            if cut is None:assert ctx['restore_receipt'] is None
            else:
                r=ctx['restore_receipt'];assert r['completed_steps']==cut and r['all_state_components_restored'] is True
                assert r['native_cpu_adam_cache']['empty_native_calls']==cut
        print(json.dumps({'completed':name,'status':result['status']}),flush=True)
    validate_model_snapshot(SNAPSHOT,manifest)
    atomic_json(root/'summary.json',{'classification':'PIVOT_SHAPE_SAVE_RESTORE_DRIVER_COMPLETE_PENDING_INDEPENDENT',
        'slurm_job_id':os.environ['SLURM_JOB_ID'],'code_commit':os.environ['ZERO3_CODE_COMMIT'],
        'approval_sha256':os.environ['ZERO3_GPU_APPROVAL_RECEIPT_SHA'],'plan':summary(),
        'checkpoints':2,'parameters':1720577025,'real_corpus_reads':0,'model_effect_measured':False,
        'uninterrupted_final_parity_measured_at_this_size':False})


if __name__=='__main__':main()
