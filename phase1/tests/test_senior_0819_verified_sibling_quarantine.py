from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pytest

from phase1 import audit_senior_0819_decision_relation_taxonomy as parent_producer
from phase1 import audit_senior_0819_verified_sibling_quarantine as producer
from phase1 import verify_senior_0819_verified_sibling_quarantine as verifier


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


def card(identifier: str, task: str, parent: str | None) -> dict:
    return {"id": identifier, "task": {"name": task}, "lineage": {"parent_id": parent}}


def decision(better: str, worse: str, parent: str, split: str) -> dict:
    return {
        **DECISION_DEFAULTS,
        "better": better,
        "worse": worse,
        "parent": parent,
        "task": "task-one",
        "intask_split": split,
    }


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def build_fixture(tmp_path: Path, reversed_core_duplicate: bool = False) -> dict[str, Path | str]:
    cards = {
        "r1": [
            card("tr-root", "task-one", None),
            card("tr-a", "task-one", "tr-root"),
            card("tr-b", "task-one", "tr-root"),
            card("tr-c", "task-one", "tr-a"),
        ],
        "r2": [card("tr2-root", "task-one", None), card("tr2-a", "task-one", "tr2-root")],
        "h1": [
            card("te-root", "task-one", None),
            card("te-a", "task-one", "te-root"),
            card("te-b", "task-one", "te-root"),
            card("te-c", "task-one", "te-a"),
        ],
        "h2": [card("te2-root", "task-one", None), card("te2-a", "task-one", "te2-root")],
    }
    cards_path = tmp_path / "cards.json"
    cards_path.write_text(json.dumps(cards, sort_keys=True), encoding="utf-8")
    split_path = tmp_path / "split.json"
    split_path.write_text(
        json.dumps({"all": ["r1", "r2", "h1", "h2"], "hold": ["h1", "h2"]}),
        encoding="utf-8",
    )
    rows = [
        decision("tr-a", "tr-b", "tr-root", "train"),
        decision("tr-b", "tr-c", "tr-root", "train"),
        decision("tr-a", "tr2-a", "te-root", "train"),
        decision("te-a", "te-b", "te-root", "test"),
        decision("te-b", "te-c", "te-root", "test"),
        decision("te-a", "te2-a", "tr-root", "test"),
    ]
    if reversed_core_duplicate:
        rows.append(decision("te-b", "te-a", "te-root", "test"))
    decision_path = tmp_path / "decision.jsonl"
    write_jsonl(decision_path, rows)

    direct = 3 if reversed_core_duplicate else 2
    same_run = 5 if reversed_core_duplicate else 4
    taxonomy_protocol = {
        "protocol": parent_producer.PROTOCOL,
        "status": parent_producer.STATUS,
        "source": {"senior_branch_commit": "1" * 40},
        "immutable_inputs": {
            "cards": {"sha256": digest(cards_path)},
            "run_split": {
                "sha256": digest(split_path),
                "all_runs_reported": 4,
                "held_runs_reported": 2,
            },
            "decision": {
                "sha256": digest(decision_path),
                "rows": len(rows),
                "train_rows": 3,
                "test_rows": len(rows) - 3,
            },
        },
        "known_before_freeze": {
            "overall_rows_seen": len(rows),
            "overall_direct_sibling_rows_seen": direct,
            "overall_declared_context_same_run_rows_seen": same_run,
            "overall_same_task_rows_seen": len(rows),
            "split_specific_class_counts_seen": False,
            "test_verified_sibling_task_run_endpoint_component_breadth_seen": False,
            "per_class_train_test_mix_seen": False,
            "per_class_dependency_concentration_seen": False,
            "per_class_identity_fingerprints_seen": False,
        },
        "fixed_taxonomy": {"class_order": list(parent_producer.CLASSES)},
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
    taxonomy_protocol_path = tmp_path / "taxonomy_protocol.json"
    taxonomy_protocol_path.write_text(
        json.dumps(taxonomy_protocol, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    parent_args = argparse.Namespace(
        protocol=taxonomy_protocol_path,
        protocol_sha256=digest(taxonomy_protocol_path),
        cards=cards_path,
        run_split=split_path,
        decision=decision_path,
    )
    parent_summary = parent_producer.audit(parent_args)
    assert parent_summary["classification"] == (
        "HISTORICAL_RELATION_AWARE_DECISION_TAXONOMY_INTEGRITY_GATE_FAIL"
    )
    parent_summary_path = tmp_path / "parent_summary.json"
    parent_summary_path.write_text(
        json.dumps(parent_summary, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    parent_verification = {
        "all_aggregate_fields_equal": True,
        "producer_result_sha256": digest(parent_summary_path),
    }
    parent_verification_path = tmp_path / "parent_verification.json"
    parent_verification_path.write_text(
        json.dumps(parent_verification, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    parent_package_manifest_path = tmp_path / "parent_package_manifest.sha256"
    parent_package_manifest_path.write_text("synthetic-parent-package-manifest\n", encoding="utf-8")

    profiles = parent_summary["split_class_profiles"]
    known_test = profiles["test"][producer.CORE]
    protocol = {
        "protocol": producer.PROTOCOL,
        "status": producer.STATUS,
        "source": {
            "senior_branch_commit": "1" * 40,
            "relation_taxonomy_protocol_sha256": digest(taxonomy_protocol_path),
            "relation_taxonomy_formal_summary_sha256": digest(parent_summary_path),
            "relation_taxonomy_independent_verification_sha256": digest(
                parent_verification_path
            ),
            "relation_taxonomy_formal_manifest_sha256": "2" * 64,
            "published_certificate_commit": "3" * 40,
            "published_package_manifest_sha256": digest(parent_package_manifest_path),
        },
        "immutable_inputs": taxonomy_protocol["immutable_inputs"],
        "known_before_freeze": {
            "relation_class_counts_seen": parent_summary["semantic_class_counts"],
            "full_file_referenced_run_overlap_seen": parent_summary["split_integrity"][
                "train_test_referenced_physical_run_overlap"
            ],
            "test_sibling_support_seen": {
                "pairs": known_test["pairs"],
                "tasks": known_test["tasks"],
                "physical_runs": known_test["physical_runs"],
                "endpoints": known_test["endpoints"],
                "components": known_test["components"],
                "maximum_single_task_pair_share": "1/1",
                "maximum_single_run_pair_share": "1/1",
                "maximum_single_component_pair_share": "1/1",
            },
            "sibling_only_parent_partition_closure_seen": False,
            "sibling_only_train_test_referenced_run_overlap_seen": False,
            "parent_partition_mismatch_counts_by_relation_and_split_seen": False,
            "quarantine_exhaustiveness_and_fingerprints_seen": False,
        },
        "fixed_selection": {
            "core_name": "verified_direct_sibling_core",
            "pair_orientation_used": False,
            "row_level_release_created": False,
        },
        "descriptive_support_compatibility_gates": {
            "minimum_test_pairs": 1,
            "minimum_test_tasks": 1,
            "minimum_test_physical_runs": 1,
            "minimum_test_endpoints": 2,
            "minimum_test_components": 1,
            "maximum_single_test_task_pair_share": "1/1",
            "maximum_single_test_run_pair_share": "1/1",
            "maximum_single_test_component_pair_share": "1/1",
        },
        "claim_boundary": {"support_counts_were_known_before_this_freeze": True},
    }
    protocol_path = tmp_path / "protocol.json"
    protocol_path.write_text(
        json.dumps(protocol, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    return {
        "protocol": protocol_path,
        "protocol_sha256": digest(protocol_path),
        "cards": cards_path,
        "run_split": split_path,
        "decision": decision_path,
        "parent_summary": parent_summary_path,
        "parent_verification": parent_verification_path,
        "parent_package_manifest": parent_package_manifest_path,
    }


def namespace(data: dict[str, Path | str]) -> argparse.Namespace:
    return argparse.Namespace(**data)


def refresh_protocol(data: dict[str, Path | str], mutate) -> None:
    path = data["protocol"]
    assert isinstance(path, Path)
    value = json.loads(path.read_text(encoding="utf-8"))
    mutate(value)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    data["protocol_sha256"] = digest(path)


def test_quarantine_recovers_partition_closed_sibling_core(tmp_path: Path) -> None:
    data = build_fixture(tmp_path)
    result = producer.audit(namespace(data))
    assert result["classification"] == (
        "HISTORICAL_VERIFIED_SIBLING_CORE_QUARANTINE_FEASIBLE"
    )
    assert result["core_counts"] == {"total": 2, "train": 1, "test": 1}
    assert result["quarantine_counts"] == {"total": 4, "train": 2, "test": 2}
    assert result["parent_partition_mismatch_total"] == 2
    assert result["parent_partition_mismatch_counts"]["cross_run_declared_context"] == {
        "total": 2,
        "train": 1,
        "test": 1,
    }
    assert result["core_split_integrity"][
        "train_test_referenced_physical_run_overlap"
    ] == 0
    assert all(result["hard_integrity_gates"].values())
    assert all(result["descriptive_support_compatibility_gates"].values())
    assert verifier.recompute(namespace(data)) == result


def test_output_is_aggregate_only_and_marks_support_as_known(tmp_path: Path) -> None:
    result = producer.audit(namespace(build_fixture(tmp_path)))
    serialized = json.dumps(result, sort_keys=True)
    for identity in ("tr-a", "te-a", "tr-root", "task-one", "r1", "h1"):
        assert identity not in serialized
    assert result["scope"]["support_counts_known_before_freeze"] is True
    assert result["scope"]["row_level_release_created"] is False
    assert result["scope"]["model_predictions_or_accuracy_read"] is False


def test_reversed_core_duplicate_fails_integrity_gate(tmp_path: Path) -> None:
    data = build_fixture(tmp_path, reversed_core_duplicate=True)
    result = producer.audit(namespace(data))
    assert result["core_split_integrity"]["duplicate_unordered_pair_rows"] == 1
    assert result["core_split_integrity"]["conflicting_orientation_unordered_pairs"] == 1
    assert result["hard_integrity_gates"]["core_unordered_pair_duplicates_zero"] is False
    assert result["hard_integrity_gates"]["core_conflicting_orientations_zero"] is False
    assert result["classification"] == (
        "HISTORICAL_VERIFIED_SIBLING_CORE_QUARANTINE_INTEGRITY_GATE_FAIL"
    )
    assert verifier.recompute(namespace(data)) == result


def test_known_support_threshold_failure_is_not_rescued(tmp_path: Path) -> None:
    data = build_fixture(tmp_path)
    refresh_protocol(
        data,
        lambda value: value["descriptive_support_compatibility_gates"].update(
            {"minimum_test_pairs": 2}
        ),
    )
    result = producer.audit(namespace(data))
    assert all(result["hard_integrity_gates"].values())
    assert result["descriptive_support_compatibility_gates"]["minimum_test_pairs"] is False
    assert result["classification"] == (
        "HISTORICAL_VERIFIED_SIBLING_CORE_QUARANTINE_LIMITED_SUPPORT"
    )


def test_parent_certificate_hash_drift_fails_closed(tmp_path: Path) -> None:
    data = build_fixture(tmp_path)
    path = data["parent_summary"]
    assert isinstance(path, Path)
    path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(producer.QuarantineAuditError, match="parent summary SHA"):
        producer.audit(namespace(data))
    with pytest.raises(verifier.IndependentQuarantineError, match="parent summary hash"):
        verifier.recompute(namespace(data))


def test_input_hash_drift_fails_closed(tmp_path: Path) -> None:
    data = build_fixture(tmp_path)
    path = data["decision"]
    assert isinstance(path, Path)
    path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(producer.QuarantineAuditError, match="input SHA"):
        producer.audit(namespace(data))
    with pytest.raises(verifier.IndependentQuarantineError, match="input hash"):
        verifier.recompute(namespace(data))
