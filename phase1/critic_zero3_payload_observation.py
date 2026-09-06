"""Check authenticated, self-generated ZeRO3 payloads against live observations.

Caller owns the checkpoint and verifies all bytes BEFORE loading with torch.
This module does not load files, construct a model, initialize CUDA, or admit
data. BF16 live parameter shards are not saved independently in this format;
only the six directly reconstructible state roles are claimed here.
"""
import math


ROLES={'master_shards','adamw','scaler','python_rng','numpy_rng','torch_rng'}


def require(ok,reason):
    if not ok:raise ValueError(reason)


def finite_tensor(t,*,dtype=None):
    import torch
    require(isinstance(t,torch.Tensor) and t.device.type=='cpu','payload_cpu_tensor')
    require(dtype is None or t.dtype==dtype,'payload_tensor_dtype')
    if t.is_floating_point():
        for chunk in t.reshape(-1).split(1<<20):
            require(bool(torch.isfinite(chunk).all()),'payload_nonfinite')


def verify_payload_observation(model,optimizer,rng,observed,*,binding,step,tokens,parameters):
    import torch
    from phase1.global_local_critic_session import state_fingerprint
    require(not torch.cuda.is_initialized(),'payload_cuda_initialized')
    require(type(step) is int and step>0 and type(tokens) is int and tokens>0
            and type(parameters) is int and parameters>0,'payload_expected_scope')
    require(observed['binding']==binding and observed['completed_steps']==step
            and observed['cumulative_valid_tokens']==tokens,'payload_observed_cursor')
    require(set(observed['state'])==ROLES|{'model_shards'},'payload_observed_roles')
    client=model.get('critic_session')
    require(client=={'binding':binding,'completed_steps':step,'cumulative_valid_tokens':tokens,
                    'counters':observed['counters']},'payload_client_state')
    require(model.get('dp_world_size')==2 and model.get('mp_world_size')==1
            and model.get('global_steps')==step and model.get('skipped_steps')==0
            and model.get('global_samples')==observed['counters']['global_samples'], 'payload_engine_cursor')
    require(model.get('optimizer') is None and model.get('lr_scheduler') is None
            and model.get('data_sampler') is None and model.get('random_ltd') is None,'payload_extra_owner')
    require(model.get('frozen_param_shapes')=={} and model.get('frozen_param_fragments')=={}
            and model.get('shared_params')=={},'payload_unqualified_parameter_modes')
    require(model.get('ds_version')==optimizer.get('ds_version')=='0.19.3'
            and model.get('ds_config')==optimizer.get('ds_config'),'payload_runtime_binding')
    shapes=model.get('param_shapes');require(type(shapes) is list and bool(shapes),'payload_parameter_shapes')
    names=set();numel=0;partitions=[]
    for group in shapes:
        require(isinstance(group,dict) and bool(group),'payload_shape_group')
        count=0
        for name,shape in group.items():
            require(type(name) is str and name not in names,'payload_duplicate_parameter')
            names.add(name)
            require(isinstance(shape,(list,tuple,torch.Size)) and len(shape)>0
                    and all(type(x) is int and x>0 for x in shape),'payload_parameter_shape')
            n=math.prod(shape);numel+=n;count+=(n+1)//2
        partitions.append(count)
    require(numel==parameters,'payload_parameter_count')
    z=optimizer.get('optimizer_state_dict');require(type(z) is dict,'payload_zero_mapping')
    require(z.get('zero_stage')==3 and type(z.get('partition_count')) is int and z['partition_count']==2,'payload_partition_mode')
    masters=z.get('fp32_flat_groups');require(type(masters) is list and len(masters)==len(partitions),'payload_master_groups')
    for t,n in zip(masters,partitions):
        finite_tensor(t,dtype=torch.float32);require(tuple(t.shape)==(n,),'payload_master_shape')
    adam=z.get('optimizer_state_dict');require(type(adam) is dict and set(adam)=={'state','param_groups'},'payload_adam_schema')
    groups=adam['param_groups'];states=adam['state']
    require(type(groups) is list and bool(groups) and type(states) is dict,'payload_adam_groups')
    indices=[p for group in groups for p in group['params']]
    require(indices==list(range(len(masters))) and set(states)==set(indices),'payload_adam_parameter_mapping')
    for index,master in enumerate(masters):
        row=states[index]
        require(type(row) is dict and set(row)=={'step','exp_avg','exp_avg_sq'}
                and type(row['step']) is int and row['step']==step,'payload_adam_step')
        for key in ('exp_avg','exp_avg_sq'):
            finite_tensor(row[key],dtype=torch.float32)
            require(row[key].shape==master.shape,'payload_moment_shape')
    require(z.get('dynamic_loss_scale') is False and z.get('overflow') is False,'payload_scaler_mode')
    scaler=z.get('loss_scaler')
    require(type(scaler).__module__=='deepspeed.runtime.fp16.loss_scaler'
            and type(scaler).__qualname__=='LossScaler' and scaler.cur_scale==1.0,'payload_scaler_class')
    require(type(rng) is dict and set(rng)=={'step','random_state','numpy_random_seed','torch_manual_seed','torch_cuda_manual_seed'},'payload_rng_schema')
    require(type(rng['torch_cuda_manual_seed']) is list and len(rng['torch_cuda_manual_seed'])==2,'payload_rng_devices')
    for t in [rng['torch_manual_seed'],*rng['torch_cuda_manual_seed']]:finite_tensor(t,dtype=torch.uint8)
    values={
        'master_shards':masters,
        'adamw':{'state':[states[i] for i in range(len(masters))],
                 'param_groups':[{k:v for k,v in g.items() if k!='params'} for g in groups]},
        'scaler':{'dynamic':False,'overflow':False,'loss_scale':1.0},
        'python_rng':rng['random_state'],'numpy_rng':rng['numpy_random_seed'],
        'torch_rng':{'cpu':rng['torch_manual_seed'],'cuda_all':rng['torch_cuda_manual_seed']}}
    actual={key:state_fingerprint(value) for key,value in values.items()}
    require(actual=={key:observed['state'][key] for key in ROLES},'payload_live_state_mismatch')
    require(not torch.cuda.is_initialized(),'payload_cuda_initialized')
    return {'classification':'ACTUAL_ZERO3_PAYLOAD_SIX_ROLE_OBSERVATION_CHECK_NOT_RESTART_PARITY',
            'direct_roles_verified':sorted(ROLES),'parameters':numel,'master_groups':len(masters),
            'local_master_elements':sum(partitions),'completed_steps':step,'cumulative_valid_tokens':tokens,
            'live_model_shards_independently_reconstructed':False,'direct_state_sha256':actual,
            'gpu_initialized':False}
