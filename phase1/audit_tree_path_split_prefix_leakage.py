#!/usr/bin/env python3
"""Exact outcome-blind audit of shared-prefix crossing under path-record splits."""

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

from phase1 import audit_prospective_tree_linearization_weights as population_loader


PROTOCOL_NAME = "tree-path-split-prefix-leakage-v1"
RECEIPT_PROTOCOL = "tree-path-split-prefix-leakage-receipt-v1"
RECEIPT_STATUS = "OUTCOME_BLIND_TREE_PATH_SPLIT_PREFIX_LEAKAGE_AUDIT_COMPLETE"
SHA64 = re.compile(r"[0-9a-f]{64}")
SHA40 = re.compile(r"[0-9a-f]{40}")


class PrefixLeakageError(RuntimeError):
    """Raised when a frozen input, graph, arithmetic, or output contract fails."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise PrefixLeakageError(message)


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
        raise PrefixLeakageError(f"path escapes repository: {relative}") from error
    require(resolved.is_file(), f"missing input: {relative}")
    return resolved


def valid_sha64(value: Any, label: str) -> str:
    require(isinstance(value, str) and SHA64.fullmatch(value) is not None, f"invalid {label}")
    return value


def parse_ratio(value: Any) -> Fraction:
    require(isinstance(value, str) and value, "invalid exact ratio")
    try:
        result = Fraction(value)
    except (ValueError, ZeroDivisionError) as error:
        raise PrefixLeakageError(f"invalid exact ratio: {value}") from error
    require(0 <= result <= 1, "ratio outside [0,1]")
    return result


def exact(value: Fraction) -> dict[str, Any]:
    return {
        "numerator": value.numerator,
        "denominator": value.denominator,
        "decimal_17g": format(float(value), ".17g"),
    }


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
    rank = math.ceil(probability * len(ordered))
    return ordered[max(1, rank) - 1]


def histogram(values: list[Fraction], edges: list[Fraction]) -> list[int]:
    require(
        len(edges) >= 2 and edges == sorted(set(edges)) and edges[0] == 0 and edges[-1] == 1,
        "invalid histogram edges",
    )
    counts = [0] * (len(edges) - 1)
    for value in values:
        require(0 <= value <= 1, "histogram value outside [0,1]")
        for index, (lower, upper) in enumerate(zip(edges, edges[1:])):
            if lower <= value < upper or (index == len(counts) - 1 and value == upper):
                counts[index] += 1
                break
        else:
            raise PrefixLeakageError("value not assigned to histogram")
    require(sum(counts) == len(values), "histogram count mismatch")
    return counts


def load_protocol(path: Path, expected_sha: str) -> tuple[dict[str, Any], str]:
    actual = sha256_file(path)
    require(actual == expected_sha, "protocol SHA mismatch")
    protocol = read_object(path)
    require(protocol.get("protocol") == PROTOCOL_NAME, "protocol name mismatch")
    require(
        protocol.get("status")
        == "OUTCOME_BLIND_PROTOCOL_FROZEN_AFTER_GLOBAL_EXPLORATION_BEFORE_CLUSTER_BREADTH",
        "protocol status mismatch",
    )
    timing = protocol.get("design_timing", {})
    require(timing.get("global_analytic_split_values_seen_before_freeze") is True, "global timing mismatch")
    require(timing.get("task_run_or_fragment_breadth_values_seen_before_freeze") is False, "breadth timing mismatch")
    require(timing.get("actual_random_partition_drawn") is False, "unexpected random split")
    return protocol, actual


def fixed_inputs(
    repo_root: Path, protocol: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, str]]:
    specs = protocol["fixed_inputs"]
    paths: dict[str, Path] = {}
    values: dict[str, dict[str, Any]] = {}
    for name in (
        "tree_population_protocol",
        "tree_linearization_receipt",
        "tree_native_contract",
        "tree_native_receipt",
    ):
        spec = specs[name]
        path = repo_file(repo_root, spec["path"])
        expected = valid_sha64(spec["sha256"], f"{name} SHA")
        require(sha256_file(path) == expected, f"{name} SHA mismatch")
        paths[name] = path
        values[name] = read_object(path)

    population = values["tree_population_protocol"]
    linear = values["tree_linearization_receipt"]
    native_contract = values["tree_native_contract"]
    native = values["tree_native_receipt"]
    snapshot = protocol["fixed_population"]["snapshot_sha256"]
    require(population.get("protocol") == "prospective-tree-linearization-weight-audit-v1", "population protocol mismatch")
    require(population.get("fixed_snapshot", {}).get("sha256") == snapshot, "population snapshot mismatch")
    require(linear.get("classification") == specs["tree_linearization_receipt"]["required_classification"], "linear classification mismatch")
    require(native_contract.get("protocol") == "tree-native-path-compatibility-contract-v1", "native contract mismatch")
    require(native.get("classification") == specs["tree_native_receipt"]["required_classification"], "native classification mismatch")
    require(linear.get("snapshot_sha256") == native.get("snapshot_sha256") == snapshot, "upstream snapshot mismatch")
    require(linear.get("pre_registered_gate", {}).get("all_hard_gates_passed") is True, "linear hard gate failed")
    require(native.get("all_verification_gates_passed") is True, "native verification gate failed")
    return population, linear, native, {name: sha256_file(path) for name, path in paths.items()}


def reconstruct_tree_rows(
    cards: dict[str, dict[str, Any]],
) -> tuple[list[tuple[str, str, str, int]], dict[str, Any], dict[str, bool]]:
    children: dict[str, list[str]] = {identifier: [] for identifier in cards}
    parent_of: dict[str, str] = {}
    roots: list[str] = []
    for child_id, child in cards.items():
        parent_id = child["parent"]
        if parent_id not in cards:
            roots.append(child_id)
            continue
        require(parent_id != child_id, "self-parent edge")
        require(cards[parent_id]["run"] == child["run"], "observed edge crosses physical runs")
        require(cards[parent_id]["task"] == child["task"], "observed edge crosses tasks")
        parent_of[child_id] = parent_id
        children[parent_id].append(child_id)
    for values in children.values():
        values.sort()
    roots.sort()
    require(bool(roots), "observed graph has no fragment roots")

    fragment_of: dict[str, str] = {}
    order: list[str] = []
    queue = collections.deque((root, root) for root in roots)
    while queue:
        node, root = queue.popleft()
        require(node not in fragment_of, "cycle or duplicate traversal")
        fragment_of[node] = root
        order.append(node)
        queue.extend((child, root) for child in children[node])
    require(len(order) == len(cards), "unrooted or cyclic observed component")

    descendant_leaves: dict[str, int] = {}
    for node in reversed(order):
        descendant_leaves[node] = (
            1 if not children[node] else sum(descendant_leaves[child] for child in children[node])
        )

    paths: list[tuple[str, ...]] = []
    for root in roots:
        stack: list[tuple[str, tuple[str, ...]]] = [(root, (root,))]
        while stack:
            node, prefix = stack.pop()
            if not children[node]:
                paths.append(prefix)
            else:
                for child in reversed(children[node]):
                    stack.append((child, prefix + (child,)))
    paths.sort(key=lambda row: (fragment_of[row[0]], row[-1], row))

    occurrence_count: collections.Counter[str] = collections.Counter()
    each_path_unique = True
    each_path_bound = True
    for path in paths:
        edge_ids = list(path[1:])
        each_path_unique = each_path_unique and len(edge_ids) == len(set(edge_ids))
        each_path_bound = each_path_bound and len({cards[node]["task"] for node in path}) == 1
        each_path_bound = each_path_bound and len({cards[node]["run"] for node in path}) == 1
        for parent, child in zip(path, path[1:]):
            require(parent_of.get(child) == parent, "non-contiguous path")
            occurrence_count[child] += 1

    rows: list[tuple[str, str, str, int]] = []
    for child_id in sorted(parent_of):
        card = cards[child_id]
        multiplicity = descendant_leaves[child_id]
        require(multiplicity >= 1, "invalid edge multiplicity")
        rows.append((card["task"], card["run"], fragment_of[child_id], multiplicity))
    require(bool(rows), "no canonical observed edges")
    occurrence_matches = all(
        occurrence_count[child] == descendant_leaves[child] for child in parent_of
    ) and set(occurrence_count) == set(parent_of)
    return rows, {
        "eligible_endpoints": len(cards),
        "observed_fragments": len(roots),
        "fragments_with_observed_edges": len({row[2] for row in rows}),
        "single_node_fragments": sum(not children[root] for root in roots),
        "root_to_leaf_path_records": len(paths),
        "canonical_observed_edges": len(rows),
        "path_edge_occurrences": sum(row[3] for row in rows),
        "tasks": len({row[0] for row in rows}),
        "physical_runs": len({row[1] for row in rows}),
    }, {
        "each_path_contains_a_canonical_edge_at_most_once": each_path_unique,
        "paths_are_fragment_task_and_run_bound": each_path_bound,
        "enumerated_edge_occurrences_equal_descendant_leaf_multiplicity": occurrence_matches,
        "each_edge_has_exactly_one_fragment_task_and_physical_run": True,
    }


def all_in_subset(population: int, subset: int, selected: int) -> Fraction:
    require(population >= 1 and 0 <= subset <= population and selected >= 0, "invalid combinatoric arguments")
    if selected > subset:
        return Fraction()
    return Fraction(math.comb(subset, selected), math.comb(population, selected))


def split_terms(
    population: int, train: int, validation: int, test: int, multiplicity: int
) -> dict[str, Fraction]:
    require(train >= 0 and validation >= 0 and test >= 0, "negative split size")
    require(train + validation + test == population, "split sizes do not sum to population")
    require(1 <= multiplicity <= population, "invalid multiplicity")
    no_train = all_in_subset(population, validation + test, multiplicity)
    no_test = all_in_subset(population, train + validation, multiplicity)
    all_validation = all_in_subset(population, validation, multiplicity)
    overlap = 1 - no_train - no_test + all_validation
    in_test = 1 - no_test
    no_other_train_given_test_occurrence = all_in_subset(
        population - 1, population - 1 - train, multiplicity - 1
    )
    expected_test_occurrences = Fraction(multiplicity * test, population)
    expected_contaminated_test_occurrences = expected_test_occurrences * (
        1 - no_other_train_given_test_occurrence
    )
    require(0 <= overlap <= in_test <= 1, "invalid edge overlap probability")
    require(
        0 <= expected_contaminated_test_occurrences <= expected_test_occurrences,
        "invalid contaminated occurrence expectation",
    )
    return {
        "train_test_overlap": overlap,
        "appears_in_test": in_test,
        "expected_test_occurrences": expected_test_occurrences,
        "expected_contaminated_test_occurrences": expected_contaminated_test_occurrences,
    }


def global_profile(
    rows: list[tuple[str, str, str, int]], protocol: dict[str, Any]
) -> tuple[dict[str, Any], dict[int, dict[str, Fraction]]]:
    design = protocol["split_design"]
    population = design["train_paths"] + design["validation_paths"] + design["test_paths"]
    cache = {
        multiplicity: split_terms(
            population,
            design["train_paths"],
            design["validation_paths"],
            design["test_paths"],
            multiplicity,
        )
        for multiplicity in sorted({row[3] for row in rows})
    }
    expected_overlap = sum((cache[row[3]]["train_test_overlap"] for row in rows), Fraction())
    expected_unique_test = sum((cache[row[3]]["appears_in_test"] for row in rows), Fraction())
    expected_test_rows = sum((cache[row[3]]["expected_test_occurrences"] for row in rows), Fraction())
    expected_contaminated_rows = sum(
        (cache[row[3]]["expected_contaminated_test_occurrences"] for row in rows), Fraction()
    )
    edge_count = len(rows)
    require(expected_unique_test > 0 and expected_test_rows > 0, "zero test support")
    return {
        "split_sizes": {
            "root_to_leaf_path_records": population,
            "train": design["train_paths"],
            "validation": design["validation_paths"],
            "test": design["test_paths"],
        },
        "expected_train_test_cross_split_canonical_edges": exact(expected_overlap),
        "canonical_edge_overlap_fraction": exact(expected_overlap / edge_count),
        "expected_unique_test_canonical_edges": exact(expected_unique_test),
        "unique_test_edge_contamination_ratio_of_expectations": exact(
            expected_overlap / expected_unique_test
        ),
        "expected_test_path_edge_occurrences": exact(expected_test_rows),
        "expected_contaminated_test_path_edge_occurrences": exact(expected_contaminated_rows),
        "test_occurrence_contamination_ratio_of_expectations": exact(
            expected_contaminated_rows / expected_test_rows
        ),
        "train_validation_identical_by_equal_split_size": design["validation_paths"]
        == design["test_paths"],
    }, cache


def group_profile(
    rows: list[tuple[str, str, str, int]],
    axis_index: int,
    cache: dict[int, dict[str, Fraction]],
    global_contaminated: Fraction,
    protocol: dict[str, Any],
    gated: bool,
) -> dict[str, Any]:
    groups: dict[str, list[int]] = collections.defaultdict(list)
    for row in rows:
        groups[row[axis_index]].append(row[3])
    ratios: list[Fraction] = []
    contributions: list[Fraction] = []
    for group in sorted(groups):
        expected_test = sum(
            (cache[m]["expected_test_occurrences"] for m in groups[group]), Fraction()
        )
        contaminated = sum(
            (cache[m]["expected_contaminated_test_occurrences"] for m in groups[group]),
            Fraction(),
        )
        require(expected_test > 0, "group has zero expected test mass")
        ratios.append(contaminated / expected_test)
        contributions.append(contaminated)
    require(bool(ratios) and global_contaminated >= 0, "empty group profile")
    require(
        sum(contributions, Fraction()) == global_contaminated,
        "group contaminated-mass decomposition mismatch",
    )
    summary_spec = protocol["fixed_distribution_summary"]
    reference = parse_ratio(summary_spec["group_ratio_reference"])
    bin_edges = [parse_ratio(value) for value in summary_spec["histogram_edges"]]
    at_reference = sum(value >= reference for value in ratios)
    breadth = Fraction(at_reference, len(ratios))
    maximum_contribution_share = (
        max(contributions) / global_contaminated if global_contaminated else Fraction()
    )
    output: dict[str, Any] = {
        "conditionable_groups": len(ratios),
        "anonymous_group_distribution": {
            "reference": exact(reference),
            "groups_at_or_above_reference": at_reference,
            "fraction_at_or_above_reference": exact(breadth),
            "histogram": {
                "edges": [exact(value) for value in bin_edges],
                "counts": histogram(ratios, bin_edges),
                "last_bin_right_closed": True,
            },
            "median": exact(median(ratios)),
            "p90_nearest_rank": exact(nearest_rank(ratios, Fraction(9, 10))),
            "maximum": exact(max(ratios)),
        },
        "maximum_anonymous_expected_contaminated_occurrence_contribution_share": exact(
            maximum_contribution_share
        ),
    }
    if gated:
        gates = protocol["strong_positive_gates"]
        is_task = axis_index == 0
        breadth_threshold = parse_ratio(
            gates[
                "minimum_task_fraction_at_or_above_group_ratio_reference"
                if is_task
                else "minimum_physical_run_fraction_at_or_above_group_ratio_reference"
            ]
        )
        dominance_threshold = parse_ratio(
            gates[
                "maximum_single_task_expected_contaminated_occurrence_contribution_share"
                if is_task
                else "maximum_single_physical_run_expected_contaminated_occurrence_contribution_share"
            ]
        )
        checks = {
            "breadth_fraction_at_least_minimum": breadth >= breadth_threshold,
            "maximum_contribution_share_at_most_maximum": maximum_contribution_share
            <= dominance_threshold,
        }
        output["strong_positive_gate"] = {
            "checks": checks,
            "all_passed": all(checks.values()),
            "breadth_threshold": exact(breadth_threshold),
            "dominance_threshold": exact(dominance_threshold),
        }
    return output


def summarize_rows(
    rows: list[tuple[str, str, str, int]], protocol: dict[str, Any]
) -> dict[str, Any]:
    global_result, cache = global_profile(rows, protocol)
    contaminated = Fraction(
        global_result["expected_contaminated_test_path_edge_occurrences"]["numerator"],
        global_result["expected_contaminated_test_path_edge_occurrences"]["denominator"],
    )
    task = group_profile(rows, 0, cache, contaminated, protocol, True)
    run = group_profile(rows, 1, cache, contaminated, protocol, True)
    fragment = group_profile(rows, 2, cache, contaminated, protocol, False)
    return {
        "global": global_result,
        "anonymous_profiles": {
            "task": task,
            "physical_run": run,
            "observed_fragment_descriptive": fragment,
        },
        "grouped_split_controls": {
            "fragment_grouped_expected_exact_canonical_edge_crossing": exact(Fraction()),
            "physical_run_grouped_expected_exact_canonical_edge_crossing": exact(Fraction()),
            "reason": "Every canonical observed edge is bound to exactly one observed fragment and one physical run.",
        },
    }


def final_classification(summary: dict[str, Any], hard_checks: dict[str, bool], protocol: dict[str, Any]) -> str:
    global_ratio = Fraction(
        summary["global"]["test_occurrence_contamination_ratio_of_expectations"]["numerator"],
        summary["global"]["test_occurrence_contamination_ratio_of_expectations"]["denominator"],
    )
    global_floor = parse_ratio(
        protocol["strong_positive_gates"]["global_test_occurrence_contamination_integrity_floor"]
    )
    if not all(hard_checks.values()) or global_ratio < global_floor:
        result = "PATH_SPLIT_PREFIX_LEAKAGE_GATE_FAIL"
    else:
        task_strong = summary["anonymous_profiles"]["task"]["strong_positive_gate"]["all_passed"]
        run_strong = summary["anonymous_profiles"]["physical_run"]["strong_positive_gate"]["all_passed"]
        if task_strong and run_strong:
            result = "BROAD_PATH_SPLIT_PREFIX_LEAKAGE_RISK"
        elif task_strong:
            result = "TASK_ONLY_BROAD_PATH_SPLIT_PREFIX_LEAKAGE_RISK"
        elif run_strong:
            result = "RUN_ONLY_BROAD_PATH_SPLIT_PREFIX_LEAKAGE_RISK"
        else:
            result = "GLOBAL_EXPECTATION_WITHOUT_BROAD_SUPPORT"
    require(result in protocol["ordered_classification"], "classification outside protocol")
    return result


def build_receipt(
    state_root: Path,
    snapshot_root: Path,
    repo_root: Path,
    protocol_path: Path,
    expected_protocol_sha: str,
    source_commit: str,
) -> dict[str, Any]:
    require(isinstance(source_commit, str) and SHA40.fullmatch(source_commit) is not None, "invalid source commit")
    protocol, protocol_sha = load_protocol(protocol_path, expected_protocol_sha)
    population_protocol, linear, native, source_hashes = fixed_inputs(repo_root, protocol)
    try:
        cards, runs, population_bindings = population_loader.load_population(
            state_root, snapshot_root, population_protocol
        )
    except population_loader.AuditError as error:
        raise PrefixLeakageError(f"population loader failed: {error}") from error
    rows, inventory, graph_checks = reconstruct_tree_rows(cards)
    summary = summarize_rows(rows, protocol)

    expected_inventory = protocol["fixed_population"]
    multiplicity_histogram = dict(
        sorted(collections.Counter(str(row[3]) for row in rows).items(), key=lambda item: int(item[0]))
    )
    disclosed = protocol["disclosed_post_hoc_global_exploration"]
    global_result = summary["global"]
    hard = {
        "latest_equals_fixed_snapshot": True,
        "population_loader_rechecked_original_tree_audit_contract": True,
        "upstream_protocol_and_receipt_hashes_classifications_snapshot_and_counts_match": True,
        "population_counts_match_frozen_protocol": inventory["eligible_endpoints"]
        == expected_inventory["eligible_endpoints"]
        and len(runs) == expected_inventory["provisional_first960_runs"]
        and inventory["tasks"] == expected_inventory["tasks"]
        and inventory["observed_fragments"] == expected_inventory["observed_fragments"]
        and inventory["root_to_leaf_path_records"] == expected_inventory["root_to_leaf_path_records"]
        and inventory["canonical_observed_edges"] == expected_inventory["canonical_observed_edges"]
        and inventory["path_edge_occurrences"] == expected_inventory["path_edge_occurrences"],
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
        == exact(Fraction())
        and summary["grouped_split_controls"][
            "physical_run_grouped_expected_exact_canonical_edge_crossing"
        ]
        == exact(Fraction()),
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
    classification = final_classification(summary, hard, protocol)
    global_floor = parse_ratio(
        protocol["strong_positive_gates"]["global_test_occurrence_contamination_integrity_floor"]
    )
    global_ratio = Fraction(
        global_result["test_occurrence_contamination_ratio_of_expectations"]["numerator"],
        global_result["test_occurrence_contamination_ratio_of_expectations"]["denominator"],
    )
    return {
        "protocol": RECEIPT_PROTOCOL,
        "status": RECEIPT_STATUS,
        "classification": classification,
        "snapshot_sha256": protocol["fixed_population"]["snapshot_sha256"],
        "protocol_sha256": protocol_sha,
        "source_commit": source_commit,
        "producer_source_sha256": sha256_file(Path(__file__)),
        "population_loader_source_sha256": sha256_file(Path(population_loader.__file__)),
        "input_bindings": {**source_hashes, **population_bindings},
        "inventory": inventory,
        "multiplicity_histogram": multiplicity_histogram,
        **summary,
        "pre_registered_gate": {
            "hard_integrity_and_support": hard,
            "all_hard_gates_passed": all(hard.values()),
            "axis_strength": {
                "task": summary["anonymous_profiles"]["task"]["strong_positive_gate"]["all_passed"],
                "physical_run": summary["anonymous_profiles"]["physical_run"]["strong_positive_gate"]["all_passed"],
            },
            "global_integrity_floor": {
                "ratio_at_least_floor": global_ratio >= global_floor,
                "floor": exact(global_floor),
                "is_new_evidence": False,
            },
            "fixed_thresholds": protocol["strong_positive_gates"],
            "global_floor_is_new_evidence": False,
        },
        "design_timing": protocol["design_timing"],
        "claim_boundary": protocol["claim_boundary"],
        "security": {
            "allowed_input_basenames": protocol["security"]["allowed_input_basenames"],
            "raw_senior_archives_opened": False,
            "prospective_label_grade_outcome_prediction_values_read": False,
            "task_run_fragment_path_card_parent_code_or_edge_values_emitted": False,
            "accuracy_effect_or_search_utility_computed": False,
            "gpu_api_model_fit_base_update": [0, 0, 0, 0],
        },
        "reproducibility": {
            "python_version": platform.python_version(),
            "randomness_used": False,
        },
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
    except (PrefixLeakageError, OSError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}")
        return 2
    print(receipt["classification"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
