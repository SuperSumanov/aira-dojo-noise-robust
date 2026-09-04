from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from phase1.g_reuse_target_a50 import (
    ALL_ARMS,
    MATCHED,
    PROTOCOL_SHA256,
    TargetReductionState,
    select_target_a50,
)
from phase1.g_reuse_target_contrast_variance import target_variances
from phase1.verify_g_reuse_target_a50 import (
    IndependentTargetState,
    independent_target_select,
)


REPO = Path(__file__).resolve().parents[2]
PROTOCOL = REPO / "phase1" / "g_reuse_target_a50_protocol_v1.json"


def toy():
    local = [("a", "b"), ("c", "d")]
    basis = [("b", "c")]
    full = basis + [("a", "c"), ("b", "d")]
    lengths = {node: 1 for node in "abcd"}
    return local, full, basis, lengths


def test_protocol_is_canonically_bound() -> None:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    canonical = json.dumps(protocol, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    assert hashlib.sha256(canonical).hexdigest() == PROTOCOL_SHA256
    assert protocol["arms"] == list(ALL_ARMS)
    assert protocol["matched_arms"] == list(MATCHED)
    assert protocol["timing_classification"].startswith("post-failure")


def test_sherman_reduction_equals_direct_variance_change() -> None:
    local, full, basis, _ = toy()
    edge = ("a", "c")
    state = TargetReductionState(local, full, basis)
    predicted = state.reduction(edge)
    before = sum(target_variances(local, basis))
    after = sum(target_variances(local, basis + [edge]))
    assert predicted == pytest.approx(before - after, rel=1e-10, abs=1e-10)
    assert predicted > 0


def test_shifted_and_grounded_reduction_match() -> None:
    local, full, basis, _ = toy()
    producer = TargetReductionState(local, full, basis)
    verifier = IndependentTargetState(local, full, basis)
    for edge in set(full) - set(basis):
        assert producer.reduction(edge) == pytest.approx(
            verifier.reduction(edge), rel=1e-10, abs=1e-10
        )


def test_shifted_and_grounded_target_selector_match() -> None:
    local, full, basis, lengths = toy()
    producer = select_target_a50(local, full, basis, lengths)
    verifier = independent_target_select(local, full, basis, lengths)
    assert producer == pytest.approx(verifier)
    assert producer["additional_tokens"] <= producer["additional_token_budget"]
    assert set(basis) <= set(producer["edges"]) <= set(full)


def test_target_selector_is_order_invariant() -> None:
    local, full, basis, lengths = toy()
    forward = select_target_a50(local, full, basis, lengths)
    reverse = select_target_a50(list(reversed(local)), list(reversed(full)), list(reversed(basis)), lengths)
    assert forward == reverse
