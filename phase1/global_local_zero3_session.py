"""Experimental ZeRO-3 checkpoint backend for the existing critic consumer.

No model/data/job entry point. Hardware qualification and input/budget approval
remain external prerequisites. The ordinary CriticSession DS guard is unchanged.
Only fixed-world, dense BF16 ZeRO-3 with CPU-offload AdamW is implemented.
"""
from pathlib import Path
import inspect
import math
import os
import random
import re

import numpy as np
import torch

from phase1.global_local_critic_session import (
    CriticSession, atomic_json, file_sha, read_small, state_fingerprint,
)
from phase1.global_local_ds_completion import _ownership, observe_deepspeed_restore
from phase1.global_local_execution_plan import PlanError, digest_records

TAG = 'pytorch_model'
ZERO_FILE_SHA = '84778a1aeeac1cdbadcc1cb8ae3644ef9a004a33e28b0247941f4ff95da8daf3'
STATE_KEYS = {'model_shards','master_shards','adamw','scaler','python_rng','numpy_rng','torch_rng'}
COUNTER_KEYS = {'global_steps','global_samples','skipped_steps','micro_steps','micro_step_id','step_applied'}


def require(ok, reason):
    if not ok: raise PlanError(reason)


def verify_restored(expected, actual):
    # Do not repurpose the old DDP/prototype checker: its fixed field set is
    # intentionally different. ZeRO-3 must compare every shard/state role here.
    require(set(expected) == set(actual) == STATE_KEYS, 'zero3_restored_component_set')
    for key in sorted(STATE_KEYS):
        require(expected[key] == actual[key], 'zero3_restored_state_mismatch:'+key)


def expected_files(world=2):
    require(type(world) is int and world == 2, 'zero3_world_not_qualified')
    return {'zero_to_fp32.py'} | {
        path for rank in range(world) for path in (
            f'{TAG}/zero_pp_rank_{rank}_mp_rank_00_model_states.pt',
            f'{TAG}/bf16_zero_pp_rank_{rank}_mp_rank_00_optim_states.pt',
            f'random_states_{rank}.pkl', f'observed_{rank}.json')}


def regular_bundle(root, *, manifest):
    expected = expected_files() | ({'manifest.json'} if manifest else set())
    require(root.is_absolute() and '..' not in root.parts
            and not any(p.is_symlink() for p in (root, *root.parents)), 'zero3_unsafe_root')
    require(root.is_dir(), 'zero3_missing_root')
    members = list(root.rglob('*'))
    require(all(not p.is_symlink() for p in members), 'zero3_symlink_member')
    require({p.relative_to(root).as_posix() for p in members if p.is_dir()} == {TAG}, 'zero3_directory_set')
    require({p.relative_to(root).as_posix() for p in members if not p.is_dir()} == expected, 'zero3_file_set')
    for name in expected:
        p = root/name
        require(p.is_file() and p.stat().st_nlink == 1 and p.stat().st_size > 0, 'zero3_unsafe_member')


def validate_counters(row, steps):
    require(isinstance(row, dict) and set(row) == COUNTER_KEYS, 'zero3_counter_schema')
    require(all(type(row[k]) is int and row[k] >= 0 for k in
                ('global_steps','global_samples','skipped_steps','micro_steps')), 'zero3_counter_type')
    require(type(row['micro_step_id']) is int and row['micro_step_id'] in (-1,0)
            and type(row['step_applied']) is bool, 'zero3_micro_state')
    require(row['global_steps'] == row['micro_steps'] == steps and row['skipped_steps'] == 0
            and row['step_applied'] is (steps > 0), 'zero3_counter_cursor')


def counters(engine):
    return {'global_steps':engine.global_steps, 'global_samples':engine.global_samples,
            'skipped_steps':engine.skipped_steps,'micro_steps':engine.micro_steps,
            'micro_step_id':engine.optimizer.micro_step_id,'step_applied':engine._step_applied}


