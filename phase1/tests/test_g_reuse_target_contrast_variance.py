from __future__ import annotations

import json
import hashlib
from pathlib import Path

import pytest

from phase1.g_reuse_target_contrast_variance import (
    ALL_ARMS,
    MATCHED,
    MAX_TASK_POSITIVE_SHARE,
    NONWORSE_TASKS_MINIMUM,
    PROTOCOL_SHA256,
    RELATIVE_REDUCTION_MINIMUM,
    STRICT_TASKS_MINIMUM,
    quantile,
    select_edges,
    selected_manifest,
    target_variances,
)
from phase1.historical_label_reuse_support import pairs
from phase1.verify_g_reuse_target_contrast_variance import (
    independent_quantile,
    independent_select_edges,
    independent_target_variances,
)


REPO = Path(__file__).resolve().parents[2]
PROTOCOL = REPO / "phase1" / "g_reuse_target_contrast_variance_protocol_v1.json"


def toy():
    local = [("a", "b"), ("c", "d")]
    basis = [("b", "c")]
    full = basis + [("a", "c"), ("b", "d")]
    lengths = {node: 1 for node in "abcd"}
    return local, full, basis, lengths


def test_protocol_constants_are_frozen() -> None:
    raw = PROTOCOL.read_bytes()
    protocol = json.loads(raw)
    assert hashlib.sha256(raw).hexdigest() == PROTOCOL_SHA256
    assert protocol["protocol"] == "g-reuse-target-contrast-variance-v1"
    assert protocol["status"] == "FROZEN_BEFORE_VARIANCE_READOUT"
    assert protocol["arms"] == list(ALL_ARMS)
    assert protocol["matched_arms"] == list(MATCHED)
    gates = protocol["gates"]
    assert gates["spectral_relative_reduction_vs_each_baseline_minimum"] == RELATIVE_REDUCTION_MINIMUM
    assert gates["spectral_nonworse_tasks_vs_each_baseline_minimum"] == NONWORSE_TASKS_MINIMUM
    assert gates["spectral_strictly_better_tasks_vs_each_baseline_minimum"] == STRICT_TASKS_MINIMUM
    assert gates["maximum_single_task_positive_reduction_share"] == MAX_TASK_POSITIVE_SHARE


def test_quantile_has_fixed_linear_interpolation() -> None:
    assert quantile([0.0, 10.0], 0.9) == pytest.approx(9.0)
    assert quantile([3.0, 1.0, 2.0], 0.5) == 2.0
    with pytest.raises(ValueError, match="invalid_quantile"):
        quantile([], 0.9)


def test_pair_direction_is_canonicalized_away() -> None:
    rows = [{"intask_split": "train", "better": "z", "worse": "a"}]
    assert pairs(rows) == [("a", "z")]


@pytest.mark.parametrize("arm", MATCHED)
def test_matched_selectors_share_budget_and_never_exceed_it(arm: str) -> None:
    local, full, basis, lengths = toy()
    selected = select_edges(local, full, basis, lengths, arm)
    assert selected["additional_token_budget"] == 2
    assert selected["additional_tokens"] <= selected["additional_token_budget"]
    assert set(basis) <= set(selected["edges"]) <= set(full)


def test_adding_edges_cannot_increase_target_variance() -> None:
    local, full, basis, _ = toy()
    sparse = target_variances(local, basis)
    dense = target_variances(local, full)
    assert len(sparse) == len(dense) == len(local)
    assert all(after <= before + 1e-10 for before, after in zip(sparse, dense))
    assert any(after < before - 1e-10 for before, after in zip(sparse, dense))


def test_selected_manifest_is_order_invariant_and_arm_sensitive() -> None:
    first = {"basis": [("a", "b")], "full": [("c", "d"), ("a", "b")]}
    reordered = {"full": [("a", "b"), ("c", "d")], "basis": [("a", "b")]}
    changed = {"basis": [("a", "b")], "full": [("a", "b")]}
    assert selected_manifest(first) == selected_manifest(reordered)
    assert selected_manifest(first) != selected_manifest(changed)


@pytest.mark.parametrize("arm", MATCHED)
def test_shifted_and_grounded_selectors_match_on_toy(arm: str) -> None:
    local, full, basis, lengths = toy()
    producer = select_edges(local, full, basis, lengths, arm)
    verifier = independent_select_edges(local, full, basis, lengths, arm)
    assert producer == verifier


def test_shifted_and_grounded_target_variances_match_on_toy() -> None:
    local, full, _, _ = toy()
    shifted = target_variances(local, full)
    grounded = independent_target_variances(local, full)
    assert shifted == pytest.approx(grounded, rel=1e-10, abs=1e-10)
    assert quantile(shifted, 0.9) == pytest.approx(independent_quantile(grounded, 0.9))
