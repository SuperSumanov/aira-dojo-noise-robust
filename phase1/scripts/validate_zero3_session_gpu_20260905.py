"""Proposed bounded GPU engineering check; NO job submission or real data.

Run only inside the separately approved two-GPU Slurm allocation. The receipt
digest binds that approval; a fabricated digest does not grant authorization.
All outputs stay in a new caller-owned directory. No model checkpoints loaded.
"""
import argparse
import csv
from dataclasses import asdict
import json
import os
from pathlib import Path
import re
import socket


def allocation_gate(environ):
    if not re.fullmatch('[0-9]+',environ.get('SLURM_JOB_ID','')):
        raise ValueError('slurm_allocation_required')
    if not re.fullmatch('[0-9a-f]{64}',environ.get('ZERO3_GPU_APPROVAL_RECEIPT_SHA','')):
        raise ValueError('separately_approved_matrix_receipt_required')
    if not re.fullmatch('[0-9a-f]{40}',environ.get('ZERO3_CODE_COMMIT','')):
        raise ValueError('exact_code_commit_required')
    devices=environ.get('CUDA_VISIBLE_DEVICES','').split(',')
    if (len(devices)!=2 or len(set(devices))!=2
            or any(not re.fullmatch(r'(?:[0-9]+|GPU-[0-9a-fA-F-]{36})',d) for d in devices)):
        raise ValueError('exactly_two_visible_devices_required')
    for k,v in {'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','OMP_NUM_THREADS':'1',
                'MAX_JOBS':'2','CUBLAS_WORKSPACE_CONFIG':':4096:8','PYTHONHASHSEED':'6'}.items():
        if environ.get(k)!=v:raise ValueError('fixed_engineering_environment_required:'+k)


def worker(rank,port,output,end,resume,source_root):
    allocation_gate(os.environ)
    os.environ.update(RANK=str(rank),LOCAL_RANK=str(rank),WORLD_SIZE='2',MASTER_ADDR='127.0.0.1',MASTER_PORT=str(port))
    import random
    import time
    from datetime import timedelta
    import numpy as np
    import torch
    import torch.distributed as dist
    from torch import nn
    from accelerate import Accelerator,DeepSpeedPlugin
    from accelerate.utils import InitProcessGroupKwargs
    from transformers import Qwen3Config,Qwen3Model
    from phase1.global_local_critic_consumer import PlannedCriticConsumer
    from phase1.global_local_zero3_session import DeepSpeedCriticSession,current_state,counters,file_sha,state_fingerprint
    from phase1.global_local_zero3_padding import initialized_partition_padding
    from phase1.scripts.validate_global_local_critic_consumer_20260905 import fixture
    from phase1.scripts.validate_g_reuse_endpoint_inference_cpu_20260905 import source_definitions
    allocation_gate(os.environ)  # imports must not erase/change the allocation
    torch.set_num_threads(1);torch.set_num_interop_threads(1);torch.cuda.set_device(rank)
    assert torch.cuda.device_count()==2 and '6000' in torch.cuda.get_device_name(rank)
    torch.use_deterministic_algorithms(True);torch.backends.cuda.matmul.allow_tf32=False
    torch.backends.cudnn.allow_tf32=False;torch.manual_seed(6)
    ref=source_definitions(source_root);cls=ref['BradleyTerryRewardModel']
    model=cls.__new__(cls);nn.Module.__init__(model)
    model.backbone=Qwen3Model(Qwen3Config(vocab_size=128,hidden_size=16,intermediate_size=32,num_hidden_layers=1,
        num_attention_heads=2,num_key_value_heads=1,head_dim=8,max_position_embeddings=64,pad_token_id=0,
        use_cache=False,attn_implementation='eager',attention_dropout=0.1))
    model.head=nn.Linear(16,1,dtype=torch.float32);model.train()
    assert sum(p.numel() for p in model.parameters())==4433
    plan,pools,encoded,truth=fixture('G_to_L')
    config={'train_micro_batch_size_per_gpu':2,'gradient_accumulation_steps':2,'train_batch_size':8,
            'gradient_clipping':1.0,'bf16':{'enabled':True},'fp16':{'enabled':False},
            'zero_force_ds_cpu_optimizer':True,
            'zero_optimization':{'stage':3,'offload_optimizer':{'device':'cpu','pin_memory':True},
                'overlap_comm':False,'contiguous_gradients':True,'reduce_bucket_size':1000000,
                'stage3_param_persistence_threshold':0,'stage3_gather_16bit_weights_on_model_save':False}}
    a=Accelerator(mixed_precision='bf16',gradient_accumulation_steps=2,
                  deepspeed_plugin=DeepSpeedPlugin(hf_ds_config=config),
                  kwargs_handlers=[InitProcessGroupKwargs(timeout=timedelta(seconds=300))])
    opt=torch.optim.AdamW(model.parameters(),lr=1e-5,weight_decay=0.01)
    with initialized_partition_padding() as padding_receipt:
        model,opt=a.prepare(model,opt)
    print(json.dumps({'rank':rank,'initial_padding':padding_receipt}),flush=True)
    c=PlannedCriticConsumer(plan=plan,pools=pools,accelerator=a,model=model,optimizer=opt,
        encoding_provider=lambda ctx,card:encoded[(ctx,card)],true_sign=lambda k:truth[k],pad_id=0)
    session=DeepSpeedCriticSession(c,training_contract_sha256=os.environ['ZERO3_GPU_APPROVAL_RECEIPT_SHA'])
    rng_seed=(600 if resume is None else 9600)+rank
    random.seed(rng_seed);np.random.seed(rng_seed);torch.manual_seed(rng_seed);torch.cuda.manual_seed_all(rng_seed)
    if resume is not None:
        root=Path(resume);old=current_state(c)
        session.restore(root,manifest_sha256=file_sha(root/'manifest.json'))
        now=current_state(c)
        assert all(old[k]!=now[k] for k in ('python_rng','numpy_rng','torch_rng'))
    start=c.completed_steps;records=[];timings=[]
    for completed in range(start+1,end+1):
        random.random();np.random.random();torch.rand(1,device=a.device)
        torch.cuda.synchronize();begin=time.monotonic()
        event=list(session.run_until(completed))[0]
        torch.cuda.synchronize();timings.append({'step':completed,'seconds':time.monotonic()-begin,'warmup':completed==start+1})
        records.append({'step':completed,'receipt_sha256':state_fingerprint(asdict(event)),
                        'local_valid_tokens':event.local_valid_tokens,'local_pair_visits':event.local_pair_visits})
        if completed in (2,3,4):session.save(Path(output)/f'checkpoint-{completed}')
    gathered=[None,None]
    dist.all_gather_object(gathered,{'rank':rank,'start':start,'end':c.completed_steps,'state':current_state(c),
        'counters':counters(model),'records':records,'step_times':timings,'initial_padding':padding_receipt,
        'peak_allocated_bytes':torch.cuda.max_memory_allocated(rank),'peak_reserved_bytes':torch.cuda.max_memory_reserved(rank)})
    if rank==0:
        with (Path(output)/'trajectory.json').open('x') as f:
            json.dump({'ranks':gathered,'seed':6,'arm':'G_to_L','planned_tokens':plan.planned_valid_tokens,
                       'binding':session.binding},f,sort_keys=True,indent=2)
    a.wait_for_everyone();dist.destroy_process_group()


