#!/usr/bin/env python3
"""Independently verify the outcome-blind structural rejection ledger."""
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


LEDGER_PROTOCOL = "prospective_structural_rejection_ledger_v1"
REGISTRY_PROTOCOL = "prospective_structural_rejection_v1"
IDENTITY_REASONS = {
    "JOURNAL_TASK_IDENTITY_ABSENT_ALL_CHECKPOINTS",
    "JOURNAL_TASK_IDENTITY_NOT_EXACTLY_ONE_WITHIN_ARCHIVE",
}
TX_RX = re.compile(r"(?P<day>[0-9]{4})-(?P<competition>.+)-(?P<seeds>[0-9]+)seeds-[0-9a-f]{16}")
ARCHIVE_RX = re.compile(r"(?P<competition>.+)-(?P<seeds>[0-9]+)seeds\.tar\.gz")


class LedgerVerificationError(RuntimeError):
    pass


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read_object(path: Path) -> tuple[bytes, dict[str, Any]]:
    if path.is_symlink() or not path.is_file():
        raise LedgerVerificationError(f"input is absent, non-regular, or symlinked: {path}")
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LedgerVerificationError(f"cannot parse JSON: {path}") from exc
    if not isinstance(value, dict):
        raise LedgerVerificationError(f"expected JSON object: {path}")
    return raw, value


def resolve_repo_path(repo_root: Path, value: Any) -> Path:
    if not isinstance(value, str):
        raise LedgerVerificationError("recorded source path is not a string")
    pure = PurePosixPath(value)
    if pure.is_absolute() or not pure.parts or any(part in {"", ".", ".."} for part in pure.parts):
        raise LedgerVerificationError("recorded source path is unsafe")
    path = repo_root.joinpath(*pure.parts)
    resolved = path.resolve()
    try:
        resolved.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise LedgerVerificationError("recorded source escapes repository") from exc
    return resolved


