from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

import phase1.global_local_critic_session as session
from phase1.global_local_execution_plan import PlanError


def bundle(root):
    binding={'world':2,'total_steps':4,'training_contract_sha256':'a'*64}
    root.mkdir()
    for name in session.expected_files(2):
        if name.startswith('observed'):
            rank=int(name.split('_')[1].split('.')[0])
            value={'rank':rank,'binding':binding,'completed_steps':2,'cumulative_valid_tokens':88,
                   'state':{k:'b'*64 for k in ('model','optimizer','python_rng','numpy_rng','torch_rng')}}
            (root/name).write_text(json.dumps(value))
        else:
            (root/name).write_bytes(b'unit fixture, never deserialized')
    manifest={'protocol':'critic-session-ddp-checkpoint-v1','binding':binding,'completed_steps':2,
              'cumulative_valid_tokens':88,'files':{n:{'bytes':(root/n).stat().st_size,'sha256':session.file_sha(root/n)}
                                                for n in session.expected_files(2)}}
    (root/'manifest.json').write_text(json.dumps(manifest))
    return binding,session.file_sha(root/'manifest.json')


def test_complete_bundle(tmp_path):
    binding,h=bundle(tmp_path/'complete')
    assert session.verify_bundle(tmp_path/'complete',binding,h)['completed_steps']==2


@pytest.mark.parametrize('name',['model.safetensors','optimizer.bin','random_states_0.pkl','random_states_1.pkl',
                                 'observed_0.json','observed_1.json'])
def test_each_component_corruption_rejected(tmp_path,name):
    root=tmp_path/'complete';binding,h=bundle(root)
    (root/name).write_bytes(b'corrupted')
    with pytest.raises(PlanError,match='member_hash'):
        session.verify_bundle(root,binding,h)


@pytest.mark.parametrize('mutation',['extra','missing','binding','manifest','step','tokens','rank'])
def test_metadata_and_inventory_rejected(tmp_path,mutation):
    root=tmp_path/'complete';binding,h=bundle(root)
    if mutation=='extra': (root/'unknown').write_bytes(b'x')
    if mutation=='missing': (root/'optimizer.bin').unlink()
    if mutation=='binding': binding={**binding,'training_contract_sha256':'c'*64}
    if mutation=='manifest': h='c'*64
    if mutation in ('step','tokens','rank'):
        manifest=json.loads((root/'manifest.json').read_text())
        if mutation=='step': manifest['completed_steps']=True
        if mutation=='tokens': manifest['cumulative_valid_tokens']=True
        if mutation=='rank':
            row=json.loads((root/'observed_1.json').read_text());row['rank']=0
            (root/'observed_1.json').write_text(json.dumps(row))
            manifest['files']['observed_1.json']={'bytes':(root/'observed_1.json').stat().st_size,
                                                 'sha256':session.file_sha(root/'observed_1.json')}
        (root/'manifest.json').write_text(json.dumps(manifest));h=session.file_sha(root/'manifest.json')
    with pytest.raises(PlanError): session.verify_bundle(root,binding,h)


@pytest.mark.parametrize('dtype',[torch.float32,torch.bfloat16,torch.int64])
def test_fingerprint_dtype_shape_and_values(dtype):
    a=torch.arange(6).to(dtype)
    assert session.state_fingerprint(a)==session.state_fingerprint(a.clone())
    assert session.state_fingerprint(a)!=session.state_fingerprint(a.reshape(2,3))
    assert session.state_fingerprint(a)!=session.state_fingerprint(a+1)
    assert session.state_fingerprint({'b':a,'a':1})==session.state_fingerprint({'a':1,'b':a})


def test_no_old_guard_weakened():
    from phase1.global_local_accelerate_checkpoint_gate import validate_binding
    with pytest.raises(ValueError,match='scope_or_binding'):
        validate_binding({'scope':'critic-session-ddp-v1'})


def test_deepspeed_not_silently_admitted():
    c=SimpleNamespace(accelerator=SimpleNamespace(distributed_type='DistributedType.DEEPSPEED'))
    with pytest.raises(PlanError,match='backend_not_yet_admitted'):
        session.CriticSession(c,training_contract_sha256='a'*64)


@pytest.mark.parametrize('failure',['corrupt','token_cursor','already_started'])
def test_restore_failure_before_deserialization_poisoned(tmp_path,failure):
    root=tmp_path/'complete';binding,h=bundle(root)
    calls=[]
    c=SimpleNamespace(poisoned=False,completed_steps=1 if failure=='already_started' else 0,
                      accelerator=SimpleNamespace(load_state=lambda *a,**k:calls.append(1)))
    obj=session.CriticSession.__new__(session.CriticSession)
    obj.consumer=c;obj.binding=binding;obj._boundary=lambda:None;obj._tokens=lambda step:99
    if failure=='corrupt': (root/'optimizer.bin').write_bytes(b'broken')
    with pytest.raises(PlanError): obj.restore(root,manifest_sha256=h)
    assert c.poisoned and not calls
