from __future__ import annotations

from collections import Counter
from dataclasses import replace
import hashlib
import itertools
import math
import os
import random

import pytest

from phase1 import global_local_execution_plan as p
from phase1.verify_global_local_execution_trace import BatchReceipt, verify_layout, verify_plan, verify_prefix


def h(text):
    return hashlib.sha256(text.encode()).hexdigest()


def row(source, i, lengths=(3, 5)):
    return p.Pair.canonical(source,
        p.Endpoint(f"synthetic:{source}:{i}:a", lengths[0], h(f"{source}:{i}:a")),
        p.Endpoint(f"synthetic:{source}:{i}:b", lengths[1], h(f"{source}:{i}:b")),
        h("synthetic:context"))


def build(arm="G_to_L", seed=6, g=None, l=None, shape=None, encoder=None):
    return p.build_plan(arm, tuple(g) if g is not None else tuple(row("G", i) for i in range(16)),
        tuple(l) if l is not None else tuple(row("L", i) for i in range(8)),
        seed=seed, shape=shape or p.BatchShape(2, 2, 2),
        encoder=encoder or p.EncoderBinding(h("synthetic:tok"), h("synthetic:ser"), 8),
        protocol_sha256=h("synthetic:protocol"))


def flattened(plan):
    return tuple(r for b in plan.batches for r in b.rows)


def synthetic_receipts(plan, completed=None):
    """Test fixtures only, explicitly not evidence of actual Trainer consumption."""
    stop = plan.steps if completed is None else completed
    binding = plan.sha256
    return [BatchReceipt(binding, b.optimizer_step, b.micro_step, b.rank,
        tuple(r.key for r in b.rows),
        tuple((r.a.encoded_sha256, r.b.encoded_sha256) for r in b.rows),
        sum(r.a.valid_tokens + r.b.valid_tokens for r in b.rows),
        2 * len(b.rows) * max(max(r.a.valid_tokens, r.b.valid_tokens) for r in b.rows))
        for b in plan.batches if b.optimizer_step < stop]


@pytest.mark.parametrize("seed", [6, 7, 8])
@pytest.mark.parametrize("arm", p.ARMS)
def test_five_arms_exact_consumption_and_budget(seed, arm):
    plan = build(arm, seed)
    rows = flattened(plan)
    assert len(rows) == (8 if arm == "L1" else 24)
    assert plan.steps == (1 if arm == "L1" else 3)
    assert sum(r.valid_tokens for r in rows) == (64 if arm == "L1" else 192)
    assert all(len(b.rows) == 2 for b in plan.batches)
    assert all(b.rank in (0, 1) and b.micro_step in (0, 1) for b in plan.batches)
    if arm in ("G_to_L", "Ghash_to_L"):
        assert [r.source for r in rows] == ["G"] * 16 + ["L"] * 8
        assert len({r.key for r in rows}) == 24
    elif arm in ("L1", "Lbudget"):
        assert {r.source for r in rows} == {"L"}
        assert set(Counter(r.key for r in rows).values()) == ({1} if arm == "L1" else {3})
    else:
        assert {r.source for r in rows} == {"G"}
        assert set(Counter(r.key for r in rows).values()) == {1, 2}
    assert plan.summary()["valid_and_steps_match_reference"] == (arm != "L1")
    assert plan.summary()["actual_compute_matched"] is None
    assert plan.summary()["training_authorized"] is False
    assert plan.summary()["trainer_integrated"] is False
    verify_plan(plan, tuple(row("G", i) for i in range(16)), tuple(row("L", i) for i in range(8)))
    assert verify_prefix(plan, synthetic_receipts(plan), completed_steps=plan.steps)


def test_seed_and_arrival_order_are_independent():
    g = tuple(row("G", i) for i in range(16))
    l = tuple(row("L", i) for i in range(8))
    assert build(g=g, l=l).sha256 == build(g=g[::-1], l=l[::-1]).sha256
    assert len({build(seed=s).input_sha256 for s in (6, 7, 8)}) == 3


