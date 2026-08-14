from __future__ import annotations

from dataclasses import replace

import pytest

from phase1 import selective_execution_audit as audit
from phase1 import verify_selective_execution_audit as verifier


def make_pair(index: int, task: str, votes=(1, 1, 1), confidence=0.5) -> audit.Pair:
    arms = audit.ARMS
    return audit.Pair(
        row_index=index,
        task=task,
        run=f"run-{index // 2}",
        parent=f"parent-{index:03d}",
        lo=f"lo-{index}",
        hi=f"hi-{index}",
        true_vote=1 if index % 2 == 0 else -1,
        gap=0.01 + index / 10_000,
        fold=index % 5,
        votes=dict(zip(arms, votes)),
        confidence={arm: confidence for arm in arms},
        percentiles={arm: confidence for arm in arms},
    )


def test_midrank_percentiles_keep_ties_equal() -> None:
    values = audit.midrank_percentiles([("a", 1.0), ("b", 1.0), ("c", 3.0), ("d", 2.0)])
    assert values["a"] == values["b"] == 0.375
    assert values["d"] == 0.75
    assert values["c"] == 1.0


def test_policy_selection_is_outcome_blind() -> None:
    pairs = []
    for task_index, task in enumerate(("task-a", "task-b")):
        for local in range(10):
            index = 10 * task_index + local
            pair = make_pair(index, task, confidence=(local + 1) / 10)
            if local == 8:
                pair = replace(pair, votes={arm: (-1 if arm == audit.ARMS[0] else 1) for arm in audit.ARMS})
            pairs.append(pair)
    first, quotas = audit.build_policies(pairs)
    changed_outcomes = [replace(pair, true_vote=-pair.true_vote, gap=pair.gap * 7) for pair in pairs]
    second, changed_quotas = audit.build_policies(changed_outcomes)
    assert quotas == changed_quotas == {"task-a": 2, "task-b": 2}
    for policy in first:
        if policy != "oracle_all":
            assert first[policy] == second[policy]
    assert len(first["tri_unanimous_q20"]) == 4
    assert "parent-009" in first["tri_unanimous_q20"]
    assert "parent-008" not in first["tri_unanimous_q20"]


def test_unanimity_rejects_ties_and_disagreement() -> None:
    assert audit.unanimous_vote(make_pair(0, "t", votes=(1, 1, 1))) == 1
    assert audit.unanimous_vote(make_pair(1, "t", votes=(-1, -1, -1))) == -1
    assert audit.unanimous_vote(make_pair(2, "t", votes=(1, -1, 1))) == 0
    assert audit.unanimous_vote(make_pair(3, "t", votes=(1, 0, 1))) == 0


def test_policy_metrics_oracle_has_zero_regret() -> None:
    pairs = [make_pair(index, "task-a" if index < 10 else "task-b") for index in range(20)]
    oracle = {pair.parent: pair.true_vote for pair in pairs}
    metrics = audit.policy_metrics(pairs, oracle, 0)
    assert metrics["micro_accuracy"] == 1.0
    assert metrics["run_macro_accuracy"] == 1.0
    assert metrics["task_macro_accuracy"] == 1.0
    assert metrics["selected_gap_weighted_accuracy"] == 1.0
    assert metrics["task_macro_total_gap_loss_ratio"] == 0.0
    assert metrics["candidate_saving_fraction"] == 0.5


def test_producer_and_verifier_hash_namespaces_match() -> None:
    parent = "parent-x"
    assert audit.stable_hex(audit.PROTOCOL, "random_all", parent) == verifier.key("random_all", parent)


def test_verifier_recursive_comparison_rejects_tamper() -> None:
    verifier.recursively_match({"x": [1.0, 2]}, {"x": [1.0, 2]})
    with pytest.raises(verifier.VerificationError, match="numeric mismatch"):
        verifier.recursively_match({"x": 1.0}, {"x": 1.1})


def test_forbidden_input_guard() -> None:
    with pytest.raises(audit.AuditError, match="forbidden"):
        audit.assert_safe_input(audit.Path("phase1/decision_frozen/oof_predictions.csv"))
    with pytest.raises(audit.AuditError, match="basename"):
        audit.assert_safe_input(audit.Path("phase1/scores.csv"))
