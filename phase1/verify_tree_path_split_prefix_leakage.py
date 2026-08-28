#!/usr/bin/env python3
"""Independent verifier for the outcome-blind path-split prefix-leakage audit."""

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
from typing import Any

from phase1 import verify_prospective_tree_linearization_weights as blind_reader


PROTOCOL_NAME = "tree-path-split-prefix-leakage-v1"
RECEIPT_PROTOCOL = "tree-path-split-prefix-leakage-receipt-v1"
VERIFY_PROTOCOL = "independent-tree-path-split-prefix-leakage-verifier-v1"
SHA64 = re.compile(r"[0-9a-f]{64}")
SHA40 = re.compile(r"[0-9a-f]{40}")


class VerificationError(RuntimeError):
    """Raised on any independently reconstructed mismatch."""


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


def repository_path(repo_root: Path, relative: str) -> Path:
    component = Path(relative)
    check(not component.is_absolute() and ".." not in component.parts, f"unsafe path: {relative}")
    root = repo_root.resolve()
    raw = root / component
    check(not raw.is_symlink(), f"symlink input: {relative}")
    candidate = raw.resolve()
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise VerificationError(f"repository escape: {relative}") from error
    check(candidate.is_file(), f"missing fixed input: {relative}")
    return candidate


def ratio(text: Any) -> Fraction:
    check(isinstance(text, str) and bool(text), "invalid ratio text")
    try:
        value = Fraction(text)
    except (ValueError, ZeroDivisionError) as error:
        raise VerificationError(f"invalid ratio: {text}") from error
    check(0 <= value <= 1, "ratio outside [0,1]")
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


def middle(values: list[Fraction]) -> Fraction:
    check(bool(values), "empty median")
    rows = sorted(values)
    pivot = len(rows) // 2
    return rows[pivot] if len(rows) % 2 else (rows[pivot - 1] + rows[pivot]) / 2


def rank_nine_tenths(values: list[Fraction]) -> Fraction:
    check(bool(values), "empty quantile")
    rows = sorted(values)
    rank = (9 * len(rows) + 9) // 10
    return rows[max(1, rank) - 1]


def bin_counts(values: list[Fraction], boundaries: list[Fraction]) -> list[int]:
    check(
        len(boundaries) >= 2
        and boundaries == sorted(set(boundaries))
        and boundaries[0] == 0
        and boundaries[-1] == 1,
        "invalid bins",
    )
    counts = [0 for _ in range(len(boundaries) - 1)]
    for value in values:
        check(0 <= value <= 1, "value outside bins")
        assigned = False
        for index in range(len(counts)):
            lower, upper = boundaries[index], boundaries[index + 1]
            if lower <= value < upper or (index == len(counts) - 1 and value == upper):
                counts[index] += 1
                assigned = True
                break
        check(assigned, "value not binned")
    check(sum(counts) == len(values), "bin count mismatch")
    return counts


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


def fixed_sources(
    repo_root: Path, protocol: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, str]]:
    values: dict[str, dict[str, Any]] = {}
    hashes: dict[str, str] = {}
    for name in (
        "tree_population_protocol",
        "tree_linearization_receipt",
        "tree_native_contract",
        "tree_native_receipt",
    ):
        spec = protocol["fixed_inputs"][name]
        expected = spec.get("sha256")
        check(isinstance(expected, str) and SHA64.fullmatch(expected) is not None, f"invalid {name} SHA")
        path = repository_path(repo_root, spec["path"])
        hashes[name] = digest(path)
        check(hashes[name] == expected, f"{name} SHA mismatch")
        values[name] = object_at(path)

    population = values["tree_population_protocol"]
    linear = values["tree_linearization_receipt"]
    native_contract = values["tree_native_contract"]
    native = values["tree_native_receipt"]
    snapshot = protocol["fixed_population"]["snapshot_sha256"]
    check(population.get("protocol") == "prospective-tree-linearization-weight-audit-v1", "population protocol")
    check(population.get("fixed_snapshot", {}).get("sha256") == snapshot, "population snapshot")
    check(linear.get("classification") == protocol["fixed_inputs"]["tree_linearization_receipt"]["required_classification"], "linear classification")
    check(native_contract.get("protocol") == "tree-native-path-compatibility-contract-v1", "native contract")
    check(native.get("classification") == protocol["fixed_inputs"]["tree_native_receipt"]["required_classification"], "native classification")
    check(linear.get("snapshot_sha256") == native.get("snapshot_sha256") == snapshot, "upstream snapshot")
    check(linear.get("pre_registered_gate", {}).get("all_hard_gates_passed") is True, "linear gate")
    check(native.get("all_verification_gates_passed") is True, "native gate")
    return population, linear, native, hashes