def test_label_control_keeps_all_inputs_and_local_phase_identical():
    true, hashed = build(), build("Ghash_to_L")
    assert true.batches == hashed.batches
    assert true.input_sha256 == hashed.input_sha256
    assert true.sha256 != hashed.sha256
    calls = []
    def truth(key):
        calls.append(key)
        return 1
    for batch in hashed.batches:
        values = p.targets(hashed.arm, batch, truth)
        assert len(values) == len(batch.rows)
    assert calls == [r.key for r in flattened(hashed) if r.source == "L"]


def test_hash_global_does_not_read_true_labels():
    plan = build("Ghash_to_L")
    def forbidden(_):
        raise AssertionError("true global label read")
    values = p.targets(plan.arm, plan.batches[0], forbidden)
    assert values == tuple(p.hash_sign(r) for r in plan.batches[0].rows)


def test_hash_seed_is_exact_and_orders_shared_endpoints_transitively():
    endpoints = [p.Endpoint(f"synthetic:{i}", 3, h(str(i))) for i in range(8)]
    def wins(a, b):
        pair = p.Pair.canonical("G", a, b, h("context"))
        sign = p.hash_sign(pair)
        return pair.a.card_id if sign == 1 else pair.b.card_id
    for a in endpoints:
        independent = int(hashlib.sha256(("20260823|" + a.card_id).encode()).hexdigest(), 16)
        assert p.endpoint_utility(a.card_id) == independent
    for a, b, c in itertools.permutations(endpoints, 3):
        if wins(a, b) == a.card_id and wins(b, c) == b.card_id:
            assert wins(a, c) == a.card_id


def test_hash_collision_fails_closed(monkeypatch):
    monkeypatch.setattr(p, "endpoint_utility", lambda _: 1)
    with pytest.raises(p.PlanError, match="endpoint_hash_collision"):
        build("Ghash_to_L")


def test_pair_identity_does_not_depend_on_orientation():
    item = row("G", 0)
    flipped = p.Pair.canonical("G", item.b, item.a, item.context_sha256)
    assert item == flipped and item.key == flipped.key
    with pytest.raises(p.PlanError, match="canonical"):
        p.Pair("G", item.b, item.a, item.context_sha256)


@pytest.mark.parametrize("g_count,l_count", [(15, 8), (16, 7), (4, 4)])
def test_partial_phase_boundaries_never_pad_drop_or_mix(g_count, l_count):
    with pytest.raises(p.PlanError, match="phase_boundary_policy_unresolved"):
        build(g=[row("G", i) for i in range(g_count)], l=[row("L", i) for i in range(l_count)])


def test_whole_pair_budget_unreachable_without_cutting_code():
    with pytest.raises(p.PlanError, match="whole_pair_token_budget_unreachable"):
        build("Lbudget", g=[row("G", 0, (2, 2))], l=[row("L", 0, (3, 3))],
              shape=p.BatchShape(1, 1, 1))


def test_exact_valid_tokens_alone_cannot_certify_equal_steps():
    with pytest.raises(p.PlanError, match="optimizer_steps_mismatch"):
        build("Lbudget", g=[row("G", 0, (1, 3))], l=[row("L", 0, (1, 1))],
              shape=p.BatchShape(1, 1, 1))


def test_padding_is_reported_separately_not_called_compute_matched():
    g = [row("G", i, (3, 5)) for i in range(16)]
    l = [row("L", i, (4, 4)) for i in range(8)]
    report = build("Lbudget", g=g, l=l).summary()
    assert report["valid_and_steps_match_reference"]
    assert not report["padded_slots_match_reference"]
    assert report["planned_valid_tokens"] == 192
    assert report["planned_padded_slots"] == 192
    assert report["reference_padded_slots"] == 224
    assert report["actual_compute_matched"] is None


def test_duplicate_and_cross_source_overlap_are_not_silently_accepted():
    g = [row("G", i) for i in range(16)]
    with pytest.raises(p.PlanError, match="duplicate_unordered_pair"):
        build(g=g[:-1] + [g[0]])
    with pytest.raises(p.PlanError, match="cross_source_pair_overlap_policy_unresolved"):
        build(g=g, l=[replace(r, source="L") for r in g[:8]])


