#!/usr/bin/env python3
"""Outcome-blind within-task/run decomposition of tree-linearization distortion."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import os
import platform
import re
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable

from phase1 import audit_prospective_tree_linearization_weights as population_loader


PROTOCOL_NAME = "tree-linearization-within-stratum-decomposition-v1"
RECEIPT_PROTOCOL = "tree-linearization-within-stratum-decomposition-receipt-v1"
RECEIPT_STATUS = "OUTCOME_BLIND_WITHIN_STRATUM_DECOMPOSITION_COMPLETE"
SHA_RE = re.compile(r"[0-9a-f]{64}")


class DecompositionError(RuntimeError):
    """Raised when any frozen input or exact identity fails."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise DecompositionError(message)


def sha256_file(path: Path) -> str:
    require(path.is_file() and not path.is_symlink(), f"unsafe file: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def read_object(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"unsafe JSON: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON root is not an object: {path}")
    return value


def valid_sha(value: Any, label: str) -> str:
    require(isinstance(value, str) and SHA_RE.fullmatch(value) is not None, f"invalid {label}")
    return value


def repo_file(repo_root: Path, relative: str) -> Path:
    candidate = Path(relative)
    require(not candidate.is_absolute() and ".." not in candidate.parts, f"unsafe path: {relative}")
    root = repo_root.resolve()
    raw = root / candidate
    require(not raw.is_symlink(), f"symlink input: {relative}")
    resolved = raw.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise DecompositionError(f"path escapes repository: {relative}") from error
    require(resolved.is_file(), f"missing input: {relative}")
    return resolved


def parse_ratio(value: str) -> Fraction:
    require(isinstance(value, str) and value, "invalid ratio")
    try:
        result = Fraction(value)
    except (ValueError, ZeroDivisionError) as error:
        raise DecompositionError(f"invalid exact ratio: {value}") from error
    require(result >= 0, "negative ratio")
    return result


def exact(value: Fraction) -> dict[str, Any]:
    return {
        "numerator": value.numerator,
        "denominator": value.denominator,
        "decimal_17g": format(float(value), ".17g"),
    }


def exact_from_payload(value: Any, label: str) -> Fraction:
    require(isinstance(value, dict), f"missing exact payload: {label}")
    numerator, denominator = value.get("numerator"), value.get("denominator")
    require(
        isinstance(numerator, int)
        and not isinstance(numerator, bool)
        and isinstance(denominator, int)
        and not isinstance(denominator, bool)
        and denominator > 0,
        f"invalid exact payload: {label}",
    )
    result = Fraction(numerator, denominator)
    require(value == exact(result), f"noncanonical exact payload: {label}")
    return result


def median(values: list[Fraction]) -> Fraction:
    require(bool(values), "empty median")
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def nearest_rank(values: list[Fraction], probability: Fraction) -> Fraction:
    require(bool(values) and 0 < probability <= 1, "invalid quantile")
    ordered = sorted(values)
    rank = (probability.numerator * len(ordered) + probability.denominator - 1) // probability.denominator
    return ordered[max(1, rank) - 1]


def total_variation(first: Iterable[Fraction], second: Iterable[Fraction]) -> Fraction:
    left, right = list(first), list(second)
    require(len(left) == len(right) and bool(left), "invalid TV vectors")
    require(sum(left, Fraction()) == 1 and sum(right, Fraction()) == 1, "TV vectors not normalized")
    return sum((abs(a - b) for a, b in zip(left, right)), Fraction()) / 2


def observed_edges(cards: dict[str, dict[str, Any]]) -> tuple[list[tuple[str, str, int]], dict[str, int]]:
    children: dict[str, list[str]] = {identifier: [] for identifier in cards}
    parent_of: dict[str, str] = {}
    roots: list[str] = []
    for child_id, child in cards.items():
        parent_id = child["parent"]
        if parent_id not in cards:
            roots.append(child_id)
            continue
        parent = cards[parent_id]
        require(parent_id != child_id, "self-parent edge")
        require(parent["run"] == child["run"], "observed edge crosses physical runs")
        require(parent["task"] == child["task"], "observed edge crosses tasks")
        parent_of[child_id] = parent_id
        children[parent_id].append(child_id)

    state: dict[str, int] = {}
    for start in cards:
        trail: list[str] = []
        cursor = start
        while cursor in parent_of and state.get(cursor, 0) == 0:
            state[cursor] = 1
            trail.append(cursor)
            cursor = parent_of[cursor]
        require(state.get(cursor, 0) != 1, "observed graph contains a cycle")
        for node in trail:
            state[node] = 2
    require(bool(roots), "observed graph has no fragment roots")

    leaf_count: dict[str, int] = {}
    stack: list[tuple[str, bool]] = [(root, False) for root in sorted(roots)]
    while stack:
        node, expanded = stack.pop()
        if expanded:
            descendants = children[node]
            leaf_count[node] = 1 if not descendants else sum(leaf_count[child] for child in descendants)
        else:
            stack.append((node, True))
            stack.extend((child, False) for child in children[node])
    require(len(leaf_count) == len(cards), "not all endpoints belong to observed fragments")

    edges: list[tuple[str, str, int]] = []
    for child_id in sorted(parent_of):
        card = cards[child_id]
        multiplicity = leaf_count[child_id]
        require(multiplicity >= 1, "invalid edge multiplicity")
        edges.append((card["task"], card["run"], multiplicity))
    require(bool(edges), "no observed edges")
    return edges, {
        "fragment_roots": len(roots),
        "fragment_leaves": sum(not children[node] for node in cards),
        "single_node_fragments": sum(not children[root] for root in roots),
    }


def conditional_tv(multiplicities: list[int]) -> Fraction:
    edge_count = len(multiplicities)
    occurrence_count = sum(multiplicities)
    require(edge_count > 0 and occurrence_count >= edge_count, "invalid group multiplicities")
    return sum(
        (abs(Fraction(1, edge_count) - Fraction(value, occurrence_count)) for value in multiplicities),
        Fraction(),
    ) / 2


def histogram(values: list[Fraction], edges: list[Fraction]) -> list[int]:
    require(len(edges) >= 2 and edges == sorted(set(edges)) and edges[0] == 0 and edges[-1] == 1, "invalid bins")
    counts = [0] * (len(edges) - 1)
    for value in values:
        require(0 <= value <= 1, "conditional TV outside [0,1]")
        for index, (lower, upper) in enumerate(zip(edges, edges[1:])):
            if lower <= value < upper or (index == len(counts) - 1 and value == upper):
                counts[index] += 1
                break
        else:
            raise DecompositionError("conditional TV not assigned to a bin")
    require(sum(counts) == len(values), "histogram count mismatch")
    return counts


def axis_profile(
    edges: list[tuple[str, str, int]],
    axis_index: int,
    overall_tv: Fraction,
    protocol: dict[str, Any],
) -> dict[str, Any]:
    groups: dict[str, list[int]] = collections.defaultdict(list)
    for edge in edges:
        groups[edge[axis_index]].append(edge[2])
    edge_total = len(edges)
    occurrence_total = sum(edge[2] for edge in edges)
    ordered = sorted(groups)
    edge_counts = [len(groups[group]) for group in ordered]
    occurrence_counts = [sum(groups[group]) for group in ordered]
    marginal_tv = total_variation(
        [Fraction(value, edge_total) for value in edge_counts],
        [Fraction(value, occurrence_total) for value in occurrence_counts],
    )
    conditional = {group: conditional_tv(groups[group]) for group in ordered}
    canonical_contributions = {
        group: Fraction(len(groups[group]), edge_total) * conditional[group] for group in ordered
    }
    path_contributions = {
        group: Fraction(sum(groups[group]), occurrence_total) * conditional[group] for group in ordered
    }
    canonical_within = sum(canonical_contributions.values(), Fraction())
    path_within = sum(path_contributions.values(), Fraction())
    triangle_lower = max(Fraction(), overall_tv - marginal_tv)
    triangle_slack = canonical_within - triangle_lower
    require(triangle_slack >= 0, "canonical within TV violates triangle lower bound")

    conditionable = [group for group in ordered if len(groups[group]) >= 2]
    values = [conditional[group] for group in conditionable]
    require(bool(values), "no conditionable groups")
    summary_spec = protocol["fixed_distribution_summary"]
    reference = parse_ratio(summary_spec["conditional_tv_reference"])
    at_reference = sum(value >= reference for value in values)
    breadth = Fraction(at_reference, len(values))
    bin_edges = [parse_ratio(value) for value in summary_spec["histogram_edges"]]
    maximum_contribution_share = (
        max(canonical_contributions.values()) / canonical_within if canonical_within else Fraction()
    )

    gates = protocol["strong_positive_gates"]
    axis_name = "task" if axis_index == 0 else "physical_run"
    breadth_threshold = parse_ratio(
        gates[
            "minimum_task_fraction_at_or_above_conditional_tv_reference"
            if axis_name == "task"
            else "minimum_physical_run_fraction_at_or_above_conditional_tv_reference"
        ]
    )
    dominance_threshold = parse_ratio(
        gates[
            "maximum_single_task_canonical_contribution_share"
            if axis_name == "task"
            else "maximum_single_physical_run_canonical_contribution_share"
        ]
    )
    within_floor = parse_ratio(
        gates[
            "minimum_task_canonical_standardized_within_tv_integrity_floor"
            if axis_name == "task"
            else "minimum_physical_run_canonical_standardized_within_tv_integrity_floor"
        ]
    )
    strong_checks = {
        "canonical_standardized_within_tv_at_least_integrity_floor": canonical_within
        >= within_floor,
        "breadth_fraction_at_least_minimum": breadth >= breadth_threshold,
        "maximum_contribution_share_at_most_maximum": maximum_contribution_share
        <= dominance_threshold,
    }
    return {
        "groups_with_observed_edges": len(groups),
        "conditionable_groups": len(conditionable),
        "group_marginal_total_variation": exact(marginal_tv),
        "canonical_marginal_standardized_within_total_variation": exact(canonical_within),
        "path_marginal_standardized_within_total_variation_secondary": exact(path_within),
        "triangle_lower_bound": exact(triangle_lower),
        "exact_slack_above_triangle_lower_bound": exact(triangle_slack),
        "anonymous_conditionable_group_distribution": {
            "reference": exact(reference),
            "groups_at_or_above_reference": at_reference,
            "fraction_at_or_above_reference": exact(breadth),
            "histogram": {
                "edges": [exact(value) for value in bin_edges],
                "counts": histogram(values, bin_edges),
                "last_bin_right_closed": True,
            },
            "median": exact(median(values)),
            "p90_nearest_rank": exact(nearest_rank(values, Fraction(9, 10))),
            "maximum": exact(max(values)),
        },
        "maximum_anonymous_canonical_contribution_share": exact(maximum_contribution_share),
        "strong_positive_gate": {
            "checks": strong_checks,
            "all_passed": all(strong_checks.values()),
            "within_tv_integrity_floor": exact(within_floor),
            "breadth_threshold": exact(breadth_threshold),
            "dominance_threshold": exact(dominance_threshold),
            "triangle_slack_is_diagnostic_only": True,
        },
    }


def summarize_edges(
    edges: list[tuple[str, str, int]], protocol: dict[str, Any]
) -> dict[str, Any]:
    require(bool(edges), "empty edge list")
    edge_total = len(edges)
    occurrence_total = sum(edge[2] for edge in edges)
    require(all(isinstance(value, int) and value >= 1 for _, _, value in edges), "invalid multiplicity")
    overall_tv = total_variation(
        [Fraction(1, edge_total) for _ in edges],
        [Fraction(edge[2], occurrence_total) for edge in edges],
    )
    task = axis_profile(edges, 0, overall_tv, protocol)
    run = axis_profile(edges, 1, overall_tv, protocol)
    hard_spec = protocol["hard_integrity_and_support_gates"]
    support_checks = {
        "conditionable_tasks_at_least_minimum": task["conditionable_groups"]
        >= hard_spec["minimum_conditionable_tasks"],
        "conditionable_physical_runs_at_least_minimum": run["conditionable_groups"]
        >= hard_spec["minimum_conditionable_physical_runs"],
    }
    task_strong = task["strong_positive_gate"]["all_passed"]
    run_strong = run["strong_positive_gate"]["all_passed"]
    return {
        "inventory": {
            "observed_unique_edges": edge_total,
            "path_edge_occurrences": occurrence_total,
            "duplicate_edge_occurrences": occurrence_total - edge_total,
            "tasks_with_observed_edges": task["groups_with_observed_edges"],
            "physical_runs_with_observed_edges": run["groups_with_observed_edges"],
        },
        "overall_edge_total_variation": exact(overall_tv),
        "partitions": {"task": task, "physical_run": run},
        "support_checks": support_checks,
        "provisional_axis_strength": {"task": task_strong, "physical_run": run_strong},
    }


def load_protocol(path: Path, expected_sha: str) -> tuple[dict[str, Any], str]:
    actual = sha256_file(path)
    require(actual == expected_sha, "protocol SHA mismatch")
    protocol = read_object(path)
    require(protocol.get("protocol") == PROTOCOL_NAME, "protocol name mismatch")
    require(
        protocol.get("status") == "OUTCOME_BLIND_PROTOCOL_FROZEN_BEFORE_WITHIN_STRATUM_AGGREGATES",
        "protocol status mismatch",
    )
    require(protocol.get("design_timing", {}).get("new_within_task_or_within_run_values_seen") is False, "design timing mismatch")
    return protocol, actual


def fixed_inputs(repo_root: Path, protocol: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, str]]:
    fixed = protocol["fixed_inputs"]
    paths: dict[str, Path] = {}
    values: dict[str, dict[str, Any]] = {}
    for name in ("population_protocol", "linearization_receipt", "estimand_sensitivity_receipt"):
        spec = fixed[name]
        path = repo_file(repo_root, spec["path"])
        expected_sha = valid_sha(spec["sha256"], f"{name} SHA")
        require(sha256_file(path) == expected_sha, f"{name} SHA mismatch")
        paths[name] = path
        values[name] = read_object(path)

    population_protocol = values["population_protocol"]
    linearization = values["linearization_receipt"]
    sensitivity = values["estimand_sensitivity_receipt"]
    snapshot = protocol["fixed_population"]["snapshot_sha256"]
    require(population_protocol.get("protocol") == "prospective-tree-linearization-weight-audit-v1", "population protocol mismatch")
    require(population_protocol.get("fixed_snapshot", {}).get("sha256") == snapshot, "population snapshot mismatch")
    require(linearization.get("classification") == fixed["linearization_receipt"]["required_classification"], "linearization classification mismatch")
    require(sensitivity.get("classification") == fixed["estimand_sensitivity_receipt"]["required_classification"], "sensitivity classification mismatch")
    require(linearization.get("snapshot_sha256") == sensitivity.get("snapshot_sha256") == snapshot, "upstream snapshot mismatch")
    require(linearization.get("pre_registered_gate", {}).get("all_hard_gates_passed") is True, "upstream hard gate failed")
    require(linearization.get("inventory", {}).get("observed_unique_edges") == protocol["disclosed_pre_freeze_values"]["canonical_unique_edges"], "upstream edge count mismatch")
    require(linearization.get("linearization", {}).get("branch_linearized_edge_occurrences") == protocol["disclosed_pre_freeze_values"]["path_edge_occurrences"], "upstream occurrence count mismatch")
    sensitivity_tv = exact_from_payload(
        sensitivity.get("edge_measure_shift", {}).get("total_variation"), "sensitivity total variation"
    )
    require(
        sensitivity_tv == parse_ratio(protocol["disclosed_pre_freeze_values"]["overall_edge_total_variation"]),
        "upstream overall TV mismatch",
    )
    return population_protocol, linearization, sensitivity, {
        name: sha256_file(path) for name, path in paths.items()
    }


