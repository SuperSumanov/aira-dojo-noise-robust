import copy
import csv
import hashlib
import json
from pathlib import Path

import pytest

from phase1 import export_status_certified_edges as producer
from phase1 import verify_status_certified_edges as verifier


COMMIT = "7" * 40


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalized_sha(path: Path) -> str:
    text = path.read_bytes().decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parent_row(role: str, task: str, run: str, parent: str) -> dict[str, str]:
    row = {field: "" for field in producer.UPSTREAM_FIELDS}
    row.update(
        {
            "role": role,
            "task": task,
            "run_id": run,
            "parent": parent,
            "pair_rows": "1",
            "unique_edges": "1",
            "published_endpoint_count": "2",
            "declared_set_size": "2",
            "raw_card_child_count": "2",
            "finite_card_child_count": "2",
            "source_declared_size": "3",
            "source_size_consistent": "True",
            "source_size_not_smaller_than_raw": "True",
            "raw_context_consistent": "True",
            "endpoints_all_finite": "True",
            "endpoint_fidelity": "True",
            "declared_matches_finite": "True",
            "finite_endpoint_coverage": "1.0",
            "pair_graph_coverage_over_finite": "1.0",
            "raw_source_retention": "0.6666666666666666",
            "finite_source_retention": "0.6666666666666666",
            "raw_equals_source": "False",
            "finite_equals_source": "False",
            "parent_card_present": "True",
            "parent_context_consistent": "True",
            "parent_children_declared_count": "3",
            "parent_children_contains_raw": "True",
            "source_size_gt_five": "False",
        }
    )
    return row


def status_row(child: str, parent: str, role: str, category: str) -> dict:
    return {
        "category": category,
        "child_id": child,
        "expected_parent_id": parent,
        "journal_parent_id": parent,
        "parent_match": True,
        "role": role,
        "source_journal_sha256": "a" * 64,
        "status": "UNIQUE_NODE_RECOVERED",
    }