def independently_reconstruct(
    cards: dict[str, dict[str, Any]],
) -> tuple[list[tuple[str, str, str, int]], dict[str, Any], dict[str, bool]]:
    parent: dict[str, str] = {}
    children: dict[str, list[str]] = {identifier: [] for identifier in cards}
    roots: set[str] = set()
    for identifier, row in cards.items():
        ancestor = row["parent"]
        if ancestor not in cards:
            roots.add(identifier)
            continue
        check(ancestor != identifier, "self-parent edge")
        check(cards[ancestor]["run"] == row["run"], "cross-run edge")
        check(cards[ancestor]["task"] == row["task"], "cross-task edge")
        parent[identifier] = ancestor
        children[ancestor].append(identifier)
    check(bool(roots), "no fragment roots")

    unresolved = set(cards)
    leaves_below: dict[str, int] = {}
    while unresolved:
        ready = sorted(
            node for node in unresolved if all(child in leaves_below for child in children[node])
        )
        check(bool(ready), "cycle or unresolved component")
        for node in ready:
            leaves_below[node] = (
                1 if not children[node] else sum(leaves_below[child] for child in children[node])
            )
            unresolved.remove(node)

    root_for: dict[str, str] = {}
    for node in cards:
        trail: list[str] = []
        cursor = node
        while cursor not in roots and cursor not in root_for:
            check(cursor in parent, "node does not reach a root")
            trail.append(cursor)
            cursor = parent[cursor]
        root = root_for.get(cursor, cursor)
        check(root in roots, "root resolution failed")
        root_for[node] = root
        for member in trail:
            root_for[member] = root
    check(len(root_for) == len(cards), "fragment assignment incomplete")

    leaves = sorted(node for node in cards if not children[node])
    occurrence_count: collections.Counter[str] = collections.Counter()
    unique_within_path = True
    bound_within_path = True
    for leaf in leaves:
        reversed_nodes = [leaf]
        cursor = leaf
        while cursor in parent:
            cursor = parent[cursor]
            reversed_nodes.append(cursor)
        path = list(reversed(reversed_nodes))
        edges = path[1:]
        unique_within_path = unique_within_path and len(edges) == len(set(edges))
        bound_within_path = bound_within_path and len({cards[node]["task"] for node in path}) == 1
        bound_within_path = bound_within_path and len({cards[node]["run"] for node in path}) == 1
        for ancestor, child in zip(path, path[1:]):
            check(parent.get(child) == ancestor, "path continuity mismatch")
            occurrence_count[child] += 1

    rows = [
        (cards[child]["task"], cards[child]["run"], root_for[child], leaves_below[child])
        for child in sorted(parent)
    ]
    check(bool(rows), "no canonical edges")
    counts_match = set(occurrence_count) == set(parent) and all(
        occurrence_count[child] == leaves_below[child] for child in parent
    )
    return rows, {
        "eligible_endpoints": len(cards),
        "observed_fragments": len(roots),
        "fragments_with_observed_edges": len({row[2] for row in rows}),
        "single_node_fragments": sum(not children[root] for root in roots),
        "root_to_leaf_path_records": len(leaves),
        "canonical_observed_edges": len(rows),
        "path_edge_occurrences": sum(row[3] for row in rows),
        "tasks": len({row[0] for row in rows}),
        "physical_runs": len({row[1] for row in rows}),
    }, {
        "each_path_contains_a_canonical_edge_at_most_once": unique_within_path,
        "paths_are_fragment_task_and_run_bound": bound_within_path,
        "enumerated_edge_occurrences_equal_descendant_leaf_multiplicity": counts_match,
        "each_edge_has_exactly_one_fragment_task_and_physical_run": True,
    }


def falling_subset_probability(total: int, subset: int, chosen: int) -> Fraction:
    check(total >= 1 and 0 <= subset <= total and chosen >= 0, "bad combinatoric arguments")
    if chosen > subset:
        return Fraction()
    result = Fraction(1)
    for offset in range(chosen):
        result *= Fraction(subset - offset, total - offset)
    return result


