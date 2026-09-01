#!/usr/bin/env python3
"""Build an identity-erased support census for every structural archive rejection."""
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

from phase1.audit_incremental_archive_rejection_support import (
    ALIAS_REASON,
    ENTRY_KEYS,
    STRUCTURAL_REASONS,
    ZERO,
    IncrementalArchiveAuditError,
    archive_parts,
    canonical_json,
    check,
    merged_metric,
    nonnegative_int,
    read_object,
    require_sha,
    sha256,
    snapshot_transactions,
    support_by_task,
    task_from_seeded_archive,
)


PROTOCOL = "archive_rejection_support_census_v1"
STATUS = "ARCHIVE_REJECTION_SUPPORT_CENSUS_COMPLETE_PARTIALLY_PREDISCLOSED"
PRIOR_SUPPORT = "PRIOR_ANCHOR_ELIGIBLE_SUPPORT"
WINDOW_SUPPORT = "CURRENT_WINDOW_ELIGIBLE_SUPPORT"
ARCHIVE_ONLY = "ACCEPTED_ARCHIVE_ONLY_NO_ELIGIBLE_SUPPORT"
NO_SUPPORT = "NO_ACCEPTED_ARCHIVE_SUPPORT"
CLASSES = (PRIOR_SUPPORT, WINDOW_SUPPORT, ARCHIVE_ONLY, NO_SUPPORT)
OBSERVER_PROTOCOL = "prospective_archive_observer_v1"


class RejectionSupportCensusError(RuntimeError):
    pass


def census_check(condition: bool, message: str) -> None:
    if not condition:
        raise RejectionSupportCensusError(message)