def validate_consumed_cpu_gradients(engine, steps):
    """Observe, never clear, the pinned Stage3 CPU-offload scratch buffers.

    Stage3 initializes persistent master .grad buffers, consumes them in CPUAdam,
    and deliberately retains them in _release_sub_group when offload is enabled.
    Next boundary's partition_grads COPYs the new accumulation into those buffers.
    Thus nonzero master .grad is not evidence of a pending update. Model grads,
    epilogue/cursor state, subgroup ownership and each actual Adam step still are.
    Only dense, no-swap CPU-offload with the exact runtime binding is supported.
    """
    z = engine.optimizer
    validate_counters(counters(engine), steps)
    require(z.offload_optimizer is True and z.swap_optimizer is False, 'zero3_gradient_mode')
    require(z.micro_step_id == 0 and z._epilogue_ran_this_backward is False
            and z.norm_for_param_grads == {}, 'zero3_pending_accumulation')
    require(all(p.grad is None for p in engine.module.parameters()), 'zero3_pending_model_gradient')
    masters = z.fp32_partitioned_groups_flat
    require(isinstance(masters,list) and bool(masters)
            and all(not g['params'] for g in z.optimizer.param_groups), 'zero3_unclosed_optimizer_group')
    require(set(z.optimizer.state).issubset(set(masters)), 'zero3_unknown_optimizer_parameter')
    for p in masters:
        g = p.grad
        require(p.device.type == 'cpu' and p.dtype == torch.float32
                and isinstance(g,torch.Tensor) and g.device.type == 'cpu'
                and g.dtype == torch.float32 and g.shape == p.shape and g.is_contiguous(),
                'zero3_persistent_gradient_buffer')
        _finite_tensors(g, 'consumed_gradient_buffer')
        state = z.optimizer.state.get(p,{})
        if steps == 0:
            require(not state and not bool(torch.count_nonzero(g)), 'zero3_nonfresh_gradient_state')
        else:
            require(type(state.get('step')) is int and state['step'] == steps,
                    'zero3_adam_step_not_consumed')


def verify_bundle(root, binding, manifest_sha256):
    require(type(binding.get('world')) is int and binding['world'] == 2, 'zero3_world_not_qualified')
    require(re.fullmatch('[0-9a-f]{64}', str(manifest_sha256)), 'zero3_manifest_sha_required')
    regular_bundle(root, manifest=True)
    require(file_sha(root/'manifest.json') == manifest_sha256, 'zero3_manifest_hash')
    m = read_small(root/'manifest.json')
    require(set(m) == {'protocol','binding','completed_steps','cumulative_valid_tokens','files'}, 'zero3_manifest_schema')
    require(m['protocol'] == 'critic-zero3-checkpoint-v1' and m['binding'] == binding, 'zero3_binding')
    step, tokens = m['completed_steps'], m['cumulative_valid_tokens']
    require(type(step) is int and 0 < step <= binding['total_steps']
            and type(tokens) is int and tokens > 0, 'zero3_manifest_cursor')
    require(set(m['files']) == expected_files(), 'zero3_manifest_inventory')
    for name, record in m['files'].items():
        p = root/name
        require(record == {'bytes':p.stat().st_size,'sha256':file_sha(p)}, 'zero3_member_hash')
    for rank in range(2):
        row = read_small(root/f'observed_{rank}.json')
        require(set(row) == {'rank','binding','completed_steps','cumulative_valid_tokens','state','counters'}, 'zero3_rank_schema')
        require(type(row['rank']) is int and row['rank'] == rank and row['binding'] == binding
                and type(row['completed_steps']) is int and row['completed_steps'] == step
                and type(row['cumulative_valid_tokens']) is int and row['cumulative_valid_tokens'] == tokens,
                'zero3_rank_binding')
        validate_counters(row['counters'], step)
        require(set(row['state']) == STATE_KEYS
                and all(re.fullmatch('[0-9a-f]{64}',str(v)) for v in row['state'].values()), 'zero3_state_schema')
    return m


def _finite_tensors(value, path='state'):
    if isinstance(value,torch.Tensor) and value.is_floating_point():
        for chunk in value.detach().reshape(-1).split(1 << 20):
            require(bool(torch.isfinite(chunk).all()), 'zero3_nonfinite_checkpoint_state:'+path)
    elif isinstance(value,dict):
        for key,item in value.items():_finite_tensors(item,path+'/'+str(key))
    elif isinstance(value,(list,tuple)):
        for index,item in enumerate(value):_finite_tensors(item,path+'/'+str(index))


