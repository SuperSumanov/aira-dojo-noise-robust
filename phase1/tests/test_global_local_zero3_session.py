from copy import deepcopy
import json
from types import SimpleNamespace as NS

import pytest
import torch

import phase1.global_local_zero3_session as z
from phase1.global_local_execution_plan import PlanError


def bundle(root):
    root.mkdir(); (root/z.TAG).mkdir()
    binding={'world':2,'total_steps':4,'training_contract_sha256':'a'*64}
    progress={'global_steps':2,'micro_steps':2,'global_samples':16,'skipped_steps':0,
              'micro_step_id':0,'step_applied':True}
    for name in z.expected_files():
        if name.startswith('observed_'):
            rank=int(name.split('_')[1].split('.')[0])
            row={'rank':rank,'binding':binding,'completed_steps':2,'cumulative_valid_tokens':88,
                 'state':{k:'b'*64 for k in z.STATE_KEYS},'counters':progress}
            (root/name).write_text(json.dumps(row))
        else: (root/name).write_bytes(b'synthetic unit-only, not deserialized')
    return binding, rewrite_manifest(root,binding)


def rewrite_manifest(root,binding):
    m={'protocol':'critic-zero3-checkpoint-v1','binding':binding,'completed_steps':2,
       'cumulative_valid_tokens':88,'files':{n:{'bytes':(root/n).stat().st_size,'sha256':z.file_sha(root/n)}
                                           for n in z.expected_files()}}
    (root/'manifest.json').write_text(json.dumps(m));return z.file_sha(root/'manifest.json')


def test_valid_complete(tmp_path):
    root=tmp_path/'cp';binding,h=bundle(root)
    assert z.verify_bundle(root,binding,h)['completed_steps']==2


@pytest.mark.parametrize('key',sorted(z.STATE_KEYS))
def test_restore_comparison_requires_every_zero3_role(key):
    expected={k:'a'*64 for k in z.STATE_KEYS}
    z.verify_restored(expected,dict(expected))
    with pytest.raises(PlanError,match='restored_state_mismatch'):
        z.verify_restored(expected,{**expected,key:'b'*64})
    with pytest.raises(PlanError,match='component_set'):
        z.verify_restored(expected,{k:v for k,v in expected.items() if k!=key})


@pytest.mark.parametrize('name', sorted(z.expected_files()))
def test_every_shard_and_rng_hash_checked(tmp_path,name):
    root=tmp_path/'cp';binding,h=bundle(root)
    (root/name).write_bytes(b'corrupt')
    with pytest.raises(PlanError,match='member_hash'):z.verify_bundle(root,binding,h)


@pytest.mark.parametrize('kind',['missing','extra','directory','wrong_binding','wrong_manifest','symlink','hardlink'])
def test_inventory_and_hash_pinning(tmp_path,kind):
    root=tmp_path/'cp';binding,h=bundle(root)
    if kind=='missing': (root/'random_states_1.pkl').unlink()
    if kind=='extra': (root/'latest').write_text('other checkpoint')
    if kind=='directory': (root/'extra').mkdir()
    if kind=='wrong_binding': binding={**binding,'world':4}
    if kind=='wrong_manifest': h='c'*64
    if kind=='symlink':
        (root/'random_states_0.pkl').unlink(); (root/'random_states_0.pkl').symlink_to(root/'random_states_1.pkl')
    if kind=='hardlink': (tmp_path/'extra-link').hardlink_to(root/'random_states_0.pkl')
    with pytest.raises(PlanError):z.verify_bundle(root,binding,h)


@pytest.mark.parametrize('field,value',[('rank',1),('completed_steps',True),('cumulative_valid_tokens',True),
    ('micro_steps',0),('global_steps',1),('global_samples',True),('step_applied',False),('micro_step_id',2)])
def test_rank_cursor_rejected_even_after_rehash(tmp_path,field,value):
    root=tmp_path/'cp';binding,h=bundle(root)
    row=z.read_small(root/'observed_0.json')
    if field in row:row[field]=value
    else:row['counters'][field]=value
    (root/'observed_0.json').write_text(json.dumps(row));h=rewrite_manifest(root,binding)
    with pytest.raises(PlanError):z.verify_bundle(root,binding,h)


