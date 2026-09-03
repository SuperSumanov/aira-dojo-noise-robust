from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
import hashlib

import pytest

from phase1 import global_local_execution_plan as legacy
from phase1 import global_local_token_budget_plan as plan
from phase1 import verify_global_local_token_budget_plan as verifier


def h(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def row(source: str, index: int, lengths=(3, 5), *, context="task"):
    return legacy.Pair.canonical(
        source,
        legacy.Endpoint(f"synthetic:{source}:{index}:a", lengths[0], h(f"{source}:{index}:a:{lengths[0]}")),
        legacy.Endpoint(f"synthetic:{source}:{index}:b", lengths[1], h(f"{source}:{index}:b:{lengths[1]}")),
        h(context),
    )


def build(arm="G_to_L", *, seed=6, g=None, l=None, shape=None):
    g = tuple(g) if g is not None else tuple(row("G", i) for i in range(10))
    l = tuple(l) if l is not None else tuple(row("L", i) for i in range(7))
    return plan.build_plan(
        arm,
        g,
        l,
        seed=seed,
        shape=shape or legacy.BatchShape(2, 2, 2),
        encoder=legacy.EncoderBinding(h("tokenizer"), h("serializer"), 8),
        protocol_sha256=h("historical-development-v1"),
    )


def flattened(value):
    return tuple(row for segment in value.segments
                 for batch in value.batches
                 if batch.segment_index == segment.index
                 for row in batch.rows)


@pytest.mark.parametrize("seed", [6, 7, 8])
def test_all_arms_replay_and_cross_arm_relations(seed):
    g = tuple(row("G", i) for i in range(10))
    l = tuple(row("L", i) for i in range(7))
    plans = {arm: build(arm, seed=seed, g=g, l=l) for arm in legacy.ARMS}
    for value in plans.values():
        receipt = verifier.verify_plan(value, g, l)
        assert receipt["status"] == "PASS_INDEPENDENT_TOKEN_PLAN_REPLAY_EFFECT_NOT_AUTHORIZED"
        assert not value.summary()["training_authorized"]
        assert value.reference_pair_visits == 17
        assert value.reference_valid_tokens == 136
        assert all(batch.rows for batch in value.batches)
    relation = verifier.verify_arm_relations(
        plans["L1"], plans["Lbudget"], plans["G_to_L"], plans["Ghash_to_L"]
    )
    assert relation["L1_exact_Lbudget_first_pass"]
    assert plans["G_to_L"].sha256 != plans["Ghash_to_L"].sha256
    assert plans["L1"].planned_pair_visits == 7
    assert plans["Lbudget"].planned_pair_visits == 17
    assert plans["Gbudget"].planned_pair_visits == 17
    assert plans["G_to_L"].planned_pair_visits == 17


@pytest.mark.parametrize(
    "shape,expected_batches",
    [
        (legacy.BatchShape(2, 8, 8), (6, 12)),
        (legacy.BatchShape(4, 8, 4), (8, 12)),
    ],
)
def test_actual_48_and_81_remainders_use_all_ranks_without_placeholders(shape, expected_batches):
    g = tuple(row("G", i) for i in range(48))
    l = tuple(row("L", i) for i in range(81))
    value = build("G_to_L", g=g, l=l, shape=shape)
    verifier.verify_plan(value, g, l)
    grouped = [
        [batch for batch in value.batches if batch.segment_index == segment]
        for segment in (0, 1)
    ]
    assert tuple(map(len, grouped)) == expected_batches
    assert {len(batch.rows) for batch in grouped[0]} == {6 if shape.world_size == 4 else 8}
    assert {len(batch.rows) for batch in grouped[1]} == {6, 7}
    assert all(batch.update_real_pairs in (48, 81) for batch in value.batches)
    assert value.summary()["partial_optimizer_updates"] == 2


def test_partial_ddp_loss_scales_reconstruct_global_pair_mean_exactly():
    g = tuple(row("G", i) for i in range(48))
    l = tuple(row("L", i) for i in range(81))
    value = build("G_to_L", g=g, l=l, shape=legacy.BatchShape(2, 8, 8))
    for step in range(value.steps):
        batches = [batch for batch in value.batches if batch.optimizer_step == step]
        coefficient_sum = sum(
            Fraction(batch.loss_mean_scale_numerator, batch.loss_mean_scale_denominator)
            for batch in batches
        ) / value.shape.world_size
        assert coefficient_sum == 1
        expected_per_pair = Fraction(1, batches[0].update_real_pairs)
        for batch in batches:
            observed = Fraction(
                batch.loss_mean_scale_numerator,
                batch.loss_mean_scale_denominator * value.shape.world_size * len(batch.rows),
            )
            assert observed == expected_per_pair


def test_budget_prefix_never_overshoots_and_reports_next_whole_pair():
    g = (row("G", 0, (2, 3)),)
    l = (row("L", 0, (3, 3)),)
    shape = legacy.BatchShape(1, 1, 4)
    local = build("Lbudget", g=g, l=l, shape=shape)
    global_only = build("Gbudget", g=g, l=l, shape=shape)
    assert local.reference_valid_tokens == 11
    assert local.planned_valid_tokens == 6
    assert local.budget_stop_next_pair_tokens == 6
    assert local.summary()["token_budget_shortfall"] == 5
    assert global_only.planned_valid_tokens == 10
    assert global_only.budget_stop_next_pair_tokens == 5
    assert global_only.summary()["token_budget_shortfall"] == 1
    verifier.verify_plan(local, g, l)
    verifier.verify_plan(global_only, g, l)


def test_exact_whole_pair_cap_has_zero_shortfall_and_no_next_pair():
    g = tuple(row("G", i, (2, 2)) for i in range(2))
    l = (row("L", 0, (4, 4)),)
    shape = legacy.BatchShape(1, 1, 4)
    for arm in ("Lbudget", "Gbudget"):
        value = build(arm, g=g, l=l, shape=shape)
        assert value.planned_valid_tokens == value.reference_valid_tokens == 16
        assert value.budget_stop_next_pair_tokens is None
        assert value.summary()["token_budget_shortfall"] == 0
        verifier.verify_plan(value, g, l)


def test_L1_is_optimizer_and_lr_prefix_not_only_row_prefix():
    g = tuple(row("G", i, (2 + i % 2, 4)) for i in range(10))
    l = tuple(row("L", i, (3, 3 + i % 3)) for i in range(7))
    l1 = build("L1", g=g, l=l)
    budget = build("Lbudget", g=g, l=l)
    verifier.verify_arm_relations(l1, budget, build("G_to_L", g=g, l=l),
                                  build("Ghash_to_L", g=g, l=l))
    assert budget.batches[:len(l1.batches)] == l1.batches
    assert budget.segments[0] == l1.segments[0]
    assert [b.lr_scale_numerator for b in budget.batches[:len(l1.batches)]] == [
        b.lr_scale_numerator for b in l1.batches
    ]


def test_lr_reaches_peak_once_and_never_restarts_at_cycle_or_phase_boundaries():
    g = tuple(row("G", i) for i in range(100))
    l = tuple(row("L", i) for i in range(70))
    value = build("Lbudget", g=g, l=l,
                  shape=legacy.BatchShape(1, 2, 2))
    fractions = [Fraction(batch.lr_scale_numerator, batch.lr_scale_denominator)
                 for batch in value.batches if batch.micro_step == 0 and batch.rank == 0]
    assert fractions == sorted(fractions)
    assert fractions[-1] == 1
    assert value.warmup_valid_tokens == 41


def test_arrival_order_and_pair_orientation_do_not_change_plan():
    g = tuple(row("G", i) for i in range(10))
    l = tuple(row("L", i) for i in range(7))
    reversed_arrival = build("G_to_L", g=g[::-1], l=l[::-1])
    flipped = tuple(legacy.Pair.canonical("G", item.b, item.a, item.context_sha256) for item in g)
    assert reversed_arrival.sha256 == build("G_to_L", g=g, l=l).sha256
    assert build("G_to_L", g=flipped, l=l).sha256 == reversed_arrival.sha256


def test_remainder_smaller_than_world_size_fails_without_hidden_placeholder():
    g = (row("G", 0),)
    l = tuple(row("L", i) for i in range(4))
    with pytest.raises(legacy.PlanError, match="insufficient_rows_for_all_rank_participation"):
        build("G_to_L", g=g, l=l, shape=legacy.BatchShape(2, 8, 8))


def test_caller_cannot_change_common_token_cap():
    g = tuple(row("G", i) for i in range(10))
    l = tuple(row("L", i) for i in range(7))
    with pytest.raises(legacy.PlanError, match="token_cap_must_equal"):
        plan.build_plan(
            "G_to_L", g, l, seed=6,
            shape=legacy.BatchShape(2, 2, 2),
            encoder=legacy.EncoderBinding(h("tokenizer"), h("serializer"), 8),
            protocol_sha256=h("protocol"), token_cap=135,
        )


@pytest.mark.parametrize("mutation", ["segment", "batch_count", "loss_scale", "lr", "token", "pool"])
def test_independent_replay_rejects_self_reported_plan_corruption(mutation):
    g = tuple(row("G", i) for i in range(10))
    l = tuple(row("L", i) for i in range(7))
    value = build("G_to_L", g=g, l=l)
    if mutation == "segment":
        value = replace(value, segments=(replace(value.segments[0], pair_visits=9),) + value.segments[1:])
    elif mutation == "batch_count":
        value = replace(value, batches=value.batches[:-1])
    elif mutation == "loss_scale":
        value = replace(value, batches=(replace(value.batches[0], loss_mean_scale_numerator=1),) + value.batches[1:])
    elif mutation == "lr":
        value = replace(value, batches=(replace(value.batches[0], lr_scale_numerator=1),) + value.batches[1:])
    elif mutation == "token":
        value = replace(value, reference_valid_tokens=value.reference_valid_tokens + 1)
    elif mutation == "pool":
        g = (replace(g[0], a=replace(g[0].a, encoded_sha256=h("changed"))),) + g[1:]
    with pytest.raises(verifier.TokenPlanVerificationError):
        verifier.verify_plan(value, g, l)


def test_legacy_full_batch_policy_rejects_the_real_local_pair_count():
    g = tuple(row("G", i) for i in range(128))
    l = tuple(row("L", i) for i in range(4689))
    with pytest.raises(legacy.PlanError, match="phase_boundary_policy_unresolved"):
        legacy.build_plan(
            "G_to_L", g, l, seed=6,
            shape=legacy.BatchShape(2, 8, 8),
            encoder=legacy.EncoderBinding(h("tokenizer"), h("serializer"), 8),
            protocol_sha256=h("legacy-protocol"),
        )


def test_hash_collision_fails_closed(monkeypatch):
    monkeypatch.setattr(plan, "endpoint_utility", lambda _: 1)
    with pytest.raises(legacy.PlanError, match="endpoint_hash_collision"):
        build("Ghash_to_L")


def test_resume_is_bound_to_exact_plan_and_update_boundary():
    value = build("G_to_L")
    cursor = legacy.ResumeCursor(value.sha256, 1)
    assert all(batch.optimizer_step >= 1 for batch in plan.remaining_batches(value, cursor))
    with pytest.raises(legacy.PlanError, match="resume_plan_binding_mismatch"):
        plan.remaining_batches(build("G_to_L", seed=7), cursor)
