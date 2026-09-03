"""Approved historical-development token-budget plans; never launches training.

This is a successor to the deliberately conservative metadata planner in
``global_local_execution_plan.py``.  That v1 planner remains unchanged.  The
successor preserves whole pairs and source/cycle boundaries, allows a terminal
optimizer update smaller than the nominal effective batch, and exposes the
exact DDP loss-normalization fraction required for that update.

The module has no readers, tokenizer/model imports, CLI, or submission path.
Callers must separately establish source provenance and effect authorization.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import itertools
import math
import re
from typing import Sequence

from phase1.global_local_execution_plan import (
    ARMS,
    HASH_LABEL_SEED,
    MAX_PLANNED_PAIRS,
    VERSION as LEGACY_ORDER_VERSION,
    BatchShape,
    EncoderBinding,
    Pair,
    PlanError,
    ResumeCursor,
    digest_records,
    endpoint_utility,
)


VERSION = "global-local-token-budget-plan-v1"
PEAK_LR_DECIMAL = "0.00001"
WARMUP_NUMERATOR = 3
WARMUP_DENOMINATOR = 100


@dataclass(frozen=True)
class Segment:
    index: int
    source: str
    cycle: int
    start_optimizer_step: int
    stop_optimizer_step: int  # exclusive
    pair_visits: int
    valid_tokens: int


@dataclass(frozen=True)
class Batch:
    optimizer_step: int
    segment_index: int
    source: str
    cycle: int
    micro_step: int
    rank: int
    rows: tuple[Pair, ...]
    update_real_pairs: int
    update_valid_tokens: int
    # If each local microbatch loss is a mean, multiply it by this fraction.
    # DDP's rank mean then equals the mean over all real pairs in the update.
    loss_mean_scale_numerator: int
    loss_mean_scale_denominator: int
    cumulative_valid_tokens_after_update: int
    lr_scale_numerator: int
    lr_scale_denominator: int

    @property
    def valid_tokens(self) -> int:
        return sum(row.valid_tokens for row in self.rows)

    @property
    def padded_slots(self) -> int:
        width = max(endpoint.valid_tokens for row in self.rows for endpoint in (row.a, row.b))
        return 2 * len(self.rows) * width


@dataclass(frozen=True)
class Plan:
    arm: str
    seed: int
    shape: BatchShape
    encoder: EncoderBinding
    protocol_sha256: str
    pools_sha256: str
    reference_pair_visits: int
    reference_valid_tokens: int
    warmup_valid_tokens: int
    peak_lr_decimal: str
    budget_stop_next_pair_tokens: int | None
    segments: tuple[Segment, ...]
    batches: tuple[Batch, ...]

    @property
    def steps(self) -> int:
        return 0 if not self.batches else self.batches[-1].optimizer_step + 1

    @property
    def planned_pair_visits(self) -> int:
        return sum(segment.pair_visits for segment in self.segments)

    @property
    def planned_valid_tokens(self) -> int:
        return sum(segment.valid_tokens for segment in self.segments)

    @property
    def input_sha256(self) -> str:
        # Arm is deliberately excluded: G_to_L and Ghash_to_L must match here.
        header = (
            VERSION,
            LEGACY_ORDER_VERSION,
            self.seed,
            asdict(self.shape),
            asdict(self.encoder),
            self.protocol_sha256,
            self.pools_sha256,
            self.reference_pair_visits,
            self.reference_valid_tokens,
            self.warmup_valid_tokens,
            self.peak_lr_decimal,
            self.budget_stop_next_pair_tokens,
        )
        return digest_records(itertools.chain(
            (header,),
            (asdict(segment) for segment in self.segments),
            (asdict(batch) for batch in self.batches),
        ))

    @property
    def sha256(self) -> str:
        return digest_records([(VERSION, self.arm, HASH_LABEL_SEED, self.input_sha256)])

    def summary(self) -> dict:
        updates = {batch.optimizer_step: batch.update_real_pairs for batch in self.batches}
        planned_tokens = self.planned_valid_tokens
        shortfall = self.reference_valid_tokens - planned_tokens
        return {
            "status": "APPROVED_METADATA_PLAN_EFFECT_TRAINING_BLOCKED",
            "arm": self.arm,
            "seed": self.seed,
            "plan_sha256": self.sha256,
            "input_sha256": self.input_sha256,
            "optimizer_steps": self.steps,
            "planned_pair_visits": self.planned_pair_visits,
            "planned_valid_tokens": planned_tokens,
            "token_budget_shortfall": shortfall,
            "budget_stop_next_pair_tokens": self.budget_stop_next_pair_tokens,
            "planned_padded_slots": sum(batch.padded_slots for batch in self.batches),
            "partial_optimizer_updates": sum(
                count < self.shape.effective_pairs for count in updates.values()
            ),
            "reference_pair_visits": self.reference_pair_visits,
            "reference_valid_tokens": self.reference_valid_tokens,
            "warmup_valid_tokens": self.warmup_valid_tokens,
            "peak_lr_decimal": self.peak_lr_decimal,
            "lr_rule": "peak*min(1,cumulative_valid_tokens_after_update/warmup_valid_tokens)",
            "phase_or_cycle_boundary_is_optimizer_boundary": True,
            "real_pair_padding_or_drop": False,
            "all_ranks_participate_each_micro_step": True,
            "actual_compute_matched": None,
            "training_authorized": False,
            "trainer_integrated": False,
        }


def _ordered_pool(rows: Sequence[Pair], source: str, seed: int) -> tuple[Pair, ...]:
    if not rows or any(not isinstance(row, Pair) or row.source != source for row in rows):
        raise PlanError("empty_or_mixed_pool")
    if len({row.key for row in rows}) != len(rows):
        raise PlanError("duplicate_unordered_pair")
    keyed = [
        (digest_records([(LEGACY_ORDER_VERSION, seed, source, row.key)]), row)
        for row in rows
    ]
    if len({key for key, _ in keyed}) != len(keyed):
        raise PlanError("order_hash_collision")
    return tuple(row for _, row in sorted(keyed, key=lambda item: item[0]))


def _validate_inputs(g: tuple[Pair, ...], l: tuple[Pair, ...], encoder: EncoderBinding) -> None:
    if {row.key for row in g} & {row.key for row in l}:
        raise PlanError("cross_source_pair_overlap_policy_unresolved")
    seen = {}
    for row in g + l:
        for endpoint in (row.a, row.b):
            if endpoint.valid_tokens > encoder.max_len:
                raise PlanError("over_context_no_automatic_truncation")
            key = (row.context_sha256, endpoint.card_id)
            if key in seen and seen[key] != endpoint:
                raise PlanError("inconsistent_endpoint_encoding")
            seen[key] = endpoint


def _budget_segments(pool: tuple[Pair, ...], token_cap: int):
    segments = []
    spent = 0
    cycle = 0
    visits = 0
    while spent < token_cap:
        current = []
        for row in pool:
            if spent + row.valid_tokens > token_cap:
                if current:
                    segments.append((pool[0].source, cycle, tuple(current)))
                return tuple(segments), row.valid_tokens
            current.append(row)
            spent += row.valid_tokens
            visits += 1
            if visits > MAX_PLANNED_PAIRS:
                raise PlanError("plan_size_limit")
            if spent == token_cap:
                segments.append((pool[0].source, cycle, tuple(current)))
                return tuple(segments), None
        segments.append((pool[0].source, cycle, tuple(current)))
        cycle += 1
    raise AssertionError("unreachable_budget_loop_state")


def _arm_segments(arm: str, g: tuple[Pair, ...], l: tuple[Pair, ...], token_cap: int):
    if arm == "L1":
        return (("L", 0, l),), None
    if arm in ("G_to_L", "Ghash_to_L"):
        return (("G", 0, g), ("L", 0, l)), None
    return _budget_segments(l if arm == "Lbudget" else g, token_cap)


def _layout(raw_segments, shape: BatchShape, warmup_tokens: int):
    segments = []
    batches = []
    optimizer_step = 0
    cumulative_tokens = 0
    for segment_index, (source, cycle, rows) in enumerate(raw_segments):
        start_step = optimizer_step
        segment_tokens = sum(row.valid_tokens for row in rows)
        for offset in range(0, len(rows), shape.effective_pairs):
            update_rows = rows[offset:offset + shape.effective_pairs]
            real_pairs = len(update_rows)
            micro_steps = math.ceil(real_pairs / (shape.world_size * shape.pairs_per_rank))
            if not 1 <= micro_steps <= shape.accumulation:
                raise PlanError("invalid_partial_update_micro_steps")
            slots = micro_steps * shape.world_size
            if real_pairs < slots:
                # This protocol never invents a real-data repeat or a synthetic
                # placeholder.  A future adapter may add an independently tested
                # zero-loss placeholder policy under a successor protocol.
                raise PlanError("insufficient_rows_for_all_rank_participation")
            quotient, remainder = divmod(real_pairs, slots)
            counts = tuple(quotient + (slot < remainder) for slot in range(slots))
            if min(counts) < 1 or max(counts) > shape.pairs_per_rank or sum(counts) != real_pairs:
                raise PlanError("invalid_balanced_partial_layout")
            update_tokens = sum(row.valid_tokens for row in update_rows)
            cumulative_tokens += update_tokens
            lr_numerator = min(cumulative_tokens, warmup_tokens)
            cursor = 0
            for slot, count in enumerate(counts):
                micro_step, rank = divmod(slot, shape.world_size)
                assigned = update_rows[cursor:cursor + count]
                cursor += count
                batches.append(Batch(
                    optimizer_step=optimizer_step,
                    segment_index=segment_index,
                    source=source,
                    cycle=cycle,
                    micro_step=micro_step,
                    rank=rank,
                    rows=assigned,
                    update_real_pairs=real_pairs,
                    update_valid_tokens=update_tokens,
                    loss_mean_scale_numerator=shape.world_size * count,
                    loss_mean_scale_denominator=real_pairs,
                    cumulative_valid_tokens_after_update=cumulative_tokens,
                    lr_scale_numerator=lr_numerator,
                    lr_scale_denominator=warmup_tokens,
                ))
            if cursor != real_pairs:
                raise AssertionError("partial_layout_cursor_mismatch")
            optimizer_step += 1
        segments.append(Segment(
            index=segment_index,
            source=source,
            cycle=cycle,
            start_optimizer_step=start_step,
            stop_optimizer_step=optimizer_step,
            pair_visits=len(rows),
            valid_tokens=segment_tokens,
        ))
    return tuple(segments), tuple(batches)


def build_plan(
    arm: str,
    global_rows: Sequence[Pair],
    local_rows: Sequence[Pair],
    *,
    seed: int,
    shape: BatchShape,
    encoder: EncoderBinding,
    protocol_sha256: str,
    token_cap: int | None = None,
) -> Plan:
    if arm not in ARMS:
        raise PlanError("invalid_arm")
    if type(seed) is not int or seed < 0:
        raise PlanError("invalid_integer")
    if not isinstance(shape, BatchShape) or not isinstance(encoder, EncoderBinding):
        raise PlanError("invalid_binding")
    if not isinstance(protocol_sha256, str) or re.fullmatch(r"[0-9a-f]{64}", protocol_sha256) is None:
        raise PlanError("invalid_sha256")
    if len(global_rows) + len(local_rows) > MAX_PLANNED_PAIRS:
        raise PlanError("plan_size_limit")
    g = _ordered_pool(tuple(global_rows), "G", seed)
    l = _ordered_pool(tuple(local_rows), "L", seed)
    _validate_inputs(g, l, encoder)
    reference_tokens = sum(row.valid_tokens for row in g + l)
    reference_pairs = len(g) + len(l)
    if token_cap is None:
        token_cap = reference_tokens
    if type(token_cap) is not int or token_cap <= 0 or token_cap != reference_tokens:
        raise PlanError("token_cap_must_equal_once_through_G_plus_L")
    warmup_tokens = (
        token_cap * WARMUP_NUMERATOR + WARMUP_DENOMINATOR - 1
    ) // WARMUP_DENOMINATOR
    raw_segments, next_pair_tokens = _arm_segments(arm, g, l, token_cap)
    segments, batches = _layout(raw_segments, shape, warmup_tokens)
    if arm == "Ghash_to_L":
        endpoint_ids = {endpoint.card_id for row in g for endpoint in (row.a, row.b)}
        if len({endpoint_utility(card_id) for card_id in endpoint_ids}) != len(endpoint_ids):
            raise PlanError("endpoint_hash_collision")
    return Plan(
        arm=arm,
        seed=seed,
        shape=shape,
        encoder=encoder,
        protocol_sha256=protocol_sha256,
        pools_sha256=digest_records(asdict(row) for row in g + l),
        reference_pair_visits=reference_pairs,
        reference_valid_tokens=reference_tokens,
        warmup_valid_tokens=warmup_tokens,
        peak_lr_decimal=PEAK_LR_DECIMAL,
        budget_stop_next_pair_tokens=next_pair_tokens,
        segments=segments,
        batches=batches,
    )


def remaining_batches(plan: Plan, cursor: ResumeCursor) -> tuple[Batch, ...]:
    if cursor.plan_sha256 != plan.sha256:
        raise PlanError("resume_plan_binding_mismatch")
    if type(cursor.completed_optimizer_steps) is not int or not 0 <= cursor.completed_optimizer_steps <= plan.steps:
        raise PlanError("resume_step_out_of_range")
    return tuple(batch for batch in plan.batches
                 if batch.optimizer_step >= cursor.completed_optimizer_steps)
