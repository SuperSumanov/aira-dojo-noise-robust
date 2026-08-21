import csv
import json
from argparse import Namespace
from pathlib import Path

import pytest

from phase1.source_decision_answerability import (
    AnswerabilityError,
    STATUS_PASS,
    UPSTREAM_FIELDS,
    digest,
    graph_summary,
    normalized_lf_digest,
    run,
)
from phase1.verify_source_decision_answerability import verify


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def make_inputs(tmp_path: Path) -> dict[str, object]:
    parent_path = tmp_path / "parents.csv"
    identity_path = tmp_path / "identity.jsonl"
    status_path = tmp_path / "status_edges.jsonl"
    pair_paths = {role: tmp_path / f"pairs_{role}.jsonl" for role in ("train", "frozen", "extension")}
    parent_specs = [
        ("train", "task-a", "run-1", "parent-1", 3, 3, 2),
        ("train", "task-a", "run-2", "parent-2", 3, 2, 1),
        ("frozen", "task-b", "run-3", "parent-3", 3, 2, 1),
    ]
    with parent_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=UPSTREAM_FIELDS, lineterminator="\n")
        writer.writeheader()
        for role, task, run_id, parent, source, finite, edges in parent_specs:
            row = {field: "" for field in UPSTREAM_FIELDS}
            row.update(
                {
                    "role": role,
                    "task": task,
                    "run_id": run_id,
                    "parent": parent,
                    "pair_rows": edges,
                    "unique_edges": edges,
                    "published_endpoint_count": finite,
                    "declared_set_size": finite,
                    "raw_card_child_count": finite,
                    "finite_card_child_count": finite,
                    "source_declared_size": source,
                    "source_size_consistent": "True",
                    "source_size_not_smaller_than_raw": "True",
                    "raw_context_consistent": "True",
                    "endpoints_all_finite": "True",
                    "endpoint_fidelity": "True",
                    "declared_matches_finite": "True",
                    "parent_context_consistent": "True",
                }
            )
            writer.writerow(row)
    identities = [
        {
            "role": "train",
            "parent": "parent-1",
            "source_declared_size": 3,
            "retained_child_count": 3,
            "source_incomplete": False,
            "exact_identity_recoverable": True,
            "missing_identity_count": 0,
            "missing_child_ids": [],
        },
        {
            "role": "train",
            "parent": "parent-2",
            "source_declared_size": 3,
            "retained_child_count": 2,
            "source_incomplete": True,
            "exact_identity_recoverable": True,
            "missing_identity_count": 1,
            "missing_child_ids": ["f"],
        },
        {
            "role": "frozen",
            "parent": "parent-3",
            "source_declared_size": 3,
            "retained_child_count": 2,
            "source_incomplete": True,
            "exact_identity_recoverable": False,
            "missing_identity_count": 0,
            "missing_child_ids": [],
        },
    ]
    identity_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in identities),
        encoding="utf-8",
    )
    pairs = {
        "train": [
            {"task": "task-a", "run_id": "run-1", "parent": "parent-1", "better": "a", "worse": "b"},
            {"task": "task-a", "run_id": "run-1", "parent": "parent-1", "better": "b", "worse": "c"},
            {"task": "task-a", "run_id": "run-2", "parent": "parent-2", "better": "d", "worse": "e"},
        ],
        "frozen": [
            {"task": "task-b", "run_id": "run-3", "parent": "parent-3", "better": "g", "worse": "h"}
        ],
        "extension": [],
    }
    for role, rows in pairs.items():
        pair_paths[role].write_text(
            "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
            encoding="utf-8",
        )
    status_rows = [
        {
            "role": "train",
            "task": "task-a",
            "run_id": "run-2",
            "parent": "parent-2",
            "valid_child_id": child,
            "invalid_child_id": "f",
            "invalid_category": "EXECUTION_ERROR",
            "relation": "VALIDITY_DOMINANCE",
        }
        for child in ("d", "e")
    ]
    status_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in status_rows),
        encoding="utf-8",
    )
    protocol = {
        "protocol": "source-decision-answerability-v1",
        "input_per_parent_sha256": digest(parent_path),
        "input_identity_sha256": digest(identity_path),
        "input_status_edges_sha256": digest(status_path),
        "pair_inputs": {
            role: {"sha256_normalized_lf": normalized_lf_digest(path), "path": str(path)}
            for role, path in pair_paths.items()
        },
        "expected_parent_rows": 3,
        "expected_identity_rows": 3,
        "expected_published_edges": 4,
        "expected_role_parent_counts": {"train": 2, "frozen": 1, "extension": 0},
        "expected_role_pair_counts": {"train": 3, "frozen": 1, "extension": 0},
        "expected_validity_edges": 2,
        "expected_certified_invalid_children": 1,
        "expected_validity_edge_categories": {"EXECUTION_ERROR": 2},
        "certifiable_categories": ["EXECUTION_ERROR", "OFFICIAL_GRADE_ABSENT"],
        "material_min_newly_identified_parents": 1,
        "material_min_overall_winner_rate_gain": 0.3,
        "material_min_train_winner_rate_gain": 0.4,
        "material_min_frozen_winner_rate_gain": 0.0,
        "material_min_status_winner_rate": 0.6,
        "minimum_supported_tasks": 1,
        "minimum_task_source_pair_capacity": 1,
        "minimum_tasks_with_positive_gain": 1,
        "maximum_dominant_added_winner_task_share": 1.0,
    }
    protocol_path = tmp_path / "protocol.json"
    write_json(protocol_path, protocol)
    return {
        "parent": parent_path,
        "identity": identity_path,
        "status": status_path,
        "pairs": pair_paths,
        "protocol": protocol_path,
    }