def independently_compute_terms(
    total: int, train: int, validation: int, test: int, multiplicity: int
) -> dict[str, Fraction]:
    check(min(train, validation, test) >= 0 and train + validation + test == total, "bad split")
    check(1 <= multiplicity <= total, "bad multiplicity")
    absent_train = falling_subset_probability(total, validation + test, multiplicity)
    absent_test = falling_subset_probability(total, train + validation, multiplicity)
    only_validation = falling_subset_probability(total, validation, multiplicity)
    both = 1 - absent_train - absent_test + only_validation
    present_test = 1 - absent_test
    no_train_among_peers = falling_subset_probability(
        total - 1, total - 1 - train, multiplicity - 1
    )
    test_rows = Fraction(multiplicity * test, total)
    leaked_rows = test_rows * (1 - no_train_among_peers)
    check(0 <= both <= present_test <= 1, "invalid overlap")
    check(0 <= leaked_rows <= test_rows, "invalid row expectation")
    return {
        "train_test_overlap": both,
        "appears_in_test": present_test,
        "expected_test_occurrences": test_rows,
        "expected_contaminated_test_occurrences": leaked_rows,
    }


def independently_global(
    rows: list[tuple[str, str, str, int]], protocol: dict[str, Any]
) -> tuple[dict[str, Any], dict[int, dict[str, Fraction]]]:
    split = protocol["split_design"]
    train, validation, test = split["train_paths"], split["validation_paths"], split["test_paths"]
    total = train + validation + test
    terms = {
        m: independently_compute_terms(total, train, validation, test, m)
        for m in sorted({row[3] for row in rows})
    }
    overlap = sum((terms[row[3]]["train_test_overlap"] for row in rows), Fraction())
    unique_test = sum((terms[row[3]]["appears_in_test"] for row in rows), Fraction())
    test_rows = sum((terms[row[3]]["expected_test_occurrences"] for row in rows), Fraction())
    leaked_rows = sum(
        (terms[row[3]]["expected_contaminated_test_occurrences"] for row in rows),
        Fraction(),
    )
    check(unique_test > 0 and test_rows > 0, "zero test support")
    return {
        "split_sizes": {
            "root_to_leaf_path_records": total,
            "train": train,
            "validation": validation,
            "test": test,
        },
        "expected_train_test_cross_split_canonical_edges": encoded(overlap),
        "canonical_edge_overlap_fraction": encoded(overlap / len(rows)),
        "expected_unique_test_canonical_edges": encoded(unique_test),
        "unique_test_edge_contamination_ratio_of_expectations": encoded(overlap / unique_test),
        "expected_test_path_edge_occurrences": encoded(test_rows),
        "expected_contaminated_test_path_edge_occurrences": encoded(leaked_rows),
        "test_occurrence_contamination_ratio_of_expectations": encoded(leaked_rows / test_rows),
        "train_validation_identical_by_equal_split_size": validation == test,
    }, terms