def validate_protocol(protocol: dict[str, Any]) -> None:
    census_check(protocol.get("protocol") == PROTOCOL, "protocol identity mismatch")
    census_check(
        protocol.get("frozen_before_full_census_support_readout") is True,
        "protocol was not frozen before census readout",
    )
    unknown = protocol.get("unknown_at_freeze")
    census_check(
        isinstance(unknown, dict) and unknown and set(unknown.values()) == {False},
        "unknown-at-freeze disclosure mismatch",
    )
    classes = protocol.get("support_classes_in_precedence_order")
    census_check(
        isinstance(classes, list)
        and tuple(row.get("class") for row in classes if isinstance(row, dict)) == CLASSES,
        "support-class precedence mismatch",
    )
    estimand = protocol.get("estimand")
    census_check(
        isinstance(estimand, dict)
        and estimand.get("full_census_not_sampling_inference") is True
        and estimand.get("no_binary_success_threshold") is True,
        "estimand contract mismatch",
    )
    census_check(
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


def bind_repo_evidence(protocol_path: Path, inputs: dict[str, Any]) -> None:
    root = protocol_path.resolve().parent
    for path_key, hash_key in (
        ("legacy_twelve_event_ledger_path", "legacy_twelve_event_ledger_sha256"),
        (
            "legacy_twelve_event_verification_path",
            "legacy_twelve_event_verification_sha256",
        ),
        ("latest_single_event_result_path", "latest_single_event_result_sha256"),
        (
            "latest_single_event_verification_path",
            "latest_single_event_verification_sha256",
        ),
    ):
        relative = inputs.get(path_key)
        census_check(isinstance(relative, str) and bool(relative), f"missing {path_key}")
        unresolved = root / relative
        census_check(not unresolved.is_symlink(), f"symlinked {path_key}")
        path = unresolved.resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise RejectionSupportCensusError(f"escaping {path_key}") from exc
        census_check(path.is_file(), f"absent {path_key}")
        census_check(
            sha256(path) == require_sha(inputs.get(hash_key), hash_key),
            f"hash mismatch for {path_key}",
        )


def classify_observations(
    protocol: dict[str, Any], observations: dict[str, Any]
) -> tuple[dict[str, str], list[dict[str, Any]], dict[str, Any]]:
    census_check(
        set(observations)
        == {"baseline_sealed_at_epoch", "entries", "protocol", "source_root"}
        and observations.get("protocol") == OBSERVER_PROTOCOL,
        "observations schema mismatch",
    )
    baseline_sealed = observations.get("baseline_sealed_at_epoch")
    census_check(
        isinstance(baseline_sealed, (int, float))
        and not isinstance(baseline_sealed, bool)
        and math.isfinite(float(baseline_sealed))
        and baseline_sealed >= 0,
        "baseline seal timestamp malformed",
    )
    entries = observations.get("entries")
    source_root = observations.get("source_root")
    census_check(isinstance(entries, dict), "observation entries missing")
    census_check(isinstance(source_root, str) and bool(source_root), "source root missing")
    prefix = source_root.rstrip("/") + "/"
    accepted: dict[str, str] = {}
    targets: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    reasons: Counter[str] = Counter()
    for relative, row in entries.items():
        census_check(isinstance(row, dict) and set(row) == ENTRY_KEYS, "observation row schema mismatch")
        archive_parts(relative)
        census_check(
            row.get("path") == prefix + relative and row.get("present") is True,
            "observation path or presence mismatch",
        )
        census_check(
            nonnegative_int(row.get("stable_observations"), "stable observations") > 0,
            "unstable observation",
        )
        nonnegative_int(row.get("size"), "archive size")
        nonnegative_int(row.get("mtime_ns"), "archive mtime")
        baseline = row.get("baseline")
        census_check(isinstance(baseline, bool), "baseline flag malformed")
        committed = row.get("committed_archive_sha256")
        committed_snapshot = row.get("committed_snapshot_sha256")
        rejected = row.get("rejected_archive_sha256")
        registry = row.get("rejection_registry_sha256")
        reason = row.get("rejection_reason_code")
        is_accepted = committed is not None or committed_snapshot is not None
        is_rejected = rejected is not None or registry is not None or reason is not None
        census_check(sum((baseline, is_accepted, is_rejected)) == 1, "observation disposition mismatch")
        if baseline:
            counts["baseline"] += 1
        elif is_accepted:
            archive_sha = require_sha(committed, "accepted archive hash")
            require_sha(committed_snapshot, "accepted snapshot hash")
            census_check(archive_sha not in accepted, "duplicate accepted payload hash")
            accepted[archive_sha] = relative
            counts["accepted"] += 1
        else:
            payload_sha = require_sha(rejected, "rejected archive hash")
            require_sha(registry, "rejection registry hash")
            census_check(reason in STRUCTURAL_REASONS | {ALIAS_REASON}, "unknown rejection reason")
            reasons[str(reason)] += 1
            if reason == ALIAS_REASON:
                counts["alias"] += 1
            else:
                counts["structural"] += 1
                targets.append(
                    {
                        "relative": relative,
                        "reason": reason,
                        "payload_sha256": payload_sha,
                    }
                )
    known = protocol["known_before_readout"]["population"]
    census_check(len(entries) == known["observed_archives"], "observed count mismatch")
    census_check(counts["baseline"] == known["baseline_archives"], "baseline count mismatch")
    census_check(counts["accepted"] == known["accepted_archives"], "accepted count mismatch")
    census_check(
        counts["structural"] == known["structural_rejected_archives"],
        "structural rejection count mismatch",
    )
    census_check(counts["alias"] == known["alias_quarantined_archives"], "alias count mismatch")
    census_check(dict(sorted(reasons.items())) == known["rejection_reason_counts"], "reason counts mismatch")
    census_check(len(targets) == 14, "census must contain exactly 14 structural events")
    census_check(
        not ({row["payload_sha256"] for row in targets} & set(accepted)),
        "rejected payload overlaps accepted payload",
    )
    partition = {
        "observed_archives": len(entries),
        "baseline_archives": counts["baseline"],
        "accepted_archives": counts["accepted"],
        "structural_rejected_archives": counts["structural"],
        "alias_quarantined_archives": counts["alias"],
        "pending_archives": 0,
        "rejection_reason_counts": dict(sorted(reasons.items())),
    }
    return accepted, targets, partition


def support_class(prior: dict[str, int], current: dict[str, int]) -> str:
    prior_eligible = (
        prior["accepted_archives"] >= 1
        and prior["eligible_runs"] >= 1
        and prior["eligible_endpoints"] >= 1
    )
    current_eligible = (
        current["accepted_archives"] >= 1
        and current["eligible_runs"] >= 1
        and current["eligible_endpoints"] >= 1
    )
    if prior_eligible:
        return PRIOR_SUPPORT
    if current_eligible:
        return WINDOW_SUPPORT
    if current["accepted_archives"] >= 1:
        return ARCHIVE_ONLY
    return NO_SUPPORT


def add_metrics(total: dict[str, int], values: dict[str, int]) -> None:
    for key in ZERO:
        total[key] += values[key]


def build_result(protocol_path: Path, observations_path: Path, state_root: Path) -> dict[str, Any]:
    census_check(protocol_path.is_file() and not protocol_path.is_symlink(), "unsafe protocol path")
    census_check(observations_path.is_file() and not observations_path.is_symlink(), "unsafe observations path")
    census_check(state_root.is_dir() and not state_root.is_symlink(), "unsafe state root")
    protocol_path = protocol_path.resolve()
    observations_path = observations_path.resolve()
    state_root = state_root.resolve()
    protocol = read_object(protocol_path, "census protocol")
    validate_protocol(protocol)
    inputs = protocol["inputs"]
    bind_repo_evidence(protocol_path, inputs)
    latest = state_root / "LATEST"
    census_check(latest.is_file() and not latest.is_symlink(), "unsafe LATEST")
    census_check(latest.read_text(encoding="ascii").strip() == inputs["current_snapshot_sha256"], "LATEST mismatch")
    census_check(
        sha256(observations_path) == inputs["current_observations_sha256"]
        and observations_path.stat().st_size == inputs["current_observations_bytes"],
        "observations binding mismatch",
    )
    accepted, targets, partition = classify_observations(
        protocol, read_object(observations_path, "observations")
    )
    prior_snapshot, prior_bytes, prior_rows = snapshot_transactions(
        state_root,
        inputs["prior_snapshot_sha256"],
        inputs["prior_transactions_sha256"],
        inputs["prior_transaction_lines"],
    )
    current_snapshot, current_bytes, current_rows = snapshot_transactions(
        state_root,
        inputs["current_snapshot_sha256"],
        inputs["current_transactions_sha256"],
        inputs["current_transaction_lines"],
    )
    census_check(prior_snapshot != current_snapshot, "snapshot anchors collapse")
    census_check(current_bytes.startswith(prior_bytes), "current transactions lack prior byte prefix")
    window_lines = nonnegative_int(
        inputs.get("current_window_transaction_lines"),
        "current-window transaction lines",
    )
    census_check(window_lines > 0, "current-window transaction lines must be positive")
    census_check(
        len(current_rows) - len(prior_rows) == window_lines,
        "current-window transaction count mismatch",
    )
    summary = read_object(current_snapshot / "accumulator" / "summary.json", "accumulator summary")
    inventory = summary.get("inventory")
    known = protocol["known_before_readout"]["population"]
    census_check(isinstance(inventory, dict), "inventory missing")
    for key, known_key in (
        ("all_physical_runs", "physical_runs"),
        ("eligible_runs", "eligible_runs"),
        ("eligible_endpoints", "eligible_endpoints"),
        ("eligible_structural_pairs", "eligible_structural_pairs"),
        ("eligible_tasks", "eligible_tasks"),
    ):
        census_check(inventory.get(key) == known[known_key], f"inventory mismatch: {key}")

    prior_metrics, new_metrics, mapping = support_by_task(
        state_root, current_rows, accepted, inputs["prior_transaction_lines"]
    )
    census_check(mapping["accepted_archives"] == known["accepted_archives"], "mapped archive total mismatch")
    census_check(mapping["physical_runs"] == known["physical_runs"], "mapped run total mismatch")
    census_check(mapping["eligible_runs"] == known["eligible_runs"], "mapped eligible-run total mismatch")
    census_check(mapping["eligible_endpoints"] == known["eligible_endpoints"], "mapped endpoint total mismatch")
    census_check(mapping["accepted_tasks"] == known["eligible_tasks"], "mapped task total mismatch")
    census_check(mapping["accepted_filename_task_mismatches"] == 0, "accepted task mapping mismatch")

    event_classes: Counter[str] = Counter()
    reason_classes: dict[str, Counter[str]] = defaultdict(Counter)
    competition_classes: dict[str, str] = {}
    event_weighted_prior = dict(ZERO)
    event_weighted_window = dict(ZERO)
    event_weighted_current = dict(ZERO)
    digest_rows: list[dict[str, Any]] = []
    for target in targets:
        task = task_from_seeded_archive(target["relative"])
        prior = dict(prior_metrics.get(task, ZERO))
        window = dict(new_metrics.get(task, ZERO))
        current = merged_metric(prior, window)
        classification = support_class(prior, current)
        event_classes[classification] += 1
        reason_classes[target["reason"]][classification] += 1
        previous = competition_classes.setdefault(task, classification)
        census_check(previous == classification, "one competition received inconsistent support classes")
        add_metrics(event_weighted_prior, prior)
        add_metrics(event_weighted_window, window)
        add_metrics(event_weighted_current, current)
        digest_rows.append(
            {
                "reason": target["reason"],
                "class": classification,
                "prior": prior,
                "window": window,
                "current": current,
            }
        )
    census_check(sum(event_classes.values()) == 14, "event classification is incomplete")
    disclosed = protocol["known_before_readout"]["partial_support_disclosure"]
    census_check(
        event_classes[PRIOR_SUPPORT] >= disclosed["legacy_structural_rejection_events"],
        "legacy support disclosure is inconsistent with census",
    )
    census_check(event_classes[NO_SUPPORT] >= 1, "latest absent-event disclosure is inconsistent with census")

    competition_counts = Counter(competition_classes.values())
    reason_table = {
        reason: {name: counts.get(name, 0) for name in CLASSES}
        for reason, counts in sorted(reason_classes.items())
    }
    classification_digest = hashlib.sha256(canonical_json(sorted(digest_rows, key=lambda row: canonical_json(row)))).hexdigest()
    return {
        "protocol": PROTOCOL,
        "status": STATUS,
        "input_bindings": {
            "protocol_sha256": sha256(protocol_path),
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
        "event_support_class_counts": {name: event_classes.get(name, 0) for name in CLASSES},
        "competition_support_class_counts": {
            "distinct_rejected_competitions": len(competition_classes),
            **{name: competition_counts.get(name, 0) for name in CLASSES},
        },
        "reason_by_event_support_class": reason_table,
        "event_weighted_support_quantity_aggregates": {
            "prior_prefix": event_weighted_prior,
            "current_window": event_weighted_window,
            "current_total": event_weighted_current,
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


def write_new(path: Path, value: dict[str, Any]) -> None:
    census_check(not path.exists(), "output already exists")
    census_check(path.parent.is_dir() and not path.parent.is_symlink(), "unsafe output parent")
    temporary = path.with_name(path.name + f".tmp-{os.getpid()}")
    temporary.write_bytes(canonical_json(value))
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
    except (IncrementalArchiveAuditError, RejectionSupportCensusError, OSError) as exc:
        print(f"ARCHIVE_REJECTION_SUPPORT_CENSUS_ERROR: {exc}", file=sys.stderr)
        return 2
    print(STATUS)
    print("IDENTITY_VALUES_EMITTED=false")
    print("LABEL_OUTCOME_PREDICTION_ACCURACY_UTILITY_READ=false/false/false/false/false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
