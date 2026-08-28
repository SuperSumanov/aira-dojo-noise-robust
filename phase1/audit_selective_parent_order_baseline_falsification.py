#!/usr/bin/env python3
"""Falsify content-based parent recovery against fixed causal-order baselines."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable

from phase1 import audit_prospective_fuzzy_code_clones as fingerprint_impl
from phase1 import audit_tree_within_stratum_forward_target522 as snapshot_impl


PROTOCOL = "selective-parent-order-baseline-falsification-v1"
PROTOCOL_SHA256 = "d6553882e56a3e6137aca1ef3d7f0beecd264171323dc38878fb9d970293f23e"
STATUS = "POST_RESULT_FALSIFICATION_FROZEN_BEFORE_ORDER_BASELINE_READOUT"
RESULT_STATUS = "DEVELOPMENT_ORDER_BASELINE_FALSIFICATION_COMPLETE"
SHA_RE = re.compile(r"[0-9a-f]{64}")
COMMIT_RE = re.compile(r"[0-9a-f]{40}")


class OrderBaselineAuditError(RuntimeError):
    """Raised when a frozen dependency, population, or gate drifts."""


@dataclass(frozen=True)
class RecoveryRow:
    task: str
    run: str
    parent: str
    content_prediction: str | None
    content_margin: Fraction
    max_prior_step_prediction: str | None
    nearest_prior_manifest_row_prediction: str | None
    latest_prior_generation_time_prediction: str | None


def require(condition: bool, message: str) -> None:
    if not condition:
        raise OrderBaselineAuditError(message)


def sha256_file(path: Path) -> str:
    require(path.is_file() and not path.is_symlink(), f"unsafe file: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"unsafe JSON: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON root is not an object: {path}")
    return value


def exact(value: Fraction) -> dict[str, Any]:
    return {
        "numerator": value.numerator,
        "denominator": value.denominator,
        "decimal_17g": format(float(value), ".17g"),
    }


def ratio(part: int, whole: int) -> Fraction:
    return Fraction(part, whole) if whole else Fraction(0, 1)


def optional_ratio(part: int, whole: int) -> dict[str, Any] | None:
    return exact(Fraction(part, whole)) if whole else None


def safe_relative(repo_root: Path, relative: str, *, directory: bool = False) -> Path:
    part = Path(relative)
    require(not part.is_absolute() and ".." not in part.parts, f"unsafe path: {relative}")
    raw = repo_root / part
    require(not raw.is_symlink(), f"symlink input: {relative}")
    resolved = raw.resolve()
    require(resolved.is_relative_to(repo_root), f"path escapes repository: {relative}")
    require(resolved.is_dir() if directory else resolved.is_file(), f"missing input: {relative}")
    return resolved


def parse_manifest(root: Path, filename: str) -> tuple[Path, dict[str, str]]:
    manifest = root / filename
    require(manifest.is_file() and not manifest.is_symlink(), "published package manifest missing")
    members: dict[str, str] = {}
    for number, line in enumerate(manifest.read_text(encoding="utf-8").splitlines(), 1):
        match = re.fullmatch(r"([0-9a-f]{64}) [ *](.+)", line)
        require(match is not None, f"malformed package manifest line {number}")
        digest, raw_name = match.groups()
        name = raw_name.removeprefix("./")
        part = Path(name)
        require(name and not part.is_absolute() and ".." not in part.parts, "unsafe manifest member")
        require(name not in members and name != filename, "duplicate manifest member")
        member = root / part
        require(member.is_file() and not member.is_symlink(), f"missing manifest member: {name}")
        require(sha256_file(member) == digest, f"manifest member hash drift: {name}")
        members[name] = digest
    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.name != filename
    }
    require(set(members) == actual, "published package manifest membership drift")
    return manifest, members


def validate_published_result(repo_root: Path, protocol: dict[str, Any]) -> dict[str, Any]:
    frozen = protocol["immutable_inputs"]
    root = safe_relative(repo_root, frozen["published_result_package_root"], directory=True)
    manifest, members = parse_manifest(root, frozen["published_result_package_manifest"])
    require(
        sha256_file(manifest) == frozen["published_result_package_manifest_sha256"],
        "published package manifest SHA drift",
    )
    summary_name = frozen["published_formal_summary"]
    verification_name = frozen["published_independent_verification"]
    require(members.get(summary_name) == frozen["published_formal_summary_sha256"], "published summary binding")
    require(
        members.get(verification_name) == frozen["published_independent_verification_sha256"],
        "published verification binding",
    )
    summary = read_json(root / summary_name)
    verification = read_json(root / verification_name)
    contract = protocol["published_content_contract"]
    require(summary.get("classification") == "DEVELOPMENT_TIME_SPLIT_HIGH_PRECISION_SELECTIVE_PARENT_RECOVERY", "published classification")
    require(summary["inventory"]["test_ambiguous_edges"] == contract["test_ambiguous_edges"], "published test population")
    require(summary["test_profile"]["selected_edges"] == contract["test_selected_edges"], "published selected rows")
    require(summary["test_profile"]["selected_correct_edges"] == contract["test_selected_correct"], "published selected correct")
    require(summary["test_profile"]["selected_error_edges"] == contract["test_selected_errors"], "published selected errors")
    require(summary["test_profile"]["unfiltered_correct_edges"] == contract["test_unfiltered_correct"], "published unfiltered correct")
    require(
        summary["test_profile"]["ambiguous_edges"] - summary["test_profile"]["unfiltered_correct_edges"]
        == contract["test_unfiltered_errors"],
        "published unfiltered errors",
    )
    threshold = summary["threshold_selection"]["threshold"]
    require(
        Fraction(threshold["numerator"], threshold["denominator"])
        == Fraction(contract["selected_margin_threshold"]),
        "published threshold",
    )
    require(verification.get("producer_imported") is False, "published verifier independence")
    require(
        verification.get("fingerprints_candidates_threshold_and_gates_independently_recomputed") is True
        and verification.get("snapshot_and_split_independently_loaded") is True,
        "published independent recomputation",
    )
    return {
        "package_root": frozen["published_result_package_root"],
        "package_manifest_sha256": frozen["published_result_package_manifest_sha256"],
        "package_manifest_members": len(members),
        "formal_summary_sha256": frozen["published_formal_summary_sha256"],
        "independent_verification_sha256": frozen["published_independent_verification_sha256"],
        "classification": summary["classification"],
    }


def read_protocol(path: Path, repo_root: Path) -> tuple[dict[str, Any], str, dict[str, Any]]:
    actual = sha256_file(path)
    require(actual == PROTOCOL_SHA256, "protocol SHA drift")
    protocol = read_json(path)
    require(protocol.get("protocol") == PROTOCOL and protocol.get("status") == STATUS, "protocol identity")
    freeze = protocol["freeze_state"]
    require(freeze["published_content_result_known"] is True, "known-result disclosure")
    for key in (
        "max_prior_step_baseline_values_seen",
        "nearest_prior_manifest_row_baseline_values_seen",
        "latest_prior_generation_time_baseline_values_seen",
        "content_order_disagreement_values_seen",
        "task_or_run_disagreement_breadth_seen",
        "target522_candidate_or_profile_seen",
    ):
        require(freeze[key] is False, f"freeze disclosure drift: {key}")
    immutable = protocol["immutable_inputs"]
    for role in (
        "producer_snapshot_loader",
        "independent_snapshot_loader",
        "producer_fingerprint",
        "independent_fingerprint",
    ):
        dependency = safe_relative(repo_root, immutable[role])
        require(sha256_file(dependency) == immutable[f"{role}_sha256"], f"dependency SHA drift: {role}")
    security = protocol["security"]
    require(security["prospective_first960_or_target300_values_read"] is False, "prospective boundary")
    require(security["target522_candidate_or_profile_read"] is False, "Target-522 boundary")
    require(security["raw_senior_archives_opened"] is False, "raw archive boundary")
    require(security["task_run_card_parent_code_or_per_edge_values_emitted"] is False, "identity boundary")
    require(security["gpu_api_model_fit_base_update"] == [0, 0, 0, 0], "resource boundary")
    published = validate_published_result(repo_root, protocol)
    return protocol, actual, published


def parsed_time(value: str) -> datetime:
    require(isinstance(value, str) and bool(value), "empty generation time")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise OrderBaselineAuditError("invalid generation time") from error
    require(parsed.tzinfo is not None, "generation time lacks timezone")
    return parsed.astimezone(timezone.utc)


def jaccard(left: frozenset[int], right: frozenset[int]) -> Fraction:
    intersection = len(left & right)
    union = len(left) + len(right) - intersection
    require(union > 0, "empty fingerprint union")
    return Fraction(intersection, union)


def unique_maximum(candidates: list[str], key: Callable[[str], Any]) -> str | None:
    if not candidates:
        return None
    maximum = max(key(candidate) for candidate in candidates)
    tops = [candidate for candidate in candidates if key(candidate) == maximum]
    return tops[0] if len(tops) == 1 else None


def build_rows(
    snapshot: snapshot_impl.BlindSnapshot,
) -> tuple[list[RecoveryRow], dict[str, Any]]:
    order = {identifier: index for index, identifier in enumerate(snapshot.card_payloads)}
    steps = {
        identifier: snapshot.card_payloads[identifier]["lineage"]["step"]
        for identifier in snapshot.card_payloads
    }
    times = {
        identifier: parsed_time(snapshot.card_payloads[identifier]["generation_started_at_utc"])
        for identifier in snapshot.card_payloads
    }
    fingerprints: dict[str, frozenset[int]] = {}
    by_run: dict[str, list[str]] = collections.defaultdict(list)
    for identifier in snapshot.card_payloads:
        value = fingerprint_impl.identifier_erased_token_shingles(
            snapshot.card_payloads[identifier]["code"]
        )
        if value is None:
            continue
        fingerprints[identifier] = value
        by_run[snapshot.cards[identifier]["run"]].append(identifier)

    rows: list[RecoveryRow] = []
    parent_present = fingerprint_eligible = depth_consistent = 0
    parent_not_prior_step = parent_not_prior_manifest = parent_after_generation_time = 0
    timestamp_equal_parent_child = 0
    for child in snapshot.card_payloads:
        child_meta = snapshot.cards[child]
        parent = child_meta["parent"]
        if parent not in snapshot.cards:
            continue
        parent_present += 1
        if not steps[parent] < steps[child]:
            parent_not_prior_step += 1
        if not order[parent] < order[child]:
            parent_not_prior_manifest += 1
        if times[parent] > times[child]:
            parent_after_generation_time += 1
        if times[parent] == times[child]:
            timestamp_equal_parent_child += 1
        if child not in fingerprints or parent not in fingerprints:
            continue
        fingerprint_eligible += 1
        if snapshot.cards[parent]["depth"] + 1 != child_meta["depth"]:
            continue
        depth_consistent += 1
        options = [
            candidate
            for candidate in by_run[child_meta["run"]]
            if snapshot.cards[candidate]["depth"] == child_meta["depth"] - 1
        ]
        require(parent in options, "recorded parent absent from fixed candidate set")
        if len(options) < 2:
            continue
        scored = [(jaccard(fingerprints[child], fingerprints[candidate]), candidate) for candidate in options]
        top_score = max(score for score, _candidate in scored)
        content_tops = [candidate for score, candidate in scored if score == top_score]
        content_prediction = content_tops[0] if len(content_tops) == 1 else None
        lower_scores = [score for score, _candidate in scored if score < top_score]
        second_score = max(lower_scores) if lower_scores else top_score
        margin = top_score - second_score if content_prediction is not None else Fraction(0, 1)

        prior_step = [candidate for candidate in options if steps[candidate] < steps[child]]
        prior_manifest = [candidate for candidate in options if order[candidate] < order[child]]
        prior_time = [candidate for candidate in options if times[candidate] < times[child]]
        rows.append(
            RecoveryRow(
                task=child_meta["task"],
                run=child_meta["run"],
                parent=parent,
                content_prediction=content_prediction,
                content_margin=margin,
                max_prior_step_prediction=unique_maximum(prior_step, steps.__getitem__),
                nearest_prior_manifest_row_prediction=unique_maximum(prior_manifest, order.__getitem__),
                latest_prior_generation_time_prediction=unique_maximum(prior_time, times.__getitem__),
            )
        )
    return rows, {
        "parent_present_edges": parent_present,
        "fingerprint_eligible_parent_edges": fingerprint_eligible,
        "depth_consistent_fingerprint_eligible_parent_edges": depth_consistent,
        "ambiguous_exact_depth_edges": len(rows),
        "recorded_parent_not_prior_step": parent_not_prior_step,
        "recorded_parent_not_prior_manifest_row": parent_not_prior_manifest,
        "recorded_parent_after_generation_time": parent_after_generation_time,
        "recorded_parent_equal_generation_time": timestamp_equal_parent_child,
        "fingerprinted_endpoints": len(fingerprints),
    }


def prediction(row: RecoveryRow, baseline: str) -> str | None:
    mapping = {
        "max_prior_step": row.max_prior_step_prediction,
        "nearest_prior_manifest_row": row.nearest_prior_manifest_row_prediction,
        "latest_prior_generation_time": row.latest_prior_generation_time_prediction,
    }
    require(baseline in mapping, f"unknown baseline: {baseline}")
    return mapping[baseline]


def compare(rows: list[RecoveryRow], baseline: str) -> tuple[dict[str, Any], list[RecoveryRow]]:
    comparable = [row for row in rows if prediction(row, baseline) is not None]
    content_correct = sum(row.content_prediction == row.parent for row in comparable)
    order_correct = sum(prediction(row, baseline) == row.parent for row in comparable)
    both_correct = sum(
        row.content_prediction == row.parent and prediction(row, baseline) == row.parent
        for row in comparable
    )
    content_only = sum(
        row.content_prediction == row.parent and prediction(row, baseline) != row.parent
        for row in comparable
    )
    order_only = sum(
        row.content_prediction != row.parent and prediction(row, baseline) == row.parent
        for row in comparable
    )
    both_wrong = len(comparable) - both_correct - content_only - order_only
    content_errors = len(comparable) - content_correct
    order_errors = len(comparable) - order_correct
    require(content_correct == both_correct + content_only, "content paired accounting")
    require(order_correct == both_correct + order_only, "order paired accounting")
    return {
        "selected_content_rows": len(rows),
        "comparable_rows": len(comparable),
        "comparable_coverage": exact(ratio(len(comparable), len(rows))),
        "content_correct": content_correct,
        "content_errors": content_errors,
        "order_correct": order_correct,
        "order_errors": order_errors,
        "paired_correctness": {
            "both_correct": both_correct,
            "content_only_correct": content_only,
            "order_only_correct": order_only,
            "both_wrong": both_wrong,
        },
        "content_to_order_error_ratio": optional_ratio(content_errors, order_errors),
        "content_only_to_order_only_win_ratio": optional_ratio(content_only, order_only),
    }, comparable


def standalone_profile(rows: list[RecoveryRow], baseline: str) -> dict[str, Any]:
    predicted = [row for row in rows if prediction(row, baseline) is not None]
    correct = sum(prediction(row, baseline) == row.parent for row in predicted)
    return {
        "rows": len(rows),
        "predicted_rows": len(predicted),
        "coverage": exact(ratio(len(predicted), len(rows))),
        "correct": correct,
        "errors": len(predicted) - correct,
        "precision": exact(ratio(correct, len(predicted))),
    }


def aggregate_gates(profile: dict[str, Any], protocol: dict[str, Any]) -> dict[str, bool]:
    support = protocol["hard_support"]
    advantage = protocol["aggregate_advantage_gates"]
    coverage = Fraction(profile["comparable_coverage"]["numerator"], profile["comparable_coverage"]["denominator"])
    content_only = profile["paired_correctness"]["content_only_correct"]
    order_only = profile["paired_correctness"]["order_only_correct"]
    return {
        "minimum_comparable_rows": profile["comparable_rows"] >= support["minimum_comparable_rows_per_primary_baseline"],
        "minimum_comparable_coverage": coverage >= Fraction(support["minimum_comparable_coverage_per_primary_baseline"]),
        "order_errors_nonzero": profile["order_errors"] > 0,
        "content_error_at_most_half_order_error": (
            profile["order_errors"] > 0
            and Fraction(profile["content_errors"], profile["order_errors"])
            <= Fraction(advantage["maximum_content_to_order_error_ratio"])
        ),
        "content_only_wins_at_least_twice_order_only_wins": (
            (order_only == 0 and content_only > 0)
            or (order_only > 0 and Fraction(content_only, order_only) >= Fraction(advantage["minimum_content_only_win_to_order_only_win_ratio"]))
        ),
    }


def breadth_profile(rows: list[RecoveryRow], baseline: str, field: str, minimum: int) -> dict[str, Any]:
    discordant = [
        row
        for row in rows
        if (row.content_prediction == row.parent) != (prediction(row, baseline) == row.parent)
    ]
    grouped: dict[str, list[RecoveryRow]] = collections.defaultdict(list)
    for row in discordant:
        grouped[getattr(row, field)].append(row)
    supported = [group for group in grouped.values() if len(group) >= minimum]
    net_positive = 0
    for group in supported:
        content_wins = sum(
            row.content_prediction == row.parent and prediction(row, baseline) != row.parent
            for row in group
        )
        order_wins = len(group) - content_wins
        net_positive += content_wins > order_wins
    sizes = [len(group) for group in grouped.values()]
    return {
        "discordant_rows": len(discordant),
        "conditionable_groups": len(supported),
        "fraction_net_content_positive": exact(ratio(net_positive, len(supported))),
        "maximum_discordance_contribution_share": exact(ratio(max(sizes, default=0), sum(sizes))),
        "identities_emitted": False,
    }


def breadth_gates(task: dict[str, Any], run: dict[str, Any], protocol: dict[str, Any]) -> dict[str, bool]:
    support = protocol["hard_support"]
    gates = protocol["breadth_gates_on_strongest_order_threat"]
    task_fraction = Fraction(task["fraction_net_content_positive"]["numerator"], task["fraction_net_content_positive"]["denominator"])
    run_fraction = Fraction(run["fraction_net_content_positive"]["numerator"], run["fraction_net_content_positive"]["denominator"])
    task_share = Fraction(task["maximum_discordance_contribution_share"]["numerator"], task["maximum_discordance_contribution_share"]["denominator"])
    run_share = Fraction(run["maximum_discordance_contribution_share"]["numerator"], run["maximum_discordance_contribution_share"]["denominator"])
    return {
        "minimum_conditionable_tasks": task["conditionable_groups"] >= support["minimum_conditionable_tasks_for_strong_breadth"],
        "minimum_conditionable_runs": run["conditionable_groups"] >= support["minimum_conditionable_runs_for_strong_breadth"],
        "task_net_content_positive_fraction": task_fraction >= Fraction(gates["minimum_task_fraction_with_more_content_only_than_order_only_wins"]),
        "run_net_content_positive_fraction": run_fraction >= Fraction(gates["minimum_run_fraction_with_more_content_only_than_order_only_wins"]),
        "task_disagreement_anti_dominance": task_share <= Fraction(gates["maximum_single_task_discordance_contribution_share"]),
        "run_disagreement_anti_dominance": run_share <= Fraction(gates["maximum_single_run_discordance_contribution_share"]),
    }


def produce(
    repo_root: Path,
    state_root: Path,
    snapshot_sha: str,
    protocol_path: Path,
    source_commit: str,
) -> dict[str, Any]:
    repo = repo_root.resolve()
    require(repo.is_dir(), "repository root missing")
    require(SHA_RE.fullmatch(snapshot_sha) is not None, "invalid snapshot SHA")
    require(COMMIT_RE.fullmatch(source_commit) is not None, "invalid source commit")
    protocol, protocol_sha, published = read_protocol(protocol_path, repo)
    require(snapshot_sha == protocol["freeze_state"]["snapshot_sha256"], "snapshot mismatch")
    snapshot = snapshot_impl.load_blind_snapshot(state_root, snapshot_sha)
    immutable = protocol["immutable_inputs"]
    require(snapshot.bindings["accumulator_summary_sha256"] == immutable["accumulator_summary_sha256"], "summary binding")
    require(snapshot.bindings["registry_sha256"] == immutable["intake_registry_sha256"], "registry binding")
    require(snapshot.bindings["provisional_runs_sha256"] == immutable["provisional_runs_sha256"], "run-ledger binding")
    freeze = protocol["freeze_state"]
    require(snapshot.bindings["runs"] == freeze["snapshot_runs"], "run count")
    require(snapshot.bindings["endpoints"] == freeze["snapshot_endpoints"], "endpoint count")
    require(snapshot.bindings["tasks"] == freeze["snapshot_tasks"], "task count")

    rows, inventory = build_rows(snapshot)
    contract = protocol["published_content_contract"]
    require(len(rows) == 9739, "ambiguous population drift")
    run_order = list(snapshot.runs)
    require(len(run_order) == contract["train_runs"] + contract["test_runs"], "run split count")
    test_runs = set(run_order[contract["train_runs"] :])
    test_rows = [row for row in rows if row.run in test_runs]
    require(len(test_rows) == contract["test_ambiguous_edges"], "test ambiguous population drift")
    threshold = Fraction(contract["selected_margin_threshold"])
    selected = [
        row
        for row in test_rows
        if row.content_prediction is not None and row.content_margin >= threshold
    ]
    selected_correct = sum(row.content_prediction == row.parent for row in selected)
    unfiltered_correct = sum(row.content_prediction == row.parent for row in test_rows)
    require(len(selected) == contract["test_selected_edges"], "selected population reproduction")
    require(selected_correct == contract["test_selected_correct"], "selected correct reproduction")
    require(len(selected) - selected_correct == contract["test_selected_errors"], "selected error reproduction")
    require(unfiltered_correct == contract["test_unfiltered_correct"], "unfiltered correct reproduction")
    require(len(test_rows) - unfiltered_correct == contract["test_unfiltered_errors"], "unfiltered error reproduction")
    baseline_order = protocol["order_baselines"]["primary_in_fixed_order"]
    comparisons: dict[str, dict[str, Any]] = {}
    comparable_rows: dict[str, list[RecoveryRow]] = {}
    gates: dict[str, dict[str, bool]] = {}
    for baseline in baseline_order:
        profile, comparable = compare(selected, baseline)
        comparisons[baseline] = profile
        comparable_rows[baseline] = comparable
        gates[baseline] = aggregate_gates(profile, protocol)
    secondary_name = "latest_prior_generation_time"
    secondary_profile, _secondary_rows = compare(selected, secondary_name)

    supported = [
        baseline
        for baseline in baseline_order
        if gates[baseline]["minimum_comparable_rows"] and gates[baseline]["minimum_comparable_coverage"]
    ]
    strongest = None
    if supported:
        strongest = min(
            supported,
            key=lambda baseline: (
                Fraction(comparisons[baseline]["order_errors"], comparisons[baseline]["comparable_rows"]),
                baseline_order.index(baseline),
            ),
        )
    if strongest is None:
        task_profile = {
            "discordant_rows": 0,
            "conditionable_groups": 0,
            "fraction_net_content_positive": exact(Fraction(0, 1)),
            "maximum_discordance_contribution_share": exact(Fraction(0, 1)),
            "identities_emitted": False,
        }
        run_profile = dict(task_profile)
    else:
        task_profile = breadth_profile(
            comparable_rows[strongest], strongest, "task", protocol["hard_support"]["task_minimum_discordant_rows"]
        )
        run_profile = breadth_profile(
            comparable_rows[strongest], strongest, "run", protocol["hard_support"]["run_minimum_discordant_rows"]
        )
    breadth_gate_map = breadth_gates(task_profile, run_profile, protocol)

    integrity_gates = {
        "protocol_and_dependencies_exact": True,
        "published_package_and_independent_certificate_exact": True,
        "snapshot_bindings_exact": True,
        "published_content_population_exactly_reproduced": True,
        "recorded_parent_strictly_precedes_child_step": inventory["recorded_parent_not_prior_step"] == 0,
        "recorded_parent_strictly_precedes_child_manifest_row": inventory["recorded_parent_not_prior_manifest_row"] == 0,
        "candidate_set_and_content_threshold_unchanged": True,
        "aggregate_only_output_without_identities": True,
    }
    hard_support_pass = len(supported) == len(baseline_order)
    aggregate_pass = hard_support_pass and all(all(gates[baseline].values()) for baseline in baseline_order)
    breadth_pass = all(breadth_gate_map.values())
    if not all(integrity_gates.values()):
        classification = "DEVELOPMENT_ORDER_BASELINE_FALSIFICATION_INTEGRITY_FAIL"
    elif not hard_support_pass:
        classification = "DEVELOPMENT_ORDER_BASELINE_SUPPORT_INSUFFICIENT"
    elif aggregate_pass and breadth_pass:
        classification = "DEVELOPMENT_CONTENT_ADDS_BROADLY_BEYOND_CAUSAL_ORDER_BASELINES"
    elif aggregate_pass:
        classification = "DEVELOPMENT_CONTENT_ADDS_AGGREGATELY_BUT_BREADTH_UNSUPPORTED"
    else:
        classification = "DEVELOPMENT_CAUSAL_ORDER_BASELINE_NOT_RULED_OUT"
    require(classification in protocol["ordered_classification"], "classification outside protocol")

    both_primary_predict = [
        row
        for row in selected
        if row.max_prior_step_prediction is not None
        and row.nearest_prior_manifest_row_prediction is not None
    ]
    primary_agreement = sum(
        row.max_prior_step_prediction == row.nearest_prior_manifest_row_prediction
        for row in both_primary_predict
    )
    return {
        "protocol": "selective-parent-order-baseline-falsification-receipt-v1",
        "status": RESULT_STATUS,
        "classification": classification,
        "source_commit": source_commit,
        "protocol_sha256": protocol_sha,
        "known_result_status": {
            "published_content_result_known_before_falsification": True,
            "order_baseline_values_unseen_at_freeze": True,
            "post_result_falsification_not_original_preregistration": True,
        },
        "published_result_binding": published,
        "snapshot_bindings": snapshot.bindings,
        "inventory": inventory,
        "reproduced_content_test": {
            "ambiguous_edges": len(test_rows),
            "selected_edges": len(selected),
            "selected_correct": selected_correct,
            "selected_errors": len(selected) - selected_correct,
            "selected_margin_threshold": exact(threshold),
            "unfiltered_correct": unfiltered_correct,
            "unfiltered_errors": len(test_rows) - unfiltered_correct,
        },
        "selected_population_primary_comparisons": comparisons,
        "selected_population_secondary_generation_time": secondary_profile,
        "all_ambiguous_test_order_baselines": {
            baseline: standalone_profile(test_rows, baseline)
            for baseline in (*baseline_order, secondary_name)
        },
        "primary_order_baseline_agreement": {
            "both_predict_rows": len(both_primary_predict),
            "same_prediction_rows": primary_agreement,
            "agreement": exact(ratio(primary_agreement, len(both_primary_predict))),
        },
        "strongest_order_threat": {
            "selection_rule": protocol["breadth_gates_on_strongest_order_threat"]["strongest_threat_selection"],
            "baseline": strongest,
            "task_breadth": task_profile,
            "run_breadth": run_profile,
        },
        "integrity_gates": integrity_gates,
        "primary_baseline_gates": gates,
        "breadth_gates": breadth_gate_map,
        "claim_boundary": protocol["claim_boundary"],
        "security": protocol["security"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = produce(
        args.repo_root,
        args.state_root,
        args.snapshot,
        args.protocol,
        args.source_commit,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
