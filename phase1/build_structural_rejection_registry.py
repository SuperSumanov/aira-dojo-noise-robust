#!/usr/bin/env python3
"""Build one immutable structural-rejection registry from a bound audit receipt."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Any


AUDIT_PROTOCOL = "prospective_archive_task_identity_audit_v1"
REJECTION_PROTOCOL = "prospective_structural_rejection_v1"
TASK_IDENTITY_REJECTION_STATUS = "STRUCTURAL_TASK_IDENTITY_REJECTION_SUPPORTED"
NO_CHECKPOINT_REJECTION_STATUS = "STRUCTURAL_NO_CHECKPOINT_REJECTION_SUPPORTED"
TASK_IDENTITY_REASON = "JOURNAL_TASK_IDENTITY_NOT_EXACTLY_ONE_WITHIN_ARCHIVE"
NO_CHECKPOINT_REASON = "ARCHIVE_HAS_NO_CHECKPOINT_JOURNALS"
SHA_RX = re.compile(r"[0-9a-f]{64}")
COMMIT_RX = re.compile(r"[0-9a-f]{40}")
EXPECTED_SECURITY = {
    "journal_scanned_before_json": True,
    "env_members_read": False,
    "live_event_journal_members_read": False,
    "task_identity_values_emitted": False,
    "code_stdout_grade_or_metric_values_emitted": False,
}


class RegistryBuildError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RegistryBuildError("cannot parse diagnostic receipt") from exc
    if not isinstance(value, dict):
        raise RegistryBuildError("diagnostic receipt is not an object")
    return value


def require_nonnegative_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise RegistryBuildError(f"invalid {label}")
    return value


def validate_relative(relative: str) -> None:
    parts = PurePosixPath(relative).parts
    if (
        not isinstance(relative, str)
        or len(parts) != 2
        or any(part in {"", ".", ".."} for part in parts)
        or not relative.endswith(".tar.gz")
        or any(character in relative for character in "\r\n\t")
    ):
        raise RegistryBuildError("invalid archive relative path")


def build_registry(
    archive: Path,
    relative: str,
    expected_archive_sha256: str,
    diagnostic_receipt: Path,
    expected_source_commit: str,
) -> dict[str, Any]:
    validate_relative(relative)
    if not SHA_RX.fullmatch(expected_archive_sha256):
        raise RegistryBuildError("invalid expected archive SHA-256")
    if not COMMIT_RX.fullmatch(expected_source_commit):
        raise RegistryBuildError("invalid expected source commit")

    archive = archive.resolve()
    diagnostic_receipt = diagnostic_receipt.resolve()
    if not archive.is_file() or archive.is_symlink():
        raise RegistryBuildError("archive is absent or not a regular file")
    if not diagnostic_receipt.is_file() or diagnostic_receipt.is_symlink():
        raise RegistryBuildError("diagnostic receipt is absent or not a regular file")
    if sha256(archive) != expected_archive_sha256:
        raise RegistryBuildError("archive SHA mismatch")

    receipt = read_object(diagnostic_receipt)
    if receipt.get("protocol") != AUDIT_PROTOCOL:
        raise RegistryBuildError("diagnostic protocol mismatch")
    status = receipt.get("status")
    reason_code = receipt.get("recommended_reason_code")
    status_to_reason = {
        TASK_IDENTITY_REJECTION_STATUS: TASK_IDENTITY_REASON,
        NO_CHECKPOINT_REJECTION_STATUS: NO_CHECKPOINT_REASON,
    }
    if status not in status_to_reason:
        raise RegistryBuildError("diagnostic does not support structural rejection")
    if receipt.get("outcomes_read") is not False:
        raise RegistryBuildError("diagnostic outcome-blindness mismatch")
    if reason_code != status_to_reason[status]:
        raise RegistryBuildError("diagnostic reason-code mismatch")
    if receipt.get("source_commit") != expected_source_commit:
        raise RegistryBuildError("diagnostic source-commit mismatch")
    security = receipt.get("security")
    if not isinstance(security, dict) or any(
        security.get(key) is not expected for key, expected in EXPECTED_SECURITY.items()
    ):
        raise RegistryBuildError("diagnostic security contract mismatch")

    archive_receipt = receipt.get("archive")
    stat = archive.stat()
    expected_archive_receipt = {
        "relative_basename": PurePosixPath(relative).name,
        "sha256": expected_archive_sha256,
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }
    if archive_receipt != expected_archive_receipt:
        raise RegistryBuildError("diagnostic archive identity mismatch")

    journals = require_nonnegative_int(receipt.get("journals"), "journal count")
    invalid = require_nonnegative_int(receipt.get("invalid_journals"), "invalid journal count")
    counts = receipt.get("task_identity_cardinality_counts")
    if not isinstance(counts, dict) or set(counts) != {"zero", "one", "multiple"}:
        raise RegistryBuildError("diagnostic cardinality-count schema mismatch")
    normalized_counts = {
        key: require_nonnegative_int(counts[key], f"{key} journal count")
        for key in ("zero", "one", "multiple")
    }
    if sum(normalized_counts.values()) != journals:
        raise RegistryBuildError("diagnostic cardinality counts do not sum to journals")
    if status == TASK_IDENTITY_REJECTION_STATUS:
        if (
            normalized_counts["zero"] + normalized_counts["multiple"] != invalid
            or invalid == 0
        ):
            raise RegistryBuildError("diagnostic invalid-journal accounting mismatch")
    elif invalid != 0 or journals != 0 or any(normalized_counts.values()):
        raise RegistryBuildError("no-checkpoint diagnostic journal accounting mismatch")

    per_journal = receipt.get("per_journal")
    if not isinstance(per_journal, list) or len(per_journal) != journals:
        raise RegistryBuildError("diagnostic per-journal accounting mismatch")
    rebuilt_counts = {"zero": 0, "one": 0, "multiple": 0}
    seen_journal_shas: set[str] = set()
    for row in per_journal:
        if not isinstance(row, dict) or set(row) != {
            "journal_sha256",
            "nodes",
            "task_identity_cardinality",
        }:
            raise RegistryBuildError("diagnostic per-journal schema mismatch")
        journal_sha = row["journal_sha256"]
        if not isinstance(journal_sha, str) or not SHA_RX.fullmatch(journal_sha):
            raise RegistryBuildError("invalid journal SHA-256")
        if journal_sha in seen_journal_shas:
            raise RegistryBuildError("duplicate journal SHA-256")
        seen_journal_shas.add(journal_sha)
        if require_nonnegative_int(row["nodes"], "journal node count") == 0:
            raise RegistryBuildError("empty journal cannot support rejection")
        cardinality = require_nonnegative_int(
            row["task_identity_cardinality"], "task identity cardinality"
        )
        bucket = "zero" if cardinality == 0 else "one" if cardinality == 1 else "multiple"
        rebuilt_counts[bucket] += 1
    if rebuilt_counts != normalized_counts:
        raise RegistryBuildError("per-journal cardinalities differ from aggregate counts")

    if status == NO_CHECKPOINT_REJECTION_STATUS:
        archive_audit = receipt.get("archive_audit")
        expected_audit_keys = {
            "checkpoint_runs",
            "checkpoint_with_live_event_log",
            "checkpoint_without_live_event_log",
            "declared_member_bytes",
            "discovered_run_roots",
            "live_only_runs_excluded",
            "members",
        }
        if not isinstance(archive_audit, dict) or set(archive_audit) != expected_audit_keys:
            raise RegistryBuildError("no-checkpoint archive-audit schema mismatch")
        normalized_audit = {
            key: require_nonnegative_int(archive_audit[key], f"archive audit {key}")
            for key in expected_audit_keys
        }
        if (
            normalized_audit["checkpoint_runs"] != 0
            or normalized_audit["checkpoint_with_live_event_log"] != 0
            or normalized_audit["checkpoint_without_live_event_log"] != 0
            or normalized_audit["discovered_run_roots"] <= 0
            or normalized_audit["members"] <= 0
            or normalized_audit["live_only_runs_excluded"]
            != normalized_audit["discovered_run_roots"]
        ):
            raise RegistryBuildError("no-checkpoint archive-audit accounting mismatch")

    return {
        "protocol": REJECTION_PROTOCOL,
        "outcomes_read": False,
        "entries": [
            {
                "archive_mtime_ns": stat.st_mtime_ns,
                "archive_relative_path": relative,
                "archive_sha256": expected_archive_sha256,
                "archive_size": stat.st_size,
                "diagnostic_receipt_file": diagnostic_receipt.name,
                "diagnostic_receipt_sha256": sha256(diagnostic_receipt),
                "reason_code": reason_code,
            }
        ],
    }


def write_new(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise RegistryBuildError("output exists")
    if not path.parent.is_dir() or path.parent.is_symlink():
        raise RegistryBuildError("output parent is absent or unsafe")
    temporary = path.with_name(path.name + f".tmp-{os.getpid()}")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--archive-relative-path", required=True)
    parser.add_argument("--expect-archive-sha256", required=True)
    parser.add_argument("--diagnostic-receipt", required=True, type=Path)
    parser.add_argument("--expect-source-commit", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        output = args.output.resolve()
        receipt = args.diagnostic_receipt.resolve()
        if output.parent != receipt.parent:
            raise RegistryBuildError("registry and diagnostic receipt must be adjacent")
        value = build_registry(
            args.archive,
            args.archive_relative_path,
            args.expect_archive_sha256,
            receipt,
            args.expect_source_commit,
        )
        write_new(output, value)
        print(json.dumps(value, sort_keys=True, separators=(",", ":")))
        return 0
    except (OSError, RegistryBuildError) as exc:
        print(f"STRUCTURAL_REJECTION_REGISTRY_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