def verify(ledger_path: Path, repo_root: Path) -> dict[str, Any]:
    ledger_raw, ledger = read_object(ledger_path.resolve())
    if ledger.get("protocol") != LEDGER_PROTOCOL:
        raise LedgerVerificationError("ledger protocol mismatch")
    if ledger.get("status") != "OUTCOME_BLIND_ARCHIVE_DISPOSITION_AUDIT_COMPLETE":
        raise LedgerVerificationError("ledger status mismatch")

    gate_source = ledger.get("source_structural_gate")
    if not isinstance(gate_source, dict):
        raise LedgerVerificationError("missing structural-gate source")
    gate_path = resolve_repo_path(repo_root, gate_source.get("path"))
    gate_raw, gate = read_object(gate_path)
    if digest(gate_raw) != gate_source.get("sha256"):
        raise LedgerVerificationError("structural-gate hash mismatch")
    if gate.get("snapshot_sha256") != gate_source.get("snapshot_sha256"):
        raise LedgerVerificationError("structural-gate snapshot mismatch")
    security = gate.get("security")
    if not isinstance(security, dict):
        raise LedgerVerificationError("missing structural-gate security receipt")
    if (
        security.get("label_vault_opened") is not False
        or security.get("outcome_files_opened") != []
    ):
        raise LedgerVerificationError("structural gate is not outcome-blind")
    inventory = gate.get("independent_inventory")
    summaries = gate.get("inputs", {}).get("intake_summary_sha256")
    if not isinstance(inventory, dict) or not isinstance(summaries, dict):
        raise LedgerVerificationError("structural-gate accounting missing")
    accepted_count = inventory.get("transactions")
    if isinstance(accepted_count, bool) or not isinstance(accepted_count, int):
        raise LedgerVerificationError("invalid accepted transaction count")
    if len(summaries) != accepted_count:
        raise LedgerVerificationError("accepted transaction accounting mismatch")

    partition_source = ledger.get("source_archive_partition_receipt")
    if not isinstance(partition_source, dict):
        raise LedgerVerificationError("missing archive partition receipt source")
    partition_path = resolve_repo_path(repo_root, partition_source.get("path"))
    partition_raw, partition = read_object(partition_path)
    if digest(partition_raw) != partition_source.get("sha256"):
        raise LedgerVerificationError("archive partition receipt hash mismatch")
    if partition.get("source_observations_sha256") != partition_source.get(
        "source_observations_sha256"
    ):
        raise LedgerVerificationError("archive partition observations hash mismatch")
    if (
        partition.get("protocol") != "prospective_archive_disposition_partition_v1"
        or partition.get("status") != "SOURCE_ARCHIVE_DISPOSITIONS_PARTITION_EXACT"
        or partition.get("latest_snapshot_sha256") != gate.get("snapshot_sha256")
        or partition.get("access_attestation")
        != {
            "observation_metadata_only": True,
            "archive_payloads_opened": False,
            "credentials_opened": False,
            "labels_grades_outcomes_or_predictions_read": False,
        }
        or partition.get("partition_checks")
        != {
            "all_observed_archives_present": True,
            "mutually_exclusive": True,
            "collectively_exhaustive": True,
            "latest_snapshot_seen_in_accepted": True,
        }
    ):
        raise LedgerVerificationError("archive partition receipt contract mismatch")

    accepted_by_competition: dict[str, list[str]] = {}
    for transaction_id in summaries:
        if not isinstance(transaction_id, str):
            raise LedgerVerificationError("invalid accepted transaction ID")
        match = TX_RX.fullmatch(transaction_id)
        if match is None:
            raise LedgerVerificationError("malformed accepted transaction ID")
        accepted_by_competition.setdefault(match.group("competition"), []).append(
            match.group("day")
        )

    registry_sources = ledger.get("source_rejection_registries")
    if not isinstance(registry_sources, list) or not registry_sources:
        raise LedgerVerificationError("missing rejection registry sources")
    rejected: list[dict[str, Any]] = []
    rejected_by_competition: dict[str, list[str]] = {}
    seen: set[tuple[str, str]] = set()
    for source in registry_sources:
        if not isinstance(source, dict):
            raise LedgerVerificationError("invalid rejection source")
        path = resolve_repo_path(repo_root, source.get("path"))
        raw, registry = read_object(path)
        if digest(raw) != source.get("sha256"):
            raise LedgerVerificationError("rejection registry hash mismatch")
        rows = registry.get("entries")
        if (
            registry.get("protocol") != REGISTRY_PROTOCOL
            or registry.get("outcomes_read") is not False
            or not isinstance(rows, list)
            or len(rows) != source.get("entries")
        ):
            raise LedgerVerificationError("rejection registry contract mismatch")
        for row in rows:
            if not isinstance(row, dict):
                raise LedgerVerificationError("invalid rejected archive row")
            relative = row.get("archive_relative_path")
            archive_sha = row.get("archive_sha256")
            if not isinstance(relative, str) or not isinstance(archive_sha, str):
                raise LedgerVerificationError("invalid rejected archive identity")
            parts = PurePosixPath(relative).parts
            if len(parts) != 2:
                raise LedgerVerificationError("malformed rejected archive path")
            match = ARCHIVE_RX.fullmatch(parts[1])
            if match is None:
                raise LedgerVerificationError("malformed rejected archive basename")
            key = (relative, archive_sha)
            if key in seen:
                raise LedgerVerificationError("duplicate rejected archive")
            seen.add(key)
            receipt_name = row.get("diagnostic_receipt_file")
            receipt_sha = row.get("diagnostic_receipt_sha256")
            if (
                not isinstance(receipt_name, str)
                or PurePosixPath(receipt_name).name != receipt_name
            ):
                raise LedgerVerificationError("unsafe diagnostic receipt path")
            receipt_raw, receipt = read_object(path.parent / receipt_name)
            if digest(receipt_raw) != receipt_sha:
                raise LedgerVerificationError("diagnostic receipt hash mismatch")
            if receipt.get("protocol") == "prospective_structural_diagnostic_v1":
                if receipt.get("labels_or_outcomes_read") is not False:
                    raise LedgerVerificationError("legacy diagnostic read labels or outcomes")
                if receipt.get("reason_code") != row.get("reason_code"):
                    raise LedgerVerificationError("legacy diagnostic reason mismatch")
                if receipt.get("archive_sha256") != archive_sha:
                    raise LedgerVerificationError("legacy diagnostic archive mismatch")
            else:
                if receipt.get("outcomes_read") is not False:
                    raise LedgerVerificationError("diagnostic receipt read outcomes")
                if receipt.get("recommended_reason_code") != row.get("reason_code"):
                    raise LedgerVerificationError("diagnostic reason mismatch")
            competition = match.group("competition")
            rejected_by_competition.setdefault(competition, []).append(parts[0])
            rejected.append(
                {
                    "day": parts[0],
                    "competition": competition,
                    "seed_count": int(match.group("seeds")),
                    "archive_relative_path": relative,
                    "archive_sha256": archive_sha,
                    "archive_size": row.get("archive_size"),
                    "archive_mtime_ns": row.get("archive_mtime_ns"),
                    "reason_code": row.get("reason_code"),
                    "diagnostic_receipt_sha256": receipt_sha,
                    "rejection_registry_sha256": source.get("sha256"),
                }
            )

    rejected.sort(key=lambda row: (row["archive_mtime_ns"], row["archive_relative_path"]))
    if ledger.get("rejected_archive_entries") != rejected:
        raise LedgerVerificationError("rejected archive entries mismatch")
    reason_counts = Counter(row["reason_code"] for row in rejected)
    if partition.get("reason_counts") != dict(sorted(reason_counts.items())):
        raise LedgerVerificationError("archive partition reason counts mismatch")
    identity_count = sum(reason_counts[reason] for reason in IDENTITY_REASONS)
    mixed = sorted(set(accepted_by_competition) & set(rejected_by_competition))
    partition_counts = partition.get("counts")
    if not isinstance(partition_counts, dict):
        raise LedgerVerificationError("archive partition counts missing")
    expected_partition_counts = {
        "accepted_archive_transactions": accepted_count,
        "rejected_archives": len(rejected),
        "pending_archives": 0,
    }
    if any(partition_counts.get(key) != value for key, value in expected_partition_counts.items()):
        raise LedgerVerificationError("archive partition disposition counts mismatch")
    baseline_count = partition_counts.get("baseline_archives")
    observed_count = partition_counts.get("observed_archives")
    if (
        isinstance(baseline_count, bool)
        or not isinstance(baseline_count, int)
        or isinstance(observed_count, bool)
        or not isinstance(observed_count, int)
        or observed_count != baseline_count + accepted_count + len(rejected)
    ):
        raise LedgerVerificationError("archive partition total mismatch")
    expected_partition_rejected = sorted(
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
    if partition.get("rejected_archive_identities") != expected_partition_rejected:
        raise LedgerVerificationError("archive partition rejection identities mismatch")
    expected_counts = {
        "accepted_archive_transactions": accepted_count,
        "rejected_archives": len(rejected),
        "settled_archive_decisions": accepted_count + len(rejected),
        "baseline_archives": baseline_count,
        "observed_archives": observed_count,
        "pending_archives": 0,
        "identity_related_rejections": identity_count,
        "rejected_competitions": len(rejected_by_competition),
        "mixed_disposition_competitions": len(mixed),
    }
    if ledger.get("counts") != expected_counts:
        raise LedgerVerificationError("ledger counts mismatch")
    expected_fractions = {
        "rejected_over_settled": {
            "numerator": len(rejected),
            "denominator": accepted_count + len(rejected),
            "value": len(rejected) / (accepted_count + len(rejected)),
        },
        "identity_related_over_rejected": {
            "numerator": identity_count,
            "denominator": len(rejected),
            "value": identity_count / len(rejected),
        },
        "mixed_disposition_over_rejected_competitions": {
            "numerator": len(mixed),
            "denominator": len(rejected_by_competition),
            "value": len(mixed) / len(rejected_by_competition),
        },
    }
    if ledger.get("fractions") != expected_fractions:
        raise LedgerVerificationError("ledger fractions mismatch")
    if ledger.get("reason_counts") != dict(sorted(reason_counts.items())):
        raise LedgerVerificationError("reason counts mismatch")

    expected_timelines = []
    for competition in sorted(rejected_by_competition):
        expected_timelines.append(
            {
                "competition": competition,
                "accepted_days": sorted(set(accepted_by_competition.get(competition, []))),
                "rejected_days": sorted(set(rejected_by_competition[competition])),
                "accepted_archive_transactions": len(
                    accepted_by_competition.get(competition, [])
                ),
                "rejected_archives": len(rejected_by_competition[competition]),
            }
        )
    if ledger.get("rejected_competition_timelines") != expected_timelines:
        raise LedgerVerificationError("competition timelines mismatch")
    expected_boundary = {
        "labels_grades_outcomes_or_winner_orientation_read": False,
        "prediction_values_aggregated": False,
        "accuracy_effect_or_search_utility_computed": False,
        "causal_effect_of_metadata_changes_estimated": False,
        "unit_of_validation": "archive_not_competition",
        "source_archive_partition_complete": True,
    }
    if ledger.get("claim_boundary") != expected_boundary:
        raise LedgerVerificationError("claim boundary mismatch")
    return {
        "protocol": "independent_prospective_structural_rejection_ledger_verifier_v1",
        "status": "INDEPENDENT_STRUCTURAL_REJECTION_LEDGER_PASS",
        "ledger_sha256": digest(ledger_raw),
        "recomputed_counts": expected_counts,
        "recomputed_reason_counts": dict(sorted(reason_counts.items())),
        "outcomes_read": False,
        "prediction_values_aggregated": False,
        "randomness_used": False,
    }


def write_new(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise LedgerVerificationError("output exists")
    if not path.parent.is_dir() or path.parent.is_symlink():
        raise LedgerVerificationError("output parent is absent or unsafe")
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
    parser.add_argument("--ledger", required=True, type=Path)
    parser.add_argument("--repo-root", default=Path("."), type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        receipt = verify(args.ledger, args.repo_root.resolve())
        write_new(args.output.resolve(), receipt)
        print(json.dumps(receipt["recomputed_counts"], sort_keys=True, separators=(",", ":")))
        return 0
    except (OSError, LedgerVerificationError) as exc:
        print(f"STRUCTURAL_REJECTION_LEDGER_VERIFY_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
