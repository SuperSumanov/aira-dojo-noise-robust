"""Actual CPU critic lifecycle through new projected-input bridge; synthetic only."""
import argparse
import csv
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import socket
import time

from phase1.global_local_training_inputs import prepare_training_inputs
from phase1.global_local_execution_plan import BatchShape,EncoderBinding,digest_records


class ByteTokenizer:
    def __call__(self,text,*,add_special_tokens):
        assert add_special_tokens is False
        return {'input_ids':[1+ord(c)%127 for c in text]}


def projected_fixture():
    cards=[];pools=[];winners={}
    for source,count in (('G',11),('L',13)):
        edges=[]
        for i in range(count):
            names=[]
            for side in range(2):
                name=f'synthetic:bridge:{source}:{i:02d}:{side}'
                cards.append({'endpoint_id':name,'task_name':'synthetic-task',
                    'code':f'# synthetic {source} {i}\nx = {i*2+side}\nprint(x)\n'})
                names.append(name)
            edges.append(tuple(names));winners[tuple(names)]=names[i%2]
        pools.append(edges)
    return cards,*pools,winners


def prepared_fixture(arm,ref=None):
    cards,g,l,winners=projected_fixture()
    binding=EncoderBinding(hashlib.sha256(b'synthetic-byte-tokenizer-mod127-v1').hexdigest(),
        hashlib.sha256(b'hash-bound-CardEncoder-task-head-quarter-no-budget').hexdigest(),8)
    prepared=prepare_training_inputs(cards,g,l,ByteTokenizer(),encoder=binding,
        protocol_sha256=hashlib.sha256(b'synthetic-input-session-engineering-v1').hexdigest())
    plan=prepared.plan(arm,6,BatchShape(2,2,2))
    assert plan.steps==4 and plan.planned_valid_tokens==384
    # Compare actual supplied token arrays to the hash-bound reference encoder.
    if ref is not None:
        code={r['endpoint_id']:r['code'] for r in cards};tasks={r['endpoint_id']:r['task_name'] for r in cards}
        old=ref['CardEncoder'](code=code,tasks=tasks,tokenizer=ByteTokenizer(),max_len=8,
            head_frac=.25,task_cond=True,budget_cond=False)
        for pool in prepared.pools:
            for row in pool:
                for e in (row.a,row.b):
                    assert prepared.encoding_provider(row.context_sha256,e.card_id)==tuple(old.encode(e.card_id))
    required=set(prepared.required_label_keys(plan))
    # Ghash's G winners are deliberately absent from the label projection.
    labels={r.key:winners[(r.a.card_id,r.b.card_id)] for pool in prepared.pools for r in pool if r.key in required}
    truth=prepared.true_sign_provider(labels,plan=plan)
    if arm=='Ghash_to_L':assert required.isdisjoint({r.key for r in prepared.pools[0]})
    return plan,prepared.pools,prepared.encoding_provider,truth


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--source-root',required=True);args=parser.parse_args()
    assert os.environ.get('CUDA_VISIBLE_DEVICES')=='' and len(os.environ.get('CRITIC_SESSION_COMMIT',''))==40
    root=args.output
    assert root.is_absolute() and root.is_relative_to(Path('/tmp')) and not root.exists()
    root.mkdir(mode=0o700)
    import torch.multiprocessing as mp
    from phase1.scripts.validate_critic_session_cpu_20260905 import worker
    from phase1.global_local_critic_session import state_fingerprint
    started=time.monotonic();cases=[];comparisons=0
    first=prepared_fixture('G_to_L')[0];second=prepared_fixture('Ghash_to_L')[0]
    assert first.input_sha256==second.input_sha256
    for arm in ('G_to_L','Ghash_to_L'):
        full=None
        for name,end,cut in [('full',4,None),('prefix2',2,None),('resume2',4,2),('prefix3',3,None),('resume3',4,3)]:
            assert time.monotonic()-started<240,'CPU_subrun_budget'
            out=root/(arm+'-'+name);out.mkdir(mode=0o700)
            resume=None if cut is None else str(root/(arm+f'-prefix{cut}')/f'checkpoint-{cut}')
            with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
            mp.spawn(worker,args=(port,arm,str(out),end,resume,args.source_root,prepared_fixture),nprocs=2,join=True)
            result=json.loads((out/'trajectory.json').read_text())
            if name=='full':
                full=result
                assert sum(e['local_valid_tokens'] for r in full['ranks'] for e in r['records'])==384
            if cut is not None:
                pre=json.loads((root/(arm+f'-prefix{cut}')/'trajectory.json').read_text())
                for rank in (0,1):
                    assert result['ranks'][rank]['state']==full['ranks'][rank]['state']
                    assert pre['ranks'][rank]['records']+result['ranks'][rank]['records']==full['ranks'][rank]['records']
                    comparisons+=1
            cases.append({'arm':arm,'seed':6,'trajectory':name,'world':2,'start':cut or 0,'end':end,
                'state_sha256':state_fingerprint([r['state'] for r in result['ranks']]),'pass':True})
            print(json.dumps({'completed':arm+'-'+name}),flush=True)
    result={'classification':'PROJECTED_INPUT_TO_ACTUAL_CRITIC_CPU_LIFECYCLE_NOT_EFFECT',
        'code_commit':os.environ['CRITIC_SESSION_COMMIT'],'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'projection_to_reference_encoder_equal':True,'actual_model_parameters':4433,'dtype':'float32',
        'optimizer':'AdamW','seed':6,'world':2,'endpoints':48,'global_pairs':11,'local_pairs':13,
        'planned_valid_tokens':384,'trajectories':len(cases),'rank_resume_comparisons':comparisons,
        'bitwise_final_state_equal':True,'exact_consumption':True,'hash_arm_true_global_labels_supplied':0,
        'GPU_or_Zero3_validated':False,'real_data_loaded':False}
    with (root/'summary.json').open('x') as f:json.dump(result,f,sort_keys=True,indent=2)
    with (root/'runs.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(cases[0]));w.writeheader();w.writerows(cases)
    print(json.dumps(result,sort_keys=True),flush=True)


if __name__=='__main__':main()
