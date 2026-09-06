"""Restore the pinned native CPUAdam bias-power cache, not model/Adam tensors.

Only for a fresh native optimizer whose ordinary checkpoint state has just been
restored. Caller owns that lifecycle and must compare every serialized state and
RNG fingerprint before/after. Empty native calls reproduce IncrementStep's float
multiplication history; they touch no coefficient and do not call Python step().
"""
import hashlib,inspect,math
from pathlib import Path
from phase1.global_local_execution_plan import PlanError

SOURCES={
    'ops/adam/cpu_adam.py':'8a65f2a4b90df3e25cc0d21f81c53e10c3f5fffffa5178c2a7bd91c065641cac',
    'ops/csrc/includes/cpu_adam.h':'860efc966eb408c56b277606346b85b7c2f2889db9740090178b70831e5f9584',
    'ops/csrc/adam/cpu_adam_impl.cpp':'27bf2f662fc119c53902011b4cc59ba4e7527b9ade56a13c8b4f1ba1f5f038ee'}


def require(ok,why):
    if not ok:raise PlanError(why)


def replay_spec(groups,steps):
    require(type(steps) is int and 0<steps<=100000,'native_cache_step_bound')
    require(type(groups) is list and bool(groups),'native_cache_groups')
    fields=('lr','betas','eps','weight_decay','bias_correction')
    specs=[]
    for group in groups:
        require(isinstance(group,dict) and set(fields).issubset(group),'native_cache_group_schema')
        require(group.get('params')==[],'native_cache_subgroup_open')
        b=group['betas']
        require(type(b) is tuple and len(b)==2 and all(type(x) is float and math.isfinite(x) and 0<x<1 for x in b),
                'native_cache_betas')
        require(all(type(group[k]) is float and math.isfinite(group[k]) for k in ('lr','eps','weight_decay'))
                and group['lr']>0 and group['eps']>0 and group['weight_decay']>=0
                and group['bias_correction'] is True,'native_cache_options')
        specs.append({k:group[k] for k in fields})
    require(all(s==specs[0] for s in specs),'native_cache_mixed_groups')
    return specs[0]


def source_binding():
    from deepspeed.ops.adam import DeepSpeedCPUAdam
    root=Path(inspect.getsourcefile(DeepSpeedCPUAdam)).parents[2]
    actual={n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in SOURCES}
    require(actual==SOURCES,'native_cache_source_drift')
    return {'runtime_sources':actual,'policy_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}


def restore_native_cache(optimizer,steps):
    import torch
    from deepspeed.ops.adam import DeepSpeedCPUAdam
    require(type(optimizer) is DeepSpeedCPUAdam and optimizer.adam_w_mode is True,'native_cache_optimizer_type')
    binding=source_binding();spec=replay_spec(optimizer.param_groups,steps)
    require(not getattr(optimizer,'_critic_native_cache_restore_attempted',False),'native_cache_already_attempted')
    require(bool(optimizer.state),'native_cache_missing_restored_state')
    for p,state in optimizer.state.items():
        require(isinstance(p,torch.Tensor) and p.device.type=='cpu' and p.dtype==torch.float32
                and type(state.get('step')) is int and state['step']==steps,'native_cache_restored_step_mismatch')
    optimizer._critic_native_cache_restore_attempted=True
    empty=torch.empty(0,dtype=torch.float32,device='cpu')
    for step in range(1,steps+1):
        result=optimizer.ds_opt_adam.adam_update(optimizer.opt_id,step,spec['lr'],*spec['betas'],spec['eps'],
            spec['weight_decay'],spec['bias_correction'],empty,empty,empty,empty)
        require(result==0,'native_cache_replay_failed')
    return {'policy':'replay_native_bias_powers_on_empty_tensors_v1','completed_steps':steps,
            'empty_native_calls':steps,'parameter_elements_passed':0,'python_optimizer_step_calls':0,
            'native_extension_sha256':hashlib.sha256(Path(optimizer.ds_opt_adam.__file__).read_bytes()).hexdigest(),
            **binding}
