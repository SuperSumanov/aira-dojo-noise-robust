"""CPU-only postflight for our own fixed synthetic RTX3090 job.

Requires caller-owned, Slurm-completed artifacts and exact released source.
Authenticates all checkpoint bytes before torch.load (not a pickle sandbox).
Does not train, change source qualification, or claim full-size restart parity.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from phase1.pivot_ampere_artifact_check import (PARAMETERS,expected_plan,verify_binding,verify_segment,require)

B=Path('/research/d7/spc/yzyang4')
SUB=B/'critic-pivot-ampere/submission-20260907-r2'
SECRET=re.compile(rb'(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16}|Bearer[ \t]+[A-Za-z0-9._-]{20,})')
FORBIDDEN=(b'/prospective_decision_v1/',b'decision_frozen_v11_',b'/target522-',b'/target300-',
    b'/label_vault/',b'/outcome_vault/',b'/prediction_escrow/',b'/external/senior_data/',b'first-960',b'first960')

def regular(p):
    require(p.is_absolute() and not any(x.is_symlink() for x in (p,*p.parents))
        and p.is_file() and p.stat().st_uid==os.getuid() and p.stat().st_nlink==1,'unsafe_or_unowned_postflight_file')

def sha(p):
    regular(p);before=p.stat();h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(1<<20),b''):h.update(block)
    after=p.stat()
    require((before.st_size,before.st_mtime_ns,before.st_ino)==(after.st_size,after.st_mtime_ns,after.st_ino),'changed_during_hash')
    return h.hexdigest()

def unique(rows):
    result={}
    for k,v in rows:require(k not in result,'duplicate_postflight_key');result[k]=v
    return result

def read(p):
    regular(p);require(0<p.stat().st_size<=2**20,'postflight_receipt_size')
    raw=p.read_bytes();require(not SECRET.search(raw),'postflight_credential_shape')
    return json.loads(raw,object_pairs_hook=unique)

def expected_members():
    return {'zero_to_fp32.py'}|{n for r in (0,1) for n in (f'random_states_{r}.pkl',f'observed_{r}.json',
        f'pytorch_model/zero_pp_rank_{r}_mp_rank_00_model_states.pt',f'pytorch_model/bf16_zero_pp_rank_{r}_mp_rank_00_optim_states.pt')}

def manifest(folder,binding,step):
    require(not any(p.is_symlink() for p in (folder,*folder.rglob('*'))),'pivot_checkpoint_symlink')
    require({p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_dir()}=={'pytorch_model'},'pivot_checkpoint_dirs')
    require({p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file()}==expected_members()|{'manifest.json'},'pivot_checkpoint_inventory')
    m=read(folder/'manifest.json')
    require(set(m)=={'protocol','binding','completed_steps','cumulative_valid_tokens','files'}
        and m['protocol']=='critic-zero3-checkpoint-v1' and m['binding']==binding
        and m['completed_steps']==step and m['cumulative_valid_tokens']==step*4194304
        and set(m['files'])==expected_members(),'pivot_manifest_binding')
    for n,record in m['files'].items():
        p=folder/n;require(record=={'bytes':p.stat().st_size,'sha256':sha(p)},'pivot_checkpoint_byte_drift')
    return m

def record(p,v):
    with p.open('x') as f:json.dump(v,f,sort_keys=True,indent=2,allow_nan=False);f.flush();os.fsync(f.fileno())

def main():
    p=argparse.ArgumentParser();p.add_argument('--job',required=True);p.add_argument('--training-commit',required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    require(re.fullmatch('[0-9]+',a.job) and a.job!='12535' and re.fullmatch('[0-9a-f]{40}',a.training_commit),'postflight_identity')
    require(os.environ.get('CUDA_VISIBLE_DEVICES')=='','postflight_cpu_only')
    require(a.output==B/('critic-pivot-ampere-postflight-'+a.job+'-20260907') and not a.output.exists(),'postflight_fresh_output')
    os.umask(0o077);root=B/'critic-pivot-ampere'/('job-'+a.job);trajectory=root/'trajectories'
    ready=read(SUB/'READY.json');control=Path(ready['control'])
    require(ready['commit']==a.training_commit and read(SUB/'RELEASED.json')=={'job_id':a.job,'commit':a.training_commit},'postflight_release')
    require(read(SUB/'INDEPENDENT_PRE_RELEASE.json')['source_commit']==a.training_commit,'postflight_independent_release')
    require(control==B/'worktrees'/('critic-pivot-ampere-'+a.training_commit[:12]),'postflight_control_root')
    for n,h in ready['hashes'].items():require(sha(control/n)==h,'postflight_source_drift')
    for n,h in ready['evidence_hashes'].items():require(sha(SUB/n)==h,'postflight_preparation_drift')
    # No model/checkpoint import until Slurm, source and all text/trace gates pass.
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    raw=subprocess.check_output(['sacct','-X','-n','-P','-j',a.job,'--format=JobIDRaw,State,ElapsedRaw,AllocTRES,ExitCode'],env=env,timeout=30)
    require(len(raw.decode().strip().splitlines())==1,'postflight_unique_slurm')
    j,state,elapsed,tres,rc=raw.decode().strip().split('|')[:5]
    require(j==a.job and state=='COMPLETED' and rc=='0:0' and elapsed.isdecimal()
        and 0<2*int(elapsed)<=ready['gpu_seconds_upper_bound']==7920 and 'gres/gpu=2' in tres.split(','),'postflight_slurm_terminal')
    require((root/'exit_status.txt').read_text().strip()=='0','postflight_worker_failure')
    inspected={};files=list(root.rglob('*'));require(all(not x.is_symlink() for x in files),'postflight_symlink')
    require((root/'file_trace.log').stat().st_size>0,'postflight_trace_missing')
    for f in files:
        if not f.is_file():continue
        regular(f)
        if f.suffix in ('.pt','.pkl'):continue
        h=hashlib.sha256()
        with f.open('rb') as stream:
            for line in stream:
                require(not SECRET.search(line),'postflight_text_credential_shape')
                if f.name=='file_trace.log':require(not any(x in line for x in FORBIDDEN),'postflight_protected_path_marker')
                h.update(line)
        inspected[f.relative_to(root).as_posix()]={'bytes':f.stat().st_size,'sha256':h.hexdigest()}
    from phase1.scripts.prepare_pivot_ampere_shape_20260907 import build_binding
    from phase1.critic_ampere_preflight import kernel_receipt_valid
    build=build_binding();require(build['build_receipt_sha256']==ready['fa2_build_receipt_sha256'],'postflight_build_binding')
    require(kernel_receipt_valid(read(root/'fa2-kernel.json'),job=a.job,commit=a.training_commit,
        build_sha=ready['fa2_build_receipt_sha256']),'postflight_kernel_math')
    allocated=read(root/'allocation.json');f=allocated['fields']
    require(allocated['source_commit']==a.training_commit and allocated['approval_sha256']==ready['approval_sha256']
        and f['NodeList']=='gpu28' and f['TresPerNode']=='gpu:rtx3090:2'
        and allocated['prior_gpu_seconds']+2*int(elapsed)<=36000,'postflight_allocation')
    require({x.name for x in trajectory.iterdir()}=={'prefix1','resume2','plan.json','summary.json'},'postflight_trajectory_inventory')
    plan,description=expected_plan();summary=read(trajectory/'summary.json')
    require(read(trajectory/'plan.json')==description and summary=={
        'classification':'AMPERE_PIVOT_SHAPE_SAVE_RESTORE_DRIVER_COMPLETE_PENDING_INDEPENDENT',
        'slurm_job_id':a.job,'code_commit':a.training_commit,'approval_sha256':ready['approval_sha256'],
        'plan':description,'checkpoints':2,'parameters':PARAMETERS,'real_corpus_reads':0,
        'model_effect_measured':False,'uninterrupted_final_parity_measured_at_this_size':False},'postflight_summary')
    binding=read(trajectory/'prefix1/rank_0_context.json')['session_binding']
    runtime=read(SUB/'runtime-plan.json')['runtime']
    verify_binding(binding,approval_sha=ready['approval_sha256'],source_sha=ready['hashes']['phase1/global_local_zero3_session.py'],runtime=runtime)
    bundles={};segments=[]
    for case,step in (('prefix1',1),('resume2',2)):
        folder=trajectory/case;cp=folder/f'checkpoint-{step}'
        expected={f'checkpoint-{step}','run_receipt.json'}|{f'rank_{rank}_{stem}.{suffix}' for rank in (0,1)
            for stem,suffix in (('context','json'),('updates','jsonl'),('engineering','json'))}
        require({x.name for x in folder.iterdir()}==expected,'postflight_segment_inventory')
        bundles[case]=manifest(cp,binding,step)
        contexts={r:read(folder/f'rank_{r}_context.json') for r in (0,1)}
        updates={r:[json.loads(x,object_pairs_hook=unique) for x in (folder/f'rank_{r}_updates.jsonl').read_text().splitlines()] for r in (0,1)}
        engineering={r:read(folder/f'rank_{r}_engineering.json') for r in (0,1)}
        observed={r:read(cp/f'observed_{r}.json') for r in (0,1)}
        segments.append(verify_segment(case,read(folder/'run_receipt.json'),contexts,updates,engineering,observed,
            binding=binding,manifest_sha=sha(cp/'manifest.json'),prefix_manifest_sha=sha(trajectory/'prefix1/checkpoint-1/manifest.json'),
            native_helper_sha=ready['hashes']['phase1/global_local_cpu_adam_resume.py'],runtime=runtime))
    # Sealed caller-owned artifacts: no future live writer or arbitrary input path.
    for x in files:
        if x.is_file():x.chmod(0o400)
    require(all(not x.stat().st_mode&0o222 for x in files if x.is_file()),'postflight_readonly')
    a.output.mkdir(mode=0o700)
    record(a.output/'AUTHENTICATED.json',{'job_id':a.job,'source_commit':a.training_commit,'segments':segments,
        'text_receipts':inspected,'checkpoint_manifest_sha256':{c:sha(trajectory/c/f'checkpoint-{i}/manifest.json') for c,i in (('prefix1',1),('resume2',2))},
        'file_trace_scope':'protected-path marker check; this trace does not include network syscalls',
        'no_claim_of_general_untrusted_pickle_sandbox':True,'verifier_sha256':sha(Path(__file__))})
    import torch
    from phase1.critic_zero3_payload_observation import verify_payload_observation
    torch.set_num_threads(1);require(not torch.cuda.is_initialized(),'postflight_cuda_initialized')
    checks=[]
    for case,step in (('prefix1',1),('resume2',2)):
        cp=trajectory/case/f'checkpoint-{step}'
        for rank in (0,1):
            paths=[cp/f'pytorch_model/zero_pp_rank_{rank}_mp_rank_00_model_states.pt',
                cp/f'pytorch_model/bf16_zero_pp_rank_{rank}_mp_rank_00_optim_states.pt',cp/f'random_states_{rank}.pkl']
            payload=[torch.load(x,map_location='cpu',weights_only=False,mmap=(x.suffix=='.pt')) for x in paths]
            receipt=verify_payload_observation(*payload,read(cp/f'observed_{rank}.json'),binding=binding,
                step=step,tokens=step*4194304,parameters=PARAMETERS)
            checks.append({'case':case,'rank':rank,'receipt':receipt});del payload
        require(manifest(cp,binding,step)==bundles[case],'postflight_bundle_changed')
    require(not torch.cuda.is_initialized(),'postflight_cuda_initialized')
    for n,h in ready['hashes'].items():require(sha(control/n)==h,'postflight_source_changed')
    result={'classification':'REAL_AMPERE_PIVOT_1P7B_16K_SAVE_RESTORE_ENGINEERING_NOT_EFFECT_OR_FULL_PARITY',
        'job_id':a.job,'training_commit':a.training_commit,'verifier_sha256':sha(Path(__file__)),
        'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'parameters':PARAMETERS,
        'elapsed_seconds':int(elapsed),'allocated_gpu_seconds':2*int(elapsed),'segments':segments,
        'actual_payload_checks':checks,'gpu_initialized_by_checker':False,'source_admission':False,
        'model_effect_measured':False,'full_size_uninterrupted_final_parity_measured':False,
        'authenticated_receipt_sha256':sha(a.output/'AUTHENTICATED.json')}
    record(a.output/'VERIFIED.json',result);(a.output/'VERIFIED.json').chmod(0o400)
    print(json.dumps({'status':result['classification'],'receipt_sha256':sha(a.output/'VERIFIED.json'),
        'actual_payload_checks':len(checks),'allocated_gpu_seconds':2*int(elapsed)},sort_keys=True))

if __name__=='__main__':main()
