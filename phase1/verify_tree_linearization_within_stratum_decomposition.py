#!/usr/bin/env python3
"""Independent verifier for the within-stratum tree-linearization decomposition."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import re
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable

from phase1 import verify_prospective_tree_linearization_weights as blind_reader


PROTOCOL_NAME = "tree-linearization-within-stratum-decomposition-v1"
RECEIPT_PROTOCOL = "tree-linearization-within-stratum-decomposition-receipt-v1"
VERIFY_PROTOCOL = "independent-tree-linearization-within-stratum-verifier-v1"
SHA_RE = re.compile(r"[0-9a-f]{64}")


class VerificationError(RuntimeError):
    """Raised on any independent reconstruction mismatch."""


def check(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def digest(path: Path) -> str:
    check(path.is_file() and not path.is_symlink(), f"unsafe file: {path}")
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def object_at(path: Path) -> dict[str, Any]:
    check(path.is_file() and not path.is_symlink(), f"unsafe JSON: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    check(isinstance(value, dict), f"non-object JSON: {path}")
    return value


def path_in_repo(repo_root: Path, relative: str) -> Path:
    piece = Path(relative)
    check(not piece.is_absolute() and ".." not in piece.parts, f"unsafe relative path: {relative}")
    root = repo_root.resolve()
    raw = root / piece
    check(not raw.is_symlink(), f"symlink input: {relative}")
    resolved = raw.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise VerificationError(f"repository escape: {relative}") from error
    check(resolved.is_file(), f"missing fixed input: {relative}")
    return resolved


def ratio(text: str) -> Fraction:
    check(isinstance(text, str) and bool(text), "invalid ratio text")
    try:
        value = Fraction(text)
    except (ValueError, ZeroDivisionError) as error:
        raise VerificationError(f"invalid ratio: {text}") from error
    check(value >= 0, "negative ratio")
    return value


def encoded(value: Fraction) -> dict[str, Any]:
    return {
        "numerator": value.numerator,
        "denominator": value.denominator,
        "decimal_17g": format(float(value), ".17g"),
    }


def decoded(value: Any, label: str) -> Fraction:
    check(isinstance(value, dict), f"missing exact value: {label}")
    numerator, denominator = value.get("numerator"), value.get("denominator")
    check(
        isinstance(numerator, int)
        and not isinstance(numerator, bool)
        and isinstance(denominator, int)
        and not isinstance(denominator, bool)
        and denominator > 0,
        f"invalid exact value: {label}",
    )
    result = Fraction(numerator, denominator)
    check(value == encoded(result), f"noncanonical exact value: {label}")
    return result


def tv(first: Iterable[Fraction], second: Iterable[Fraction]) -> Fraction:
    a, b = list(first), list(second)
    check(len(a) == len(b) and bool(a), "bad TV vectors")
    check(sum(a, Fraction()) == 1 and sum(b, Fraction()) == 1, "unnormalized TV vectors")
    return sum((abs(x - y) for x, y in zip(a, b)), Fraction()) / 2


def middle(values: list[Fraction]) -> Fraction:
    check(bool(values), "empty median")
    rows = sorted(values)
    pivot = len(rows) // 2
    return rows[pivot] if len(rows) % 2 else (rows[pivot - 1] + rows[pivot]) / 2


def rank90(values: list[Fraction]) -> Fraction:
    check(bool(values), "empty quantile")
    rows = sorted(values)
    rank = (9 * len(rows) + 9) // 10
    return rows[max(1, rank) - 1]


def reconstruct_edges(cards: dict[str, dict[str, Any]]) -> tuple[list[tuple[str, str, int]], dict[str, int]]:
    parent: dict[str, str] = {}
    child_map: dict[str, list[str]] = {identifier: [] for identifier in cards}
    roots: set[str] = set()
    for identifier, row in cards.items():
        ancestor = row["parent"]
        if ancestor not in cards:
            roots.add(identifier)
            continue
        check(ancestor != identifier, "self-parent")
        check(cards[ancestor]["run"] == row["run"], "cross-run edge")
        check(cards[ancestor]["task"] == row["task"], "cross-task edge")
        parent[identifier] = ancestor
        child_map[ancestor].append(identifier)
    check(bool(roots), "no fragment roots")

    unresolved = set(cards)
    leaves_below: dict[str, int] = {}
    while unresolved:
        ready = sorted(
            node
            for node in unresolved
            if all(child in leaves_below for child in child_map[node])
        )
        check(bool(ready), "cycle or unresolved component")
        for node in ready:
            descendants = child_map[node]
            leaves_below[node] = 1 if not descendants else sum(leaves_below[child] for child in descendants)
            unresolved.remove(node)
    check(all(node in leaves_below for node in roots), "root accounting mismatch")

    edge_rows = [
        (cards[child]["task"], cards[child]["run"], leaves_below[child])
        for child in sorted(parent)
    ]
    check(bool(edge_rows) and all(row[2] >= 1 for row in edge_rows), "invalid reconstructed edges")
    return edge_rows, {
        "fragment_roots": len(roots),
        "fragment_leaves": sum(not child_map[node] for node in cards),
        "single_node_fragments": sum(not child_map[root] for root in roots),
    }


def group_tv(multiplicities: list[int]) -> Fraction:
    edge_count, occurrence_count = len(multiplicities), sum(multiplicities)
    check(edge_count > 0 and occurrence_count >= edge_count, "bad group")
    canonical = [Fraction(1, edge_count)] * edge_count
    path = [Fraction(value, occurrence_count) for value in multiplicities]
    return tv(canonical, path)


def bins(values: list[Fraction], boundaries: list[Fraction]) -> list[int]:
    check(boundaries == sorted(set(boundaries)) and boundaries[0] == 0 and boundaries[-1] == 1, "bad bins")
    counts = [0 for _ in range(len(boundaries) - 1)]
    for value in values:
        assigned = False
        for index in range(len(counts)):
            lower, upper = boundaries[index], boundaries[index + 1]
            if lower <= value < upper or (index == len(counts) - 1 and value == upper):
                counts[index] += 1
                assigned = True
                break
        check(assigned, "unbinned conditional TV")
    check(sum(counts) == len(values), "bin accounting mismatch")
    return counts


def independently_profile(
    edge_rows: list[tuple[str, str, int]],
    group_column: int,
    overall: Fraction,
    protocol: dict[str, Any],
) -> dict[str, Any]:
    grouped: dict[str, list[int]] = collections.defaultdict(list)
    for row in edge_rows:
        grouped[row[group_column]].append(row[2])
    names = sorted(grouped)
    total_edges = len(edge_rows)
    total_occurrences = sum(row[2] for row in edge_rows)
    edge_masses = [Fraction(len(grouped[name]), total_edges) for name in names]
    occurrence_masses = [Fraction(sum(grouped[name]), total_occurrences) for name in names]
    marginal = tv(edge_masses, occurrence_masses)
    conditional = {name: group_tv(grouped[name]) for name in names}
    canonical_parts = {
        name: Fraction(len(grouped[name]), total_edges) * conditional[name] for name in names
    }
    path_parts = {
        name: Fraction(sum(grouped[name]), total_occurrences) * conditional[name] for name in names
    }
    within_canonical = sum(canonical_parts.values(), Fraction())
    within_path = sum(path_parts.values(), Fraction())
    lower = max(Fraction(), overall - marginal)
    slack = within_canonical - lower
    check(slack >= 0, "triangle lower bound failed")
    conditionable_names = [name for name in names if len(grouped[name]) >= 2]
    conditional_values = [conditional[name] for name in conditionable_names]
    check(bool(conditional_values), "no conditionable groups")
    distribution = protocol["fixed_distribution_summary"]
    reference = ratio(distribution["conditional_tv_reference"])
    above = sum(value >= reference for value in conditional_values)
    fraction_above = Fraction(above, len(conditional_values))
    boundaries = [ratio(value) for value in distribution["histogram_edges"]]
    max_share = max(canonical_parts.values()) / within_canonical if within_canonical else Fraction()

    gate = protocol["strong_positive_gates"]
    task_axis = group_column == 0
    breadth_limit = ratio(
        gate[
            "minimum_task_fraction_at_or_above_conditional_tv_reference"
            if task_axis
            else "minimum_physical_run_fraction_at_or_above_conditional_tv_reference"
        ]
    )
    dominance_limit = ratio(
        gate[
            "maximum_single_task_canonical_contribution_share"
            if task_axis
            else "maximum_single_physical_run_canonical_contribution_share"
        ]
    )
    within_floor = ratio(
        gate[
            "minimum_task_canonical_standardized_within_tv_integrity_floor"
            if task_axis
            else "minimum_physical_run_canonical_standardized_within_tv_integrity_floor"
        ]
    )
    checks = {
        "canonical_standardized_within_tv_at_least_integrity_floor": within_canonical
        >= within_floor,
        "breadth_fraction_at_least_minimum": fraction_above >= breadth_limit,
        "maximum_contribution_share_at_most_maximum": max_share <= dominance_limit,
    }
    return {
        "groups_with_observed_edges": len(grouped),
        "conditionable_groups": len(conditionable_names),
        "group_marginal_total_variation": encoded(marginal),
        "canonical_marginal_standardized_within_total_variation": encoded(within_canonical),
        "path_marginal_standardized_within_total_variation_secondary": encoded(within_path),
        "triangle_lower_bound": encoded(lower),
        "exact_slack_above_triangle_lower_bound": encoded(slack),
        "anonymous_conditionable_group_distribution": {
            "reference": encoded(reference),
            "groups_at_or_above_reference": above,
            "fraction_at_or_above_reference": encoded(fraction_above),
            "histogram": {
                "edges": [encoded(value) for value in boundaries],
                "counts": bins(conditional_values, boundaries),
                "last_bin_right_closed": True,
            },
            "median": encoded(middle(conditional_values)),
            "p90_nearest_rank": encoded(rank90(conditional_values)),
            "maximum": encoded(max(conditional_values)),
        },
        "maximum_anonymous_canonical_contribution_share": encoded(max_share),
        "strong_positive_gate": {
            "checks": checks,
            "all_passed": all(checks.values()),
            "within_tv_integrity_floor": encoded(within_floor),
            "breadth_threshold": encoded(breadth_limit),
            "dominance_threshold": encoded(dominance_limit),
            "triangle_slack_is_diagnostic_only": True,
        },
    }


def independently_summarize(
    edge_rows: list[tuple[str, str, int]], protocol: dict[str, Any]
) -> dict[str, Any]:
    check(bool(edge_rows), "empty edges")
    edge_total = len(edge_rows)
    occurrence_total = sum(row[2] for row in edge_rows)
    overall = tv(
        [Fraction(1, edge_total)] * edge_total,
        [Fraction(row[2], occurrence_total) for row in edge_rows],
    )
    task = independently_profile(edge_rows, 0, overall, protocol)
    run = independently_profile(edge_rows, 1, overall, protocol)
    support = protocol["hard_integrity_and_support_gates"]
    support_checks = {
        "conditionable_tasks_at_least_minimum": task["conditionable_groups"]
        >= support["minimum_conditionable_tasks"],
        "conditionable_physical_runs_at_least_minimum": run["conditionable_groups"]
        >= support["minimum_conditionable_physical_runs"],
    }
    return {
        "inventory": {
            "observed_unique_edges": edge_total,
            "path_edge_occurrences": occurrence_total,
            "duplicate_edge_occurrences": occurrence_total - edge_total,
            "tasks_with_observed_edges": task["groups_with_observed_edges"],
            "physical_runs_with_observed_edges": run["groups_with_observed_edges"],
        },
        "overall_edge_total_variation": encoded(overall),
        "partitions": {"task": task, "physical_run": run},
        "support_checks": support_checks,
        "axis_strength": {
            "task": task["strong_positive_gate"]["all_passed"],
            "physical_run": run["strong_positive_gate"]["all_passed"],
        },
    }


def deep_equal(expected: Any, actual: Any, path: str) -> None:
    if isinstance(expected, dict):
        check(isinstance(actual, dict) and set(actual) == set(expected), f"mapping mismatch: {path}")
        for key in expected:
            deep_equal(expected[key], actual[key], f"{path}.{key}")
    elif isinstance(expected, list):
        check(isinstance(actual, list) and len(actual) == len(expected), f"list mismatch: {path}")
        for index, (left, right) in enumerate(zip(expected, actual)):
            deep_equal(left, right, f"{path}[{index}]")
    else:
        check(expected == actual, f"value mismatch: {path}")


def fixed_sources(repo_root: Path, protocol: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, str]]:
    values: dict[str, dict[str, Any]] = {}
    hashes: dict[str, str] = {}
    for name in ("population_protocol", "linearization_receipt", "estimand_sensitivity_receipt"):
        spec = protocol["fixed_inputs"][name]
        check(isinstance(spec.get("sha256"), str) and SHA_RE.fullmatch(spec["sha256"]) is not None, f"invalid {name} SHA")
        path = path_in_repo(repo_root, spec["path"])
        hashes[name] = digest(path)
        check(hashes[name] == spec["sha256"], f"{name} hash mismatch")
        values[name] = object_at(path)
    population = values["population_protocol"]
    linear = values["linearization_receipt"]
    sensitivity = values["estimand_sensitivity_receipt"]
    snapshot = protocol["fixed_population"]["snapshot_sha256"]
    check(population.get("protocol") == "prospective-tree-linearization-weight-audit-v1", "population protocol")
    check(population.get("fixed_snapshot", {}).get("sha256") == snapshot, "population snapshot")
    check(linear.get("classification") == protocol["fixed_inputs"]["linearization_receipt"]["required_classification"], "linear classification")
    check(sensitivity.get("classification") == protocol["fixed_inputs"]["estimand_sensitivity_receipt"]["required_classification"], "sensitivity classification")
    check(linear.get("snapshot_sha256") == sensitivity.get("snapshot_sha256") == snapshot, "source snapshot")
    check(linear.get("pre_registered_gate", {}).get("all_hard_gates_passed") is True, "source gates")
    disclosed = protocol["disclosed_pre_freeze_values"]
    check(linear.get("inventory", {}).get("observed_unique_edges") == disclosed["canonical_unique_edges"], "source edge count")
    check(linear.get("linearization", {}).get("branch_linearized_edge_occurrences") == disclosed["path_edge_occurrences"], "source occurrence count")
    check(decoded(sensitivity.get("edge_measure_shift", {}).get("total_variation"), "source overall TV") == ratio(disclosed["overall_edge_total_variation"]), "source TV")
    return population, linear, sensitivity, hashes


def classify(summary: dict[str, Any], protocol: dict[str, Any], hard: dict[str, bool]) -> str:
    if not all(hard.values()):
        value = "WITHIN_STRATUM_DECOMPOSITION_GATE_FAIL"
    else:
        task, run = summary["axis_strength"]["task"], summary["axis_strength"]["physical_run"]
        task_value = decoded(summary["partitions"]["task"]["canonical_marginal_standardized_within_total_variation"], "task TV")
        run_value = decoded(summary["partitions"]["physical_run"]["canonical_marginal_standardized_within_total_variation"], "run TV")
        if task and run:
            value = "BROAD_NONCOMPOSITIONAL_LINEARIZATION_DISTORTION"
        elif task:
            value = "TASK_ONLY_BROAD_NONCOMPOSITIONAL_LINEARIZATION_DISTORTION"
        elif run:
            value = "RUN_ONLY_BROAD_NONCOMPOSITIONAL_LINEARIZATION_DISTORTION"
        elif task_value > 0 or run_value > 0:
            value = "WITHIN_STRATUM_PROFILE_BELOW_STRONG_GATE"
        else:
            value = "NO_OBSERVED_WITHIN_STRATUM_DISTORTION"
    check(value in protocol["ordered_classification"], "classification outside contract")
    return value


def verify(
    state_root: Path,
    snapshot_root: Path,
    repo_root: Path,
    protocol_path: Path,
    protocol_sha: str,
    receipt_path: Path,
    receipt_sha: str,
    producer_source: Path,
    producer_source_sha: str,
    source_commit: str,
) -> dict[str, Any]:
    check(digest(protocol_path) == protocol_sha, "protocol SHA mismatch")
    protocol = object_at(protocol_path)
    check(protocol.get("protocol") == PROTOCOL_NAME, "protocol name")
    check(protocol.get("status") == "OUTCOME_BLIND_PROTOCOL_FROZEN_BEFORE_WITHIN_STRATUM_AGGREGATES", "protocol status")
    check(protocol.get("design_timing", {}).get("new_within_task_or_within_run_values_seen") is False, "design timing")
    check(digest(receipt_path) == receipt_sha, "receipt SHA mismatch")
    receipt = object_at(receipt_path)
    check(receipt.get("protocol") == RECEIPT_PROTOCOL, "receipt protocol")
    check(receipt.get("status") == "OUTCOME_BLIND_WITHIN_STRATUM_DECOMPOSITION_COMPLETE", "receipt status")
    check(digest(producer_source) == producer_source_sha, "producer source SHA mismatch")
    check(re.fullmatch(r"[0-9a-f]{40}", source_commit) is not None, "invalid source commit")
    check(receipt.get("source_commit") == source_commit, "receipt commit mismatch")
    check(receipt.get("producer_source_sha256") == producer_source_sha, "receipt producer hash")
    check(receipt.get("protocol_sha256") == protocol_sha, "receipt protocol hash")

    population_protocol, linear, _sensitivity, source_hashes = fixed_sources(repo_root, protocol)
    try:
        cards, runs, population_bindings = blind_reader.collect_inputs(
            state_root, snapshot_root, population_protocol
        )
    except blind_reader.VerificationError as error:
        raise VerificationError(f"blind population reconstruction failed: {error}") from error
    edge_rows, graph_inventory = reconstruct_edges(cards)
    summary = independently_summarize(edge_rows, protocol)
    disclosed = protocol["disclosed_pre_freeze_values"]
    task_marginal = summary["partitions"]["task"]["group_marginal_total_variation"]
    run_marginal = summary["partitions"]["physical_run"]["group_marginal_total_variation"]
    hard = {
        "latest_equals_fixed_snapshot": True,
        "population_loader_rechecked_original_contract": True,
        "upstream_receipt_hash_classification_snapshot_and_counts_match": True,
        "recomputed_overall_edge_tv_matches_exact_upstream_fraction": summary["overall_edge_total_variation"]
        == encoded(ratio(disclosed["overall_edge_total_variation"])),
        "recomputed_task_marginal_tv_roundtrips_to_disclosed_17g": task_marginal["decimal_17g"]
        == disclosed["task_marginal_total_variation_decimal_17g"],
        "recomputed_run_marginal_tv_roundtrips_to_disclosed_17g": run_marginal["decimal_17g"]
        == disclosed["physical_run_marginal_total_variation_decimal_17g"],
        "edge_and_occurrence_counts_match_upstream": summary["inventory"]["observed_unique_edges"]
        == linear["inventory"]["observed_unique_edges"]
        and summary["inventory"]["path_edge_occurrences"]
        == linear["linearization"]["branch_linearized_edge_occurrences"],
        **summary["support_checks"],
    }
    expected_classification = classify(summary, protocol, hard)
    deep_equal({**source_hashes, **population_bindings}, receipt.get("input_bindings"), "input_bindings")
    deep_equal(
        {**summary["inventory"], **graph_inventory, "eligible_endpoints": len(cards), "physical_runs": len(runs)},
        receipt.get("inventory"),
        "inventory",
    )
    deep_equal(summary["overall_edge_total_variation"], receipt.get("overall_edge_total_variation"), "overall TV")
    deep_equal(summary["partitions"], receipt.get("partitions"), "partitions")
    deep_equal(
        {
            "hard_integrity_and_support": hard,
            "all_hard_gates_passed": all(hard.values()),
            "axis_strength": summary["axis_strength"],
            "fixed_thresholds": protocol["strong_positive_gates"],
        },
        receipt.get("pre_registered_gate"),
        "gates",
    )
    deep_equal(expected_classification, receipt.get("classification"), "classification")
    deep_equal(protocol["design_timing"], receipt.get("design_timing"), "design timing")
    deep_equal(protocol["claim_boundary"], receipt.get("claim_boundary"), "claim boundary")
    expected_security = {
        "allowed_input_basenames": protocol["security"]["allowed_input_basenames"],
        "raw_senior_archives_opened": False,
        "prospective_label_grade_outcome_prediction_values_read": False,
        "task_run_card_parent_code_or_per_edge_values_emitted": False,
        "accuracy_effect_or_search_utility_computed": False,
        "gpu_api_model_fit_base_update": [0, 0, 0, 0],
    }
    deep_equal(expected_security, receipt.get("security"), "security")
    check(receipt.get("population_loader_source_sha256") == digest(repo_root / "phase1" / "audit_prospective_tree_linearization_weights.py"), "population loader hash")
    return {
        "protocol": VERIFY_PROTOCOL,
        "status": "INDEPENDENT_WITHIN_STRATUM_DECOMPOSITION_PASS",
        "classification": expected_classification,
        "snapshot_sha256": protocol["fixed_population"]["snapshot_sha256"],
        "receipt_sha256": receipt_sha,
        "producer_source_sha256": producer_source_sha,
        "observed_unique_edges": summary["inventory"]["observed_unique_edges"],
        "path_edge_occurrences": summary["inventory"]["path_edge_occurrences"],
        "task_canonical_standardized_within_total_variation": summary["partitions"]["task"][
            "canonical_marginal_standardized_within_total_variation"
        ],
        "physical_run_canonical_standardized_within_total_variation": summary["partitions"]["physical_run"][
            "canonical_marginal_standardized_within_total_variation"
        ],
        "all_hard_gates_passed": all(hard.values()),
        "checks": {
            "fixed_inputs_rehashed": True,
            "blind_population_independently_reconstructed": True,
            "graph_and_multiplicities_independently_reconstructed": True,
            "exact_partition_metrics_independently_recomputed": True,
            "classification_independently_recomputed": True,
            "identity_free_contract_exact": True,
        },
        "security": {
            "imports_new_producer": False,
            "prospective_label_grade_outcome_prediction_values_read": False,
            "task_run_card_parent_code_or_per_edge_values_emitted": False,
            "gpu_api_model_fit_base_update": [0, 0, 0, 0],
        },
    }


def write_once(path: Path, value: dict[str, Any]) -> None:
    check(not path.exists(), "refusing to overwrite output")
    check(path.parent.is_dir() and not path.parent.is_symlink(), "unsafe output parent")
    temporary = path.with_name(path.name + f".tmp-{os.getpid()}")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-root", required=True, type=Path)
    parser.add_argument("--snapshot-root", required=True, type=Path)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--expect-protocol-sha256", required=True)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--expect-receipt-sha256", required=True)
    parser.add_argument("--producer-source", required=True, type=Path)
    parser.add_argument("--expect-producer-source-sha256", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = verify(
            args.state_root,
            args.snapshot_root,
            args.repo_root,
            args.protocol,
            args.expect_protocol_sha256,
            args.receipt,
            args.expect_receipt_sha256,
            args.producer_source,
            args.expect_producer_source_sha256,
            args.source_commit,
        )
        write_once(args.out.resolve(), result)
    except (VerificationError, OSError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}")
        return 2
    print(result["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
