#!/usr/bin/env python3
"""Aggregate immutable archive dispositions without reading outcomes."""
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


REGISTRY_PROTOCOL = "prospective_structural_rejection_v1"
LEDGER_PROTOCOL = "prospective_structural_rejection_ledger_v1"
GATE_PROTOCOL = "prospective_structural_gate_independent_verifier_v5"
PARTITION_PROTOCOL = "prospective_archive_disposition_partition_v1"
REASONS = {
    "JOURNAL_TASK_IDENTITY_ABSENT_ALL_CHECKPOINTS",
    "JOURNAL_TASK_IDENTITY_NOT_EXACTLY_ONE_WITHIN_ARCHIVE",
    "ARCHIVE_HAS_NO_CHECKPOINT_JOURNALS",
}
IDENTITY_REASONS = REASONS - {"ARCHIVE_HAS_NO_CHECKPOINT_JOURNALS"}
SHA_RX = re.compile(r"[0-9a-f]{64}")
TX_RX = re.compile(r"(?P<day>[0-9]{4})-(?P<competition>.+)-(?P<seeds>[0-9]+)seeds-[0-9a-f]{16}")
ARCHIVE_RX = re.compile(r"(?P<competition>.+)-(?P<seeds>[0-9]+)seeds\.tar\.gz")


