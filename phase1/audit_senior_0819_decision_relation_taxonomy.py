#!/usr/bin/env python3
"""Aggregate-only relation taxonomy audit for the senior 0819 decision corpus.

The taxonomy uses structural Card metadata only.  It never consumes pair orientation,
scores, labels, model predictions, or prospective cohort values.  Card, run, task,
parent, and pair identities are hashed into anonymous fingerprints but never emitted.
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
    from phase1 import audit_senior_0819_pair_benchmark_integrity as base
except ImportError:  # direct execution from phase1/
    import audit_senior_0819_pair_benchmark_integrity as base


PROTOCOL = "senior-0819-decision-relation-taxonomy-v1"
STATUS = "FROZEN_AFTER_OVERALL_SEMANTICS_BEFORE_SPLIT_SPECIFIC_TAXONOMY"
RECEIPT = "senior-0819-decision-relation-taxonomy-receipt-v1"
CLASSES = (
    "verified_direct_sibling",
    "same_run_declared_context_non_sibling",
    "cross_run_declared_context",
)
COMMIT_RE = re.compile(r"[0-9a-f]{40}")


class TaxonomyError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise TaxonomyError(message)


def sha256(path: Path) -> str:
    require(path.is_file() and not path.is_symlink(), f"unsafe file: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def ratio_payload(value: Fraction) -> dict[str, Any]:
    return {
        "numerator": value.numerator,
        "denominator": value.denominator,
        "decimal_17g": format(float(value), ".17g"),
    }


def fraction(text: str) -> Fraction:
    require(bool(re.fullmatch(r"[0-9]+/[1-9][0-9]*", text)), "invalid fraction")
    numerator, denominator = map(int, text.split("/"))
    return Fraction(numerator, denominator)


@dataclass(frozen=True)
class DecisionRow:
    first: str
    second: str
    parent: str
    task: str
    split: str
    first_run: str
    second_run: str
    parent_run: str
    relation: str

    @property
    def unordered(self) -> tuple[str, str]:
        return tuple(sorted((self.first, self.second)))

    @property
    def ordered(self) -> tuple[str, str]:
        return self.first, self.second


class Components:
    def __init__(self) -> None:
        self.links: dict[str, str] = {}

    def root(self, item: str) -> str:
        self.links.setdefault(item, item)
        root = item
        while self.links[root] != root:
            root = self.links[root]
        while self.links[item] != item:
            next_item = self.links[item]
            self.links[item] = root
            item = next_item
        return root

    def connect(self, left: str, right: str) -> None:
        left_root, right_root = self.root(left), self.root(right)
        if left_root != right_root:
            self.links[max(left_root, right_root)] = min(left_root, right_root)


def load_protocol(path: Path, expected_sha: str) -> dict[str, Any]:
    require(sha256(path) == expected_sha, "protocol SHA mismatch")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), "protocol object required")
    require(value.get("protocol") == PROTOCOL, "protocol name mismatch")
    require(value.get("status") == STATUS, "protocol status mismatch")
    require(value["fixed_taxonomy"]["class_order"] == list(CLASSES), "class order drift")
    known = value["known_before_freeze"]
    require(
        known["overall_rows_seen"] == value["immutable_inputs"]["decision"]["rows"],
        "prior row count drift",
    )
    require(
        0
        <= known["overall_direct_sibling_rows_seen"]
        <= known["overall_declared_context_same_run_rows_seen"]
        <= known["overall_rows_seen"],
        "prior semantic count ordering",
    )
    require(known["overall_same_task_rows_seen"] == known["overall_rows_seen"], "prior task count drift")
    for key in (
        "split_specific_class_counts_seen",
        "test_verified_sibling_task_run_endpoint_component_breadth_seen",
        "per_class_train_test_mix_seen",
        "per_class_dependency_concentration_seen",
        "per_class_identity_fingerprints_seen",
    ):
        require(known[key] is False, f"result seen before freeze: {key}")
    require(COMMIT_RE.fullmatch(value["source"]["senior_branch_commit"]) is not None, "commit")
    return value


def relation_for(
    first: base.CardRef, second: base.CardRef, parent: base.CardRef, parent_id: str
) -> tuple[str, bool, bool]:
    direct = first.parent == second.parent == parent_id
    same_run = first.run == second.run == parent.run
    if direct and same_run:
        relation = CLASSES[0]
    elif same_run:
        relation = CLASSES[1]
    else:
        relation = CLASSES[2]
    return relation, direct, same_run


def read_rows(
    path: Path,
    cards: dict[str, base.CardRef],
    held_runs: set[str],
    expected: dict[str, Any],
) -> tuple[list[DecisionRow], dict[str, int]]:
    rows: list[DecisionRow] = []
    diagnostics: collections.Counter[str] = collections.Counter()
    split_counts: collections.Counter[str] = collections.Counter()
    with path.open(encoding="utf-8") as handle:
        for number, text in enumerate(handle, 1):
            require(bool(text.strip()), f"blank decision row: {number}")
            value = json.loads(text)
            require(isinstance(value, dict), f"decision object: {number}")
            require(frozenset(value) == base.DECISION_FIELDS, f"decision schema: {number}")
            first, second, parent_id = value["better"], value["worse"], value["parent"]
            task, split = value["task"], value["intask_split"]
            require(
                all(isinstance(item, str) and item for item in (first, second, parent_id, task)),
                f"decision identity: {number}",
            )
            require(first != second, f"identical endpoints: {number}")
            require(first in cards and second in cards and parent_id in cards, f"unknown Card: {number}")
            require(split in {"train", "test"}, f"split: {number}")
            first_card, second_card, parent_card = cards[first], cards[second], cards[parent_id]
            require(first_card.task == second_card.task == parent_card.task == task, f"task: {number}")
            endpoint_hold = (first_card.run in held_runs, second_card.run in held_runs)
            require(endpoint_hold[0] == endpoint_hold[1], f"endpoint cross-split: {number}")
            expected_split = "test" if endpoint_hold[0] else "train"
            require(split == expected_split, f"split assignment: {number}")
            parent_split_matches = (parent_card.run in held_runs) == endpoint_hold[0]
            diagnostics["parent_split_matches"] += parent_split_matches
            diagnostics["same_task"] += 1
            relation, direct, same_run = relation_for(
                first_card, second_card, parent_card, parent_id
            )
            diagnostics["direct"] += direct
            diagnostics["same_run"] += same_run
            diagnostics["direct_cross_run"] += direct and not same_run
            diagnostics[f"class:{relation}"] += 1
            split_counts[split] += 1
            rows.append(
                DecisionRow(
                    first,
                    second,
                    parent_id,
                    task,
                    split,
                    first_card.run,
                    second_card.run,
                    parent_card.run,
                    relation,
                )
            )
    require(len(rows) == expected["rows"], "decision row count")
    require(split_counts["train"] == expected["train_rows"], "train row count")
    require(split_counts["test"] == expected["test_rows"], "test row count")
    diagnostics["rows"] = len(rows)
    return rows, dict(diagnostics)


def profile(rows: list[DecisionRow]) -> tuple[dict[str, Any], dict[str, Fraction]]:
    tasks: collections.Counter[str] = collections.Counter()
    runs: collections.Counter[str] = collections.Counter()
    degrees: collections.Counter[str] = collections.Counter()
    graph = Components()
    fingerprint_rows: list[str] = []
    for row in rows:
        tasks[row.task] += 1
        for run in {row.first_run, row.second_run}:
            runs[run] += 1
        degrees[row.first] += 1
        degrees[row.second] += 1
        graph.connect(row.first, row.second)
        first, second = row.unordered
        fingerprint_rows.append(
            "\0".join((row.relation, row.split, first, second, row.parent)) + "\n"
        )
    components = collections.Counter(graph.root(row.first) for row in rows)
    count = len(rows)
    exacts = {
        "maximum_single_task_pair_share": Fraction(max(tasks.values()), count)
        if count
        else Fraction(0, 1),
        "maximum_single_run_pair_share": Fraction(max(runs.values()), count)
        if count
        else Fraction(0, 1),
        "maximum_single_component_pair_share": Fraction(max(components.values()), count)
        if count
        else Fraction(0, 1),
    }
    ordered_degrees = sorted(degrees.values())
    digest = hashlib.sha256("".join(sorted(fingerprint_rows)).encode()).hexdigest()
    return {
        "pairs": count,
        "tasks": len(tasks),
        "physical_runs": len(runs),
        "endpoints": len(degrees),
        "components": len(components),
        "endpoint_degree_median_nearest_rank": (
            ordered_degrees[(len(ordered_degrees) - 1) // 2] if ordered_degrees else 0
        ),
        "endpoint_degree_p90_nearest_rank": (
            ordered_degrees[max(0, math.ceil(0.9 * len(ordered_degrees)) - 1)]
            if ordered_degrees
            else 0
        ),
        "endpoint_degree_maximum": max(ordered_degrees) if ordered_degrees else 0,
        "orientation_free_identity_fingerprint_sha256": digest,
        **{key: ratio_payload(value) for key, value in exacts.items()},
    }, exacts


def overlap_profile(rows: list[DecisionRow]) -> dict[str, int]:
    split_rows = {split: [row for row in rows if row.split == split] for split in ("train", "test")}
    pair_sets = {split: {row.unordered for row in values} for split, values in split_rows.items()}
    endpoint_sets = {
        split: {item for row in values for item in (row.first, row.second)}
        for split, values in split_rows.items()
    }
    referenced_run_sets = {
        split: {
            item
            for row in values
            for item in (row.first_run, row.second_run, row.parent_run)
        }
        for split, values in split_rows.items()
    }
    orientations: dict[tuple[str, str], set[tuple[str, str]]] = collections.defaultdict(set)
    for row in rows:
        orientations[row.unordered].add(row.ordered)
    unique = {row.unordered for row in rows}
    return {
        "train_test_unordered_pair_overlap": len(pair_sets["train"] & pair_sets["test"]),
        "train_test_endpoint_overlap": len(endpoint_sets["train"] & endpoint_sets["test"]),
        "train_test_referenced_physical_run_overlap": len(
            referenced_run_sets["train"] & referenced_run_sets["test"]
        ),
        "duplicate_unordered_pair_rows": len(rows) - len(unique),
        "conflicting_orientation_unordered_pairs": sum(
            len(values) > 1 for values in orientations.values()
        ),
    }


def classify(
    hard: dict[str, bool], support: dict[str, bool]
) -> str:
    if not all(hard.values()):
        return "HISTORICAL_RELATION_AWARE_DECISION_TAXONOMY_INTEGRITY_GATE_FAIL"
    if all(support.values()):
        return "HISTORICAL_RELATION_AWARE_DECISION_TAXONOMY_BROAD_VERIFIED_SIBLING_CORE"
    return "HISTORICAL_RELATION_AWARE_DECISION_TAXONOMY_LIMITED_VERIFIED_SIBLING_CORE"


def audit(args: argparse.Namespace) -> dict[str, Any]:
    protocol_path = Path(args.protocol).resolve()
    protocol = load_protocol(protocol_path, args.protocol_sha256)
    paths = {
        "cards": Path(args.cards).resolve(),
        "run_split": Path(args.run_split).resolve(),
        "decision": Path(args.decision).resolve(),
    }
    observed = {}
    for role, path in paths.items():
        observed[role] = sha256(path)
        require(observed[role] == protocol["immutable_inputs"][role]["sha256"], f"input SHA: {role}")

    all_runs, held_runs = base.load_run_split(paths["run_split"], protocol)
    cards, card_inventory = base.load_cards(paths["cards"], all_runs)
    rows, diagnostics = read_rows(
        paths["decision"], cards, held_runs, protocol["immutable_inputs"]["decision"]
    )

    profiles: dict[str, dict[str, Any]] = {"train": {}, "test": {}}
    exact_profiles: dict[str, dict[str, dict[str, Fraction]]] = {"train": {}, "test": {}}
    counts: dict[str, dict[str, int]] = {}
    for relation in CLASSES:
        counts[relation] = {
            "total": sum(row.relation == relation for row in rows),
            "train": sum(row.relation == relation and row.split == "train" for row in rows),
            "test": sum(row.relation == relation and row.split == "test" for row in rows),
        }
        for split in ("train", "test"):
            selected = [row for row in rows if row.relation == relation and row.split == split]
            profiles[split][relation], exact_profiles[split][relation] = profile(selected)

    train_count = protocol["immutable_inputs"]["decision"]["train_rows"]
    test_count = protocol["immutable_inputs"]["decision"]["test_rows"]
    mix_tv = sum(
        abs(Fraction(counts[name]["train"], train_count) - Fraction(counts[name]["test"], test_count))
        for name in CLASSES
    ) / 2
    overlap = overlap_profile(rows)
    direct_total = counts[CLASSES[0]]["total"]
    same_run_total = direct_total + counts[CLASSES[1]]["total"]
    taxonomy_total = sum(value["total"] for value in counts.values())

    hard = {
        "all_input_hashes_and_reported_counts_exact": True,
        "cards_exactly_cover_frozen_run_manifest": card_inventory["physical_runs"] == len(all_runs),
        "card_ids_unique_and_present_lineage_parents_within_run": True,
        "all_decision_endpoints_parent_tasks_and_splits_valid": (
            diagnostics.get("same_task", 0) == len(rows)
            and diagnostics.get("parent_split_matches", 0) == len(rows)
        ),
        "taxonomy_is_exhaustive_and_mutually_exclusive": taxonomy_total == len(rows),
        "verified_direct_sibling_class_is_semantically_pure": (
            direct_total == diagnostics.get("direct", 0) - diagnostics.get("direct_cross_run", 0)
        ),
        "no_direct_sibling_crosses_physical_run": diagnostics.get("direct_cross_run", 0) == 0,
        "same_run_non_sibling_class_is_semantically_pure": (
            same_run_total == diagnostics.get("same_run", 0)
        ),
        "cross_run_class_is_semantically_pure": (
            counts[CLASSES[2]]["total"] == len(rows) - diagnostics.get("same_run", 0)
        ),
        "train_test_unordered_pair_overlap_zero": overlap["train_test_unordered_pair_overlap"] == 0,
        "train_test_endpoint_overlap_zero": overlap["train_test_endpoint_overlap"] == 0,
        "train_test_physical_run_overlap_zero": overlap[
            "train_test_referenced_physical_run_overlap"
        ] == 0,
        "unordered_pair_duplicates_zero": overlap["duplicate_unordered_pair_rows"] == 0,
        "conflicting_orientations_zero": overlap["conflicting_orientation_unordered_pairs"] == 0,
        "prior_overall_semantic_aggregate_exactly_reproduced": (
            len(rows) == protocol["known_before_freeze"]["overall_rows_seen"]
            and direct_total == protocol["known_before_freeze"]["overall_direct_sibling_rows_seen"]
            and same_run_total
            == protocol["known_before_freeze"]["overall_declared_context_same_run_rows_seen"]
            and diagnostics.get("same_task", 0)
            == protocol["known_before_freeze"]["overall_same_task_rows_seen"]
        ),
    }

    frozen = protocol["verified_sibling_test_support_gates"]
    sibling = profiles["test"][CLASSES[0]]
    sibling_exact = exact_profiles["test"][CLASSES[0]]
    support = {
        "minimum_pairs": sibling["pairs"] >= frozen["minimum_pairs"],
        "minimum_tasks": sibling["tasks"] >= frozen["minimum_tasks"],
        "minimum_physical_runs": sibling["physical_runs"] >= frozen["minimum_physical_runs"],
        "minimum_endpoints": sibling["endpoints"] >= frozen["minimum_endpoints"],
        "minimum_components": sibling["components"] >= frozen["minimum_components"],
        "maximum_single_task_pair_share": sibling_exact["maximum_single_task_pair_share"]
        <= fraction(frozen["maximum_single_task_pair_share"]),
        "maximum_single_run_pair_share": sibling_exact["maximum_single_run_pair_share"]
        <= fraction(frozen["maximum_single_run_pair_share"]),
        "maximum_single_component_pair_share": sibling_exact[
            "maximum_single_component_pair_share"
        ]
        <= fraction(frozen["maximum_single_component_pair_share"]),
    }

    return {
        "protocol": RECEIPT,
        "status": "HISTORICAL_DECISION_RELATION_TAXONOMY_AUDIT_COMPLETE",
        "protocol_sha256": args.protocol_sha256,
        "source_commit": protocol["source"]["senior_branch_commit"],
        "input_sha256": observed,
        "inventory": {
            "cards": card_inventory["cards"],
            "physical_runs": card_inventory["physical_runs"],
            "decision_rows": len(rows),
            "train_rows": train_count,
            "test_rows": test_count,
        },
        "semantic_class_counts": counts,
        "split_class_profiles": profiles,
        "train_test_semantic_mix_total_variation": ratio_payload(mix_tv),
        "split_integrity": overlap,
        "hard_integrity_gates": hard,
        "verified_sibling_test_support_gates": support,
        "classification": classify(hard, support),
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--protocol-sha256", required=True)
    parser.add_argument("--cards", required=True)
    parser.add_argument("--run-split", required=True)
    parser.add_argument("--decision", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = audit(args)
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(result["classification"])


if __name__ == "__main__":
    main()
