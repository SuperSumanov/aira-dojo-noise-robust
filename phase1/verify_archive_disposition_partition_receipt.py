#!/usr/bin/env python3
"""Independently verify a metadata-only archive disposition partition."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any


class PartitionVerificationError(RuntimeError):
    pass


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_lines(rows: list[list[Any]]) -> str:
    return digest(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for row in sorted(rows)
        ).encode("utf-8")
    )


def read_object(path: Path) -> tuple[bytes, dict[str, Any]]:
    if path.is_symlink() or not path.is_file():
        raise PartitionVerificationError("input is absent, non-regular, or symlinked")
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PartitionVerificationError("cannot parse input JSON") from exc
    if not isinstance(value, dict):
        raise PartitionVerificationError("input is not a JSON object")
    return raw, value


def verify(
    observations_path: Path,
    expected_observations_sha256: str,
    receipt_path: Path,
    expected_receipt_sha256: str,
) -> dict[str, Any]:
    observations_raw, observations = read_object(observations_path)
    receipt_raw, receipt = read_object(receipt_path)
    if digest(observations_raw) != expected_observations_sha256:
        raise PartitionVerificationError("observations hash mismatch")
    if digest(receipt_raw) != expected_receipt_sha256:
        raise PartitionVerificationError("partition receipt hash mismatch")
    if observations.get("protocol") != "prospective_archive_observer_v1":
        raise PartitionVerificationError("observations protocol mismatch")
    if receipt.get("protocol") != "prospective_archive_disposition_partition_v1":
        raise PartitionVerificationError("partition protocol mismatch")
    if receipt.get("source_observations_sha256") != expected_observations_sha256:
        raise PartitionVerificationError("partition source binding mismatch")
    source_root = observations.get("source_root")
    entries = observations.get("entries")
    if not isinstance(source_root, str) or not isinstance(entries, dict) or not entries:
        raise PartitionVerificationError("observations schema mismatch")
    source_prefix = source_root.rstrip("/") + "/"

    counts = Counter()
    reasons = Counter()
    all_rows: list[list[Any]] = []
    baseline_rows: list[list[Any]] = []
    accepted_rows: list[list[Any]] = []
    rejected_rows: list[list[Any]] = []
    rejected_identities: list[dict[str, Any]] = []
    latest_snapshot = receipt.get("latest_snapshot_sha256")
    latest_seen = False
    for relative, row in entries.items():
        if not isinstance(relative, str) or not isinstance(row, dict):
            raise PartitionVerificationError("invalid observation row")
        if row.get("path") != source_prefix + relative or row.get("present") is not True:
            raise PartitionVerificationError("observation path/presence mismatch")
        baseline = row.get("baseline") is True
        accepted = (
            row.get("committed_archive_sha256") is not None
            or row.get("committed_snapshot_sha256") is not None
        )
        rejected = (
            row.get("rejected_archive_sha256") is not None
            or row.get("rejection_registry_sha256") is not None
            or row.get("rejection_reason_code") is not None
        )
        size = row.get("size")
        mtime_ns = row.get("mtime_ns")
        if baseline:
            if accepted or rejected:
                raise PartitionVerificationError("baseline disposition overlap")
            disposition = "baseline"
            baseline_rows.append([relative, size, mtime_ns])
        elif accepted:
            archive_sha = row.get("committed_archive_sha256")
            snapshot_sha = row.get("committed_snapshot_sha256")
            if rejected or archive_sha is None or snapshot_sha is None:
                raise PartitionVerificationError("accepted disposition overlap")
            disposition = "accepted"
            accepted_rows.append([relative, archive_sha, snapshot_sha])
            latest_seen |= snapshot_sha == latest_snapshot
        elif rejected:
            archive_sha = row.get("rejected_archive_sha256")
            registry_sha = row.get("rejection_registry_sha256")
            reason = row.get("rejection_reason_code")
            if archive_sha is None or registry_sha is None or not isinstance(reason, str):
                raise PartitionVerificationError("incomplete rejected disposition")
            disposition = "rejected"
            reasons[reason] += 1
            rejected_rows.append([relative, archive_sha, reason, registry_sha])
            rejected_identities.append(
                {
                    "archive_relative_path": relative,
                    "archive_sha256": archive_sha,
                    "reason_code": reason,
                    "rejection_registry_sha256": registry_sha,
                }
            )
        else:
            disposition = "pending"
        counts[disposition] += 1
        all_rows.append([relative, disposition, size, mtime_ns])

    expected_counts = {
        "observed_archives": len(entries),
        "baseline_archives": counts["baseline"],
        "accepted_archive_transactions": counts["accepted"],
        "rejected_archives": counts["rejected"],
        "pending_archives": counts["pending"],
    }
    expected_mappings = {
        "all_observed_path_disposition_size_mtime": canonical_lines(all_rows),
        "baseline_path_size_mtime": canonical_lines(baseline_rows),
        "accepted_path_archive_snapshot": canonical_lines(accepted_rows),
        "rejected_path_archive_reason_registry": canonical_lines(rejected_rows),
    }
    if receipt.get("counts") != expected_counts:
        raise PartitionVerificationError("partition counts mismatch")
    if receipt.get("mapping_sha256") != expected_mappings:
        raise PartitionVerificationError("partition mapping hashes mismatch")
    if receipt.get("reason_counts") != dict(sorted(reasons.items())):
        raise PartitionVerificationError("partition reason counts mismatch")
    if receipt.get("rejected_archive_identities") != sorted(
        rejected_identities, key=lambda row: row["archive_relative_path"]
    ):
        raise PartitionVerificationError("partition rejection identities mismatch")
    if not latest_seen:
        raise PartitionVerificationError("latest snapshot not found")
    if receipt.get("partition_checks") != {
        "all_observed_archives_present": True,
        "mutually_exclusive": True,
        "collectively_exhaustive": True,
        "latest_snapshot_seen_in_accepted": True,
    }:
        raise PartitionVerificationError("partition check receipt mismatch")
    if receipt.get("access_attestation") != {
        "observation_metadata_only": True,
        "archive_payloads_opened": False,
        "credentials_opened": False,
        "labels_grades_outcomes_or_predictions_read": False,
    }:
        raise PartitionVerificationError("partition access attestation mismatch")
    return {
        "protocol": "independent_prospective_archive_disposition_partition_v1",
        "status": "INDEPENDENT_ARCHIVE_DISPOSITION_PARTITION_PASS",
        "source_observations_sha256": expected_observations_sha256,
        "partition_receipt_sha256": expected_receipt_sha256,
        "recomputed_counts": expected_counts,
        "recomputed_reason_counts": dict(sorted(reasons.items())),
        "recomputed_mapping_sha256": expected_mappings,
        "outcomes_or_predictions_read": False,
        "randomness_used": False,
    }


def write_new(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise PartitionVerificationError("output exists")
    if not path.parent.is_dir() or path.parent.is_symlink():
        raise PartitionVerificationError("output parent is absent or unsafe")
    temporary = path.with_name(path.name + f".tmp-{os.getpid()}")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--observations", required=True, type=Path)
    parser.add_argument("--expect-observations-sha256", required=True)
    parser.add_argument("--partition-receipt", required=True, type=Path)
    parser.add_argument("--expect-partition-receipt-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = verify(
            args.observations,
            args.expect_observations_sha256,
            args.partition_receipt,
            args.expect_partition_receipt_sha256,
        )
        write_new(args.output.resolve(), result)
        print(json.dumps(result["recomputed_counts"], sort_keys=True, separators=(",", ":")))
        return 0
    except (OSError, PartitionVerificationError) as exc:
        print(f"ARCHIVE_DISPOSITION_PARTITION_VERIFY_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
