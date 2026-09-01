#!/usr/bin/env python3
"""Independently reconstruct the identity-erased rejected-competition support floor."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import Counter
from fractions import Fraction
from pathlib import Path
from typing import Any

from phase1.verify_archive_rejection_support_census import (
    ARCHIVE_ONLY,
    CLASSES,
    NO_SUPPORT,
    PRIOR_SUPPORT,
    WINDOW_SUPPORT,
    CensusVerificationError,
    classify,
    merge,
    partition_observations,
)
from phase1.verify_incremental_archive_rejection_support import (
    IndependentVerificationError,
    digest,
    integer,
    object_from,
    read_snapshot_transactions,
    reconstruct_support,
    sha,
    target_task,
    zero_metrics,
)


PROTOCOL = "archive_rejection_support_floor_v1"
RESULT_STATUS = "ARCHIVE_REJECTION_SUPPORT_FLOOR_COMPLETE_POST_HOC"
VERIFIER_STATUS = "INDEPENDENT_ARCHIVE_REJECTION_SUPPORT_FLOOR_PASS_POST_HOC"
METRICS = tuple(zero_metrics())


class SupportFloorVerificationError(RuntimeError):
    pass


def verify_check(condition: bool, message: str) -> None:
    if not condition:
        raise SupportFloorVerificationError(message)


def canonical(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def rational(value: Fraction) -> dict[str, Any]:
    return {
        "numerator": value.numerator,
        "denominator": value.denominator,
        "decimal_17g": format(float(value), ".17g"),
    }


def describe(values: list[int]) -> dict[str, Any]:
    values = sorted(values)
    if not values:
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
    count = len(values)
    total = sum(values)
    midpoint = count // 2
    median = (
        Fraction(values[midpoint], 1)
        if count % 2
        else Fraction(values[midpoint - 1] + values[midpoint], 2)
    )
    return {
        "count": count,
        "sum": total,
        "minimum": values[0],
        "median": rational(median),
        "maximum": values[-1],
        "zero_count": sum(value == 0 for value in values),
        "one_count": sum(value == 1 for value in values),
        "positive_count": sum(value > 0 for value in values),
        "maximum_share": rational(Fraction(values[-1], total)) if total else None,
    }


def describe_anchor(rows: list[dict[str, Any]], anchor: str) -> dict[str, Any]:
    return {
        metric: describe([row[anchor][metric] for row in rows])
        for metric in METRICS
    }


def total_anchor(rows: list[dict[str, Any]], anchor: str) -> dict[str, int]:
    return {
        metric: sum(row[anchor][metric] for row in rows)
        for metric in METRICS
    }


def min_ratio(
    rows: list[dict[str, Any]], anchor: str, numerator: str, denominator: str
) -> dict[str, Any] | None:
    values = [
        Fraction(row[anchor][numerator], row[anchor][denominator])
        for row in rows
        if row[anchor][denominator] > 0
    ]
    return rational(min(values)) if values else None


def validate_protocol(protocol: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    verify_check(protocol.get("protocol") == PROTOCOL, "protocol mismatch")
    verify_check(
        protocol.get("frozen_before_distinct_competition_floor_readout") is True
        and protocol.get("post_hoc_after_aggregate_census_readout") is True,
        "freeze or post-hoc disclosure mismatch",
    )
    unknown = protocol.get("unknown_at_freeze")
    verify_check(
        isinstance(unknown, dict) and unknown and set(unknown.values()) == {False},
        "unknown disclosure mismatch",
    )
    estimand = protocol.get("estimand")
    verify_check(
        isinstance(estimand, dict)
        and tuple(estimand.get("metrics", ())) == METRICS
        and estimand.get("full_census_not_sampling_inference") is True
        and estimand.get("no_binary_success_threshold") is True,
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
    known = protocol.get("known_before_floor_readout")
    verify_check(isinstance(inputs, dict) and isinstance(known, dict), "protocol inputs missing")
    return inputs, known


def read_bound_evidence(
    protocol_path: Path, inputs: dict[str, Any], known: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    root = protocol_path.parent
    resolved: dict[str, Path] = {}
    for path_key, hash_key in (
        ("census_result_path", "census_result_sha256"),
        ("census_verification_path", "census_verification_sha256"),
    ):
        relative = inputs.get(path_key)
        verify_check(isinstance(relative, str) and bool(relative), f"missing {path_key}")
        unresolved = root / relative
        verify_check(not unresolved.is_symlink(), f"symlinked {path_key}")
        path = unresolved.resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise SupportFloorVerificationError(f"escaping {path_key}") from exc
        verify_check(path.is_file(), f"absent {path_key}")
        verify_check(
            digest(path) == sha(inputs.get(hash_key), hash_key),
            f"hash mismatch: {path_key}",
        )
        resolved[path_key] = path
    census = object_from(resolved["census_result_path"], "census result")
    receipt = object_from(resolved["census_verification_path"], "census verification")
    verify_check(
        census.get("status")
        == "ARCHIVE_REJECTION_SUPPORT_CENSUS_COMPLETE_PARTIALLY_PREDISCLOSED"
        and census.get("event_support_class_counts")
        == known["census_event_support_class_counts"]
        and census.get("competition_support_class_counts")
        == known["census_competition_support_class_counts"]
        and census.get("event_weighted_support_quantity_aggregates")
        == known["census_event_weighted_support_quantities"],
        "census evidence differs from frozen disclosure",
    )
    verify_check(
        receipt.get("status")
        == "INDEPENDENT_ARCHIVE_REJECTION_SUPPORT_CENSUS_PASS"
        and receipt.get("result_sha256") == inputs["census_result_sha256"]
        and receipt.get("all_result_fields_equal") is True
        and receipt.get("identity_values_emitted") is False,
        "census verification mismatch",
    )
    return census, receipt


def observation_contract(known: dict[str, Any], census: dict[str, Any]) -> dict[str, Any]:
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
                "rejection_reason_counts": census["population"][
                    "rejection_reason_counts"
                ],
            }
        }
    }


def expected_result(
    protocol_path: Path,
    observations_path: Path,
    state_root: Path,
) -> dict[str, Any]:
    protocol = object_from(protocol_path, "support-floor protocol")
    inputs, known = validate_protocol(protocol)
    census, _receipt = read_bound_evidence(protocol_path, inputs, known)

    latest = state_root / "LATEST"
    verify_check(latest.is_file() and not latest.is_symlink(), "unsafe LATEST")
    verify_check(
        latest.read_text(encoding="ascii").strip() == inputs["current_snapshot_sha256"],
        "LATEST mismatch",
    )
    verify_check(
        digest(observations_path) == inputs["current_observations_sha256"],
        "observations hash mismatch",
    )
    verify_check(
        observations_path.stat().st_size == inputs["current_observations_bytes"],
        "observations size mismatch",
    )
    accepted, targets, partition = partition_observations(
        observation_contract(known, census),
        object_from(observations_path, "observations"),
    )

    prior_snapshot, prior_raw, prior_rows = read_snapshot_transactions(
        state_root,
        inputs["prior_snapshot_sha256"],
        inputs["prior_transactions_sha256"],
        inputs["prior_transaction_lines"],
    )
    current_snapshot, current_raw, current_rows = read_snapshot_transactions(
        state_root,
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
    population = known["population"]
    verify_check(isinstance(inventory, dict), "inventory missing")
    for source_key, known_key in (
        ("all_physical_runs", "physical_runs"),
        ("eligible_runs", "eligible_runs"),
        ("eligible_endpoints", "eligible_endpoints"),
        ("eligible_structural_pairs", "eligible_structural_pairs"),
        ("eligible_tasks", "eligible_tasks"),
    ):
        verify_check(
            inventory.get(source_key) == population[known_key],
            f"inventory mismatch: {source_key}",
        )

    prior, window, mapping = reconstruct_support(
        state_root, current_rows, accepted, inputs["prior_transaction_lines"]
    )
    for mapping_key, population_key in (
        ("accepted_archives", "accepted_archives"),
        ("physical_runs", "physical_runs"),
        ("eligible_runs", "eligible_runs"),
        ("eligible_endpoints", "eligible_endpoints"),
        ("accepted_tasks", "eligible_tasks"),
    ):
        verify_check(
            mapping[mapping_key] == population[population_key],
            f"mapping mismatch: {mapping_key}",
        )
    verify_check(mapping["accepted_filename_task_mismatches"] == 0, "task mapping mismatch")

    event_counts: Counter[str] = Counter()
    competition_classes: dict[str, str] = {}
    for target in targets:
        task = target_task(target["relative"])
        prior_metric = dict(prior.get(task, zero_metrics()))
        current_metric = merge(prior_metric, dict(window.get(task, zero_metrics())))
        support_class = classify(prior_metric, current_metric)
        event_counts[support_class] += 1
        previous = competition_classes.setdefault(task, support_class)
        verify_check(previous == support_class, "competition class mismatch")
    reconstructed_events = {name: event_counts.get(name, 0) for name in CLASSES}
    verify_check(
        reconstructed_events == known["census_event_support_class_counts"],
        "event classes differ from census",
    )
    competition_counts = Counter(competition_classes.values())
    reconstructed_competitions = {
        "distinct_rejected_competitions": len(competition_classes),
        **{name: competition_counts.get(name, 0) for name in CLASSES},
    }
    verify_check(
        reconstructed_competitions
        == known["census_competition_support_class_counts"],
        "competition classes differ from census",
    )

    rows: list[dict[str, Any]] = []
    for task, support_class in competition_classes.items():
        prior_metric = dict(prior.get(task, zero_metrics()))
        window_metric = dict(window.get(task, zero_metrics()))
        rows.append(
            {
                "class": support_class,
                "prior_prefix": prior_metric,
                "current_window": window_metric,
                "current_total": merge(prior_metric, window_metric),
            }
        )
    expected_competitions = known["census_competition_support_class_counts"]
    verify_check(
        len(rows) == expected_competitions["distinct_rejected_competitions"],
        "distinct competition population incomplete",
    )
    rows.sort(key=canonical)
    by_class = {
        name: [row for row in rows if row["class"] == name]
        for name in CLASSES
    }
    prior_supported = by_class[PRIOR_SUPPORT]
    verify_check(
        len(prior_supported) == expected_competitions[PRIOR_SUPPORT],
        "prior-supported population mismatch",
    )
    per_class = {
        name: {
            "competition_count": len(class_rows),
            "prior_prefix": describe_anchor(class_rows, "prior_prefix"),
            "current_window": describe_anchor(class_rows, "current_window"),
            "current_total": describe_anchor(class_rows, "current_total"),
        }
        for name, class_rows in by_class.items()
    }
    distinct_totals = {
        anchor: total_anchor(rows, anchor)
        for anchor in ("prior_prefix", "current_window", "current_total")
    }
    window_counts = {
        metric: sum(row["current_window"][metric] > 0 for row in rows)
        for metric in METRICS
    }
    floor = describe_anchor(prior_supported, "prior_prefix")
    classification_digest = hashlib.sha256(canonical(rows)).hexdigest()
    return {
        "protocol": PROTOCOL,
        "status": RESULT_STATUS,
        "input_bindings": {
            "protocol_sha256": digest(protocol_path),
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
            "prior_metric_summaries": floor,
            "competitions_with_exactly_one_prior_accepted_archive": floor[
                "accepted_archives"
            ]["one_count"],
            "competitions_with_exactly_one_prior_physical_run": floor[
                "physical_runs"
            ]["one_count"],
            "competitions_with_exactly_one_prior_eligible_run": floor[
                "eligible_runs"
            ]["one_count"],
            "minimum_prior_eligible_run_fraction": min_ratio(
                prior_supported, "prior_prefix", "eligible_runs", "physical_runs"
            ),
            "minimum_prior_endpoints_per_eligible_run": min_ratio(
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
    state_root = state_root.resolve()
    candidate = object_from(result_path, "candidate result")
    expected = expected_result(protocol_path, observations_path, state_root)
    verify_check(
        candidate == expected,
        "candidate result differs from independent reconstruction",
    )
    return {
        "protocol": "independent_archive_rejection_support_floor_v1",
        "status": VERIFIER_STATUS,
        "result_sha256": digest(result_path),
        "result_status": candidate["status"],
        "population": candidate["population"],
        "competition_support_class_counts": candidate[
            "competition_support_class_counts"
        ],
        "prior_supported_competition_floor": candidate[
            "prior_supported_competition_floor"
        ],
        "classification_and_metric_digest": candidate[
            "classification_and_metric_digest"
        ],
        "all_result_fields_equal": True,
        "producer_imported": False,
        "identity_values_emitted": False,
        "outcomes_predictions_labels_accuracy_utility_read": False,
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
    except (
        SupportFloorVerificationError,
        CensusVerificationError,
        IndependentVerificationError,
        OSError,
    ) as exc:
        print(f"ARCHIVE_REJECTION_SUPPORT_FLOOR_VERIFY_ERROR: {exc}", file=sys.stderr)
        return 2
    print(VERIFIER_STATUS)
    print("IDENTITY_VALUES_EMITTED=false")
    print("OUTCOME_PREDICTION_LABEL_ACCURACY_UTILITY_READ=false/false/false/false/false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
