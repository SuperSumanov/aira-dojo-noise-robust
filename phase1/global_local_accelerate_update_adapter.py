"""Exact-update adapter for the approved historical Global-to-Local plan.

This module is deliberately below ``transformers.Trainer``.  Trainer 5.12.1
can shorten only the final accumulation window of an epoch, while the plan
requires every source-cycle boundary to be an optimizer boundary.  The helper
therefore drives Accelerate's synchronization flag explicitly.  It has no CLI,
data reader, model loader, checkpoint selector, or job-submission path.

The adapter does not authorize an effect fit.  Callers must independently bind
the plan, source provenance, model checkpoint, split, storage, and GPU budget.
"""
from __future__ import annotations

from contextlib import contextmanager, nullcontext
from decimal import Decimal
import hashlib
import inspect
from pathlib import Path

from phase1.global_local_execution_plan import PlanError


RUNTIME_VERSIONS = {
    "torch": "2.11.0+cu128",
    "transformers": "5.12.1",
    "accelerate": "1.14.0",
    "deepspeed": "0.19.3",
}
RUNTIME_FILE_SHA256 = {
    "transformers.trainer": "c1a56423fcfcf9cfec6847467ffb2e2c8a9a9e8cc1836b82c87ed0c81e504be0",
    "accelerate.accelerator": "47088e0ab3bf21eec97e16afa14595e1db511f6ead9ab85c4eaa5f6f66fe5e61",
    "accelerate.state": "18e0a2c38bfc745a7bdeb5878ab232c55b4a8256d856699a2825051689e7dce2",
    "accelerate.utils.deepspeed": "82dfa3c0ea4eb51b3a378b2886e48ed88df1d6a2e83bab986239cfacaa7a664e",
    "deepspeed.runtime.engine": "e5d1e2642302fc092994dd4a4712a0d4c62c3541c632dcd93528281fd40dd1ec",
}
RUNTIME_METHOD_SHA256 = {
    "Trainer._run_epoch": "c704c082dae4b742beb3787afb7636c247294aefbe5803b79f02994ab241221c",
    "Trainer.training_step": "7acfd3d5040fed7c2ea94cfce8979d1fb8d38bb1f79f4dbb20f729c8bd96863c",
    "Accelerator.backward": "fb25ccb046cab6646be1b6ee2ddef9fd0b3f5e9bc924825f19db492ffa1dc515",
    "GradientState._set_sync_gradients": "c853f24eddceec3c822352eecf8516013a392f4bb2a9b7862b8b0edd0a53feb4",
    "DeepSpeedEngineWrapper.backward": "0185cad8f450094b32cfb1014e9ae7a06c3a266f7341c3a5ae673109e36aa536",
    "DeepSpeedEngine.is_gradient_accumulation_boundary": "a49bef80e4f79efd44fa9e72096db82132ab9510535887732e8117ca91994c3c",
    "DeepSpeedEngine.set_gradient_accumulation_boundary": "f0a8b49e1dfa6bc1fcc8b70db2821521195c21d39b80b31455d3eb0075b925b8",
    "DeepSpeedEngine.step": "650173b0513bc0d354bdbdfc3a061d41193f619af766d944cbcbd89d32af4c1d",
}


def _sha_file(value) -> str:
    return hashlib.sha256(Path(inspect.getsourcefile(value)).read_bytes()).hexdigest()


def _sha_method(value) -> str:
    return hashlib.sha256(inspect.getsource(value).encode()).hexdigest()