def independently_group(
    rows: list[tuple[str, str, str, int]],
    column: int,
    terms: dict[int, dict[str, Fraction]],
    global_leaked_rows: Fraction,
    protocol: dict[str, Any],
    gated: bool,
) -> dict[str, Any]:
    groups: dict[str, list[int]] = collections.defaultdict(list)
    for row in rows:
        groups[row[column]].append(row[3])
    ratios: list[Fraction] = []
    numerators: list[Fraction] = []
    for name in sorted(groups):
        denominator = sum(
            (terms[m]["expected_test_occurrences"] for m in groups[name]), Fraction()
        )
        numerator = sum(
            (terms[m]["expected_contaminated_test_occurrences"] for m in groups[name]),
            Fraction(),
        )
        check(denominator > 0, "zero group denominator")
        ratios.append(numerator / denominator)
        numerators.append(numerator)
    check(
        bool(ratios) and sum(numerators, Fraction()) == global_leaked_rows,
        "group decomposition mismatch",
    )
    spec = protocol["fixed_distribution_summary"]
    reference = ratio(spec["group_ratio_reference"])
    boundaries = [ratio(value) for value in spec["histogram_edges"]]
    count = sum(value >= reference for value in ratios)
    breadth = Fraction(count, len(ratios))
    max_share = max(numerators) / global_leaked_rows if global_leaked_rows else Fraction()
    output: dict[str, Any] = {
        "conditionable_groups": len(ratios),
        "anonymous_group_distribution": {
            "reference": encoded(reference),
            "groups_at_or_above_reference": count,
            "fraction_at_or_above_reference": encoded(breadth),
            "histogram": {
                "edges": [encoded(value) for value in boundaries],
                "counts": bin_counts(ratios, boundaries),
                "last_bin_right_closed": True,
            },
            "median": encoded(middle(ratios)),
            "p90_nearest_rank": encoded(rank_nine_tenths(ratios)),
            "maximum": encoded(max(ratios)),
        },
        "maximum_anonymous_expected_contaminated_occurrence_contribution_share": encoded(
            max_share
        ),
    }
    if gated:
        limits = protocol["strong_positive_gates"]
        task = column == 0
        breadth_limit = ratio(
            limits[
                "minimum_task_fraction_at_or_above_group_ratio_reference"
                if task
                else "minimum_physical_run_fraction_at_or_above_group_ratio_reference"
            ]
        )
        dominance_limit = ratio(
            limits[
                "maximum_single_task_expected_contaminated_occurrence_contribution_share"
                if task
                else "maximum_single_physical_run_expected_contaminated_occurrence_contribution_share"
            ]
        )
        checks = {
            "breadth_fraction_at_least_minimum": breadth >= breadth_limit,
            "maximum_contribution_share_at_most_maximum": max_share <= dominance_limit,
        }
        output["strong_positive_gate"] = {
            "checks": checks,
            "all_passed": all(checks.values()),
            "breadth_threshold": encoded(breadth_limit),
            "dominance_threshold": encoded(dominance_limit),
        }
    return output


def independently_summarize(
    rows: list[tuple[str, str, str, int]], protocol: dict[str, Any]
) -> dict[str, Any]:
    global_result, terms = independently_global(rows, protocol)
    leaked = decoded(
        global_result["expected_contaminated_test_path_edge_occurrences"],
        "global leaked rows",
    )
    return {
        "global": global_result,
        "anonymous_profiles": {
            "task": independently_group(rows, 0, terms, leaked, protocol, True),
            "physical_run": independently_group(rows, 1, terms, leaked, protocol, True),
            "observed_fragment_descriptive": independently_group(
                rows, 2, terms, leaked, protocol, False
            ),
        },
        "grouped_split_controls": {
            "fragment_grouped_expected_exact_canonical_edge_crossing": encoded(Fraction()),
            "physical_run_grouped_expected_exact_canonical_edge_crossing": encoded(Fraction()),
            "reason": "Every canonical observed edge is bound to exactly one observed fragment and one physical run.",
        },
    }