def fake_state():
    model=torch.nn.Linear(2,1,bias=False).bfloat16()
    model.weight.ds_tensor=torch.tensor([1.,2.],dtype=torch.bfloat16)
    master=torch.nn.Parameter(torch.tensor([1.,2.]))
    optimizer=torch.optim.AdamW([master],lr=1e-3)
    master.grad=torch.ones(2);optimizer.step();master.grad=None
    optimizer.param_groups[0]['params']=[]
    raw=NS(fp32_partitioned_groups_flat=[master],optimizer=optimizer,overflow=False,
           dynamic_loss_scale=False,loss_scale=1.0)
    engine=NS(module=model,optimizer=raw)
    wrapper=NS(optimizer=raw)
    accelerator=NS(distributed_type='DEEPSPEED',deepspeed_engine_wrapped=NS(engine=engine),
                   _optimizers=[wrapper],device=torch.device('cpu'))
    return NS(model=engine,optimizer=wrapper,accelerator=accelerator)


@pytest.mark.parametrize('component',['bf16','master','moment','rng'])
def test_real_tensor_fingerprints_detect_changes(component):
    c=fake_state(); before=z.current_state(c)
    if component=='bf16':c.model.module.weight.ds_tensor.add_(1)
    if component=='master':c.model.optimizer.fp32_partitioned_groups_flat[0].data.add_(1)
    if component=='moment':
        p=c.model.optimizer.fp32_partitioned_groups_flat[0]
        c.model.optimizer.optimizer.state[p]['exp_avg'].add_(1)
    if component=='rng':torch.rand(1)
    assert before!=z.current_state(c)


@pytest.mark.parametrize('reason',['token_cursor','corrupt','fresh'])
def test_gate_fails_before_deserialization(tmp_path,reason):
    root=tmp_path/'cp';binding,h=bundle(root)
    calls=[];c=NS(poisoned=False,completed_steps=int(reason=='fresh'),model=NS(global_steps=0,micro_steps=0),
                  accelerator=NS(load_state=lambda *a,**kw:calls.append(1)))
    s=z.DeepSpeedCriticSession.__new__(z.DeepSpeedCriticSession)
    s.consumer=c;s.binding=binding;s._boundary=lambda:None;s._tokens=lambda n:99
    if reason=='corrupt':(root/'random_states_0.pkl').write_bytes(b'wrong')
    with pytest.raises(PlanError):s.restore(root,manifest_sha256=h)
    assert c.poisoned and not calls and c.completed_steps==int(reason=='fresh')


def test_ddp_guard_unchanged():
    with pytest.raises(PlanError,match='backend_not_yet_admitted'):
        z.CriticSession(NS(accelerator=NS(distributed_type='DEEPSPEED')),training_contract_sha256='a'*64)


def test_nonfinite_master_rejected():
    c=fake_state();c.model.optimizer.fp32_partitioned_groups_flat[0].data[0]=float('nan')
    with pytest.raises(PlanError,match='nonfinite'):z.current_state(c)


@pytest.mark.parametrize('case',['success','zero','state','sample_counter','boundary'])
def test_restore_cursor_commits_only_after_last_check(tmp_path,monkeypatch,case):
    root=tmp_path/'cp';binding,h=bundle(root)
    row=z.read_small(root/'observed_0.json')
    raw=NS(micro_step_id=0)
    e=NS(global_steps=0,micro_steps=0,global_samples=0,skipped_steps=0,lr_scheduler=None,optimizer=raw)
    o=NS(optimizer=raw)
    a=NS(distributed_type='DEEPSPEED',deepspeed_engine_wrapped=NS(engine=e),_optimizers=[o])
    c=NS(model=e,optimizer=o,accelerator=a,rank=0,completed_steps=0,poisoned=False)
    expected={'binding':binding,'completed_steps':2,'cumulative_valid_tokens':88,'counters':row['counters']}
    e._load_zero_checkpoint=lambda *args,**kwargs:case!='zero'
    def load(path,tag,**kwargs):
        e.global_steps=2;e.global_samples=17 if case=='sample_counter' else 16
        e._load_zero_checkpoint()
        return str(root/z.TAG),{'critic_session':expected}
    e.load_checkpoint=load
    a.load_state=lambda path,**kwargs:e.load_checkpoint(path,z.TAG,**kwargs)
    s=z.DeepSpeedCriticSession.__new__(z.DeepSpeedCriticSession);s.consumer=c;s.binding=binding;s._tokens=lambda n:88
    def boundary(**kwargs):
        if case=='boundary' and kwargs.get('expected_steps')==2:raise PlanError('injected_final_boundary_failure')
    s._boundary=boundary
    monkeypatch.setattr(z,'current_state',lambda c: {**row['state'],'adamw':'c'*64} if case=='state' else row['state'])
    if case=='success':
        assert s.restore(root,manifest_sha256=h)['completed_steps']==c.completed_steps==2
        assert not c.poisoned and z.counters(e)==row['counters']
    else:
        with pytest.raises((ValueError,PlanError)):s.restore(root,manifest_sha256=h)
        assert c.poisoned and c.completed_steps==0