def test_context_and_endpoint_encoding_binding():
    g = [row("G", i) for i in range(16)]
    shared = p.Pair.canonical("G", replace(g[0].a, encoded_sha256=h("changed")),
                             g[1].b, g[0].context_sha256)
    with pytest.raises(p.PlanError, match="inconsistent_endpoint_encoding"):
        build(g=g[:-1] + [shared])
    with pytest.raises(p.PlanError, match="over_context"):
        build(g=[row("G", i, (3, 9)) for i in range(16)])


@pytest.mark.parametrize("bad", [0, -1, True, 1.5])
def test_invalid_shape_rejected(bad):
    with pytest.raises(p.PlanError, match="invalid_integer"):
        p.BatchShape(bad, 2, 2)


@pytest.mark.parametrize("bad", [True, -1, 1.5])
def test_invalid_seed_rejected(bad):
    with pytest.raises(p.PlanError, match="invalid_integer"):
        build(seed=bad)


@pytest.mark.parametrize("bad", [0, True, None, 2])
def test_invalid_true_target_sign_rejected(bad):
    with pytest.raises(p.PlanError, match="invalid_target_sign"):
        p.targets("Lbudget", build("Lbudget").batches[0], lambda _: bad)


def test_unknown_arm_empty_and_mixed_pools_rejected():
    for kwargs, message in [({"arm": "interleaved"}, "invalid_arm"),
                            ({"g": []}, "empty_or_mixed_pool"),
                            ({"l": [row("G", 0)]}, "empty_or_mixed_pool")]:
        with pytest.raises(p.PlanError, match=message):
            build(**kwargs)


def test_signed_loss_and_gradients_match_legacy_better_first_objective():
    rng = random.Random(20260903)
    for sign in (-1, 1):
        for _ in range(100):
            a, b = rng.uniform(-8, 8), rng.uniform(-8, 8)
            loss, da, db = p.bt_loss_and_gradient(a, b, sign)
            better, worse = (a, b) if sign == 1 else (b, a)
            margin = better - worse
            legacy_loss = math.log1p(math.exp(-margin))
            legacy_better_grad = -1.0 / (1.0 + math.exp(margin))
            assert loss == pytest.approx(legacy_loss)
            assert da == pytest.approx(legacy_better_grad if sign == 1 else -legacy_better_grad)
            assert db == -da
            eps = 1e-5
            finite_difference = (p.bt_loss_and_gradient(a + eps, b, sign)[0]
                                 - p.bt_loss_and_gradient(a - eps, b, sign)[0]) / (2 * eps)
            assert da == pytest.approx(finite_difference, abs=1e-9)


@pytest.mark.parametrize("a,b", [(1000.0, -1000.0), (-1000.0, 1000.0)])
def test_loss_is_numerically_stable(a, b):
    assert all(math.isfinite(x) for x in p.bt_loss_and_gradient(a, b, 1))


@pytest.mark.parametrize("a,b", [(math.nan, 0), (0, math.inf), (1e308, -1e308)])
def test_loss_rejects_nonfinite_values_and_overflow(a, b):
    with pytest.raises(p.PlanError, match="nonfinite"):
        p.bt_loss_and_gradient(a, b, 1)


@pytest.mark.parametrize("completed", [0, 1, 2, 3])
def test_resume_exact_suffix_at_every_update_boundary(completed):
    plan = build()
    cursor = verify_prefix(plan, synthetic_receipts(plan, completed), completed_steps=completed)
    prefix = tuple(b for b in plan.batches if b.optimizer_step < completed)
    suffix = p.remaining_batches(plan, cursor)
    assert prefix + suffix == plan.batches


def test_resume_binding_rejects_seed_arm_shape_and_encoder_drift():
    plan = build()
    cursor = verify_prefix(plan, synthetic_receipts(plan, 1), completed_steps=1)
    others = [build(seed=7), build("Ghash_to_L"), build(shape=p.BatchShape(4, 1, 2)),
              build(encoder=p.EncoderBinding(h("different"), h("synthetic:ser"), 8))]
    for other in others:
        with pytest.raises(p.PlanError, match="resume_plan_binding_mismatch"):
            p.remaining_batches(other, cursor)
    with pytest.raises(p.PlanError, match="resume_step_out_of_range"):
        p.remaining_batches(plan, replace(cursor, completed_optimizer_steps=4))
    with pytest.raises(p.PlanError, match="invalid_integer"):
        replace(cursor, completed_optimizer_steps=True)