def classify(summary: dict[str, Any], hard: dict[str, bool], protocol: dict[str, Any]) -> str:
    global_ratio = decoded(
        summary["global"]["test_occurrence_contamination_ratio_of_expectations"],
        "global ratio",
    )
    floor = ratio(
        protocol["strong_positive_gates"]["global_test_occurrence_contamination_integrity_floor"]
    )
    if not all(hard.values()) or global_ratio < floor:
        value = "PATH_SPLIT_PREFIX_LEAKAGE_GATE_FAIL"
    else:
        task = summary["anonymous_profiles"]["task"]["strong_positive_gate"]["all_passed"]
        run = summary["anonymous_profiles"]["physical_run"]["strong_positive_gate"]["all_passed"]
        if task and run:
            value = "BROAD_PATH_SPLIT_PREFIX_LEAKAGE_RISK"
        elif task:
            value = "TASK_ONLY_BROAD_PATH_SPLIT_PREFIX_LEAKAGE_RISK"
        elif run:
            value = "RUN_ONLY_BROAD_PATH_SPLIT_PREFIX_LEAKAGE_RISK"
        else:
            value = "GLOBAL_EXPECTATION_WITHOUT_BROAD_SUPPORT"
    check(value in protocol["ordered_classification"], "classification outside protocol")
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
    check(protocol.get("protocol") == PROTOCOL_NAME, "protocol name mismatch")
    check(
        protocol.get("status")
        == "OUTCOME_BLIND_PROTOCOL_FROZEN_AFTER_GLOBAL_EXPLORATION_BEFORE_CLUSTER_BREADTH",
        "protocol status mismatch",
    )
    timing = protocol.get("design_timing", {})
    check(timing.get("task_run_or_fragment_breadth_values_seen_before_freeze") is False, "timing mismatch")
    check(timing.get("actual_random_partition_drawn") is False, "random split mismatch")
    check(digest(receipt_path) == receipt_sha, "receipt SHA mismatch")
    receipt = object_at(receipt_path)
    check(receipt.get("protocol") == RECEIPT_PROTOCOL, "receipt protocol mismatch")
    check(
        receipt.get("status") == "OUTCOME_BLIND_TREE_PATH_SPLIT_PREFIX_LEAKAGE_AUDIT_COMPLETE",
        "receipt status mismatch",
    )
    check(digest(producer_source) == producer_source_sha, "producer SHA mismatch")
    check(isinstance(source_commit, str) and SHA40.fullmatch(source_commit) is not None, "source commit")
    check(receipt.get("source_commit") == source_commit, "receipt commit mismatch")
    check(receipt.get("producer_source_sha256") == producer_source_sha, "receipt producer hash")
    check(receipt.get("protocol_sha256") == protocol_sha, "receipt protocol hash")

    population_protocol, linear, native, source_hashes = fixed_sources(repo_root, protocol)
    try:
        cards, runs, population_bindings = blind_reader.collect_inputs(
            state_root, snapshot_root, population_protocol
        )
    except blind_reader.VerificationError as error:
        raise VerificationError(f"blind population reconstruction failed: {error}") from error
    rows, inventory, graph_checks = independently_reconstruct(cards)
    summary = independently_summarize(rows, protocol)
    multiplicity_histogram = dict(
        sorted(collections.Counter(str(row[3]) for row in rows).items(), key=lambda item: int(item[0]))
    )
    fixed = protocol["fixed_population"]
    disclosed = protocol["disclosed_post_hoc_global_exploration"]
    global_result = summary["global"]
    hard = {
        "latest_equals_fixed_snapshot": True,
        "population_loader_rechecked_original_tree_audit_contract": True,
        "upstream_protocol_and_receipt_hashes_classifications_snapshot_and_counts_match": True,
        "population_counts_match_frozen_protocol": inventory["eligible_endpoints"]
        == fixed["eligible_endpoints"]
        and len(runs) == fixed["provisional_first960_runs"]
        and inventory["tasks"] == fixed["tasks"]
        and inventory["observed_fragments"] == fixed["observed_fragments"]
        and inventory["root_to_leaf_path_records"] == fixed["root_to_leaf_path_records"]
        and inventory["canonical_observed_edges"] == fixed["canonical_observed_edges"]
        and inventory["path_edge_occurrences"] == fixed["path_edge_occurrences"],
        "recomputed_multiplicity_histogram_matches_both_upstream_receipts": multiplicity_histogram
        == linear["linearization"]["edge_multiplicity"]["histogram"]
        == native["path_compatibility"]["edge_multiplicity_histogram"],
        "global_exact_combinatorics_roundtrip_to_disclosed_17g_values": global_result[
            "expected_train_test_cross_split_canonical_edges"
        ]["decimal_17g"]
        == disclosed["expected_train_test_cross_split_canonical_edges_decimal_17g"]
        and global_result["canonical_edge_overlap_fraction"]["decimal_17g"]
        == disclosed["canonical_edge_overlap_fraction_decimal_17g"]
        and global_result["unique_test_edge_contamination_ratio_of_expectations"]["decimal_17g"]
        == disclosed["unique_test_edge_contamination_ratio_of_expectations_decimal_17g"]
        and global_result["test_occurrence_contamination_ratio_of_expectations"]["decimal_17g"]
        == disclosed["test_occurrence_contamination_ratio_of_expectations_decimal_17g"],
        "fragment_and_run_grouped_controls_are_exact_zero": summary["grouped_split_controls"][
            "fragment_grouped_expected_exact_canonical_edge_crossing"
        ]
        == encoded(Fraction())
        and summary["grouped_split_controls"][
            "physical_run_grouped_expected_exact_canonical_edge_crossing"
        ]
        == encoded(Fraction()),
        "conditionable_tasks_at_least_minimum": summary["anonymous_profiles"]["task"][
            "conditionable_groups"
        ]
        >= protocol["hard_integrity_and_support_gates"]["minimum_conditionable_tasks"],
        "conditionable_physical_runs_at_least_minimum": summary["anonymous_profiles"][
            "physical_run"
        ]["conditionable_groups"]
        >= protocol["hard_integrity_and_support_gates"]["minimum_conditionable_physical_runs"],
        **graph_checks,
    }
    expected_classification = classify(summary, hard, protocol)
    global_floor = ratio(
        protocol["strong_positive_gates"]["global_test_occurrence_contamination_integrity_floor"]
    )
    global_ratio = decoded(
        global_result["test_occurrence_contamination_ratio_of_expectations"],
        "global ratio for gate",
    )
    expected_gate = {
        "hard_integrity_and_support": hard,
        "all_hard_gates_passed": all(hard.values()),
        "axis_strength": {
            "task": summary["anonymous_profiles"]["task"]["strong_positive_gate"]["all_passed"],
            "physical_run": summary["anonymous_profiles"]["physical_run"]["strong_positive_gate"]["all_passed"],
        },
        "global_integrity_floor": {
            "ratio_at_least_floor": global_ratio >= global_floor,
            "floor": encoded(global_floor),
            "is_new_evidence": False,
        },
        "fixed_thresholds": protocol["strong_positive_gates"],
        "global_floor_is_new_evidence": False,
    }
    expected_security = {
        "allowed_input_basenames": protocol["security"]["allowed_input_basenames"],
        "raw_senior_archives_opened": False,
        "prospective_label_grade_outcome_prediction_values_read": False,
        "task_run_fragment_path_card_parent_code_or_edge_values_emitted": False,
        "accuracy_effect_or_search_utility_computed": False,
        "gpu_api_model_fit_base_update": [0, 0, 0, 0],
    }
    deep_equal({**source_hashes, **population_bindings}, receipt.get("input_bindings"), "bindings")
    deep_equal(inventory, receipt.get("inventory"), "inventory")
    deep_equal(multiplicity_histogram, receipt.get("multiplicity_histogram"), "multiplicity histogram")
    deep_equal(summary["global"], receipt.get("global"), "global")
    deep_equal(summary["anonymous_profiles"], receipt.get("anonymous_profiles"), "profiles")
    deep_equal(summary["grouped_split_controls"], receipt.get("grouped_split_controls"), "controls")
    deep_equal(expected_gate, receipt.get("pre_registered_gate"), "gates")
    deep_equal(expected_classification, receipt.get("classification"), "classification")
    deep_equal(protocol["design_timing"], receipt.get("design_timing"), "design timing")
    deep_equal(protocol["claim_boundary"], receipt.get("claim_boundary"), "claim boundary")
    deep_equal(expected_security, receipt.get("security"), "security")
    deep_equal(
        {"python_version": platform.python_version(), "randomness_used": False},
        receipt.get("reproducibility"),
        "reproducibility",
    )
    check(
        receipt.get("population_loader_source_sha256")
        == digest(repo_root / "phase1" / "audit_prospective_tree_linearization_weights.py"),
        "population loader hash mismatch",
    )
    return {
        "protocol": VERIFY_PROTOCOL,
        "status": "INDEPENDENT_TREE_PATH_SPLIT_PREFIX_LEAKAGE_PASS",
        "classification": expected_classification,
        "snapshot_sha256": protocol["fixed_population"]["snapshot_sha256"],
        "receipt_sha256": receipt_sha,
        "producer_source_sha256": producer_source_sha,
        "canonical_observed_edges": inventory["canonical_observed_edges"],
        "root_to_leaf_path_records": inventory["root_to_leaf_path_records"],
        "test_occurrence_contamination_ratio_of_expectations": summary["global"][
            "test_occurrence_contamination_ratio_of_expectations"
        ],
        "all_hard_gates_passed": all(hard.values()),
        "checks": {
            "fixed_inputs_rehashed": True,
            "blind_population_independently_reconstructed": True,
            "paths_multiplicities_and_fragments_independently_reconstructed": True,
            "fixed_size_combinatorics_independently_recomputed": True,
            "anonymous_profiles_and_classification_independently_recomputed": True,
            "identity_free_contract_exact": True,
        },
        "security": {
            "imports_new_producer": False,
            "prospective_label_grade_outcome_prediction_values_read": False,
            "task_run_fragment_path_card_parent_code_or_edge_values_emitted": False,
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
