"""In-memory token-plan -> scalar critic -> exact-update consumer.

No dataset/checkpoint readers, model loader, scheduler, launcher, or resume
admission. The caller owns input authorization, prepared model/optimizer,
distributed failure handling, and persistence. This is not a research entry.
Existing synthetic Trainer/checkpoint guards remain unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from types import SimpleNamespace

import torch

from phase1.global_local_accelerate_update_adapter import (
    backward_local_pair_mean, finish_non_deepspeed_update,
    planned_microbatch_context, runtime_binding,
    set_optimizer_learning_rate, update_learning_rate,
)
from phase1.global_local_batch_adapter import PackedBatch, observe_batch, pack_batch
from phase1.global_local_ds_completion import begin_deepspeed_update
from phase1.global_local_execution_plan import PlanError
from phase1.global_local_token_budget_plan import Plan
from phase1.verify_global_local_token_budget_plan import verify_plan


@dataclass(frozen=True)
class UpdateReceipt:
    plan_sha256: str
    rank: int
    completed_steps: int
    source: str
    cycle: int
    local_pair_visits: int
    local_valid_tokens: int
    global_update_pairs: int
    cumulative_global_valid_tokens: int
    learning_rate: float
    step_owner: str
    consumption: tuple


def pair_forward(model, ids, mask, signs):
    """Caller tensors use canonical A-half/B-half, never winner-first input."""
    if (not torch.is_grad_enabled() or not model.training
            or ids.dtype != torch.long or mask.dtype != torch.long
            or signs.dtype != torch.long or ids.ndim != 2
            or mask.shape != ids.shape or signs.ndim != 1
            or ids.shape[0] != 2 * signs.numel() or signs.numel() == 0
            or ids.device != mask.device or ids.device != signs.device
            or not bool(((signs == 1) | (signs == -1)).all())):
        raise PlanError('invalid_critic_training_batch')
    output = model(input_ids=ids, attention_mask=mask)
    if not isinstance(output, dict) or 'logits' not in output:
        raise PlanError('missing_critic_scalar_logits')
    scores = output['logits']
    # Pinned senior reward forward explicitly returns float32, including bf16.
    if (not isinstance(scores, torch.Tensor) or scores.dtype != torch.float32
            or scores.shape != (ids.shape[0],) or scores.device != ids.device
            or not scores.requires_grad or not bool(torch.isfinite(scores).all())):
        raise PlanError('invalid_critic_scalar_logits')
    n = signs.numel()
    loss = torch.nn.functional.softplus(-signs * (scores[:n] - scores[n:])).mean()
    if not bool(torch.isfinite(loss)):
        raise PlanError('nonfinite_critic_loss')
    return loss


class PlannedCriticConsumer:
    """Execute in strict order; exceptions poison this process-local consumer.

    Starts at zero only. A fresh object must NOT be used to retry partially
    mutated weights; restoring a complete checkpoint is a separate caller gate.
    A completed update is not a checkpoint or data-provenance certificate.
    """
    def __init__(self, *, plan, pools, accelerator, model, optimizer,
                 encoding_provider, true_sign, pad_id, max_grad_norm=1.0):
        if type(plan) is not Plan:
            raise PlanError('token_budget_plan_required')
        verify_plan(plan, *pools)
        self.runtime = runtime_binding()
        if (type(pad_id) is not int or pad_id < 0 or not callable(encoding_provider)
                or not callable(true_sign) or type(max_grad_norm) not in (float, int)
                or not math.isfinite(max_grad_norm) or max_grad_norm <= 0):
            raise PlanError('invalid_critic_consumer_configuration')
        rank = accelerator.process_index
        if (type(rank) is not int or not 0 <= rank < plan.shape.world_size
                or accelerator.num_processes != plan.shape.world_size
                or accelerator.gradient_accumulation_steps != plan.shape.accumulation
                or not isinstance(model, torch.nn.Module) or not model.training):
            raise PlanError('critic_consumer_topology_or_mode_mismatch')
        if getattr(accelerator, '_schedulers', None):
            raise PlanError('second_learning_rate_owner')
        optimizers = getattr(accelerator, '_optimizers', None)
        if not isinstance(optimizers, list) or len(optimizers) != 1 or optimizers[0] is not optimizer:
            raise PlanError('critic_optimizer_not_prepared')
        self.plan, self.accelerator = plan, accelerator
        self.model, self.optimizer = model, optimizer
        self.encoding_provider, self.true_sign = encoding_provider, true_sign
        self.pad_id, self.max_grad_norm, self.rank = pad_id, max_grad_norm, rank
        self.completed_steps, self.poisoned = 0, False
        self._deepspeed = str(accelerator.distributed_type).upper().endswith('DEEPSPEED')
        # Hash/verify once, not once per microbatch (quadratic in corpus size).
        self._view = SimpleNamespace(sha256=plan.sha256, arm=plan.arm, encoder=plan.encoder)
        updates = [[] for _ in range(plan.steps)]
        for batch in plan.batches:
            if batch.rank == rank:
                updates[batch.optimizer_step].append(batch)
        self._updates = tuple(tuple(batches) for batches in updates)

    def run_next_update(self):
        if self.poisoned:
            raise PlanError('consumer_failed_requires_external_checkpoint_restore')
        if self.completed_steps >= self.plan.steps:
            raise PlanError('plan_already_complete')
        try:
            return self._run_update()
        except BaseException:
            self.poisoned = True
            raise

    def _run_update(self):
        accelerator, model, optimizer = self.accelerator, self.model, self.optimizer
        if (accelerator.process_index != self.rank
                or accelerator.num_processes != self.plan.shape.world_size
                or accelerator.gradient_accumulation_steps != self.plan.shape.accumulation
                or not model.training or getattr(accelerator, '_schedulers', None)):
            raise PlanError('critic_consumer_configuration_drift')
        batches = self._updates[self.completed_steps]
        if not batches or tuple(b.micro_step for b in batches) != tuple(range(len(batches))):
            raise PlanError('invalid_consumer_update_sequence')
        lr = update_learning_rate(self.plan, batches, self.plan.peak_lr_decimal)
        before = (begin_deepspeed_update(accelerator, model, optimizer, max_grad_norm=self.max_grad_norm)
                  if self._deepspeed else None)
        set_optimizer_learning_rate(optimizer, lr)
        if not self._deepspeed:
            optimizer.zero_grad(set_to_none=True)
        receipts = []
        for index, batch in enumerate(batches):
            packed = pack_batch(self._view, batch, self.encoding_provider, self.true_sign, pad_id=self.pad_id)
            ids = torch.tensor(packed.input_ids, dtype=torch.long, device=accelerator.device)
            mask = torch.tensor(packed.attention_mask, dtype=torch.long, device=accelerator.device)
            signs = torch.tensor(packed.signs, dtype=torch.long, device=accelerator.device)
            # Observe the actual tensors given to the model, including padding.
            observed = PackedBatch(tuple(tuple(x) for x in ids.detach().cpu().tolist()),
                                   tuple(tuple(x) for x in mask.detach().cpu().tolist()),
                                   tuple(signs.detach().cpu().tolist()))
            receipt = observe_batch(self._view, batch, observed, self.true_sign, pad_id=self.pad_id)
            with planned_microbatch_context(accelerator, model, synchronize=index == len(batches) - 1):
                with accelerator.autocast():
                    loss = pair_forward(model, ids, mask, signs)
                backward_local_pair_mean(accelerator, loss, batch)
            receipts.append(receipt)
        finish = finish_non_deepspeed_update(accelerator, model, optimizer,
                                            max_grad_norm=self.max_grad_norm, deepspeed_before=before)
        # Do not advance a data/token cursor when an optimizer update was skipped.
        skipped = torch.tensor(int(finish['optimizer_step_skipped']), device=accelerator.device)
        if int(accelerator.reduce(skipped, reduction='sum').item()) != 0:
            raise PlanError('optimizer_update_skipped_cursor_not_committed')
        if sum(r.valid_tokens for r in receipts) != sum(b.valid_tokens for b in batches):
            raise PlanError('observed_update_token_mismatch')
        self.completed_steps += 1
        return UpdateReceipt(self._view.sha256, self.rank, self.completed_steps,
                             batches[0].source, batches[0].cycle,
                             sum(len(b.rows) for b in batches), sum(r.valid_tokens for r in receipts),
                             batches[0].update_real_pairs, batches[0].cumulative_valid_tokens_after_update,
                             lr, finish['owner'], tuple(receipts))
