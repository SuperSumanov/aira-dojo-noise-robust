"""Fresh-process AdamW + random-Qwen checkpoint lifecycle, not an effect fit."""
import argparse
import csv
from dataclasses import asdict
from datetime import timedelta
import hashlib
import json
import os
from pathlib import Path
import random
import socket
import time

import numpy as np
import torch
import torch.distributed as dist
import torch.multiprocessing as mp
from torch import nn
from accelerate import Accelerator
from accelerate.utils import InitProcessGroupKwargs
from transformers import Qwen3Config,Qwen3Model

from phase1.global_local_critic_consumer import PlannedCriticConsumer
from phase1.global_local_critic_session import CriticSession,current_state,file_sha,state_fingerprint
from phase1.scripts.validate_global_local_critic_consumer_20260905 import fixture
from phase1.scripts.validate_g_reuse_endpoint_inference_cpu_20260905 import source_definitions,SOURCE_COMMIT


def worker(rank,port,arm,output,end_step,resume,source_root,inputs_factory=None):
    os.environ.update(RANK=str(rank),LOCAL_RANK=str(rank),WORLD_SIZE='2',MASTER_ADDR='127.0.0.1',
                      MASTER_PORT=str(port),GLOO_SOCKET_IFNAME='lo',ACCELERATE_USE_CPU='true',OMP_NUM_THREADS='1')
    assert os.environ['CUDA_VISIBLE_DEVICES']==''
    torch.set_num_threads(1);torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(True)
    torch.manual_seed(6)
    ref=source_definitions(source_root)
    cls=ref['BradleyTerryRewardModel']
    model=cls.__new__(cls);nn.Module.__init__(model)
    model.backbone=Qwen3Model(Qwen3Config(vocab_size=128,hidden_size=16,intermediate_size=32,
        num_hidden_layers=1,num_attention_heads=2,num_key_value_heads=1,head_dim=8,
        max_position_embeddings=64,pad_token_id=0,use_cache=False,attn_implementation='eager',attention_dropout=0.1))
    model.head=nn.Linear(16,1,dtype=torch.float32)
    model.train()
    assert sum(p.numel() for p in model.parameters())==4433
    if inputs_factory is None:
        plan,pools,encoded,truth=fixture(arm)
        encoding_provider=lambda ctx,card:encoded[(ctx,card)]
        truth_provider=lambda key:truth[key]
    else:
        plan,pools,encoding_provider,truth_provider=inputs_factory(arm,ref)
    global_keys={r.key for r in pools[0]}
    def target(key):
        if arm=='Ghash_to_L' and key in global_keys:
            raise RuntimeError('true_global_target_read_forbidden')
        return truth_provider(key)
    accelerator=Accelerator(cpu=True,mixed_precision='no',gradient_accumulation_steps=plan.shape.accumulation,
        kwargs_handlers=[InitProcessGroupKwargs(timeout=timedelta(seconds=60))])
    optimizer=torch.optim.AdamW(model.parameters(),lr=1e-5,weight_decay=0.01)
    model,optimizer=accelerator.prepare(model,optimizer)
    c=PlannedCriticConsumer(plan=plan,pools=pools,accelerator=accelerator,model=model,optimizer=optimizer,
        encoding_provider=encoding_provider,true_sign=target,pad_id=0)
    contract=hashlib.sha256(('synthetic-critic-session:'+os.environ['CRITIC_SESSION_COMMIT']).encode()).hexdigest()
    session=CriticSession(c,training_contract_sha256=contract)
    initial_seed=(600 if resume is None else 9600)+rank
    random.seed(initial_seed);np.random.seed(initial_seed);torch.manual_seed(initial_seed)
    restored=None
    if resume is not None:
        root=Path(resume)
        old=current_state(c)
        restored=session.restore(root,manifest_sha256=file_sha(root/'manifest.json'))
        now=current_state(c)
        assert all(old[k]!=now[k] for k in ('python_rng','numpy_rng','torch_rng'))
    start=c.completed_steps
    records=[]
    for completed in range(start+1,end_step+1):
        random.random();np.random.random();torch.rand(1)
        events=list(session.run_until(completed))
        assert len(events)==1
        event=events[0]
        records.append({'completed_steps':completed,'event_sha256':state_fingerprint(asdict(event)),
                        'local_pair_visits':event.local_pair_visits,'local_valid_tokens':event.local_valid_tokens,
                        'cumulative_global_valid_tokens':event.cumulative_global_valid_tokens})
        if completed in (2,3,4):
            session.save(Path(output)/f'checkpoint-{completed}')
    final=current_state(c)
    assert not torch.cuda.is_initialized()
    gathered=[None,None]
    dist.all_gather_object(gathered,{'rank':rank,'start':start,'end':c.completed_steps,
                                   'state':final,'records':records,'restored':restored is not None})
    if rank==0:
        with (Path(output)/'trajectory.json').open('x') as f:
            json.dump({'arm':arm,'seed':6,'ranks':gathered,'planned_tokens':plan.planned_valid_tokens},f,sort_keys=True,indent=2)
    accelerator.wait_for_everyone();dist.destroy_process_group()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--source-root',required=True);args=parser.parse_args()
    assert os.environ.get('CUDA_VISIBLE_DEVICES')=='' and os.environ.get('CRITIC_SESSION_COMMIT')
    root=args.output
    assert root.is_absolute() and root.is_relative_to(Path('/tmp')) and not root.exists()
    root.mkdir(mode=0o700)
    started=time.monotonic();cases=[];comparisons=0
    for arm in ('G_to_L','Ghash_to_L'):
        full=None
        for tag,end,cut in (('full',4,None),('prefix2',2,None),('resume2',4,2),('prefix3',3,None),('resume3',4,3)):
            assert time.monotonic()-started<1200,'cpu_budget_exceeded'
            out=root/(arm+'-'+tag);out.mkdir(mode=0o700)
            resume=None if cut is None else str(root/(arm+f'-prefix{cut}')/f'checkpoint-{cut}')
            with socket.socket() as sock:
                sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
            mp.spawn(worker,args=(port,arm,str(out),end,resume,args.source_root),nprocs=2,join=True)
            result=json.loads((out/'trajectory.json').read_text())
            if tag=='full':
                full=result
                assert sum(r['local_valid_tokens'] for rank in full['ranks'] for r in rank['records'])==full['planned_tokens']
            if cut is not None:
                for a,b in zip(result['ranks'],full['ranks']):
                    assert a['state']==b['state'],'restored_final_state_not_bitwise_equal'
                    assert a['records']==[r for r in b['records'] if r['completed_steps']>cut],'repeated_or_skipped_consumption'
                    comparisons+=1
            if tag.startswith('prefix'):
                for a,b in zip(result['ranks'],full['ranks']):
                    assert a['records']==[r for r in b['records'] if r['completed_steps']<=end]
            cases.append({'arm':arm,'seed':6,'trajectory':tag,'world':2,'start_step':cut or 0,'end_step':end,
                'optimizer_updates':end-(cut or 0),'final_rank_state_sha256':state_fingerprint([r['state'] for r in result['ranks']]),
                'consumption_sha256':state_fingerprint([r['records'] for r in result['ranks']]),'pass':True})
            print(json.dumps({'completed_trajectories':len(cases),'arm':arm,'trajectory':tag}),flush=True)
    summary={'classification':'RANDOM_QWEN_ADAMW_DDP_SESSION_LIFECYCLE_NOT_EFFECT',
             'code_commit':os.environ['CRITIC_SESSION_COMMIT'],'source_commit':SOURCE_COMMIT,
             'session_sha256':file_sha(Path(__file__).parents[1]/'global_local_critic_session.py'),
             'validation_sha256':file_sha(Path(__file__)),'parameters':4433,'dtype':'float32','optimizer':'AdamW',
             'seed':6,'attention_dropout':0.1,'world':2,'trajectories':len(cases),'final_rank_resume_comparisons':comparisons,
             'final_state_bitwise_equal':True,'resumed_consumption_exact_suffix':True,
             'real_data_opened':False,'gpu_used':False,'deepspeed_or_bf16_gpu_validated':False}
    with (root/'summary.json').open('x') as f: json.dump(summary,f,sort_keys=True,indent=2)
    with (root/'runs.csv').open('x',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(cases[0]));writer.writeheader();writer.writerows(cases)
    print(json.dumps(summary,sort_keys=True),flush=True)


if __name__=='__main__':main()