def make_fixture(tmp_path: Path, status_rows: list[dict] | None = None) -> dict[str, Path]:
    root = tmp_path / "repo"
    root.mkdir()
    parent_path = tmp_path / "parents.csv"
    rows = [
        parent_row("train", "task-a", "run-a", "parent-a"),
        parent_row("frozen", "task-b", "run-b", "parent-b"),
        parent_row("extension", "task-c", "run-c", "parent-c"),
    ]
    with parent_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=producer.UPSTREAM_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    pair_paths: dict[str, Path] = {}
    for role, task, parent, prefix in (
        ("train", "task-a", "parent-a", "t"),
        ("frozen", "task-b", "parent-b", "f"),
        ("extension", "task-c", "parent-c", "e"),
    ):
        path = root / f"{role}.jsonl"
        path.write_text(
            json.dumps(
                {
                    "task": task,
                    "parent": parent,
                    "better": f"{prefix}-left",
                    "worse": f"{prefix}-right",
                    "budget": 0,
                    "gap_raw": 123.0,
                },
                sort_keys=True,
            ) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        pair_paths[role] = path

    statuses = status_rows or [
        status_row("bad-a", "parent-a", "train", "EXECUTION_ERROR"),
        status_row("bad-b", "parent-b", "frozen", "OFFICIAL_GRADE_ABSENT"),
    ]
    status_path = tmp_path / "status.jsonl"
    status_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in statuses),
        encoding="utf-8",
        newline="\n",
    )
    formal_path = root / "formal.json"
    formal_path.write_text(
        json.dumps(
            {
                "status": "VERIFIED_MATERIAL_STATUS_CERTIFIED_RELATION_RECOVERY",
                "overall": {"validity_dominance_edges": 4},
            },
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    protocol = {
        "protocol": producer.PROTOCOL,
        "expected_certified_invalid_children": len(statuses),
        "expected_parent_rows": 3,
        "expected_published_edges": 3,
        "expected_role_pair_rows": {"train": 1, "frozen": 1, "extension": 1},
        "expected_source_pair_capacity": 9,
        "expected_validity_edges": len(statuses) * 2,
        "formal_summary_path": "formal.json",
        "formal_summary_sha256_normalized_lf": normalized_sha(formal_path),
        "input_per_parent_sha256": sha(parent_path),
        "input_status_sha256": sha(status_path),
        "material_min_added_relations": 1,
        "material_min_frozen_coverage_gain": 0.0,
        "material_min_gap_recovery_share": 0.1,
        "material_min_overall_coverage_gain": 0.1,
        "material_min_train_coverage_gain": 0.1,
        "maximum_dominant_added_relation_task_share": 1.0,
        "minimum_supported_tasks": 1,
        "minimum_task_source_pair_capacity": 1,
        "minimum_tasks_with_positive_gain": 1,
        "pair_inputs": {
            role: {
                "path": path.name,
                "sha256_normalized_lf": normalized_sha(path),
            }
            for role, path in pair_paths.items()
        },
    }
    protocol_path = tmp_path / "protocol.json"
    protocol_path.write_text(json.dumps(protocol, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "root": root,
        "parents": parent_path,
        "status": status_path,
        "protocol": protocol_path,
    }


def build(paths: dict[str, Path], output: Path) -> dict:
    protocol = producer.load_protocol(paths["protocol"], paths["root"])
    parents = producer.load_parent_rows(paths["parents"], protocol)
    endpoints = producer.load_endpoint_sets(protocol, paths["root"], parents)
    invalid = producer.load_certified_invalid(paths["status"], protocol, parents)
    edges = producer.build_edges(invalid, endpoints, parents)
    summary = producer.summarize(edges, parents, protocol, COMMIT)
    producer.write_outputs(output, edges, summary)
    return summary


def test_explicit_edges_and_execution_error_sensitivity(tmp_path: Path):
    paths = make_fixture(tmp_path)
    output = tmp_path / "artifact"
    summary = build(paths, output)
    edges = [json.loads(line) for line in (output / "edges.jsonl").read_text().splitlines()]
    assert len(edges) == 4
    assert {row["relation"] for row in edges} == {"VALIDITY_DOMINANCE"}
    assert summary["by_category"] == {"EXECUTION_ERROR": 2, "OFFICIAL_GRADE_ABSENT": 2}
    sensitivity = summary["execution_error_only_sensitivity"]
    assert sensitivity["overall"]["validity_dominance_edges"] == 2
    assert sensitivity["roles"]["frozen"]["validity_dominance_edges"] == 0
    assert sensitivity["preserves_all_original_material_gates"] is True


def test_independent_verifier_reconstructs_every_edge(tmp_path: Path):
    paths = make_fixture(tmp_path)
    output = tmp_path / "artifact"
    build(paths, output)
    receipt = verifier.verify(
        paths["root"], paths["protocol"], paths["parents"], paths["status"], COMMIT, output
    )
    assert receipt["status"] == verifier.VERIFY_STATUS
    assert receipt["edge_count"] == 4
    assert receipt["maximum_reconstruction_difference"] == 0
    assert receipt["pair_orientation_direction_used"] is False


def test_independent_verifier_rejects_edge_drift(tmp_path: Path):
    paths = make_fixture(tmp_path)
    output = tmp_path / "artifact"
    build(paths, output)
    edge_path = output / "edges.jsonl"
    rows = edge_path.read_text(encoding="utf-8").splitlines()
    changed = json.loads(rows[0])
    changed["valid_child_id"] = "tampered"
    rows[0] = json.dumps(changed, sort_keys=True)
    edge_path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    with pytest.raises(verifier.VerificationError, match="edge manifest differs"):
        verifier.verify(
            paths["root"], paths["protocol"], paths["parents"], paths["status"], COMMIT, output
        )


def test_certified_invalid_endpoint_overlap_is_rejected(tmp_path: Path):
    overlap = status_row("t-left", "parent-a", "train", "EXECUTION_ERROR")
    absent = status_row("bad-b", "parent-b", "frozen", "OFFICIAL_GRADE_ABSENT")
    paths = make_fixture(tmp_path, [overlap, absent])
    protocol = producer.load_protocol(paths["protocol"], paths["root"])
    parents = producer.load_parent_rows(paths["parents"], protocol)
    endpoints = producer.load_endpoint_sets(protocol, paths["root"], parents)
    invalid = producer.load_certified_invalid(paths["status"], protocol, parents)
    with pytest.raises(producer.ExportError, match="appears among finite endpoints"):
        producer.build_edges(invalid, endpoints, parents)


def test_orientation_swap_does_not_change_reconstructed_edges(tmp_path: Path):
    paths = make_fixture(tmp_path)
    protocol = producer.load_protocol(paths["protocol"], paths["root"])
    parents = producer.load_parent_rows(paths["parents"], protocol)
    before = producer.load_endpoint_sets(protocol, paths["root"], parents)
    train_path = paths["root"] / "train.jsonl"
    row = json.loads(train_path.read_text(encoding="utf-8"))
    row["better"], row["worse"] = row["worse"], row["better"]
    train_path.write_text(json.dumps(row, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    protocol_value = copy.deepcopy(protocol)
    protocol_value["pair_inputs"]["train"]["sha256_normalized_lf"] = normalized_sha(train_path)
    paths["protocol"].write_text(json.dumps(protocol_value, sort_keys=True) + "\n", encoding="utf-8")
    after_protocol = producer.load_protocol(paths["protocol"], paths["root"])
    after = producer.load_endpoint_sets(after_protocol, paths["root"], parents)
    assert before == after
