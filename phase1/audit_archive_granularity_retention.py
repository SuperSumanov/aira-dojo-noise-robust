#!/usr/bin/env python3
"""Outcome-blind accounting of support retained by archive-granular validation."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath
from typing import Any


PROTOCOL_NAME = "archive_granularity_retention_audit_v1"
OBSERVATION_PROTOCOL = "prospective_archive_observer_v1"
PRIOR_PROTOCOL = "archive_disposition_longitudinal_replication_v2"
PRIOR_STATUS = "LONGITUDINAL_ARCHIVE_LEVEL_GATE_REPLICATED"
PRIOR_VERIFICATION_STATUS = "INDEPENDENT_ARCHIVE_DISPOSITION_REPLICATION_PASS"
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


class RetentionAuditError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_object(path: Path, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise RetentionAuditError(f"{label} path is absent or unsafe")
    try:
        value = json.loads(path.read_bytes())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RetentionAuditError(f"cannot parse {label}") from exc
    if not isinstance(value, dict):
        raise RetentionAuditError(f"{label} is not an object")
    return value


def read_list(path: Path, label: str) -> list[Any]:
    if path.is_symlink() or not path.is_file():
        raise RetentionAuditError(f"{label} path is absent or unsafe")
    try:
        value = json.loads(path.read_bytes())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RetentionAuditError(f"cannot parse {label}") from exc
    if not isinstance(value, list):
        raise RetentionAuditError(f"{label} is not a list")
    return value


def read_jsonl(path: Path, label: str) -> list[dict[str, Any]]:
    if path.is_symlink() or not path.is_file():
        raise RetentionAuditError(f"{label} path is absent or unsafe")
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise RetentionAuditError(
                        f"non-object {label} row {line_number}"
                    )
                rows.append(value)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RetentionAuditError(f"cannot parse {label}") from exc
    if not rows:
        raise RetentionAuditError(f"{label} is empty")
    return rows


def nonnegative_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise RetentionAuditError(f"invalid {label}")
    return value


def fraction(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RetentionAuditError(f"invalid {label}")
    normalized = float(value)
    if not math.isfinite(normalized) or not 0.0 <= normalized <= 1.0:
        raise RetentionAuditError(f"invalid {label}")
    return normalized


def require_sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or SHA_RX.fullmatch(value) is None:
        raise RetentionAuditError(f"invalid {label}")
    return value


def archive_parts(value: Any) -> tuple[str, str]:
    if not isinstance(value, str):
        raise RetentionAuditError("archive path is not a string")
    path = PurePosixPath(value)
    if path.is_absolute() or len(path.parts) != 2 or any(
        part in {"", ".", ".."} for part in path.parts
    ):
        raise RetentionAuditError("archive path is malformed")
    directory, basename = path.parts
    if not basename.endswith(".tar.gz"):
        raise RetentionAuditError("archive suffix is malformed")
    return directory, basename


def normalize_task(value: Any) -> str:
    if not isinstance(value, str):
        raise RetentionAuditError("task metadata is not a string")
    normalized = NON_ASCII_ALNUM.sub("-", value.casefold()).strip("-")
    if not normalized:
        raise RetentionAuditError("task metadata normalizes to empty")
    return normalized


def task_from_seeded_archive(relative: Any) -> str:
    _directory, basename = archive_parts(relative)
    match = SEEDED_ARCHIVE_RX.fullmatch(basename)
    if match is None:
        raise RetentionAuditError("rejected archive lacks a seeded filename")
    return normalize_task(match.group("competition"))


def bound_repo_evidence(
    protocol_path: Path,
    inputs: dict[str, Any],
    path_key: str,
    hash_key: str,
    label: str,
) -> Path:
    relative = inputs.get(path_key)
    if not isinstance(relative, str) or not relative:
        raise RetentionAuditError(f"{label} path missing")
    root = protocol_path.resolve().parent
    unresolved = root / relative
    if unresolved.is_symlink():
        raise RetentionAuditError(f"{label} path is symlinked")
    path = unresolved.resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise RetentionAuditError(f"{label} path escapes protocol root") from exc
    if not path.is_file() or sha256(path) != require_sha(inputs.get(hash_key), label):
        raise RetentionAuditError(f"{label} binding mismatch")
    return path


def validate_protocol(protocol: dict[str, Any]) -> None:
    if (
        protocol.get("protocol") != PROTOCOL_NAME
        or protocol.get("frozen_before_retention_count_readout") is not True
    ):
        raise RetentionAuditError("protocol identity or freeze mismatch")
    access = protocol.get("access_contract")
    if access != {
        "observation_and_hash_bound_intake_metadata_only": True,
        "archive_payloads_opened": False,
        "labels_grades_outcomes_predictions_accuracy_or_utility_read": False,
        "candidate_identities_or_profiles_read": False,
        "archive_task_run_or_candidate_identity_values_emitted": False,
        "gpu_paid_api_model_fit_base_update": "0/0/0/0",
    }:
        raise RetentionAuditError("protocol access contract mismatch")
    disclosure = protocol.get("disclosure_at_freeze")
    if not isinstance(disclosure, dict) or any(
        disclosure.get(key) is not False
        for key in (
            "affected_competition_identities_read_or_emitted",
            "retained_accepted_archive_count_read",
            "retained_physical_run_count_read",
            "retained_eligible_run_count_read",
            "retained_eligible_endpoint_count_read",
            "affected_task_dominance_read",
        )
    ):
        raise RetentionAuditError("protocol disclosure mismatch")


def validate_prior_result(
    protocol: dict[str, Any], protocol_path: Path
) -> tuple[dict[str, Any], int, int]:
    inputs = protocol.get("inputs")
    disclosure = protocol.get("disclosure_at_freeze")
    if not isinstance(inputs, dict) or not isinstance(disclosure, dict):
        raise RetentionAuditError("protocol inputs missing")
    result_path = bound_repo_evidence(
        protocol_path,
        inputs,
        "archive_disposition_v2_result_path",
        "archive_disposition_v2_result_sha256",
        "prior result hash",
    )
    verification_path = bound_repo_evidence(
        protocol_path,
        inputs,
        "archive_disposition_v2_verification_path",
        "archive_disposition_v2_verification_sha256",
        "prior verification hash",
    )
    result = read_object(result_path, "prior result")
    verification = read_object(verification_path, "prior verification")
    current = result.get("current")
    access = result.get("access_attestation")
    if (
        result.get("protocol") != PRIOR_PROTOCOL
        or result.get("status") != PRIOR_STATUS
        or not isinstance(current, dict)
        or not isinstance(access, dict)
        or access.get(
            "labels_grades_outcomes_predictions_accuracy_or_utility_read"
        )
        is not False
        or access.get("candidate_identities_emitted") is not False
        or verification.get("status") != PRIOR_VERIFICATION_STATUS
        or verification.get("all_aggregate_fields_equal") is not True
        or verification.get("result_sha256") != sha256(result_path)
    ):
        raise RetentionAuditError("prior result contract mismatch")
    rejected = nonnegative_int(
        current.get("structural_rejected_competitions"),
        "prior structural rejected competitions",
    )
    mixed = nonnegative_int(
        current.get("structural_mixed_disposition_competitions"),
        "prior structural mixed competitions",
    )
    if (
        rejected
        != nonnegative_int(
            disclosure.get("structural_rejected_competition_count_known"),
            "disclosed structural rejected competitions",
        )
        or mixed
        != nonnegative_int(
            disclosure.get("structural_mixed_disposition_competition_count_known"),
            "disclosed structural mixed competitions",
        )
    ):
        raise RetentionAuditError("prior aggregate disclosure mismatch")
    return inputs, rejected, mixed


def classify_observations(
    protocol: dict[str, Any], observations: dict[str, Any]
) -> tuple[dict[str, str], set[str], dict[str, int]]:
    if (
        set(observations)
        != {"baseline_sealed_at_epoch", "entries", "protocol", "source_root"}
        or observations.get("protocol") != OBSERVATION_PROTOCOL
    ):
        raise RetentionAuditError("observations schema mismatch")
    entries = observations.get("entries")
    source_root = observations.get("source_root")
    if not isinstance(entries, dict) or not isinstance(source_root, str):
        raise RetentionAuditError("observations entries missing")
    prefix = source_root.rstrip("/") + "/"
    taxonomy = protocol.get("rejection_taxonomy")
    known = protocol.get("known_structural_metadata_before_readout")
    if not isinstance(taxonomy, dict) or not isinstance(known, dict):
        raise RetentionAuditError("protocol taxonomy or known metadata missing")
    target_value = taxonomy.get("structural_target_reasons")
    alias_value = taxonomy.get("quarantine_only_reasons")
    if not isinstance(target_value, list) or not isinstance(alias_value, list):
        raise RetentionAuditError("rejection taxonomy malformed")
    target_reasons = set(target_value)
    alias_reasons = set(alias_value)
    if (
        not target_reasons
        or not alias_reasons
        or target_reasons & alias_reasons
        or taxonomy.get("aliases_enter_retention_estimand") is not False
    ):
        raise RetentionAuditError("rejection taxonomy contract mismatch")

    counts = Counter()
    accepted: dict[str, str] = {}
    structural_tasks: set[str] = set()
    latest = require_sha(
        protocol["inputs"].get("current_latest_snapshot_sha256"), "latest snapshot"
    )
    latest_seen = False
    for relative, row in entries.items():
        archive_parts(relative)
        if not isinstance(row, dict) or set(row) != ENTRY_KEYS:
            raise RetentionAuditError("observation entry schema mismatch")
        if row.get("path") != prefix + relative or row.get("present") is not True:
            raise RetentionAuditError("observation path or presence mismatch")
        baseline = row.get("baseline")
        committed_fields = (
            row.get("committed_archive_sha256"),
            row.get("committed_snapshot_sha256"),
        )
        rejected_fields = (
            row.get("rejected_archive_sha256"),
            row.get("rejection_reason_code"),
            row.get("rejection_registry_sha256"),
        )
        committed = any(value is not None for value in committed_fields)
        rejected = any(value is not None for value in rejected_fields)
        if not isinstance(baseline, bool) or sum((baseline, committed, rejected)) > 1:
            raise RetentionAuditError("observation disposition overlap")
        if nonnegative_int(row.get("stable_observations"), "stable observations") == 0:
            raise RetentionAuditError("unstable archive in frozen observations")
        nonnegative_int(row.get("size"), "archive size")
        if baseline:
            if committed or rejected:
                raise RetentionAuditError("baseline disposition fields overlap")
            counts["baseline"] += 1
        elif committed:
            if any(value is None for value in committed_fields) or rejected:
                raise RetentionAuditError("accepted disposition is incomplete")
            archive_sha = require_sha(
                row.get("committed_archive_sha256"), "accepted archive hash"
            )
            if archive_sha in accepted:
                raise RetentionAuditError("duplicate accepted archive hash")
            accepted[archive_sha] = relative
            latest_seen |= (
                require_sha(
                    row.get("committed_snapshot_sha256"), "accepted snapshot hash"
                )
                == latest
            )
            counts["accepted"] += 1
        elif rejected:
            if any(value is None for value in rejected_fields) or committed:
                raise RetentionAuditError("rejected disposition is incomplete")
            require_sha(row.get("rejected_archive_sha256"), "rejected archive hash")
            require_sha(row.get("rejection_registry_sha256"), "rejection registry hash")
            reason = row.get("rejection_reason_code")
            if reason in target_reasons:
                structural_tasks.add(task_from_seeded_archive(relative))
                counts["structural_rejected"] += 1
            elif reason in alias_reasons:
                task_from_seeded_archive(relative)
                counts["alias_quarantined"] += 1
            else:
                raise RetentionAuditError("unclassified rejection reason")
            counts["rejected"] += 1
        else:
            counts["pending"] += 1
    expected = {
        "observed": nonnegative_int(known.get("observed_archives"), "known observed"),
        "baseline": nonnegative_int(known.get("baseline_archives"), "known baseline"),
        "accepted": nonnegative_int(known.get("accepted_archives"), "known accepted"),
        "structural_rejected": nonnegative_int(
            known.get("structural_rejected_archives"), "known structural rejected"
        ),
        "alias_quarantined": nonnegative_int(
            known.get("alias_quarantined_archives"), "known aliases"
        ),
        "pending": nonnegative_int(known.get("pending_archives"), "known pending"),
    }
    actual = {
        "observed": len(entries),
        "baseline": counts["baseline"],
        "accepted": counts["accepted"],
        "structural_rejected": counts["structural_rejected"],
        "alias_quarantined": counts["alias_quarantined"],
        "pending": counts["pending"],
    }
    if actual != expected or counts["rejected"] != actual["structural_rejected"] + actual["alias_quarantined"]:
        raise RetentionAuditError("observation partition mismatch")
    if actual["pending"] != 0 or not latest_seen:
        raise RetentionAuditError("frozen population is not settled")
    return accepted, structural_tasks, actual


def snapshot_task_metrics(
    protocol: dict[str, Any], state_root: Path, accepted: dict[str, str]
) -> tuple[dict[str, dict[str, int]], dict[str, int]]:
    known = protocol["known_structural_metadata_before_readout"]
    latest = require_sha(
        protocol["inputs"].get("current_latest_snapshot_sha256"), "latest snapshot"
    )
    if state_root.is_symlink() or not state_root.is_dir():
        raise RetentionAuditError("state root is absent or unsafe")
    root = state_root.resolve()
    snapshot = root / "snapshots" / latest
    if snapshot.is_symlink() or not snapshot.is_dir():
        raise RetentionAuditError("bound snapshot is absent or unsafe")
    manifest = snapshot / "SHA256SUMS"
    if manifest.is_symlink() or not manifest.is_file():
        raise RetentionAuditError("snapshot manifest is absent or unsafe")
    if sha256(manifest) != latest:
        raise RetentionAuditError("snapshot manifest hash mismatch")
    transaction_sha: str | None = None
    for line in manifest.read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if match is None:
            raise RetentionAuditError("snapshot manifest row malformed")
        if match.group(2) == "transactions.jsonl":
            transaction_sha = match.group(1)
    if transaction_sha is None:
        raise RetentionAuditError("snapshot transaction registry absent")
    transaction_path = snapshot / "transactions.jsonl"
    if transaction_path.is_symlink() or not transaction_path.is_file():
        raise RetentionAuditError("transaction registry is absent or unsafe")
    if sha256(transaction_path) != transaction_sha:
        raise RetentionAuditError("transaction registry hash mismatch")
    transactions = read_jsonl(transaction_path, "transaction registry")
    by_archive: dict[str, dict[str, Any]] = {}
    for row in transactions:
        if set(row) != TRANSACTION_KEYS:
            raise RetentionAuditError("transaction schema mismatch")
        archive_sha = require_sha(row.get("archive_sha256"), "transaction archive hash")
        if archive_sha in by_archive:
            raise RetentionAuditError("duplicate transaction archive hash")
        archive_parts(row.get("archive_relative_path"))
        require_sha(row.get("intake_summary_sha256"), "intake summary hash")
        by_archive[archive_sha] = row
    if set(by_archive) != set(accepted):
        raise RetentionAuditError("transactions and accepted observations differ")

    metrics: dict[str, dict[str, int]] = defaultdict(
        lambda: {
            "accepted_archives": 0,
            "physical_runs": 0,
            "eligible_runs": 0,
            "eligible_endpoints": 0,
        }
    )
    seen_run_ids: set[str] = set()
    provenance_rows = 0
    for archive_sha, relative in sorted(accepted.items()):
        transaction = by_archive[archive_sha]
        if transaction.get("archive_relative_path") != relative:
            raise RetentionAuditError("transaction archive path mismatch")
        drop_id = transaction.get("drop_id")
        intake_value = transaction.get("intake_dir")
        if (
            not isinstance(drop_id, str)
            or not drop_id
            or not isinstance(intake_value, str)
            or not intake_value
        ):
            raise RetentionAuditError("transaction intake binding mismatch")
        intake = Path(intake_value)
        if (
            intake.is_symlink()
            or not intake.is_dir()
            or intake.resolve().parent != root / "intakes"
            or intake.resolve().name != drop_id
        ):
            raise RetentionAuditError("transaction intake binding mismatch")
        intake = intake.resolve()
        summary_path = intake / "summary.json"
        if summary_path.is_symlink() or not summary_path.is_file():
            raise RetentionAuditError("intake summary is absent or unsafe")
        if sha256(summary_path) != transaction["intake_summary_sha256"]:
            raise RetentionAuditError("intake summary hash mismatch")
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
            raise RetentionAuditError("intake summary blindness mismatch")
        provenance_path = intake / "source_provenance.json"
        if provenance_path.is_symlink() or not provenance_path.is_file():
            raise RetentionAuditError("source provenance is absent or unsafe")
        if sha256(provenance_path) != require_sha(
            outputs.get("source_provenance_sha256"), "source provenance hash"
        ):
            raise RetentionAuditError("source provenance hash mismatch")
        provenance = read_list(provenance_path, "source provenance")
        tasks: set[str] = set()
        _directory, basename = archive_parts(relative)
        for row in provenance:
            if not isinstance(row, dict) or not (
                PROVENANCE_REQUIRED_KEYS
                <= set(row)
                <= PROVENANCE_REQUIRED_KEYS | PROVENANCE_OPTIONAL_KEYS
            ):
                raise RetentionAuditError("source provenance schema mismatch")
            if (
                row.get("archive_sha256") != archive_sha
                or row.get("archive_name") != basename
            ):
                raise RetentionAuditError("source provenance archive binding mismatch")
            task = normalize_task(row.get("task"))
            tasks.add(task)
            run_id = row.get("run_id")
            if not isinstance(run_id, str) or not run_id or run_id in seen_run_ids:
                raise RetentionAuditError("source provenance run identity duplicated")
            seen_run_ids.add(run_id)
            eligible = row.get("eligible")
            if not isinstance(eligible, bool):
                raise RetentionAuditError("eligible flag malformed")
            endpoints = nonnegative_int(row.get("endpoints"), "provenance endpoints")
            metrics[task]["physical_runs"] += 1
            if eligible:
                metrics[task]["eligible_runs"] += 1
                metrics[task]["eligible_endpoints"] += endpoints
            provenance_rows += 1
        if len(tasks) != 1:
            raise RetentionAuditError("accepted archive is not single-task")
        metrics[next(iter(tasks))]["accepted_archives"] += 1

    totals = {
        "accepted_archives": sum(row["accepted_archives"] for row in metrics.values()),
        "accepted_tasks": len(metrics),
        "physical_runs": sum(row["physical_runs"] for row in metrics.values()),
        "eligible_runs": sum(row["eligible_runs"] for row in metrics.values()),
        "eligible_endpoints": sum(
            row["eligible_endpoints"] for row in metrics.values()
        ),
        "hash_bound_source_provenance_rows": provenance_rows,
        "unique_run_ids": len(seen_run_ids),
    }
    expected = {
        "accepted_archives": nonnegative_int(
            known.get("accepted_archives"), "known accepted archives"
        ),
        "accepted_tasks": nonnegative_int(known.get("accepted_tasks"), "known tasks"),
        "physical_runs": nonnegative_int(
            known.get("accepted_physical_runs"), "known physical runs"
        ),
        "eligible_runs": nonnegative_int(
            known.get("accepted_eligible_runs"), "known eligible runs"
        ),
        "eligible_endpoints": nonnegative_int(
            known.get("accepted_eligible_endpoints"), "known eligible endpoints"
        ),
        "hash_bound_source_provenance_rows": nonnegative_int(
            known.get("hash_bound_source_provenance_rows"), "known provenance rows"
        ),
        "unique_run_ids": nonnegative_int(
            known.get("accepted_physical_runs"), "known unique runs"
        ),
    }
    if totals != expected:
        raise RetentionAuditError("accepted structural totals mismatch")
    if totals["eligible_runs"] == 0 or totals["eligible_endpoints"] == 0:
        raise RetentionAuditError("accepted eligible support is empty")
    return dict(metrics), totals


def metric_summary(values: list[int]) -> dict[str, int | float]:
    if not values:
        raise RetentionAuditError("empty anonymous metric distribution")
    return {
        "minimum": min(values),
        "median": statistics.median(values),
        "maximum": max(values),
    }


def build_result(
    protocol_path: Path, observations_path: Path, state_root: Path
) -> dict[str, Any]:
    if protocol_path.is_symlink() or not protocol_path.is_file():
        raise RetentionAuditError("protocol path is absent or unsafe")
    if observations_path.is_symlink() or not observations_path.is_file():
        raise RetentionAuditError("observations path is absent or unsafe")
    protocol_path = protocol_path.resolve()
    observations_path = observations_path.resolve()
    protocol = read_object(protocol_path, "protocol")
    validate_protocol(protocol)
    inputs, prior_rejected, prior_mixed = validate_prior_result(protocol, protocol_path)
    if sha256(observations_path) != require_sha(
        inputs.get("current_observations_sha256"), "observations hash"
    ):
        raise RetentionAuditError("observations hash mismatch")
    if observations_path.stat().st_size != nonnegative_int(
        inputs.get("current_observations_bytes"), "observations bytes"
    ):
        raise RetentionAuditError("observations byte count mismatch")
    observations = read_object(observations_path, "observations")
    accepted, structural_tasks, partition = classify_observations(
        protocol, observations
    )
    if len(structural_tasks) != prior_rejected:
        raise RetentionAuditError("structural rejected competition count drift")
    known = protocol["known_structural_metadata_before_readout"]
    if prior_rejected != nonnegative_int(
        known.get("structural_rejected_competitions"),
        "known structural rejected competitions",
    ) or prior_mixed != nonnegative_int(
        known.get("structural_mixed_disposition_competitions"),
        "known structural mixed competitions",
    ):
        raise RetentionAuditError("known competition aggregate drift")
    metrics, totals = snapshot_task_metrics(protocol, state_root, accepted)
    accepted_tasks = set(metrics)
    affected = accepted_tasks & structural_tasks
    if len(affected) != prior_mixed:
        raise RetentionAuditError("structural mixed competition count drift")

    retained = {
        unit: sum(metrics[task][unit] for task in affected)
        for unit in (
            "accepted_archives",
            "physical_runs",
            "eligible_runs",
            "eligible_endpoints",
        )
    }
    eligible_support_tasks = sum(
        metrics[task]["eligible_runs"] > 0
        and metrics[task]["eligible_endpoints"] > 0
        for task in affected
    )
    run_share = retained["eligible_runs"] / totals["eligible_runs"]
    endpoint_share = retained["eligible_endpoints"] / totals["eligible_endpoints"]
    dominant_run_share = (
        max(metrics[task]["eligible_runs"] for task in affected)
        / retained["eligible_runs"]
        if retained["eligible_runs"]
        else 1.0
    )
    dominant_endpoint_share = (
        max(metrics[task]["eligible_endpoints"] for task in affected)
        / retained["eligible_endpoints"]
        if retained["eligible_endpoints"]
        else 1.0
    )

    rules = protocol.get("decision_rule")
    if not isinstance(rules, dict):
        raise RetentionAuditError("decision rule missing")
    strong = rules.get("strong")
    partial = rules.get("partial")
    kill = rules.get("kill")
    if not all(isinstance(row, dict) for row in (strong, partial, kill)):
        raise RetentionAuditError("decision rule malformed")

    def passes(rule: dict[str, Any]) -> bool:
        return (
            eligible_support_tasks
            >= nonnegative_int(
                rule.get("minimum_affected_competitions_with_eligible_support"),
                "minimum affected support tasks",
            )
            and run_share
            >= fraction(rule.get("minimum_retained_eligible_run_share"), "run share")
            and endpoint_share
            >= fraction(
                rule.get("minimum_retained_eligible_endpoint_share"),
                "endpoint share",
            )
            and dominant_run_share
            <= fraction(
                rule.get("maximum_dominant_affected_task_eligible_run_share"),
                "run dominance",
            )
            and dominant_endpoint_share
            <= fraction(
                rule.get("maximum_dominant_affected_task_eligible_endpoint_share"),
                "endpoint dominance",
            )
        )

    if passes(strong):
        status = strong.get("status")
    elif passes(partial):
        status = partial.get("status")
    else:
        status = kill.get("status")
    if not isinstance(status, str) or not status:
        raise RetentionAuditError("decision status malformed")

    anonymous = {
        unit: metric_summary([metrics[task][unit] for task in affected])
        for unit in (
            "accepted_archives",
            "physical_runs",
            "eligible_runs",
            "eligible_endpoints",
        )
    }
    remaining = {
        "accepted_archives": totals["accepted_archives"] - retained["accepted_archives"],
        "physical_runs": totals["physical_runs"] - retained["physical_runs"],
        "eligible_runs": totals["eligible_runs"] - retained["eligible_runs"],
        "eligible_endpoints": totals["eligible_endpoints"]
        - retained["eligible_endpoints"],
    }
    return {
        "protocol": PROTOCOL_NAME,
        "status": status,
        "input_bindings": {
            "protocol_sha256": sha256(protocol_path),
            "latest_snapshot_sha256": inputs["current_latest_snapshot_sha256"],
            "observations_sha256": inputs["current_observations_sha256"],
            "prior_result_sha256": inputs["archive_disposition_v2_result_sha256"],
            "prior_verification_sha256": inputs[
                "archive_disposition_v2_verification_sha256"
            ],
        },
        "integrity": {
            "observation_partition_reproduced": True,
            "prior_taxonomy_result_and_verification_hash_bound": True,
            "snapshot_transaction_registry_hash_bound": True,
            "accepted_archives_single_task_hash_bound": True,
            "accepted_provenance_run_ids_unique": True,
            "accepted_structural_totals_reproduced": True,
            "structural_rejected_and_mixed_competition_counts_reproduced": True,
            "aliases_excluded_from_retention_estimand": True,
            "identities_emitted": False,
        },
        "population": {
            **totals,
            "structural_rejected_competitions": len(structural_tasks),
            "structural_mixed_disposition_competitions": len(affected),
            "alias_quarantined_archives": partition["alias_quarantined"],
        },
        "retained_by_archive_granular_validation": {
            "affected_competitions": len(affected),
            "affected_competitions_with_eligible_support": eligible_support_tasks,
            **retained,
            "eligible_run_share_of_accepted_corpus": run_share,
            "eligible_endpoint_share_of_accepted_corpus": endpoint_share,
            "dominant_affected_task_eligible_run_share": dominant_run_share,
            "dominant_affected_task_eligible_endpoint_share": dominant_endpoint_share,
            "anonymous_affected_task_distribution": anonymous,
        },
        "task_blacklist_counterfactual": {
            "additional_valid_support_discarded": retained,
            "remaining_valid_support": remaining,
            "eligible_run_loss_share": run_share,
            "eligible_endpoint_loss_share": endpoint_share,
            "observed_method_effect": False,
        },
        "decision": {
            "strong_gate_passed": status == strong.get("status"),
            "partial_gate_passed": status == partial.get("status"),
            "kill_gate_triggered": status == kill.get("status"),
            "identities_emitted": False,
        },
        "access_attestation": {
            "observation_and_hash_bound_intake_metadata_only": True,
            "archive_payloads_opened": False,
            "labels_grades_outcomes_predictions_accuracy_or_utility_read": False,
            "candidate_identities_or_profiles_read": False,
            "archive_task_run_or_candidate_identity_values_emitted": False,
            "randomness_used": False,
            "gpu_paid_api_model_fit_base_update": "0/0/0/0",
        },
        "claim_boundary": {
            "supports_archive_granularity_retention_accounting": status
            == strong.get("status"),
            "is_observed_method_effect": False,
            "supports_task_whitelist_or_blacklist": False,
            "estimates_predictor_accuracy_scaling_or_search_utility": False,
            "claims_future_corpus_stationarity": False,
        },
    }


def write_new(path: Path, value: dict[str, Any]) -> None:
    if path.exists() or not path.parent.is_dir() or path.parent.is_symlink():
        raise RetentionAuditError("output path exists or parent is unsafe")
    temporary = path.with_name(path.name + f".tmp-{os.getpid()}")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--observations", required=True, type=Path)
    parser.add_argument("--state-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = build_result(args.protocol, args.observations, args.state_root)
        write_new(args.output.resolve(), result)
        retained = result["retained_by_archive_granular_validation"]
        print(
            json.dumps(
                {
                    "status": result["status"],
                    "affected_competitions": retained["affected_competitions"],
                    "eligible_runs_retained": retained["eligible_runs"],
                    "eligible_endpoints_retained": retained["eligible_endpoints"],
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 0
    except (OSError, RetentionAuditError, TypeError, ZeroDivisionError) as exc:
        print(f"ARCHIVE_GRANULARITY_RETENTION_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