def current_state(consumer):
    """Observe local live shards; do NOT gather a full model or mutate groups."""
    e, a = consumer.model, consumer.accelerator
    z = _ownership(a, e, consumer.optimizer)
    masters = z.fp32_partitioned_groups_flat
    require(isinstance(masters,list) and bool(masters), 'zero3_missing_masters')
    require(all(p.dtype == torch.float32 for p in masters), 'zero3_master_dtype')
    named = list(e.module.named_parameters())
    require(bool(named) and all(p.requires_grad and hasattr(p,'ds_tensor')
                               and p.ds_tensor.dtype == torch.bfloat16 for _,p in named), 'zero3_parameter_shards')
    require(all(not g['params'] for g in z.optimizer.param_groups), 'zero3_unclosed_optimizer_group')
    require(set(z.optimizer.state).issubset(set(masters)), 'zero3_unknown_optimizer_parameter')
    require(z.dynamic_loss_scale is False and z.overflow is False
            and math.isfinite(float(z.loss_scale)) and float(z.loss_scale) == 1.0, 'zero3_scaler_not_static_bf16')
    rng = {'cpu':torch.get_rng_state()}
    if a.device.type == 'cuda': rng['cuda_all'] = torch.cuda.get_rng_state_all()
    values = {
        'model_shards': {'parameters':{n:p.ds_tensor for n,p in named}, 'buffers':dict(e.module.named_buffers())},
        'master_shards':masters,
        'adamw': {'state':[z.optimizer.state.get(p,{}) for p in masters],
                  'param_groups':[{k:v for k,v in g.items() if k != 'params'} for g in z.optimizer.param_groups]},
        'scaler':{'dynamic':z.dynamic_loss_scale,'overflow':z.overflow,'loss_scale':float(z.loss_scale)},
        'python_rng':random.getstate(),'numpy_rng':np.random.get_state(),'torch_rng':rng}
    for key in ('model_shards','master_shards','adamw'):_finite_tensors(values[key],key)
    return {k:state_fingerprint(v) for k,v in values.items()}


def runtime_binding():
    from phase1 import global_local_zero3_padding as padding
    from phase1.global_local_cpu_adam_resume import source_binding as native_cache_binding
    from deepspeed.runtime.zero.stage3 import DeepSpeedZeroOptimizer_Stage3
    from deepspeed.runtime.checkpoint_engine.torch_checkpoint_engine import TorchCheckpointEngine
    from deepspeed.ops.adam import DeepSpeedCPUAdam
    from phase1.global_local_accelerate_update_adapter import runtime_binding as update_runtime
    from phase1.global_local_accelerate_resume_validation import checkpoint_runtime
    require(file_sha(Path(inspect.getsourcefile(DeepSpeedZeroOptimizer_Stage3))) == ZERO_FILE_SHA, 'zero3_runtime_drift')
    cpu_adam_sha=file_sha(Path(inspect.getsourcefile(DeepSpeedCPUAdam)))
    require(cpu_adam_sha=='8a65f2a4b90df3e25cc0d21f81c53e10c3f5fffffa5178c2a7bd91c065641cac',
            'zero3_cpu_adam_runtime_drift')
    import hashlib
    io_methods = {name:hashlib.sha256(inspect.getsource(getattr(TorchCheckpointEngine,name)).encode()).hexdigest()
                  for name in ('save','load')}
    require(io_methods == {'save':'85c17d05c806c95d9efcd176c8a17a9ea22740fbdc71d51721f47f0652070466',
                            'load':'634b7e06db58550c2088a2aed8f176a66e92e929f0f8ba3266006858fcb87ef7'},
            'zero3_checkpoint_io_drift')
    from deepspeed.runtime.zero.partition_parameters import Init
    require(file_sha(Path(inspect.getsourcefile(Init))) == padding.PARTITION_FILE_SHA, 'zero3_partition_runtime_drift')
    return {'update':update_runtime(),'checkpoint':checkpoint_runtime(),'zero3_file_sha256':ZERO_FILE_SHA,
            'checkpoint_io':io_methods,'partition_file_sha256':padding.PARTITION_FILE_SHA,
            'initial_padding_policy_sha256':file_sha(Path(padding.__file__)),
            'cpu_adam_file_sha256':cpu_adam_sha,'native_cpu_adam_cache':native_cache_binding()}


