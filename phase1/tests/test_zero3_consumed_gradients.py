"""CPU tensor negative controls; not a substitute for actual GPU resume parity."""
from types import SimpleNamespace as NS
import ast
import hashlib
from pathlib import Path
import __future__
import pytest
import torch
from phase1.global_local_zero3_session import validate_consumed_cpu_gradients
from phase1.global_local_execution_plan import PlanError


def fixture(steps=2):
    model=torch.nn.Linear(2,1,bias=False).bfloat16()
    p=torch.nn.Parameter(torch.tensor([1.,2.]))
    p.grad=torch.tensor([0.25,0.75]) if steps else torch.zeros(2)
    opt=NS(param_groups=[{'params':[]}],state={p:{'step':steps}} if steps else {})
    z=NS(fp32_partitioned_groups_flat=[p],optimizer=opt,offload_optimizer=True,swap_optimizer=False,
         micro_step_id=0,_epilogue_ran_this_backward=False,norm_for_param_grads={})
    e=NS(module=model,optimizer=z,global_steps=steps,micro_steps=steps,global_samples=8*steps,
         skipped_steps=0,_step_applied=steps>0)
    return e,p


@pytest.mark.parametrize('steps',[0,2,3,4])
def test_readonly_consumed_buffer_is_not_pending(steps):
    e,p=fixture(steps);before=p.grad.clone();identity=id(p.grad);version=p.grad._version
    validate_consumed_cpu_gradients(e,steps)
    assert id(p.grad)==identity and p.grad._version==version and torch.equal(p.grad,before)


@pytest.mark.parametrize('fault',['model_grad','epilogue','micro','norm','group','missing_buffer',
    'nonfinite','adam_behind','adam_ahead','bool_step','no_adam','engine_behind','skipped','not_applied',
    'no_offload','swap','unknown_state'])
def test_pending_or_corrupt_state_is_rejected(fault):
    e,p=fixture();z=e.optimizer
    if fault=='model_grad':e.module.weight.grad=torch.zeros_like(e.module.weight)
    if fault=='epilogue':z._epilogue_ran_this_backward=True
    if fault=='micro':z.micro_step_id=1
    if fault=='norm':z.norm_for_param_grads={0:1.}
    if fault=='group':z.optimizer.param_groups[0]['params']=[p]
    if fault=='missing_buffer':p.grad=None
    if fault=='nonfinite':p.grad[0]=float('nan')
    if fault=='adam_behind':z.optimizer.state[p]['step']=1
    if fault=='adam_ahead':z.optimizer.state[p]['step']=3
    if fault=='bool_step':z.optimizer.state[p]['step']=True
    if fault=='no_adam':z.optimizer.state={}
    if fault=='engine_behind':e.global_steps=1
    if fault=='skipped':e.skipped_steps=1
    if fault=='not_applied':e._step_applied=False
    if fault=='no_offload':z.offload_optimizer=False
    if fault=='swap':z.swap_optimizer=True
    if fault=='unknown_state':z.optimizer.state[torch.nn.Parameter(torch.ones(1))]={}
    with pytest.raises(PlanError):validate_consumed_cpu_gradients(e,2)


def test_fresh_engine_cannot_hide_nonzero_master_buffer():
    e,p=fixture(0);p.grad[0]=1.
    with pytest.raises(PlanError,match='nonfresh'):validate_consumed_cpu_gradients(e,0)


def installed_method(name):
    path=Path('/research/d7/spc/yzyang4/venvs/critic-blackwell-g0-20260905-r5/lib/python3.11/site-packages/deepspeed/runtime/zero/stage3.py')
    if not path.is_file():pytest.skip('pinned Linux runtime source required')
    raw=path.read_bytes()
    assert hashlib.sha256(raw).hexdigest()=='84778a1aeeac1cdbadcc1cb8ae3644ef9a004a33e28b0247941f4ff95da8daf3'
    cls=next(n for n in ast.parse(raw).body if isinstance(n,ast.ClassDef) and n.name=='DeepSpeedZeroOptimizer_Stage3')
    fn=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name==name)
    fn.decorator_list=[]
    env={'torch':torch,'see_memory_usage':lambda *a,**kw:None,
         'get_accelerator':lambda:NS(on_accelerator=lambda t:t.device.type=='cuda',is_synchronized_device=lambda:True)}
    exec(compile(ast.Module(body=[fn],type_ignores=[]),str(path),'exec',flags=__future__.annotations.compiler_flag),env)
    return env[name]


def test_actual_installed_release_retains_cpu_offload_gradient():
    e,p=fixture();z=e.optimizer;before=p.grad.clone();identity=id(p.grad)
    z._swappable_optimizer_subgroup=lambda i:False
    installed_method('_release_sub_group')(z,0,set())
    assert id(p.grad)==identity and torch.equal(p.grad,before)
    z.offload_optimizer=False
    installed_method('_release_sub_group')(z,0,set())
    assert p.grad is None


def test_actual_installed_partition_overwrites_old_then_accumulates_new():
    e,p=fixture();z=e.optimizer;q=e.module.weight
    q.ds_numel=2;q.ds_id=0;q.partition_numel=lambda:2
    z._get_param_partition_rank=lambda param:0;z.get_param_id=lambda param:0
    z.grad_position={0:(0,0,2)};z._swappable_optimizer_subgroup=lambda i:False
    z._constant_buffered_norm2=lambda g:float(torch.linalg.vector_norm(g))
    z.gradient_accumulation_dtype=torch.float32;z.master_weights_and_grads_dtype=torch.float32
    z.__param_id_to_grad_partition={0:torch.full((2,),999.)}
    z.is_gradient_accumulation_boundary=False;old=p.grad.clone()
    partition=installed_method('partition_grads')
    partition(z,[q],[torch.tensor([2.,3.])])
    assert torch.equal(p.grad,old)  # no premature replacement at intermediate microbatch
    assert torch.equal(z.__param_id_to_grad_partition[0],torch.tensor([2.,3.]))
    z.micro_step_id=1;z.is_gradient_accumulation_boundary=True
    partition(z,[q],[torch.tensor([5.,7.])])
    assert torch.equal(p.grad,torch.tensor([7.,10.]))  # not old+new, exact fresh sum
    assert q.grad is None and z.norm_for_param_grads
    with pytest.raises(PlanError):validate_consumed_cpu_gradients(e,2)


def test_actual_zero_grad_preserves_master_buffer_and_resets_epilogue():
    e,p=fixture();z=e.optimizer;z.fp16_groups=[list(e.module.parameters())]
    z.micro_step_id=1;z._epilogue_ran_this_backward=True
    e.module.weight.grad=torch.ones_like(e.module.weight);old=p.grad.clone()
    installed_method('zero_grad')(z)
    assert z.micro_step_id==0 and z._epilogue_ran_this_backward is False
    assert e.module.weight.grad is None and torch.equal(p.grad,old)
