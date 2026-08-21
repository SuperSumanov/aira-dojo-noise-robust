import copy
import csv
import hashlib
import json
from pathlib import Path

import pytest

from phase1 import status_certified_partial_order as producer
from phase1 import verify_status_certified_partial_order as verifier


COMMIT = "1" * 40


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parent_row(role: str, task: str, run: str, parent: str, source: int, finite: int) -> dict[str, str]:
    capacity = finite * (finite - 1) // 2
    row = {field: "" for field in producer.UPSTREAM_FIELDS}
    row.update(
        {
            "role": role,
            "task": task,
            "run_id": run,
            "parent": parent,
            "pair_rows": str(capacity),
            "unique_edges": str(capacity),
            "published_endpoint_count": str(finite),
            "declared_set_size": str(finite),
            "raw_card_child_count": str(finite),
            "finite_card_child_count": str(finite),
            "source_declared_size": str(source),
            "source_size_consistent": "True",
            "source_size_not_smaller_than_raw": "True",
            "raw_context_consistent": "True",
            "endpoints_all_finite": "True",
            "endpoint_fidelity": "True",
            "declared_matches_finite": "True",
            "finite_endpoint_coverage": "1.0",
            "pair_graph_coverage_over_finite": "1.0",
            "raw_source_retention": str(finite / source),
            "finite_source_retention": str(finite / source),
            "raw_equals_source": str(finite == source),
            "finite_equals_source": str(finite == source),
            "parent_card_present": "True",
            "parent_context_consistent": "True",
            "parent_children_declared_count": str(source),
            "parent_children_contains_raw": "True",
            "source_size_gt_five": "False",
        }
    )
    return row


def recovered(child: str, parent: str, role: str, category: str) -> dict:
    return {
        "category": category,
        "child_id": child,
        "expected_parent_id": parent,
        "journal_parent_id": parent,
        "normalization_threshold_present": False,
        "official_grade_present": False,
        "parent_match": True,
        "role": role,
        "source_journal_sha256": "a" * 64,
        "status": "UNIQUE_NODE_RECOVERED",
    }


def unknown(child: str, parent: str, role: str) -> dict:
    return {
        "category": "UNKNOWN",
        "child_id": child,
        "expected_parent_id": parent,
        "journal_parent_id": None,
        "normalization_threshold_present": None,
        "official_grade_present": None,
        "parent_match": False,
        "role": role,
        "source_journal_sha256": None,
        "status": "SOURCE_JOURNAL_NOT_FOUND",
    }


def fixture(tmp_path: Path, statuses: list[dict] | None = None):
    parent_path = tmp_path / "parents.csv"
    parent_rows = [
        parent_row("train", "task-a", "run-a", "parent-a", 3, 2),
        parent_row("train", "task-b", "run-b", "parent-b", 2, 2),
        parent_row("frozen", "task-a", "run-c", "parent-c", 3, 2),
    ]
    with parent_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=producer.UPSTREAM_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(parent_rows)

    status_rows = statuses or [
        recovered("child-a", "parent-a", "train", "EXECUTION_ERROR"),
        recovered("child-c", "parent-c", "frozen", "OFFICIAL_GRADE_ABSENT"),
    ]
    status_path = tmp_path / "status.jsonl"
    status_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in status_rows),
        encoding="utf-8",
        newline="\n",
    )
    status_counts = {}
    category_counts = {}
    for row in status_rows:
        status_counts[row["status"]] = status_counts.get(row["status"], 0) + 1
        category_counts[row["category"]] = category_counts.get(row["category"], 0) + 1
    protocol = {
        "protocol": producer.PROTOCOL,
        "certifiable_categories": ["EXECUTION_ERROR", "OFFICIAL_GRADE_ABSENT"],
        "expected_parent_rows": 3,
        "expected_role_parent_counts": {"train": 2, "frozen": 1, "extension": 0},
        "expected_status_rows": len(status_rows),
        "expected_status_counts": status_counts,
        "expected_status_category_counts": category_counts,
        "input_per_parent_sha256": sha(parent_path),
        "input_status_sha256": sha(status_path),
        "material_min_added_relations": 1,
        "material_min_frozen_coverage_gain": 0.01,
        "material_min_gap_recovery_share": 0.01,
        "material_min_overall_coverage_gain": 0.01,
        "material_min_train_coverage_gain": 0.01,
        "maximum_dominant_added_relation_task_share": 1.0,
        "minimum_supported_tasks": 1,
        "minimum_task_source_pair_capacity": 1,
        "minimum_tasks_with_positive_gain": 1,
    }
    protocol_path = tmp_path / "protocol.json"
    protocol_path.write_text(json.dumps(protocol, sort_keys=True) + "\n", encoding="utf-8")
    return protocol_path, parent_path, status_path


