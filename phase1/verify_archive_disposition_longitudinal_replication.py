#!/usr/bin/env python3
"""Independent verifier for the archive-disposition longitudinal replication."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any


SHA_RX = re.compile(r"[0-9a-f]{64}")
SEED_NAME_RX = re.compile(r"(?P<task>.+)-(?P<seeds>[0-9]+)seeds\.tar\.gz")
NON_TASK_CHARACTER = re.compile(r"[^a-z0-9]+")
TRANSACTION_FIELDS = {
    "archive_relative_path",
    "archive_sha256",
    "archive_size",
    "committed_at_utc",
    "drop_id",
    "intake_dir",
    "intake_summary_sha256",
    "score_dir",
    "score_summary_sha256",
}
PROVENANCE_REQUIRED_FIELDS = {
    "archive_name",
    "archive_sha256",
    "eligible",
    "empty_code_nodes_excluded",
    "endpoints",
    "flow_status",
    "generation_started_at_utc",
    "journal_member",
    "journal_mtime",
    "journal_sha256",
    "run_id",
    "task",
}
PROVENANCE_OPTIONAL_FIELDS = {"competition_id_source"}


class VerificationError(RuntimeError):
    pass


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def load(path: Path, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise VerificationError(f"unsafe {label} path")
    try:
        value = json.loads(path.read_bytes())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VerificationError(f"cannot parse {label}") from exc
    if not isinstance(value, dict):
        raise VerificationError(f"{label} is not an object")
    return value


def integer(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise VerificationError(f"invalid {label}")
    return value


def unit_fraction(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise VerificationError(f"invalid {label}")
    normalized = float(value)
    if not math.isfinite(normalized) or not 0.0 <= normalized <= 1.0:
        raise VerificationError(f"invalid {label}")
    return normalized


def sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or SHA_RX.fullmatch(value) is None:
        raise VerificationError(f"invalid {label}")
    return value


def archive_parts(relative: Any) -> tuple[str, str]:
    if not isinstance(relative, str):
        raise VerificationError("non-string archive path")
    path = PurePosixPath(relative)
    parts = path.parts
    if path.is_absolute() or len(parts) != 2 or any(
        item in {"", ".", ".."} for item in parts
    ):
        raise VerificationError("malformed archive path")
    directory, basename = parts
    if not basename.endswith(".tar.gz"):
        raise VerificationError("malformed archive suffix")
    return directory, basename


def canonical_task(value: Any) -> str:
    if not isinstance(value, str):
        raise VerificationError("non-string task metadata")
    normalized = NON_TASK_CHARACTER.sub("-", value.casefold()).strip("-")
    if not normalized:
        raise VerificationError("empty canonical task")
    return normalized


def rejected_task(relative: Any) -> str:
    _directory, basename = archive_parts(relative)
    match = SEED_NAME_RX.fullmatch(basename)
    if match is None:
        raise VerificationError("rejected archive lacks seeded filename")
    return canonical_task(match.group("task"))


def load_list(path: Path, label: str) -> list[Any]:
    if path.is_symlink() or not path.is_file():
        raise VerificationError(f"unsafe {label} path")
    try:
        value = json.loads(path.read_bytes())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VerificationError(f"cannot parse {label}") from exc
    if not isinstance(value, list):
        raise VerificationError(f"{label} is not a list")
    return value


def load_lines(path: Path, label: str) -> list[dict[str, Any]]:
    if path.is_symlink() or not path.is_file():
        raise VerificationError(f"unsafe {label} path")
    rows: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            value = json.loads(line)
            if not isinstance(value, dict):
                raise VerificationError(f"non-object {label} row")
            rows.append(value)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VerificationError(f"cannot parse {label}") from exc
    if not rows:
        raise VerificationError(f"empty {label}")
    return rows


def interval(successes: int, total: int) -> list[float]:
    if total <= 0 or successes < 0 or successes > total:
        raise VerificationError("invalid interval inputs")
    z = 1.959963984540054
    p = successes / total
    z2 = z**2
    divisor = 1.0 + z2 / total
    midpoint = (p + z2 / (2.0 * total)) / divisor
    radius = z * math.sqrt((p * (1.0 - p) + z2 / (4.0 * total)) / total) / divisor
    return [midpoint - radius, midpoint + radius]


def proportion(successes: int, total: int) -> dict[str, Any]:
    return {
        "numerator": successes,
        "denominator": total,
        "value": successes / total,
        "wilson_95": interval(successes, total),
    }


def assert_equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise VerificationError(f"{label} mismatch")


def reconstruct_accepted_tasks(
    state_root: Path,
    snapshot_sha: str,
    accepted: dict[str, str],
    known: dict[str, Any],
) -> tuple[set[str], dict[str, int]]:
    if state_root.is_symlink() or not state_root.is_dir():
        raise VerificationError("unsafe state root")
    state = state_root.resolve()
    snapshot = state / "snapshots" / snapshot_sha
    if snapshot.is_symlink() or not snapshot.is_dir():
        raise VerificationError("unsafe snapshot root")
    manifest = snapshot / "SHA256SUMS"
    if digest(manifest) != snapshot_sha:
        raise VerificationError("snapshot manifest binding mismatch")
    paths: dict[str, str] = {}
    try:
        manifest_lines = manifest.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise VerificationError("snapshot manifest encoding mismatch") from exc
    for line in manifest_lines:
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if match is None:
            raise VerificationError("snapshot manifest syntax mismatch")
        relative = match.group(2)
        path = PurePosixPath(relative)
        if (
            path.is_absolute()
            or any(item in {"", ".", ".."} for item in path.parts)
            or relative in paths
        ):
            raise VerificationError("snapshot manifest path mismatch")
        paths[relative] = match.group(1)
    transaction_expected = paths.get("transactions.jsonl")
    transaction_path = snapshot / "transactions.jsonl"
    if transaction_expected is None or digest(transaction_path) != transaction_expected:
        raise VerificationError("transaction registry binding mismatch")
    transactions = load_lines(transaction_path, "transaction registry")
    transaction_by_hash: dict[str, dict[str, Any]] = {}
    for row in transactions:
        if set(row) != TRANSACTION_FIELDS:
            raise VerificationError("transaction schema mismatch")
        archive_hash = sha(row.get("archive_sha256"), "transaction archive hash")
        if archive_hash in transaction_by_hash:
            raise VerificationError("duplicate transaction archive")
        integer(row.get("archive_size"), "transaction archive size")
        for key in (
            "archive_relative_path",
            "committed_at_utc",
            "drop_id",
            "intake_dir",
            "score_dir",
        ):
            if not isinstance(row.get(key), str) or not row[key]:
                raise VerificationError("transaction string field mismatch")
        sha(row.get("intake_summary_sha256"), "intake summary hash")
        sha(row.get("score_summary_sha256"), "score summary hash")
        archive_parts(row["archive_relative_path"])
        transaction_by_hash[archive_hash] = row
    assert_equal(set(transaction_by_hash), set(accepted), "accepted transaction support")

    accepted_tasks: set[str] = set()
    seeded = 0
    fallback = 0
    mismatches = 0
    source_rows = 0
    competition_source_rows = 0
    for archive_hash, relative in sorted(accepted.items()):
        transaction = transaction_by_hash[archive_hash]
        assert_equal(
            transaction["archive_relative_path"], relative, "accepted archive path"
        )
        intake_unresolved = Path(transaction["intake_dir"])
        if intake_unresolved.is_symlink():
            raise VerificationError("symlinked intake directory")
        intake = intake_unresolved.resolve()
        if intake.parent != state / "intakes" or intake.name != transaction["drop_id"]:
            raise VerificationError("intake directory binding mismatch")
        summary_path = intake / "summary.json"
        if digest(summary_path) != transaction["intake_summary_sha256"]:
            raise VerificationError("intake summary digest mismatch")
        summary = load(summary_path, "intake summary")
        outputs = summary.get("outputs")
        security = summary.get("security")
        blindness = summary.get("blindness")
        if (
            summary.get("status") != "PROSPECTIVE_DROP_INTAKE_COMPLETE"
            or summary.get("protocol") != "prospective_drop_intake_v1"
            or not isinstance(outputs, dict)
            or not isinstance(security, dict)
            or not isinstance(blindness, dict)
            or security.get("env_members_read") is not False
            or security.get("live_event_journal_members_read") is not False
            or security.get("journal_scanned_before_json") is not True
            or blindness.get("labels_used_for_run_selection") is not False
            or blindness.get("labels_used_for_endpoint_selection") is not False
            or blindness.get("label_values_printed") is not False
        ):
            raise VerificationError("unsafe intake metadata")
        provenance_path = intake / "source_provenance.json"
        provenance_hash = sha(
            outputs.get("source_provenance_sha256"), "source provenance hash"
        )
        if digest(provenance_path) != provenance_hash:
            raise VerificationError("source provenance digest mismatch")
        provenance = load_list(provenance_path, "source provenance")
        tasks: set[str] = set()
        _directory, basename = archive_parts(relative)
        for item in provenance:
            if not isinstance(item, dict) or not (
                PROVENANCE_REQUIRED_FIELDS
                <= set(item)
                <= PROVENANCE_REQUIRED_FIELDS | PROVENANCE_OPTIONAL_FIELDS
            ):
                raise VerificationError("source provenance schema mismatch")
            if item.get("archive_sha256") != archive_hash or item.get(
                "archive_name"
            ) != basename:
                raise VerificationError("source provenance archive mismatch")
            tasks.add(canonical_task(item.get("task")))
            competition_source_rows += "competition_id_source" in item
        source_rows += len(provenance)
        if len(tasks) != 1:
            raise VerificationError("accepted archive task multiplicity mismatch")
        task = next(iter(tasks))
        filename_match = SEED_NAME_RX.fullmatch(basename)
        if filename_match is None:
            fallback += 1
        else:
            seeded += 1
            mismatches += canonical_task(filename_match.group("task")) != task
        accepted_tasks.add(task)
    audit = {
        "snapshot_transactions": len(transactions),
        "accepted_single_task_archives": len(accepted),
        "accepted_seeded_filename_archives": seeded,
        "accepted_task_metadata_fallback_archives": fallback,
        "accepted_filename_task_mismatches": mismatches,
        "hash_bound_source_provenance_rows": source_rows,
        "source_provenance_competition_source_rows": competition_source_rows,
    }
    expected = {
        "snapshot_transactions": integer(
            known.get("current_snapshot_transactions"), "known snapshot transactions"
        ),
        "accepted_single_task_archives": integer(
            known.get("current_accepted_single_task_archives"),
            "known accepted single-task archives",
        ),
        "accepted_seeded_filename_archives": integer(
            known.get("current_accepted_seeded_filename_archives"),
            "known accepted seeded filenames",
        ),
        "accepted_task_metadata_fallback_archives": integer(
            known.get("current_accepted_task_metadata_fallback_archives"),
            "known accepted task metadata fallbacks",
        ),
        "accepted_filename_task_mismatches": 0,
        "hash_bound_source_provenance_rows": integer(
            known.get("current_hash_bound_source_provenance_rows"),
            "known source provenance rows",
        ),
        "source_provenance_competition_source_rows": integer(
            known.get("current_source_provenance_competition_source_rows"),
            "known source provenance competition-source rows",
        ),
    }
    assert_equal(audit, expected, "accepted task mapping audit")
    return accepted_tasks, audit


def verify(
    protocol_path: Path,
    observations_path: Path,
    historical_path: Path,
    result_path: Path,
    state_root: Path,
) -> dict[str, Any]:
    protocol = load(protocol_path.resolve(), "protocol")
    observations = load(observations_path.resolve(), "observations")
    historical = load(historical_path.resolve(), "historical ledger")
    result = load(result_path.resolve(), "result")
    if protocol.get("protocol") != "archive_disposition_longitudinal_replication_v1":
        raise VerificationError("protocol identity mismatch")
    if protocol.get("frozen_before_current_mixed_disposition_readout") is not True:
        raise VerificationError("protocol was not frozen")
    inputs = protocol.get("inputs")
    known = protocol.get("known_metadata_before_readout")
    rules = protocol.get("decision_rule")
    if not all(isinstance(value, dict) for value in (inputs, known, rules)):
        raise VerificationError("protocol sections missing")
    assert_equal(
        protocol.get("access_contract"),
        {
            "observation_metadata_only": True,
            "hash_bound_intake_task_metadata_only": True,
            "archive_payloads_opened": False,
            "labels_grades_outcomes_predictions_accuracy_or_utility_read": False,
            "candidate_identities_emitted": False,
            "run_or_card_identity_values_emitted": False,
            "gpu_paid_api_model_fit_base_update": "0/0/0/0",
        },
        "protocol access contract",
    )
    if digest(observations_path.resolve()) != sha(
        inputs.get("current_observations_sha256"), "observation hash"
    ):
        raise VerificationError("observation hash mismatch")
    if observations_path.stat().st_size != integer(
        inputs.get("current_observations_bytes"), "observation bytes"
    ):
        raise VerificationError("observation byte count mismatch")
    if digest(historical_path.resolve()) != sha(
        inputs.get("historical_ledger_sha256"), "historical hash"
    ):
        raise VerificationError("historical ledger hash mismatch")

    hcounts = historical.get("counts")
    if (
        historical.get("protocol") != "prospective_structural_rejection_ledger_v1"
        or historical.get("status")
        != "OUTCOME_BLIND_ARCHIVE_DISPOSITION_AUDIT_COMPLETE"
        or not isinstance(hcounts, dict)
    ):
        raise VerificationError("historical ledger contract mismatch")
    historical_counts = {
        "observed": integer(hcounts.get("observed_archives"), "historical observed"),
        "baseline": integer(hcounts.get("baseline_archives"), "historical baseline"),
        "accepted": integer(
            hcounts.get("accepted_archive_transactions"), "historical accepted"
        ),
        "rejected": integer(hcounts.get("rejected_archives"), "historical rejected"),
        "settled": integer(
            hcounts.get("settled_archive_decisions"), "historical settled"
        ),
        "pending": integer(hcounts.get("pending_archives"), "historical pending"),
    }
    assert_equal(
        historical_counts,
        {
            "observed": integer(
                known.get("historical_observed_archives"), "known historical observed"
            ),
            "baseline": 128,
            "accepted": 78,
            "rejected": 12,
            "settled": integer(
                known.get("historical_settled_postbaseline_archives"),
                "known historical settled",
            ),
            "pending": 0,
        },
        "historical counts",
    )
    historical_accepted: set[str] = set()
    historical_rejected: set[str] = set()
    timelines = historical.get("rejected_competition_timelines")
    if not isinstance(timelines, list):
        raise VerificationError("historical competition timelines missing")
    for row in timelines:
        if not isinstance(row, dict) or not isinstance(row.get("competition"), str):
            raise VerificationError("malformed historical competition timeline")
        task = row["competition"]
        if task in historical_rejected:
            raise VerificationError("duplicate historical competition timeline")
        rejected_count = integer(
            row.get("rejected_archives"), "historical timeline rejected count"
        )
        accepted_count = integer(
            row.get("accepted_archive_transactions"),
            "historical timeline accepted count",
        )
        if rejected_count == 0:
            raise VerificationError("historical timeline has no rejection")
        historical_rejected.add(task)
        if accepted_count > 0:
            historical_accepted.add(task)
    assert_equal(
        len(historical_rejected),
        integer(
            known.get("historical_rejected_competitions"),
            "known historical rejected competitions",
        ),
        "historical rejected competition count",
    )
    assert_equal(
        len(historical_accepted & historical_rejected),
        integer(
            known.get("historical_mixed_disposition_competitions"),
            "known historical mixed competitions",
        ),
        "historical mixed competition count",
    )

    if observations.get("protocol") != "prospective_archive_observer_v1":
        raise VerificationError("observation protocol mismatch")
    entries = observations.get("entries")
    source_root = observations.get("source_root")
    if not isinstance(entries, dict) or not isinstance(source_root, str):
        raise VerificationError("observation schema mismatch")
    prefix = source_root.rstrip("/") + "/"
    allowed_value = protocol.get("recognized_rejection_reasons")
    if not isinstance(allowed_value, list) or not allowed_value:
        raise VerificationError("recognized reason set missing")
    allowed = set(allowed_value)
    current_counts: Counter[str] = Counter()
    reason_counts: Counter[str] = Counter()
    accepted_archive_paths: dict[str, str] = {}
    current_rejected: set[str] = set()
    payload_hashes: set[str] = set()
    latest = sha(inputs.get("current_latest_snapshot_sha256"), "current latest")
    latest_seen = False
    for relative, row in entries.items():
        archive_parts(relative)
        if not isinstance(row, dict):
            raise VerificationError("malformed observation row")
        if row.get("path") != prefix + relative or row.get("present") is not True:
            raise VerificationError("observation path/presence mismatch")
        if integer(row.get("stable_observations"), "stable observation count") == 0:
            raise VerificationError("unstable archive in frozen population")
        baseline = row.get("baseline") is True
        committed_archive = row.get("committed_archive_sha256")
        committed_snapshot = row.get("committed_snapshot_sha256")
        rejected_archive = row.get("rejected_archive_sha256")
        rejected_registry = row.get("rejection_registry_sha256")
        reason = row.get("rejection_reason_code")
        accepted = committed_archive is not None or committed_snapshot is not None
        rejected = rejected_archive is not None or rejected_registry is not None or reason is not None
        if sum((baseline, accepted, rejected)) > 1:
            raise VerificationError("overlapping disposition")
        if baseline:
            current_counts["baseline"] += 1
        elif accepted:
            archive_hash = sha(committed_archive, "accepted payload hash")
            snapshot_hash = sha(committed_snapshot, "accepted snapshot hash")
            if archive_hash in payload_hashes:
                raise VerificationError("duplicate payload hash")
            payload_hashes.add(archive_hash)
            current_counts["accepted"] += 1
            accepted_archive_paths[archive_hash] = relative
            latest_seen |= snapshot_hash == latest
        elif rejected:
            archive_hash = sha(rejected_archive, "rejected payload hash")
            sha(rejected_registry, "rejection registry hash")
            if not isinstance(reason, str) or reason not in allowed:
                raise VerificationError("unknown rejection reason")
            if archive_hash in payload_hashes:
                raise VerificationError("duplicate payload hash")
            payload_hashes.add(archive_hash)
            current_counts["rejected"] += 1
            current_rejected.add(rejected_task(relative))
            reason_counts[reason] += 1
        else:
            current_counts["pending"] += 1
    current = {
        "observed": len(entries),
        "baseline": current_counts["baseline"],
        "accepted": current_counts["accepted"],
        "rejected": current_counts["rejected"],
        "pending": current_counts["pending"],
    }
    assert_equal(
        current,
        {
            "observed": integer(
                inputs.get("current_source_archive_count"), "current source count"
            ),
            "baseline": integer(
                known.get("current_baseline_archives"), "known current baseline"
            ),
            "accepted": integer(
                known.get("current_accepted_archives"), "known current accepted"
            ),
            "rejected": integer(
                known.get("current_rejected_archives"), "known current rejected"
            ),
            "pending": integer(
                known.get("current_pending_archives"), "known current pending"
            ),
        },
        "current partition",
    )
    if current["pending"] != 0 or not latest_seen:
        raise VerificationError("current frozen population is not settled")
    current_accepted, accepted_mapping_audit = reconstruct_accepted_tasks(
        state_root, latest, accepted_archive_paths, known
    )
    assert_equal(
        current["rejected"],
        integer(
            known.get("current_rejected_seeded_filename_archives"),
            "known rejected seeded filenames",
        ),
        "rejected filename mapping audit",
    )
    competition_mapping_audit = {
        **accepted_mapping_audit,
        "rejected_seeded_filename_archives": current["rejected"],
    }
    rejected_tasks = len(current_rejected)
    mixed_tasks = len(current_accepted & current_rejected)
    if rejected_tasks == 0:
        raise VerificationError("zero rejected competitions")
    extension = {
        "observed": current["observed"] - historical_counts["observed"],
        "accepted": current["accepted"] - historical_counts["accepted"],
        "rejected": current["rejected"] - historical_counts["rejected"],
    }
    extension["settled"] = extension["accepted"] + extension["rejected"]
    if extension["observed"] != extension["settled"] or any(
        value < 0 for value in extension.values()
    ):
        raise VerificationError("extension does not close")
    strong = rules.get("strong")
    partial = rules.get("partial")
    kill = rules.get("kill")
    if not all(isinstance(value, dict) for value in (strong, partial, kill)):
        raise VerificationError("decision rules malformed")
    required_exact_fraction = unit_fraction(
        strong.get("required_current_mixed_disposition_fraction"),
        "strong exact mixed-disposition fraction",
    )
    partial_fraction = unit_fraction(
        partial.get("minimum_current_mixed_disposition_fraction"),
        "partial mixed-disposition fraction",
    )
    if (
        rejected_tasks
        >= integer(
            strong.get("minimum_current_rejected_competitions"),
            "strong rejected competition minimum",
        )
        and extension["settled"]
        >= integer(
            strong.get("minimum_extension_settled_archives"),
            "strong extension minimum",
        )
        and mixed_tasks == rejected_tasks
        and required_exact_fraction == 1.0
    ):
        expected_status = strong.get("status")
    elif mixed_tasks / rejected_tasks >= partial_fraction:
        expected_status = partial.get("status")
    else:
        expected_status = kill.get("status")

    assert_equal(result.get("protocol"), protocol.get("protocol"), "result protocol")
    assert_equal(result.get("status"), expected_status, "result status")
    assert_equal(
        result.get("input_bindings"),
        {
            "protocol_sha256": digest(protocol_path.resolve()),
            "current_latest_snapshot_sha256": latest,
            "current_observations_sha256": inputs["current_observations_sha256"],
            "historical_ledger_sha256": inputs["historical_ledger_sha256"],
        },
        "input bindings",
    )
    assert_equal(
        result.get("integrity"),
        {
            "source_count_equals_observation_count": True,
            "disposition_partition_mutually_exclusive_and_exhaustive": True,
            "pending_archives_zero": True,
            "postbaseline_archive_payload_hashes_unique": True,
            "all_rejection_reasons_recognized": True,
            "latest_snapshot_seen_in_accepted": True,
            "snapshot_transaction_registry_hash_bound": True,
            "accepted_archives_single_task_hash_bound": True,
            "accepted_seeded_filename_task_match": True,
            "rejected_seeded_filenames_complete": True,
            "historical_anchor_reproduced": True,
        },
        "integrity receipt",
    )
    assert_equal(
        result.get("historical"),
        {
            "observed_archives": historical_counts["observed"],
            "settled_postbaseline_archives": historical_counts["settled"],
            "accepted_archives": historical_counts["accepted"],
            "rejected_archives": historical_counts["rejected"],
            "rejected_competitions": len(historical_rejected),
            "mixed_disposition_competitions": len(
                historical_accepted & historical_rejected
            ),
            "rejection_rate": proportion(
                historical_counts["rejected"], historical_counts["settled"]
            ),
        },
        "historical aggregate",
    )
    current_settled = current["accepted"] + current["rejected"]
    assert_equal(
        result.get("current"),
        {
            "observed_archives": current["observed"],
            "settled_postbaseline_archives": current_settled,
            "baseline_archives": current["baseline"],
            "accepted_archives": current["accepted"],
            "rejected_archives": current["rejected"],
            "pending_archives": current["pending"],
            "postbaseline_unique_archive_hashes": len(payload_hashes),
            "rejected_competitions": rejected_tasks,
            "mixed_disposition_competitions": mixed_tasks,
            "nonmixed_rejected_competitions": rejected_tasks - mixed_tasks,
            "mixed_disposition_fraction": proportion(mixed_tasks, rejected_tasks),
            "rejection_rate": proportion(current["rejected"], current_settled),
            "rejection_reason_counts": dict(sorted(reason_counts.items())),
            "competition_mapping_audit": competition_mapping_audit,
        },
        "current aggregate",
    )
    assert_equal(
        result.get("extension_beyond_historical_anchor"),
        {
            "observed_archives": extension["observed"],
            "settled_archives": extension["settled"],
            "accepted_archives": extension["accepted"],
            "rejected_archives": extension["rejected"],
            "rejection_rate": proportion(
                extension["rejected"], extension["settled"]
            ),
        },
        "extension aggregate",
    )
    assert_equal(
        result.get("decision"),
        {
            "strong_gate_passed": expected_status == strong.get("status"),
            "partial_gate_passed": expected_status == partial.get("status"),
            "kill_gate_triggered": expected_status == kill.get("status"),
            "identities_emitted": False,
        },
        "decision receipt",
    )
    assert_equal(
        result.get("access_attestation"),
        {
            "observation_metadata_only": True,
            "hash_bound_intake_task_metadata_only": True,
            "archive_payloads_opened": False,
            "labels_grades_outcomes_predictions_accuracy_or_utility_read": False,
            "candidate_identities_emitted": False,
            "run_or_card_identity_values_emitted": False,
            "randomness_used": False,
            "gpu_paid_api_model_fit_base_update": "0/0/0/0",
        },
        "access attestation",
    )
    assert_equal(
        result.get("claim_boundary"),
        {
            "supports_archive_level_fail_closed_validation": expected_status
            == strong.get("status"),
            "supports_task_whitelist_or_blacklist": False,
            "estimates_metadata_repair_causal_effect": False,
            "estimates_predictor_accuracy_scaling_or_search_utility": False,
            "claims_rejection_rate_stationarity": False,
        },
        "claim boundary",
    )
    return {
        "protocol": "independent_archive_disposition_longitudinal_replication_v1",
        "status": "INDEPENDENT_ARCHIVE_DISPOSITION_REPLICATION_PASS",
        "result_sha256": digest(result_path.resolve()),
        "result_status": expected_status,
        "recomputed_counts": {
            "current_observed_archives": current["observed"],
            "current_settled_archives": current_settled,
            "current_rejected_competitions": rejected_tasks,
            "current_mixed_disposition_competitions": mixed_tasks,
            "extension_settled_archives": extension["settled"],
        },
        "all_aggregate_fields_equal": True,
        "identities_emitted": False,
        "outcomes_predictions_labels_read": False,
        "randomness_used": False,
    }


def write_new(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise VerificationError("verification output already exists")
    if not path.parent.is_dir() or path.parent.is_symlink():
        raise VerificationError("verification output parent is unsafe")
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
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--observations", required=True, type=Path)
    parser.add_argument("--historical-ledger", required=True, type=Path)
    parser.add_argument("--result", required=True, type=Path)
    parser.add_argument("--state-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        receipt = verify(
            args.protocol,
            args.observations,
            args.historical_ledger,
            args.result,
            args.state_root,
        )
        write_new(args.output.resolve(), receipt)
        print(json.dumps(receipt["recomputed_counts"], sort_keys=True, separators=(",", ":")))
        return 0
    except (OSError, VerificationError, TypeError, ZeroDivisionError) as exc:
        print(f"ARCHIVE_DISPOSITION_REPLICATION_VERIFY_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
