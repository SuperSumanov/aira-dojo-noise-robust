import copy
import random
import pytest
from phase1.critic_zero3_payload_observation import verify_payload_observation


def fixture():
    torch=pytest.importorskip('torch');np=pytest.importorskip('numpy');pytest.importorskip('deepspeed')
    from deepspeed.runtime.fp16.loss_scaler import LossScaler
    from phase1.global_local_critic_session import state_fingerprint as h
    binding={'world':2,'total_steps':2};counters={'global_samples':128}
    master=torch.tensor([1.,2.]);moment=torch.tensor([.1,.2])
    states={0:{'step':1,'exp_avg':moment,'exp_avg_sq':moment.square()}}
    groups=[{'params':[0],'lr':1e-5}]
    rng={'step':0,'random_state':random.Random(6).getstate(),'numpy_random_seed':np.random.RandomState(6).get_state(),
         'torch_manual_seed':torch.tensor([1,2],dtype=torch.uint8),
         'torch_cuda_manual_seed':[torch.tensor([3,4],dtype=torch.uint8),torch.tensor([5,6],dtype=torch.uint8)]}
    z={'zero_stage':3,'partition_count':2,'fp32_flat_groups':[master],
       'optimizer_state_dict':{'state':states,'param_groups':groups},
       'dynamic_loss_scale':False,'overflow':False,'loss_scaler':LossScaler(1.0)}
    opt={'ds_version':'0.19.3','ds_config':{'test':'synthetic'},'optimizer_state_dict':z}
    model={'critic_session':{'binding':binding,'completed_steps':1,'cumulative_valid_tokens':8,'counters':counters},
           'dp_world_size':2,'mp_world_size':1,'global_steps':1,'skipped_steps':0,'global_samples':128,
           'optimizer':None,'lr_scheduler':None,'data_sampler':None,'random_ltd':None,
           'frozen_param_shapes':{},'frozen_param_fragments':{},'shared_params':{},
           'ds_version':'0.19.3','ds_config':{'test':'synthetic'},'param_shapes':[{'a':torch.Size([3])}]}
    v={'master_shards':[master],'adamw':{'state':[states[0]],'param_groups':[{'lr':1e-5}]},
       'scaler':{'dynamic':False,'overflow':False,'loss_scale':1.0},'python_rng':rng['random_state'],
       'numpy_rng':rng['numpy_random_seed'],'torch_rng':{'cpu':rng['torch_manual_seed'],'cuda_all':rng['torch_cuda_manual_seed']}}
    observed={'binding':binding,'completed_steps':1,'cumulative_valid_tokens':8,'counters':counters,
              'state':{**{k:h(x) for k,x in v.items()},'model_shards':'a'*64}}
    return model,opt,rng,observed,binding


def check(f):
    model,opt,rng,observed,binding=f
    return verify_payload_observation(model,opt,rng,observed,binding=binding,step=1,tokens=8,parameters=3)


def test_actual_six_roles():
    result=check(fixture());assert len(result['direct_roles_verified'])==6
    assert result['live_model_shards_independently_reconstructed'] is False


@pytest.mark.parametrize('failure',['master','nan','moment','step','rng','groups','size','client','scaler','extra_role','world'])
def test_actual_payload_mismatch(failure):
    torch=pytest.importorskip('torch');f=fixture();model,opt,rng,observed,_=f;z=opt['optimizer_state_dict']
    if failure=='master':z['fp32_flat_groups'][0][0]=4
    elif failure=='nan':z['fp32_flat_groups'][0][0]=float('nan')
    elif failure=='moment':z['optimizer_state_dict']['state'][0]['exp_avg'][0]=5
    elif failure=='step':z['optimizer_state_dict']['state'][0]['step']=True
    elif failure=='rng':rng['torch_cuda_manual_seed'][1][0]=7
    elif failure=='groups':z['optimizer_state_dict']['param_groups'][0]['params']=[1]
    elif failure=='size':model['param_shapes'][0]['a']=torch.Size([5])
    elif failure=='client':model['critic_session']['completed_steps']=2
    elif failure=='scaler':z['dynamic_loss_scale']=True
    elif failure=='extra_role':observed['state']['unknown']='b'*64
    elif failure=='world':z['partition_count']=4
    with pytest.raises(ValueError):check(f)


def test_module_import_does_not_load_backend():
    import subprocess,sys
    p=subprocess.run([sys.executable,'-B','-c',
        "import sys; import phase1.critic_zero3_payload_observation; assert 'torch' not in sys.modules; assert 'deepspeed' not in sys.modules"],capture_output=True)
    assert p.returncode==0
