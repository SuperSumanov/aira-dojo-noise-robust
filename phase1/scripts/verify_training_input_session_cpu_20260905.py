"""Independent checks of this engineering run's own hash-bound checkpoints."""
import argparse
import hashlib
import json
import os
from pathlib import Path

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);args=parser.parse_args()
    root=args.root
    assert root.is_absolute() and root.parent==Path('/tmp') and root.name.startswith('train-input-session-')
    assert not any(p.is_symlink() for p in (root,*root.parents)) and root.stat().st_uid==os.getuid()
    assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
    import torch
    from safetensors.torch import load_file
    from phase1.scripts.verify_zero3_engineering_20260905 import same
    torch.set_num_threads(1);assert not torch.cuda.is_initialized()
    names={'model.safetensors','optimizer.bin','random_states_0.pkl','random_states_1.pkl','observed_0.json','observed_1.json'}
    checkpoints=[];comparisons=0;trajectories=0
    for repeat in ('a','b'):
        for arm in ('G_to_L','Ghash_to_L'):
            paths={name:root/repeat/(arm+'-'+name) for name in ('full','prefix2','resume2','prefix3','resume3')}
            results={n:json.loads((p/'trajectory.json').read_text()) for n,p in paths.items()}
            for n,p in paths.items():
                trajectories+=1
                for cp in p.glob('checkpoint-*'):
                    assert {x.name for x in cp.iterdir()}==names|{'manifest.json'}
                    m=json.loads((cp/'manifest.json').read_text());assert set(m['files'])==names
                    for name,record in m['files'].items():
                        f=cp/name;assert f.is_file() and not f.is_symlink() and f.stat().st_nlink==1
                        assert record=={'bytes':f.stat().st_size,'sha256':sha(f)}
                    checkpoints.append({'path':str(cp.relative_to(root)),'manifest_sha256':sha(cp/'manifest.json')})
            full=results['full']
            for cut in (2,3):
                pre,res=results[f'prefix{cut}'],results[f'resume{cut}']
                for rank in (0,1):
                    assert pre['ranks'][rank]['records']+res['ranks'][rank]['records']==full['ranks'][rank]['records']
                    assert res['ranks'][rank]['state']==full['ranks'][rank]['state']
                for other,step in ((f'prefix{cut}',cut),(f'resume{cut}',4)):
                    a,b=paths['full']/f'checkpoint-{step}',paths[other]/f'checkpoint-{step}'
                    same(load_file(str(a/'model.safetensors')),load_file(str(b/'model.safetensors')))
                    same(torch.load(a/'optimizer.bin',weights_only=True,map_location='cpu'),torch.load(b/'optimizer.bin',weights_only=True,map_location='cpu'))
                    for rank in (0,1):
                        same(torch.load(a/f'random_states_{rank}.pkl',weights_only=False,map_location='cpu'),
                             torch.load(b/f'random_states_{rank}.pkl',weights_only=False,map_location='cpu'))
                    comparisons+=1
    for a in (root/'a').rglob('*'):
        if a.name in ('summary.json','runs.csv','trajectory.json'):
            b=root/'b'/a.relative_to(root/'a');assert a.read_bytes()==b.read_bytes()
    assert not torch.cuda.is_initialized()
    result={'classification':'INDEPENDENT_ACTUAL_CPU_BRIDGE_CHECKPOINT_CHECK_NOT_EFFECT',
        'verifier_sha256':sha(Path(__file__)),'checkpoint_bundles':len(checkpoints),'actual_state_comparisons':comparisons,
        'trajectories':trajectories,'AB_summary_csv_trajectory_bytes_equal':True,
        'checkpoints':checkpoints,'CUDA_initialized':False,'trace_review_required':True}
    with (root/'independent_verification.json').open('x') as f:json.dump(result,f,sort_keys=True,indent=2)
    print(json.dumps(result,sort_keys=True))

if __name__=='__main__':main()
