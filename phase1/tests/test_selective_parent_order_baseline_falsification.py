from __future__ import annotations

import inspect
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

from phase1 import audit_selective_parent_order_baseline_falsification as producer
from phase1 import verify_selective_parent_order_baseline_falsification as independent


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "phase1/selective_parent_order_baseline_falsification_v1.json"


def row(
    *,
    task: str = "t",
    run: str = "r",
    parent: str = "p",
    content: str | None = "p",
    step: str | None = "p",
    manifest: str | None = "p",
    time: str | None = None,
) -> producer.RecoveryRow:
    return producer.RecoveryRow(
        task=task,
        run=run,
        parent=parent,
        content_prediction=content,
        content_margin=Fraction(1, 2),
        max_prior_step_prediction=step,
        nearest_prior_manifest_row_prediction=manifest,
        latest_prior_generation_time_prediction=time,
    )


def test_protocol_is_hash_bound_and_discloses_post_result_falsification() -> None:
    protocol, digest, published = producer.read_protocol(PROTOCOL, ROOT)
    assert digest == producer.PROTOCOL_SHA256
    assert protocol["freeze_state"]["published_content_result_known"] is True
    assert protocol["freeze_state"]["max_prior_step_baseline_values_seen"] is False
    assert protocol["freeze_state"]["nearest_prior_manifest_row_baseline_values_seen"] is False
    assert published["package_manifest_members"] == 7
    assert published["classification"] == "DEVELOPMENT_TIME_SPLIT_HIGH_PRECISION_SELECTIVE_PARENT_RECOVERY"


def test_unique_maximum_abstains_on_top_tie() -> None:
    values = {"a": 1, "b": 2, "c": 2}
    assert producer.unique_maximum(["a", "b"], values.__getitem__) == "b"
    assert producer.unique_maximum(["a", "b", "c"], values.__getitem__) is None
    assert producer.unique_maximum([], values.__getitem__) is None


def test_paired_profile_uses_only_baseline_predictions() -> None:
    rows = [
        row(content="p", step="p"),
        row(content="p", step="wrong"),
        row(content="wrong", step="p"),
        row(content="wrong", step="wrong"),
        row(content="p", step=None),
    ]
    profile, comparable = producer.compare(rows, "max_prior_step")
    assert len(comparable) == 4
    assert profile["comparable_rows"] == 4
    assert profile["content_correct"] == 2
    assert profile["order_correct"] == 2
    assert profile["paired_correctness"] == {
        "both_correct": 1,
        "content_only_correct": 1,
        "order_only_correct": 1,
        "both_wrong": 1,
    }


def test_aggregate_advantage_gate_requires_nonzero_order_error_and_twofold_wins() -> None:
    protocol = producer.read_json(PROTOCOL)
    passing = {
        "comparable_rows": 2100,
        "comparable_coverage": producer.exact(Fraction(20, 21)),
        "content_errors": 5,
        "order_errors": 20,
        "paired_correctness": {"content_only_correct": 18, "order_only_correct": 3},
    }
    assert all(producer.aggregate_gates(passing, protocol).values())
    zero_order_error = dict(passing)
    zero_order_error["order_errors"] = 0
    gates = producer.aggregate_gates(zero_order_error, protocol)
    assert gates["order_errors_nonzero"] is False
    assert gates["content_error_at_most_half_order_error"] is False
    weak_wins = dict(passing)
    weak_wins["paired_correctness"] = {"content_only_correct": 5, "order_only_correct": 3}
    assert producer.aggregate_gates(weak_wins, protocol)["content_only_wins_at_least_twice_order_only_wins"] is False


def test_anonymous_breadth_never_emits_group_identity() -> None:
    rows = [
        row(task="task-a", run="run-a", content="p", step="wrong"),
        row(task="task-a", run="run-a", content="p", step="wrong"),
        row(task="task-b", run="run-b", content="wrong", step="p"),
    ]
    profile = producer.breadth_profile(rows, "max_prior_step", "task", 1)
    assert profile["discordant_rows"] == 3
    assert profile["conditionable_groups"] == 2
    assert profile["identities_emitted"] is False
    assert "task-a" not in repr(profile)
    assert "task-b" not in repr(profile)


def test_producer_and_independent_baselines_agree_on_synthetic_snapshot(monkeypatch) -> None:
    cards = {
        "root": {"task": "t", "run": "r", "parent": "missing", "depth": 0},
        "p1": {"task": "t", "run": "r", "parent": "root", "depth": 1},
        "p2": {"task": "t", "run": "r", "parent": "root", "depth": 1},
        "child": {"task": "t", "run": "r", "parent": "p2", "depth": 2},
    }
    objects = {
        "root": {
            "code": "root",
            "generation_started_at_utc": "2026-01-01T00:00:00Z",
            "lineage": {"step": 0},
        },
        "p1": {
            "code": "p1",
            "generation_started_at_utc": "2026-01-01T00:00:01Z",
            "lineage": {"step": 1},
        },
        "p2": {
            "code": "p2",
            "generation_started_at_utc": "2026-01-01T00:00:02Z",
            "lineage": {"step": 2},
        },
        "child": {
            "code": "child",
            "generation_started_at_utc": "2026-01-01T00:00:03Z",
            "lineage": {"step": 3},
        },
    }
    fingerprints = {
        "root": frozenset({1, 2}),
        "p1": frozenset({3, 4}),
        "p2": frozenset({5, 6, 7}),
        "child": frozenset({5, 6, 8}),
    }
    monkeypatch.setattr(
        producer.fingerprint_impl,
        "identifier_erased_token_shingles",
        lambda code: fingerprints[code],
    )
    monkeypatch.setattr(
        independent.fingerprint_check,
        "identifier_erased_shingles",
        lambda code: fingerprints[code],
    )
    producer_snapshot = SimpleNamespace(cards=cards, card_payloads=objects)
    verifier_snapshot = SimpleNamespace(graph_cards=cards, card_objects=objects)
    producer_rows, producer_inventory = producer.build_rows(producer_snapshot)
    verifier_rows, verifier_inventory = independent.independently_recover(verifier_snapshot)
    assert producer_inventory == verifier_inventory
    assert len(producer_rows) == len(verifier_rows) == 1
    assert producer_rows[0].content_prediction == verifier_rows[0].content == "p2"
    assert producer_rows[0].max_prior_step_prediction == verifier_rows[0].step_choice == "p2"
    assert producer_rows[0].nearest_prior_manifest_row_prediction == verifier_rows[0].manifest_choice == "p2"
    assert producer_rows[0].latest_prior_generation_time_prediction == verifier_rows[0].time_choice == "p2"


def test_independent_verifier_does_not_import_new_producer() -> None:
    source = inspect.getsource(independent)
    assert "audit_selective_parent_order_baseline_falsification" not in source
    assert "from phase1 import audit_selective" not in source