def test_receipt_interleaving_between_ranks_is_allowed():
    plan = build()
    receipts = synthetic_receipts(plan)
    rank_grouped = [r for rank in (1, 0) for r in receipts if r.rank == rank]
    assert verify_prefix(plan, rank_grouped, completed_steps=3)


@pytest.mark.parametrize("mutation", ["missing", "extra", "duplicate", "wrong_plan", "pair_order",
    "encoding_order", "valid_tokens", "padded_slots", "rank_order", "bad_address", "bad_count"])
def test_independent_trace_checker_rejects_corruption(mutation):
    plan = build()
    events = synthetic_receipts(plan)
    if mutation == "missing": events.pop()
    elif mutation == "extra": events.append(events[-1])
    elif mutation == "duplicate": events[1] = events[0]
    elif mutation == "wrong_plan": events[0] = replace(events[0], plan_sha256=h("other"))
    elif mutation == "pair_order": events[0] = replace(events[0], pair_keys=events[0].pair_keys[::-1])
    elif mutation == "encoding_order":
        events[0] = replace(events[0], encoded_digests=tuple((b, a) for a, b in events[0].encoded_digests))
    elif mutation == "valid_tokens": events[0] = replace(events[0], valid_tokens=1)
    elif mutation == "padded_slots": events[0] = replace(events[0], padded_slots=1)
    elif mutation == "rank_order": events[0], events[2] = events[2], events[0]
    elif mutation == "bad_address": events[0] = replace(events[0], rank=True)
    elif mutation == "bad_count": events[0] = replace(events[0], valid_tokens=True)
    with pytest.raises(p.PlanError):
        verify_prefix(plan, events, completed_steps=3)


@pytest.mark.parametrize("completed", [True, -1, 1.5, 4])
def test_bad_completed_steps_rejected(completed):
    with pytest.raises(p.PlanError, match="invalid_completed_steps"):
        verify_prefix(build(), [], completed_steps=completed)


def test_demo_is_synthetic_only_and_has_no_model_or_file_access(monkeypatch):
    import builtins
    def forbidden(*args, **kwargs):
        raise AssertionError("unexpected file access")
    monkeypatch.setattr(builtins, "open", forbidden)
    plans = tuple(p.demo_plans())
    assert len(plans) == 15
    assert all(e.card_id.startswith("synthetic:") for plan in plans
               for batch in plan.batches for r in batch.rows for e in (r.a, r.b))
    assert all(not plan.summary()["training_authorized"] for plan in plans)


@pytest.mark.parametrize("mutation", ["partial", "duplicate_address", "repeat_row", "mixed_phase",
                                    "reference_steps", "reference_valid", "reference_padding"])
def test_independent_verifier_also_checks_the_plan_not_only_receipts(mutation):
    plan = build()
    batches = list(plan.batches)
    if mutation == "partial": plan = replace(plan, batches=plan.batches[:-1])
    elif mutation == "duplicate_address":
        batches[1] = batches[0]
        plan = replace(plan, batches=tuple(batches))
    elif mutation == "repeat_row":
        batches[1] = replace(batches[1], rows=batches[0].rows)
        plan = replace(plan, batches=tuple(batches))
    elif mutation == "mixed_phase":
        batches[0] = replace(batches[0], rows=plan.batches[-1].rows)
        plan = replace(plan, batches=tuple(batches))
    elif mutation == "reference_steps": plan = replace(plan, reference_steps=4)
    elif mutation == "reference_valid": plan = replace(plan, reference_valid_tokens=1)
    elif mutation == "reference_padding": plan = replace(plan, reference_padded_slots=1)
    with pytest.raises(p.PlanError):
        verify_layout(plan)


