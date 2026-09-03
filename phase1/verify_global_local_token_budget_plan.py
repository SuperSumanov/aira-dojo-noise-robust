"""Independent replay of the historical token-budget plan contract.

This module intentionally does not import ``global_local_token_budget_plan`` or
its helpers.  It accepts a plan object by duck typing, reconstructs ordering,
cycle-prefix stopping, partial DDP layout, loss normalization, LR progress, and
both plan hashes from the supplied source descriptors.
"""
from __future__ import annotations

from dataclasses import asdict
from fractions import Fraction
import hashlib
import itertools
import json
import math
import re


ARMS = {"L1", "Lbudget", "Gbudget", "G_to_L", "Ghash_to_L"}
VERSION = "global-local-token-budget-plan-v1"
LEGACY_ORDER_VERSION = "global-local-metadata-plan-v1"
HASH_LABEL_SEED = 20260823
PEAK_LR_DECIMAL = "0.00001"


class TokenPlanVerificationError(ValueError):
    pass


def _check(condition: bool, reason: str) -> None:
    if not condition:
        raise TokenPlanVerificationError(reason)


def _encoded(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _digest_records(records) -> str:
    digest = hashlib.sha256()
    for record in records:
        raw = _encoded(record)
        digest.update(len(raw).to_bytes(8, "big"))
        digest.update(raw)
    return digest.hexdigest()


def _pair_key(row) -> str:
    _check(row.a.card_id < row.b.card_id, "noncanonical_pair")
    key = _digest_records([(row.context_sha256, row.a.card_id, row.b.card_id)])
    _check(row.key == key, "pair_key_mismatch")
    return key


def _ordered(rows, source: str, seed: int):
    rows = tuple(rows)
    _check(bool(rows) and all(row.source == source for row in rows), "invalid_reference_pool")
    keys = [_pair_key(row) for row in rows]
    _check(len(set(keys)) == len(keys), "duplicate_reference_pair")
    keyed = [
        (_digest_records([(LEGACY_ORDER_VERSION, seed, source, key)]), row)
        for key, row in zip(keys, rows)
    ]
    _check(len({key for key, _ in keyed}) == len(keyed), "order_hash_collision")
    return tuple(row for _, row in sorted(keyed, key=lambda item: item[0]))


def _budget_segments(pool, token_cap: int):
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
            _check(visits <= 1_000_000, "plan_size_limit")
            if spent == token_cap:
                segments.append((pool[0].source, cycle, tuple(current)))
                return tuple(segments), None
        segments.append((pool[0].source, cycle, tuple(current)))
        cycle += 1
    raise AssertionError("unreachable_budget_loop_state")


def _raw_segments(arm, g, l, token_cap):
    if arm == "L1":
        return (("L", 0, l),), None
    if arm in ("G_to_L", "Ghash_to_L"):
        return (("G", 0, g), ("L", 0, l)), None
    return _budget_segments(l if arm == "Lbudget" else g, token_cap)


def _expected_layout(raw_segments, shape, warmup_tokens):
    expected_segments = []
    expected_batches = []
    step = 0
    cumulative = 0
    effective = shape.world_size * shape.pairs_per_rank * shape.accumulation
    for segment_index, (source, cycle, rows) in enumerate(raw_segments):
        start = step
        segment_tokens = sum(row.valid_tokens for row in rows)
        for offset in range(0, len(rows), effective):
            update = rows[offset:offset + effective]
            count = len(update)
            micros = math.ceil(count / (shape.world_size * shape.pairs_per_rank))
            _check(1 <= micros <= shape.accumulation, "invalid_partial_update_micro_steps")
            slots = micros * shape.world_size
            _check(count >= slots, "insufficient_rows_for_all_rank_participation")
            quotient, remainder = divmod(count, slots)
            sizes = [quotient + (slot < remainder) for slot in range(slots)]
            _check(min(sizes) >= 1 and max(sizes) <= shape.pairs_per_rank,
                   "invalid_balanced_partial_layout")
            update_tokens = sum(row.valid_tokens for row in update)
            cumulative += update_tokens
            cursor = 0
            for slot, size in enumerate(sizes):
                micro, rank = divmod(slot, shape.world_size)
                expected_batches.append({
                    "optimizer_step": step,
                    "segment_index": segment_index,
                    "source": source,
                    "cycle": cycle,
                    "micro_step": micro,
                    "rank": rank,
                    "rows": update[cursor:cursor + size],
                    "update_real_pairs": count,
                    "update_valid_tokens": update_tokens,
                    "loss_mean_scale_numerator": shape.world_size * size,
                    "loss_mean_scale_denominator": count,
                    "cumulative_valid_tokens_after_update": cumulative,
                    "lr_scale_numerator": min(cumulative, warmup_tokens),
                    "lr_scale_denominator": warmup_tokens,
                })
                cursor += size
            _check(cursor == count, "partial_layout_cursor_mismatch")
            step += 1
        expected_segments.append({
            "index": segment_index,
            "source": source,
            "cycle": cycle,
            "start_optimizer_step": start,
            "stop_optimizer_step": step,
            "pair_visits": len(rows),
            "valid_tokens": segment_tokens,
        })
    return expected_segments, expected_batches


def verify_plan(plan, global_rows, local_rows) -> dict:
    _check(plan.arm in ARMS, "invalid_arm")
    _check(type(plan.seed) is int and plan.seed >= 0, "invalid_seed")
    _check(re.fullmatch(r"[0-9a-f]{64}", plan.protocol_sha256) is not None,
           "invalid_protocol_sha256")
    shape = plan.shape
    _check(all(type(value) is int and value >= 1 for value in (
        shape.world_size, shape.pairs_per_rank, shape.accumulation
    )), "invalid_shape")
    g = _ordered(global_rows, "G", plan.seed)
    l = _ordered(local_rows, "L", plan.seed)
    _check(not ({_pair_key(row) for row in g} & {_pair_key(row) for row in l}),
           "reference_cross_source_overlap")
    seen_endpoints = {}
    for row in g + l:
        for endpoint in (row.a, row.b):
            _check(type(endpoint.valid_tokens) is int and 1 <= endpoint.valid_tokens <= plan.encoder.max_len,
                   "invalid_endpoint_tokens")
            _check(re.fullmatch(r"[0-9a-f]{64}", endpoint.encoded_sha256) is not None,
                   "invalid_endpoint_digest")
            key = (row.context_sha256, endpoint.card_id)
            _check(key not in seen_endpoints or seen_endpoints[key] == endpoint,
                   "inconsistent_endpoint_encoding")
            seen_endpoints[key] = endpoint
    pools_sha = _digest_records(asdict(row) for row in g + l)
    _check(plan.pools_sha256 == pools_sha, "reference_manifest_binding_mismatch")
    reference_pairs = len(g) + len(l)
    reference_tokens = sum(row.valid_tokens for row in g + l)
    warmup_tokens = (reference_tokens * 3 + 99) // 100
    _check(plan.reference_pair_visits == reference_pairs, "reference_pair_count_mismatch")
    _check(plan.reference_valid_tokens == reference_tokens, "reference_token_count_mismatch")
    _check(plan.warmup_valid_tokens == warmup_tokens, "warmup_token_count_mismatch")
    _check(plan.peak_lr_decimal == PEAK_LR_DECIMAL, "peak_lr_mismatch")
    raw_segments, next_tokens = _raw_segments(plan.arm, g, l, reference_tokens)
    _check(plan.budget_stop_next_pair_tokens == next_tokens, "budget_stop_receipt_mismatch")
    expected_segments, expected_batches = _expected_layout(raw_segments, shape, warmup_tokens)
    _check(len(plan.segments) == len(expected_segments), "segment_count_mismatch")
    for observed, expected in zip(plan.segments, expected_segments):
        _check(asdict(observed) == expected, "segment_layout_mismatch")
    _check(len(plan.batches) == len(expected_batches), "batch_count_mismatch")
    for observed, expected in zip(plan.batches, expected_batches):
        observed_dict = asdict(observed)
        expected_dict = dict(expected)
        expected_dict["rows"] = tuple(asdict(row) for row in expected_dict["rows"])
        observed_dict["rows"] = tuple(observed_dict["rows"])
        _check(observed_dict == expected_dict, "batch_layout_mismatch")

    # Independently check every update's all-rank participation and DDP mean.
    grouped = {}
    for batch in plan.batches:
        grouped.setdefault(batch.optimizer_step, []).append(batch)
    _check(set(grouped) == set(range(len(grouped))), "optimizer_step_gap")
    for step, rows in grouped.items():
        addresses = {(batch.micro_step, batch.rank) for batch in rows}
        micro_count = max(batch.micro_step for batch in rows) + 1
        _check(addresses == set(itertools.product(range(micro_count), range(shape.world_size))),
               "rank_participation_mismatch")
        _check(len({batch.source for batch in rows}) == 1, "mixed_source_optimizer_update")
        total_weight = sum(Fraction(
            batch.loss_mean_scale_numerator, batch.loss_mean_scale_denominator
        ) for batch in rows) / shape.world_size
        _check(total_weight == 1, "ddp_loss_normalization_mismatch")
        real_pairs = sum(len(batch.rows) for batch in rows)
        _check(real_pairs == rows[0].update_real_pairs, "update_pair_count_mismatch")
        _check(sum(batch.valid_tokens for batch in rows) == rows[0].update_valid_tokens,
               "update_token_count_mismatch")

    header = (
        VERSION,
        LEGACY_ORDER_VERSION,
        plan.seed,
        asdict(plan.shape),
        asdict(plan.encoder),
        plan.protocol_sha256,
        plan.pools_sha256,
        plan.reference_pair_visits,
        plan.reference_valid_tokens,
        plan.warmup_valid_tokens,
        plan.peak_lr_decimal,
        plan.budget_stop_next_pair_tokens,
    )
    input_sha = _digest_records(itertools.chain(
        (header,),
        (asdict(segment) for segment in plan.segments),
        (asdict(batch) for batch in plan.batches),
    ))
    _check(plan.input_sha256 == input_sha, "input_plan_hash_mismatch")
    plan_sha = _digest_records([(VERSION, plan.arm, HASH_LABEL_SEED, input_sha)])
    _check(plan.sha256 == plan_sha, "plan_hash_mismatch")

    planned_tokens = sum(segment.valid_tokens for segment in plan.segments)
    _check(planned_tokens <= reference_tokens, "token_budget_overshoot")
    if plan.arm in ("Lbudget", "Gbudget") and next_tokens is not None:
        _check(planned_tokens + next_tokens > reference_tokens,
               "budget_prefix_not_maximal")
    if plan.arm in ("G_to_L", "Ghash_to_L"):
        _check(planned_tokens == reference_tokens, "staged_budget_mismatch")
    return {
        "status": "PASS_INDEPENDENT_TOKEN_PLAN_REPLAY_EFFECT_NOT_AUTHORIZED",
        "arm": plan.arm,
        "seed": plan.seed,
        "optimizer_steps": len(grouped),
        "planned_pair_visits": sum(segment.pair_visits for segment in plan.segments),
        "planned_valid_tokens": planned_tokens,
        "plan_sha256": plan_sha,
        "model_fits": 0,
        "gpu_jobs": 0,
        "api_calls": 0,
    }


def verify_arm_relations(l1, lbudget, staged, hash_staged) -> dict:
    _check(staged.input_sha256 == hash_staged.input_sha256,
           "G_and_Ghash_input_mismatch")
    _check(staged.batches == hash_staged.batches and staged.segments == hash_staged.segments,
           "G_and_Ghash_schedule_mismatch")
    _check(lbudget.segments and l1.segments and lbudget.segments[0] == l1.segments[0],
           "L1_first_segment_mismatch")
    _check(lbudget.batches[:len(l1.batches)] == l1.batches,
           "L1_not_exact_Lbudget_prefix")
    return {
        "status": "PASS_CROSS_ARM_INPUT_RELATIONS",
        "G_and_Ghash_identical_inputs": True,
        "L1_exact_Lbudget_first_pass": True,
    }

