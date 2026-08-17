#!/usr/bin/env python3
"""Credential-safe, outcome-blind task-identity cardinality audit for one archive."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from phase1.prospective_drop_intake import IntakeError, journals_from_archive, sha256, sha256_bytes


PROTOCOL = "prospective_archive_task_identity_audit_v1"


class AuditError(RuntimeError):
    pass


def identity_cardinality(blob: bytes) -> tuple[int, int]:
    try:
        text = blob.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AuditError("journal is not UTF-8") from exc
    nodes = []
    for line_number, line in enumerate(text.splitlines(), 1):
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise AuditError(f"invalid journal JSON at line {line_number}") from exc
        if not isinstance(row, dict):
            raise AuditError("journal row is not an object")
        nodes.append(row)
    if not nodes:
        raise AuditError("empty journal")
    identities = {
        str((node.get("metric_info") or {}).get("competition_id"))
        for node in nodes
        if isinstance(node.get("metric_info"), dict)
        and (node.get("metric_info") or {}).get("competition_id")
    }
    return len(nodes), len(identities)


def audit(archive: Path, expected_sha256: str, source_commit: str) -> dict[str, Any]:
    archive = archive.resolve()
    if not archive.is_file() or archive.is_symlink():
        raise AuditError("archive is absent or not a regular file")
    actual_sha = sha256(archive)
    if actual_sha != expected_sha256:
        raise AuditError("archive SHA mismatch")
    sources, archive_audit = journals_from_archive(
        archive,
        max_member_bytes=512 * 1024 * 1024,
        max_members=1_000_000,
        max_total_member_bytes=256 * 1024 * 1024 * 1024,
    )
    per_journal = []
    counts = {"zero": 0, "one": 0, "multiple": 0}
    for source in sources:
        node_count, cardinality = identity_cardinality(source["blob"])
        bucket = "zero" if cardinality == 0 else "one" if cardinality == 1 else "multiple"
        counts[bucket] += 1
        per_journal.append(
            {
                "journal_sha256": sha256_bytes(source["blob"]),
                "nodes": node_count,
                "task_identity_cardinality": cardinality,
            }
        )
    per_journal.sort(key=lambda row: row["journal_sha256"])
    invalid = counts["zero"] + counts["multiple"]
    stat = archive.stat()
    return {
        "protocol": PROTOCOL,
        "status": (
            "STRUCTURAL_TASK_IDENTITY_REJECTION_SUPPORTED"
            if invalid > 0
            else "TASK_IDENTITY_EXACTLY_ONE_IN_ALL_JOURNALS"
        ),
        "archive": {
            "relative_basename": archive.name,
            "sha256": actual_sha,
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
        },
        "journals": len(sources),
        "task_identity_cardinality_counts": counts,
        "invalid_journals": invalid,
        "per_journal": per_journal,
        "archive_audit": archive_audit,
        "security": {
            "journal_scanned_before_json": True,
            "env_members_read": False,
            "live_event_journal_members_read": False,
            "task_identity_values_emitted": False,
            "code_stdout_grade_or_metric_values_emitted": False,
        },
        "outcomes_read": False,
        "recommended_reason_code": (
            "JOURNAL_TASK_IDENTITY_NOT_EXACTLY_ONE_WITHIN_ARCHIVE"
            if invalid > 0
            else None
        ),
        "source_commit": source_commit,
    }


def write_new(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise AuditError("output exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".tmp-{os.getpid()}")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", required=True)
    parser.add_argument("--expect-archive-sha256", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        value = audit(Path(args.archive), args.expect_archive_sha256, args.source_commit)
        write_new(Path(args.output).resolve(), value)
        print(json.dumps(value, sort_keys=True, separators=(",", ":")))
        return 0
    except (AuditError, IntakeError, OSError) as exc:
        print(f"ARCHIVE_TASK_IDENTITY_AUDIT_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
