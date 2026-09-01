#!/usr/bin/env python3
"""Independently rebuild the identity-erased archive-rejection support census."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from phase1.verify_incremental_archive_rejection_support import (
    ALIAS,
    OBSERVATION_FIELDS,
    STRUCTURAL,
    IndependentVerificationError,
    archive_path,
    canonical_task,
    digest,
    integer,
    object_from,
    read_snapshot_transactions,
    reconstruct_support,
    require,
    sha,
    target_task,
    zero_metrics,
)


PROTOCOL = "archive_rejection_support_census_v1"
RESULT_STATUS = "ARCHIVE_REJECTION_SUPPORT_CENSUS_COMPLETE_PARTIALLY_PREDISCLOSED"
VERIFIER_STATUS = "INDEPENDENT_ARCHIVE_REJECTION_SUPPORT_CENSUS_PASS"
PRIOR_SUPPORT = "PRIOR_ANCHOR_ELIGIBLE_SUPPORT"
WINDOW_SUPPORT = "CURRENT_WINDOW_ELIGIBLE_SUPPORT"
ARCHIVE_ONLY = "ACCEPTED_ARCHIVE_ONLY_NO_ELIGIBLE_SUPPORT"
NO_SUPPORT = "NO_ACCEPTED_ARCHIVE_SUPPORT"
CLASSES = (PRIOR_SUPPORT, WINDOW_SUPPORT, ARCHIVE_ONLY, NO_SUPPORT)
OBSERVER_PROTOCOL = "prospective_archive_observer_v1"


class CensusVerificationError(RuntimeError):
    pass


def verify_check(condition: bool, message: str) -> None:
    if not condition:
        raise CensusVerificationError(message)


def canonical(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def validate_protocol(protocol: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    verify_check(protocol.get("protocol") == PROTOCOL, "protocol mismatch")
    verify_check(
        protocol.get("frozen_before_full_census_support_readout") is True,
        "protocol is not frozen",
    )
    unknown = protocol.get("unknown_at_freeze")
    verify_check(
        isinstance(unknown, dict) and unknown and set(unknown.values()) == {False},
        "unknown disclosure mismatch",
    )
    rows = protocol.get("support_classes_in_precedence_order")
    verify_check(
        isinstance(rows, list)
        and tuple(row.get("class") for row in rows if isinstance(row, dict)) == CLASSES,
        "class precedence mismatch",
    )
    verify_check(
        protocol.get("estimand", {}).get("full_census_not_sampling_inference") is True
        and protocol.get("estimand", {}).get("no_binary_success_threshold") is True,
        "estimand mismatch",
    )
    verify_check(
        protocol.get("access_contract")
        == {
            "observation_and_hash_bound_intake_metadata_only": True,
            "rejection_registry_contents_opened": False,
            "archive_payloads_opened": False,
            "labels_grades_outcomes_predictions_accuracy_or_utility_read": False,
            "candidate_identities_or_profiles_read": False,
            "identity_values_emitted": False,
            "gpu_paid_api_model_fit_base_update": "0/0/0/0",
        },
        "access contract mismatch",
    )
    inputs = protocol.get("inputs")
    known = protocol.get("known_before_readout")
    verify_check(isinstance(inputs, dict) and isinstance(known, dict), "protocol inputs missing")
    return inputs, known


def bind_evidence(protocol_path: Path, inputs: dict[str, Any]) -> None:
    root = protocol_path.parent
    for path_key, hash_key in (
        ("legacy_twelve_event_ledger_path", "legacy_twelve_event_ledger_sha256"),
        ("legacy_twelve_event_verification_path", "legacy_twelve_event_verification_sha256"),
        ("latest_single_event_result_path", "latest_single_event_result_sha256"),
        ("latest_single_event_verification_path", "latest_single_event_verification_sha256"),
    ):
        relative = inputs.get(path_key)
        verify_check(isinstance(relative, str) and bool(relative), f"missing {path_key}")
        unresolved = root / relative
        verify_check(not unresolved.is_symlink(), f"symlinked {path_key}")
        path = unresolved.resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise CensusVerificationError(f"escaping {path_key}") from exc
        verify_check(path.is_file(), f"absent {path_key}")
        verify_check(digest(path) == sha(inputs.get(hash_key), hash_key), f"hash mismatch: {path_key}")


def partition_observations(
    protocol: dict[str, Any], observations: dict[str, Any]
) -> tuple[dict[str, str], list[dict[str, str]], dict[str, Any]]:
    verify_check(
        set(observations)
        == {"baseline_sealed_at_epoch", "entries", "protocol", "source_root"}
        and observations.get("protocol") == OBSERVER_PROTOCOL,
        "observation container mismatch",
    )
    seal = observations.get("baseline_sealed_at_epoch")
    verify_check(
        isinstance(seal, (int, float))
        and not isinstance(seal, bool)
        and math.isfinite(float(seal))
        and seal >= 0,
        "baseline seal mismatch",
    )
    entries = observations.get("entries")
    source_root = observations.get("source_root")
    verify_check(isinstance(entries, dict), "entries missing")
    verify_check(isinstance(source_root, str) and bool(source_root), "source root missing")
    prefix = source_root.rstrip("/") + "/"
    accepted: dict[str, str] = {}
    targets: list[dict[str, str]] = []
    counts: Counter[str] = Counter()
    reasons: Counter[str] = Counter()
    for relative, row in entries.items():
        archive_path(relative)
        verify_check(isinstance(row, dict) and set(row) == OBSERVATION_FIELDS, "row schema mismatch")
        verify_check(row.get("path") == prefix + relative and row.get("present") is True, "row path mismatch")
        verify_check(integer(row.get("stable_observations"), "stable observations") > 0, "unstable row")
        integer(row.get("size"), "archive size")
        integer(row.get("mtime_ns"), "archive mtime")
        baseline = row.get("baseline")
        verify_check(isinstance(baseline, bool), "baseline flag mismatch")
        committed = row.get("committed_archive_sha256")
        committed_snapshot = row.get("committed_snapshot_sha256")
        rejected = row.get("rejected_archive_sha256")
        registry = row.get("rejection_registry_sha256")
        reason = row.get("rejection_reason_code")
        accepted_state = committed is not None or committed_snapshot is not None
        rejected_state = rejected is not None or registry is not None or reason is not None
        verify_check(sum((baseline, accepted_state, rejected_state)) == 1, "disposition mismatch")
        if baseline:
            counts["baseline"] += 1
        elif accepted_state:
            archive_sha = sha(committed, "accepted hash")
            sha(committed_snapshot, "accepted snapshot hash")
            verify_check(archive_sha not in accepted, "duplicate accepted hash")
            accepted[archive_sha] = relative
            counts["accepted"] += 1
        else:
            payload_sha = sha(rejected, "rejected hash")
            sha(registry, "registry hash")
            verify_check(reason in STRUCTURAL | {ALIAS}, "unknown rejection reason")
            reasons[str(reason)] += 1
            if reason == ALIAS:
                counts["alias"] += 1
            else:
                counts["structural"] += 1
                targets.append({"relative": relative, "reason": str(reason), "payload_sha256": payload_sha})
    known = protocol["known_before_readout"]["population"]
    verify_check(len(entries) == known["observed_archives"], "observed count mismatch")
    verify_check(counts["baseline"] == known["baseline_archives"], "baseline count mismatch")
    verify_check(counts["accepted"] == known["accepted_archives"], "accepted count mismatch")
    verify_check(counts["structural"] == known["structural_rejected_archives"], "structural count mismatch")
    verify_check(counts["alias"] == known["alias_quarantined_archives"], "alias count mismatch")
    verify_check(dict(sorted(reasons.items())) == known["rejection_reason_counts"], "reason counts mismatch")
    verify_check(len(targets) == 14, "census target count mismatch")
    verify_check(not ({row["payload_sha256"] for row in targets} & set(accepted)), "payload overlap")
    return accepted, targets, {
        "observed_archives": len(entries),
        "baseline_archives": counts["baseline"],
        "accepted_archives": counts["accepted"],
        "structural_rejected_archives": counts["structural"],
        "alias_quarantined_archives": counts["alias"],
        "pending_archives": 0,
        "rejection_reason_counts": dict(sorted(reasons.items())),
    }


def classify(prior: dict[str, int], current: dict[str, int]) -> str:
    if (
        prior["accepted_archives"] >= 1
        and prior["eligible_runs"] >= 1
        and prior["eligible_endpoints"] >= 1
    ):
        return PRIOR_SUPPORT
    if (
        current["accepted_archives"] >= 1
        and current["eligible_runs"] >= 1
        and current["eligible_endpoints"] >= 1
    ):
        return WINDOW_SUPPORT
    if current["accepted_archives"] >= 1:
        return ARCHIVE_ONLY
    return NO_SUPPORT


def merge(left: dict[str, int], right: dict[str, int]) -> dict[str, int]:
    return {key: left[key] + right[key] for key in zero_metrics()}


def accumulate(total: dict[str, int], values: dict[str, int]) -> None:
    for key in total:
        total[key] += values[key]


def expected_result(
    protocol_path: Path,
    observations_path: Path,
    state: Path,
) -> dict[str, Any]:
    protocol = object_from(protocol_path, "protocol")
    inputs, known_all = validate_protocol(protocol)
    bind_evidence(protocol_path, inputs)
    latest = state / "LATEST"
    verify_check(latest.is_file() and not latest.is_symlink(), "unsafe LATEST")
    verify_check(latest.read_text(encoding="ascii").strip() == inputs["current_snapshot_sha256"], "LATEST mismatch")
    verify_check(digest(observations_path) == inputs["current_observations_sha256"], "observations hash mismatch")
    verify_check(observations_path.stat().st_size == inputs["current_observations_bytes"], "observations size mismatch")
    accepted, targets, partition = partition_observations(
        protocol, object_from(observations_path, "observations")
    )
    prior_snapshot, prior_raw, prior_rows = read_snapshot_transactions(
        state,
        inputs["prior_snapshot_sha256"],
        inputs["prior_transactions_sha256"],
        inputs["prior_transaction_lines"],
    )
    current_snapshot, current_raw, current_rows = read_snapshot_transactions(
        state,
        inputs["current_snapshot_sha256"],
        inputs["current_transactions_sha256"],
        inputs["current_transaction_lines"],
    )
    verify_check(prior_snapshot != current_snapshot, "snapshot anchors collapse")
    verify_check(current_raw.startswith(prior_raw), "prior prefix mismatch")
    window_lines = integer(
        inputs.get("current_window_transaction_lines"),
        "current-window transaction lines",
    )
    verify_check(window_lines > 0, "current-window transaction lines must be positive")
    verify_check(
        len(current_rows) - len(prior_rows) == window_lines,
        "window size mismatch",
    )
    summary = object_from(current_snapshot / "accumulator" / "summary.json", "summary")
    inventory = summary.get("inventory")
    known = known_all["population"]
    verify_check(isinstance(inventory, dict), "inventory missing")
    for source_key, known_key in (
        ("all_physical_runs", "physical_runs"),
        ("eligible_runs", "eligible_runs"),
        ("eligible_endpoints", "eligible_endpoints"),
        ("eligible_structural_pairs", "eligible_structural_pairs"),
        ("eligible_tasks", "eligible_tasks"),
    ):
        verify_check(inventory.get(source_key) == known[known_key], f"inventory mismatch: {source_key}")
    prior, window, mapping = reconstruct_support(
        state, current_rows, accepted, inputs["prior_transaction_lines"]
    )
    verify_check(mapping["accepted_archives"] == known["accepted_archives"], "archive mapping mismatch")
    verify_check(mapping["physical_runs"] == known["physical_runs"], "run mapping mismatch")
    verify_check(mapping["eligible_runs"] == known["eligible_runs"], "eligible-run mapping mismatch")
    verify_check(mapping["eligible_endpoints"] == known["eligible_endpoints"], "endpoint mapping mismatch")
    verify_check(mapping["accepted_tasks"] == known["eligible_tasks"], "task mapping mismatch")
    verify_check(mapping["accepted_filename_task_mismatches"] == 0, "task filename mismatch")

    event_counts: Counter[str] = Counter()
    reason_counts: dict[str, Counter[str]] = defaultdict(Counter)
    competition_classes: dict[str, str] = {}
    weighted_prior = zero_metrics()
    weighted_window = zero_metrics()
    weighted_current = zero_metrics()
    digest_rows: list[dict[str, Any]] = []
    for target in targets:
        task = target_task(target["relative"])
        prior_metric = dict(prior.get(task, zero_metrics()))
        window_metric = dict(window.get(task, zero_metrics()))
        current_metric = merge(prior_metric, window_metric)
        support_class = classify(prior_metric, current_metric)
        event_counts[support_class] += 1
        reason_counts[target["reason"]][support_class] += 1
        previous = competition_classes.setdefault(task, support_class)
        verify_check(previous == support_class, "competition class mismatch")
        accumulate(weighted_prior, prior_metric)
        accumulate(weighted_window, window_metric)
        accumulate(weighted_current, current_metric)
        digest_rows.append(
            {
                "reason": target["reason"],
                "class": support_class,
                "prior": prior_metric,
                "window": window_metric,
                "current": current_metric,
            }
        )
    verify_check(sum(event_counts.values()) == 14, "incomplete event classes")
    disclosure = known_all["partial_support_disclosure"]
    verify_check(event_counts[PRIOR_SUPPORT] >= disclosure["legacy_structural_rejection_events"], "legacy disclosure mismatch")
    verify_check(event_counts[NO_SUPPORT] >= 1, "absent-event disclosure mismatch")
    competition_counts = Counter(competition_classes.values())
    reason_table = {
        reason: {name: counts.get(name, 0) for name in CLASSES}
        for reason, counts in sorted(reason_counts.items())
    }
    classification_digest = hashlib.sha256(
        canonical(sorted(digest_rows, key=lambda row: canonical(row)))
    ).hexdigest()
    return {
        "protocol": PROTOCOL,
        "status": RESULT_STATUS,
        "input_bindings": {
            "protocol_sha256": digest(protocol_path),
            "prior_snapshot_sha256": inputs["prior_snapshot_sha256"],
            "current_snapshot_sha256": inputs["current_snapshot_sha256"],
            "current_observations_sha256": inputs["current_observations_sha256"],
            "prior_transactions_sha256": inputs["prior_transactions_sha256"],
            "current_transactions_sha256": inputs["current_transactions_sha256"],
            "legacy_ledger_sha256": inputs["legacy_twelve_event_ledger_sha256"],
            "legacy_verification_sha256": inputs["legacy_twelve_event_verification_sha256"],
            "latest_single_event_result_sha256": inputs["latest_single_event_result_sha256"],
            "latest_single_event_verification_sha256": inputs["latest_single_event_verification_sha256"],
        },
        "population": {
            **partition,
            "physical_runs": mapping["physical_runs"],
            "eligible_runs": mapping["eligible_runs"],
            "eligible_endpoints": mapping["eligible_endpoints"],
            "eligible_structural_pairs": known["eligible_structural_pairs"],
            "eligible_tasks": mapping["accepted_tasks"],
            "prior_transaction_prefix_lines": len(prior_rows),
            "current_transaction_lines": len(current_rows),
        },
        "event_support_class_counts": {name: event_counts.get(name, 0) for name in CLASSES},
        "competition_support_class_counts": {
            "distinct_rejected_competitions": len(competition_classes),
            **{name: competition_counts.get(name, 0) for name in CLASSES},
        },
        "reason_by_event_support_class": reason_table,
        "event_weighted_support_quantity_aggregates": {
            "prior_prefix": weighted_prior,
            "current_window": weighted_window,
            "current_total": weighted_current,
            "repeated_competitions_are_repeated_per_event": True,
        },
        "classification_digest": classification_digest,
        "mapping_audit": mapping,
        "integrity": {
            "current_transactions_have_exact_prior_byte_prefix": True,
            "all_and_only_14_structural_rejections_classified": True,
            "alias_rejections_excluded": True,
            "rejected_payloads_disjoint_from_accepted": True,
            "accepted_transactions_match_observations": True,
            "accepted_archives_single_task_hash_bound": True,
            "accepted_run_ids_unique": True,
            "current_inventory_reproduced": True,
            "partial_prior_disclosure_consistent": True,
        },
        "access_attestation": {
            "observation_and_hash_bound_intake_metadata_only": True,
            "rejection_registry_contents_opened": False,
            "archive_payloads_opened": False,
            "labels_grades_outcomes_predictions_accuracy_or_utility_read": False,
            "candidate_identities_or_profiles_read": False,
            "event_competition_archive_task_run_or_candidate_identity_values_emitted": False,
            "randomness_used": False,
            "gpu_paid_api_model_fit_base_update": "0/0/0/0",
        },
        "claim_boundary": {
            "full_census_descriptive_not_sampling_inference": True,
            "partially_predisclosed_not_fully_blind_confirmation": True,
            "prior_anchor_support_is_not_event_time_preexistence": True,
            "estimates_causal_effect": False,
            "supports_task_whitelist_or_blacklist": False,
            "estimates_predictor_accuracy_scaling_search_utility_or_method_effect": False,
        },
    }


def verify(
    protocol_path: Path,
    observations_path: Path,
    result_path: Path,
    state_root: Path,
) -> dict[str, Any]:
    for path, label in (
        (protocol_path, "protocol"),
        (observations_path, "observations"),
        (result_path, "result"),
    ):
        verify_check(path.is_file() and not path.is_symlink(), f"unsafe {label}")
    verify_check(state_root.is_dir() and not state_root.is_symlink(), "unsafe state root")
    protocol_path = protocol_path.resolve()
    observations_path = observations_path.resolve()
    result_path = result_path.resolve()
    state = state_root.resolve()
    candidate = object_from(result_path, "candidate result")
    expected = expected_result(protocol_path, observations_path, state)
    verify_check(candidate == expected, "candidate result differs from independent reconstruction")
    return {
        "protocol": "independent_archive_rejection_support_census_v1",
        "status": VERIFIER_STATUS,
        "result_sha256": digest(result_path),
        "result_status": candidate["status"],
        "event_support_class_counts": candidate["event_support_class_counts"],
        "competition_support_class_counts": candidate["competition_support_class_counts"],
        "classification_digest": candidate["classification_digest"],
        "all_result_fields_equal": True,
        "producer_imported": False,
        "identity_values_emitted": False,
        "outcomes_predictions_labels_read": False,
        "randomness_used": False,
    }


def write_new(path: Path, value: dict[str, Any]) -> None:
    verify_check(not path.exists(), "output already exists")
    verify_check(path.parent.is_dir() and not path.parent.is_symlink(), "unsafe output parent")
    temporary = path.with_name(path.name + f".tmp-{os.getpid()}")
    temporary.write_bytes(canonical(value))
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
    except (CensusVerificationError, IndependentVerificationError, OSError) as exc:
        print(f"ARCHIVE_REJECTION_SUPPORT_CENSUS_VERIFY_ERROR: {exc}", file=sys.stderr)
        return 2
    print(VERIFIER_STATUS)
    print("IDENTITY_VALUES_EMITTED=false")
    print("OUTCOME_PREDICTION_LABEL_READ=false/false/false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