class LedgerBuildError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_object(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise LedgerBuildError(f"input is absent, non-regular, or symlinked: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LedgerBuildError(f"cannot parse JSON object: {path}") from exc
    if not isinstance(value, dict):
        raise LedgerBuildError(f"expected JSON object: {path}")
    return value


def nonnegative_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise LedgerBuildError(f"invalid {label}")
    return value


def logical_path(path: Path) -> str:
    value = path.as_posix()
    parts = PurePosixPath(value).parts
    if path.is_absolute() or not parts or any(part in {"", ".", ".."} for part in parts):
        raise LedgerBuildError("inputs must use clean repository-relative paths")
    return value


def accepted_transactions(gate: dict[str, Any]) -> list[dict[str, Any]]:
    if gate.get("protocol") != GATE_PROTOCOL:
        raise LedgerBuildError("structural-gate protocol mismatch")
    security = gate.get("security")
    if not isinstance(security, dict) or security.get("label_vault_opened") is not False:
        raise LedgerBuildError("structural gate does not attest a closed label vault")
    if security.get("outcome_files_opened") != []:
        raise LedgerBuildError("structural gate opened outcome files")
    inventory = gate.get("independent_inventory")
    inputs = gate.get("inputs")
    if not isinstance(inventory, dict) or not isinstance(inputs, dict):
        raise LedgerBuildError("structural-gate schema mismatch")
    expected_count = nonnegative_int(inventory.get("transactions"), "transaction count")
    summaries = inputs.get("intake_summary_sha256")
    if not isinstance(summaries, dict) or len(summaries) != expected_count:
        raise LedgerBuildError("accepted transaction accounting mismatch")
    rows: list[dict[str, Any]] = []
    for transaction_id, summary_sha in summaries.items():
        if not isinstance(transaction_id, str) or not isinstance(summary_sha, str):
            raise LedgerBuildError("invalid accepted transaction entry")
        match = TX_RX.fullmatch(transaction_id)
        if match is None or SHA_RX.fullmatch(summary_sha) is None:
            raise LedgerBuildError("invalid accepted transaction identity")
        rows.append(
            {
                "day": match.group("day"),
                "competition": match.group("competition"),
                "seed_count": int(match.group("seeds")),
                "transaction_id": transaction_id,
                "intake_summary_sha256": summary_sha,
            }
        )
    return sorted(rows, key=lambda row: row["transaction_id"])


def rejected_archives(
    registry_paths: list[Path],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    entries: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for unresolved in registry_paths:
        display_path = logical_path(unresolved)
        path = unresolved.resolve()
        registry = read_object(path)
        if (
            registry.get("protocol") != REGISTRY_PROTOCOL
            or registry.get("outcomes_read") is not False
        ):
            raise LedgerBuildError(f"unsafe or incompatible registry: {path}")
        rows = registry.get("entries")
        if not isinstance(rows, list) or not rows:
            raise LedgerBuildError(f"empty rejection registry: {path}")
        sources.append(
            {
                "path": display_path,
                "sha256": sha256(path),
                "entries": len(rows),
            }
        )
        for row in rows:
            if not isinstance(row, dict):
                raise LedgerBuildError("rejection entry is not an object")
            relative = row.get("archive_relative_path")
            archive_sha = row.get("archive_sha256")
            reason = row.get("reason_code")
            receipt_name = row.get("diagnostic_receipt_file")
            receipt_sha = row.get("diagnostic_receipt_sha256")
            if not isinstance(relative, str) or len(PurePosixPath(relative).parts) != 2:
                raise LedgerBuildError("invalid rejected archive path")
            day, basename = PurePosixPath(relative).parts
            match = ARCHIVE_RX.fullmatch(basename)
            if match is None or not day.isdigit() or len(day) != 4:
                raise LedgerBuildError("invalid rejected archive identity")
            if not isinstance(archive_sha, str) or SHA_RX.fullmatch(archive_sha) is None:
                raise LedgerBuildError("invalid rejected archive hash")
            if reason not in REASONS:
                raise LedgerBuildError("unknown rejection reason")
            if (
                not isinstance(receipt_name, str)
                or PurePosixPath(receipt_name).name != receipt_name
            ):
                raise LedgerBuildError("invalid diagnostic receipt basename")
            if not isinstance(receipt_sha, str) or SHA_RX.fullmatch(receipt_sha) is None:
                raise LedgerBuildError("invalid diagnostic receipt hash")
            receipt_path = path.parent / receipt_name
            receipt = read_object(receipt_path)
            if sha256(receipt_path) != receipt_sha:
                raise LedgerBuildError("diagnostic receipt hash mismatch")
            if receipt.get("protocol") == "prospective_structural_diagnostic_v1":
                if receipt.get("labels_or_outcomes_read") is not False:
                    raise LedgerBuildError("legacy diagnostic is not outcome-blind")
                if receipt.get("reason_code") != reason:
                    raise LedgerBuildError("legacy diagnostic reason mismatch")
                if receipt.get("archive_sha256") != archive_sha:
                    raise LedgerBuildError("legacy diagnostic archive mismatch")
            else:
                if receipt.get("outcomes_read") is not False:
                    raise LedgerBuildError("diagnostic receipt is not outcome-blind")
                if receipt.get("recommended_reason_code") != reason:
                    raise LedgerBuildError("diagnostic receipt reason mismatch")
                archive_receipt = receipt.get("archive")
                if (
                    not isinstance(archive_receipt, dict)
                    or archive_receipt.get("sha256") != archive_sha
                ):
                    raise LedgerBuildError("diagnostic receipt archive mismatch")
            key = (relative, archive_sha)
            if key in seen:
                raise LedgerBuildError("duplicate rejected archive identity")
            seen.add(key)
            entries.append(
                {
                    "day": day,
                    "competition": match.group("competition"),
                    "seed_count": int(match.group("seeds")),
                    "archive_relative_path": relative,
                    "archive_sha256": archive_sha,
                    "archive_size": nonnegative_int(row.get("archive_size"), "archive size"),
                    "archive_mtime_ns": nonnegative_int(
                        row.get("archive_mtime_ns"), "archive mtime"
                    ),
                    "reason_code": reason,
                    "diagnostic_receipt_sha256": receipt_sha,
                    "rejection_registry_sha256": sources[-1]["sha256"],
                }
            )
    return (
        sorted(entries, key=lambda row: (row["archive_mtime_ns"], row["archive_relative_path"])),
        sorted(sources, key=lambda row: row["path"]),
    )


def build_ledger(
    gate_path: Path,
    partition_receipt_path: Path,
    registry_paths: list[Path],
) -> dict[str, Any]:
    gate_display_path = logical_path(gate_path)
    partition_display_path = logical_path(partition_receipt_path)
    gate_path = gate_path.resolve()
    partition_receipt_path = partition_receipt_path.resolve()
    gate = read_object(gate_path)
    partition = read_object(partition_receipt_path)
    accepted = accepted_transactions(gate)
    rejected, sources = rejected_archives(registry_paths)
    accepted_count = len(accepted)
    rejected_count = len(rejected)
    settled_count = accepted_count + rejected_count
    if settled_count == 0:
        raise LedgerBuildError("empty settled archive population")

    expected_partition_access = {
        "observation_metadata_only": True,
        "archive_payloads_opened": False,
        "credentials_opened": False,
        "labels_grades_outcomes_or_predictions_read": False,
    }
    if (
        partition.get("protocol") != PARTITION_PROTOCOL
        or partition.get("status") != "SOURCE_ARCHIVE_DISPOSITIONS_PARTITION_EXACT"
        or partition.get("access_attestation") != expected_partition_access
        or partition.get("partition_checks")
        != {
            "all_observed_archives_present": True,
            "mutually_exclusive": True,
            "collectively_exhaustive": True,
            "latest_snapshot_seen_in_accepted": True,
        }
    ):
        raise LedgerBuildError("source archive partition contract mismatch")
    partition_counts = partition.get("counts")
    if not isinstance(partition_counts, dict):
        raise LedgerBuildError("source archive partition counts missing")
    if set(partition_counts) != {
        "observed_archives",
        "baseline_archives",
        "accepted_archive_transactions",
        "rejected_archives",
        "pending_archives",
    }:
        raise LedgerBuildError("source archive partition counts mismatch")
    normalized_partition_counts = {
        key: nonnegative_int(value, f"partition {key}")
        for key, value in partition_counts.items()
    }
    if (
        normalized_partition_counts["accepted_archive_transactions"] != accepted_count
        or normalized_partition_counts["rejected_archives"] != rejected_count
        or normalized_partition_counts["pending_archives"] != 0
        or normalized_partition_counts["observed_archives"]
        != normalized_partition_counts["baseline_archives"] + settled_count
    ):
        raise LedgerBuildError("source archive partition counts mismatch")
    if partition.get("latest_snapshot_sha256") != gate.get("snapshot_sha256"):
        raise LedgerBuildError("source archive partition snapshot mismatch")

    reasons = Counter(row["reason_code"] for row in rejected)
    if partition.get("reason_counts") != dict(sorted(reasons.items())):
        raise LedgerBuildError("source archive partition reason counts mismatch")
    partition_rejected = partition.get("rejected_archive_identities")
    expected_rejected = sorted(
        [
            {
                "archive_relative_path": row["archive_relative_path"],
                "archive_sha256": row["archive_sha256"],
                "reason_code": row["reason_code"],
                "rejection_registry_sha256": row["rejection_registry_sha256"],
            }
            for row in rejected
        ],
        key=lambda row: row["archive_relative_path"],
    )
    if partition_rejected != expected_rejected:
        raise LedgerBuildError("source partition and immutable rejection registries disagree")
    identity_count = sum(reasons[reason] for reason in IDENTITY_REASONS)
    accepted_by_competition: dict[str, list[dict[str, Any]]] = {}
    rejected_by_competition: dict[str, list[dict[str, Any]]] = {}
    for row in accepted:
        accepted_by_competition.setdefault(row["competition"], []).append(row)
    for row in rejected:
        rejected_by_competition.setdefault(row["competition"], []).append(row)
    rejected_competitions = sorted(rejected_by_competition)
    mixed = sorted(set(accepted_by_competition) & set(rejected_by_competition))
    timelines = []
    for competition in rejected_competitions:
        timelines.append(
            {
                "competition": competition,
                "accepted_days": sorted(
                    {row["day"] for row in accepted_by_competition.get(competition, [])}
                ),
                "rejected_days": sorted(
                    {row["day"] for row in rejected_by_competition[competition]}
                ),
                "accepted_archive_transactions": len(
                    accepted_by_competition.get(competition, [])
                ),
                "rejected_archives": len(rejected_by_competition[competition]),
            }
        )

    return {
        "protocol": LEDGER_PROTOCOL,
        "status": "OUTCOME_BLIND_ARCHIVE_DISPOSITION_AUDIT_COMPLETE",
        "source_structural_gate": {
            "path": gate_display_path,
            "sha256": sha256(gate_path),
            "snapshot_sha256": gate.get("snapshot_sha256"),
        },
        "source_archive_partition_receipt": {
            "path": partition_display_path,
            "sha256": sha256(partition_receipt_path),
            "source_observations_sha256": partition.get("source_observations_sha256"),
        },
        "source_rejection_registries": sources,
        "counts": {
            "accepted_archive_transactions": accepted_count,
            "rejected_archives": rejected_count,
            "settled_archive_decisions": settled_count,
            "identity_related_rejections": identity_count,
            "rejected_competitions": len(rejected_competitions),
            "mixed_disposition_competitions": len(mixed),
            "baseline_archives": normalized_partition_counts["baseline_archives"],
            "observed_archives": normalized_partition_counts["observed_archives"],
            "pending_archives": normalized_partition_counts["pending_archives"],
        },
        "fractions": {
            "rejected_over_settled": {
                "numerator": rejected_count,
                "denominator": settled_count,
                "value": rejected_count / settled_count,
            },
            "identity_related_over_rejected": {
                "numerator": identity_count,
                "denominator": rejected_count,
                "value": identity_count / rejected_count if rejected_count else None,
            },
            "mixed_disposition_over_rejected_competitions": {
                "numerator": len(mixed),
                "denominator": len(rejected_competitions),
                "value": len(mixed) / len(rejected_competitions)
                if rejected_competitions
                else None,
            },
        },
        "reason_counts": dict(sorted(reasons.items())),
        "rejected_archive_entries": rejected,
        "rejected_competition_timelines": timelines,
        "claim_boundary": {
            "labels_grades_outcomes_or_winner_orientation_read": False,
            "prediction_values_aggregated": False,
            "accuracy_effect_or_search_utility_computed": False,
            "causal_effect_of_metadata_changes_estimated": False,
            "unit_of_validation": "archive_not_competition",
            "source_archive_partition_complete": True,
        },
    }


def write_new(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise LedgerBuildError("output exists")
    if not path.parent.is_dir() or path.parent.is_symlink():
        raise LedgerBuildError("output parent is absent or unsafe")
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
    parser.add_argument("--structural-gate", required=True, type=Path)
    parser.add_argument("--archive-partition-receipt", required=True, type=Path)
    parser.add_argument("--rejection-registry", required=True, action="append", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        value = build_ledger(
            args.structural_gate,
            args.archive_partition_receipt,
            args.rejection_registry,
        )
        write_new(args.output.resolve(), value)
        print(json.dumps(value["counts"], sort_keys=True, separators=(",", ":")))
        return 0
    except (OSError, LedgerBuildError) as exc:
        print(f"STRUCTURAL_REJECTION_LEDGER_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