def main():
    allocation_gate(os.environ)  # refuse before importing CUDA-capable packages
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--source-root',required=True);args=parser.parse_args()
    root=args.output
    assert root.is_absolute() and not root.exists() and '..' not in root.parts
    assert not any(p.is_symlink() for p in root.parents)
    root.mkdir(mode=0o700)
    import torch.multiprocessing as mp
    from phase1.global_local_critic_session import state_fingerprint
    cases=[];full=None
    for name,end,cut in [('full',4,None),('prefix2',2,None),('resume2',4,2),('prefix3',3,None),('resume3',4,3)]:
        out=root/name;out.mkdir(mode=0o700)
        resume=None if cut is None else str(root/f'prefix{cut}'/f'checkpoint-{cut}')
        with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        mp.spawn(worker,args=(port,str(out),end,resume,args.source_root),nprocs=2,join=True)
        result=json.loads((out/'trajectory.json').read_text())
        if name=='full':
            full=result
            assert sum(e['local_valid_tokens'] for r in full['ranks'] for e in r['records'])==full['planned_tokens']
        if cut is not None:
            prefix=json.loads((root/f'prefix{cut}'/'trajectory.json').read_text())
            for r in (0,1):
                actual,reference=result['ranks'][r],full['ranks'][r]
                assert actual['state']==reference['state'],'zero3_final_state_not_equal'
                assert actual['counters']==reference['counters'],'zero3_final_counters_not_equal'
                assert prefix['ranks'][r]['records']+actual['records']==reference['records'],'zero3_consumption_mismatch'
        cases.append({'trajectory':name,'seed':6,'arm':'G_to_L','start':cut or 0,'end':end,'world':2,
                      'state_sha256':state_fingerprint([r['state'] for r in result['ranks']]),'pass':True})
        print(json.dumps({'completed':name}),flush=True)
    summary={'classification':'TINY_BF16_ZERO3_CPUADAM_GPU_ENGINEERING_NOT_EFFECT','seed':6,
             'code_commit':os.environ['ZERO3_CODE_COMMIT'],'slurm_job_id':os.environ['SLURM_JOB_ID'],
             'approval_receipt_sha256':os.environ['ZERO3_GPU_APPROVAL_RECEIPT_SHA'],'trajectories':len(cases),
             'corpus_reads':0,'parameters':4433,'world':2,'resume_comparisons':4,'bitwise_state_equal':True}
    with (root/'summary.json').open('x') as f:json.dump(summary,f,sort_keys=True,indent=2)
    with (root/'runs.csv').open('x',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(cases[0]));writer.writeheader();writer.writerows(cases)
    print(json.dumps(summary,sort_keys=True),flush=True)


if __name__=='__main__':main()