def final_classification(summary: dict[str, Any], protocol: dict[str, Any], hard_checks: dict[str, bool]) -> str:
    if not all(hard_checks.values()):
        result = "WITHIN_STRATUM_DECOMPOSITION_GATE_FAIL"
    else:
        task_strong = summary["provisional_axis_strength"]["task"]
        run_strong = summary["provisional_axis_strength"]["physical_run"]
        task_tv = exact_from_payload(
            summary["partitions"]["task"]["canonical_marginal_standardized_within_total_variation"],
            "task within TV",
        )
        run_tv = exact_from_payload(
            summary["partitions"]["physical_run"]["canonical_marginal_standardized_within_total_variation"],
            "run within TV",
        )
        if task_strong and run_strong:
            result = "BROAD_NONCOMPOSITIONAL_LINEARIZATION_DISTORTION"
        elif task_strong:
            result = "TASK_ONLY_BROAD_NONCOMPOSITIONAL_LINEARIZATION_DISTORTION"
        elif run_strong:
            result = "RUN_ONLY_BROAD_NONCOMPOSITIONAL_LINEARIZATION_DISTORTION"
        elif task_tv > 0 or run_tv > 0:
            result = "WITHIN_STRATUM_PROFILE_BELOW_STRONG_GATE"
        else:
            result = "NO_OBSERVED_WITHIN_STRATUM_DISTORTION"
    require(result in protocol["ordered_classification"], "classification outside protocol")
    return result


