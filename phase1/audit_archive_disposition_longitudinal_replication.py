#!/usr/bin/env python3
"""Outcome-blind longitudinal replication of archive-level disposition validity."""
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


PROTOCOL_NAME = "archive_disposition_longitudinal_replication_v2"
OBSERVATION_PROTOCOL = "prospective_archive_observer_v1"
HISTORICAL_LEDGER_PROTOCOL = "prospective_structural_rejection_ledger_v1"
HISTORICAL_LEDGER_STATUS = "OUTCOME_BLIND_ARCHIVE_DISPOSITION_AUDIT_COMPLETE"
SHA_RX = re.compile(r"[0-9a-f]{64}")
SEEDED_ARCHIVE_RX = re.compile(r"(?P<competition>.+)-(?P<seeds>[0-9]+)seeds\.tar\.gz")
NON_ASCII_ALNUM = re.compile(r"[^a-z0-9]+")
TRANSACTION_KEYS = {
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
PROVENANCE_REQUIRED_KEYS = {
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
PROVENANCE_OPTIONAL_KEYS = {"competition_id_source"}
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


class ReplicationError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_object(path: Path, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ReplicationError(f"{label} is absent, non-regular, or symlinked")
    try:
        value = json.loads(path.read_bytes())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReplicationError(f"cannot parse {label}") from exc
    if not isinstance(value, dict):
        raise ReplicationError(f"{label} is not a JSON object")
    return value


def nonnegative_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ReplicationError(f"invalid {label}")
    return value


def unit_fraction(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ReplicationError(f"invalid {label}")
    normalized = float(value)
    if not math.isfinite(normalized) or not 0.0 <= normalized <= 1.0:
        raise ReplicationError(f"invalid {label}")
    return normalized


def require_sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or SHA_RX.fullmatch(value) is None:
        raise ReplicationError(f"invalid {label}")
    return value


def clean_archive_relative(value: Any) -> tuple[str, str]:
    if not isinstance(value, str):
        raise ReplicationError("archive identity is not a string")
    path = PurePosixPath(value)
    parts = path.parts
    if path.is_absolute() or len(parts) != 2 or any(
        part in {"", ".", ".."} for part in parts
    ):
        raise ReplicationError("archive identity is not a clean two-part path")
    directory, basename = parts
    if not basename.endswith(".tar.gz"):
        raise ReplicationError("archive identity is not a tar.gz")
    return directory, basename


def normalize_competition(value: Any) -> str:
    if not isinstance(value, str):
        raise ReplicationError("competition identity is not a string")
    normalized = NON_ASCII_ALNUM.sub("-", value.casefold()).strip("-")
    if not normalized:
        raise ReplicationError("empty normalized competition identity")
    return normalized


def rejected_competition_from_relative(value: Any) -> str:
    _directory, basename = clean_archive_relative(value)
    match = SEEDED_ARCHIVE_RX.fullmatch(basename)
    if match is None:
        raise ReplicationError("rejected archive lacks a -Nseeds filename")
    return normalize_competition(match.group("competition"))


def read_list(path: Path, label: str) -> list[Any]:
    if path.is_symlink() or not path.is_file():
        raise ReplicationError(f"{label} is absent, non-regular, or symlinked")
    try:
        value = json.loads(path.read_bytes())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReplicationError(f"cannot parse {label}") from exc
    if not isinstance(value, list):
        raise ReplicationError(f"{label} is not a JSON list")
    return value


def read_jsonl(path: Path, label: str) -> list[dict[str, Any]]:
    if path.is_symlink() or not path.is_file():
        raise ReplicationError(f"{label} is absent, non-regular, or symlinked")
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ReplicationError(f"non-object {label} row {line_number}")
                rows.append(value)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReplicationError(f"cannot parse {label}") from exc
    if not rows:
        raise ReplicationError(f"{label} is empty")
    return rows


def wilson_95(numerator: int, denominator: int) -> list[float]:
    if denominator <= 0 or numerator < 0 or numerator > denominator:
        raise ReplicationError("invalid Wilson interval inputs")
    z = 1.959963984540054
    p = numerator / denominator
    z2 = z * z
    scale = 1.0 + z2 / denominator
    centre = (p + z2 / (2.0 * denominator)) / scale
    half = (
        z
        * math.sqrt((p * (1.0 - p) + z2 / (4.0 * denominator)) / denominator)
        / scale
    )
    return [centre - half, centre + half]


def rate(numerator: int, denominator: int) -> dict[str, Any]:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "value": numerator / denominator,
        "wilson_95": wilson_95(numerator, denominator),
    }


def validate_protocol(protocol: dict[str, Any]) -> None:
    if protocol.get("protocol") != PROTOCOL_NAME:
        raise ReplicationError("protocol identity mismatch")
    if (
        protocol.get("frozen_before_current_structural_mixed_disposition_readout")
        is not True
    ):
        raise ReplicationError("protocol is not result-before frozen")
    access = protocol.get("access_contract")
    if access != {
        "observation_metadata_only": True,
        "hash_bound_intake_task_metadata_only": True,
        "archive_payloads_opened": False,
        "labels_grades_outcomes_predictions_accuracy_or_utility_read": False,
        "candidate_identities_emitted": False,
        "run_or_card_identity_values_emitted": False,
        "gpu_paid_api_model_fit_base_update": "0/0/0/0",
    }:
        raise ReplicationError("access contract mismatch")


def validate_bound_repo_evidence(
    protocol_path: Path, inputs: dict[str, Any]
) -> None:
    repo_root = protocol_path.resolve().parent
    bindings = (
        ("v1_failure_path", "v1_failure_sha256", "v1 failure"),
        ("v1_protocol_path", "v1_protocol_sha256", "v1 protocol"),
        (
            "alias_formal_summary_path",
            "alias_formal_summary_sha256",
            "alias formal summary",
        ),
        (
            "alias_declaration_report_path",
            "alias_declaration_report_sha256",
            "alias declaration report",
        ),
    )
    for path_key, hash_key, label in bindings:
        relative = inputs.get(path_key)
        if not isinstance(relative, str) or not relative:
            raise ReplicationError(f"{label} path missing")
        unresolved = repo_root / relative
        if unresolved.is_symlink():
            raise ReplicationError(f"{label} path is unsafe")
        candidate = unresolved.resolve()
        try:
            candidate.relative_to(repo_root)
        except ValueError as exc:
            raise ReplicationError(f"{label} path escapes repository") from exc
        if not candidate.is_file():
            raise ReplicationError(f"{label} path is absent or unsafe")
        if sha256(candidate) != require_sha(inputs.get(hash_key), f"{label} hash"):
            raise ReplicationError(f"{label} hash mismatch")


def accepted_competitions_from_snapshot(
    protocol: dict[str, Any],
    state_root: Path,
    accepted_archives: dict[str, str],
) -> tuple[set[str], dict[str, int]]:
    inputs = protocol.get("inputs")
    known = protocol.get("known_metadata_before_readout")
    if not isinstance(inputs, dict) or not isinstance(known, dict):
        raise ReplicationError("protocol mapping metadata missing")
    latest = require_sha(inputs.get("current_latest_snapshot_sha256"), "current latest")
    unresolved_root = state_root
    if unresolved_root.is_symlink() or not unresolved_root.is_dir():
        raise ReplicationError("state root is absent, non-directory, or symlinked")
    root = unresolved_root.resolve()
    snapshot = root / "snapshots" / latest
    if snapshot.is_symlink() or not snapshot.is_dir() or snapshot.parent != root / "snapshots":
        raise ReplicationError("bound snapshot is absent or unsafe")
    manifest = snapshot / "SHA256SUMS"
    if sha256(manifest) != latest:
        raise ReplicationError("bound snapshot manifest hash mismatch")
    transaction_sha: str | None = None
    try:
        lines = manifest.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise ReplicationError("snapshot manifest is not UTF-8") from exc
    seen_manifest_paths: set[str] = set()
    for line in lines:
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if match is None:
            raise ReplicationError("snapshot manifest row malformed")
        relative = match.group(2)
        path = PurePosixPath(relative)
        if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
            raise ReplicationError("snapshot manifest path malformed")
        if relative in seen_manifest_paths:
            raise ReplicationError("duplicate snapshot manifest path")
        seen_manifest_paths.add(relative)
        if relative == "transactions.jsonl":
            transaction_sha = match.group(1)
    if transaction_sha is None:
        raise ReplicationError("snapshot transaction registry absent from manifest")
    transaction_path = snapshot / "transactions.jsonl"
    if sha256(transaction_path) != transaction_sha:
        raise ReplicationError("snapshot transaction registry hash mismatch")
    transactions = read_jsonl(transaction_path, "transaction registry")
    by_archive: dict[str, dict[str, Any]] = {}
    for row in transactions:
        if set(row) != TRANSACTION_KEYS:
            raise ReplicationError("transaction registry schema mismatch")
        archive_sha = require_sha(row.get("archive_sha256"), "transaction archive hash")
        if archive_sha in by_archive:
            raise ReplicationError("duplicate transaction archive hash")
        if nonnegative_int(row.get("archive_size"), "transaction archive size") < 0:
            raise ReplicationError("negative transaction archive size")
        for key in (
            "archive_relative_path",
            "committed_at_utc",
            "drop_id",
            "intake_dir",
            "score_dir",
        ):
            if not isinstance(row.get(key), str) or not row[key]:
                raise ReplicationError("transaction string field malformed")
        require_sha(row.get("intake_summary_sha256"), "intake summary hash")
        require_sha(row.get("score_summary_sha256"), "score summary hash")
        clean_archive_relative(row["archive_relative_path"])
        by_archive[archive_sha] = row
    if set(by_archive) != set(accepted_archives):
        raise ReplicationError("snapshot transactions and accepted observations differ")

    competitions: set[str] = set()
    seeded_filenames = 0
    task_metadata_fallbacks = 0
    filename_task_mismatches = 0
    provenance_rows = 0
    provenance_competition_source_rows = 0
    for archive_sha, relative in sorted(accepted_archives.items()):
        row = by_archive[archive_sha]
        if row["archive_relative_path"] != relative:
            raise ReplicationError("accepted observation path differs from transaction")
        intake = Path(row["intake_dir"])
        if intake.is_symlink():
            raise ReplicationError("intake directory is symlinked")
        intake = intake.resolve()
        if intake.parent != root / "intakes" or intake.name != row["drop_id"]:
            raise ReplicationError("transaction intake path binding mismatch")
        summary_path = intake / "summary.json"
        if sha256(summary_path) != row["intake_summary_sha256"]:
            raise ReplicationError("intake summary hash mismatch")
        summary = read_object(summary_path, "intake summary")
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
            raise ReplicationError("intake task metadata is not outcome-blind")
        provenance_path = intake / "source_provenance.json"
        expected_provenance_sha = require_sha(
            outputs.get("source_provenance_sha256"), "source provenance hash"
        )
        if sha256(provenance_path) != expected_provenance_sha:
            raise ReplicationError("source provenance hash mismatch")
        provenance = read_list(provenance_path, "source provenance")
        tasks: set[str] = set()
        _directory, basename = clean_archive_relative(relative)
        for provenance_row in provenance:
            if not isinstance(provenance_row, dict) or not (
                PROVENANCE_REQUIRED_KEYS
                <= set(provenance_row)
                <= PROVENANCE_REQUIRED_KEYS | PROVENANCE_OPTIONAL_KEYS
            ):
                raise ReplicationError("source provenance schema mismatch")
            if (
                provenance_row.get("archive_sha256") != archive_sha
                or provenance_row.get("archive_name") != basename
            ):
                raise ReplicationError("source provenance archive binding mismatch")
            tasks.add(normalize_competition(provenance_row.get("task")))
            provenance_competition_source_rows += (
                "competition_id_source" in provenance_row
            )
        provenance_rows += len(provenance)
        if len(tasks) != 1:
            raise ReplicationError("accepted archive is not single-task")
        task = next(iter(tasks))
        match = SEEDED_ARCHIVE_RX.fullmatch(basename)
        if match is None:
            task_metadata_fallbacks += 1
        else:
            seeded_filenames += 1
            filename_task_mismatches += (
                normalize_competition(match.group("competition")) != task
            )
        competitions.add(task)

    mapping_audit = {
        "snapshot_transactions": len(transactions),
        "accepted_single_task_archives": len(accepted_archives),
        "accepted_seeded_filename_archives": seeded_filenames,
        "accepted_task_metadata_fallback_archives": task_metadata_fallbacks,
        "accepted_filename_task_mismatches": filename_task_mismatches,
        "hash_bound_source_provenance_rows": provenance_rows,
        "source_provenance_competition_source_rows": provenance_competition_source_rows,
    }
    expected_mapping_audit = {
        "snapshot_transactions": nonnegative_int(
            known.get("current_snapshot_transactions"), "known snapshot transactions"
        ),
        "accepted_single_task_archives": nonnegative_int(
            known.get("current_accepted_single_task_archives"),
            "known accepted single-task archives",
        ),
        "accepted_seeded_filename_archives": nonnegative_int(
            known.get("current_accepted_seeded_filename_archives"),
            "known accepted seeded filenames",
        ),
        "accepted_task_metadata_fallback_archives": nonnegative_int(
            known.get("current_accepted_task_metadata_fallback_archives"),
            "known accepted task metadata fallbacks",
        ),
        "accepted_filename_task_mismatches": 0,
        "hash_bound_source_provenance_rows": nonnegative_int(
            known.get("current_hash_bound_source_provenance_rows"),
            "known source provenance rows",
        ),
        "source_provenance_competition_source_rows": nonnegative_int(
            known.get("current_source_provenance_competition_source_rows"),
            "known source provenance competition-source rows",
        ),
    }
    if mapping_audit != expected_mapping_audit:
        raise ReplicationError("accepted competition mapping audit mismatch")
    return competitions, mapping_audit


def historical_anchor(
    protocol: dict[str, Any], historical: dict[str, Any]
) -> tuple[dict[str, int], set[str], set[str]]:
    if (
        historical.get("protocol") != HISTORICAL_LEDGER_PROTOCOL
        or historical.get("status") != HISTORICAL_LEDGER_STATUS
    ):
        raise ReplicationError("historical ledger contract mismatch")
    counts = historical.get("counts")
    if not isinstance(counts, dict):
        raise ReplicationError("historical counts missing")
    expected = protocol.get("known_metadata_before_readout")
    if not isinstance(expected, dict):
        raise ReplicationError("known historical metadata missing")
    normalized = {
        "observed": nonnegative_int(counts.get("observed_archives"), "historical observed"),
        "baseline": nonnegative_int(counts.get("baseline_archives"), "historical baseline"),
        "accepted": nonnegative_int(
            counts.get("accepted_archive_transactions"), "historical accepted"
        ),
        "rejected": nonnegative_int(counts.get("rejected_archives"), "historical rejected"),
        "settled": nonnegative_int(
            counts.get("settled_archive_decisions"), "historical settled"
        ),
        "pending": nonnegative_int(counts.get("pending_archives"), "historical pending"),
        "rejected_competitions": nonnegative_int(
            counts.get("rejected_competitions"), "historical rejected competitions"
        ),
        "mixed_competitions": nonnegative_int(
            counts.get("mixed_disposition_competitions"), "historical mixed competitions"
        ),
    }
    if normalized != {
        "observed": nonnegative_int(
            expected.get("historical_observed_archives"), "expected historical observed"
        ),
        "baseline": 128,
        "accepted": 78,
        "rejected": 12,
        "settled": nonnegative_int(
            expected.get("historical_settled_postbaseline_archives"),
            "expected historical settled",
        ),
        "pending": 0,
        "rejected_competitions": nonnegative_int(
            expected.get("historical_rejected_competitions"),
            "expected historical rejected competitions",
        ),
        "mixed_competitions": nonnegative_int(
            expected.get("historical_mixed_disposition_competitions"),
            "expected historical mixed competitions",
        ),
    }:
        raise ReplicationError("historical committed counts do not reproduce")
    if normalized["observed"] != normalized["baseline"] + normalized["settled"]:
        raise ReplicationError("historical partition does not close")
    fractions = historical.get("fractions")
    if not isinstance(fractions, dict) or fractions.get(
        "mixed_disposition_over_rejected_competitions"
    ) != {
        "numerator": normalized["mixed_competitions"],
        "denominator": normalized["rejected_competitions"],
        "value": 1.0,
    }:
        raise ReplicationError("historical mixed-disposition anchor mismatch")
    accepted_competitions: set[str] = set()
    rejected_competitions: set[str] = set()
    timelines = historical.get("rejected_competition_timelines")
    if not isinstance(timelines, list):
        raise ReplicationError("historical competition timelines missing")
    for row in timelines:
        if not isinstance(row, dict) or not isinstance(row.get("competition"), str):
            raise ReplicationError("historical competition timeline malformed")
        competition = row["competition"]
        if competition in rejected_competitions:
            raise ReplicationError("duplicate historical competition timeline")
        rejected_count = nonnegative_int(
            row.get("rejected_archives"), "historical timeline rejected count"
        )
        accepted_count = nonnegative_int(
            row.get("accepted_archive_transactions"),
            "historical timeline accepted count",
        )
        if rejected_count == 0:
            raise ReplicationError("historical timeline lacks a rejection")
        rejected_competitions.add(competition)
        if accepted_count > 0:
            accepted_competitions.add(competition)
    if (
        len(rejected_competitions) != normalized["rejected_competitions"]
        or len(accepted_competitions & rejected_competitions)
        != normalized["mixed_competitions"]
    ):
        raise ReplicationError("historical competition sets do not reproduce")
    return normalized, accepted_competitions, rejected_competitions


def current_population(
    protocol: dict[str, Any], observations: dict[str, Any], state_root: Path
) -> dict[str, Any]:
    if set(observations) != {
        "baseline_sealed_at_epoch",
        "entries",
        "protocol",
        "source_root",
    } or observations.get("protocol") != OBSERVATION_PROTOCOL:
        raise ReplicationError("observations schema mismatch")
    entries = observations.get("entries")
    source_root = observations.get("source_root")
    if not isinstance(entries, dict) or not entries:
        raise ReplicationError("observation entries missing")
    if not isinstance(source_root, str) or not source_root.startswith("/"):
        raise ReplicationError("observation source root malformed")
    prefix = source_root.rstrip("/") + "/"
    known = protocol.get("known_metadata_before_readout")
    inputs = protocol.get("inputs")
    if not isinstance(known, dict) or not isinstance(inputs, dict):
        raise ReplicationError("protocol metadata missing")
    taxonomy = protocol.get("rejection_taxonomy")
    if not isinstance(taxonomy, dict):
        raise ReplicationError("rejection taxonomy missing")
    target_value = taxonomy.get("structural_target_reasons")
    quarantine_value = taxonomy.get("quarantine_only_reasons")
    if not isinstance(target_value, list) or not isinstance(quarantine_value, list):
        raise ReplicationError("rejection taxonomy classes malformed")
    target_reasons = set(target_value)
    quarantine_reasons = set(quarantine_value)
    if (
        not target_reasons
        or not quarantine_reasons
        or target_reasons & quarantine_reasons
        or len(target_reasons) != len(target_value)
        or len(quarantine_reasons) != len(quarantine_value)
        or not all(
            isinstance(item, str) and item
            for item in target_reasons | quarantine_reasons
        )
        or taxonomy.get(
            "quarantine_archives_contribute_to_structural_competition_estimand"
        )
        is not False
        or taxonomy.get("quarantine_archives_contribute_to_overall_settled_growth_gate")
        is not True
    ):
        raise ReplicationError("rejection taxonomy contract mismatch")
    allowed = target_reasons | quarantine_reasons

    counts = Counter()
    reasons: Counter[str] = Counter()
    accepted_archives: dict[str, str] = {}
    structural_rejected_competitions: set[str] = set()
    accepted_hashes: set[str] = set()
    structural_hashes: set[str] = set()
    alias_hashes: set[str] = set()
    alias_registry_hashes: set[str] = set()
    latest_seen = False
    latest = require_sha(inputs.get("current_latest_snapshot_sha256"), "current latest")
    for relative, row in entries.items():
        clean_archive_relative(relative)
        if not isinstance(row, dict) or set(row) != ENTRY_KEYS:
            raise ReplicationError("observation entry schema mismatch")
        if row.get("path") != prefix + relative or row.get("present") is not True:
            raise ReplicationError("observation path or presence mismatch")
        if nonnegative_int(row.get("stable_observations"), "stable observations") == 0:
            raise ReplicationError("archive lacks stable observations")
        nonnegative_int(row.get("size"), "archive size")
        nonnegative_int(row.get("mtime_ns"), "archive mtime")
        baseline = row.get("baseline")
        if not isinstance(baseline, bool):
            raise ReplicationError("baseline flag malformed")
        committed_archive = row.get("committed_archive_sha256")
        committed_snapshot = row.get("committed_snapshot_sha256")
        rejected_archive = row.get("rejected_archive_sha256")
        rejection_registry = row.get("rejection_registry_sha256")
        reason = row.get("rejection_reason_code")
        accepted = committed_archive is not None or committed_snapshot is not None
        rejected = rejected_archive is not None or rejection_registry is not None or reason is not None
        if sum((baseline, accepted, rejected)) > 1:
            raise ReplicationError("overlapping archive dispositions")
        if baseline:
            counts["baseline"] += 1
            continue
        if accepted:
            archive_sha = require_sha(committed_archive, "accepted archive hash")
            snapshot_sha = require_sha(committed_snapshot, "accepted snapshot hash")
            if archive_sha in accepted_hashes:
                raise ReplicationError("duplicate accepted archive payload hash")
            accepted_hashes.add(archive_sha)
            counts["accepted"] += 1
            accepted_archives[archive_sha] = relative
            latest_seen |= snapshot_sha == latest
            continue
        if rejected:
            archive_sha = require_sha(rejected_archive, "rejected archive hash")
            registry_sha = require_sha(rejection_registry, "rejection registry hash")
            if not isinstance(reason, str) or reason not in allowed:
                raise ReplicationError("unknown rejection reason")
            competition = rejected_competition_from_relative(relative)
            counts["rejected"] += 1
            reasons[reason] += 1
            if reason in target_reasons:
                if archive_sha in structural_hashes:
                    raise ReplicationError("duplicate structural archive payload hash")
                structural_hashes.add(archive_sha)
                counts["structural_rejected"] += 1
                structural_rejected_competitions.add(competition)
            else:
                if archive_sha in alias_hashes:
                    raise ReplicationError("duplicate alias archive payload hash")
                alias_hashes.add(archive_sha)
                alias_registry_hashes.add(registry_sha)
                counts["alias_quarantined"] += 1
            continue
        counts["pending"] += 1

    normalized = {
        "observed": len(entries),
        "baseline": counts["baseline"],
        "accepted": counts["accepted"],
        "rejected": counts["rejected"],
        "pending": counts["pending"],
    }
    expected_counts = {
        "observed": nonnegative_int(
            inputs.get("current_source_archive_count"), "current source archive count"
        ),
        "baseline": nonnegative_int(
            known.get("current_baseline_archives"), "current baseline"
        ),
        "accepted": nonnegative_int(
            known.get("current_accepted_archives"), "current accepted"
        ),
        "rejected": nonnegative_int(
            known.get("current_rejected_archives"), "current rejected"
        ),
        "pending": nonnegative_int(
            known.get("current_pending_archives"), "current pending"
        ),
    }
    if normalized != expected_counts:
        raise ReplicationError("current source/observation partition mismatch")
    if normalized["pending"] != 0:
        raise ReplicationError("current population has pending archives")
    if normalized["observed"] != sum(normalized[key] for key in ("baseline", "accepted", "rejected", "pending")):
        raise ReplicationError("current partition does not close")
    if not latest_seen:
        raise ReplicationError("current latest snapshot is absent from accepted dispositions")
    expected_subcounts = {
        "structural_rejected": nonnegative_int(
            known.get("current_structural_rejected_archives"),
            "known structural rejected archives",
        ),
        "alias_quarantined": nonnegative_int(
            known.get("current_alias_quarantined_archives"),
            "known alias quarantined archives",
        ),
    }
    actual_subcounts = {
        "structural_rejected": counts["structural_rejected"],
        "alias_quarantined": counts["alias_quarantined"],
    }
    if actual_subcounts != expected_subcounts or sum(actual_subcounts.values()) != normalized["rejected"]:
        raise ReplicationError("rejection taxonomy partition mismatch")
    expected_reason_counts = known.get("current_rejection_reason_counts")
    if not isinstance(expected_reason_counts, dict) or any(
        not isinstance(key, str)
        or isinstance(value, bool)
        or not isinstance(value, int)
        or value < 0
        for key, value in expected_reason_counts.items()
    ):
        raise ReplicationError("known rejection reason counts malformed")
    if dict(sorted(reasons.items())) != dict(sorted(expected_reason_counts.items())):
        raise ReplicationError("rejection reason count mismatch")
    structural_overlap = len(structural_hashes & accepted_hashes)
    alias_overlap = len(alias_hashes & accepted_hashes)
    hash_audit = {
        "accepted_unique_payload_hashes": len(accepted_hashes),
        "structural_unique_payload_hashes": len(structural_hashes),
        "structural_payload_hashes_overlapping_accepted": structural_overlap,
        "alias_unique_payload_hashes": len(alias_hashes),
        "alias_payload_hashes_overlapping_accepted": alias_overlap,
        "distinct_alias_registry_hashes": len(alias_registry_hashes),
        "distinct_postbaseline_payload_hashes": len(
            accepted_hashes | structural_hashes | alias_hashes
        ),
    }
    expected_hash_audit = {
        "accepted_unique_payload_hashes": nonnegative_int(
            known.get("current_accepted_unique_payload_hashes"),
            "known accepted unique payload hashes",
        ),
        "structural_unique_payload_hashes": nonnegative_int(
            known.get("current_structural_unique_payload_hashes"),
            "known structural unique payload hashes",
        ),
        "structural_payload_hashes_overlapping_accepted": nonnegative_int(
            known.get("current_structural_payload_hashes_overlapping_accepted"),
            "known structural payload overlap",
        ),
        "alias_unique_payload_hashes": nonnegative_int(
            known.get("current_alias_unique_payload_hashes"),
            "known alias unique payload hashes",
        ),
        "alias_payload_hashes_overlapping_accepted": nonnegative_int(
            known.get("current_alias_payload_hashes_overlapping_accepted"),
            "known alias payload overlap",
        ),
        "distinct_alias_registry_hashes": nonnegative_int(
            known.get("current_distinct_alias_registry_hashes"),
            "known alias registry hash count",
        ),
        "distinct_postbaseline_payload_hashes": (
            nonnegative_int(
                known.get("current_accepted_unique_payload_hashes"),
                "known accepted unique payload hashes",
            )
            + nonnegative_int(
                known.get("current_structural_unique_payload_hashes"),
                "known structural unique payload hashes",
            )
        ),
    }
    if hash_audit != expected_hash_audit:
        raise ReplicationError("payload hash taxonomy audit mismatch")
    if structural_overlap != 0 or alias_overlap != len(alias_hashes):
        raise ReplicationError("payload hash taxonomy semantics mismatch")
    accepted_competitions, mapping_audit = accepted_competitions_from_snapshot(
        protocol, state_root, accepted_archives
    )
    if counts["rejected"] != nonnegative_int(
        known.get("current_rejected_seeded_filename_archives"),
        "known rejected seeded filenames",
    ):
        raise ReplicationError("rejected competition mapping audit mismatch")
    return {
        "counts": normalized,
        "taxonomy_counts": actual_subcounts,
        "reason_counts": dict(sorted(reasons.items())),
        "accepted_competitions": accepted_competitions,
        "structural_rejected_competitions": structural_rejected_competitions,
        "hash_partition_audit": hash_audit,
        "competition_mapping_audit": {
            **mapping_audit,
            "rejected_seeded_filename_archives": counts["rejected"],
        },
    }


def build_result(
    protocol_path: Path,
    observations_path: Path,
    historical_ledger_path: Path,
    state_root: Path,
) -> dict[str, Any]:
    protocol = read_object(protocol_path.resolve(), "protocol")
    validate_protocol(protocol)
    inputs = protocol.get("inputs")
    if not isinstance(inputs, dict):
        raise ReplicationError("protocol inputs missing")
    validate_bound_repo_evidence(protocol_path, inputs)
    if sha256(observations_path.resolve()) != require_sha(
        inputs.get("current_observations_sha256"), "current observations hash"
    ):
        raise ReplicationError("current observations hash mismatch")
    if observations_path.stat().st_size != nonnegative_int(
        inputs.get("current_observations_bytes"), "current observations bytes"
    ):
        raise ReplicationError("current observations byte count mismatch")
    if sha256(historical_ledger_path.resolve()) != require_sha(
        inputs.get("historical_ledger_sha256"), "historical ledger hash"
    ):
        raise ReplicationError("historical ledger hash mismatch")
    observations = read_object(observations_path.resolve(), "observations")
    historical = read_object(historical_ledger_path.resolve(), "historical ledger")
    historical_counts, historical_accepted, historical_rejected = historical_anchor(
        protocol, historical
    )
    current = current_population(protocol, observations, state_root)
    current_counts = current["counts"]
    accepted_competitions = current["accepted_competitions"]
    rejected_competitions = current["structural_rejected_competitions"]
    mixed = accepted_competitions & rejected_competitions
    rejected_competition_count = len(rejected_competitions)
    mixed_count = len(mixed)
    if rejected_competition_count == 0:
        raise ReplicationError("current population has no rejected competitions")
    taxonomy_counts = current["taxonomy_counts"]
    extension = {
        "observed": current_counts["observed"] - historical_counts["observed"],
        "accepted": current_counts["accepted"] - historical_counts["accepted"],
        "total_rejected": current_counts["rejected"] - historical_counts["rejected"],
        "structural_rejected": (
            taxonomy_counts["structural_rejected"] - historical_counts["rejected"]
        ),
        "alias_quarantined": taxonomy_counts["alias_quarantined"],
        "overall_settled": (
            current_counts["accepted"]
            + current_counts["rejected"]
            - historical_counts["settled"]
        ),
        "structural_target_settled": (
            current_counts["accepted"]
            + taxonomy_counts["structural_rejected"]
            - historical_counts["settled"]
        ),
    }
    if any(value < 0 for value in extension.values()):
        raise ReplicationError("current population is not an extension of historical counts")
    if (
        extension["observed"] != extension["overall_settled"]
        or extension["overall_settled"]
        != extension["accepted"] + extension["total_rejected"]
        or extension["total_rejected"]
        != extension["structural_rejected"] + extension["alias_quarantined"]
        or extension["structural_target_settled"]
        != extension["accepted"] + extension["structural_rejected"]
    ):
        raise ReplicationError("extension archive accounting mismatch")
    decision = protocol.get("decision_rule")
    if not isinstance(decision, dict):
        raise ReplicationError("decision rule missing")
    strong = decision.get("strong")
    partial = decision.get("partial")
    kill = decision.get("kill")
    if not all(isinstance(item, dict) for item in (strong, partial, kill)):
        raise ReplicationError("decision rule malformed")
    required_exact_fraction = unit_fraction(
        strong.get("required_current_structural_mixed_disposition_fraction"),
        "strong exact mixed-disposition fraction",
    )
    partial_fraction = unit_fraction(
        partial.get("minimum_current_structural_mixed_disposition_fraction"),
        "partial mixed-disposition fraction",
    )
    exact_mixed = mixed_count == rejected_competition_count
    if (
        rejected_competition_count
        >= nonnegative_int(
            strong.get("minimum_current_structural_rejected_competitions"),
            "strong competition minimum",
        )
        and extension["overall_settled"]
        >= nonnegative_int(
            strong.get("minimum_overall_extension_settled_archives"),
            "strong extension minimum",
        )
        and exact_mixed
        and required_exact_fraction == 1.0
    ):
        status = strong.get("status")
    elif mixed_count / rejected_competition_count >= partial_fraction:
        status = partial.get("status")
    else:
        status = kill.get("status")
    if not isinstance(status, str) or not status:
        raise ReplicationError("decision status malformed")

    current_settled = current_counts["accepted"] + current_counts["rejected"]
    current_target_settled = (
        current_counts["accepted"] + taxonomy_counts["structural_rejected"]
    )
    result = {
        "protocol": PROTOCOL_NAME,
        "status": status,
        "input_bindings": {
            "protocol_sha256": sha256(protocol_path.resolve()),
            "current_latest_snapshot_sha256": inputs["current_latest_snapshot_sha256"],
            "current_observations_sha256": inputs["current_observations_sha256"],
            "historical_ledger_sha256": inputs["historical_ledger_sha256"],
            "v1_failure_sha256": inputs["v1_failure_sha256"],
            "v1_protocol_sha256": inputs["v1_protocol_sha256"],
            "alias_formal_summary_sha256": inputs["alias_formal_summary_sha256"],
            "alias_declaration_report_sha256": inputs[
                "alias_declaration_report_sha256"
            ],
        },
        "integrity": {
            "source_count_equals_observation_count": True,
            "taxonomy_partition_mutually_exclusive_and_exhaustive": True,
            "pending_archives_zero": True,
            "accepted_payload_hashes_unique": True,
            "structural_payload_hashes_unique_and_disjoint_from_accepted": True,
            "alias_payload_hashes_unique_and_all_overlap_accepted": True,
            "alias_registry_hash_count_bound": True,
            "all_rejection_reasons_classified": True,
            "latest_snapshot_seen_in_accepted": True,
            "snapshot_transaction_registry_hash_bound": True,
            "accepted_archives_single_task_hash_bound": True,
            "accepted_seeded_filename_task_match": True,
            "rejected_seeded_filenames_complete": True,
            "historical_anchor_reproduced": True,
        },
        "historical": {
            "observed_archives": historical_counts["observed"],
            "settled_postbaseline_archives": historical_counts["settled"],
            "accepted_archives": historical_counts["accepted"],
            "rejected_archives": historical_counts["rejected"],
            "rejected_competitions": len(historical_rejected),
            "mixed_disposition_competitions": len(
                historical_accepted & historical_rejected
            ),
            "rejection_rate": rate(
                historical_counts["rejected"], historical_counts["settled"]
            ),
        },
        "current": {
            "observed_archives": current_counts["observed"],
            "overall_settled_postbaseline_archives": current_settled,
            "structural_target_settled_postbaseline_archives": current_target_settled,
            "baseline_archives": current_counts["baseline"],
            "accepted_archives": current_counts["accepted"],
            "total_rejected_archives": current_counts["rejected"],
            "structural_rejected_archives": taxonomy_counts["structural_rejected"],
            "alias_quarantined_archives": taxonomy_counts["alias_quarantined"],
            "pending_archives": current_counts["pending"],
            "payload_hash_partition_audit": current["hash_partition_audit"],
            "structural_rejected_competitions": rejected_competition_count,
            "structural_mixed_disposition_competitions": mixed_count,
            "structural_nonmixed_rejected_competitions": (
                rejected_competition_count - mixed_count
            ),
            "structural_mixed_disposition_fraction": rate(
                mixed_count, rejected_competition_count
            ),
            "overall_rejection_rate": rate(current_counts["rejected"], current_settled),
            "structural_rejection_rate": rate(
                taxonomy_counts["structural_rejected"], current_target_settled
            ),
            "alias_quarantine_rate": rate(
                taxonomy_counts["alias_quarantined"], current_settled
            ),
            "rejection_reason_counts": current["reason_counts"],
            "competition_mapping_audit": current["competition_mapping_audit"],
        },
        "extension_beyond_historical_anchor": {
            "observed_archives": extension["observed"],
            "accepted_archives": extension["accepted"],
            "total_rejected_archives": extension["total_rejected"],
            "structural_rejected_archives": extension["structural_rejected"],
            "alias_quarantined_archives": extension["alias_quarantined"],
            "overall_settled_archives": extension["overall_settled"],
            "structural_target_settled_archives": extension[
                "structural_target_settled"
            ],
            "overall_rejection_rate": rate(
                extension["total_rejected"], extension["overall_settled"]
            ),
            "structural_rejection_rate": rate(
                extension["structural_rejected"],
                extension["structural_target_settled"],
            ),
            "alias_quarantine_rate": rate(
                extension["alias_quarantined"], extension["overall_settled"]
            ),
        },
        "decision": {
            "strong_gate_passed": status == strong.get("status"),
            "partial_gate_passed": status == partial.get("status"),
            "kill_gate_triggered": status == kill.get("status"),
            "identities_emitted": False,
        },
        "access_attestation": {
            "observation_metadata_only": True,
            "hash_bound_intake_task_metadata_only": True,
            "archive_payloads_opened": False,
            "labels_grades_outcomes_predictions_accuracy_or_utility_read": False,
            "candidate_identities_emitted": False,
            "run_or_card_identity_values_emitted": False,
            "randomness_used": False,
            "gpu_paid_api_model_fit_base_update": "0/0/0/0",
        },
        "claim_boundary": {
            "supports_taxonomy_aware_archive_level_fail_closed_validation": (
                status == strong.get("status")
            ),
            "supports_task_whitelist_or_blacklist": False,
            "estimates_metadata_repair_causal_effect": False,
            "estimates_predictor_accuracy_scaling_or_search_utility": False,
            "claims_rejection_rate_stationarity": False,
        },
    }
    return result


def write_new(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise ReplicationError("output already exists")
    if not path.parent.is_dir() or path.parent.is_symlink():
        raise ReplicationError("output parent is absent or unsafe")
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
    parser.add_argument("--state-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = build_result(
            args.protocol, args.observations, args.historical_ledger, args.state_root
        )
        write_new(args.output.resolve(), result)
        print(
            json.dumps(
                {
                    "status": result["status"],
                    "current_structural_rejected_competitions": result["current"][
                        "structural_rejected_competitions"
                    ],
                    "current_structural_mixed_disposition_competitions": result[
                        "current"
                    ][
                        "structural_mixed_disposition_competitions"
                    ],
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 0
    except (OSError, ReplicationError, TypeError, ZeroDivisionError) as exc:
        print(f"ARCHIVE_DISPOSITION_REPLICATION_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