def runtime_binding() -> dict:
    """Fail closed unless the exact audited G0 software is active."""
    import accelerate
    import deepspeed
    import torch
    import transformers
    from accelerate import Accelerator
    from accelerate.state import GradientState
    from accelerate.utils.deepspeed import DeepSpeedEngineWrapper
    from deepspeed.runtime.engine import DeepSpeedEngine
    from transformers import Trainer

    versions = {
        "torch": str(torch.__version__),
        "transformers": transformers.__version__,
        "accelerate": accelerate.__version__,
        "deepspeed": deepspeed.__version__,
    }
    if versions != RUNTIME_VERSIONS:
        raise PlanError("unvalidated_accelerate_runtime_version")
    files = {
        "transformers.trainer": _sha_file(Trainer),
        "accelerate.accelerator": _sha_file(Accelerator),
        "accelerate.state": _sha_file(GradientState),
        "accelerate.utils.deepspeed": _sha_file(DeepSpeedEngineWrapper),
        "deepspeed.runtime.engine": _sha_file(DeepSpeedEngine),
    }
    if files != RUNTIME_FILE_SHA256:
        raise PlanError("unvalidated_accelerate_runtime_source")
    methods = {
        "Trainer._run_epoch": _sha_method(Trainer._run_epoch),
        "Trainer.training_step": _sha_method(Trainer.training_step),
        "Accelerator.backward": _sha_method(Accelerator.backward),
        "GradientState._set_sync_gradients": _sha_method(GradientState._set_sync_gradients),
        "DeepSpeedEngineWrapper.backward": _sha_method(DeepSpeedEngineWrapper.backward),
        "DeepSpeedEngine.is_gradient_accumulation_boundary": _sha_method(
            DeepSpeedEngine.is_gradient_accumulation_boundary
        ),
        "DeepSpeedEngine.set_gradient_accumulation_boundary": _sha_method(
            DeepSpeedEngine.set_gradient_accumulation_boundary
        ),
        "DeepSpeedEngine.step": _sha_method(DeepSpeedEngine.step),
    }
    if methods != RUNTIME_METHOD_SHA256:
        raise PlanError("unvalidated_accelerate_runtime_method")
    return {"versions": versions, "file_sha256": files, "method_sha256": methods}


def rank_update_batches(plan, rank: int, optimizer_step: int):
    """Return one rank's complete, contiguous microbatch sequence for an update."""
    if type(rank) is not int or not 0 <= rank < plan.shape.world_size:
        raise PlanError("invalid_plan_rank")
    if type(optimizer_step) is not int or not 0 <= optimizer_step < plan.steps:
        raise PlanError("invalid_plan_optimizer_step")
    batches = tuple(
        batch for batch in plan.batches
        if batch.rank == rank and batch.optimizer_step == optimizer_step
    )
    if not batches or tuple(batch.micro_step for batch in batches) != tuple(range(len(batches))):
        raise PlanError("missing_or_noncontiguous_rank_microbatches")
    shared = {
        (
            batch.source,
            batch.segment_index,
            batch.cycle,
            batch.update_real_pairs,
            batch.update_valid_tokens,
            batch.cumulative_valid_tokens_after_update,
            batch.lr_scale_numerator,
            batch.lr_scale_denominator,
        )
        for batch in batches
    }
    if len(shared) != 1 or any(not batch.rows for batch in batches):
        raise PlanError("rank_update_metadata_mismatch")
    return batches


def update_learning_rate(plan, batches, peak_learning_rate: str | Decimal | float) -> float:
    """Set no state; compute the predeclared LR for the current update exactly."""
    if not batches:
        raise PlanError("empty_update")
    fractions = {(batch.lr_scale_numerator, batch.lr_scale_denominator) for batch in batches}
    if len(fractions) != 1:
        raise PlanError("mixed_learning_rate_within_update")
    numerator, denominator = next(iter(fractions))
    if denominator != plan.warmup_valid_tokens or not 0 < numerator <= denominator:
        raise PlanError("learning_rate_plan_mismatch")
    peak = Decimal(str(peak_learning_rate))
    if peak <= 0 or str(peak) != plan.peak_lr_decimal:
        raise PlanError("peak_learning_rate_mismatch")
    return float(peak * Decimal(numerator) / Decimal(denominator))


def set_optimizer_learning_rate(optimizer, value: float) -> None:
    if not isinstance(value, float) or not 0 < value < 1:
        raise PlanError("invalid_update_learning_rate")
    groups = getattr(optimizer, "param_groups", None)
    if not isinstance(groups, list) or not groups:
        raise PlanError("optimizer_param_groups_unavailable")
    for group in groups:
        group["lr"] = value
    if any(group.get("lr") != value for group in groups):
        raise PlanError("optimizer_learning_rate_write_failed")


