#!/usr/bin/env python3
"""Outcome-blind event-level audit of support behind one new archive rejection."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath
from typing import Any


PROTOCOL_NAME = "incremental_archive_rejection_support_audit_v1"
OBSERVATION_PROTOCOL = "prospective_archive_observer_v1"
PRIOR_STATUS = "LONGITUDINAL_ARCHIVE_LEVEL_GATE_REPLICATED"
PRIOR_VERIFY_STATUS = "INDEPENDENT_ARCHIVE_DISPOSITION_REPLICATION_PASS"
ALIAS_REASON = "ARCHIVE_BYTES_DUPLICATE_COMMITTED_TRANSACTION"
STRUCTURAL_REASONS = {
    "ARCHIVE_HAS_NO_CHECKPOINT_JOURNALS",
    "JOURNAL_TASK_IDENTITY_ABSENT_ALL_CHECKPOINTS",
    "JOURNAL_TASK_IDENTITY_NOT_EXACTLY_ONE_WITHIN_ARCHIVE",
}
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
ZERO = {
    "accepted_archives": 0,
    "physical_runs": 0,
    "eligible_runs": 0,
    "eligible_endpoints": 0,
}


class IncrementalArchiveAuditError(RuntimeError):
    pass


def check(condition: bool, message: str) -> None:
    if not condition:
        raise IncrementalArchiveAuditError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def read_object(path: Path, label: str) -> dict[str, Any]:
    check(path.is_file() and not path.is_symlink(), f"{label} is absent or unsafe")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise IncrementalArchiveAuditError(f"cannot parse {label}") from exc
    check(isinstance(value, dict), f"{label} is not an object")
    return value


def read_list(path: Path, label: str) -> list[Any]:
    check(path.is_file() and not path.is_symlink(), f"{label} is absent or unsafe")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise IncrementalArchiveAuditError(f"cannot parse {label}") from exc
    check(isinstance(value, list), f"{label} is not a list")
    return value


def read_jsonl_bytes(data: bytes, label: str) -> list[dict[str, Any]]:
    try:
        lines = data.decode("utf-8").splitlines()
        rows = [json.loads(line) for line in lines if line]
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise IncrementalArchiveAuditError(f"cannot parse {label}") from exc
    check(rows and all(isinstance(row, dict) for row in rows), f"{label} is empty or malformed")
    return rows


def nonnegative_int(value: Any, label: str) -> int:
    check(isinstance(value, int) and not isinstance(value, bool) and value >= 0, f"invalid {label}")
    return value


def require_sha(value: Any, label: str) -> str:
    check(isinstance(value, str) and SHA_RX.fullmatch(value) is not None, f"invalid {label}")
    return value


def archive_parts(value: Any) -> tuple[str, str]:
    check(isinstance(value, str), "archive path is not a string")
    path = PurePosixPath(value)
    check(
        not path.is_absolute()
        and len(path.parts) == 2
        and all(part not in {"", ".", ".."} for part in path.parts),
        "archive path is malformed",
    )
    directory, basename = path.parts
    check(basename.endswith(".tar.gz"), "archive suffix is malformed")
    return directory, basename


def normalize_task(value: Any) -> str:
    check(isinstance(value, str), "task metadata is not a string")
    normalized = NON_ASCII_ALNUM.sub("-", value.casefold()).strip("-")
    check(bool(normalized), "task metadata normalizes to empty")
    return normalized


def task_from_seeded_archive(value: Any) -> str:
    _directory, basename = archive_parts(value)
    match = SEEDED_ARCHIVE_RX.fullmatch(basename)
    check(match is not None, "target rejected archive lacks a seeded filename")
    return normalize_task(match.group("competition"))


def bound_repo_file(
    protocol_path: Path, inputs: dict[str, Any], path_key: str, hash_key: str, label: str
) -> Path:
    relative = inputs.get(path_key)
    check(isinstance(relative, str) and bool(relative), f"{label} path missing")
    root = protocol_path.resolve().parent
    unresolved = root / relative
    check(not unresolved.is_symlink(), f"{label} path is symlinked")
    path = unresolved.resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise IncrementalArchiveAuditError(f"{label} path escapes protocol root") from exc
    check(path.is_file(), f"{label} path is absent")
    check(sha256(path) == require_sha(inputs.get(hash_key), f"{label} hash"), f"{label} hash mismatch")
    return path


def validate_protocol(protocol: dict[str, Any]) -> None:
    check(protocol.get("protocol") == PROTOCOL_NAME, "protocol identity mismatch")
    check(
        protocol.get("frozen_before_target_competition_or_support_readout") is True,
        "protocol is not result-before frozen",
    )
    unknown = protocol.get("unknown_at_freeze")
    check(
        isinstance(unknown, dict) and unknown and all(value is False for value in unknown.values()),
        "unknown-at-freeze disclosure mismatch",
    )
    selector = protocol.get("target_selection")
    check(
        isinstance(selector, dict)
        and selector.get("required_count") == 1
        and selector.get("caller_may_choose_archive_or_competition") is False
        and selector.get("registry_contents_required_for_selection") is False
        and selector.get("registry_file_hash_only") is True,
        "target selector mismatch",
    )
    access = protocol.get("access_contract")
    check(
        access
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


def validate_prior_evidence(protocol: dict[str, Any], protocol_path: Path) -> None:
    inputs = protocol["inputs"]
    result_path = bound_repo_file(
        protocol_path,
        inputs,
        "prior_archive_disposition_result_path",
        "prior_archive_disposition_result_sha256",
        "prior result",
    )
    verification_path = bound_repo_file(
        protocol_path,
        inputs,
        "prior_archive_disposition_verification_path",
        "prior_archive_disposition_verification_sha256",
        "prior verification",
    )
    target_registry = bound_repo_file(
        protocol_path,
        inputs,
        "target_rejection_registry_path",
        "target_rejection_registry_sha256",
        "target registry",
    )
    check(target_registry.stat().st_size > 0, "target registry is empty")
    result = read_object(result_path, "prior result")
    verification = read_object(verification_path, "prior verification")
    prior = protocol["known_before_readout"]["prior"]
    current = result.get("current")
    check(result.get("status") == PRIOR_STATUS and isinstance(current, dict), "prior result status mismatch")
    check(
        result.get("input_bindings", {}).get("current_latest_snapshot_sha256")
        == inputs["prior_snapshot_sha256"],
        "prior result snapshot mismatch",
    )
    for key in (
        "observed_archives",
        "accepted_archives",
        "structural_rejected_archives",
        "alias_quarantined_archives",
        "pending_archives",
    ):
        check(current.get(key) == prior[key], f"prior result {key} mismatch")
    check(
        verification.get("status") == PRIOR_VERIFY_STATUS
        and verification.get("result_sha256") == inputs["prior_archive_disposition_result_sha256"]
        and verification.get("identities_emitted") is False
        and verification.get("outcomes_predictions_labels_read") is False,
        "prior independent verification mismatch",
    )


def snapshot_transactions(
    state_root: Path, snapshot_sha: str, expected_transaction_sha: str, expected_lines: int
) -> tuple[Path, bytes, list[dict[str, Any]]]:
    snapshot = state_root / "snapshots" / snapshot_sha
    check(snapshot.is_dir() and not snapshot.is_symlink(), "snapshot root is absent or unsafe")
    manifest = snapshot / "SHA256SUMS"
    check(manifest.is_file() and not manifest.is_symlink(), "snapshot manifest is absent or unsafe")
    check(sha256(manifest) == snapshot_sha, "snapshot manifest identity mismatch")
    manifest_entries: dict[str, str] = {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        check(match is not None, "snapshot manifest row malformed")
        relative = match.group(2)
        pure = PurePosixPath(relative)
        check(
            not pure.is_absolute()
            and all(part not in {"", ".", ".."} for part in pure.parts)
            and relative not in manifest_entries,
            "snapshot manifest path malformed or duplicated",
        )
        manifest_entries[relative] = match.group(1)
    transaction_path = snapshot / "transactions.jsonl"
    check(
        manifest_entries.get("transactions.jsonl") == expected_transaction_sha
        and transaction_path.is_file()
        and not transaction_path.is_symlink(),
        "transaction registry manifest binding mismatch",
    )
    data = transaction_path.read_bytes()
    check(hashlib.sha256(data).hexdigest() == expected_transaction_sha, "transaction registry hash mismatch")
    rows = read_jsonl_bytes(data, "transaction registry")
    check(len(rows) == expected_lines, "transaction registry line count mismatch")
    return snapshot, data, rows


def classify_observations(
    protocol: dict[str, Any], observations: dict[str, Any]
) -> tuple[dict[str, str], dict[str, Any], dict[str, Any]]:
    check(
        set(observations)
        == {"baseline_sealed_at_epoch", "entries", "protocol", "source_root"}
        and observations.get("protocol") == OBSERVATION_PROTOCOL,
        "observations schema mismatch",
    )
    baseline_sealed = observations.get("baseline_sealed_at_epoch")
    check(
        isinstance(baseline_sealed, (int, float))
        and not isinstance(baseline_sealed, bool)
        and math.isfinite(float(baseline_sealed))
        and baseline_sealed >= 0,
        "baseline seal timestamp malformed",
    )
    entries = observations.get("entries")
    check(isinstance(entries, dict), "observations entries missing")
    source_root = observations.get("source_root")
    check(isinstance(source_root, str) and bool(source_root), "observations source root missing")
    path_prefix = source_root.rstrip("/") + "/"
    accepted: dict[str, str] = {}
    target_rows: list[dict[str, Any]] = []
    reason_counts: Counter[str] = Counter()
    counts = Counter()
    target_registry = protocol["inputs"]["target_rejection_registry_sha256"]
    for relative, row in entries.items():
        check(isinstance(row, dict) and set(row) == ENTRY_KEYS, "observation row schema mismatch")
        archive_parts(relative)
        check(
            row.get("path") == path_prefix + relative and row.get("present") is True,
            "observation path/presence mismatch",
        )
        check(nonnegative_int(row.get("stable_observations"), "stable observations") > 0, "unstable observation")
        nonnegative_int(row.get("size"), "archive size")
        nonnegative_int(row.get("mtime_ns"), "archive mtime")
        baseline = row.get("baseline")
        check(isinstance(baseline, bool), "baseline flag malformed")
        committed = row.get("committed_archive_sha256")
        committed_snapshot = row.get("committed_snapshot_sha256")
        rejected = row.get("rejected_archive_sha256")
        rejection_registry = row.get("rejection_registry_sha256")
        reason = row.get("rejection_reason_code")
        has_acceptance = committed is not None or committed_snapshot is not None
        has_rejection = rejected is not None or rejection_registry is not None or reason is not None
        check(sum((baseline, has_acceptance, has_rejection)) == 1, "observation disposition mismatch")
        if baseline:
            counts["baseline"] += 1
            continue
        if has_acceptance:
            archive_sha = require_sha(committed, "accepted archive hash")
            require_sha(committed_snapshot, "accepted snapshot hash")
            check(archive_sha not in accepted, "duplicate accepted archive hash")
            accepted[archive_sha] = relative
            counts["accepted"] += 1
        else:
            require_sha(rejected, "rejected archive hash")
            check(reason in STRUCTURAL_REASONS | {ALIAS_REASON}, "unknown rejection reason")
            require_sha(rejection_registry, "rejection registry hash")
            reason_counts[str(reason)] += 1
            counts["alias" if reason == ALIAS_REASON else "structural"] += 1
            if rejection_registry == target_registry:
                target_rows.append({"relative": relative, "row": row})
    known = protocol["known_before_readout"]["current"]
    check(len(entries) == known["observed_archives"], "observed archive count mismatch")
    check(counts["baseline"] == known["baseline_archives"], "baseline count mismatch")
    check(counts["accepted"] == known["accepted_archives"], "accepted count mismatch")
    check(counts["structural"] == known["structural_rejected_archives"], "structural count mismatch")
    check(counts["alias"] == known["alias_quarantined_archives"], "alias count mismatch")
    check(dict(sorted(reason_counts.items())) == known["rejection_reason_counts"], "rejection reason counts mismatch")
    check(len(target_rows) == 1, "target registry does not select exactly one observation")
    target = target_rows[0]
    check(
        target["row"]["rejection_reason_code"]
        == protocol["target_selection"]["required_rejection_reason"],
        "target rejection reason mismatch",
    )
    check(target["row"]["rejected_archive_sha256"] not in accepted, "target payload overlaps accepted payload")
    partition = {
        "observed_archives": len(entries),
        "baseline_archives": counts["baseline"],
        "accepted_archives": counts["accepted"],
        "structural_rejected_archives": counts["structural"],
        "alias_quarantined_archives": counts["alias"],
        "pending_archives": 0,
        "rejection_reason_counts": dict(sorted(reason_counts.items())),
    }
    return accepted, target, partition


def validate_transaction(row: dict[str, Any]) -> str:
    check(set(row) == TRANSACTION_KEYS, "transaction schema mismatch")
    archive_sha = require_sha(row.get("archive_sha256"), "transaction archive hash")
    nonnegative_int(row.get("archive_size"), "transaction archive size")
    for key in ("archive_relative_path", "committed_at_utc", "drop_id", "intake_dir", "score_dir"):
        check(isinstance(row.get(key), str) and bool(row[key]), "transaction string field malformed")
    archive_parts(row["archive_relative_path"])
    require_sha(row.get("intake_summary_sha256"), "intake summary hash")
    require_sha(row.get("score_summary_sha256"), "score summary hash")
    return archive_sha


def add_metric(metric: dict[str, int], key: str, value: int = 1) -> None:
    metric[key] += value


def support_by_task(
    state_root: Path,
    transactions: list[dict[str, Any]],
    accepted: dict[str, str],
    prior_lines: int,
) -> tuple[dict[str, dict[str, int]], dict[str, dict[str, int]], dict[str, Any]]:
    by_archive: dict[str, tuple[int, dict[str, Any]]] = {}
    for index, row in enumerate(transactions):
        archive_sha = validate_transaction(row)
        check(archive_sha not in by_archive, "duplicate transaction archive hash")
        by_archive[archive_sha] = (index, row)
    check(set(by_archive) == set(accepted), "accepted observations and transactions differ")

    prior_metrics: dict[str, dict[str, int]] = defaultdict(lambda: dict(ZERO))
    new_metrics: dict[str, dict[str, int]] = defaultdict(lambda: dict(ZERO))
    seen_run_ids: set[str] = set()
    provenance_rows = 0
    seeded = 0
    fallbacks = 0
    mismatches = 0
    for archive_sha, relative in sorted(accepted.items()):
        index, transaction = by_archive[archive_sha]
        check(transaction["archive_relative_path"] == relative, "transaction archive path mismatch")
        intake = Path(transaction["intake_dir"])
        check(
            intake.is_dir()
            and not intake.is_symlink()
            and intake.resolve().parent == state_root / "intakes"
            and intake.resolve().name == transaction["drop_id"],
            "transaction intake binding mismatch",
        )
        intake = intake.resolve()
        summary_path = intake / "summary.json"
        check(summary_path.is_file() and not summary_path.is_symlink(), "intake summary is unsafe")
        check(sha256(summary_path) == transaction["intake_summary_sha256"], "intake summary hash mismatch")
        summary = read_object(summary_path, "intake summary")
        outputs = summary.get("outputs")
        security = summary.get("security")
        blindness = summary.get("blindness")
        check(
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
        check(
            provenance_path.is_file() and not provenance_path.is_symlink(),
            "source provenance is unsafe",
        )
        check(
            sha256(provenance_path) == require_sha(outputs.get("source_provenance_sha256"), "provenance hash"),
            "source provenance hash mismatch",
        )
        provenance = read_list(provenance_path, "source provenance")
        tasks: set[str] = set()
        _directory, basename = archive_parts(relative)
        target_metrics = prior_metrics if index < prior_lines else new_metrics
        for provenance_row in provenance:
            check(
                isinstance(provenance_row, dict)
                and PROVENANCE_REQUIRED_KEYS <= set(provenance_row) <= PROVENANCE_REQUIRED_KEYS | PROVENANCE_OPTIONAL_KEYS,
                "source provenance schema mismatch",
            )
            check(
                provenance_row.get("archive_sha256") == archive_sha
                and provenance_row.get("archive_name") == basename,
                "source provenance archive binding mismatch",
            )
            task = normalize_task(provenance_row.get("task"))
            tasks.add(task)
            run_id = provenance_row.get("run_id")
            check(isinstance(run_id, str) and bool(run_id) and run_id not in seen_run_ids, "duplicate run identity")
            seen_run_ids.add(run_id)
            eligible = provenance_row.get("eligible")
            check(isinstance(eligible, bool), "eligible flag malformed")
            endpoints = nonnegative_int(provenance_row.get("endpoints"), "provenance endpoints")
            add_metric(target_metrics[task], "physical_runs")
            if eligible:
                add_metric(target_metrics[task], "eligible_runs")
                add_metric(target_metrics[task], "eligible_endpoints", endpoints)
            provenance_rows += 1
        check(len(tasks) == 1, "accepted archive is not single-task")
        task = next(iter(tasks))
        add_metric(target_metrics[task], "accepted_archives")
        match = SEEDED_ARCHIVE_RX.fullmatch(basename)
        if match is None:
            fallbacks += 1
        else:
            seeded += 1
            mismatches += normalize_task(match.group("competition")) != task

    all_tasks = set(prior_metrics) | set(new_metrics)
    totals = dict(ZERO)
    for task in all_tasks:
        for key in ZERO:
            totals[key] += prior_metrics[task][key] + new_metrics[task][key]
    mapping = {
        "accepted_single_task_archives": totals["accepted_archives"],
        "accepted_seeded_filename_archives": seeded,
        "accepted_task_metadata_fallback_archives": fallbacks,
        "accepted_filename_task_mismatches": mismatches,
        "hash_bound_source_provenance_rows": provenance_rows,
        "unique_run_ids": len(seen_run_ids),
        "accepted_tasks": len(all_tasks),
        **totals,
    }
    return prior_metrics, new_metrics, mapping


def merged_metric(left: dict[str, int], right: dict[str, int]) -> dict[str, int]:
    return {key: left[key] + right[key] for key in ZERO}


def decide(protocol: dict[str, Any], prior: dict[str, int], current: dict[str, int]) -> str:
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


def build_result(protocol_path: Path, observations_path: Path, state_root: Path) -> dict[str, Any]:
    check(protocol_path.is_file() and not protocol_path.is_symlink(), "protocol path is absent or unsafe")
    check(
        observations_path.is_file() and not observations_path.is_symlink(),
        "observations path is absent or unsafe",
    )
    check(state_root.is_dir() and not state_root.is_symlink(), "state root is absent or unsafe")
    protocol_path = protocol_path.resolve()
    observations_path = observations_path.resolve()
    state_root = state_root.resolve()
    protocol = read_object(protocol_path, "protocol")
    validate_protocol(protocol)
    validate_prior_evidence(protocol, protocol_path)
    inputs = protocol["inputs"]
    latest_path = state_root / "LATEST"
    check(latest_path.is_file() and not latest_path.is_symlink(), "LATEST is absent or unsafe")
    check(latest_path.read_text(encoding="ascii").strip() == inputs["current_snapshot_sha256"], "LATEST mismatch")
    check(
        sha256(observations_path) == inputs["current_observations_sha256"]
        and observations_path.stat().st_size == inputs["current_observations_bytes"],
        "observations binding mismatch",
    )
    observations = read_object(observations_path, "observations")
    accepted, target, partition = classify_observations(protocol, observations)

    prior_snapshot, prior_bytes, prior_transactions = snapshot_transactions(
        state_root,
        inputs["prior_snapshot_sha256"],
        inputs["prior_transactions_sha256"],
        inputs["prior_transaction_lines"],
    )
    current_snapshot, current_bytes, current_transactions = snapshot_transactions(
        state_root,
        inputs["current_snapshot_sha256"],
        inputs["current_transactions_sha256"],
        inputs["current_transaction_lines"],
    )
    check(current_bytes.startswith(prior_bytes), "current transactions lack exact prior byte prefix")
    check(
        len(current_transactions) - len(prior_transactions)
        == protocol["known_before_readout"]["increment"]["accepted_archives"],
        "accepted transaction increment mismatch",
    )
    check(prior_snapshot != current_snapshot, "prior and current snapshots collapse")

    summary = read_object(current_snapshot / "accumulator" / "summary.json", "current accumulator summary")
    inventory = summary.get("inventory")
    known_current = protocol["known_before_readout"]["current"]
    check(isinstance(inventory, dict), "current inventory missing")
    expected_inventory = {
        "all_physical_runs": known_current["physical_runs"],
        "eligible_runs": known_current["eligible_runs"],
        "eligible_endpoints": known_current["eligible_endpoints"],
        "eligible_structural_pairs": known_current["eligible_structural_pairs"],
        "eligible_tasks": known_current["eligible_tasks"],
    }
    check(all(inventory.get(key) == value for key, value in expected_inventory.items()), "current inventory mismatch")

    prior_metrics, new_metrics, mapping = support_by_task(
        state_root, current_transactions, accepted, inputs["prior_transaction_lines"]
    )
    check(mapping["accepted_archives"] == known_current["accepted_archives"], "mapped archive total mismatch")
    check(mapping["physical_runs"] == known_current["physical_runs"], "mapped physical-run total mismatch")
    check(mapping["eligible_runs"] == known_current["eligible_runs"], "mapped eligible-run total mismatch")
    check(mapping["eligible_endpoints"] == known_current["eligible_endpoints"], "mapped endpoint total mismatch")
    check(mapping["accepted_tasks"] == known_current["eligible_tasks"], "mapped task total mismatch")
    check(mapping["unique_run_ids"] == known_current["physical_runs"], "run identity total mismatch")
    check(mapping["accepted_filename_task_mismatches"] == 0, "accepted filename/task mismatch")

    target_task = task_from_seeded_archive(target["relative"])
    prior_support = dict(prior_metrics.get(target_task, ZERO))
    new_support = dict(new_metrics.get(target_task, ZERO))
    current_support = merged_metric(prior_support, new_support)
    status = decide(protocol, prior_support, current_support)
    eligible_runs = known_current["eligible_runs"]
    eligible_endpoints = known_current["eligible_endpoints"]
    shares = {
        "eligible_run_share_of_current_corpus": current_support["eligible_runs"] / eligible_runs,
        "eligible_endpoint_share_of_current_corpus": current_support["eligible_endpoints"] / eligible_endpoints,
    }
    check(all(math.isfinite(value) and 0 <= value <= 1 for value in shares.values()), "support share invalid")

    return {
        "protocol": PROTOCOL_NAME,
        "status": status,
        "input_bindings": {
            "protocol_sha256": sha256(protocol_path),
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
            "eligible_structural_pairs": known_current["eligible_structural_pairs"],
            "eligible_tasks": mapping["accepted_tasks"],
            "transaction_lines": len(current_transactions),
            "prior_transaction_prefix_lines": len(prior_transactions),
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
            "current_total": current_support,
            **shares,
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--observations", required=True, type=Path)
    parser.add_argument("--state-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = build_result(args.protocol, args.observations, args.state_root)
        check(not args.output.exists(), "output already exists")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(canonical_json(result))
    except (IncrementalArchiveAuditError, OSError) as exc:
        print(f"INCREMENTAL_ARCHIVE_SUPPORT_INTEGRITY_FAIL: {exc}", file=sys.stderr)
        return 2
    print(result["status"])
    print("TARGET_COMPETITION_IDENTITY_EMITTED=false")
    print("LABEL_OUTCOME_PREDICTION_ACCURACY_UTILITY_READ=false/false/false/false/false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