def args_for(inputs: dict[str, object], output: Path) -> Namespace:
    pair_paths = inputs["pairs"]
    assert isinstance(pair_paths, dict)
    return Namespace(
        protocol=str(inputs["protocol"]),
        per_parent=str(inputs["parent"]),
        identity_registry=str(inputs["identity"]),
        status_edges=str(inputs["status"]),
        pair=[f"{role}={pair_paths[role]}" for role in ("train", "frozen", "extension")],
        source_commit="0" * 40,
        output=str(output),
    )


def test_answerability_recovery_and_independent_verifier(tmp_path: Path) -> None:
    inputs = make_inputs(tmp_path)
    artifact = tmp_path / "artifact"
    args = args_for(inputs, artifact)
    assert run(args) == 0
    summary = json.loads((artifact / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == STATUS_PASS
    assert summary["overall"]["published_winners"] == 1
    assert summary["overall"]["status_winners"] == 2
    assert summary["overall"]["newly_identified_by_status"] == 1
    assert summary["overall"]["execution_only_winners"] == 2
    verification = verify(
        Namespace(
            **{key: value for key, value in vars(args).items() if key != "output"},
            artifact=str(artifact),
        )
    )
    assert verification["status"] == "INDEPENDENT_SOURCE_DECISION_ANSWERABILITY_VERIFIED"
    assert verification["producer_status"] == STATUS_PASS
    assert verification["producer_imported"] is False


def test_unknown_source_identity_never_becomes_answerable(tmp_path: Path) -> None:
    inputs = make_inputs(tmp_path)
    artifact = tmp_path / "artifact"
    assert run(args_for(inputs, artifact)) == 0
    with (artifact / "per_parent.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    frozen = next(row for row in rows if row["role"] == "frozen")
    assert frozen["source_identity_available"] == "False"
    assert frozen["published_winner_identified"] == "False"
    assert frozen["status_winner_identified"] == "False"
    assert frozen["published_top_set_size"] == ""


def test_transitive_closure_identifies_unique_winner() -> None:
    result = graph_summary({"a", "b", "c"}, {("a", "b"), ("b", "c")})
    assert result["direct_relations"] == 2
    assert result["transitive_relations"] == 3
    assert result["top_set_size"] == 1
    assert result["winner"] == "a"


def test_cycle_fails_closed() -> None:
    with pytest.raises(AnswerabilityError, match="cycle"):
        graph_summary({"a", "b"}, {("a", "b"), ("b", "a")})


def test_manifest_tamper_is_detected(tmp_path: Path) -> None:
    inputs = make_inputs(tmp_path)
    artifact = tmp_path / "artifact"
    args = args_for(inputs, artifact)
    assert run(args) == 0
    with (artifact / "per_parent.csv").open("a", encoding="utf-8") as handle:
        handle.write("tamper\n")
    with pytest.raises(Exception, match="manifest"):
        verify(
            Namespace(
                **{key: value for key, value in vars(args).items() if key != "output"},
                artifact=str(artifact),
            )
        )
