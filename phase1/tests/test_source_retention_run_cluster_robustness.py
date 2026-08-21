from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
from pathlib import Path

import pytest

from phase1 import source_retention_run_cluster_robustness as producer
from phase1 import verify_source_retention_run_cluster_robustness as verifier


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_input(path: Path, *, reverse: bool = False) -> tuple[dict[str, int], list[str]]:
    counts = {"train": 0, "frozen": 0, "extension": 0}
    tasks = [f"task-{index:02d}" for index in range(12)]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=producer.UPSTREAM_FIELDS, lineterminator="\n")
        writer.writeheader()
        for task_index, task in enumerate(tasks):
            for role, runs in (("train", 5), ("frozen", 3), ("extension", 1)):
                effective = 11 - task_index if reverse and role == "frozen" else task_index
                for run_index in range(runs):
                    parents = 2 if role != "extension" else 1
                    for parent_index in range(parents):
                        retained = 30 + 4 * effective + (run_index + parent_index) % 2
                        counts[role] += 1
                        writer.writerow({
                            "role": role,
                            "task": task,
                            "run_id": f"{role}-{task}-run-{run_index}",
                            "parent": f"{role}-{task}-{run_index}-{parent_index}",
                            "pair_rows": 1,
                            "unique_edges": 1,
                            "published_endpoint_count": 2,
                            "declared_set_size": 2,
                            "raw_card_child_count": retained,
                            "finite_card_child_count": retained,
                            "source_declared_size": 100,
                            "source_size_consistent": True,
                            "source_size_not_smaller_than_raw": True,
                            "raw_context_consistent": True,
                            "endpoints_all_finite": True,
                            "endpoint_fidelity": True,
                            "declared_matches_finite": True,
                            "finite_endpoint_coverage": 1.0,
                            "pair_graph_coverage_over_finite": 1.0,
                            "raw_source_retention": retained / 100,
                            "finite_source_retention": retained / 100,
                            "raw_equals_source": False,
                            "finite_equals_source": False,
                            "parent_card_present": True,
                            "parent_context_consistent": True,
                            "parent_children_declared_count": retained,
                            "parent_children_contains_raw": True,
                            "source_size_gt_five": True,
                        })
    return counts, tasks


def write_protocol(path: Path, input_path: Path, counts: dict[str, int], tasks: list[str]) -> None:
    value = {
        "bootstrap_repetitions": 1000,
        "bootstrap_seed": 20260823,
        "expected_parent_rows": sum(counts.values()),
        "expected_role_parent_counts": counts,
        "input_per_parent_sha256": file_sha(input_path),
        "metric": "run_equal_finite_source_retention",
        "minimum_bootstrap_valid_fraction": 0.9,
        "minimum_frozen_runs_per_task": 3,
        "minimum_loto_rho": 0.0,
        "minimum_primary_rho": 0.5,
        "minimum_robust_tasks": 10,
        "minimum_train_runs_per_task": 5,
        "permutation_repetitions": 2000,
        "permutation_seed": 20260824,
        "primary_task_ids": tasks,
        "protocol": producer.PROTOCOL,
        "significance_alpha": 0.05,
    }
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def fixture(tmp_path: Path, *, reverse: bool = False) -> dict[str, Path]:
    paths = {
        "input": tmp_path / "parents.csv",
        "protocol": tmp_path / "protocol.json",
        "a": tmp_path / "artifact_a",
        "b": tmp_path / "artifact_b",
        "va": tmp_path / "verify_a.json",
        "vb": tmp_path / "verify_b.json",
    }
    counts, tasks = write_input(paths["input"], reverse=reverse)
    write_protocol(paths["protocol"], paths["input"], counts, tasks)
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


def test_run_cluster_positive_is_deterministic_and_verified(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    assert producer.run(producer_args(paths, paths["a"])) == 0
    assert producer.run(producer_args(paths, paths["b"])) == 0
    assert tree_bytes(paths["a"]) == tree_bytes(paths["b"])
    summary = json.loads((paths["a"] / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == producer.STATUS_PASS
    assert summary["primary"]["spearman_rho"] > 0.99
    assert all(summary["criteria"].values())
    assert verifier.verify(verifier_args(paths, paths["a"], paths["va"])) == 0
    assert verifier.verify(verifier_args(paths, paths["b"], paths["vb"])) == 0
    assert paths["va"].read_bytes() == paths["vb"].read_bytes()


def test_reversed_run_profile_fails(tmp_path: Path) -> None:
    paths = fixture(tmp_path, reverse=True)
    assert producer.run(producer_args(paths, paths["a"])) == 0
    summary = json.loads((paths["a"] / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == producer.STATUS_FAIL
    assert summary["primary"]["spearman_rho"] < -0.99


def test_verifier_rejects_rehashed_rho_tamper(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    assert producer.run(producer_args(paths, paths["a"])) == 0
    summary_path = paths["a"] / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["primary"]["spearman_rho"] = 0.7
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
    assert all("source_retention_run_cluster_robustness" not in name for name in imports)


def test_formal_protocol_binds_v1_task_universe() -> None:
    root = Path(__file__).resolve().parents[2]
    protocol = json.loads(
        (root / "phase1/source_retention_run_cluster_protocol_v1.json").read_text(encoding="utf-8")
    )
    assert protocol["expected_parent_rows"] == 3252
    assert len(protocol["primary_task_ids"]) == 15
    assert protocol["minimum_train_runs_per_task"] == 5
    assert protocol["minimum_frozen_runs_per_task"] == 3
    assert protocol["minimum_robust_tasks"] == 10
    assert protocol["bootstrap_repetitions"] == 20000
    assert protocol["permutation_repetitions"] == 100000
