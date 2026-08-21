from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
from pathlib import Path

import pytest

from phase1 import source_retention_transport as producer
from phase1 import verify_source_retention_transport as verifier


def write_parent_csv(path: Path, *, reverse_frozen: bool = False) -> dict[str, int]:
    role_counts = {"train": 0, "frozen": 0, "extension": 0}
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=producer.UPSTREAM_FIELDS, lineterminator="\n"
        )
        writer.writeheader()
        for task_index in range(12):
            task = f"task-{task_index:02d}"
            for role, count in (("train", 4), ("frozen", 3), ("extension", 1)):
                role_counts[role] += count
                rate_index = 11 - task_index if reverse_frozen and role == "frozen" else task_index
                retained = 30 + 5 * rate_index
                for row_index in range(count):
                    parent = f"{role}-{task}-{row_index}"
                    writer.writerow(
                        {
                            "role": role,
                            "task": task,
                            "run_id": f"run-{role}-{task}-{row_index}",
                            "parent": parent,
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
                            "raw_equals_source": retained == 100,
                            "finite_equals_source": retained == 100,
                            "parent_card_present": True,
                            "parent_context_consistent": True,
                            "parent_children_declared_count": retained,
                            "parent_children_contains_raw": True,
                            "source_size_gt_five": True,
                        }
                    )
    return role_counts


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_protocol(path: Path, parent_path: Path, role_counts: dict[str, int]) -> None:
    value = {
        "bootstrap_repetitions": 1000,
        "bootstrap_seed": 20260822,
        "expected_parent_rows": sum(role_counts.values()),
        "expected_role_parent_counts": role_counts,
        "input_per_parent_sha256": sha(parent_path),
        "metric": "finite_source_retention",
        "minimum_bootstrap_valid_fraction": 0.9,
        "minimum_common_tasks": 10,
        "minimum_frozen_parents_per_task": 3,
        "minimum_loto_rho": 0.0,
        "minimum_primary_rho": 0.5,
        "minimum_train_parents_per_task": 4,
        "permutation_repetitions": 2000,
        "permutation_seed": 20260821,
        "protocol": producer.PROTOCOL,
        "significance_alpha": 0.05,
    }
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def make_fixture(tmp_path: Path, *, reverse_frozen: bool = False) -> dict[str, Path]:
    paths = {
        "parent": tmp_path / "per_parent.csv",
        "protocol": tmp_path / "protocol.json",
        "artifact_a": tmp_path / "artifact_a",
        "artifact_b": tmp_path / "artifact_b",
        "verify_a": tmp_path / "verify_a.json",
        "verify_b": tmp_path / "verify_b.json",
    }
    role_counts = write_parent_csv(paths["parent"], reverse_frozen=reverse_frozen)
    write_protocol(paths["protocol"], paths["parent"], role_counts)
    return paths


def producer_args(paths: dict[str, Path], output: Path) -> argparse.Namespace:
    return argparse.Namespace(
        protocol=str(paths["protocol"]),
        per_parent=str(paths["parent"]),
        source_commit="a" * 40,
        output=str(output),
    )


def verifier_args(paths: dict[str, Path], artifact: Path, output: Path) -> argparse.Namespace:
    return argparse.Namespace(
        artifact=str(artifact),
        protocol=str(paths["protocol"]),
        per_parent=str(paths["parent"]),
        source_commit="a" * 40,
        output=str(output),
    )


def directory_bytes(path: Path) -> dict[str, bytes]:
    return {
        item.relative_to(path).as_posix(): item.read_bytes()
        for item in sorted(path.rglob("*"))
        if item.is_file()
    }


def test_positive_transport_is_deterministic_and_independently_verified(tmp_path: Path) -> None:
    paths = make_fixture(tmp_path)
    assert producer.run(producer_args(paths, paths["artifact_a"])) == 0
    assert producer.run(producer_args(paths, paths["artifact_b"])) == 0
    assert directory_bytes(paths["artifact_a"]) == directory_bytes(paths["artifact_b"])
    summary = json.loads((paths["artifact_a"] / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == producer.STATUS_PASS
    assert summary["primary"]["spearman_rho"] == pytest.approx(1.0)
    assert all(summary["criteria"].values())
    assert verifier.verify(verifier_args(paths, paths["artifact_a"], paths["verify_a"])) == 0
    assert verifier.verify(verifier_args(paths, paths["artifact_b"], paths["verify_b"])) == 0
    assert paths["verify_a"].read_bytes() == paths["verify_b"].read_bytes()


def test_reversed_frozen_profile_fails_positive_gate(tmp_path: Path) -> None:
    paths = make_fixture(tmp_path, reverse_frozen=True)
    assert producer.run(producer_args(paths, paths["artifact_a"])) == 0
    summary = json.loads((paths["artifact_a"] / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == producer.STATUS_FAIL
    assert summary["primary"]["spearman_rho"] == pytest.approx(-1.0)
    assert summary["claim_allowed"] is False


def test_independent_verifier_rejects_rehashed_science_tamper(tmp_path: Path) -> None:
    paths = make_fixture(tmp_path)
    assert producer.run(producer_args(paths, paths["artifact_a"])) == 0
    summary_path = paths["artifact_a"] / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["primary"]["spearman_rho"] = 0.75
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    manifest_path = paths["artifact_a"] / "sha256_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["summary.json"] = sha(summary_path)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    with pytest.raises(verifier.VerificationError, match="scientific reconstruction"):
        verifier.verify(verifier_args(paths, paths["artifact_a"], paths["verify_a"]))


def test_credential_shape_is_rejected_before_csv_parse(tmp_path: Path) -> None:
    paths = make_fixture(tmp_path)
    paths["parent"].write_bytes(b"not,csv\nsk-" + b"A" * 24 + b"\n")
    write_protocol(
        paths["protocol"],
        paths["parent"],
        {"train": 1, "frozen": 0, "extension": 0},
    )
    with pytest.raises(producer.TransportError, match="credential-shaped"):
        producer.run(producer_args(paths, paths["artifact_a"]))


def test_independent_verifier_source_does_not_import_producer() -> None:
    source = Path(verifier.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.append(node.module or "")
    assert all("source_retention_transport" not in name for name in names)


def test_formal_protocol_remains_frozen() -> None:
    root = Path(__file__).resolve().parents[2]
    value = json.loads(
        (root / "phase1/source_retention_transport_protocol_v1.json").read_text(encoding="utf-8")
    )
    assert value["input_per_parent_sha256"] == (
        "75c02200d1f9b8d87614762a9f2b71ba3c678d598ff28bc237c8a46a4bc36d03"
    )
    assert value["expected_parent_rows"] == 3252
    assert value["expected_role_parent_counts"] == {
        "train": 2293,
        "frozen": 845,
        "extension": 114,
    }
    assert value["minimum_train_parents_per_task"] == 30
    assert value["minimum_frozen_parents_per_task"] == 15
    assert value["minimum_common_tasks"] == 10
    assert value["minimum_primary_rho"] == 0.5
    assert value["permutation_repetitions"] == 100000
    assert value["bootstrap_repetitions"] == 20000
