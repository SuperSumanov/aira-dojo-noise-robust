#!/usr/bin/env python3
"""Independent raw-archive verifier for a no-checkpoint rejection receipt.

This module deliberately does not import the production intake or its diagnostic.
It traverses tar metadata only and never reads journal bytes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tarfile
from collections import defaultdict
from pathlib import Path, PurePosixPath
from typing import Any


STATUS = "STRUCTURAL_NO_CHECKPOINT_REJECTION_INDEPENDENTLY_VERIFIED"
AUDIT_PROTOCOL = "prospective_archive_task_identity_audit_v1"
AUDIT_STATUS = "STRUCTURAL_NO_CHECKPOINT_REJECTION_SUPPORTED"
REASON = "ARCHIVE_HAS_NO_CHECKPOINT_JOURNALS"
SHA_RX = re.compile(r"[0-9a-f]{64}")
CREDENTIAL_NAME_RX = re.compile(
    r"(?:sk-(?:or-v1-)?[A-Za-z0-9._-]{10,}|api[_-]?key|authorization[_-]?bearer)",
    re.IGNORECASE,
)


class VerificationError(RuntimeError):
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
        raise VerificationError("cannot parse diagnostic receipt") from exc
    if not isinstance(value, dict):
        raise VerificationError("diagnostic receipt is not an object")
    return value


def safe_path(name: str) -> PurePosixPath:
    if "\\" in name or "\x00" in name:
        raise VerificationError("unsafe tar member spelling")
    pure = PurePosixPath(name)
    if pure.is_absolute() or not pure.parts or ".." in pure.parts:
        raise VerificationError("unsafe tar member path")
    return pure


def role(pure: PurePosixPath) -> tuple[str, str] | None:
    if len(pure.parts) >= 3 and pure.parts[-2:] == ("checkpoint", "journal.jsonl"):
        return "/".join(pure.parts[:-2]), "checkpoint"
    if len(pure.parts) >= 3 and pure.parts[-2:] == ("json", "JOURNAL.jsonl"):
        return "/".join(pure.parts[:-2]), "live"
    return None


def inspect_tar_metadata(archive: Path) -> dict[str, int]:
    groups: dict[str, set[str]] = defaultdict(set)
    members = 0
    declared_member_bytes = 0
    credential_name_hits = 0
    with tarfile.open(archive, "r|gz") as handle:
        for member in handle:
            members += 1
            declared_member_bytes += max(0, member.size)
            pure = safe_path(member.name)
            if member.issym() or member.islnk() or member.isdev() or member.isfifo():
                raise VerificationError("unsafe tar member type")
            credential_name_hits += int(bool(CREDENTIAL_NAME_RX.search(member.name)))
            member_role = role(pure)
            if member_role is not None and member.isfile():
                root, kind = member_role
                if kind in groups[root]:
                    raise VerificationError("duplicate journal role within run root")
                groups[root].add(kind)
    if credential_name_hits:
        raise VerificationError("credential-shaped tar member name")
    if not groups:
        raise VerificationError("archive has no supported journal members")
    return {
        "members": members,
        "declared_member_bytes": declared_member_bytes,
        "discovered_run_roots": len(groups),
        "checkpoint_runs": sum("checkpoint" in values for values in groups.values()),
        "checkpoint_with_live_event_log": sum(
            values == {"checkpoint", "live"} for values in groups.values()
        ),
        "checkpoint_without_live_event_log": sum(
            values == {"checkpoint"} for values in groups.values()
        ),
        "live_only_runs_excluded": sum(values == {"live"} for values in groups.values()),
        "credential_shaped_member_names": credential_name_hits,
    }


def verify(
    archive: Path,
    expected_archive_sha256: str,
    receipt_path: Path,
    expected_receipt_sha256: str,
) -> dict[str, Any]:
    if not SHA_RX.fullmatch(expected_archive_sha256):
        raise VerificationError("invalid archive SHA-256")
    if not SHA_RX.fullmatch(expected_receipt_sha256):
        raise VerificationError("invalid receipt SHA-256")
    archive = archive.resolve()
    receipt_path = receipt_path.resolve()
    if not archive.is_file() or archive.is_symlink():
        raise VerificationError("archive is absent or unsafe")
    if not receipt_path.is_file() or receipt_path.is_symlink():
        raise VerificationError("diagnostic receipt is absent or unsafe")
    archive_sha = sha256(archive)
    receipt_sha = sha256(receipt_path)
    if archive_sha != expected_archive_sha256:
        raise VerificationError("archive SHA mismatch")
    if receipt_sha != expected_receipt_sha256:
        raise VerificationError("diagnostic receipt SHA mismatch")

    observed = inspect_tar_metadata(archive)
    if (
        observed["checkpoint_runs"] != 0
        or observed["discovered_run_roots"] <= 0
        or observed["live_only_runs_excluded"] != observed["discovered_run_roots"]
    ):
        raise VerificationError("raw archive does not support no-checkpoint rejection")

    receipt = read_object(receipt_path)
    if (
        receipt.get("protocol") != AUDIT_PROTOCOL
        or receipt.get("status") != AUDIT_STATUS
        or receipt.get("recommended_reason_code") != REASON
        or receipt.get("outcomes_read") is not False
        or receipt.get("journals") != 0
        or receipt.get("invalid_journals") != 0
        or receipt.get("per_journal") != []
        or receipt.get("task_identity_cardinality_counts")
        != {"zero": 0, "one": 0, "multiple": 0}
    ):
        raise VerificationError("diagnostic receipt contract mismatch")
    security = receipt.get("security")
    if not isinstance(security, dict) or (
        security.get("env_members_read") is not False
        or security.get("live_event_journal_members_read") is not False
        or security.get("task_identity_values_emitted") is not False
        or security.get("code_stdout_grade_or_metric_values_emitted") is not False
    ):
        raise VerificationError("diagnostic security contract mismatch")
    stat = archive.stat()
    if receipt.get("archive") != {
        "relative_basename": archive.name,
        "sha256": archive_sha,
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }:
        raise VerificationError("diagnostic archive binding mismatch")
    expected_audit = dict(observed)
    expected_audit.pop("credential_shaped_member_names")
    if receipt.get("archive_audit") != expected_audit:
        raise VerificationError("diagnostic archive accounting mismatch")

    return {
        "status": STATUS,
        "archive_sha256": archive_sha,
        "diagnostic_receipt_sha256": receipt_sha,
        "archive_audit": observed,
        "journal_member_bytes_read": 0,
        "candidate_identities_emitted": False,
        "outcomes_read": False,
    }


def write_new(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise VerificationError("output exists")
    path.parent.mkdir(parents=True, exist_ok=True)
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
    parser.add_argument("--expect-archive-sha256", required=True)
    parser.add_argument("--diagnostic-receipt", required=True, type=Path)
    parser.add_argument("--expect-diagnostic-receipt-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        value = verify(
            args.archive,
            args.expect_archive_sha256,
            args.diagnostic_receipt,
            args.expect_diagnostic_receipt_sha256,
        )
        write_new(args.output.resolve(), value)
        print(json.dumps(value, sort_keys=True, separators=(",", ":")))
        return 0
    except (OSError, tarfile.TarError, VerificationError) as exc:
        print(f"NO_CHECKPOINT_REJECTION_VERIFY_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
