"""Fail-closed completion accounting for the exact-source DeepSpeed adapter.

No engine constructor, tensor operations, data readers, optimizer steps or CLI.
Callers still need runtime_binding(), source/split and budget authorization.
Snapshots are process-local, not serializable checkpoint admission receipts.
"""
from dataclasses import dataclass
import math

from phase1.global_local_execution_plan import PlanError


def _require(ok, reason):
    if not ok:
        raise PlanError(reason)


def _count(engine, name):
    value = getattr(engine, name, None)
    _require(type(value) is int and value >= 0, 'invalid_deepspeed_'+name)
    return value


def _flag(holder, name):
    value = getattr(holder, name, None)
    _require(type(value) is bool, 'unobserved_deepspeed_'+name)
    return value


def _ownership(accelerator, engine, optimizer):
    _require(str(getattr(accelerator, 'distributed_type', '')).upper().endswith('DEEPSPEED'), 'not_deepspeed_update')
    wrapper = getattr(accelerator, 'deepspeed_engine_wrapped', None)
    _require(getattr(wrapper, 'engine', None) is engine, 'deepspeed_engine_identity_mismatch')
    registered = getattr(accelerator, '_optimizers', None)
    _require(isinstance(registered, list) and len(registered) == 1 and registered[0] is optimizer,
             'deepspeed_optimizer_registration_mismatch')
    raw = getattr(engine, 'optimizer', None)
    _require(raw is not None and getattr(optimizer, 'optimizer', None) is raw, 'deepspeed_optimizer_identity_mismatch')
    return raw


def _skipped(accelerator, engine, optimizer):
    raw = _ownership(accelerator, engine, optimizer)
    # The bound ZeRO implementation exposes overflow. Missing is not False.
    values = (_flag(accelerator, 'optimizer_step_was_skipped'),
              _flag(optimizer, 'step_was_skipped'), _flag(raw, 'overflow'))
    _require(len(set(values)) == 1, 'deepspeed_skip_signal_disagreement')
    return values[0]


@dataclass
class DeepSpeedBefore:
    engine_identity: int
    optimizer_identity: int
    global_steps: int
    skipped_steps: int
    micro_steps: int
    consumed: bool = False


def begin_deepspeed_update(accelerator, engine, optimizer, *, max_grad_norm):
    """Capture BEFORE any microbatch backward of one planned update.

DeepSpeed owns clipping/step/zeroing. A second scheduler would own LR too,
which is unsupported by the explicit token-progress-LR contract.
"""
    _ownership(accelerator, engine, optimizer)
    _require(type(max_grad_norm) in (float, int) and math.isfinite(max_grad_norm) and max_grad_norm > 0,
             'invalid_max_gradient_norm')
    clipping = getattr(engine, 'gradient_clipping', None)
    _require(callable(clipping), 'deepspeed_clipping_unobserved')
    actual = clipping()
    _require(type(actual) in (float, int) and math.isfinite(actual) and actual == max_grad_norm,
             'deepspeed_gradient_clipping_mismatch')
    _require(hasattr(engine, 'lr_scheduler') and engine.lr_scheduler is None, 'deepspeed_second_lr_owner')
    _require(not _skipped(accelerator, engine, optimizer), 'previous_deepspeed_skip_not_reconciled')
    return DeepSpeedBefore(id(engine), id(optimizer), _count(engine, 'global_steps'),
                           _count(engine, 'skipped_steps'), _count(engine, 'micro_steps'))


def finish_deepspeed_update(accelerator, engine, optimizer, before):
    """Observe, NEVER step. global_steps alone counts attempted, not applied steps.

In the bound Accelerate wrapper engine.step() is called once, only on the
sync boundary; its micro_steps therefore advances once per PLANNED update.
DeepSpeed global_samples is not consumed-pair accounting for partial updates.
"""
    _ownership(accelerator, engine, optimizer)
    _require(type(before) is DeepSpeedBefore, 'missing_deepspeed_before_receipt')
    _require(before.consumed is False, 'deepspeed_before_receipt_already_consumed')
    _require(before.engine_identity == id(engine) and before.optimizer_identity == id(optimizer),
             'deepspeed_before_identity_mismatch')
    _require(_flag(accelerator, 'sync_gradients'), 'deepspeed_finish_without_sync')
    step_delta = _count(engine, 'global_steps') - before.global_steps
    micro_delta = _count(engine, 'micro_steps') - before.micro_steps
    skipped_delta = _count(engine, 'skipped_steps') - before.skipped_steps
    _require(step_delta == micro_delta == 1, 'deepspeed_missing_or_duplicate_step')
    skipped = _skipped(accelerator, engine, optimizer)
    applied = _flag(engine, '_step_applied')
    _require(skipped_delta == int(skipped) and applied is (not skipped), 'deepspeed_completion_disagreement')
    before.consumed = True
    return dict(owner='deepspeed_boundary_backward', optimizer_step_skipped=skipped,
                attempted_update_delta=step_delta, applied_update_delta=int(applied),
                skipped_update_delta=skipped_delta, can_commit_plan_cursor=applied,
                actual_pair_count_source='frozen_consumption_receipts_not_engine_global_samples')
