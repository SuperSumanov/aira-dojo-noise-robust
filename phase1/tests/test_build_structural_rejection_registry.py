from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from phase1.build_structural_rejection_registry import (
    RegistryBuildError,
    build_registry,
)
from phase1.prospective_production_runner import load_structural_rejections


COMMIT = "a" * 40


def _sha(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def _receipt(archive: Path, archive_sha: str) -> dict[str, object]:
    stat = archive.stat()
    return {
        "protocol": "prospective_archive_task_identity_audit_v1",
        "status": "STRUCTURAL_TASK_IDENTITY_REJECTION_SUPPORTED",
        "archive": {
            "relative_basename": archive.name,
            "sha256": archive_sha,
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
        },
        "journals": 2,
        "task_identity_cardinality_counts": {"zero": 1, "one": 0, "multiple": 1},
        "invalid_journals": 2,
        "per_journal": [
            {
                "journal_sha256": "b" * 64,
                "nodes": 3,
                "task_identity_cardinality": 0,
            },
            {
                "journal_sha256": "c" * 64,
                "nodes": 4,
                "task_identity_cardinality": 2,
            },
        ],
        "archive_audit": {},
        "security": {
            "journal_scanned_before_json": True,
            "env_members_read": False,
            "live_event_journal_members_read": False,
            "task_identity_values_emitted": False,
            "code_stdout_grade_or_metric_values_emitted": False,
        },
        "outcomes_read": False,
        "recommended_reason_code": "JOURNAL_TASK_IDENTITY_NOT_EXACTLY_ONE_WITHIN_ARCHIVE",
        "source_commit": COMMIT,
    }


def _no_checkpoint_receipt(archive: Path, archive_sha: str) -> dict[str, object]:
    value = _receipt(archive, archive_sha)
    value.update(
        {
            "status": "STRUCTURAL_NO_CHECKPOINT_REJECTION_SUPPORTED",
            "journals": 0,
            "task_identity_cardinality_counts": {"zero": 0, "one": 0, "multiple": 0},
            "invalid_journals": 0,
            "per_journal": [],
            "archive_audit": {
                "checkpoint_runs": 0,
                "checkpoint_with_live_event_log": 0,
                "checkpoint_without_live_event_log": 0,
                "declared_member_bytes": 123,
                "discovered_run_roots": 4,
                "live_only_runs_excluded": 4,
                "members": 8,
            },
            "recommended_reason_code": "ARCHIVE_HAS_NO_CHECKPOINT_JOURNALS",
        }
    )
    return value


def test_builds_registry_bound_to_receipt_and_runner_accepts_it(tmp_path: Path) -> None:
    archive = tmp_path / "task.tar.gz"
    archive.write_bytes(b"opaque archive")
    archive_sha = _sha(archive.read_bytes())
    receipt_path = tmp_path / "diagnostic.json"
    receipt_path.write_text(json.dumps(_receipt(archive, archive_sha)) + "\n", encoding="utf-8")

    registry = build_registry(
        archive,
        "0819/task.tar.gz",
        archive_sha,
        receipt_path,
        COMMIT,
    )
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(json.dumps(registry, sort_keys=True) + "\n", encoding="utf-8")
    registry_sha = _sha(registry_path.read_bytes())
    rows, actual_sha = load_structural_rejections(registry_path, registry_sha)

    assert actual_sha == registry_sha
    assert rows[0]["archive_relative_path"] == "0819/task.tar.gz"
    assert rows[0]["archive_sha256"] == archive_sha
    assert rows[0]["diagnostic_receipt_file"] == "diagnostic.json"


def test_builds_no_checkpoint_registry_and_runner_accepts_it(tmp_path: Path) -> None:
    archive = tmp_path / "task.tar.gz"
    archive.write_bytes(b"opaque archive")
    archive_sha = _sha(archive.read_bytes())
    receipt_path = tmp_path / "diagnostic.json"
    receipt_path.write_text(
        json.dumps(_no_checkpoint_receipt(archive, archive_sha)) + "\n", encoding="utf-8"
    )

    registry = build_registry(
        archive,
        "0822/task.tar.gz",
        archive_sha,
        receipt_path,
        COMMIT,
    )
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(json.dumps(registry, sort_keys=True) + "\n", encoding="utf-8")
    registry_sha = _sha(registry_path.read_bytes())
    rows, actual_sha = load_structural_rejections(registry_path, registry_sha)

    assert actual_sha == registry_sha
    assert rows[0]["reason_code"] == "ARCHIVE_HAS_NO_CHECKPOINT_JOURNALS"


def test_rejects_inconsistent_no_checkpoint_archive_audit(tmp_path: Path) -> None:
    archive = tmp_path / "task.tar.gz"
    archive.write_bytes(b"opaque archive")
    archive_sha = _sha(archive.read_bytes())
    value = _no_checkpoint_receipt(archive, archive_sha)
    value["archive_audit"]["checkpoint_runs"] = 1
    receipt_path = tmp_path / "diagnostic.json"
    receipt_path.write_text(json.dumps(value) + "\n", encoding="utf-8")

    with pytest.raises(RegistryBuildError, match="no-checkpoint archive-audit accounting"):
        build_registry(
            archive,
            "0822/task.tar.gz",
            archive_sha,
            receipt_path,
            COMMIT,
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda receipt: receipt.__setitem__("outcomes_read", True), "outcome-blindness"),
        (
            lambda receipt: receipt["security"].__setitem__("env_members_read", True),
            "security contract",
        ),
        (lambda receipt: receipt.__setitem__("invalid_journals", 0), "accounting"),
        (lambda receipt: receipt.__setitem__("source_commit", "d" * 40), "source-commit"),
    ],
)
def test_rejects_unsafe_or_inconsistent_receipt(
    tmp_path: Path, mutation, message: str
) -> None:
    archive = tmp_path / "task.tar.gz"
    archive.write_bytes(b"opaque archive")
    archive_sha = _sha(archive.read_bytes())
    value = _receipt(archive, archive_sha)
    mutation(value)
    receipt_path = tmp_path / "diagnostic.json"
    receipt_path.write_text(json.dumps(value) + "\n", encoding="utf-8")

    with pytest.raises(RegistryBuildError, match=message):
        build_registry(
            archive,
            "0819/task.tar.gz",
            archive_sha,
            receipt_path,
            COMMIT,
        )
