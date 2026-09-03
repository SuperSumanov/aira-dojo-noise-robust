"""Label-blind CPU planning primitives, NOT a Trainer or launch authorization.

No file readers, tokenizer/model imports, training, LR policy, or submission code.
The caller must separately establish provenance and permissions before supplying
real train metadata. The runnable demo uses synthetic descriptors only.

Conservative v1: require full optimizer batches at each G/L boundary and exact
whole-pair valid-token AND step matching. Unresolved cases raise; nothing is
dropped, padded with repeated examples, re-tokenized, or silently relaxed.
Metadata-derived padded slots are reported separately, never called FLOPs.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import itertools
import json
import math
import re
from typing import Callable, Sequence


ARMS = ("L1", "Lbudget", "Gbudget", "G_to_L", "Ghash_to_L")
HASH_LABEL_SEED = 20260823
MAX_PLANNED_PAIRS = 1_000_000
VERSION = "global-local-metadata-plan-v1"


class PlanError(ValueError):
    """Messages intentionally exclude candidate IDs and any supplied values."""


def _integer(value: int, minimum: int = 0) -> None:
    if type(value) is not int or value < minimum:
        raise PlanError("invalid_integer")


def _digest(value: str) -> None:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise PlanError("invalid_sha256")


def _encoded(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest_records(records) -> str:
    h = hashlib.sha256()
    for record in records:
        raw = _encoded(record)
        h.update(len(raw).to_bytes(8, "big"))
        h.update(raw)
    return h.hexdigest()


@dataclass(frozen=True)
class Endpoint:
    card_id: str
    valid_tokens: int
    encoded_sha256: str

    def __post_init__(self):
        if not isinstance(self.card_id, str) or not self.card_id or any(
            ord(c) < 32 for c in self.card_id
        ):
            raise PlanError("invalid_endpoint_id")
        _integer(self.valid_tokens, 1)
        _digest(self.encoded_sha256)


@dataclass(frozen=True)
class Pair:
    source: str
    a: Endpoint
    b: Endpoint
    context_sha256: str

    def __post_init__(self):
        if self.source not in ("G", "L"):
            raise PlanError("invalid_source")
        if not isinstance(self.a, Endpoint) or not isinstance(self.b, Endpoint):
            raise PlanError("invalid_endpoint")
        if self.a.card_id >= self.b.card_id:
            raise PlanError("endpoints_must_be_distinct_and_canonical")
        _digest(self.context_sha256)

    @classmethod
    def canonical(cls, source, left, right, context_sha256):
        a, b = sorted((left, right), key=lambda e: e.card_id)
        return cls(source, a, b, context_sha256)

    @property
    def key(self) -> str:
        # No true label, winner/loser ordering, or caller-provided row ID.
        return digest_records([(self.context_sha256, self.a.card_id, self.b.card_id)])

    @property
    def valid_tokens(self) -> int:
        return self.a.valid_tokens + self.b.valid_tokens


@dataclass(frozen=True)
class BatchShape:
    world_size: int
    pairs_per_rank: int
    accumulation: int

    def __post_init__(self):
        for n in (self.world_size, self.pairs_per_rank, self.accumulation):
            _integer(n, 1)

    @property
    def effective_pairs(self) -> int:
        return self.world_size * self.pairs_per_rank * self.accumulation


@dataclass(frozen=True)
class EncoderBinding:
    tokenizer_sha256: str
    serialization_sha256: str
    max_len: int

    def __post_init__(self):
        _digest(self.tokenizer_sha256)
        _digest(self.serialization_sha256)
        _integer(self.max_len, 1)


@dataclass(frozen=True)
class Batch:
    optimizer_step: int  # zero-based update being accumulated
    micro_step: int
    rank: int
    rows: tuple[Pair, ...]

    @property
    def valid_tokens(self) -> int:
        return sum(row.valid_tokens for row in self.rows)

    @property
    def padded_slots(self) -> int:
        return 2 * len(self.rows) * max(
            max(row.a.valid_tokens, row.b.valid_tokens) for row in self.rows
        )


@dataclass(frozen=True)
class Plan:
    arm: str
    seed: int
    shape: BatchShape
    encoder: EncoderBinding
    protocol_sha256: str
    pools_sha256: str
    reference_steps: int
    reference_valid_tokens: int
    reference_padded_slots: int
    batches: tuple[Batch, ...]

    @property
    def steps(self):
        return len(self.batches) // (self.shape.world_size * self.shape.accumulation)

    @property
    def input_sha256(self):
        # Deliberately excludes arm/target rule: G and Ghash inputs must match.
        header = (VERSION, self.seed, asdict(self.shape), asdict(self.encoder),
                  self.protocol_sha256, self.pools_sha256)
        return digest_records(itertools.chain((header,), (asdict(b) for b in self.batches)))

    @property
    def sha256(self):
        return digest_records([(VERSION, self.arm, HASH_LABEL_SEED, self.input_sha256,
                                self.reference_steps, self.reference_valid_tokens,
                                self.reference_padded_slots)])

    def summary(self):
        valid = sum(b.valid_tokens for b in self.batches)
        padded = sum(b.padded_slots for b in self.batches)
        return {
            "status": "METADATA_PLAN_ONLY_NOT_TRAINING_READY", "arm": self.arm,
            "seed": self.seed, "plan_sha256": self.sha256,
            "input_sha256": self.input_sha256, "optimizer_steps": self.steps,
            "planned_pair_visits": sum(len(b.rows) for b in self.batches),
            "planned_valid_tokens": valid, "planned_padded_slots": padded,
            "reference_steps": self.reference_steps,
            "reference_valid_tokens": self.reference_valid_tokens,
            "reference_padded_slots": self.reference_padded_slots,
            "valid_and_steps_match_reference": (valid == self.reference_valid_tokens
                                                and self.steps == self.reference_steps),
            "padded_slots_match_reference": padded == self.reference_padded_slots,
            "actual_compute_matched": None, "training_authorized": False,
            "trainer_integrated": False, "lr_contract_resolved": False,
        }


def endpoint_utility(card_id: str) -> int:
    return int.from_bytes(hashlib.sha256(
        (str(HASH_LABEL_SEED) + "|" + card_id).encode("utf-8")
    ).digest(), "big")


def hash_sign(pair: Pair) -> int:
    a, b = endpoint_utility(pair.a.card_id), endpoint_utility(pair.b.card_id)
    if a == b:
        raise PlanError("endpoint_hash_collision")
    return 1 if a > b else -1


def targets(arm: str, batch: Batch, true_sign: Callable[[str], int]) -> tuple[int, ...]:
    """Separate labels from inputs; hash-global never calls the truth provider."""
    if arm not in ARMS:
        raise PlanError("invalid_arm")
    values = []
    for row in batch.rows:
        y = hash_sign(row) if arm == "Ghash_to_L" and row.source == "G" else true_sign(row.key)
        if type(y) is not int or y not in (-1, 1):
            raise PlanError("invalid_target_sign")
        values.append(y)
    return tuple(values)


def bt_loss_and_gradient(score_a: float, score_b: float, sign: int):
    """Scalar CPU oracle for future adapter tests; never performs a model fit."""
    if type(sign) is not int or sign not in (-1, 1):
        raise PlanError("invalid_target_sign")
    if not all(math.isfinite(x) for x in (score_a, score_b)):
        raise PlanError("nonfinite_score")
    z = sign * (score_a - score_b)
    if not math.isfinite(z):
        raise PlanError("nonfinite_margin")
    loss = max(-z, 0.0) + math.log1p(math.exp(-abs(z)))
    p = math.exp(-z) / (1.0 + math.exp(-z)) if z >= 0 else 1.0 / (1.0 + math.exp(z))
    grad_a = -sign * p
    return loss, grad_a, -grad_a


def _ordered_pool(rows, source, seed):
    if not rows or any(not isinstance(r, Pair) or r.source != source for r in rows):
        raise PlanError("empty_or_mixed_pool")
    if len({r.key for r in rows}) != len(rows):
        raise PlanError("duplicate_unordered_pair")
    keyed = [(digest_records([(VERSION, seed, source, r.key)]), r) for r in rows]
    if len({k for k, _ in keyed}) != len(keyed):
        raise PlanError("order_hash_collision")
    return tuple(row for _, row in sorted(keyed, key=lambda x: x[0]))


def _cycle_exact(pool, target):
    cycles, remainder = divmod(target, sum(r.valid_tokens for r in pool))
    prefix = []
    for row in pool:
        if not remainder:
            break
        remainder -= row.valid_tokens
        if remainder < 0:
            raise PlanError("whole_pair_token_budget_unreachable")
        prefix.append(row)
    if remainder:
        raise PlanError("whole_pair_token_budget_unreachable")
    if cycles * len(pool) + len(prefix) > MAX_PLANNED_PAIRS:
        raise PlanError("plan_size_limit")
    return pool * cycles + tuple(prefix)


def _batches(rows, shape):
    if len(rows) % shape.effective_pairs:
        raise PlanError("partial_optimizer_batch_policy_unresolved")
    result = []
    for offset in range(0, len(rows), shape.effective_pairs):
        for micro in range(shape.accumulation):
            for rank in range(shape.world_size):
                start = offset + (micro * shape.world_size + rank) * shape.pairs_per_rank
                result.append(Batch(offset // shape.effective_pairs, micro, rank,
                                    rows[start:start + shape.pairs_per_rank]))
    return tuple(result)


def build_plan(arm: str, global_rows: Sequence[Pair], local_rows: Sequence[Pair], *,
               seed: int, shape: BatchShape, encoder: EncoderBinding,
               protocol_sha256: str) -> Plan:
    if arm not in ARMS:
        raise PlanError("invalid_arm")
    _integer(seed)
    _digest(protocol_sha256)
    if not isinstance(shape, BatchShape) or not isinstance(encoder, EncoderBinding):
        raise PlanError("invalid_binding")
    if len(global_rows) + len(local_rows) > MAX_PLANNED_PAIRS:
        raise PlanError("plan_size_limit")
    g = _ordered_pool(global_rows, "G", seed)
    l = _ordered_pool(local_rows, "L", seed)
    if {r.key for r in g} & {r.key for r in l}:
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
    if any(len(pool) % shape.effective_pairs for pool in (g, l)):
        raise PlanError("phase_boundary_policy_unresolved")
    if arm == "Ghash_to_L":
        ids = {e.card_id for row in g for e in (row.a, row.b)}
        if len({endpoint_utility(i) for i in ids}) != len(ids):
            raise PlanError("endpoint_hash_collision")
    reference = _batches(g + l, shape)
    ref_valid = sum(b.valid_tokens for b in reference)
    ref_steps = len(g + l) // shape.effective_pairs
    if arm == "L1":
        rows = l
    elif arm in ("Lbudget", "Gbudget"):
        rows = _cycle_exact(l if arm == "Lbudget" else g, ref_valid)
    else:
        rows = g + l
    batches = _batches(rows, shape)
    if arm != "L1" and len(rows) // shape.effective_pairs != ref_steps:
        raise PlanError("exact_valid_tokens_but_optimizer_steps_mismatch")
    return Plan(arm, seed, shape, encoder, protocol_sha256,
                digest_records(asdict(r) for r in g + l), ref_steps, ref_valid,
                sum(b.padded_slots for b in reference), batches)


@dataclass(frozen=True)
class ResumeCursor:
    plan_sha256: str
    completed_optimizer_steps: int

    def __post_init__(self):
        _digest(self.plan_sha256)
        _integer(self.completed_optimizer_steps)


def remaining_batches(plan: Plan, cursor: ResumeCursor) -> tuple[Batch, ...]:
    """Plan slicing only; optimizer/scheduler/RNG state is NOT restored here."""
    if cursor.plan_sha256 != plan.sha256:
        raise PlanError("resume_plan_binding_mismatch")
    if cursor.completed_optimizer_steps > plan.steps:
        raise PlanError("resume_step_out_of_range")
    return tuple(b for b in plan.batches if b.optimizer_step >= cursor.completed_optimizer_steps)


def demo_plans():
    def h(value):
        return hashlib.sha256(value.encode()).hexdigest()
    def rows(source, n):
        return tuple(Pair.canonical(source,
            Endpoint(f"synthetic:{source}:{i}:a", 3, h(f"input:{source}:{i}:a")),
            Endpoint(f"synthetic:{source}:{i}:b", 5, h(f"input:{source}:{i}:b")),
            h("synthetic:context")) for i in range(n))
    g, l = rows("G", 16), rows("L", 8)
    for seed in (6, 7, 8):
        for arm in ARMS:
            yield build_plan(arm, g, l, seed=seed, shape=BatchShape(2, 2, 2),
                encoder=EncoderBinding(h("synthetic:tokenizer"), h("synthetic:serializer"), 8),
                protocol_sha256=h("synthetic:protocol-binding-not-the-real-protocol"))


if __name__ == "__main__":
    print(json.dumps({"synthetic_only": True, "model_fits": 0, "gpu_jobs": 0,
                      "plans": [p.summary() for p in demo_plans()]}, sort_keys=True))
