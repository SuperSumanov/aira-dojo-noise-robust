#!/usr/bin/env python3
"""Freeze a metadata-only partition of observed source archives."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any


OBSERVATION_PROTOCOL = "prospective_archive_observer_v1"
RECEIPT_PROTOCOL = "prospective_archive_disposition_partition_v1"
SHA_RX = re.compile(r"[0-9a-f]{64}")
ENTRY_KEYS = {
    "baseline",
    "committed_archive_sha256",
    "committed_snapshot_sha256",
    "first_stable_at_epoch",
    "last_observed_at_epoch",
    "mtime_ns",
    "path",
    "present",
    "rejected_archive_sha256",
    "rejection_reason_code",
    "rejection_registry_sha256",
    "size",
    "stable_observations",
}


class PartitionBuildError(RuntimeError):
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


def clean_relative(value: Any) -> str:
    if not isinstance(value, str):
        raise PartitionBuildError("archive path is not a string")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or len(path.parts) != 2
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise PartitionBuildError("archive path is not a clean two-part relative path")
    if not value.endswith(".tar.gz"):
        raise PartitionBuildError("archive path is not a tar.gz")
    return value


def nonnegative_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise PartitionBuildError(f"invalid {label}")
    return value


def sha_or_none(value: Any, label: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or SHA_RX.fullmatch(value) is None:
        raise PartitionBuildError(f"invalid {label}")
    return value


def build_receipt(
    observations_path: Path,
    expected_observations_sha256: str,
    expected_latest_snapshot_sha256: str,
) -> dict[str, Any]:
    if SHA_RX.fullmatch(expected_observations_sha256) is None:
        raise PartitionBuildError("invalid expected observations hash")
    if SHA_RX.fullmatch(expected_latest_snapshot_sha256) is None:
        raise PartitionBuildError("invalid expected latest snapshot hash")
    if observations_path.is_symlink() or not observations_path.is_file():
        raise PartitionBuildError("observations input is absent, non-regular, or symlinked")
    raw = observations_path.read_bytes()
    if digest(raw) != expected_observations_sha256:
        raise PartitionBuildError("observations hash mismatch")
    try:
        observations = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PartitionBuildError("cannot parse observations") from exc
    if not isinstance(observations, dict) or observations.get("protocol") != OBSERVATION_PROTOCOL:
        raise PartitionBuildError("observations protocol mismatch")
    if set(observations) != {"baseline_sealed_at_epoch", "entries", "protocol", "source_root"}:
        raise PartitionBuildError("observations top-level schema mismatch")
    entries = observations.get("entries")
    source_root = observations.get("source_root")
    if not isinstance(source_root, str) or not source_root.startswith("/"):
        raise PartitionBuildError("invalid source root")
    source_prefix = source_root.rstrip("/") + "/"
    if not isinstance(entries, dict) or not entries:
        raise PartitionBuildError("observations entries missing")

    counts = Counter()
    reasons = Counter()
    all_rows: list[list[Any]] = []
    baseline_rows: list[list[Any]] = []
    accepted_rows: list[list[Any]] = []
    rejected_rows: list[list[Any]] = []
    rejected_identities: list[dict[str, Any]] = []
    latest_seen = False
    for key, value in entries.items():
        relative = clean_relative(key)
        if not isinstance(value, dict) or set(value) != ENTRY_KEYS:
            raise PartitionBuildError("observation entry schema or path mismatch")
        observed_path = value.get("path")
        if (
            not isinstance(observed_path, str)
            or not observed_path.startswith(source_prefix)
            or observed_path[len(source_prefix) :] != relative
        ):
            raise PartitionBuildError("observation absolute/relative path mismatch")
        if value.get("present") is not True:
            raise PartitionBuildError("absent archive in frozen source population")
        baseline = value.get("baseline")
        if not isinstance(baseline, bool):
            raise PartitionBuildError("invalid baseline flag")
        size = nonnegative_int(value.get("size"), "archive size")
        mtime_ns = nonnegative_int(value.get("mtime_ns"), "archive mtime")
        stable = nonnegative_int(value.get("stable_observations"), "stable observations")
        if stable == 0:
            raise PartitionBuildError("archive lacks a stable observation")
        committed_archive = sha_or_none(value.get("committed_archive_sha256"), "commit hash")
        committed_snapshot = sha_or_none(value.get("committed_snapshot_sha256"), "snapshot hash")
        rejected_archive = sha_or_none(value.get("rejected_archive_sha256"), "rejection hash")
        rejection_registry = sha_or_none(value.get("rejection_registry_sha256"), "registry hash")
        reason = value.get("rejection_reason_code")
        accepted = committed_archive is not None or committed_snapshot is not None
        rejected = (
            rejected_archive is not None
            or rejection_registry is not None
            or reason is not None
        )
        if baseline:
            if accepted or rejected:
                raise PartitionBuildError("baseline archive also has a post-baseline disposition")
            disposition = "baseline"
            baseline_rows.append([relative, size, mtime_ns])
        elif accepted:
            if rejected or committed_archive is None or committed_snapshot is None:
                raise PartitionBuildError("incomplete or overlapping accepted disposition")
            disposition = "accepted"
            accepted_rows.append([relative, committed_archive, committed_snapshot])
            latest_seen |= committed_snapshot == expected_latest_snapshot_sha256
        elif rejected:
            if (
                rejected_archive is None
                or rejection_registry is None
                or not isinstance(reason, str)
                or not reason
            ):
                raise PartitionBuildError("incomplete rejected disposition")
            disposition = "rejected"
            reasons[reason] += 1
            rejected_rows.append([relative, rejected_archive, reason, rejection_registry])
            rejected_identities.append(
                {
                    "archive_relative_path": relative,
                    "archive_sha256": rejected_archive,
                    "reason_code": reason,
                    "rejection_registry_sha256": rejection_registry,
                }
            )
        else:
            disposition = "pending"
        counts[disposition] += 1
        all_rows.append([relative, disposition, size, mtime_ns])
    if not latest_seen:
        raise PartitionBuildError("latest snapshot is absent from accepted dispositions")
    if sum(counts.values()) != len(entries):
        raise PartitionBuildError("disposition partition does not cover observations")

    return {
        "protocol": RECEIPT_PROTOCOL,
        "status": "SOURCE_ARCHIVE_DISPOSITIONS_PARTITION_EXACT",
        "source_observations_sha256": expected_observations_sha256,
        "latest_snapshot_sha256": expected_latest_snapshot_sha256,
        "counts": {
            "observed_archives": len(entries),
            "baseline_archives": counts["baseline"],
            "accepted_archive_transactions": counts["accepted"],
            "rejected_archives": counts["rejected"],
            "pending_archives": counts["pending"],
        },
        "partition_checks": {
            "all_observed_archives_present": True,
            "mutually_exclusive": True,
            "collectively_exhaustive": True,
            "latest_snapshot_seen_in_accepted": True,
        },
        "reason_counts": dict(sorted(reasons.items())),
        "mapping_sha256": {
            "all_observed_path_disposition_size_mtime": canonical_lines(all_rows),
            "baseline_path_size_mtime": canonical_lines(baseline_rows),
            "accepted_path_archive_snapshot": canonical_lines(accepted_rows),
            "rejected_path_archive_reason_registry": canonical_lines(rejected_rows),
        },
        "rejected_archive_identities": sorted(
            rejected_identities, key=lambda row: row["archive_relative_path"]
        ),
        "access_attestation": {
            "observation_metadata_only": True,
            "archive_payloads_opened": False,
            "credentials_opened": False,
            "labels_grades_outcomes_or_predictions_read": False,
        },
    }


def write_new(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise PartitionBuildError("output exists")
    if not path.parent.is_dir() or path.parent.is_symlink():
        raise PartitionBuildError("output parent is absent or unsafe")
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
    parser.add_argument("--expect-latest-snapshot-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        receipt = build_receipt(
            args.observations,
            args.expect_observations_sha256,
            args.expect_latest_snapshot_sha256,
        )
        write_new(args.output.resolve(), receipt)
        print(json.dumps(receipt["counts"], sort_keys=True, separators=(",", ":")))
        return 0
    except (OSError, PartitionBuildError) as exc:
        print(f"ARCHIVE_DISPOSITION_PARTITION_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
