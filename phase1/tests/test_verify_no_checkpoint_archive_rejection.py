from __future__ import annotations

import hashlib
import io
import json
import tarfile
from pathlib import Path

import pytest

from phase1.verify_no_checkpoint_archive_rejection import VerificationError, sha256, verify


def _archive(
    path: Path,
    *,
    checkpoint: bool = False,
    unsafe: bool = False,
    credential_name: bool = False,
) -> None:
    with tarfile.open(path, "w:gz") as handle:
        for index in range(2):
            name = f"run-{index}/json/JOURNAL.jsonl"
            info = tarfile.TarInfo(name)
            payload = b"not-read"
            info.size = len(payload)
            handle.addfile(info, io.BytesIO(payload))
            if checkpoint and index == 0:
                checkpoint_info = tarfile.TarInfo(f"run-{index}/checkpoint/journal.jsonl")
                checkpoint_info.size = len(payload)
                handle.addfile(checkpoint_info, io.BytesIO(payload))
        if unsafe:
            link = tarfile.TarInfo("unsafe-link")
            link.type = tarfile.SYMTYPE
            link.linkname = "target"
            handle.addfile(link)
        if credential_name:
            secret_named = tarfile.TarInfo("metadata/api_key")
            secret_named.size = 0
            handle.addfile(secret_named, io.BytesIO(b""))


def _receipt(archive: Path) -> dict[str, object]:
    stat = archive.stat()
    return {
        "protocol": "prospective_archive_task_identity_audit_v1",
        "status": "STRUCTURAL_NO_CHECKPOINT_REJECTION_SUPPORTED",
        "archive": {
            "relative_basename": archive.name,
            "sha256": sha256(archive),
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
        },
        "journals": 0,
        "task_identity_cardinality_counts": {"zero": 0, "one": 0, "multiple": 0},
        "invalid_journals": 0,
        "per_journal": [],
        "archive_audit": {
            "checkpoint_runs": 0,
            "checkpoint_with_live_event_log": 0,
            "checkpoint_without_live_event_log": 0,
            "declared_member_bytes": 16,
            "discovered_run_roots": 2,
            "live_only_runs_excluded": 2,
            "members": 2,
        },
        "security": {
            "journal_scanned_before_json": True,
            "env_members_read": False,
            "live_event_journal_members_read": False,
            "task_identity_values_emitted": False,
            "code_stdout_grade_or_metric_values_emitted": False,
        },
        "outcomes_read": False,
        "recommended_reason_code": "ARCHIVE_HAS_NO_CHECKPOINT_JOURNALS",
        "source_commit": "a" * 40,
    }


def _bound_receipt(tmp_path: Path, archive: Path) -> Path:
    receipt = tmp_path / "receipt.json"
    receipt.write_text(json.dumps(_receipt(archive)) + "\n", encoding="utf-8")
    return receipt


def test_independently_verifies_live_only_archive(tmp_path: Path) -> None:
    archive = tmp_path / "task.tar.gz"
    _archive(archive)
    receipt = _bound_receipt(tmp_path, archive)
    value = verify(archive, sha256(archive), receipt, sha256(receipt))
    assert value["status"] == "STRUCTURAL_NO_CHECKPOINT_REJECTION_INDEPENDENTLY_VERIFIED"
    assert value["archive_audit"]["checkpoint_runs"] == 0
    assert value["archive_audit"]["live_only_runs_excluded"] == 2
    assert value["journal_member_bytes_read"] == 0
    assert value["outcomes_read"] is False


def test_rejects_archive_with_checkpoint(tmp_path: Path) -> None:
    archive = tmp_path / "task.tar.gz"
    _archive(archive, checkpoint=True)
    receipt = _bound_receipt(tmp_path, archive)
    with pytest.raises(VerificationError, match="does not support"):
        verify(archive, sha256(archive), receipt, sha256(receipt))


def test_rejects_unsafe_tar_member(tmp_path: Path) -> None:
    archive = tmp_path / "task.tar.gz"
    _archive(archive, unsafe=True)
    receipt = _bound_receipt(tmp_path, archive)
    with pytest.raises(VerificationError, match="unsafe tar member type"):
        verify(archive, sha256(archive), receipt, sha256(receipt))


def test_rejects_credential_shaped_member_name(tmp_path: Path) -> None:
    archive = tmp_path / "task.tar.gz"
    _archive(archive, credential_name=True)
    receipt = _bound_receipt(tmp_path, archive)
    with pytest.raises(VerificationError, match="credential-shaped"):
        verify(archive, sha256(archive), receipt, sha256(receipt))


def test_rejects_receipt_hash_drift(tmp_path: Path) -> None:
    archive = tmp_path / "task.tar.gz"
    _archive(archive)
    receipt = _bound_receipt(tmp_path, archive)
    with pytest.raises(VerificationError, match="receipt SHA mismatch"):
        verify(archive, sha256(archive), receipt, hashlib.sha256(b"wrong").hexdigest())