def build(tmp_path: Path, statuses: list[dict] | None = None):
    protocol_path, parent_path, status_path = fixture(tmp_path, statuses)
    protocol = producer.load_protocol(protocol_path)
    parents = producer.load_parents(parent_path, protocol)
    lookup = {(row["role"], row["parent"]): row for row in parents}
    status_map = producer.load_statuses(status_path, protocol, lookup)
    rows = producer.build_parent_rows(parents, status_map)
    summary, aggregates = producer.summarize(rows, protocol, COMMIT)
    return protocol_path, parent_path, status_path, rows, summary, aggregates


def test_material_status_relations_pass_and_account_exactly(tmp_path: Path):
    _, _, _, rows, summary, _ = build(tmp_path)
    assert summary["status"] == producer.STATUS_PASS
    assert summary["overall"]["source_pair_capacity"] == 7
    assert summary["overall"]["published_unique_edges"] == 3
    assert summary["overall"]["validity_dominance_edges"] == 4
    assert summary["overall"]["certified_relations"] == 7
    assert summary["overall"]["lost_relation_recovery"] == 1.0
    assert sum(row["validity_dominance_edges"] for row in rows) == 4


def test_unknown_status_is_not_promoted(tmp_path: Path):
    statuses = [
        recovered("child-a", "parent-a", "train", "EXECUTION_ERROR"),
        unknown("child-c", "parent-c", "frozen"),
    ]
    _, _, _, rows, summary, _ = build(tmp_path, statuses)
    frozen = next(row for row in rows if row["role"] == "frozen")
    assert frozen["unknown_status_children"] == 1
    assert frozen["validity_dominance_edges"] == 0
    assert summary["scope"]["unknown_status_imputed"] is False


def test_duplicate_status_child_is_rejected(tmp_path: Path):
    duplicate = recovered("same-child", "parent-a", "train", "EXECUTION_ERROR")
    protocol_path, parent_path, status_path = fixture(tmp_path, [duplicate, copy.deepcopy(duplicate)])
    protocol = producer.load_protocol(protocol_path)
    parents = producer.load_parents(parent_path, protocol)
    with pytest.raises(producer.PartialOrderError, match="duplicate"):
        producer.load_statuses(
            status_path, protocol, {(row["role"], row["parent"]): row for row in parents}
        )


def test_independent_verifier_reconstructs_every_artifact(tmp_path: Path):
    protocol_path, parent_path, status_path, rows, summary, aggregates = build(tmp_path)
    output = tmp_path / "artifact"
    producer.write_outputs(output, rows, aggregates, summary)
    receipt = verifier.verify(protocol_path, parent_path, status_path, COMMIT, output)
    assert receipt["status"] == "INDEPENDENT_STATUS_CERTIFIED_PARTIAL_ORDER_VERIFIED"
    assert receipt["validity_dominance_edges"] == 4
    assert receipt["maximum_reconstruction_difference"] == 0.0


def test_independent_verifier_rejects_artifact_drift(tmp_path: Path):
    protocol_path, parent_path, status_path, rows, summary, aggregates = build(tmp_path)
    output = tmp_path / "artifact"
    producer.write_outputs(output, rows, aggregates, summary)
    path = output / "summary.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["claim_allowed"] = False
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    with pytest.raises(verifier.VerificationError, match="summary differs"):
        verifier.verify(protocol_path, parent_path, status_path, COMMIT, output)

