"""Independent consumer-side metadata trace check, not a training verifier.

Expects receipts from the point of consumption, NOT generated plans presented as
observations. Tests use explicitly synthetic receipts. A future Trainer adapter
must compute encoder hashes/counts at its actual batch boundary and separately
verify saved model/optimizer/scheduler/RNG state. This module never reads data.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Sequence

from phase1.global_local_execution_plan import (
    ARMS, VERSION, Plan, PlanError, ResumeCursor, digest_records,
)


@dataclass(frozen=True)
class BatchReceipt:
    plan_sha256: str
    optimizer_step: int
    micro_step: int
    rank: int
    pair_keys: tuple[str, ...]
    encoded_digests: tuple[tuple[str, str], ...]
    valid_tokens: int
    padded_slots: int


def verify_layout(plan: Plan):
    """Check layout/budgets independently of the builder's batching functions.

    Does not attest that the supplied pool digest came from authorized data.
    Authentic source manifests and seed-order replay remain caller obligations.
    """
    shape = plan.shape
    stride = shape.world_size * shape.accumulation
    if plan.arm not in ARMS or not plan.batches or len(plan.batches) % stride:
        raise PlanError("invalid_plan_layout")
    if any(type(x) is not int or x <= 0 for x in (
        plan.reference_steps, plan.reference_valid_tokens, plan.reference_padded_slots
    )):
        raise PlanError("invalid_reference_budget")
    global_keys, local_keys = [], []
    valid, padded = 0, 0
    local_started = False
    sources_per_update = {}
    for index, batch in enumerate(plan.batches):
        update, within = divmod(index, stride)
        micro, rank = divmod(within, shape.world_size)
        if (batch.optimizer_step, batch.micro_step, batch.rank) != (update, micro, rank):
            raise PlanError("invalid_plan_address_order")
        if any(type(x) is not int for x in (batch.optimizer_step, batch.micro_step, batch.rank)):
            raise PlanError("invalid_plan_address_type")
        if len(batch.rows) != shape.pairs_per_rank:
            raise PlanError("partial_plan_microbatch")
        counts = []
        for row in batch.rows:
            sources_per_update.setdefault(update, set()).add(row.source)
            if row.source == "L":
                local_started = True
                local_keys.append(row.key)
            else:
                global_keys.append(row.key)
                if local_started and plan.arm in ("G_to_L", "Ghash_to_L"):
                    raise PlanError("global_after_local_in_plan")
            counts.extend((row.a.valid_tokens, row.b.valid_tokens))
        if max(counts) > plan.encoder.max_len:
            raise PlanError("plan_over_context")
        valid += sum(counts)
        padded += len(counts) * max(counts)
    if any(len(sources) != 1 for sources in sources_per_update.values()):
        raise PlanError("mixed_source_optimizer_update")
    if plan.arm in ("G_to_L", "Ghash_to_L"):
        if (not global_keys or not local_keys or len(set(global_keys)) != len(global_keys)
                or len(set(local_keys)) != len(local_keys)):
            raise PlanError("staged_exactly_once_violation")
        if set(global_keys) & set(local_keys):
            raise PlanError("cross_source_pair_overlap")
        if padded != plan.reference_padded_slots:
            raise PlanError("reference_padding_mismatch")
    elif plan.arm in ("L1", "Lbudget") and global_keys:
        raise PlanError("wrong_source_in_local_arm")
    elif plan.arm == "Gbudget" and local_keys:
        raise PlanError("wrong_source_in_global_arm")
    if plan.arm == "L1":
        if len(set(local_keys)) != len(local_keys):
            raise PlanError("local_once_violation")
        if len(plan.batches) // stride >= plan.reference_steps or valid >= plan.reference_valid_tokens:
            raise PlanError("invalid_local_once_budget")
    elif len(plan.batches) // stride != plan.reference_steps or valid != plan.reference_valid_tokens:
        raise PlanError("reference_budget_mismatch")


def verify_plan(plan: Plan, global_rows, local_rows):
    """Replay source metadata independently: no build_plan/_cycle_exact/_batches.

    Hash encoding is the shared wire format, not the scheduling implementation.
    Verifies supplied metadata, not its authorization/provenance or tokenization.
    """
    verify_layout(plan)
    ordered = []
    for source, rows in (("G", global_rows), ("L", local_rows)):
        if not rows or any(r.source != source for r in rows):
            raise PlanError("invalid_reference_pool")
        if len({r.key for r in rows}) != len(rows):
            raise PlanError("duplicate_reference_pair")
        ordered.append(tuple(sorted(rows, key=lambda r: digest_records([
            (VERSION, plan.seed, source, r.key)
        ]))))
    g, l = ordered
    if {r.key for r in g} & {r.key for r in l}:
        raise PlanError("reference_cross_source_overlap")
    if any(len(pool) % plan.shape.effective_pairs for pool in (g, l)):
        raise PlanError("reference_phase_not_aligned")
    reference = g + l
    if digest_records(asdict(r) for r in reference) != plan.pools_sha256:
        raise PlanError("reference_manifest_binding_mismatch")
    if plan.reference_steps != len(reference) // plan.shape.effective_pairs:
        raise PlanError("reference_step_count_mismatch")
    if plan.reference_valid_tokens != sum(r.valid_tokens for r in reference):
        raise PlanError("reference_valid_count_mismatch")
    width = plan.shape.pairs_per_rank
    independent_padding = sum(
        2 * width * max(e.valid_tokens for r in reference[i:i + width] for e in (r.a, r.b))
        for i in range(0, len(reference), width)
    )
    if plan.reference_padded_slots != independent_padding:
        raise PlanError("reference_padded_count_mismatch")
    if plan.arm == "L1":
        expected = l
    elif plan.arm in ("G_to_L", "Ghash_to_L"):
        expected = reference
    else:
        pool = l if plan.arm == "Lbudget" else g
        # Common steps and batch fix the visit count. Check token equality after
        # modular indexing, independent of the builder's quotient/remainder rule.
        expected = tuple(pool[i % len(pool)] for i in range(len(reference)))
    observed = tuple(r for b in plan.batches for r in b.rows)
    if observed != expected:
        raise PlanError("seeded_source_schedule_mismatch")


def verify_prefix(plan: Plan, receipts: Sequence[BatchReceipt], *, completed_steps: int):
    verify_layout(plan)
    if type(completed_steps) is not int or not 0 <= completed_steps <= plan.steps:
        raise PlanError("invalid_completed_steps")
    expected = { (b.optimizer_step, b.micro_step, b.rank): b for b in plan.batches
                 if b.optimizer_step < completed_steps }
    if len(receipts) != len(expected):
        raise PlanError("missing_or_extra_batch_receipts")
    seen = set()
    last_per_rank = {}
    plan_hash = plan.sha256
    for event in receipts:
        address = (event.optimizer_step, event.micro_step, event.rank)
        if any(type(n) is not int or n < 0 for n in address):
            raise PlanError("invalid_receipt_address")
        if event.plan_sha256 != plan_hash:
            raise PlanError("receipt_plan_binding_mismatch")
        if address not in expected or address in seen:
            raise PlanError("unknown_or_duplicate_batch")
        if address[:2] <= last_per_rank.get(event.rank, (-1, -1)):
            raise PlanError("per_rank_consumption_order_mismatch")
        batch = expected[address]
        if event.pair_keys != tuple(row.key for row in batch.rows):
            raise PlanError("consumed_pair_order_mismatch")
        encodings = tuple((row.a.encoded_sha256, row.b.encoded_sha256) for row in batch.rows)
        if event.encoded_digests != encodings:
            raise PlanError("consumed_encoding_order_mismatch")
        # Recompute directly from descriptors, not the builder's count helpers.
        counts = [e.valid_tokens for row in batch.rows for e in (row.a, row.b)]
        if (type(event.valid_tokens) is not int or type(event.padded_slots) is not int
                or event.valid_tokens != sum(counts)
                or event.padded_slots != len(counts) * max(counts)):
            raise PlanError("consumed_budget_mismatch")
        seen.add(address)
        last_per_rank[event.rank] = address[:2]
    if seen != set(expected):
        raise PlanError("incomplete_consumption")
    return ResumeCursor(plan_hash, completed_steps)
