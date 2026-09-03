"""Read-only saved-state verification, no producer/adapter imports or fit."""
import argparse
import hashlib
import json
from pathlib import Path
import torch


def equal(a,b):
    if isinstance(a,torch.Tensor):
        return isinstance(b,torch.Tensor) and a.dtype==b.dtype and a.shape==b.shape and torch.equal(a,b)
    if type(a) is not type(b): return False
    if isinstance(a,dict): return a.keys()==b.keys() and all(equal(a[k],b[k]) for k in a)
    if isinstance(a,(list,tuple)): return len(a)==len(b) and all(equal(x,y) for x,y in zip(a,b))
    return a==b


def read(root):
    m=json.loads((root/'manifest.json').read_text())
    assert set(m['rank_files'])=={f'rank-{i}.pt' for i in range(m['world'])}
    for name,h in m['rank_files'].items(): assert hashlib.sha256((root/name).read_bytes()).hexdigest()==h
    return [torch.load(root/f'rank-{i}.pt',map_location='cpu',weights_only=True) for i in range(m['world'])]


def verify(root):
    report=json.loads((root/'summary.json').read_text())
    cases=[]
    for world in (2,4):
        for arm in ('G_to_L','Ghash_to_L'):
            full=read(root/f'w{world}-{arm}-stochastic-full')
            resumed=read(root/f'w{world}-{arm}-fresh-process-resume')
            prefix=read(root/f'w{world}-{arm}-prefix')
            for rank,(a,b,c) in enumerate(zip(full,resumed,prefix)):
                for key in ('binding','model','optimizer','scheduler','rng','events','completed_steps'):
                    assert equal(a[key],b[key]),key
                assert a['binding']['rank']==rank and a['binding']['world']==world
                assert a['completed_steps']==b['completed_steps']==4 and c['completed_steps']==2
                assert len(a['events'])==8 and a['events'][:4]==c['events']
                assert a['new_forward_calls']==8 and b['new_forward_calls']==4
                assert not equal(a['model'],c['model'])
                for key in ('model','optimizer','scheduler'):
                    assert equal(a[key],full[0][key])
            cases.append({'world':world,'arm':arm,'verified_ranks':len(full),'complete_state_bitwise_equal':True})
        a=read(root/f'w{world}-G_to_L-stochastic-full')
        b=read(root/f'w{world}-Ghash_to_L-stochastic-full')
        for rank in range(world):
            for x,y in zip(a[rank]['events'],b[rank]['events']):
                assert {k:v for k,v in x.items() if k!='plan_sha256'}=={k:v for k,v in y.items() if k!='plan_sha256'}
    assert len(report['trials'])==16
    return {'status':'PASS_INDEPENDENT_SAVED_STATE_ONLY','resume_cases':cases,
            'input_identity_across_label_arms':True,'research_model_fits':0,
            'summary_sha256':hashlib.sha256((root/'summary.json').read_bytes()).hexdigest(),
            'verifier_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}


if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--root',required=True,type=Path)
    print(json.dumps(verify(p.parse_args().root.resolve()),sort_keys=True))