def test_reference_replay_rejects_a_self_consistent_but_wrong_seeded_plan():
    plan = build()
    batches = list(plan.batches)
    batches[0] = replace(batches[0], rows=batches[0].rows[::-1])
    wrong = replace(plan, batches=tuple(batches))
    verify_layout(wrong)  # Counts and exactly-once alone cannot catch this.
    with pytest.raises(p.PlanError, match="seeded_source_schedule_mismatch"):
        verify_plan(wrong, tuple(row("G", i) for i in range(16)), tuple(row("L", i) for i in range(8)))


def test_reference_replay_rejects_changed_manifest():
    plan = build()
    g = [row("G", i) for i in range(16)]
    g[0] = replace(g[0], a=replace(g[0].a, encoded_sha256=h("changed")))
    with pytest.raises(p.PlanError, match="reference_manifest_binding_mismatch"):
        verify_plan(plan, g, tuple(row("L", i) for i in range(8)))


@pytest.mark.parametrize("world,per_rank,accumulation", [(1, 1, 1), (1, 3, 2), (2, 1, 3),
                                                       (2, 3, 2), (4, 1, 2), (4, 3, 1)])
def test_layout_and_resume_generalize_across_shapes(world, per_rank, accumulation):
    shape = p.BatchShape(world, per_rank, accumulation)
    g = tuple(row("G", i) for i in range(2 * shape.effective_pairs))
    l = tuple(row("L", i) for i in range(shape.effective_pairs))
    for arm in p.ARMS:
        plan = build(arm, g=g, l=l, shape=shape)
        verify_plan(plan, g, l)
        for completed in range(plan.steps + 1):
            cursor = verify_prefix(plan, synthetic_receipts(plan, completed), completed_steps=completed)
            prefix = tuple(b for b in plan.batches if b.optimizer_step < completed)
            assert prefix + p.remaining_batches(plan, cursor) == plan.batches


def test_standalone_validation_receipt_and_golden_digest(monkeypatch):
    from phase1 import global_local_cpu_validation as validation
    def forbidden():
        raise AssertionError("torch check must remain opt-in")
    monkeypatch.setattr(validation, "check_cpu_autograd", forbidden)
    receipt = validation.validate_cpu()
    assert receipt["demo_sha256"] == "ceec67c7cf406525303301be8b8b6ed817cd07740717d958f422de59b3d35d03"
    assert receipt["resume_boundaries_checked"] == 54
    assert receipt["synthetic_plans"] == 15
    assert receipt["autograd"] == {"status": "NOT_REQUESTED"}
    assert receipt["actual_training_batches_observed"] == 0
    assert receipt["model_fits"] == receipt["gpu_jobs"] == receipt["frozen_or_train_data_files_opened"] == 0


@pytest.mark.skipif(os.environ.get("GL_CPU_TORCH_CHECK") != "1", reason="explicit opt-in CPU autograd check")
def test_cpu_torch_signed_loss_and_autograd_match_legacy():
    # No network/module/optimizer/train call, and all tensors explicitly on CPU.
    import torch
    assert not torch.cuda.is_initialized()
    for sign in (-1, 1):
        a = torch.tensor([-6.0, -0.25, 0.0, 0.7, 8.0], dtype=torch.float64,
                         device="cpu", requires_grad=True)
        b = torch.tensor([3.0, 0.75, 0.0, -1.3, -4.0], dtype=torch.float64,
                         device="cpu", requires_grad=True)
        signed = torch.nn.functional.softplus(-sign * (a - b)).mean()
        signed_grads = torch.autograd.grad(signed, (a, b))
        legacy = -torch.nn.functional.logsigmoid((a - b) if sign == 1 else (b - a)).mean()
        legacy_grads = torch.autograd.grad(legacy, (a, b))
        torch.testing.assert_close(signed, legacy, rtol=1e-12, atol=1e-12)
        for observed, expected in zip(signed_grads, legacy_grads):
            torch.testing.assert_close(observed, expected, rtol=1e-12, atol=1e-12)
        for i, (x, y) in enumerate(zip(a.detach().tolist(), b.detach().tolist())):
            loss, da, db = p.bt_loss_and_gradient(x, y, sign)
            assert float(signed_grads[0][i]) == pytest.approx(da / len(a), abs=1e-12)
            assert float(signed_grads[1][i]) == pytest.approx(db / len(a), abs=1e-12)
    assert not torch.cuda.is_initialized()