class DeepSpeedCriticSession(CriticSession):
    """Explicit experimental backend. Never an automatic fallback from DDP.

    Only _tokens/run_until are inherited; the ordinary DDP gate stays closed.
    Caller must enforce all-rank participation and a bounded abort on failure.
    Checkpoints must be caller-owned/private; hashing is not a pickle sandbox.
    """
    def __init__(self, consumer, *, training_contract_sha256):
        require(re.fullmatch('[0-9a-f]{64}',str(training_contract_sha256)), 'training_contract_hash_required')
        self.consumer = c = consumer
        e, a = c.model, c.accelerator
        z = _ownership(a,e,c.optimizer)
        from deepspeed.runtime.engine import DeepSpeedEngine
        from deepspeed.runtime.zero.stage3 import DeepSpeedZeroOptimizer_Stage3
        from deepspeed.ops.adam import DeepSpeedCPUAdam
        from deepspeed.runtime.checkpoint_engine.torch_checkpoint_engine import TorchCheckpointEngine
        require(type(e) is DeepSpeedEngine and type(z) is DeepSpeedZeroOptimizer_Stage3
                and type(z.optimizer) is DeepSpeedCPUAdam and z.optimizer.adam_w_mode is True,
                'zero3_backend_type')
        require(type(e.checkpoint_engine) is TorchCheckpointEngine and not e.checkpoint_engine.is_decoupled()
                and not e.use_node_local_storage(), 'zero3_checkpoint_engine')
        require(a.num_processes == 2 and e.dp_world_size == 2 and e.mp_world_size == 1 and e.mpu is None
                and not e.has_moe_layers and not e.load_universal_checkpoint() and z.partition_count == 2,
                'zero3_topology')
        require(a.mixed_precision == 'bf16' and e.bfloat16_enabled() and not e.fp16_enabled()
                and e.zero_optimization_stage() == 3 and z.offload_optimizer is True
                and not z.swap_optimizer and not z.elastic_checkpoint and not e.zero_nvme_offload_optimizer()
                and not getattr(z,'params_in_nvme_and_cpu',False), 'zero3_mode')
        require(e.lr_scheduler is None and e.training_dataloader is None
                and not e.random_ltd_enabled() and not e.curriculum_learning_enabled(), 'zero3_extra_state_owner')
        require(e.save_non_zero_checkpoint and e.save_zero_checkpoint, 'zero3_all_rank_save_required')
        require(not c.poisoned and c.completed_steps == 0 and e.global_steps == e.micro_steps == e.skipped_steps == 0
                and not getattr(a,'scaler',None) and not a._schedulers and not a._dataloaders
                and not a._custom_objects and len(a._models) == 1 and a._models[0] is e
                and not a.project_configuration.automatic_checkpoint_naming, 'zero3_initial_state')
        self.runtime = runtime_binding()
        # No full state_dict() on a ZeRO-3 model: its parameter tensors may be placeholders.
        schema = [(n,list(p.ds_shape),str(p.dtype),p.requires_grad) for n,p in e.module.named_parameters()]
        self.binding = {'protocol':'critic-zero3-session-v1','world':2,'total_steps':c.plan.steps,
            'seed':c.plan.seed,'arm':c.plan.arm,'training_contract_sha256':training_contract_sha256,
            'plan_sha256':c.plan.sha256,'input_sha256':c.plan.input_sha256,
            'runtime_sha256':digest_records([self.runtime]),'ds_config_sha256':state_fingerprint(e.config),
            'model_schema_sha256':state_fingerprint(schema),
            'initial_optimizer_groups_sha256':state_fingerprint([{k:v for k,v in g.items() if k!='params'}
                                                                for g in z.optimizer.param_groups]),
            'source_sha256':file_sha(Path(__file__))}
        current_state(c)

    def _boundary(self, *, expected_steps=None):
        c = self.consumer; e, a = c.model,c.accelerator
        require(not c.poisoned and e.training and a.step == 0 and a.sync_gradients, 'zero3_not_clean_boundary')
        step = c.completed_steps if expected_steps is None else expected_steps
        require(e.global_steps == step and e.skipped_steps == 0, 'zero3_engine_cursor_drift')
        require(not e.optimizer.overflow and not a.optimizer_step_was_skipped, 'zero3_skipped_update')
        validate_consumed_cpu_gradients(e,step)

    def save(self, root):
        c, root = self.consumer,Path(root)
        try:
            self._boundary()
            require(c.completed_steps > 0 and root.is_absolute() and not root.exists()
                    and '..' not in root.parts and not any(p.is_symlink() for p in (root,*root.parents)), 'zero3_new_save_path')
            progress = counters(c.model); validate_counters(progress,c.completed_steps)
            before = current_state(c)
            client = {'binding':self.binding,'completed_steps':c.completed_steps,
                      'cumulative_valid_tokens':self._tokens(c.completed_steps),'counters':progress}
            partial = root.with_name(root.name+'.partial')
            if c.rank == 0: partial.mkdir(mode=0o700)
            c.accelerator.wait_for_everyone()
            c.accelerator.save_state(str(partial),client_state={'critic_session':client},save_latest=False)
            verify_restored(before,current_state(c))
            require(progress == counters(c.model),'zero3_save_changed_counters')
            atomic_json(partial/f'observed_{c.rank}.json',{'rank':c.rank,'binding':self.binding,
                'completed_steps':c.completed_steps,'cumulative_valid_tokens':self._tokens(c.completed_steps),
                'state':before,'counters':progress})
            c.accelerator.wait_for_everyone()
            if c.rank == 0:
                regular_bundle(partial,manifest=False)
                atomic_json(partial/'manifest.json',{'protocol':'critic-zero3-checkpoint-v1','binding':self.binding,
                    'completed_steps':c.completed_steps,'cumulative_valid_tokens':self._tokens(c.completed_steps),
                    'files':{n:{'bytes':(partial/n).stat().st_size,'sha256':file_sha(partial/n)} for n in sorted(expected_files())}})
                os.rename(partial,root)
            c.accelerator.wait_for_everyone()
            sha = file_sha(root/'manifest.json');verify_bundle(root,self.binding,sha)
            return sha
        except BaseException:
            c.poisoned = True
            raise

    def restore(self, root, *, manifest_sha256):
        c,root = self.consumer,Path(root)
        try:
            self._boundary()
            require(c.completed_steps == c.model.global_steps == c.model.micro_steps == 0, 'zero3_fresh_restore_only')
            m = verify_bundle(root,self.binding,manifest_sha256)
            step = m['completed_steps']
            require(m['cumulative_valid_tokens'] == self._tokens(step), 'zero3_token_cursor')
            row = read_small(root/f'observed_{c.rank}.json')
            client = {'binding':self.binding,'completed_steps':step,
                      'cumulative_valid_tokens':self._tokens(step),'counters':row['counters']}
            with observe_deepspeed_restore(c.accelerator,c.model,c.optimizer,completed_steps=step,client_binding=client):
                c.accelerator.load_state(str(root),load_module_strict=True,load_optimizer_states=True,
                                         load_module_only=False,load_lr_scheduler_states=False)
            verify_restored(row['state'],current_state(c))
            # CPUAdam's native step/beta-power cache is NOT in state_dict().
            # This engine was fresh before load (see initial and restore gates).
            # Reproduce the consumed cache history without touching coefficients.
            from phase1.global_local_cpu_adam_resume import restore_native_cache
            native_cache=restore_native_cache(c.model.optimizer.optimizer,step)
            verify_restored(row['state'],current_state(c))
            e,z = c.model,c.model.optimizer
            require(e.global_samples == row['counters']['global_samples'], 'zero3_restored_sample_counter')
            # Pinned DS does NOT save/restore these counters. Set only after the
            # full optimizer/master/BF16/RNG comparison, not before a failed load.
            e.micro_steps = row['counters']['micro_steps']
            z.micro_step_id = row['counters']['micro_step_id']
            e._step_applied = row['counters']['step_applied']
            require(counters(e) == row['counters'], 'zero3_restored_counters')
            self._boundary(expected_steps=step)
            c.completed_steps = step
            return {'completed_steps':step,'cumulative_valid_tokens':self._tokens(step),
                    'all_state_components_restored':True,'manifest_sha256':manifest_sha256,
                    'native_cpu_adam_cache':native_cache}
        except BaseException:
            c.poisoned = True
            raise
