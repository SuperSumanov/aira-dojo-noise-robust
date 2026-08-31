#!/usr/bin/env python3
"""Independent verifier for the archive-granularity retention accounting."""
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


PROTOCOL = "archive_granularity_retention_audit_v1"
OBS_PROTOCOL = "prospective_archive_observer_v1"
PRIOR_PROTOCOL = "archive_disposition_longitudinal_replication_v2"
PRIOR_STATUS = "LONGITUDINAL_ARCHIVE_LEVEL_GATE_REPLICATED"
PRIOR_VERIFY_STATUS = "INDEPENDENT_ARCHIVE_DISPOSITION_REPLICATION_PASS"
HEX64 = re.compile(r"[0-9a-f]{64}")
SEEDED = re.compile(r"(?P<task>.+)-(?P<seeds>[0-9]+)seeds\.tar\.gz")
NORMALIZE = re.compile(r"[^a-z0-9]+")
OBS_KEYS = {
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
TX_KEYS = {
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
PROV_REQUIRED = {
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
PROV_OPTIONAL = {"competition_id_source"}


class VerificationError(RuntimeError):
    pass


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def object_at(path: Path, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise VerificationError(f"unsafe or absent {label}")
    try:
        value = json.loads(path.read_bytes())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VerificationError(f"unparseable {label}") from exc
    if not isinstance(value, dict):
        raise VerificationError(f"non-object {label}")
    return value


def list_at(path: Path, label: str) -> list[Any]:
    if path.is_symlink() or not path.is_file():
        raise VerificationError(f"unsafe or absent {label}")
    try:
        value = json.loads(path.read_bytes())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VerificationError(f"unparseable {label}") from exc
    if not isinstance(value, list):
        raise VerificationError(f"non-list {label}")
    return value


def jsonl_at(path: Path, label: str) -> list[dict[str, Any]]:
    if path.is_symlink() or not path.is_file():
        raise VerificationError(f"unsafe or absent {label}")
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for number, line in enumerate(handle, 1):
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise VerificationError(f"non-object {label} row {number}")
                rows.append(row)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VerificationError(f"unparseable {label}") from exc
    if not rows:
        raise VerificationError(f"empty {label}")
    return rows


def integer(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise VerificationError(f"invalid {label}")
    return value


def unit(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise VerificationError(f"invalid {label}")
    number = float(value)
    if not math.isfinite(number) or not 0.0 <= number <= 1.0:
        raise VerificationError(f"invalid {label}")
    return number


def sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or HEX64.fullmatch(value) is None:
        raise VerificationError(f"invalid {label}")
    return value


def relative_archive(value: Any) -> tuple[str, str]:
    if not isinstance(value, str):
        raise VerificationError("archive path type mismatch")
    parsed = PurePosixPath(value)
    if parsed.is_absolute() or len(parsed.parts) != 2 or any(
        part in {"", ".", ".."} for part in parsed.parts
    ):
        raise VerificationError("archive path shape mismatch")
    directory, basename = parsed.parts
    if not basename.endswith(".tar.gz"):
        raise VerificationError("archive suffix mismatch")
    return directory, basename


def canonical_task(value: Any) -> str:
    if not isinstance(value, str):
        raise VerificationError("task type mismatch")
    normalized = NORMALIZE.sub("-", value.casefold()).strip("-")
    if not normalized:
        raise VerificationError("empty normalized task")
    return normalized


def rejected_task(relative: Any) -> str:
    _directory, basename = relative_archive(relative)
    match = SEEDED.fullmatch(basename)
    if match is None:
        raise VerificationError("rejected archive filename is not seeded")
    return canonical_task(match.group("task"))


def evidence_path(
    protocol_path: Path,
    inputs: dict[str, Any],
    path_key: str,
    hash_key: str,
    label: str,
) -> Path:
    relative = inputs.get(path_key)
    if not isinstance(relative, str) or not relative:
        raise VerificationError(f"missing {label} path")
    root = protocol_path.resolve().parent
    unresolved = root / relative
    if unresolved.is_symlink():
        raise VerificationError(f"symlinked {label}")
    resolved = unresolved.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise VerificationError(f"escaping {label} path") from exc
    if not resolved.is_file() or digest(resolved) != sha(inputs.get(hash_key), label):
        raise VerificationError(f"{label} hash binding mismatch")
    return resolved


def validate_freeze(protocol: dict[str, Any]) -> None:
    if protocol.get("protocol") != PROTOCOL:
        raise VerificationError("protocol identity mismatch")
    if protocol.get("frozen_before_retention_count_readout") is not True:
        raise VerificationError("protocol was not frozen")
    disclosure = protocol.get("disclosure_at_freeze")
    if not isinstance(disclosure, dict):
        raise VerificationError("missing disclosure receipt")
    for key in (
        "affected_competition_identities_read_or_emitted",
        "retained_accepted_archive_count_read",
        "retained_physical_run_count_read",
        "retained_eligible_run_count_read",
        "retained_eligible_endpoint_count_read",
        "affected_task_dominance_read",
    ):
        if disclosure.get(key) is not False:
            raise VerificationError("pre-readout disclosure mismatch")
    if protocol.get("access_contract") != {
        "observation_and_hash_bound_intake_metadata_only": True,
        "archive_payloads_opened": False,
        "labels_grades_outcomes_predictions_accuracy_or_utility_read": False,
        "candidate_identities_or_profiles_read": False,
        "archive_task_run_or_candidate_identity_values_emitted": False,
        "gpu_paid_api_model_fit_base_update": "0/0/0/0",
    }:
        raise VerificationError("access contract mismatch")


def bind_prior(
    protocol_path: Path, protocol: dict[str, Any]
) -> tuple[dict[str, Any], int, int]:
    inputs = protocol.get("inputs")
    disclosure = protocol.get("disclosure_at_freeze")
    if not isinstance(inputs, dict) or not isinstance(disclosure, dict):
        raise VerificationError("protocol inputs/disclosure missing")
    prior_path = evidence_path(
        protocol_path,
        inputs,
        "archive_disposition_v2_result_path",
        "archive_disposition_v2_result_sha256",
        "prior result",
    )
    check_path = evidence_path(
        protocol_path,
        inputs,
        "archive_disposition_v2_verification_path",
        "archive_disposition_v2_verification_sha256",
        "prior verification",
    )
    prior = object_at(prior_path, "prior result")
    check = object_at(check_path, "prior verification")
    current = prior.get("current")
    access = prior.get("access_attestation")
    if (
        prior.get("protocol") != PRIOR_PROTOCOL
        or prior.get("status") != PRIOR_STATUS
        or not isinstance(current, dict)
        or not isinstance(access, dict)
        or access.get("labels_grades_outcomes_predictions_accuracy_or_utility_read")
        is not False
        or access.get("candidate_identities_emitted") is not False
        or check.get("status") != PRIOR_VERIFY_STATUS
        or check.get("all_aggregate_fields_equal") is not True
        or check.get("result_sha256") != digest(prior_path)
    ):
        raise VerificationError("prior evidence contract mismatch")
    structural = integer(
        current.get("structural_rejected_competitions"),
        "prior structural rejected task count",
    )
    mixed = integer(
        current.get("structural_mixed_disposition_competitions"),
        "prior structural mixed task count",
    )
    if structural != integer(
        disclosure.get("structural_rejected_competition_count_known"),
        "disclosed structural task count",
    ) or mixed != integer(
        disclosure.get("structural_mixed_disposition_competition_count_known"),
        "disclosed mixed task count",
    ):
        raise VerificationError("prior disclosure count mismatch")
    return inputs, structural, mixed


def observation_partition(
    protocol: dict[str, Any], observations: dict[str, Any]
) -> tuple[dict[str, str], set[str], dict[str, int]]:
    if set(observations) != {
        "baseline_sealed_at_epoch",
        "entries",
        "protocol",
        "source_root",
    } or observations.get("protocol") != OBS_PROTOCOL:
        raise VerificationError("observation schema mismatch")
    entries = observations.get("entries")
    source_root = observations.get("source_root")
    if not isinstance(entries, dict) or not isinstance(source_root, str):
        raise VerificationError("observation population missing")
    taxonomy = protocol.get("rejection_taxonomy")
    known = protocol.get("known_structural_metadata_before_readout")
    if not isinstance(taxonomy, dict) or not isinstance(known, dict):
        raise VerificationError("taxonomy/known metadata missing")
    target_raw = taxonomy.get("structural_target_reasons")
    alias_raw = taxonomy.get("quarantine_only_reasons")
    if not isinstance(target_raw, list) or not isinstance(alias_raw, list):
        raise VerificationError("taxonomy lists malformed")
    target = set(target_raw)
    aliases = set(alias_raw)
    if (
        not target
        or not aliases
        or target & aliases
        or taxonomy.get("aliases_enter_retention_estimand") is not False
    ):
        raise VerificationError("taxonomy semantics mismatch")
    expected_latest = sha(
        protocol["inputs"].get("current_latest_snapshot_sha256"), "snapshot hash"
    )
    prefix = source_root.rstrip("/") + "/"
    counts = Counter()
    accepted: dict[str, str] = {}
    rejected_tasks: set[str] = set()
    latest_seen = False
    for relative, row in entries.items():
        relative_archive(relative)
        if not isinstance(row, dict) or set(row) != OBS_KEYS:
            raise VerificationError("observation row schema mismatch")
        if row.get("path") != prefix + relative or row.get("present") is not True:
            raise VerificationError("observation row path mismatch")
        if integer(row.get("stable_observations"), "stable observations") == 0:
            raise VerificationError("unstable archive in frozen observations")
        integer(row.get("size"), "archive size")
        baseline = row.get("baseline")
        accepted_fields = (
            row.get("committed_archive_sha256"),
            row.get("committed_snapshot_sha256"),
        )
        rejected_fields = (
            row.get("rejected_archive_sha256"),
            row.get("rejection_reason_code"),
            row.get("rejection_registry_sha256"),
        )
        is_accepted = any(value is not None for value in accepted_fields)
        is_rejected = any(value is not None for value in rejected_fields)
        if not isinstance(baseline, bool) or sum((baseline, is_accepted, is_rejected)) > 1:
            raise VerificationError("observation disposition overlaps")
        if baseline:
            counts["baseline"] += 1
        elif is_accepted:
            if any(value is None for value in accepted_fields):
                raise VerificationError("incomplete accepted disposition")
            archive_hash = sha(accepted_fields[0], "accepted archive hash")
            snapshot_hash = sha(accepted_fields[1], "accepted snapshot hash")
            if archive_hash in accepted:
                raise VerificationError("duplicate accepted archive hash")
            accepted[archive_hash] = relative
            latest_seen |= snapshot_hash == expected_latest
            counts["accepted"] += 1
        elif is_rejected:
            if any(value is None for value in rejected_fields):
                raise VerificationError("incomplete rejected disposition")
            sha(rejected_fields[0], "rejected archive hash")
            sha(rejected_fields[2], "rejection registry hash")
            reason = rejected_fields[1]
            if reason in target:
                rejected_tasks.add(rejected_task(relative))
                counts["structural"] += 1
            elif reason in aliases:
                rejected_task(relative)
                counts["alias"] += 1
            else:
                raise VerificationError("unclassified rejection reason")
        else:
            counts["pending"] += 1
    actual = {
        "observed": len(entries),
        "baseline": counts["baseline"],
        "accepted": counts["accepted"],
        "structural_rejected": counts["structural"],
        "alias_quarantined": counts["alias"],
        "pending": counts["pending"],
    }
    expected = {
        "observed": integer(known.get("observed_archives"), "known observed"),
        "baseline": integer(known.get("baseline_archives"), "known baseline"),
        "accepted": integer(known.get("accepted_archives"), "known accepted"),
        "structural_rejected": integer(
            known.get("structural_rejected_archives"), "known structural rejects"
        ),
        "alias_quarantined": integer(
            known.get("alias_quarantined_archives"), "known aliases"
        ),
        "pending": integer(known.get("pending_archives"), "known pending"),
    }
    if actual != expected or actual["pending"] != 0 or not latest_seen:
        raise VerificationError("frozen observation partition mismatch")
    return accepted, rejected_tasks, actual


def accepted_metrics(
    protocol: dict[str, Any], root_arg: Path, accepted: dict[str, str]
) -> tuple[dict[str, dict[str, int]], dict[str, int]]:
    if root_arg.is_symlink() or not root_arg.is_dir():
        raise VerificationError("unsafe or absent state root")
    root = root_arg.resolve()
    latest = sha(
        protocol["inputs"].get("current_latest_snapshot_sha256"), "snapshot hash"
    )
    snapshot = root / "snapshots" / latest
    manifest = snapshot / "SHA256SUMS"
    if (
        snapshot.is_symlink()
        or not snapshot.is_dir()
        or manifest.is_symlink()
        or not manifest.is_file()
        or digest(manifest) != latest
    ):
        raise VerificationError("snapshot manifest binding mismatch")
    tx_hashes: list[str] = []
    for line in manifest.read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if match is None:
            raise VerificationError("malformed snapshot manifest")
        if match.group(2) == "transactions.jsonl":
            tx_hashes.append(match.group(1))
    if len(tx_hashes) != 1:
        raise VerificationError("transaction manifest cardinality mismatch")
    tx_path = snapshot / "transactions.jsonl"
    if tx_path.is_symlink() or not tx_path.is_file() or digest(tx_path) != tx_hashes[0]:
        raise VerificationError("transaction file hash mismatch")
    transactions: dict[str, dict[str, Any]] = {}
    for row in jsonl_at(tx_path, "transaction registry"):
        if set(row) != TX_KEYS:
            raise VerificationError("transaction schema mismatch")
        archive_hash = sha(row.get("archive_sha256"), "transaction archive hash")
        if archive_hash in transactions:
            raise VerificationError("duplicate transaction archive hash")
        relative_archive(row.get("archive_relative_path"))
        sha(row.get("intake_summary_sha256"), "intake summary hash")
        transactions[archive_hash] = row
    if set(transactions) != set(accepted):
        raise VerificationError("transaction population differs from observations")

    metrics: dict[str, dict[str, int]] = defaultdict(
        lambda: {
            "accepted_archives": 0,
            "physical_runs": 0,
            "eligible_runs": 0,
            "eligible_endpoints": 0,
        }
    )
    run_ids: set[str] = set()
    provenance_count = 0
    for archive_hash, relative in sorted(accepted.items()):
        tx = transactions[archive_hash]
        if tx.get("archive_relative_path") != relative:
            raise VerificationError("transaction archive path mismatch")
        drop_id = tx.get("drop_id")
        intake_value = tx.get("intake_dir")
        if not isinstance(drop_id, str) or not drop_id or not isinstance(intake_value, str):
            raise VerificationError("transaction intake identity mismatch")
        intake = Path(intake_value)
        if (
            intake.is_symlink()
            or not intake.is_dir()
            or intake.resolve().parent != root / "intakes"
            or intake.resolve().name != drop_id
        ):
            raise VerificationError("transaction intake binding mismatch")
        intake = intake.resolve()
        summary_path = intake / "summary.json"
        if summary_path.is_symlink() or not summary_path.is_file():
            raise VerificationError("unsafe or absent intake summary")
        if digest(summary_path) != tx["intake_summary_sha256"]:
            raise VerificationError("intake summary hash mismatch")
        summary = object_at(summary_path, "intake summary")
        output = summary.get("outputs")
        security = summary.get("security")
        blindness = summary.get("blindness")
        if (
            summary.get("protocol") != "prospective_drop_intake_v1"
            or summary.get("status") != "PROSPECTIVE_DROP_INTAKE_COMPLETE"
            or not isinstance(output, dict)
            or not isinstance(security, dict)
            or not isinstance(blindness, dict)
            or security.get("env_members_read") is not False
            or security.get("live_event_journal_members_read") is not False
            or security.get("journal_scanned_before_json") is not True
            or blindness.get("labels_used_for_run_selection") is not False
            or blindness.get("labels_used_for_endpoint_selection") is not False
            or blindness.get("label_values_printed") is not False
        ):
            raise VerificationError("intake blindness receipt mismatch")
        provenance_path = intake / "source_provenance.json"
        if provenance_path.is_symlink() or not provenance_path.is_file():
            raise VerificationError("unsafe or absent source provenance")
        if digest(provenance_path) != sha(
            output.get("source_provenance_sha256"), "source provenance hash"
        ):
            raise VerificationError("source provenance hash mismatch")
        tasks: set[str] = set()
        _directory, basename = relative_archive(relative)
        for row in list_at(provenance_path, "source provenance"):
            if not isinstance(row, dict) or not (
                PROV_REQUIRED <= set(row) <= PROV_REQUIRED | PROV_OPTIONAL
            ):
                raise VerificationError("source provenance schema mismatch")
            if row.get("archive_sha256") != archive_hash or row.get("archive_name") != basename:
                raise VerificationError("source provenance archive binding mismatch")
            task = canonical_task(row.get("task"))
            tasks.add(task)
            run_id = row.get("run_id")
            if not isinstance(run_id, str) or not run_id or run_id in run_ids:
                raise VerificationError("duplicate provenance run identity")
            run_ids.add(run_id)
            eligible = row.get("eligible")
            if not isinstance(eligible, bool):
                raise VerificationError("malformed eligibility flag")
            endpoints = integer(row.get("endpoints"), "eligible endpoints")
            metrics[task]["physical_runs"] += 1
            if eligible:
                metrics[task]["eligible_runs"] += 1
                metrics[task]["eligible_endpoints"] += endpoints
            provenance_count += 1
        if len(tasks) != 1:
            raise VerificationError("accepted archive is not single-task")
        metrics[next(iter(tasks))]["accepted_archives"] += 1

    totals = {
        "accepted_archives": sum(row["accepted_archives"] for row in metrics.values()),
        "accepted_tasks": len(metrics),
        "physical_runs": sum(row["physical_runs"] for row in metrics.values()),
        "eligible_runs": sum(row["eligible_runs"] for row in metrics.values()),
        "eligible_endpoints": sum(row["eligible_endpoints"] for row in metrics.values()),
        "hash_bound_source_provenance_rows": provenance_count,
        "unique_run_ids": len(run_ids),
    }
    known = protocol["known_structural_metadata_before_readout"]
    expected = {
        "accepted_archives": integer(known.get("accepted_archives"), "known archives"),
        "accepted_tasks": integer(known.get("accepted_tasks"), "known tasks"),
        "physical_runs": integer(known.get("accepted_physical_runs"), "known physical runs"),
        "eligible_runs": integer(known.get("accepted_eligible_runs"), "known eligible runs"),
        "eligible_endpoints": integer(
            known.get("accepted_eligible_endpoints"), "known endpoints"
        ),
        "hash_bound_source_provenance_rows": integer(
            known.get("hash_bound_source_provenance_rows"), "known provenance rows"
        ),
        "unique_run_ids": integer(known.get("accepted_physical_runs"), "known unique runs"),
    }
    if totals != expected:
        raise VerificationError("accepted totals mismatch")
    if totals["eligible_runs"] == 0 or totals["eligible_endpoints"] == 0:
        raise VerificationError("accepted eligible support is empty")
    return dict(metrics), totals


def distribution(values: list[int]) -> dict[str, int | float]:
    if not values:
        raise VerificationError("empty anonymous affected distribution")
    return {
        "minimum": min(values),
        "median": statistics.median(values),
        "maximum": max(values),
    }


def verify(
    protocol_path: Path,
    observations_path: Path,
    result_path: Path,
    state_root: Path,
) -> dict[str, Any]:
    if protocol_path.is_symlink() or not protocol_path.is_file():
        raise VerificationError("unsafe or absent protocol")
    if observations_path.is_symlink() or not observations_path.is_file():
        raise VerificationError("unsafe or absent observations")
    if result_path.is_symlink() or not result_path.is_file():
        raise VerificationError("unsafe or absent result")
    protocol_path = protocol_path.resolve()
    observations_path = observations_path.resolve()
    result_path = result_path.resolve()
    protocol = object_at(protocol_path, "protocol")
    result = object_at(result_path, "result")
    validate_freeze(protocol)
    inputs, prior_structural, prior_mixed = bind_prior(protocol_path, protocol)
    if digest(observations_path) != sha(inputs.get("current_observations_sha256"), "observations hash"):
        raise VerificationError("observations hash mismatch")
    if observations_path.stat().st_size != integer(
        inputs.get("current_observations_bytes"), "observations byte count"
    ):
        raise VerificationError("observations byte count mismatch")
    observations = object_at(observations_path, "observations")
    accepted, structural_tasks, partition = observation_partition(protocol, observations)
    if len(structural_tasks) != prior_structural:
        raise VerificationError("structural task count differs from prior result")
    known = protocol["known_structural_metadata_before_readout"]
    if prior_structural != integer(
        known.get("structural_rejected_competitions"),
        "known structural rejected task count",
    ) or prior_mixed != integer(
        known.get("structural_mixed_disposition_competitions"),
        "known mixed task count",
    ):
        raise VerificationError("known competition aggregate mismatch")
    metrics, totals = accepted_metrics(protocol, state_root, accepted)
    affected = set(metrics) & structural_tasks
    if len(affected) != prior_mixed:
        raise VerificationError("mixed task count differs from prior result")

    units = ("accepted_archives", "physical_runs", "eligible_runs", "eligible_endpoints")
    retained = {unit_name: sum(metrics[t][unit_name] for t in affected) for unit_name in units}
    support_tasks = sum(
        metrics[t]["eligible_runs"] > 0 and metrics[t]["eligible_endpoints"] > 0
        for t in affected
    )
    run_share = retained["eligible_runs"] / totals["eligible_runs"]
    endpoint_share = retained["eligible_endpoints"] / totals["eligible_endpoints"]
    run_dominance = (
        max(metrics[t]["eligible_runs"] for t in affected) / retained["eligible_runs"]
        if retained["eligible_runs"]
        else 1.0
    )
    endpoint_dominance = (
        max(metrics[t]["eligible_endpoints"] for t in affected)
        / retained["eligible_endpoints"]
        if retained["eligible_endpoints"]
        else 1.0
    )
    rules = protocol.get("decision_rule")
    if not isinstance(rules, dict):
        raise VerificationError("missing decision rules")
    strong, partial, kill = rules.get("strong"), rules.get("partial"), rules.get("kill")
    if not all(isinstance(value, dict) for value in (strong, partial, kill)):
        raise VerificationError("malformed decision rules")

    def rule_passes(rule: dict[str, Any]) -> bool:
        return (
            support_tasks
            >= integer(
                rule.get("minimum_affected_competitions_with_eligible_support"),
                "minimum support tasks",
            )
            and run_share >= unit(rule.get("minimum_retained_eligible_run_share"), "minimum run share")
            and endpoint_share
            >= unit(rule.get("minimum_retained_eligible_endpoint_share"), "minimum endpoint share")
            and run_dominance
            <= unit(
                rule.get("maximum_dominant_affected_task_eligible_run_share"),
                "maximum run dominance",
            )
            and endpoint_dominance
            <= unit(
                rule.get("maximum_dominant_affected_task_eligible_endpoint_share"),
                "maximum endpoint dominance",
            )
        )

    if rule_passes(strong):
        status = strong.get("status")
    elif rule_passes(partial):
        status = partial.get("status")
    else:
        status = kill.get("status")
    if not isinstance(status, str) or not status:
        raise VerificationError("invalid expected status")
    anonymous = {
        unit_name: distribution([metrics[t][unit_name] for t in affected])
        for unit_name in units
    }
    remaining = {
        "accepted_archives": totals["accepted_archives"] - retained["accepted_archives"],
        "physical_runs": totals["physical_runs"] - retained["physical_runs"],
        "eligible_runs": totals["eligible_runs"] - retained["eligible_runs"],
        "eligible_endpoints": totals["eligible_endpoints"] - retained["eligible_endpoints"],
    }
    expected = {
        "protocol": PROTOCOL,
        "status": status,
        "input_bindings": {
            "protocol_sha256": digest(protocol_path),
            "latest_snapshot_sha256": inputs["current_latest_snapshot_sha256"],
            "observations_sha256": inputs["current_observations_sha256"],
            "prior_result_sha256": inputs["archive_disposition_v2_result_sha256"],
            "prior_verification_sha256": inputs["archive_disposition_v2_verification_sha256"],
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
            "affected_competitions_with_eligible_support": support_tasks,
            **retained,
            "eligible_run_share_of_accepted_corpus": run_share,
            "eligible_endpoint_share_of_accepted_corpus": endpoint_share,
            "dominant_affected_task_eligible_run_share": run_dominance,
            "dominant_affected_task_eligible_endpoint_share": endpoint_dominance,
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
            "supports_archive_granularity_retention_accounting": status == strong.get("status"),
            "is_observed_method_effect": False,
            "supports_task_whitelist_or_blacklist": False,
            "estimates_predictor_accuracy_scaling_or_search_utility": False,
            "claims_future_corpus_stationarity": False,
        },
    }
    if result != expected:
        raise VerificationError("result differs from independent reconstruction")
    return {
        "protocol": "independent_archive_granularity_retention_v1",
        "status": "INDEPENDENT_ARCHIVE_GRANULARITY_RETENTION_PASS",
        "result_sha256": digest(result_path),
        "result_status": status,
        "recomputed_aggregate": {
            "affected_competitions": len(affected),
            "affected_competitions_with_eligible_support": support_tasks,
            "retained_accepted_archives": retained["accepted_archives"],
            "retained_physical_runs": retained["physical_runs"],
            "retained_eligible_runs": retained["eligible_runs"],
            "retained_eligible_endpoints": retained["eligible_endpoints"],
            "eligible_run_share_of_accepted_corpus": run_share,
            "eligible_endpoint_share_of_accepted_corpus": endpoint_share,
            "dominant_affected_task_eligible_run_share": run_dominance,
            "dominant_affected_task_eligible_endpoint_share": endpoint_dominance,
        },
        "all_aggregate_fields_equal": True,
        "identities_emitted": False,
        "outcomes_predictions_labels_read": False,
        "randomness_used": False,
    }


def write_new(path: Path, value: dict[str, Any]) -> None:
    if path.exists() or not path.parent.is_dir() or path.parent.is_symlink():
        raise VerificationError("verification output exists or parent is unsafe")
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
    parser.add_argument("--result", required=True, type=Path)
    parser.add_argument("--state-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        receipt = verify(
            args.protocol,
            args.observations,
            args.result,
            args.state_root,
        )
        write_new(args.output.resolve(), receipt)
        print(json.dumps(receipt["recomputed_aggregate"], sort_keys=True, separators=(",", ":")))
        return 0
    except (OSError, VerificationError, TypeError, ZeroDivisionError) as exc:
        print(f"ARCHIVE_GRANULARITY_RETENTION_VERIFY_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
