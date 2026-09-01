#!/usr/bin/env python3
"""Build identity-erased support-depth summaries for rejected competitions."""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
from collections import Counter
from fractions import Fraction
from pathlib import Path
from typing import Any

from phase1.audit_archive_rejection_support_census import (
    ARCHIVE_ONLY,
    CLASSES,
    NO_SUPPORT,
    PRIOR_SUPPORT,
    WINDOW_SUPPORT,
    classify_observations,
    support_class,
)
from phase1.audit_incremental_archive_rejection_support import (
    ZERO,
    IncrementalArchiveAuditError,
    canonical_json,
    merged_metric,
    nonnegative_int,
    read_object,
    require_sha,
    sha256,
    snapshot_transactions,
    support_by_task,
    task_from_seeded_archive,
)


PROTOCOL = "archive_rejection_support_floor_v1"
STATUS = "ARCHIVE_REJECTION_SUPPORT_FLOOR_COMPLETE_POST_HOC"
METRICS = tuple(ZERO)


class SupportFloorError(RuntimeError):
    pass


def floor_check(condition: bool, message: str) -> None:
    if not condition:
        raise SupportFloorError(message)


def rational(value: Fraction) -> dict[str, Any]:
    return {
        "numerator": value.numerator,
        "denominator": value.denominator,
        "decimal_17g": format(float(value), ".17g"),
    }


def metric_summary(values: list[int]) -> dict[str, Any]:
    ordered = sorted(values)
    if not ordered:
        return {
            "count": 0,
            "sum": 0,
            "minimum": None,
            "median": None,
            "maximum": None,
            "zero_count": 0,
            "one_count": 0,
            "positive_count": 0,
            "maximum_share": None,
        }
    total = sum(ordered)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        median = Fraction(ordered[middle], 1)
    else:
        median = Fraction(ordered[middle - 1] + ordered[middle], 2)
    return {
        "count": len(ordered),
        "sum": total,
        "minimum": ordered[0],
        "median": rational(median),
        "maximum": ordered[-1],
        "zero_count": sum(value == 0 for value in ordered),
        "one_count": sum(value == 1 for value in ordered),
        "positive_count": sum(value > 0 for value in ordered),
        "maximum_share": rational(Fraction(ordered[-1], total)) if total else None,
    }


def summarize_anchor(rows: list[dict[str, Any]], anchor: str) -> dict[str, Any]:
    return {
        metric: metric_summary([row[anchor][metric] for row in rows])
        for metric in METRICS
    }


def sum_anchor(rows: list[dict[str, Any]], anchor: str) -> dict[str, int]:
    return {
        metric: sum(row[anchor][metric] for row in rows)
        for metric in METRICS
    }


def minimum_ratio(
    rows: list[dict[str, Any]], anchor: str, numerator: str, denominator: str
) -> dict[str, Any] | None:
    ratios = [
        Fraction(row[anchor][numerator], row[anchor][denominator])
        for row in rows
        if row[anchor][denominator] > 0
    ]
    return rational(min(ratios)) if ratios else None


