from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path

import pytest

from phase1 import source_opportunity_journal_status as producer
from phase1 import verify_source_opportunity_journal_status as verifier


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )


def metric(*, score: float | None, thresholds: bool = False) -> dict:
    value = {"competition_id": "task-a"}
    if score is not None:
        value["score"] = score
    if thresholds:
        value["gold_threshold"] = 0.9
    return value


def nodes(*, include_last: bool = True, parent_id: str = "parent") -> list[dict]:
    result = [
        {"step": 0, "id": "root", "parents": [], "exit_code": 0, "metric_info": metric(score=0.1)},
        {
            "step": 1,
            "id": parent_id,
            "parents": [0],
            "exit_code": 0,
            "metric_info": metric(score=0.2, thresholds=True),
        },
        {"step": 2, "id": "c1", "parents": [1], "exit_code": 1, "metric_info": metric(score=None)},
        {"step": 3, "id": "c2", "parents": [1], "exit_code": 0, "metric_info": metric(score=None)},
        {"step": 4, "id": "c3", "parents": [1], "exit_code": 0, "metric_info": metric(score=0.3)},
    ]
    if include_last:
        result.append(
            {
                "step": 5,
                "id": "c4",
                "parents": [1],
                "exit_code": 0,
                "metric_info": metric(score=0.4, thresholds=True),
            }
        )
    return result


def fixture(tmp_path: Path, *, include_last: bool = True) -> dict[str, Path]:
    root = tmp_path / "journals"
    journal = root / "run-a" / "checkpoint" / "journal.jsonl"
    write_jsonl(journal, nodes(include_last=include_last))
    registry = tmp_path / "identity.jsonl"
    write_jsonl(
        registry,
        [
            {
                "role": "train",
                "parent": "task-a__parent",
                "source_incomplete": True,
                "exact_identity_recoverable": True,
                "missing_child_ids": [
                    "task-a__c1",
                    "task-a__c2",
                    "task-a__c3",
                    "task-a__c4",
                ],
            }
        ],
    )
    return {
        "root": root,
        "registry": registry,
        "status": tmp_path / "status",
        "receipt": tmp_path / "receipt.json",
    }


def producer_args(paths: dict[str, Path]) -> argparse.Namespace:
    return argparse.Namespace(
        identity_registry=str(paths["registry"]),
        root=[f"synthetic={paths['root']}"],
        source_commit="a" * 40,
        output=str(paths["status"]),
    )


def verifier_args(paths: dict[str, Path]) -> argparse.Namespace:
    return argparse.Namespace(
        status_root=str(paths["status"]),
        identity_registry=str(paths["registry"]),
        root=[f"synthetic={paths['root']}"],
        output=str(paths["receipt"]),
    )


def summary(paths: dict[str, Path]) -> dict:
    return json.loads((paths["status"] / "summary.json").read_text(encoding="utf-8"))


def test_high_coverage_recovers_four_frozen_status_categories(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    assert producer.run(producer_args(paths)) == 0
    value = summary(paths)
    assert value["status"] == producer.STATUS_HIGH
    assert value["node_recovery_rate"] == 1.0
    assert value["categories"] == {
        "EXECUTION_ERROR": 1,
        "NORMALIZATION_METADATA_ABSENT": 1,
        "OFFICIAL_GRADE_ABSENT": 1,
        "UNEXPLAINED_FILTER": 1,
    }
    assert value["scope"]["reads_numeric_grade"] is False
    assert verifier.verify(verifier_args(paths)) == 0


def test_partial_when_fixed_target_node_is_not_found(tmp_path: Path) -> None:
    paths = fixture(tmp_path, include_last=False)
    assert producer.run(producer_args(paths)) == 0
    value = summary(paths)
    assert value["status"] == producer.STATUS_PARTIAL
    assert value["node_recovery_rate"] == 0.75
    assert verifier.verify(verifier_args(paths)) == 0


def test_distinct_source_collision_fails_closed(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    second = paths["root"] / "run-b" / "checkpoint" / "journal.jsonl"
    write_jsonl(second, nodes(parent_id="other-parent"))
    assert producer.run(producer_args(paths)) == 0
    value = summary(paths)
    assert value["status"] == producer.STATUS_UNSUPPORTED
    assert value["source_journal_collisions"] == 4
    assert value["missing_status_registry_claim_allowed"] is False
    assert verifier.verify(verifier_args(paths)) == 0


def test_byte_identical_journal_copy_collapses_by_source_sha(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    original = paths["root"] / "run-a" / "checkpoint" / "journal.jsonl"
    duplicate = paths["root"] / "run-copy" / "checkpoint" / "journal.jsonl"
    duplicate.parent.mkdir(parents=True, exist_ok=True)
    duplicate.write_bytes(original.read_bytes())
    assert producer.run(producer_args(paths)) == 0
    value = summary(paths)
    assert value["status"] == producer.STATUS_HIGH
    assert value["source_journal_collisions"] == 0
    assert verifier.verify(verifier_args(paths)) == 0


def test_credential_journal_is_skipped_before_json_parse(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    journal = paths["root"] / "run-a" / "checkpoint" / "journal.jsonl"
    journal.write_bytes(b"not-json sk-" + b"A" * 20 + b"\n")
    assert producer.run(producer_args(paths)) == 0
    value = summary(paths)
    assert value["unique_nodes_recovered"] == 0
    assert value["journal_inventory"]["roots"]["synthetic"][
        "credential_shape_journals_skipped"
    ] == 1
    assert verifier.verify(verifier_args(paths)) == 0


def test_independent_verifier_rejects_rehashed_child_tamper(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    assert producer.run(producer_args(paths)) == 0
    child_path = paths["status"] / "per_child.jsonl"
    rows = [json.loads(line) for line in child_path.read_text(encoding="utf-8").splitlines()]
    rows[0]["category"] = "INVENTED"
    write_jsonl(child_path, rows)
    manifest_path = paths["status"] / "sha256_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["per_child.jsonl"] = hashlib.sha256(child_path.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(verifier.VerificationError, match="per-child"):
        verifier.verify(verifier_args(paths))


def test_independent_verifier_source_does_not_import_producer() -> None:
    source = Path(verifier.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
    assert not any("source_opportunity_journal_status" in name for name in imported)
