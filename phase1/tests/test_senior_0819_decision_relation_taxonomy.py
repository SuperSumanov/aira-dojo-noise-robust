from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pytest

from phase1 import audit_senior_0819_decision_relation_taxonomy as producer
from phase1 import verify_senior_0819_decision_relation_taxonomy as verifier


DECISION_DEFAULTS = {
    "budget": 1,
    "clears_tau": True,
    "gap_raw": 0.1,
    "loto_fold": "fold",
    "set_size": 2,
    "src": "decision",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def card(identifier: str, run_task: str, parent: str | None) -> dict:
    return {
        "id": identifier,
        "task": {"name": run_task},
        "lineage": {"parent_id": parent},
    }


def decision(
    better: str, worse: str, parent: str, split: str, task: str = "task-one"
) -> dict:
    return {
        **DECISION_DEFAULTS,
        "better": better,
        "worse": worse,
        "parent": parent,
        "task": task,
        "intask_split": split,
    }


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8"
    )


def fixture(tmp_path: Path) -> dict[str, Path | str]:
    cards = {
        "r1": [
            card("tr-root", "task-one", None),
            card("tr-a", "task-one", "tr-root"),
            card("tr-b", "task-one", "tr-root"),
            card("tr-c", "task-one", "tr-a"),
        ],
        "r2": [
            card("tr2-root", "task-one", None),
            card("tr2-a", "task-one", "tr2-root"),
        ],
        "h1": [
            card("te-root", "task-one", None),
            card("te-a", "task-one", "te-root"),
            card("te-b", "task-one", "te-root"),
            card("te-c", "task-one", "te-a"),
        ],
        "h2": [
            card("te2-root", "task-one", None),
            card("te2-a", "task-one", "te2-root"),
        ],
    }
    card_path = tmp_path / "cards.json"
    card_path.write_text(json.dumps(cards, sort_keys=True), encoding="utf-8")
    split_path = tmp_path / "split.json"
    split_path.write_text(
        json.dumps({"all": ["r1", "r2", "h1", "h2"], "hold": ["h1", "h2"]}),
        encoding="utf-8",
    )
    rows = [
        decision("tr-a", "tr-b", "tr-root", "train"),
        decision("tr-b", "tr-c", "tr-root", "train"),
        decision("tr-a", "tr2-a", "tr-root", "train"),
        decision("te-a", "te-b", "te-root", "test"),
        decision("te-b", "te-c", "te-root", "test"),
        decision("te-a", "te2-a", "te-root", "test"),
    ]
    decision_path = tmp_path / "decision.jsonl"
    write_jsonl(decision_path, rows)
    protocol = {
        "protocol": producer.PROTOCOL,
        "status": producer.STATUS,
        "source": {
            "senior_branch_commit": "1" * 40,
        },
        "immutable_inputs": {
            "cards": {"sha256": digest(card_path)},
            "run_split": {
                "sha256": digest(split_path),
                "all_runs_reported": 4,
                "held_runs_reported": 2,
            },
            "decision": {
                "sha256": digest(decision_path),
                "rows": 6,
                "train_rows": 3,
                "test_rows": 3,
            },
        },
        "known_before_freeze": {
            "overall_rows_seen": 6,
            "overall_direct_sibling_rows_seen": 2,
            "overall_declared_context_same_run_rows_seen": 4,
            "overall_same_task_rows_seen": 6,
            "split_specific_class_counts_seen": False,
            "test_verified_sibling_task_run_endpoint_component_breadth_seen": False,
            "per_class_train_test_mix_seen": False,
            "per_class_dependency_concentration_seen": False,
            "per_class_identity_fingerprints_seen": False,
        },
        "fixed_taxonomy": {"class_order": list(producer.CLASSES)},
        "verified_sibling_test_support_gates": {
            "minimum_pairs": 1,
            "minimum_tasks": 1,
            "minimum_physical_runs": 1,
            "minimum_endpoints": 2,
            "minimum_components": 1,
            "maximum_single_task_pair_share": "1/1",
            "maximum_single_run_pair_share": "1/1",
            "maximum_single_component_pair_share": "1/1",
        },
    }
    protocol_path = tmp_path / "protocol.json"
    protocol_path.write_text(json.dumps(protocol, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return {
        "cards": card_path,
        "run_split": split_path,
        "decision": decision_path,
        "protocol": protocol_path,
        "protocol_sha256": digest(protocol_path),
    }


def namespace(data: dict[str, Path | str]) -> argparse.Namespace:
    return argparse.Namespace(**data)


def refresh_protocol(data: dict[str, Path | str], mutate) -> None:
    protocol_path = data["protocol"]
    assert isinstance(protocol_path, Path)
    value = json.loads(protocol_path.read_text(encoding="utf-8"))
    mutate(value)
    protocol_path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    data["protocol_sha256"] = digest(protocol_path)


def test_three_way_taxonomy_has_broad_verified_sibling_core(tmp_path: Path) -> None:
    data = fixture(tmp_path)
    result = producer.audit(namespace(data))
    assert result["classification"] == (
        "HISTORICAL_RELATION_AWARE_DECISION_TAXONOMY_BROAD_VERIFIED_SIBLING_CORE"
    )
    assert result["semantic_class_counts"] == {
        "verified_direct_sibling": {"total": 2, "train": 1, "test": 1},
        "same_run_declared_context_non_sibling": {"total": 2, "train": 1, "test": 1},
        "cross_run_declared_context": {"total": 2, "train": 1, "test": 1},
    }
    assert all(result["hard_integrity_gates"].values())
    assert all(result["verified_sibling_test_support_gates"].values())
    assert verifier.recompute(namespace(data)) == result


def test_output_is_aggregate_only_and_orientation_free(tmp_path: Path) -> None:
    data = fixture(tmp_path)
    result = producer.audit(namespace(data))
    serialized = json.dumps(result, sort_keys=True)
    for identity in ("tr-a", "te-a", "tr-root", "task-one", "r1", "h1"):
        assert identity not in serialized
    assert result["scope"]["pair_orientation_used_by_taxonomy"] is False
    assert result["split_integrity"]["train_test_referenced_physical_run_overlap"] == 0


def test_parent_partition_mismatch_is_reported_as_frozen_gate_failure(tmp_path: Path) -> None:
    data = fixture(tmp_path)
    decision_path = data["decision"]
    assert isinstance(decision_path, Path)
    rows = [json.loads(line) for line in decision_path.read_text(encoding="utf-8").splitlines()]
    rows[2]["parent"] = "te-root"
    write_jsonl(decision_path, rows)
    refresh_protocol(
        data,
        lambda value: value["immutable_inputs"]["decision"].update(
            {"sha256": digest(decision_path)}
        ),
    )
    result = producer.audit(namespace(data))
    assert result["hard_integrity_gates"][
        "all_decision_endpoints_parent_tasks_and_splits_valid"
    ] is False
    assert result["classification"] == (
        "HISTORICAL_RELATION_AWARE_DECISION_TAXONOMY_INTEGRITY_GATE_FAIL"
    )
    assert verifier.recompute(namespace(data)) == result


def test_insufficient_test_sibling_support_cannot_be_rescued(tmp_path: Path) -> None:
    data = fixture(tmp_path)
    refresh_protocol(
        data,
        lambda value: value["verified_sibling_test_support_gates"].update(
            {"minimum_pairs": 2}
        ),
    )
    result = producer.audit(namespace(data))
    assert all(result["hard_integrity_gates"].values())
    assert result["verified_sibling_test_support_gates"]["minimum_pairs"] is False
    assert result["classification"] == (
        "HISTORICAL_RELATION_AWARE_DECISION_TAXONOMY_LIMITED_VERIFIED_SIBLING_CORE"
    )


def test_reversed_duplicate_is_not_hidden_by_taxonomy(tmp_path: Path) -> None:
    data = fixture(tmp_path)
    decision_path = data["decision"]
    assert isinstance(decision_path, Path)
    rows = [json.loads(line) for line in decision_path.read_text(encoding="utf-8").splitlines()]
    rows.append(decision("te-b", "te-a", "te-root", "test"))
    write_jsonl(decision_path, rows)

    def update(value: dict) -> None:
        value["immutable_inputs"]["decision"].update(
            {"sha256": digest(decision_path), "rows": 7, "test_rows": 4}
        )
        value["known_before_freeze"].update(
            {
                "overall_rows_seen": 7,
                "overall_direct_sibling_rows_seen": 3,
                "overall_declared_context_same_run_rows_seen": 5,
                "overall_same_task_rows_seen": 7,
            }
        )

    refresh_protocol(data, update)
    result = producer.audit(namespace(data))
    assert result["split_integrity"]["duplicate_unordered_pair_rows"] == 1
    assert result["split_integrity"]["conflicting_orientation_unordered_pairs"] == 1
    assert result["hard_integrity_gates"]["unordered_pair_duplicates_zero"] is False
    assert result["hard_integrity_gates"]["conflicting_orientations_zero"] is False
    assert result["classification"] == (
        "HISTORICAL_RELATION_AWARE_DECISION_TAXONOMY_INTEGRITY_GATE_FAIL"
    )
    assert verifier.recompute(namespace(data)) == result


def test_input_hash_drift_fails_closed(tmp_path: Path) -> None:
    data = fixture(tmp_path)
    decision_path = data["decision"]
    assert isinstance(decision_path, Path)
    decision_path.write_text(decision_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(producer.TaxonomyError, match="input SHA"):
        producer.audit(namespace(data))
    with pytest.raises(verifier.VerificationError, match="input hash"):
        verifier.recompute(namespace(data))