def _is_deepspeed(accelerator) -> bool:
    return str(getattr(accelerator, "distributed_type", "")).upper().endswith("DEEPSPEED")


@contextmanager
def planned_microbatch_context(accelerator, model, *, synchronize: bool):
    """Set the same boundary seen by DDP and DeepSpeed before forward/backward."""
    if type(synchronize) is not bool:
        raise PlanError("invalid_synchronization_flag")
    state = getattr(accelerator, "gradient_state", None)
    setter = getattr(state, "_set_sync_gradients", None)
    if not callable(setter):
        raise PlanError("accelerate_sync_boundary_unavailable")
    setter(synchronize)
    if bool(getattr(accelerator, "sync_gradients", None)) is not synchronize:
        raise PlanError("accelerate_sync_boundary_write_failed")
    context = nullcontext() if synchronize or _is_deepspeed(accelerator) else accelerator.no_sync(model)
    with context:
        yield


def backward_local_pair_mean(accelerator, local_mean_loss, batch) -> float:
    """Backpropagate a local pair mean so rank-mean DDP equals the global pair mean."""
    import torch

    if not isinstance(local_mean_loss, torch.Tensor) or local_mean_loss.numel() != 1:
        raise PlanError("loss_must_be_scalar_tensor")
    if not torch.isfinite(local_mean_loss):
        raise PlanError("nonfinite_local_mean_loss")
    count = len(batch.rows)
    if (
        type(batch.loss_mean_scale_numerator) is not int
        or batch.loss_mean_scale_numerator <= 0
        or type(batch.loss_mean_scale_denominator) is not int
        or batch.loss_mean_scale_denominator != batch.update_real_pairs
        or batch.loss_mean_scale_denominator <= 0
    ):
        raise PlanError("invalid_loss_scale_metadata")
    expected_numerator = count * getattr(accelerator, "num_processes", 0)
    if batch.loss_mean_scale_numerator != expected_numerator:
        raise PlanError("loss_scale_world_or_count_mismatch")
    scaled = (
        local_mean_loss
        * batch.loss_mean_scale_numerator
        / batch.loss_mean_scale_denominator
    )
    if _is_deepspeed(accelerator):
        # Accelerate's DS wrapper passes this through to engine.backward and
        # performs engine.step only at the manually supplied sync boundary.
        accelerator.backward(scaled, scale_wrt_gas=False)
    else:
        # Accelerator.backward divides by its fixed configured GAS.  Cancel
        # that factor because this plan supplies exact per-update scaling.
        gas = getattr(accelerator, "gradient_accumulation_steps", None)
        if type(gas) is not int or gas < 1:
            raise PlanError("invalid_accelerate_gradient_accumulation_steps")
        accelerator.backward(scaled * gas)
    return float(scaled.detach().cpu())


def finish_non_deepspeed_update(accelerator, model, optimizer, *, max_grad_norm: float) -> dict:
    """Finish a DDP update; DeepSpeed already steps inside its boundary backward."""
    if not bool(getattr(accelerator, "sync_gradients", False)):
        raise PlanError("optimizer_step_without_sync_boundary")
    if _is_deepspeed(accelerator):
        return {"owner": "deepspeed_boundary_backward", "optimizer_step_skipped": False}
    if not isinstance(max_grad_norm, (int, float)) or max_grad_norm <= 0:
        raise PlanError("invalid_max_gradient_norm")
    norm = accelerator.clip_grad_norm_(model.parameters(), float(max_grad_norm))
    optimizer.step()
    skipped = bool(getattr(accelerator, "optimizer_step_was_skipped", False))
    optimizer.zero_grad(set_to_none=True)
    return {
        "owner": "adapter_non_deepspeed",
        "optimizer_step_skipped": skipped,
        "preclip_gradient_norm": float(norm.detach().cpu()),
    }
