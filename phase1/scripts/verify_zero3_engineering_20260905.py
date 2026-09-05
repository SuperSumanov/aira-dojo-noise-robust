"""Independent terminal acceptance of caller-owned synthetic GPU artifacts.

No training backend imported, no CUDA and no real-corpus reader. Check every
manifest member before unpickling our own hash-bound checkpoints. This is not
a safe general-purpose untrusted-checkpoint loader.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

BASE=Path('/research/d7/spc/yzyang4/critic-zero3-engineering')
CASES={'full':(0,4),'prefix2':(0,2),'resume2':(2,4),'prefix3':(0,3),'resume3':(3,4)}
ROLES={'model_shards','master_shards','adamw','scaler','python_rng','numpy_rng','torch_rng'}

def require(ok,why):
    if not ok:raise ValueError(why)

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def regular(p):
    require(p.is_file() and p.stat().st_uid==os.getuid() and p.stat().st_nlink==1
        and not any(x.is_symlink() for x in (p,*p.parents)), 'unsafe_or_unowned_file')

def unique_object(pairs):
    result={}
    for key,value in pairs:
        require(key not in result,'duplicate_json_key');result[key]=value
    return result

def read(p):
    regular(p);require(0<p.stat().st_size<=1_000_000,'receipt_size')
    return json.loads(p.read_text(),object_pairs_hook=unique_object)

def members():
    return {'zero_to_fp32.py'}|{x for r in range(2) for x in (
        f'random_states_{r}.pkl',f'observed_{r}.json',
        f'pytorch_model/zero_pp_rank_{r}_mp_rank_00_model_states.pt',
        f'pytorch_model/bf16_zero_pp_rank_{r}_mp_rank_00_optim_states.pt')}

def verify_manifests(root,binding):
    receipts=[]
    for case,(start,end) in CASES.items():
        expected={f'checkpoint-{i}' for i in range(start+1,end+1) if i in (2,3,4)}
        require({p.name for p in (root/case).iterdir()}==expected|{'trajectory.json'},'trajectory_inventory')
        for name in sorted(expected):
            folder=root/case/name;m=read(folder/'manifest.json')
            files={p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file()}
            require(files==members()|{'manifest.json'} and set(m['files'])==members(),'bundle_inventory')
            require({p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_dir()}=={'pytorch_model'},'bundle_directories')
            require(m['protocol']=='critic-zero3-checkpoint-v1' and m['binding']==binding,'bundle_binding')
            for relative,entry in m['files'].items():
                p=folder/relative;regular(p)
                require(entry=={'bytes':p.stat().st_size,'sha256':digest(p)},'file_hash_mismatch')
            for rank in range(2):
                row=read(folder/f'observed_{rank}.json')
                require(row['rank']==rank and row['binding']==binding and set(row['state'])==ROLES,'observed_binding')
                require(all(isinstance(x,str) and re.fullmatch('[0-9a-f]{64}',x) for x in row['state'].values()),'observed_hash_schema')
                require(type(m['cumulative_valid_tokens']) is int and m['cumulative_valid_tokens']>0
                    and row['cumulative_valid_tokens']==m['cumulative_valid_tokens'],'token_progress')
                require(row['completed_steps']==m['completed_steps']==int(name.split('-')[1]),'checkpoint_progress')
            receipts.append({'path':str(folder.relative_to(root)),'manifest_sha256':digest(folder/'manifest.json'),
                             'files':len(m['files'])})
    return receipts

def same(a,b):
    import numpy as np
    import torch
    if isinstance(a,torch.Tensor):
        require(isinstance(b,torch.Tensor) and a.shape==b.shape and a.dtype==b.dtype,'tensor_schema')
        if a.is_floating_point():require(bool(torch.isfinite(a).all()) and bool(torch.isfinite(b).all()),'nonfinite_payload')
        require(torch.equal(a.reshape(-1).contiguous().view(torch.uint8),b.reshape(-1).contiguous().view(torch.uint8)),'tensor_bits')
    elif isinstance(a,np.ndarray):
        require(isinstance(b,np.ndarray) and a.dtype==b.dtype and a.shape==b.shape and a.tobytes()==b.tobytes(),'numpy_bits')
    elif isinstance(a,dict):
        require(isinstance(b,dict) and set(a)==set(b),'mapping_schema')
        for k in a:same(a[k],b[k])
    elif isinstance(a,(list,tuple)):
        require(type(a)==type(b) and len(a)==len(b),'sequence_schema')
        for x,y in zip(a,b):same(x,y)
    elif isinstance(a,set):
        require(type(b) is set and all(type(x) in (str,int) for x in a|b) and a==b,'metadata_set')
    elif type(a) in (int,str,bool,float,type(None)):
        require(type(a)==type(b) and (a.hex()==b.hex() if type(a) is float else a==b),'scalar_state')
    else:
        # DS static LossScaler is a Python class; compare all actual attributes.
        require(type(a)==type(b) and type(a).__module__=='deepspeed.runtime.fp16.loss_scaler','unknown_pickle_state')
        same(vars(a),vars(b))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--job',required=True);parser.add_argument('--submission',required=True)
    args=parser.parse_args();require(re.fullmatch('[0-9]+',args.job),'job_id')
    socket_portability=args.submission=='submission-20260906-3090-socket'
    private_portability=args.submission=='submission-20260906-3090-private' or socket_portability
    portability=args.submission=='submission-20260906-3090' or private_portability
    require(portability or re.fullmatch('submission-20260905-r[0-9]+',args.submission),'submission_id')
    require(os.environ.get('CUDA_VISIBLE_DEVICES')=='','CPU_only')
    root=BASE/('job-'+args.job);control=BASE/args.submission;trajectories=root/'trajectories'
    require((root/'exit_status.txt').read_text().strip()=='0','worker_not_successful')
    ready=read(control/'READY.json');released=read(control/'RELEASED.json')
    require(released['job_id']==args.job and released['commit']==ready['commit'],'released_identity')
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    raw=subprocess.check_output(['sacct','-X','-n','-P','-j',args.job,'--format=JobIDRaw,State,ElapsedRaw,AllocTRES,ExitCode'],env=env).decode().strip()
    jid,state,elapsed,tres,exitcode=raw.split('|')[:5]
    require(jid==args.job and state=='COMPLETED' and exitcode=='0:0' and 'gres/gpu=2' in tres.split(','),'scheduler_terminal')
    require(2*int(elapsed)<=ready['gpu_seconds_upper_bound'],'actual_budget')
    retry=None
    if (control/'RETRY_READY.json').exists():
        retry=read(control/'RETRY_READY.json')
        require(retry['commit']==ready['commit'] and retry['ready_sha256']==digest(control/'READY.json'),
                'retry_binding')
        budget=retry['budget']
        prior=subprocess.check_output(['sacct','-X','-n','-P','-j',budget['previous_job_id'],
            '--format=JobIDRaw,State,ElapsedRaw,AllocTRES,ExitCode'],env=env).decode().strip().split('|')
        require(prior[:3]==['12510','FAILED','149'] and prior[4]=='1:0' and 'gres/gpu=2' in prior[3].split(','),
                'prior_accounting_drift')
        require(2*int(prior[2])==budget['previous_allocated_gpu_seconds']==298
                and 2*int(elapsed)<=budget['retry_gpu_seconds_upper_bound']==3840
                and 298+2*int(elapsed)<=budget['original_cap_gpu_seconds']==4320,'cumulative_actual_budget')
    summary=read(trajectories/'summary.json')
    if portability:
        expected_cap=2880 if private_portability else 3120
        require(ready['gpu_seconds_upper_bound']==expected_cap and 2*int(elapsed)<=expected_cap,'portability_budget')
        require(summary['expected_gpu']=='RTX 3090' and len(summary['gpu_names'])==2
                and all('RTX 3090' in n for n in summary['gpu_names']),'portability_devices')
        require(read(root/'build_tools.json')['hostname'].split('.')[0]=='gpu28','portability_host')
        if private_portability:
            from phase1.scripts.check_zero3_private_tools_20260906 import ROOT,RECOVERY,INDEPENDENT,MANIFEST
            require(digest(ROOT/'RECOVERY_COMPLETE.json')==RECOVERY and digest(ROOT/'INDEPENDENT_VERIFIED.json')==INDEPENDENT
                    and digest(ROOT/'installed_manifest.json')==MANIFEST,'private_toolchain_binding')
            build=read(root/'build_tools.json')
            require(build['toolkit_manifest_sha256']==MANIFEST and build['toolkit_recovery_sha256']==RECOVERY
                and build['toolkit_independent_sha256']==INDEPENDENT and build['cuda_home']==str(ROOT/'prefix'), 'allocated_private_toolchain')
            prior_jobs=[('12570',('FAILED','1','1:0',2)),('12571',('COMPLETED','5','0:0',1))]
            if socket_portability:
                prior_jobs.append(('12572',('FAILED','73','1:0',2)))
                require(build['nccl_ib_disable']=='1' and build['nccl_net']=='Socket'
                    and build['nccl_debug']=='INFO' and build['python_faulthandler']=='1','socket_profile_binding')
                require(b'Using network Socket' in (root/'driver.log').read_bytes(),'socket_transport_unverified')
            for previous, expected in prior_jobs:
                row=subprocess.check_output(['sacct','-X','-n','-P','-j',previous,
                    '--format=JobIDRaw,State,ElapsedRaw,AllocTRES,ExitCode'],env=env).decode().strip().split('|')
                state0,seconds0,code0,gpus0=expected
                require(row[:3]==[previous,state0,seconds0] and row[4]==code0 and f'gres/gpu={gpus0}' in row[3].split(','),'prior_private_budget')
            require((153 if socket_portability else 7)+2*int(elapsed)<=3120,'aggregate_private_budget')
    require(summary['code_commit']==ready['commit'] and summary['slurm_job_id']==args.job
            and summary['approval_receipt_sha256']==ready['approval_sha256'],'driver_binding')
    require(summary['trajectories']==5 and summary['resume_comparisons']==4 and summary['parameters']==4433,'driver_matrix')
    data={case:read(trajectories/case/'trajectory.json') for case in CASES}
    binding=data['full']['binding']
    require(binding['training_contract_sha256']==ready['approval_sha256'] and binding['world']==2,'session_binding')
    require(sum(e['local_valid_tokens'] for r in data['full']['ranks'] for e in r['records'])
        ==data['full']['planned_tokens'],'full_consumed_tokens')
    for name,(start,end) in CASES.items():
        d=data[name];require(d['binding']==binding and d['seed']==6 and d['arm']=='G_to_L','trajectory_binding')
        require([r['rank'] for r in d['ranks']]==[0,1],'ranks')
        for r in d['ranks']:
            if retry is not None or portability:
                padding=r['initial_padding']
                require(padding['partition_source_sha256']=='8b3c65d20fada0fc85c3685615b0da65247f4e8739313ca1de01b1a3102f2500'
                        and padding['new_partitions']>0 and padding['padding_elements_initialized']==r['rank']
                        and padding['nonfinite_padding_before_initialization']==r['rank'],'initial_padding_receipt')
            require(r['start']==start and r['end']==end and set(r['state'])==ROLES,'trajectory_steps')
            require([x['step'] for x in r['records']]==list(range(start+1,end+1)),'consumption_steps')
    for cut in (2,3):
        for rank in range(2):
            full=data['full']['ranks'][rank];prefix=data[f'prefix{cut}']['ranks'][rank];resumed=data[f'resume{cut}']['ranks'][rank]
            require(full['state']==resumed['state'] and full['counters']==resumed['counters'],'observed_final_state')
            require(prefix['records']+resumed['records']==full['records'],'exact_consumption')
    manifests=verify_manifests(trajectories,binding)
    # All actual file hashes verified above; only self-generated synthetic files.
    import torch
    torch.set_num_threads(1);require(not torch.cuda.is_initialized(),'no_cuda_context')
    comparisons=[]
    for rank in range(2):
        filenames=[f'pytorch_model/zero_pp_rank_{rank}_mp_rank_00_model_states.pt',
                   f'pytorch_model/bf16_zero_pp_rank_{rank}_mp_rank_00_optim_states.pt',f'random_states_{rank}.pkl']
        for relative in filenames:
            reference=torch.load(trajectories/'full/checkpoint-4'/relative,map_location='cpu',weights_only=False)
            for case in ('resume2','resume3'):
                actual=torch.load(trajectories/case/'checkpoint-4'/relative,map_location='cpu',weights_only=False)
                # Check the actual payloads, not the driver's hashes alone.
                same(reference,actual)
                comparisons.append({'rank':rank,'case':case,'file':relative,'all_payload_bits_equal':True})
    require(not torch.cuda.is_initialized(),'cuda_context_created')
    result={'classification':'INDEPENDENT_TINY_ZERO3_RESUME_ACCEPTANCE_NOT_EFFECT',
        'job_id':args.job,'code_commit':ready['commit'],'verifier_sha256':digest(Path(__file__)),
        'elapsed_seconds':int(elapsed),'allocated_gpu_seconds':2*int(elapsed),
        'actual_checkpoint_payload_comparisons':comparisons,'manifests':manifests,
        'trace_acceptance':'SEPARATE_REVIEW_REQUIRED','gpu_initialized':False}
    with (root/'independent_acceptance.json').open('x') as f:json.dump(result,f,indent=2,sort_keys=True)
    print(json.dumps({'status':'PAYLOAD_COMPARISONS_PASS_TRACE_REVIEW_PENDING','comparisons':len(comparisons),
                      'checkpoint_bundles':len(manifests),'allocated_gpu_seconds':2*int(elapsed)}))

if __name__=='__main__':main()
