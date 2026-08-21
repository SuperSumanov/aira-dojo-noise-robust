from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
from pathlib import Path

import pytest

from phase1 import decision_observability_funnel as producer
from phase1 import verify_decision_observability_funnel as verifier


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_input(path: Path, *, attrition: bool = True) -> tuple[dict[str, int], list[str]]:
    tasks = [f"task-{index:02d}" for index in range(12)]
    counts = {"train": 0, "frozen": 0, "extension": 0}
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=producer.UPSTREAM_FIELDS, lineterminator="\n")
        writer.writeheader()
        for task in tasks:
            for role, parent_count in (("train", 3), ("frozen", 3), ("extension", 1)):
                for parent_index in range(parent_count):
                    source = 6
                    raw_count = 4 if attrition else 6
                    finite = 3 if attrition else 6
                    endpoints = finite
                    edges = 1 if attrition else producer.comb2(finite)
                    counts[role] += 1
                    writer.writerow({
                        "role": role,
                        "task": task,
                        "run_id": f"{role}-{task}-run-{parent_index}",
                        "parent": f"{role}-{task}-parent-{parent_index}",
                        "pair_rows": edges,
                        "unique_edges": edges,
                        "published_endpoint_count": endpoints,
                        "declared_set_size": endpoints,
                        "raw_card_child_count": raw_count,
                        "finite_card_child_count": finite,
                        "source_declared_size": source,
                        "source_size_consistent": True,
                        "source_size_not_smaller_than_raw": True,
                        "raw_context_consistent": True,
                        "endpoints_all_finite": True,
                        "endpoint_fidelity": True,
                        "declared_matches_finite": True,
                        "finite_endpoint_coverage": endpoints / finite,
                        "pair_graph_coverage_over_finite": edges / producer.comb2(finite),
                        "raw_source_retention": raw_count / source,
                        "finite_source_retention": finite / source,
                        "raw_equals_source": raw_count == source,
                        "finite_equals_source": finite == source,
                        "parent_card_present": True,
                        "parent_context_consistent": True,
                        "parent_children_declared_count": raw_count,
                        "parent_children_contains_raw": True,
                        "source_size_gt_five": True,
                    })
    return counts, tasks


def write_protocol(path: Path, input_path: Path, counts: dict[str, int]) -> None:
    value = {
        "expected_parent_rows": sum(counts.values()),
        "expected_role_parent_counts": counts,
        "input_per_parent_sha256": file_sha(input_path),
        "material_min_finite_pair_loss_share": 0.15,
        "material_min_pair_minus_child_loss_share": 0.03,
        "minimum_supported_tasks": 10,
        "minimum_task_source_pair_capacity": 100,
        "minimum_tasks_with_pair_loss_gt_child_loss": 8,
        "protocol": producer.PROTOCOL,
        "require_train_and_frozen_pair_loss_gt_child_loss": True,
    }
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def fixture(tmp_path: Path, *, attrition: bool = True) -> dict[str, Path]:
    paths = {
        "input": tmp_path / "parents.csv",
        "protocol": tmp_path / "protocol.json",
        "a": tmp_path / "artifact_a",
        "b": tmp_path / "artifact_b",
        "va": tmp_path / "verify_a.json",
        "vb": tmp_path / "verify_b.json",
    }
    counts, _ = write_input(paths["input"], attrition=attrition)
    write_protocol(paths["protocol"], paths["input"], counts)
    return paths


def producer_args(paths: dict[str, Path], output: Path) -> argparse.Namespace:
    return argparse.Namespace(
        protocol=str(paths["protocol"]),
        per_parent=str(paths["input"]),
        source_commit="a" * 40,
        output=str(output),
    )


def verifier_args(paths: dict[str, Path], artifact: Path, output: Path) -> argparse.Namespace:
    return argparse.Namespace(
        artifact=str(artifact),
        protocol=str(paths["protocol"]),
        per_parent=str(paths["input"]),
        source_commit="a" * 40,
        output=str(output),
    )


def tree_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_material_funnel_is_deterministic_and_independently_verified(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    assert producer.run(producer_args(paths, paths["a"])) == 0
    assert producer.run(producer_args(paths, paths["b"])) == 0
    assert tree_bytes(paths["a"]) == tree_bytes(paths["b"])
    summary = json.loads((paths["a"] / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == producer.STATUS_PASS
    assert summary["overall"]["source_to_finite_child_loss_share"] == 0.5
    assert summary["overall"]["source_to_finite_pair_loss_share"] == 0.8
    assert all(summary["criteria"].values())
    assert verifier.verify(verifier_args(paths, paths["a"], paths["va"])) == 0
    assert verifier.verify(verifier_args(paths, paths["b"], paths["vb"])) == 0
    assert paths["va"].read_bytes() == paths["vb"].read_bytes()


def test_no_child_attrition_rejects_material_status(tmp_path: Path) -> None:
    paths = fixture(tmp_path, attrition=False)
    assert producer.run(producer_args(paths, paths["a"])) == 0
    summary = json.loads((paths["a"] / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == producer.STATUS_NO_MATERIAL
    assert summary["claim_allowed"] is False
    assert summary["overall"]["source_to_finite_pair_loss_share"] == 0.0


def test_published_edge_capacity_violation_fails_closed(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    with paths["input"].open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    rows[0]["unique_edges"] = "4"
    rows[0]["pair_rows"] = "4"
    with paths["input"].open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=producer.UPSTREAM_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    protocol = json.loads(paths["protocol"].read_text(encoding="utf-8"))
    protocol["input_per_parent_sha256"] = file_sha(paths["input"])
    paths["protocol"].write_text(
        json.dumps(protocol, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    with pytest.raises(producer.FunnelError, match="published edges exceed capacity"):
        producer.run(producer_args(paths, paths["a"]))


def test_verifier_rejects_rehashed_summary_tamper(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    assert producer.run(producer_args(paths, paths["a"])) == 0
    summary_path = paths["a"] / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["overall"]["finite_pair_capacity"] += 1
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    manifest_path = paths["a"] / "sha256_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["summary.json"] = file_sha(summary_path)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    with pytest.raises(verifier.VerificationError, match="scientific reconstruction"):
        verifier.verify(verifier_args(paths, paths["a"], paths["va"]))


def test_independent_verifier_does_not_import_producer() -> None:
    source = Path(verifier.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    assert all("decision_observability_funnel" not in name for name in imports)


def test_formal_protocol_binds_material_thresholds() -> None:
    root = Path(__file__).resolve().parents[2]
    protocol = json.loads(
        (root / "phase1/decision_observability_funnel_protocol_v1.json").read_text(encoding="utf-8")
    )
    assert protocol["expected_parent_rows"] == 3252
    assert protocol["minimum_task_source_pair_capacity"] == 100
    assert protocol["minimum_supported_tasks"] == 10
    assert protocol["minimum_tasks_with_pair_loss_gt_child_loss"] == 8
    assert protocol["material_min_finite_pair_loss_share"] == 0.15
    assert protocol["material_min_pair_minus_child_loss_share"] == 0.03
