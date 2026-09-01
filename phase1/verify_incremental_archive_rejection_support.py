#!/usr/bin/env python3
"""Non-importing verifier for the incremental archive-rejection support audit."""
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


AUDIT_PROTOCOL = "incremental_archive_rejection_support_audit_v1"
OBSERVER_PROTOCOL = "prospective_archive_observer_v1"
PRIOR_RESULT_STATUS = "LONGITUDINAL_ARCHIVE_LEVEL_GATE_REPLICATED"
PRIOR_VERIFIER_STATUS = "INDEPENDENT_ARCHIVE_DISPOSITION_REPLICATION_PASS"
VERIFIER_PROTOCOL = "independent_incremental_archive_rejection_support_v1"
VERIFIER_STATUS = "INDEPENDENT_INCREMENTAL_ARCHIVE_SUPPORT_PASS"
ALIAS = "ARCHIVE_BYTES_DUPLICATE_COMMITTED_TRANSACTION"
STRUCTURAL = {
    "ARCHIVE_HAS_NO_CHECKPOINT_JOURNALS",
    "JOURNAL_TASK_IDENTITY_ABSENT_ALL_CHECKPOINTS",
    "JOURNAL_TASK_IDENTITY_NOT_EXACTLY_ONE_WITHIN_ARCHIVE",
}
HEX64 = re.compile(r"[0-9a-f]{64}")
SEEDED = re.compile(r"(?P<task>.+)-(?P<count>[0-9]+)seeds\.tar\.gz")
NON_TASK = re.compile(r"[^a-z0-9]+")
OBSERVATION_FIELDS = {
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
PROVENANCE_REQUIRED = {
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
PROVENANCE_OPTIONAL = {"competition_id_source"}
METRIC_KEYS = ("accepted_archives", "physical_runs", "eligible_runs", "eligible_endpoints")


class IndependentVerificationError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise IndependentVerificationError(message)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def object_from(path: Path, label: str) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"unsafe {label}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise IndependentVerificationError(f"cannot parse {label}") from exc
    require(isinstance(value, dict), f"{label} is not an object")
    return value


def list_from(path: Path, label: str) -> list[Any]:
    require(path.is_file() and not path.is_symlink(), f"unsafe {label}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise IndependentVerificationError(f"cannot parse {label}") from exc
    require(isinstance(value, list), f"{label} is not a list")
    return value


def integer(value: Any, label: str) -> int:
    require(isinstance(value, int) and not isinstance(value, bool) and value >= 0, f"bad {label}")
    return value


def sha(value: Any, label: str) -> str:
    require(isinstance(value, str) and HEX64.fullmatch(value) is not None, f"bad {label}")
    return value


def archive_path(value: Any) -> tuple[str, str]:
    require(isinstance(value, str), "archive path is not text")
    parsed = PurePosixPath(value)
    require(
        not parsed.is_absolute()
        and len(parsed.parts) == 2
        and all(part not in {"", ".", ".."} for part in parsed.parts),
        "archive path is malformed",
    )
    directory, basename = parsed.parts
    require(basename.endswith(".tar.gz"), "archive suffix is malformed")
    return directory, basename


def canonical_task(value: Any) -> str:
    require(isinstance(value, str), "task metadata is not text")
    normalized = NON_TASK.sub("-", value.casefold()).strip("-")
    require(bool(normalized), "task metadata is empty after normalization")
    return normalized


def target_task(relative: Any) -> str:
    _directory, basename = archive_path(relative)
    match = SEEDED.fullmatch(basename)
    require(match is not None, "target rejection does not have a seeded filename")
    return canonical_task(match.group("task"))


def zero_metrics() -> dict[str, int]:
    return {key: 0 for key in METRIC_KEYS}


def add_metrics(left: dict[str, int], right: dict[str, int]) -> dict[str, int]:
    return {key: left[key] + right[key] for key in METRIC_KEYS}


def bind_repo_file(
    repo_root: Path,
    inputs: dict[str, Any],
    path_field: str,
    hash_field: str,
    label: str,
) -> Path:
    relative = inputs.get(path_field)
    require(isinstance(relative, str) and bool(relative), f"{label} path missing")
    unresolved = repo_root / relative
    require(not unresolved.is_symlink(), f"{label} path is symlinked")
    resolved = unresolved.resolve()
    try:
        resolved.relative_to(repo_root)
    except ValueError as exc:
        raise IndependentVerificationError(f"{label} escapes repository") from exc
    require(resolved.is_file(), f"{label} missing")
    require(digest(resolved) == sha(inputs.get(hash_field), f"{label} hash"), f"{label} hash differs")
    return resolved


def validate_protocol(protocol: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    require(protocol.get("protocol") == AUDIT_PROTOCOL, "audit protocol mismatch")
    require(protocol.get("frozen_before_target_competition_or_support_readout") is True, "audit not frozen")
    unknown = protocol.get("unknown_at_freeze")
    require(isinstance(unknown, dict) and unknown and set(unknown.values()) == {False}, "unknown disclosure mismatch")
    selector = protocol.get("target_selection")
    require(
        isinstance(selector, dict)
        and selector.get("required_count") == 1
        and selector.get("caller_may_choose_archive_or_competition") is False
        and selector.get("registry_contents_required_for_selection") is False
        and selector.get("registry_file_hash_only") is True,
        "selector contract mismatch",
    )
    require(
        protocol.get("access_contract")
        == {
            "observation_and_hash_bound_intake_metadata_only": True,
            "target_registry_contents_opened": False,
            "archive_payloads_opened": False,
            "labels_grades_outcomes_predictions_accuracy_or_utility_read": False,
            "candidate_identities_or_profiles_read": False,
            "archive_task_run_or_candidate_identity_values_emitted": False,
            "gpu_paid_api_model_fit_base_update": "0/0/0/0",
        },
        "access contract mismatch",
    )
    inputs = protocol.get("inputs")
    known = protocol.get("known_before_readout")
    require(isinstance(inputs, dict) and isinstance(known, dict), "protocol inputs missing")
    return inputs, known


def verify_prior_anchors(protocol_path: Path, protocol: dict[str, Any]) -> None:
    inputs = protocol["inputs"]
    repo_root = protocol_path.parent
    prior_result_path = bind_repo_file(
        repo_root,
        inputs,
        "prior_archive_disposition_result_path",
        "prior_archive_disposition_result_sha256",
        "prior result",
    )
    prior_verification_path = bind_repo_file(
        repo_root,
        inputs,
        "prior_archive_disposition_verification_path",
        "prior_archive_disposition_verification_sha256",
        "prior verification",
    )
    target_registry_path = bind_repo_file(
        repo_root,
        inputs,
        "target_rejection_registry_path",
        "target_rejection_registry_sha256",
        "target registry",
    )
    require(target_registry_path.stat().st_size > 0, "target registry empty")
    prior_result = object_from(prior_result_path, "prior result")
    prior_verification = object_from(prior_verification_path, "prior verification")
    expected_prior = protocol["known_before_readout"]["prior"]
    prior_counts = prior_result.get("current")
    require(
        prior_result.get("status") == PRIOR_RESULT_STATUS and isinstance(prior_counts, dict),
        "prior result status mismatch",
    )
    require(
        prior_result.get("input_bindings", {}).get("current_latest_snapshot_sha256")
        == inputs["prior_snapshot_sha256"],
        "prior result snapshot mismatch",
    )
    for field in (
        "observed_archives",
        "accepted_archives",
        "structural_rejected_archives",
        "alias_quarantined_archives",
        "pending_archives",
    ):
        require(prior_counts.get(field) == expected_prior[field], f"prior result {field} mismatch")
    require(
        prior_verification.get("status") == PRIOR_VERIFIER_STATUS
        and prior_verification.get("result_sha256") == inputs["prior_archive_disposition_result_sha256"]
        and prior_verification.get("identities_emitted") is False
        and prior_verification.get("outcomes_predictions_labels_read") is False,
        "prior verification mismatch",
    )


def read_snapshot_transactions(
    state: Path, snapshot_sha: str, transaction_sha: str, expected_lines: int
) -> tuple[Path, bytes, list[dict[str, Any]]]:
    snapshot = state / "snapshots" / snapshot_sha
    require(snapshot.is_dir() and not snapshot.is_symlink(), "unsafe snapshot root")
    manifest = snapshot / "SHA256SUMS"
    require(manifest.is_file() and not manifest.is_symlink(), "unsafe snapshot manifest")
    require(digest(manifest) == snapshot_sha, "snapshot identity mismatch")
    manifest_entries: dict[str, str] = {}
    try:
        manifest_lines = manifest.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise IndependentVerificationError("snapshot manifest encoding mismatch") from exc
    for line in manifest_lines:
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        require(match is not None, "snapshot manifest syntax mismatch")
        relative = match.group(2)
        pure = PurePosixPath(relative)
        require(
            not pure.is_absolute()
            and all(part not in {"", ".", ".."} for part in pure.parts)
            and relative not in manifest_entries,
            "snapshot manifest path mismatch",
        )
        manifest_entries[relative] = match.group(1)
    transaction_path = snapshot / "transactions.jsonl"
    require(
        transaction_path.is_file()
        and not transaction_path.is_symlink()
        and manifest_entries.get("transactions.jsonl") == transaction_sha,
        "transactions manifest binding mismatch",
    )
    data = transaction_path.read_bytes()
    require(hashlib.sha256(data).hexdigest() == transaction_sha, "transactions hash mismatch")
    try:
        rows = [json.loads(line) for line in data.decode("utf-8").splitlines() if line]
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise IndependentVerificationError("transactions parse failure") from exc
    require(len(rows) == expected_lines and all(isinstance(row, dict) for row in rows), "transactions count mismatch")
    return snapshot, data, rows


def classify_observations(
    protocol: dict[str, Any], observations: dict[str, Any]
) -> tuple[dict[str, str], dict[str, Any], dict[str, Any]]:
    require(
        set(observations) == {"entries", "minimum_age_seconds", "protocol", "source_root", "updated_at_utc"}
        and observations.get("protocol") == OBSERVER_PROTOCOL,
        "observation container mismatch",
    )
    entries = observations.get("entries")
    source_root = observations.get("source_root")
    require(isinstance(entries, dict), "observation entries missing")
    require(isinstance(source_root, str) and bool(source_root), "observation source root missing")
    prefix = source_root.rstrip("/") + "/"
    target_registry = protocol["inputs"]["target_rejection_registry_sha256"]
    accepted: dict[str, str] = {}
    targets: list[tuple[str, dict[str, Any]]] = []
    counts: Counter[str] = Counter()
    reasons: Counter[str] = Counter()
    for relative, row in entries.items():
        archive_path(relative)
        require(isinstance(row, dict) and set(row) == OBSERVATION_FIELDS, "observation row schema mismatch")
        require(row.get("path") == prefix + relative and row.get("present") is True, "observation path mismatch")
        require(integer(row.get("stable_observations"), "stable observations") > 0, "unstable observation")
        integer(row.get("size"), "archive size")
        integer(row.get("mtime_ns"), "archive mtime")
        baseline = row.get("baseline")
        require(isinstance(baseline, bool), "baseline flag mismatch")
        committed = row.get("committed_archive_sha256")
        committed_snapshot = row.get("committed_snapshot_sha256")
        rejected = row.get("rejected_archive_sha256")
        registry = row.get("rejection_registry_sha256")
        reason = row.get("rejection_reason_code")
        is_accepted = committed is not None or committed_snapshot is not None
        is_rejected = rejected is not None or registry is not None or reason is not None
        require(sum((baseline, is_accepted, is_rejected)) == 1, "observation disposition overlap or gap")
        if baseline:
            counts["baseline"] += 1
        elif is_accepted:
            archive_sha = sha(committed, "accepted archive hash")
            sha(committed_snapshot, "accepted snapshot hash")
            require(archive_sha not in accepted, "duplicate accepted archive hash")
            accepted[archive_sha] = relative
            counts["accepted"] += 1
        else:
            sha(rejected, "rejected archive hash")
            registry_sha = sha(registry, "rejection registry hash")
            require(reason in STRUCTURAL | {ALIAS}, "unknown rejection reason")
            counts["alias" if reason == ALIAS else "structural"] += 1
            reasons[str(reason)] += 1
            if registry_sha == target_registry:
                targets.append((relative, row))
    known = protocol["known_before_readout"]["current"]
    require(len(entries) == known["observed_archives"], "observed count mismatch")
    require(counts["baseline"] == known["baseline_archives"], "baseline count mismatch")
    require(counts["accepted"] == known["accepted_archives"], "accepted count mismatch")
    require(counts["structural"] == known["structural_rejected_archives"], "structural count mismatch")
    require(counts["alias"] == known["alias_quarantined_archives"], "alias count mismatch")
    require(dict(sorted(reasons.items())) == known["rejection_reason_counts"], "rejection reasons mismatch")
    require(len(targets) == 1, "target hash did not select exactly one rejection")
    target_relative, target_row = targets[0]
    require(
        target_row.get("rejection_reason_code") == protocol["target_selection"]["required_rejection_reason"],
        "target reason mismatch",
    )
    require(target_row.get("rejected_archive_sha256") not in accepted, "target payload overlaps accepted payload")
    partition = {
        "observed_archives": len(entries),
        "baseline_archives": counts["baseline"],
        "accepted_archives": counts["accepted"],
        "structural_rejected_archives": counts["structural"],
        "alias_quarantined_archives": counts["alias"],
        "pending_archives": 0,
        "rejection_reason_counts": dict(sorted(reasons.items())),
    }
    return accepted, {"relative": target_relative, "row": target_row}, partition


def validate_transaction(row: dict[str, Any]) -> str:
    require(set(row) == TRANSACTION_FIELDS, "transaction schema mismatch")
    archive_sha = sha(row.get("archive_sha256"), "transaction archive hash")
    integer(row.get("archive_size"), "transaction archive size")
    for field in ("archive_relative_path", "committed_at_utc", "drop_id", "intake_dir", "score_dir"):
        require(isinstance(row.get(field), str) and bool(row[field]), "transaction text field mismatch")
    archive_path(row["archive_relative_path"])
    sha(row.get("intake_summary_sha256"), "intake summary hash")
    sha(row.get("score_summary_sha256"), "score summary hash")
    return archive_sha


def reconstruct_support(
    state: Path,
    transactions: list[dict[str, Any]],
    accepted: dict[str, str],
    prior_cutoff: int,
) -> tuple[dict[str, dict[str, int]], dict[str, dict[str, int]], dict[str, int]]:
    transaction_by_hash: dict[str, tuple[int, dict[str, Any]]] = {}
    for index, row in enumerate(transactions):
        archive_sha = validate_transaction(row)
        require(archive_sha not in transaction_by_hash, "duplicate transaction archive hash")
        transaction_by_hash[archive_sha] = (index, row)
    require(set(transaction_by_hash) == set(accepted), "accepted observations and transactions differ")

    prior: dict[str, dict[str, int]] = {}
    new: dict[str, dict[str, int]] = {}
    seen_runs: set[str] = set()
    mapping = {
        "accepted_single_task_archives": 0,
        "accepted_seeded_filename_archives": 0,
        "accepted_task_metadata_fallback_archives": 0,
        "accepted_filename_task_mismatches": 0,
        "hash_bound_source_provenance_rows": 0,
        "unique_run_ids": 0,
        "accepted_tasks": 0,
        **zero_metrics(),
    }
    for archive_sha, relative in sorted(accepted.items()):
        index, transaction = transaction_by_hash[archive_sha]
        require(transaction["archive_relative_path"] == relative, "transaction archive path mismatch")
        unresolved_intake = Path(transaction["intake_dir"])
        require(not unresolved_intake.is_symlink(), "intake path is symlinked")
        intake = unresolved_intake.resolve()
        require(
            intake.is_dir() and intake.parent == state / "intakes" and intake.name == transaction["drop_id"],
            "intake path binding mismatch",
        )
        summary_path = intake / "summary.json"
        require(summary_path.is_file() and not summary_path.is_symlink(), "unsafe intake summary")
        require(digest(summary_path) == transaction["intake_summary_sha256"], "intake summary hash mismatch")
        summary = object_from(summary_path, "intake summary")
        outputs = summary.get("outputs")
        security = summary.get("security")
        blindness = summary.get("blindness")
        require(
            summary.get("status") == "PROSPECTIVE_DROP_INTAKE_COMPLETE"
            and summary.get("protocol") == "prospective_drop_intake_v1"
            and isinstance(outputs, dict)
            and isinstance(security, dict)
            and isinstance(blindness, dict)
            and security.get("env_members_read") is False
            and security.get("live_event_journal_members_read") is False
            and security.get("journal_scanned_before_json") is True
            and blindness.get("labels_used_for_run_selection") is False
            and blindness.get("labels_used_for_endpoint_selection") is False
            and blindness.get("label_values_printed") is False,
            "intake blindness receipt mismatch",
        )
        provenance_path = intake / "source_provenance.json"
        require(provenance_path.is_file() and not provenance_path.is_symlink(), "unsafe source provenance")
        require(
            digest(provenance_path) == sha(outputs.get("source_provenance_sha256"), "source provenance hash"),
            "source provenance hash mismatch",
        )
        provenance = list_from(provenance_path, "source provenance")
        tasks: set[str] = set()
        _directory, basename = archive_path(relative)
        table = prior if index < prior_cutoff else new
        for item in provenance:
            require(
                isinstance(item, dict)
                and PROVENANCE_REQUIRED <= set(item) <= PROVENANCE_REQUIRED | PROVENANCE_OPTIONAL,
                "source provenance schema mismatch",
            )
            require(
                item.get("archive_sha256") == archive_sha and item.get("archive_name") == basename,
                "source provenance archive binding mismatch",
            )
            task = canonical_task(item.get("task"))
            tasks.add(task)
            run_id = item.get("run_id")
            require(isinstance(run_id, str) and bool(run_id) and run_id not in seen_runs, "duplicate run identity")
            seen_runs.add(run_id)
            eligible = item.get("eligible")
            require(isinstance(eligible, bool), "eligible flag mismatch")
            endpoints = integer(item.get("endpoints"), "endpoint count")
            metric = table.setdefault(task, zero_metrics())
            metric["physical_runs"] += 1
            mapping["physical_runs"] += 1
            if eligible:
                metric["eligible_runs"] += 1
                metric["eligible_endpoints"] += endpoints
                mapping["eligible_runs"] += 1
                mapping["eligible_endpoints"] += endpoints
            mapping["hash_bound_source_provenance_rows"] += 1
        require(len(tasks) == 1, "accepted archive has multiple tasks")
        task = next(iter(tasks))
        table[task]["accepted_archives"] += 1
        mapping["accepted_archives"] += 1
        mapping["accepted_single_task_archives"] += 1
        filename_match = SEEDED.fullmatch(basename)
        if filename_match is None:
            mapping["accepted_task_metadata_fallback_archives"] += 1
        else:
            mapping["accepted_seeded_filename_archives"] += 1
            mapping["accepted_filename_task_mismatches"] += canonical_task(filename_match.group("task")) != task
    mapping["unique_run_ids"] = len(seen_runs)
    mapping["accepted_tasks"] = len(set(prior) | set(new))
    return prior, new, mapping


def choose_status(protocol: dict[str, Any], prior: dict[str, int], current: dict[str, int]) -> str:
    rules = protocol["decision_rule"]
    strong = rules["strong"]
    if (
        prior["accepted_archives"] >= strong["minimum_prior_accepted_archives"]
        and prior["eligible_runs"] >= strong["minimum_prior_eligible_runs"]
        and prior["eligible_endpoints"] >= strong["minimum_prior_eligible_endpoints"]
    ):
        return strong["status"]
    partial = rules["partial"]
    if (
        current["accepted_archives"] >= partial["minimum_current_accepted_archives"]
        and current["eligible_runs"] >= partial["minimum_current_eligible_runs"]
        and current["eligible_endpoints"] >= partial["minimum_current_eligible_endpoints"]
    ):
        return partial["status"]
    return rules["absent"]["status"]


def verify(
    protocol_path: Path,
    observations_path: Path,
    result_path: Path,
    state_root: Path,
) -> dict[str, Any]:
    require(protocol_path.is_file() and not protocol_path.is_symlink(), "unsafe protocol path")
    require(observations_path.is_file() and not observations_path.is_symlink(), "unsafe observations path")
    require(result_path.is_file() and not result_path.is_symlink(), "unsafe result path")
    require(state_root.is_dir() and not state_root.is_symlink(), "unsafe state root")
    protocol_path = protocol_path.resolve()
    observations_path = observations_path.resolve()
    result_path = result_path.resolve()
    state = state_root.resolve()
    protocol = object_from(protocol_path, "protocol")
    inputs, known = validate_protocol(protocol)
    verify_prior_anchors(protocol_path, protocol)
    latest_path = state / "LATEST"
    require(latest_path.is_file() and not latest_path.is_symlink(), "unsafe LATEST")
    require(latest_path.read_text(encoding="ascii").strip() == inputs["current_snapshot_sha256"], "LATEST mismatch")
    require(digest(observations_path) == inputs["current_observations_sha256"], "observations hash mismatch")
    require(observations_path.stat().st_size == inputs["current_observations_bytes"], "observations size mismatch")
    accepted, target, partition = classify_observations(protocol, object_from(observations_path, "observations"))
    prior_snapshot, prior_bytes, prior_rows = read_snapshot_transactions(
        state,
        inputs["prior_snapshot_sha256"],
        inputs["prior_transactions_sha256"],
        inputs["prior_transaction_lines"],
    )
    current_snapshot, current_bytes, current_rows = read_snapshot_transactions(
        state,
        inputs["current_snapshot_sha256"],
        inputs["current_transactions_sha256"],
        inputs["current_transaction_lines"],
    )
    require(current_bytes.startswith(prior_bytes), "current transactions lack prior byte prefix")
    require(
        len(current_rows) - len(prior_rows) == known["increment"]["accepted_archives"],
        "accepted transaction increment mismatch",
    )
    require(prior_snapshot != current_snapshot, "snapshot roots collapse")
    accumulator_summary = object_from(current_snapshot / "accumulator" / "summary.json", "accumulator summary")
    inventory = accumulator_summary.get("inventory")
    current_known = known["current"]
    require(isinstance(inventory, dict), "inventory missing")
    expected_inventory = {
        "all_physical_runs": current_known["physical_runs"],
        "eligible_runs": current_known["eligible_runs"],
        "eligible_endpoints": current_known["eligible_endpoints"],
        "eligible_structural_pairs": current_known["eligible_structural_pairs"],
        "eligible_tasks": current_known["eligible_tasks"],
    }
    require(all(inventory.get(key) == value for key, value in expected_inventory.items()), "inventory mismatch")
    prior_by_task, new_by_task, mapping = reconstruct_support(
        state, current_rows, accepted, inputs["prior_transaction_lines"]
    )
    for key, expected in (
        ("accepted_archives", current_known["accepted_archives"]),
        ("physical_runs", current_known["physical_runs"]),
        ("eligible_runs", current_known["eligible_runs"]),
        ("eligible_endpoints", current_known["eligible_endpoints"]),
        ("accepted_tasks", current_known["eligible_tasks"]),
        ("unique_run_ids", current_known["physical_runs"]),
    ):
        require(mapping[key] == expected, f"mapped {key} mismatch")
    require(mapping["accepted_filename_task_mismatches"] == 0, "filename/task mismatch")

    anonymous_task = target_task(target["relative"])
    prior_support = dict(prior_by_task.get(anonymous_task, zero_metrics()))
    new_support = dict(new_by_task.get(anonymous_task, zero_metrics()))
    total_support = add_metrics(prior_support, new_support)
    status = choose_status(protocol, prior_support, total_support)
    run_share = total_support["eligible_runs"] / current_known["eligible_runs"]
    endpoint_share = total_support["eligible_endpoints"] / current_known["eligible_endpoints"]
    require(
        math.isfinite(run_share)
        and math.isfinite(endpoint_share)
        and 0 <= run_share <= 1
        and 0 <= endpoint_share <= 1,
        "support share invalid",
    )
    expected_result = {
        "protocol": AUDIT_PROTOCOL,
        "status": status,
        "input_bindings": {
            "protocol_sha256": digest(protocol_path),
            "prior_snapshot_sha256": inputs["prior_snapshot_sha256"],
            "current_snapshot_sha256": inputs["current_snapshot_sha256"],
            "current_observations_sha256": inputs["current_observations_sha256"],
            "prior_transactions_sha256": inputs["prior_transactions_sha256"],
            "current_transactions_sha256": inputs["current_transactions_sha256"],
            "target_rejection_registry_sha256": inputs["target_rejection_registry_sha256"],
            "prior_result_sha256": inputs["prior_archive_disposition_result_sha256"],
            "prior_verification_sha256": inputs["prior_archive_disposition_verification_sha256"],
        },
        "population": {
            **partition,
            "physical_runs": mapping["physical_runs"],
            "eligible_runs": mapping["eligible_runs"],
            "eligible_endpoints": mapping["eligible_endpoints"],
            "eligible_structural_pairs": current_known["eligible_structural_pairs"],
            "eligible_tasks": mapping["accepted_tasks"],
            "transaction_lines": len(current_rows),
            "prior_transaction_prefix_lines": len(prior_rows),
        },
        "target_event": {
            "target_rejection_count": 1,
            "rejection_reason": target["row"]["rejection_reason_code"],
            "competition_identity_emitted": False,
            "archive_identity_emitted": False,
            "payload_hash_emitted": False,
            "payload_hash_disjoint_from_accepted": True,
        },
        "anonymized_target_support": {
            "prior_prefix": prior_support,
            "new_window": new_support,
            "current_total": total_support,
            "eligible_run_share_of_current_corpus": run_share,
            "eligible_endpoint_share_of_current_corpus": endpoint_share,
        },
        "mapping_audit": mapping,
        "decision": {
            "strong_preexisting_support": status == protocol["decision_rule"]["strong"]["status"],
            "contemporaneous_only_support": status == protocol["decision_rule"]["partial"]["status"],
            "support_absent": status == protocol["decision_rule"]["absent"]["status"],
            "single_event_scope": True,
            "identities_emitted": False,
        },
        "integrity": {
            "current_transactions_have_exact_prior_byte_prefix": True,
            "observation_partition_reproduced": True,
            "target_registry_selected_exactly_one_rejection": True,
            "target_payload_disjoint_from_accepted": True,
            "accepted_transactions_match_observations": True,
            "accepted_archives_single_task_hash_bound": True,
            "accepted_run_ids_unique": True,
            "current_inventory_reproduced": True,
            "prior_result_and_verification_hash_bound": True,
        },
        "access_attestation": {
            "observation_and_hash_bound_intake_metadata_only": True,
            "target_registry_contents_opened": False,
            "archive_payloads_opened": False,
            "labels_grades_outcomes_predictions_accuracy_or_utility_read": False,
            "candidate_identities_or_profiles_read": False,
            "archive_task_run_or_candidate_identity_values_emitted": False,
            "randomness_used": False,
            "gpu_paid_api_model_fit_base_update": "0/0/0/0",
        },
        "claim_boundary": {
            "single_event_confirmation_only": True,
            "population_level_replication": False,
            "supports_task_whitelist_or_blacklist": False,
            "estimates_predictor_accuracy_scaling_search_utility_or_method_effect": False,
        },
    }
    result = object_from(result_path, "candidate result")
    require(result == expected_result, "candidate result differs from independent reconstruction")
    return {
        "protocol": VERIFIER_PROTOCOL,
        "status": VERIFIER_STATUS,
        "result_sha256": digest(result_path),
        "result_status": status,
        "recomputed_anonymized_support": {
            "prior_prefix": prior_support,
            "new_window": new_support,
            "current_total": total_support,
        },
        "all_result_fields_equal": True,
        "identities_emitted": False,
        "outcomes_predictions_labels_read": False,
        "randomness_used": False,
        "gpu_paid_api_model_fit_base_update": "0/0/0/0",
    }


def write_new(path: Path, value: dict[str, Any]) -> None:
    require(not path.exists(), "verification output already exists")
    require(path.parent.is_dir() and not path.parent.is_symlink(), "unsafe verification output parent")
    temporary = path.with_name(path.name + f".tmp-{os.getpid()}")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
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
        receipt = verify(args.protocol, args.observations, args.result, args.state_root)
        write_new(args.output.resolve(), receipt)
    except (IndependentVerificationError, OSError, TypeError, ZeroDivisionError) as exc:
        print(f"INCREMENTAL_ARCHIVE_SUPPORT_VERIFY_ERROR: {exc}", file=sys.stderr)
        return 2
    print(receipt["status"])
    print("IDENTITIES_EMITTED=false")
    print("LABEL_OUTCOME_PREDICTION_ACCURACY_UTILITY_READ=false/false/false/false/false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
