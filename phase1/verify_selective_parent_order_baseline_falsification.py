#!/usr/bin/env python3
"""Independent verifier for the selective-parent order-baseline falsification."""

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

from phase1 import verify_prospective_fuzzy_code_clones as fingerprint_check
from phase1 import verify_tree_within_stratum_forward_target522 as snapshot_check


PROTOCOL_SHA256 = "d6553882e56a3e6137aca1ef3d7f0beecd264171323dc38878fb9d970293f23e"
SHA_PATTERN = re.compile(r"[0-9a-f]{64}")
COMMIT_PATTERN = re.compile(r"[0-9a-f]{40}")


class OrderBaselineVerificationError(RuntimeError):
    """Raised when independent reconstruction or candidate equality fails."""


@dataclass(frozen=True)
class IndependentRow:
    task: str
    run: str
    parent: str
    content: str | None
    margin: Fraction
    step_choice: str | None
    manifest_choice: str | None
    time_choice: str | None


def check(condition: bool, message: str) -> None:
    if not condition:
        raise OrderBaselineVerificationError(message)


def file_digest(path: Path) -> str:
    check(path.is_file() and not path.is_symlink(), f"unsafe file: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1 << 20):
            digest.update(block)
    return digest.hexdigest()


def object_file(path: Path) -> dict[str, Any]:
    check(path.is_file() and not path.is_symlink(), f"unsafe JSON: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    check(isinstance(value, dict), f"non-object JSON: {path}")
    return value


def fraction_payload(value: Fraction) -> dict[str, Any]:
    return {
        "numerator": value.numerator,
        "denominator": value.denominator,
        "decimal_17g": format(float(value), ".17g"),
    }


def divide(part: int, whole: int) -> Fraction:
    return Fraction(part, whole) if whole else Fraction(0, 1)


def maybe_fraction(part: int, whole: int) -> dict[str, Any] | None:
    return fraction_payload(Fraction(part, whole)) if whole else None


def repository_member(repo: Path, relative: str, *, directory: bool = False) -> Path:
    part = Path(relative)
    check(not part.is_absolute() and ".." not in part.parts, f"unsafe path: {relative}")
    raw = repo / part
    check(not raw.is_symlink(), f"symlink input: {relative}")
    resolved = raw.resolve()
    check(resolved.is_relative_to(repo), f"path escaped repository: {relative}")
    check(resolved.is_dir() if directory else resolved.is_file(), f"missing input: {relative}")
    return resolved


def package_members(root: Path, filename: str) -> tuple[Path, dict[str, str]]:
    manifest = root / filename
    check(manifest.is_file() and not manifest.is_symlink(), "package manifest absent")
    rows: dict[str, str] = {}
    for number, line in enumerate(manifest.read_text(encoding="utf-8").splitlines(), 1):
        match = re.fullmatch(r"([0-9a-f]{64}) [ *](.+)", line)
        check(match is not None, f"manifest syntax line {number}")
        expected, raw_name = match.groups()
        name = raw_name.removeprefix("./")
        part = Path(name)
        check(name and not part.is_absolute() and ".." not in part.parts, "unsafe manifest path")
        check(name not in rows and name != filename, "manifest duplicate")
        member = root / part
        check(member.is_file() and not member.is_symlink(), f"manifest member absent: {name}")
        check(file_digest(member) == expected, f"manifest member digest: {name}")
        rows[name] = expected
    actual = {
        item.relative_to(root).as_posix()
        for item in root.rglob("*")
        if item.is_file() and item.name != filename
    }
    check(set(rows) == actual, "manifest membership mismatch")
    return manifest, rows


def published_certificate(repo: Path, protocol: dict[str, Any]) -> dict[str, Any]:
    fixed = protocol["immutable_inputs"]
    root = repository_member(repo, fixed["published_result_package_root"], directory=True)
    manifest, members = package_members(root, fixed["published_result_package_manifest"])
    check(file_digest(manifest) == fixed["published_result_package_manifest_sha256"], "package manifest digest")
    summary_name = fixed["published_formal_summary"]
    verification_name = fixed["published_independent_verification"]
    check(members.get(summary_name) == fixed["published_formal_summary_sha256"], "summary package binding")
    check(members.get(verification_name) == fixed["published_independent_verification_sha256"], "verification package binding")
    summary = object_file(root / summary_name)
    verification = object_file(root / verification_name)
    contract = protocol["published_content_contract"]
    check(summary.get("classification") == "DEVELOPMENT_TIME_SPLIT_HIGH_PRECISION_SELECTIVE_PARENT_RECOVERY", "published classification")
    observed = summary["test_profile"]
    check(summary["inventory"]["test_ambiguous_edges"] == contract["test_ambiguous_edges"], "published ambiguous")
    check(observed["selected_edges"] == contract["test_selected_edges"], "published selected")
    check(observed["selected_correct_edges"] == contract["test_selected_correct"], "published correct")
    check(observed["selected_error_edges"] == contract["test_selected_errors"], "published errors")
    check(observed["unfiltered_correct_edges"] == contract["test_unfiltered_correct"], "published unfiltered")
    check(observed["ambiguous_edges"] - observed["unfiltered_correct_edges"] == contract["test_unfiltered_errors"], "published unfiltered errors")
    selected_threshold = summary["threshold_selection"]["threshold"]
    check(
        Fraction(selected_threshold["numerator"], selected_threshold["denominator"])
        == Fraction(contract["selected_margin_threshold"]),
        "published threshold",
    )
    check(verification.get("producer_imported") is False, "published verifier independence")
    check(
        verification.get("fingerprints_candidates_threshold_and_gates_independently_recomputed") is True
        and verification.get("snapshot_and_split_independently_loaded") is True,
        "published independent recomputation",
    )
    return {
        "package_root": fixed["published_result_package_root"],
        "package_manifest_sha256": fixed["published_result_package_manifest_sha256"],
        "package_manifest_members": len(members),
        "formal_summary_sha256": fixed["published_formal_summary_sha256"],
        "independent_verification_sha256": fixed["published_independent_verification_sha256"],
        "classification": summary["classification"],
    }


def validate_protocol(path: Path, repo: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    check(file_digest(path) == PROTOCOL_SHA256, "protocol digest")
    protocol = object_file(path)
    check(protocol.get("protocol") == "selective-parent-order-baseline-falsification-v1", "protocol identity")
    check(protocol.get("status") == "POST_RESULT_FALSIFICATION_FROZEN_BEFORE_ORDER_BASELINE_READOUT", "protocol status")
    freeze = protocol["freeze_state"]
    check(freeze["published_content_result_known"] is True, "known result disclosure")
    unseen = (
        "max_prior_step_baseline_values_seen",
        "nearest_prior_manifest_row_baseline_values_seen",
        "latest_prior_generation_time_baseline_values_seen",
        "content_order_disagreement_values_seen",
        "task_or_run_disagreement_breadth_seen",
        "target522_candidate_or_profile_seen",
    )
    check(all(freeze[name] is False for name in unseen), "unseen baseline disclosure")
    immutable = protocol["immutable_inputs"]
    for role in (
        "producer_snapshot_loader",
        "independent_snapshot_loader",
        "producer_fingerprint",
        "independent_fingerprint",
    ):
        dependency = repository_member(repo, immutable[role])
        check(file_digest(dependency) == immutable[f"{role}_sha256"], f"dependency digest: {role}")
    security = protocol["security"]
    check(security["prospective_first960_or_target300_values_read"] is False, "prospective scope")
    check(security["target522_candidate_or_profile_read"] is False, "Target-522 scope")
    check(security["raw_senior_archives_opened"] is False, "archive scope")
    check(security["task_run_card_parent_code_or_per_edge_values_emitted"] is False, "identity scope")
    check(security["gpu_api_model_fit_base_update"] == [0, 0, 0, 0], "resource scope")
    return protocol, published_certificate(repo, protocol)


def timestamp(value: str) -> datetime:
    check(isinstance(value, str) and bool(value), "empty generation time")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise OrderBaselineVerificationError("malformed generation time") from error
    check(parsed.tzinfo is not None, "naive generation time")
    return parsed.astimezone(timezone.utc)


def similarity(left: frozenset[int], right: frozenset[int]) -> Fraction:
    common = len(left.intersection(right))
    total = len(left) + len(right) - common
    check(total > 0, "empty fingerprint union")
    return Fraction(common, total)


def sole_latest(values: list[str], key: Callable[[str], Any]) -> str | None:
    if not values:
        return None
    ranked: dict[Any, list[str]] = collections.defaultdict(list)
    for value in values:
        ranked[key(value)].append(value)
    latest = max(ranked)
    return ranked[latest][0] if len(ranked[latest]) == 1 else None


def independently_recover(snapshot: snapshot_check.SnapshotView) -> tuple[list[IndependentRow], dict[str, Any]]:
    manifest_position = {identifier: index for index, identifier in enumerate(snapshot.card_objects)}
    step = {
        identifier: snapshot.card_objects[identifier]["lineage"]["step"]
        for identifier in snapshot.card_objects
    }
    generated = {
        identifier: timestamp(snapshot.card_objects[identifier]["generation_started_at_utc"])
        for identifier in snapshot.card_objects
    }
    prints: dict[str, frozenset[int]] = {}
    candidates_by_run: dict[str, list[str]] = collections.defaultdict(list)
    for identifier, card in snapshot.card_objects.items():
        value = fingerprint_check.identifier_erased_shingles(card["code"])
        if value is None:
            continue
        prints[identifier] = value
        candidates_by_run[snapshot.graph_cards[identifier]["run"]].append(identifier)

    result: list[IndependentRow] = []
    parent_present = fingerprint_ready = depth_ready = 0
    bad_step = bad_manifest = parent_after_time = equal_time = 0
    for child, child_object in snapshot.card_objects.items():
        child_graph = snapshot.graph_cards[child]
        parent = child_graph["parent"]
        if parent not in snapshot.graph_cards:
            continue
        parent_present += 1
        bad_step += not step[parent] < step[child]
        bad_manifest += not manifest_position[parent] < manifest_position[child]
        parent_after_time += generated[parent] > generated[child]
        equal_time += generated[parent] == generated[child]
        if child not in prints or parent not in prints:
            continue
        fingerprint_ready += 1
        if snapshot.graph_cards[parent]["depth"] + 1 != child_graph["depth"]:
            continue
        depth_ready += 1
        options = [
            candidate
            for candidate in candidates_by_run[child_graph["run"]]
            if snapshot.graph_cards[candidate]["depth"] == child_graph["depth"] - 1
        ]
        check(parent in options, "parent missing from candidates")
        if len(options) < 2:
            continue
        scores = {candidate: similarity(prints[child], prints[candidate]) for candidate in options}
        maximum = max(scores.values())
        content_tops = [candidate for candidate, value in scores.items() if value == maximum]
        content = content_tops[0] if len(content_tops) == 1 else None
        runner_up = max((value for value in scores.values() if value < maximum), default=maximum)
        margin = maximum - runner_up if content is not None else Fraction(0, 1)
        prior_step = [candidate for candidate in options if step[candidate] < step[child]]
        prior_row = [candidate for candidate in options if manifest_position[candidate] < manifest_position[child]]
        prior_time = [candidate for candidate in options if generated[candidate] < generated[child]]
        result.append(
            IndependentRow(
                task=child_graph["task"],
                run=child_graph["run"],
                parent=parent,
                content=content,
                margin=margin,
                step_choice=sole_latest(prior_step, step.__getitem__),
                manifest_choice=sole_latest(prior_row, manifest_position.__getitem__),
                time_choice=sole_latest(prior_time, generated.__getitem__),
            )
        )
    return result, {
        "parent_present_edges": parent_present,
        "fingerprint_eligible_parent_edges": fingerprint_ready,
        "depth_consistent_fingerprint_eligible_parent_edges": depth_ready,
        "ambiguous_exact_depth_edges": len(result),
        "recorded_parent_not_prior_step": bad_step,
        "recorded_parent_not_prior_manifest_row": bad_manifest,
        "recorded_parent_after_generation_time": parent_after_time,
        "recorded_parent_equal_generation_time": equal_time,
        "fingerprinted_endpoints": len(prints),
    }


def baseline_choice(row: IndependentRow, name: str) -> str | None:
    choices = {
        "max_prior_step": row.step_choice,
        "nearest_prior_manifest_row": row.manifest_choice,
        "latest_prior_generation_time": row.time_choice,
    }
    check(name in choices, f"unknown baseline: {name}")
    return choices[name]


def paired_profile(rows: list[IndependentRow], name: str) -> tuple[dict[str, Any], list[IndependentRow]]:
    common = [row for row in rows if baseline_choice(row, name) is not None]
    content_correct = sum(row.content == row.parent for row in common)
    order_correct = sum(baseline_choice(row, name) == row.parent for row in common)
    both = sum(row.content == row.parent and baseline_choice(row, name) == row.parent for row in common)
    content_only = sum(row.content == row.parent and baseline_choice(row, name) != row.parent for row in common)
    order_only = sum(row.content != row.parent and baseline_choice(row, name) == row.parent for row in common)
    neither = len(common) - both - content_only - order_only
    content_errors = len(common) - content_correct
    order_errors = len(common) - order_correct
    check(content_correct == both + content_only, "content table accounting")
    check(order_correct == both + order_only, "order table accounting")
    return {
        "selected_content_rows": len(rows),
        "comparable_rows": len(common),
        "comparable_coverage": fraction_payload(divide(len(common), len(rows))),
        "content_correct": content_correct,
        "content_errors": content_errors,
        "order_correct": order_correct,
        "order_errors": order_errors,
        "paired_correctness": {
            "both_correct": both,
            "content_only_correct": content_only,
            "order_only_correct": order_only,
            "both_wrong": neither,
        },
        "content_to_order_error_ratio": maybe_fraction(content_errors, order_errors),
        "content_only_to_order_only_win_ratio": maybe_fraction(content_only, order_only),
    }, common


def raw_profile(rows: list[IndependentRow], name: str) -> dict[str, Any]:
    predictions = [row for row in rows if baseline_choice(row, name) is not None]
    correct = sum(baseline_choice(row, name) == row.parent for row in predictions)
    return {
        "rows": len(rows),
        "predicted_rows": len(predictions),
        "coverage": fraction_payload(divide(len(predictions), len(rows))),
        "correct": correct,
        "errors": len(predictions) - correct,
        "precision": fraction_payload(divide(correct, len(predictions))),
    }


def gate_profile(profile: dict[str, Any], protocol: dict[str, Any]) -> dict[str, bool]:
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


def anonymous_breadth(
    rows: list[IndependentRow], name: str, attribute: str, minimum: int
) -> dict[str, Any]:
    disagreements = [
        row
        for row in rows
        if (row.content == row.parent) != (baseline_choice(row, name) == row.parent)
    ]
    grouped: dict[str, list[IndependentRow]] = collections.defaultdict(list)
    for row in disagreements:
        grouped[getattr(row, attribute)].append(row)
    supported = [group for group in grouped.values() if len(group) >= minimum]
    positive = 0
    for group in supported:
        content_wins = sum(
            row.content == row.parent and baseline_choice(row, name) != row.parent
            for row in group
        )
        positive += content_wins > len(group) - content_wins
    sizes = [len(group) for group in grouped.values()]
    return {
        "discordant_rows": len(disagreements),
        "conditionable_groups": len(supported),
        "fraction_net_content_positive": fraction_payload(divide(positive, len(supported))),
        "maximum_discordance_contribution_share": fraction_payload(divide(max(sizes, default=0), sum(sizes))),
        "identities_emitted": False,
    }


def breadth_decisions(task: dict[str, Any], run: dict[str, Any], protocol: dict[str, Any]) -> dict[str, bool]:
    support = protocol["hard_support"]
    rule = protocol["breadth_gates_on_strongest_order_threat"]
    task_fraction = Fraction(task["fraction_net_content_positive"]["numerator"], task["fraction_net_content_positive"]["denominator"])
    run_fraction = Fraction(run["fraction_net_content_positive"]["numerator"], run["fraction_net_content_positive"]["denominator"])
    task_share = Fraction(task["maximum_discordance_contribution_share"]["numerator"], task["maximum_discordance_contribution_share"]["denominator"])
    run_share = Fraction(run["maximum_discordance_contribution_share"]["numerator"], run["maximum_discordance_contribution_share"]["denominator"])
    return {
        "minimum_conditionable_tasks": task["conditionable_groups"] >= support["minimum_conditionable_tasks_for_strong_breadth"],
        "minimum_conditionable_runs": run["conditionable_groups"] >= support["minimum_conditionable_runs_for_strong_breadth"],
        "task_net_content_positive_fraction": task_fraction >= Fraction(rule["minimum_task_fraction_with_more_content_only_than_order_only_wins"]),
        "run_net_content_positive_fraction": run_fraction >= Fraction(rule["minimum_run_fraction_with_more_content_only_than_order_only_wins"]),
        "task_disagreement_anti_dominance": task_share <= Fraction(rule["maximum_single_task_discordance_contribution_share"]),
        "run_disagreement_anti_dominance": run_share <= Fraction(rule["maximum_single_run_discordance_contribution_share"]),
    }


def reconstruct(
    repo_root: Path,
    state_root: Path,
    snapshot_sha: str,
    protocol_path: Path,
    source_commit: str,
) -> dict[str, Any]:
    repo = repo_root.resolve()
    check(repo.is_dir(), "repository root missing")
    check(SHA_PATTERN.fullmatch(snapshot_sha) is not None, "snapshot digest syntax")
    check(COMMIT_PATTERN.fullmatch(source_commit) is not None, "commit syntax")
    protocol, published = validate_protocol(protocol_path, repo)
    check(snapshot_sha == protocol["freeze_state"]["snapshot_sha256"], "snapshot mismatch")
    snapshot = snapshot_check.collect_snapshot(state_root, snapshot_sha)
    fixed = protocol["immutable_inputs"]
    check(snapshot.bindings["accumulator_summary_sha256"] == fixed["accumulator_summary_sha256"], "summary binding")
    check(snapshot.bindings["registry_sha256"] == fixed["intake_registry_sha256"], "registry binding")
    check(snapshot.bindings["provisional_runs_sha256"] == fixed["provisional_runs_sha256"], "run binding")
    freeze = protocol["freeze_state"]
    check(snapshot.bindings["runs"] == freeze["snapshot_runs"], "run count")
    check(snapshot.bindings["endpoints"] == freeze["snapshot_endpoints"], "endpoint count")
    check(snapshot.bindings["tasks"] == freeze["snapshot_tasks"], "task count")

    rows, inventory = independently_recover(snapshot)
    contract = protocol["published_content_contract"]
    check(len(rows) == 9739, "ambiguous row count")
    run_order = list(snapshot.run_objects)
    check(len(run_order) == contract["train_runs"] + contract["test_runs"], "split size")
    test_runs = set(run_order[contract["train_runs"] :])
    test = [row for row in rows if row.run in test_runs]
    check(len(test) == contract["test_ambiguous_edges"], "test row count")
    threshold = Fraction(contract["selected_margin_threshold"])
    selected = [row for row in test if row.content is not None and row.margin >= threshold]
    selected_correct = sum(row.content == row.parent for row in selected)
    unfiltered_correct = sum(row.content == row.parent for row in test)
    check(len(selected) == contract["test_selected_edges"], "selected rows")
    check(selected_correct == contract["test_selected_correct"], "selected correct")
    check(len(selected) - selected_correct == contract["test_selected_errors"], "selected errors")
    check(unfiltered_correct == contract["test_unfiltered_correct"], "unfiltered correct")
    check(len(test) - unfiltered_correct == contract["test_unfiltered_errors"], "unfiltered errors")
    primary = protocol["order_baselines"]["primary_in_fixed_order"]
    comparisons: dict[str, dict[str, Any]] = {}
    common_rows: dict[str, list[IndependentRow]] = {}
    primary_gates: dict[str, dict[str, bool]] = {}
    for name in primary:
        profile, common = paired_profile(selected, name)
        comparisons[name] = profile
        common_rows[name] = common
        primary_gates[name] = gate_profile(profile, protocol)
    secondary = "latest_prior_generation_time"
    secondary_profile, _secondary_common = paired_profile(selected, secondary)
    supported = [
        name
        for name in primary
        if primary_gates[name]["minimum_comparable_rows"] and primary_gates[name]["minimum_comparable_coverage"]
    ]
    strongest = None
    if supported:
        strongest = min(
            supported,
            key=lambda name: (
                Fraction(comparisons[name]["order_errors"], comparisons[name]["comparable_rows"]),
                primary.index(name),
            ),
        )
    if strongest is None:
        task_profile = {
            "discordant_rows": 0,
            "conditionable_groups": 0,
            "fraction_net_content_positive": fraction_payload(Fraction(0, 1)),
            "maximum_discordance_contribution_share": fraction_payload(Fraction(0, 1)),
            "identities_emitted": False,
        }
        run_profile = dict(task_profile)
    else:
        task_profile = anonymous_breadth(
            common_rows[strongest], strongest, "task", protocol["hard_support"]["task_minimum_discordant_rows"]
        )
        run_profile = anonymous_breadth(
            common_rows[strongest], strongest, "run", protocol["hard_support"]["run_minimum_discordant_rows"]
        )
    breadth_gates = breadth_decisions(task_profile, run_profile, protocol)
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
    support_pass = len(supported) == len(primary)
    aggregate_pass = support_pass and all(all(primary_gates[name].values()) for name in primary)
    breadth_pass = all(breadth_gates.values())
    if not all(integrity_gates.values()):
        classification = "DEVELOPMENT_ORDER_BASELINE_FALSIFICATION_INTEGRITY_FAIL"
    elif not support_pass:
        classification = "DEVELOPMENT_ORDER_BASELINE_SUPPORT_INSUFFICIENT"
    elif aggregate_pass and breadth_pass:
        classification = "DEVELOPMENT_CONTENT_ADDS_BROADLY_BEYOND_CAUSAL_ORDER_BASELINES"
    elif aggregate_pass:
        classification = "DEVELOPMENT_CONTENT_ADDS_AGGREGATELY_BUT_BREADTH_UNSUPPORTED"
    else:
        classification = "DEVELOPMENT_CAUSAL_ORDER_BASELINE_NOT_RULED_OUT"
    check(classification in protocol["ordered_classification"], "classification ordering")

    dual = [row for row in selected if row.step_choice is not None and row.manifest_choice is not None]
    agreement = sum(row.step_choice == row.manifest_choice for row in dual)
    return {
        "protocol": "selective-parent-order-baseline-falsification-receipt-v1",
        "status": "DEVELOPMENT_ORDER_BASELINE_FALSIFICATION_COMPLETE",
        "classification": classification,
        "source_commit": source_commit,
        "protocol_sha256": PROTOCOL_SHA256,
        "known_result_status": {
            "published_content_result_known_before_falsification": True,
            "order_baseline_values_unseen_at_freeze": True,
            "post_result_falsification_not_original_preregistration": True,
        },
        "published_result_binding": published,
        "snapshot_bindings": snapshot.bindings,
        "inventory": inventory,
        "reproduced_content_test": {
            "ambiguous_edges": len(test),
            "selected_edges": len(selected),
            "selected_correct": selected_correct,
            "selected_errors": len(selected) - selected_correct,
            "selected_margin_threshold": fraction_payload(threshold),
            "unfiltered_correct": unfiltered_correct,
            "unfiltered_errors": len(test) - unfiltered_correct,
        },
        "selected_population_primary_comparisons": comparisons,
        "selected_population_secondary_generation_time": secondary_profile,
        "all_ambiguous_test_order_baselines": {
            name: raw_profile(test, name) for name in (*primary, secondary)
        },
        "primary_order_baseline_agreement": {
            "both_predict_rows": len(dual),
            "same_prediction_rows": agreement,
            "agreement": fraction_payload(divide(agreement, len(dual))),
        },
        "strongest_order_threat": {
            "selection_rule": protocol["breadth_gates_on_strongest_order_threat"]["strongest_threat_selection"],
            "baseline": strongest,
            "task_breadth": task_profile,
            "run_breadth": run_profile,
        },
        "integrity_gates": integrity_gates,
        "primary_baseline_gates": primary_gates,
        "breadth_gates": breadth_gates,
        "claim_boundary": protocol["claim_boundary"],
        "security": protocol["security"],
    }


def verify(
    repo_root: Path,
    state_root: Path,
    snapshot_sha: str,
    protocol_path: Path,
    source_commit: str,
    candidate_path: Path,
) -> dict[str, Any]:
    expected = reconstruct(repo_root, state_root, snapshot_sha, protocol_path, source_commit)
    candidate = object_file(candidate_path)
    check(candidate == expected, "candidate differs from independent reconstruction")
    return {
        "protocol": "selective-parent-order-baseline-falsification-independent-verification-v1",
        "status": "INDEPENDENT_ORDER_BASELINE_FALSIFICATION_VERIFIED",
        "classification": candidate["classification"],
        "protocol_sha256": PROTOCOL_SHA256,
        "candidate_sha256": file_digest(candidate_path),
        "all_aggregate_fields_equal": True,
        "producer_imported": False,
        "independent_snapshot_loader_sha256": file_digest(
            repo_root.resolve() / "phase1/verify_tree_within_stratum_forward_target522.py"
        ),
        "independent_fingerprint_sha256": file_digest(
            repo_root.resolve() / "phase1/verify_prospective_fuzzy_code_clones.py"
        ),
        "prospective_values_read": False,
        "target522_candidate_or_profile_read": False,
        "raw_senior_archives_opened": False,
        "row_level_release_created": False,
        "gpu_api_model_fit_base_update": [0, 0, 0, 0],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = verify(
        args.repo_root,
        args.state_root,
        args.snapshot,
        args.protocol,
        args.source_commit,
        args.candidate,
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