def validate_protocol(protocol: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    floor_check(protocol.get("protocol") == PROTOCOL, "protocol identity mismatch")
    floor_check(
        protocol.get("frozen_before_distinct_competition_floor_readout") is True
        and protocol.get("post_hoc_after_aggregate_census_readout") is True,
        "freeze or post-hoc disclosure mismatch",
    )
    unknown = protocol.get("unknown_at_freeze")
    floor_check(
        isinstance(unknown, dict) and unknown and set(unknown.values()) == {False},
        "unknown-at-freeze disclosure mismatch",
    )
    estimand = protocol.get("estimand")
    floor_check(
        isinstance(estimand, dict)
        and tuple(estimand.get("metrics", ())) == METRICS
        and estimand.get("full_census_not_sampling_inference") is True
        and estimand.get("no_binary_success_threshold") is True,
        "estimand contract mismatch",
    )
    floor_check(
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
    known = protocol.get("known_before_floor_readout")
    floor_check(isinstance(inputs, dict) and isinstance(known, dict), "protocol inputs missing")
    return inputs, known


def bound_evidence(
    protocol_path: Path, inputs: dict[str, Any], known: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    root = protocol_path.resolve().parent
    resolved: dict[str, Path] = {}
    for path_key, hash_key in (
        ("census_result_path", "census_result_sha256"),
        ("census_verification_path", "census_verification_sha256"),
    ):
        relative = inputs.get(path_key)
        floor_check(isinstance(relative, str) and relative, f"missing {path_key}")
        unresolved = root / relative
        floor_check(not unresolved.is_symlink(), f"symlinked {path_key}")
        path = unresolved.resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise SupportFloorError(f"escaping {path_key}") from exc
        floor_check(path.is_file(), f"absent {path_key}")
        floor_check(
            sha256(path) == require_sha(inputs.get(hash_key), hash_key),
            f"hash mismatch for {path_key}",
        )
        resolved[path_key] = path
    result = read_object(resolved["census_result_path"], "census result")
    verification = read_object(
        resolved["census_verification_path"], "census verification"
    )
    floor_check(
        result.get("status")
        == "ARCHIVE_REJECTION_SUPPORT_CENSUS_COMPLETE_PARTIALLY_PREDISCLOSED"
        and result.get("event_support_class_counts")
        == known["census_event_support_class_counts"]
        and result.get("competition_support_class_counts")
        == known["census_competition_support_class_counts"]
        and result.get("event_weighted_support_quantity_aggregates")
        == known["census_event_weighted_support_quantities"],
        "bound census result differs from frozen disclosure",
    )
    floor_check(
        verification.get("status")
        == "INDEPENDENT_ARCHIVE_REJECTION_SUPPORT_CENSUS_PASS"
        and verification.get("result_sha256") == inputs["census_result_sha256"]
        and verification.get("all_result_fields_equal") is True
        and verification.get("identity_values_emitted") is False,
        "bound census verification mismatch",
    )
    return result, verification


def classification_contract(
    known: dict[str, Any], census_result: dict[str, Any]
) -> dict[str, Any]:
    population = known["population"]
    return {
        "known_before_readout": {
            "population": {
                "observed_archives": population["observed_archives"],
                "baseline_archives": population["baseline_archives"],
                "accepted_archives": population["accepted_archives"],
                "structural_rejected_archives": population[
                    "structural_rejected_archives"
                ],
                "alias_quarantined_archives": population[
                    "alias_quarantined_archives"
                ],
                "rejection_reason_counts": census_result["population"][
                    "rejection_reason_counts"
                ],
            }
        }
    }


def build_result(protocol_path: Path, observations_path: Path, state_root: Path) -> dict[str, Any]:
    floor_check(protocol_path.is_file() and not protocol_path.is_symlink(), "unsafe protocol")
    floor_check(
        observations_path.is_file() and not observations_path.is_symlink(),
        "unsafe observations",
    )
    floor_check(state_root.is_dir() and not state_root.is_symlink(), "unsafe state root")
    protocol_path = protocol_path.resolve()
    observations_path = observations_path.resolve()
    state_root = state_root.resolve()
    protocol = read_object(protocol_path, "support-floor protocol")
    inputs, known = validate_protocol(protocol)
    census_result, _census_verification = bound_evidence(
        protocol_path, inputs, known
    )

    latest = state_root / "LATEST"
    floor_check(latest.is_file() and not latest.is_symlink(), "unsafe LATEST")
    floor_check(
        latest.read_text(encoding="ascii").strip() == inputs["current_snapshot_sha256"],
        "LATEST mismatch",
    )
    floor_check(
        sha256(observations_path) == inputs["current_observations_sha256"]
        and observations_path.stat().st_size == inputs["current_observations_bytes"],
        "observations binding mismatch",
    )
    observations = read_object(observations_path, "observations")
    accepted, targets, partition = classify_observations(
        classification_contract(known, census_result), observations
    )

    prior_snapshot, prior_raw, prior_rows = snapshot_transactions(
        state_root,
        inputs["prior_snapshot_sha256"],
        inputs["prior_transactions_sha256"],
        inputs["prior_transaction_lines"],
    )
    current_snapshot, current_raw, current_rows = snapshot_transactions(
        state_root,
        inputs["current_snapshot_sha256"],
        inputs["current_transactions_sha256"],
        inputs["current_transaction_lines"],
    )
    floor_check(prior_snapshot != current_snapshot, "snapshot anchors collapse")
    floor_check(current_raw.startswith(prior_raw), "current transactions lack prior prefix")
    window_lines = nonnegative_int(
        inputs.get("current_window_transaction_lines"),
        "current-window transaction lines",
    )
    floor_check(window_lines > 0, "current-window transaction lines must be positive")
    floor_check(
        len(current_rows) - len(prior_rows)
        == window_lines,
        "current-window transaction count mismatch",
    )

    summary = read_object(current_snapshot / "accumulator" / "summary.json", "summary")
    inventory = summary.get("inventory")
    population = known["population"]
    floor_check(isinstance(inventory, dict), "inventory missing")
    for key, frozen in (
        ("all_physical_runs", population["physical_runs"]),
        ("eligible_runs", population["eligible_runs"]),
        ("eligible_endpoints", population["eligible_endpoints"]),
        ("eligible_structural_pairs", population["eligible_structural_pairs"]),
        ("eligible_tasks", population["eligible_tasks"]),
    ):
        floor_check(inventory.get(key) == frozen, f"inventory mismatch: {key}")

    prior_metrics, window_metrics, mapping = support_by_task(
        state_root, current_rows, accepted, inputs["prior_transaction_lines"]
    )
    for key, frozen in (
        ("accepted_archives", population["accepted_archives"]),
        ("physical_runs", population["physical_runs"]),
        ("eligible_runs", population["eligible_runs"]),
        ("eligible_endpoints", population["eligible_endpoints"]),
        ("accepted_tasks", population["eligible_tasks"]),
    ):
        floor_check(mapping.get(key) == frozen, f"mapping mismatch: {key}")
    floor_check(mapping["accepted_filename_task_mismatches"] == 0, "task mapping mismatch")

    event_counts: Counter[str] = Counter()
    competition_classes: dict[str, str] = {}
    for target in targets:
        task = task_from_seeded_archive(target["relative"])
        prior = dict(prior_metrics.get(task, ZERO))
        current = merged_metric(prior, dict(window_metrics.get(task, ZERO)))
        classification = support_class(prior, current)
        event_counts[classification] += 1
        previous = competition_classes.setdefault(task, classification)
        floor_check(previous == classification, "inconsistent competition class")
    floor_check(
        {name: event_counts.get(name, 0) for name in CLASSES}
        == known["census_event_support_class_counts"],
        "event classes differ from completed census",
    )
    competition_counts = Counter(competition_classes.values())
    reconstructed_competitions = {
        "distinct_rejected_competitions": len(competition_classes),
        **{name: competition_counts.get(name, 0) for name in CLASSES},
    }
    floor_check(
        reconstructed_competitions
        == known["census_competition_support_class_counts"],
        "competition classes differ from completed census",
    )

    rows: list[dict[str, Any]] = []
    for task, classification in competition_classes.items():
        prior = dict(prior_metrics.get(task, ZERO))
        window = dict(window_metrics.get(task, ZERO))
        rows.append(
            {
                "class": classification,
                "prior_prefix": prior,
                "current_window": window,
                "current_total": merged_metric(prior, window),
            }
        )
    expected_competitions = known["census_competition_support_class_counts"]
    floor_check(
        len(rows) == expected_competitions["distinct_rejected_competitions"],
        "distinct competition population incomplete",
    )
    rows.sort(key=canonical_json)
    by_class = {
        name: [row for row in rows if row["class"] == name]
        for name in CLASSES
    }
    prior_supported = by_class[PRIOR_SUPPORT]
    floor_check(
        len(prior_supported) == expected_competitions[PRIOR_SUPPORT],
        "prior-supported population mismatch",
    )

    per_class = {
        name: {
            "competition_count": len(class_rows),
            "prior_prefix": summarize_anchor(class_rows, "prior_prefix"),
            "current_window": summarize_anchor(class_rows, "current_window"),
            "current_total": summarize_anchor(class_rows, "current_total"),
        }
        for name, class_rows in by_class.items()
    }
    distinct_totals = {
        anchor: sum_anchor(rows, anchor)
        for anchor in ("prior_prefix", "current_window", "current_total")
    }
    window_counts = {
        metric: sum(row["current_window"][metric] > 0 for row in rows)
        for metric in METRICS
    }
    floor_summary = summarize_anchor(prior_supported, "prior_prefix")
    classification_digest = hashlib.sha256(canonical_json(rows)).hexdigest()
    return {
        "protocol": PROTOCOL,
        "status": STATUS,
        "input_bindings": {
            "protocol_sha256": sha256(protocol_path),
            "prior_snapshot_sha256": inputs["prior_snapshot_sha256"],
            "current_snapshot_sha256": inputs["current_snapshot_sha256"],
            "current_observations_sha256": inputs["current_observations_sha256"],
            "census_result_sha256": inputs["census_result_sha256"],
            "census_verification_sha256": inputs["census_verification_sha256"],
        },
        "population": {
            **partition,
            "distinct_rejected_competitions": len(rows),
            "prior_supported_competitions": len(prior_supported),
            "physical_runs": mapping["physical_runs"],
            "eligible_runs": mapping["eligible_runs"],
            "eligible_endpoints": mapping["eligible_endpoints"],
            "eligible_structural_pairs": population["eligible_structural_pairs"],
            "eligible_tasks": mapping["accepted_tasks"],
        },
        "competition_support_class_counts": reconstructed_competitions,
        "distinct_competition_support_totals": distinct_totals,
        "per_class_metric_summaries": per_class,
        "prior_supported_competition_floor": {
            "competition_count": len(prior_supported),
            "prior_metric_summaries": floor_summary,
            "competitions_with_exactly_one_prior_accepted_archive": floor_summary[
                "accepted_archives"
            ]["one_count"],
            "competitions_with_exactly_one_prior_physical_run": floor_summary[
                "physical_runs"
            ]["one_count"],
            "competitions_with_exactly_one_prior_eligible_run": floor_summary[
                "eligible_runs"
            ]["one_count"],
            "minimum_prior_eligible_run_fraction": minimum_ratio(
                prior_supported, "prior_prefix", "eligible_runs", "physical_runs"
            ),
            "minimum_prior_endpoints_per_eligible_run": minimum_ratio(
                prior_supported,
                "prior_prefix",
                "eligible_endpoints",
                "eligible_runs",
            ),
        },
        "current_window_competition_counts_with_positive_increment": window_counts,
        "classification_and_metric_digest": classification_digest,
        "mapping_audit": mapping,
        "integrity": {
            "completed_census_result_and_verification_bound": True,
            "census_event_and_competition_counts_reproduced": True,
            "current_transactions_have_exact_prior_byte_prefix": True,
            "all_expected_distinct_rejected_competitions_summarized": True,
            "one_consistent_class_per_competition": True,
            "accepted_transactions_and_provenance_hash_bound": True,
            "accepted_run_ids_unique": True,
            "current_inventory_reproduced": True,
        },
        "access_attestation": {
            "observation_and_hash_bound_intake_metadata_only": True,
            "rejection_registry_contents_opened": False,
            "archive_payloads_opened": False,
            "labels_grades_outcomes_predictions_accuracy_or_utility_read": False,
            "candidate_identities_or_profiles_read": False,
            "competition_archive_task_run_or_candidate_identity_values_emitted": False,
            "randomness_used": False,
            "gpu_paid_api_model_fit_base_update": "0/0/0/0",
        },
        "claim_boundary": {
            "post_hoc_after_aggregate_census_readout": True,
            "full_census_descriptive_not_sampling_inference": True,
            "no_binary_success_threshold": True,
            "prior_anchor_support_is_not_event_time_preexistence": True,
            "estimates_future_rejection_frequency_or_causal_effect": False,
            "supports_task_whitelist_or_blacklist": False,
            "estimates_predictor_accuracy_scaling_search_utility_or_method_effect": False,
        },
    }


def write_new(path: Path, value: dict[str, Any]) -> None:
    floor_check(not path.exists(), "output already exists")
    floor_check(path.parent.is_dir() and not path.parent.is_symlink(), "unsafe output parent")
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
    except (IncrementalArchiveAuditError, SupportFloorError, OSError) as exc:
        print(f"ARCHIVE_REJECTION_SUPPORT_FLOOR_ERROR: {exc}", file=sys.stderr)
        return 2
    print(STATUS)
    print("IDENTITY_VALUES_EMITTED=false")
    print("LABEL_OUTCOME_PREDICTION_ACCURACY_UTILITY_READ=false/false/false/false/false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