def build_receipt(
    state_root: Path,
    snapshot_root: Path,
    repo_root: Path,
    protocol_path: Path,
    protocol_sha: str,
    source_commit: str,
) -> dict[str, Any]:
    require(re.fullmatch(r"[0-9a-f]{40}", source_commit) is not None, "invalid source commit")
    protocol, actual_protocol_sha = load_protocol(protocol_path, protocol_sha)
    population_protocol, linearization, _sensitivity, source_hashes = fixed_inputs(repo_root, protocol)
    try:
        cards, runs, population_bindings = population_loader.load_population(
            state_root, snapshot_root, population_protocol
        )
    except population_loader.AuditError as error:
        raise DecompositionError(f"population loader failed: {error}") from error
    edges, graph_inventory = observed_edges(cards)
    summary = summarize_edges(edges, protocol)

    disclosed = protocol["disclosed_pre_freeze_values"]
    task_marginal = summary["partitions"]["task"]["group_marginal_total_variation"]
    run_marginal = summary["partitions"]["physical_run"]["group_marginal_total_variation"]
    upstream_checks = {
        "latest_equals_fixed_snapshot": True,
        "population_loader_rechecked_original_contract": True,
        "upstream_receipt_hash_classification_snapshot_and_counts_match": True,
        "recomputed_overall_edge_tv_matches_exact_upstream_fraction": summary[
            "overall_edge_total_variation"
        ]
        == exact(parse_ratio(disclosed["overall_edge_total_variation"])),
        "recomputed_task_marginal_tv_roundtrips_to_disclosed_17g": task_marginal[
            "decimal_17g"
        ]
        == disclosed["task_marginal_total_variation_decimal_17g"],
        "recomputed_run_marginal_tv_roundtrips_to_disclosed_17g": run_marginal[
            "decimal_17g"
        ]
        == disclosed["physical_run_marginal_total_variation_decimal_17g"],
        "edge_and_occurrence_counts_match_upstream": summary["inventory"][
            "observed_unique_edges"
        ]
        == linearization["inventory"]["observed_unique_edges"]
        and summary["inventory"]["path_edge_occurrences"]
        == linearization["linearization"]["branch_linearized_edge_occurrences"],
        **summary["support_checks"],
    }
    classification = final_classification(summary, protocol, upstream_checks)
    return {
        "protocol": RECEIPT_PROTOCOL,
        "status": RECEIPT_STATUS,
        "classification": classification,
        "snapshot_sha256": protocol["fixed_population"]["snapshot_sha256"],
        "protocol_sha256": actual_protocol_sha,
        "source_commit": source_commit,
        "producer_source_sha256": sha256_file(Path(__file__)),
        "population_loader_source_sha256": sha256_file(Path(population_loader.__file__)),
        "input_bindings": {**source_hashes, **population_bindings},
        "inventory": {**summary["inventory"], **graph_inventory, "eligible_endpoints": len(cards), "physical_runs": len(runs)},
        "overall_edge_total_variation": summary["overall_edge_total_variation"],
        "partitions": summary["partitions"],
        "pre_registered_gate": {
            "hard_integrity_and_support": upstream_checks,
            "all_hard_gates_passed": all(upstream_checks.values()),
            "axis_strength": summary["provisional_axis_strength"],
            "fixed_thresholds": protocol["strong_positive_gates"],
        },
        "design_timing": protocol["design_timing"],
        "claim_boundary": protocol["claim_boundary"],
        "security": {
            "allowed_input_basenames": protocol["security"]["allowed_input_basenames"],
            "raw_senior_archives_opened": False,
            "prospective_label_grade_outcome_prediction_values_read": False,
            "task_run_card_parent_code_or_per_edge_values_emitted": False,
            "accuracy_effect_or_search_utility_computed": False,
            "gpu_api_model_fit_base_update": [0, 0, 0, 0],
        },
        "reproducibility": {"python_version": platform.python_version(), "randomness_used": False},
    }


def write_new(path: Path, value: dict[str, Any]) -> None:
    require(not path.exists(), "refusing to overwrite output")
    require(path.parent.is_dir() and not path.parent.is_symlink(), "unsafe output parent")
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
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    try:
        receipt = build_receipt(
            args.state_root,
            args.snapshot_root,
            args.repo_root,
            args.protocol,
            args.expect_protocol_sha256,
            args.source_commit,
        )
        write_new(args.out.resolve(), receipt)
    except (DecompositionError, OSError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}")
        return 2
    print(receipt["classification"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
