import json
import os
from pathlib import Path
import pytest
from phase1.scripts import verify_zero3_engineering_20260905 as v


def fixture(tmp_path,monkeypatch):
    if not hasattr(os,'getuid'):monkeypatch.setattr(os,'getuid',lambda:0,raising=False)
    binding={'synthetic':True};root=tmp_path/'trajectories';root.mkdir()
    for case,(start,end) in v.CASES.items():
        (root/case).mkdir();(root/case/'trajectory.json').write_text('{}')
        for step in range(start+1,end+1):
            if step not in (2,3,4):continue
            d=root/case/f'checkpoint-{step}';(d/'pytorch_model').mkdir(parents=True)
            for name in v.members():(d/name).write_bytes(b'synthetic-only')
            for r in range(2):
                (d/f'observed_{r}.json').write_text(json.dumps({'rank':r,'binding':binding,
                    'completed_steps':step,'cumulative_valid_tokens':step*8,'state':{k:'a'*64 for k in v.ROLES}}))
            m={'protocol':'critic-zero3-checkpoint-v1','binding':binding,'completed_steps':step,
               'cumulative_valid_tokens':step*8,
               'files':{p:{'bytes':(d/p).stat().st_size,'sha256':v.digest(d/p)} for p in v.members()}}
            (d/'manifest.json').write_text(json.dumps(m))
    return root,binding


def test_complete_hash_inventory(tmp_path,monkeypatch):
    root,binding=fixture(tmp_path,monkeypatch)
    result=v.verify_manifests(root,binding)
    assert len(result)==9 and sum(x['files'] for x in result)==81


@pytest.mark.parametrize('failure',['hash','missing','extra','directory','binding','progress','alias','symlink','duplicate_json'])
def test_fail_closed_bundle(tmp_path,monkeypatch,failure):
    root,binding=fixture(tmp_path,monkeypatch);d=root/'full/checkpoint-4'
    if failure=='hash':(d/'zero_to_fp32.py').write_bytes(b'changed')
    elif failure=='missing':(d/'random_states_0.pkl').unlink()
    elif failure=='extra':(d/'unexpected.pt').write_bytes(b'extra')
    elif failure=='directory':(d/'empty').mkdir()
    elif failure=='binding':binding={'different':True}
    elif failure=='progress':
        p=d/'manifest.json';m=json.loads(p.read_text());m['completed_steps']=3;p.write_text(json.dumps(m))
    elif failure=='alias':
        try:os.link(d/'random_states_0.pkl',tmp_path/'alias')
        except OSError:pytest.skip('hardlinks unavailable')
    elif failure=='symlink':
        p=d/'random_states_0.pkl';p.unlink()
        try:p.symlink_to(d/'random_states_1.pkl')
        except OSError:pytest.skip('symlinks unavailable')
    elif failure=='duplicate_json':(d/'manifest.json').write_text('{"protocol":"a","protocol":"b"}')
    with pytest.raises(ValueError):v.verify_manifests(root,binding)


@pytest.mark.parametrize('failure',['value','dtype','shape','signed_zero','nan','optimizer_missing','rng'])
def test_actual_tensor_payloads_not_only_reported_digests(failure):
    torch=pytest.importorskip('torch');np=pytest.importorskip('numpy')
    a={'model':torch.tensor([0.,2.],dtype=torch.bfloat16),'optimizer':{'state':torch.tensor([1.,2.])},
       'rng':np.array([1,2],dtype=np.uint32)}
    import copy
    b=copy.deepcopy(a);v.same(a,b)
    if failure=='value':b['model'][1]=3
    elif failure=='dtype':b['model']=b['model'].float()
    elif failure=='shape':b['model']=b['model'].reshape(1,2)
    elif failure=='signed_zero':b['model'][0]=-0.
    elif failure=='nan':a['model'][0]=b['model'][0]=float('nan')
    elif failure=='optimizer_missing':del b['optimizer']['state']
    elif failure=='rng':b['rng'][0]=5
    with pytest.raises(ValueError):v.same(a,b)
