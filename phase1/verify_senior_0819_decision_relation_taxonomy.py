#!/usr/bin/env python3
"""Independent verifier for the senior 0819 decision relation taxonomy.

This module does not import the taxonomy producer.  It uses the independently written
Card-map decoder from the earlier integrity verifier, then recomputes every taxonomy
field with separately named row, graph, profile, and gate implementations.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import re
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

try:
    from phase1 import verify_senior_0819_pair_benchmark_integrity as prior
except ImportError:
    import verify_senior_0819_pair_benchmark_integrity as prior


FROZEN_NAME = "senior-0819-decision-relation-taxonomy-v1"
FROZEN_STATUS = "FROZEN_AFTER_OVERALL_SEMANTICS_BEFORE_SPLIT_SPECIFIC_TAXONOMY"
RESULT_NAME = "senior-0819-decision-relation-taxonomy-receipt-v1"
RELATIONS = (
    "verified_direct_sibling",
    "same_run_declared_context_non_sibling",
    "cross_run_declared_context",
)


class VerificationError(RuntimeError):
    pass


def check(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def payload(value: Fraction) -> dict[str, Any]:
    return {
        "numerator": value.numerator,
        "denominator": value.denominator,
        "decimal_17g": format(float(value), ".17g"),
    }


def frozen_fraction(text: str) -> Fraction:
    check(bool(re.fullmatch(r"[0-9]+/[1-9][0-9]*", text)), "frozen fraction")
    top, bottom = text.split("/")
    return Fraction(int(top), int(bottom))


@dataclass(frozen=True)
class RelationEdge:
    high: str
    low: str
    declared: str
    task: str
    split: str
    high_run: str
    low_run: str
    declared_run: str
    category: str

    def pair(self) -> tuple[str, str]:
        return (self.high, self.low) if self.high < self.low else (self.low, self.high)

    def direction(self) -> tuple[str, str]:
        return self.high, self.low


class Graph:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def leader(self, value: str) -> str:
        self.parent.setdefault(value, value)
        path: list[str] = []
        while self.parent[value] != value:
            path.append(value)
            value = self.parent[value]
        for item in path:
            self.parent[item] = value
        return value

    def join(self, first: str, second: str) -> None:
        left, right = self.leader(first), self.leader(second)
        if left != right:
            self.parent[max(left, right)] = min(left, right)


def frozen_protocol(path: Path, expected_sha: str) -> dict[str, Any]:
    check(prior.digest(path) == expected_sha, "protocol hash")
    value = prior.object_json(path)
    check(value.get("protocol") == FROZEN_NAME, "protocol name")
    check(value.get("status") == FROZEN_STATUS, "protocol status")
    check(value["fixed_taxonomy"]["class_order"] == list(RELATIONS), "relation order")
    known = value["known_before_freeze"]
    check(
        known["overall_rows_seen"] == value["immutable_inputs"]["decision"]["rows"],
        "prior rows",
    )
    check(
        0
        <= known["overall_direct_sibling_rows_seen"]
        <= known["overall_declared_context_same_run_rows_seen"]
        <= known["overall_rows_seen"],
        "prior semantic ordering",
    )
    check(known["overall_same_task_rows_seen"] == known["overall_rows_seen"], "prior task")
    for key in (
        "split_specific_class_counts_seen",
        "test_verified_sibling_task_run_endpoint_component_breadth_seen",
        "per_class_train_test_mix_seen",
        "per_class_dependency_concentration_seen",
        "per_class_identity_fingerprints_seen",
    ):
        check(known[key] is False, "readout seen before freeze")
    return value


def parse_decisions(
    path: Path,
    nodes: dict[str, prior.Node],
    held: set[str],
    expected: dict[str, Any],
) -> tuple[list[RelationEdge], dict[str, int]]:
    edges: list[RelationEdge] = []
    counts = collections.Counter()
    splits = collections.Counter()
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            check(bool(line.strip()), f"blank decision row {line_number}")
            row = json.loads(line)
            check(isinstance(row, dict) and frozenset(row) == prior.DECISION_KEYS, "decision schema")
            high, low, declared = row["better"], row["worse"], row["parent"]
            task, split = row["task"], row["intask_split"]
            check(
                all(isinstance(value, str) and value for value in (high, low, declared, task)),
                "decision IDs",
            )
            check(high != low and high in nodes and low in nodes and declared in nodes, "Card refs")
            check(split in {"train", "test"}, "split value")
            high_node, low_node, declared_node = nodes[high], nodes[low], nodes[declared]
            check(high_node.task == low_node.task == declared_node.task == task, "task agreement")
            endpoint_membership = (high_node.run in held, low_node.run in held)
            check(endpoint_membership[0] == endpoint_membership[1], "cross-boundary endpoints")
            expected_split = "test" if endpoint_membership[0] else "train"
            check(split == expected_split, "split assignment")
            parent_partition_ok = (declared_node.run in held) == endpoint_membership[0]
            direct = high_node.ancestor == low_node.ancestor == declared
            one_run = high_node.run == low_node.run == declared_node.run
            if direct and one_run:
                category = RELATIONS[0]
            elif one_run:
                category = RELATIONS[1]
            else:
                category = RELATIONS[2]
            counts["rows"] += 1
            counts["same_task"] += 1
            counts["parent_split_matches"] += parent_partition_ok
            counts["direct"] += direct
            counts["same_run"] += one_run
            counts["direct_cross_run"] += direct and not one_run
            counts[f"class:{category}"] += 1
            splits[split] += 1
            edges.append(
                RelationEdge(
                    high,
                    low,
                    declared,
                    task,
                    split,
                    high_node.run,
                    low_node.run,
                    declared_node.run,
                    category,
                )
            )
    check(len(edges) == expected["rows"], "row count")
    check(splits["train"] == expected["train_rows"], "train count")
    check(splits["test"] == expected["test_rows"], "test count")
    return edges, dict(counts)


def group_profile(edges: list[RelationEdge]) -> tuple[dict[str, Any], dict[str, Fraction]]:
    task_counts = collections.Counter(edge.task for edge in edges)
    run_counts: collections.Counter[str] = collections.Counter()
    endpoint_degrees: collections.Counter[str] = collections.Counter()
    graph = Graph()
    records: list[bytes] = []
    for edge in edges:
        for run in {edge.high_run, edge.low_run}:
            run_counts[run] += 1
        endpoint_degrees[edge.high] += 1
        endpoint_degrees[edge.low] += 1
        graph.join(edge.high, edge.low)
        high, low = edge.pair()
        records.append(
            ("\0".join((edge.category, edge.split, high, low, edge.declared)) + "\n").encode()
        )
    component_counts = collections.Counter(graph.leader(edge.high) for edge in edges)
    total = len(edges)
    exacts = {
        "maximum_single_task_pair_share": Fraction(max(task_counts.values()), total)
        if total
        else Fraction(),
        "maximum_single_run_pair_share": Fraction(max(run_counts.values()), total)
        if total
        else Fraction(),
        "maximum_single_component_pair_share": Fraction(max(component_counts.values()), total)
        if total
        else Fraction(),
    }
    degrees = sorted(endpoint_degrees.values())
    fingerprint = hashlib.sha256(b"".join(sorted(records))).hexdigest()
    return {
        "pairs": total,
        "tasks": len(task_counts),
        "physical_runs": len(run_counts),
        "endpoints": len(endpoint_degrees),
        "components": len(component_counts),
        "endpoint_degree_median_nearest_rank": degrees[(len(degrees) - 1) // 2]
        if degrees
        else 0,
        "endpoint_degree_p90_nearest_rank": degrees[
            max(0, math.ceil(0.9 * len(degrees)) - 1)
        ]
        if degrees
        else 0,
        "endpoint_degree_maximum": max(degrees) if degrees else 0,
        "orientation_free_identity_fingerprint_sha256": fingerprint,
        **{name: payload(value) for name, value in exacts.items()},
    }, exacts


def separation(edges: list[RelationEdge]) -> dict[str, int]:
    selected = {split: [edge for edge in edges if edge.split == split] for split in ("train", "test")}
    pairs = {split: {edge.pair() for edge in rows} for split, rows in selected.items()}
    endpoints = {
        split: {value for edge in rows for value in (edge.high, edge.low)}
        for split, rows in selected.items()
    }
    references = {
        split: {
            value
            for edge in rows
            for value in (edge.high_run, edge.low_run, edge.declared_run)
        }
        for split, rows in selected.items()
    }
    directions: dict[tuple[str, str], set[tuple[str, str]]] = collections.defaultdict(set)
    for edge in edges:
        directions[edge.pair()].add(edge.direction())
    unique = {edge.pair() for edge in edges}
    return {
        "train_test_unordered_pair_overlap": len(pairs["train"] & pairs["test"]),
        "train_test_endpoint_overlap": len(endpoints["train"] & endpoints["test"]),
        "train_test_referenced_physical_run_overlap": len(references["train"] & references["test"]),
        "duplicate_unordered_pair_rows": len(edges) - len(unique),
        "conflicting_orientation_unordered_pairs": sum(
            len(values) > 1 for values in directions.values()
        ),
    }


def result_classification(hard: dict[str, bool], support: dict[str, bool]) -> str:
    if not all(hard.values()):
        return "HISTORICAL_RELATION_AWARE_DECISION_TAXONOMY_INTEGRITY_GATE_FAIL"
    if all(support.values()):
        return "HISTORICAL_RELATION_AWARE_DECISION_TAXONOMY_BROAD_VERIFIED_SIBLING_CORE"
    return "HISTORICAL_RELATION_AWARE_DECISION_TAXONOMY_LIMITED_VERIFIED_SIBLING_CORE"


def recompute(args: argparse.Namespace) -> dict[str, Any]:
    protocol = frozen_protocol(Path(args.protocol).resolve(), args.protocol_sha256)
    files = {
        "cards": Path(args.cards).resolve(),
        "run_split": Path(args.run_split).resolve(),
        "decision": Path(args.decision).resolve(),
    }
    hashes: dict[str, str] = {}
    for name, path in files.items():
        hashes[name] = prior.digest(path)
        check(hashes[name] == protocol["immutable_inputs"][name]["sha256"], f"input hash {name}")
    all_runs, held = prior.manifest(files["run_split"], protocol)
    nodes, node_inventory = prior.card_index(files["cards"], all_runs)
    edges, diagnostics = parse_decisions(
        files["decision"], nodes, held, protocol["immutable_inputs"]["decision"]
    )

    profiles: dict[str, dict[str, Any]] = {"train": {}, "test": {}}
    exacts: dict[str, dict[str, dict[str, Fraction]]] = {"train": {}, "test": {}}
    counts: dict[str, dict[str, int]] = {}
    for category in RELATIONS:
        counts[category] = {
            "total": sum(edge.category == category for edge in edges),
            "train": sum(edge.category == category and edge.split == "train" for edge in edges),
            "test": sum(edge.category == category and edge.split == "test" for edge in edges),
        }
        for split in ("train", "test"):
            group = [edge for edge in edges if edge.category == category and edge.split == split]
            profiles[split][category], exacts[split][category] = group_profile(group)

    train_total = protocol["immutable_inputs"]["decision"]["train_rows"]
    test_total = protocol["immutable_inputs"]["decision"]["test_rows"]
    mix = sum(
        abs(
            Fraction(counts[name]["train"], train_total)
            - Fraction(counts[name]["test"], test_total)
        )
        for name in RELATIONS
    ) / 2
    split = separation(edges)
    direct_total = counts[RELATIONS[0]]["total"]
    same_run_total = direct_total + counts[RELATIONS[1]]["total"]
    taxonomy_total = sum(value["total"] for value in counts.values())
    hard = {
        "all_input_hashes_and_reported_counts_exact": True,
        "cards_exactly_cover_frozen_run_manifest": node_inventory["physical_runs"] == len(all_runs),
        "card_ids_unique_and_present_lineage_parents_within_run": True,
        "all_decision_endpoints_parent_tasks_and_splits_valid": (
            diagnostics.get("same_task", 0) == len(edges)
            and diagnostics.get("parent_split_matches", 0) == len(edges)
        ),
        "taxonomy_is_exhaustive_and_mutually_exclusive": taxonomy_total == len(edges),
        "verified_direct_sibling_class_is_semantically_pure": (
            direct_total == diagnostics.get("direct", 0) - diagnostics.get("direct_cross_run", 0)
        ),
        "no_direct_sibling_crosses_physical_run": diagnostics.get("direct_cross_run", 0) == 0,
        "same_run_non_sibling_class_is_semantically_pure": same_run_total
        == diagnostics.get("same_run", 0),
        "cross_run_class_is_semantically_pure": counts[RELATIONS[2]]["total"]
        == len(edges) - diagnostics.get("same_run", 0),
        "train_test_unordered_pair_overlap_zero": split["train_test_unordered_pair_overlap"] == 0,
        "train_test_endpoint_overlap_zero": split["train_test_endpoint_overlap"] == 0,
        "train_test_physical_run_overlap_zero": split[
            "train_test_referenced_physical_run_overlap"
        ] == 0,
        "unordered_pair_duplicates_zero": split["duplicate_unordered_pair_rows"] == 0,
        "conflicting_orientations_zero": split["conflicting_orientation_unordered_pairs"] == 0,
        "prior_overall_semantic_aggregate_exactly_reproduced": (
            len(edges) == protocol["known_before_freeze"]["overall_rows_seen"]
            and direct_total == protocol["known_before_freeze"]["overall_direct_sibling_rows_seen"]
            and same_run_total
            == protocol["known_before_freeze"]["overall_declared_context_same_run_rows_seen"]
            and diagnostics.get("same_task", 0)
            == protocol["known_before_freeze"]["overall_same_task_rows_seen"]
        ),
    }
    limits = protocol["verified_sibling_test_support_gates"]
    sibling = profiles["test"][RELATIONS[0]]
    sibling_exacts = exacts["test"][RELATIONS[0]]
    support = {
        "minimum_pairs": sibling["pairs"] >= limits["minimum_pairs"],
        "minimum_tasks": sibling["tasks"] >= limits["minimum_tasks"],
        "minimum_physical_runs": sibling["physical_runs"] >= limits["minimum_physical_runs"],
        "minimum_endpoints": sibling["endpoints"] >= limits["minimum_endpoints"],
        "minimum_components": sibling["components"] >= limits["minimum_components"],
        "maximum_single_task_pair_share": sibling_exacts["maximum_single_task_pair_share"]
        <= frozen_fraction(limits["maximum_single_task_pair_share"]),
        "maximum_single_run_pair_share": sibling_exacts["maximum_single_run_pair_share"]
        <= frozen_fraction(limits["maximum_single_run_pair_share"]),
        "maximum_single_component_pair_share": sibling_exacts[
            "maximum_single_component_pair_share"
        ]
        <= frozen_fraction(limits["maximum_single_component_pair_share"]),
    }
    return {
        "protocol": RESULT_NAME,
        "status": "HISTORICAL_DECISION_RELATION_TAXONOMY_AUDIT_COMPLETE",
        "protocol_sha256": args.protocol_sha256,
        "source_commit": protocol["source"]["senior_branch_commit"],
        "input_sha256": hashes,
        "inventory": {
            "cards": node_inventory["cards"],
            "physical_runs": node_inventory["physical_runs"],
            "decision_rows": len(edges),
            "train_rows": train_total,
            "test_rows": test_total,
        },
        "semantic_class_counts": counts,
        "split_class_profiles": profiles,
        "train_test_semantic_mix_total_variation": payload(mix),
        "split_integrity": split,
        "hard_integrity_gates": hard,
        "verified_sibling_test_support_gates": support,
        "classification": result_classification(hard, support),
        "scope": {
            "historical_exploratory_dataset": True,
            "pair_orientation_used_by_taxonomy": False,
            "model_predictions_or_accuracy_read": False,
            "search_utility_computed": False,
            "prospective_first960_or_target300_values_read": False,
            "raw_senior_archives_opened": False,
            "identities_or_row_values_emitted": False,
            "row_level_release_created": False,
            "gpu_jobs": 0,
            "api_calls": 0,
            "model_fits": 0,
            "base_llm_updates": 0,
        },
    }


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--protocol-sha256", required=True)
    parser.add_argument("--cards", required=True)
    parser.add_argument("--run-split", required=True)
    parser.add_argument("--decision", required=True)
    parser.add_argument("--producer-result", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> None:
    args = arguments()
    expected = recompute(args)
    producer_path = Path(args.producer_result).resolve()
    producer = prior.object_json(producer_path)
    check(producer == expected, "producer aggregate differs from independent recomputation")
    receipt = {
        "protocol": "senior-0819-decision-relation-taxonomy-independent-verification-v1",
        "status": "INDEPENDENT_HISTORICAL_DECISION_RELATION_TAXONOMY_VERIFIED",
        "protocol_sha256": args.protocol_sha256,
        "source_commit": expected["source_commit"],
        "classification": expected["classification"],
        "producer_result_sha256": prior.digest(producer_path),
        "producer_imported": False,
        "all_aggregate_fields_equal": True,
        "scope": expected["scope"],
    }
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(receipt["classification"])


if __name__ == "__main__":
    main()
