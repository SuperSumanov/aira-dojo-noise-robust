#!/usr/bin/env python3
"""Independent recomputation of the senior 0819 pair benchmark integrity receipt.

This module intentionally does not import the producer.
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
from typing import Any, Iterator


FROZEN_PROTOCOL = "senior-0819-pair-benchmark-integrity-v1"
FROZEN_STATUS = "FROZEN_AFTER_REPORT_AND_SCHEMA_BEFORE_OVERLAP_COMPONENT_AND_RUN_AUDIT"
RESULT_PROTOCOL = "senior-0819-pair-benchmark-integrity-receipt-v1"
RESULT_STATUS = "HISTORICAL_PAIR_BENCHMARK_INTEGRITY_AUDIT_COMPLETE"

DECISION_KEYS = frozenset(
    "better budget clears_tau gap_raw intask_split loto_fold parent set_size src task worse".split()
)
VALUE_KEYS = frozenset(
    "agrees_with_quality better budget_secs budget_steps clears_tau gap_raw intask_split loto_fold src steps_to_best subtree_sizes task worse".split()
)


class IndependentIntegrityError(RuntimeError):
    pass


def check(condition: bool, message: str) -> None:
    if not condition:
        raise IndependentIntegrityError(message)


def digest(path: Path) -> str:
    check(path.is_file() and not path.is_symlink(), f"unsafe path: {path}")
    value = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(4 << 20)
            if not block:
                break
            value.update(block)
    return value.hexdigest()


def fraction_payload(value: Fraction) -> dict[str, Any]:
    return {
        "numerator": value.numerator,
        "denominator": value.denominator,
        "decimal_17g": format(float(value), ".17g"),
    }


def divide(left: int, right: int) -> Fraction:
    return Fraction(left, right) if right else Fraction(0, 1)


def fraction_text(text: str) -> Fraction:
    check(bool(re.fullmatch(r"[0-9]+/[1-9][0-9]*", text)), "bad frozen fraction")
    left, right = text.split("/")
    return Fraction(int(left), int(right))


def object_json(path: Path) -> dict[str, Any]:
    check(path.is_file() and not path.is_symlink(), f"unsafe JSON: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    check(isinstance(value, dict), "JSON object required")
    return value


class RunReader:
    """Second, independently named incremental decoder for the top-level run map."""

    def __init__(self, path: Path) -> None:
        check(path.is_file() and not path.is_symlink(), "unsafe Card map")
        self.stream = path.open(encoding="utf-8")
        self.text = ""
        self.cursor = 0
        self.done = False
        self.decoder = json.JSONDecoder()

    def finish(self) -> None:
        self.stream.close()

    def refill(self) -> None:
        self.text = self.text[self.cursor :]
        self.cursor = 0
        part = self.stream.read(768 * 1024)
        if part:
            self.text += part
        else:
            self.done = True

    def whitespace(self) -> None:
        while True:
            while self.cursor < len(self.text) and self.text[self.cursor] in " \t\r\n":
                self.cursor += 1
            if self.cursor < len(self.text) or self.done:
                return
            self.refill()

    def symbol(self) -> str:
        self.whitespace()
        check(self.cursor < len(self.text), "unexpected end of Card map")
        return self.text[self.cursor]

    def take(self, symbol: str) -> None:
        check(self.symbol() == symbol, f"missing symbol: {symbol}")
        self.cursor += 1

    def value(self) -> Any:
        while True:
            self.whitespace()
            try:
                value, end = self.decoder.raw_decode(self.text, self.cursor)
            except json.JSONDecodeError as error:
                check(not self.done, f"invalid Card map: {error}")
                self.refill()
                continue
            self.cursor = end
            return value

    def runs(self) -> Iterator[tuple[str, list[Any]]]:
        self.refill()
        self.take("{")
        comma = False
        while self.symbol() != "}":
            if comma:
                self.take(",")
            run = self.value()
            self.take(":")
            cards = self.value()
            check(isinstance(run, str) and isinstance(cards, list), "bad run entry")
            yield run, cards
            comma = True
        self.take("}")
        self.whitespace()
        while not self.done:
            self.refill()
            self.whitespace()
        check(self.cursor == len(self.text), "Card map trailing content")


@dataclass(frozen=True)
class Node:
    run: str
    task: str
    ancestor: str | None


@dataclass(frozen=True)
class Edge:
    high: str
    low: str
    task: str
    split: str
    run_high: str
    run_low: str
    parent: str | None
    serialized: str

    def unordered(self) -> tuple[str, str]:
        return (self.high, self.low) if self.high < self.low else (self.low, self.high)

    def ordered(self) -> tuple[str, str]:
        return self.high, self.low


def stable_row(row: dict[str, Any]) -> str:
    try:
        return json.dumps(
            row,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as error:
        raise IndependentIntegrityError("noncanonical row") from error


def protocol_and_hash(path: Path, expected: str) -> tuple[dict[str, Any], str]:
    actual = digest(path)
    check(actual == expected, "protocol digest mismatch")
    value = object_json(path)
    check(value.get("protocol") == FROZEN_PROTOCOL, "protocol mismatch")
    check(value.get("status") == FROZEN_STATUS, "freeze status mismatch")
    prior = value["known_before_freeze"]
    check(prior["report_accuracy_and_scaling_values_seen"] is True, "prior disclosure")
    unseen = [key for key in prior if key.endswith("_seen") and key not in {"report_accuracy_and_scaling_values_seen", "input_row_counts_seen", "input_field_schemas_seen", "run_manifest_counts_seen"}]
    check(all(prior[key] is False for key in unseen), "audit result seen before freeze")
    return value, actual


def manifest(path: Path, protocol: dict[str, Any]) -> tuple[set[str], set[str]]:
    value = object_json(path)
    check(set(value) == {"all", "hold"}, "manifest schema")
    all_list, hold_list = value["all"], value["hold"]
    check(isinstance(all_list, list) and isinstance(hold_list, list), "manifest lists")
    check(all(isinstance(item, str) and item for item in all_list + hold_list), "manifest IDs")
    all_runs, held = set(all_list), set(hold_list)
    check(len(all_runs) == len(all_list) and len(held) == len(hold_list), "manifest duplicate")
    check(held <= all_runs, "held outside manifest")
    frozen = protocol["immutable_inputs"]["run_split"]
    check(len(all_runs) == frozen["all_runs_reported"], "manifest all count")
    check(len(held) == frozen["held_runs_reported"], "manifest hold count")
    return all_runs, held


def card_index(path: Path, expected_runs: set[str]) -> tuple[dict[str, Node], dict[str, int]]:
    nodes: dict[str, Node] = {}
    seen_runs: set[str] = set()
    reader = RunReader(path)
    try:
        for run, records in reader.runs():
            check(run in expected_runs and run not in seen_runs and records, "bad Card run")
            seen_runs.add(run)
            for record in records:
                check(isinstance(record, dict), "Card must be object")
                identifier = record.get("id")
                task = record.get("task")
                lineage = record.get("lineage")
                check(isinstance(identifier, str) and identifier and identifier not in nodes, "Card ID")
                check(isinstance(task, dict) and isinstance(task.get("name"), str) and task["name"], "Card task")
                check(isinstance(lineage, dict), "Card lineage")
                parent = lineage.get("parent_id")
                check(parent is None or (isinstance(parent, str) and parent), "Card parent")
                nodes[identifier] = Node(run, task["name"], parent)
    finally:
        reader.finish()
    check(seen_runs == expected_runs, "Card run coverage")
    present = missing = 0
    for node in nodes.values():
        if node.ancestor is None:
            continue
        if node.ancestor in nodes:
            present += 1
            check(nodes[node.ancestor].run == node.run, "parent run mismatch")
            check(nodes[node.ancestor].task == node.task, "parent task mismatch")
        else:
            missing += 1
    return nodes, {
        "physical_runs": len(seen_runs),
        "cards": len(nodes),
        "present_lineage_parent_edges": present,
        "orphan_lineage_parent_edges": missing,
    }


def rows_for(
    path: Path,
    role: str,
    nodes: dict[str, Node],
    held: set[str],
    protocol: dict[str, Any],
) -> tuple[list[Edge], dict[str, Any]]:
    result: list[Edge] = []
    splits = collections.Counter()
    schemas = collections.Counter()
    with path.open(encoding="utf-8") as handle:
        for number, text in enumerate(handle, 1):
            check(bool(text.strip()), f"blank row {role}:{number}")
            row = json.loads(text)
            check(isinstance(row, dict), "pair row type")
            keys = frozenset(row)
            if role == "decision":
                check(keys == DECISION_KEYS, "decision fields")
            elif role in {"value", "value_hardware_time"}:
                check(keys == VALUE_KEYS, "value fields")
            else:
                check(keys in {DECISION_KEYS, VALUE_KEYS}, "mixed fields")
            kind = "decision" if keys == DECISION_KEYS else "value"
            schemas[kind] += 1
            high, low = row.get("better"), row.get("worse")
            task, split = row.get("task"), row.get("intask_split")
            check(isinstance(high, str) and isinstance(low, str) and high != low, "pair endpoints")
            check(high in nodes and low in nodes, "unknown endpoint")
            check(isinstance(task, str) and task and split in {"train", "test"}, "pair metadata")
            high_node, low_node = nodes[high], nodes[low]
            check(high_node.task == low_node.task == task, "task mismatch")
            high_hold, low_hold = high_node.run in held, low_node.run in held
            check(high_hold == low_hold, "cross-boundary pair")
            check(split == ("test" if high_hold else "train"), "split mismatch")
            parent = None
            if kind == "decision":
                parent = row.get("parent")
                check(isinstance(parent, str) and parent in nodes, "decision parent")
                check(high_node.ancestor == parent and low_node.ancestor == parent, "shared parent")
                check(high_node.run == low_node.run == nodes[parent].run, "decision run")
                check(nodes[parent].task == task, "decision parent task")
            result.append(
                Edge(high, low, task, split, high_node.run, low_node.run, parent, stable_row(row))
            )
            splits[split] += 1
    frozen = protocol["immutable_inputs"][role]
    check(len(result) == frozen["rows"], "row count")
    check(splits["train"] == frozen["train_rows"], "train count")
    check(splits["test"] == frozen["test_rows"], "test count")
    return result, {
        "rows": len(result),
        "train_rows": splits["train"],
        "test_rows": splits["test"],
        "decision_schema_rows": schemas["decision"],
        "value_schema_rows": schemas["value"],
    }


def integrity_profile(edges: list[Edge]) -> dict[str, Any]:
    split_edges = {name: [edge for edge in edges if edge.split == name] for name in ("train", "test")}
    pair_sets = {name: {edge.unordered() for edge in values} for name, values in split_edges.items()}
    endpoints = {
        name: {item for edge in values for item in (edge.high, edge.low)}
        for name, values in split_edges.items()
    }
    runs = {
        name: {item for edge in values for item in (edge.run_high, edge.run_low)}
        for name, values in split_edges.items()
    }
    orientations: dict[tuple[str, str], set[tuple[str, str]]] = collections.defaultdict(set)
    for edge in edges:
        orientations[edge.unordered()].add(edge.ordered())
    all_pairs = {edge.unordered() for edge in edges}
    return {
        "unique_unordered_pairs": len(all_pairs),
        "duplicate_unordered_pair_rows": len(edges) - len(all_pairs),
        "conflicting_orientation_unordered_pairs": sum(len(value) > 1 for value in orientations.values()),
        "train_unique_endpoints": len(endpoints["train"]),
        "test_unique_endpoints": len(endpoints["test"]),
        "train_physical_runs": len(runs["train"]),
        "test_physical_runs": len(runs["test"]),
        "train_test_unordered_pair_overlap": len(pair_sets["train"] & pair_sets["test"]),
        "train_test_endpoint_overlap": len(endpoints["train"] & endpoints["test"]),
        "train_test_physical_run_overlap": len(runs["train"] & runs["test"]),
        "test_duplicate_unordered_pair_rows": len(split_edges["test"]) - len(pair_sets["test"]),
    }


class Components:
    def __init__(self) -> None:
        self.links: dict[str, str] = {}

    def root(self, item: str) -> str:
        if item not in self.links:
            self.links[item] = item
        chain = []
        while self.links[item] != item:
            chain.append(item)
            item = self.links[item]
        for member in chain:
            self.links[member] = item
        return item

    def connect(self, first: str, second: str) -> None:
        left, right = self.root(first), self.root(second)
        if left != right:
            if left < right:
                self.links[right] = left
            else:
                self.links[left] = right


def dependency(edges: list[Edge]) -> tuple[dict[str, Any], dict[str, Fraction]]:
    check(bool(edges), "empty test")
    tasks = collections.Counter()
    runs = collections.Counter()
    degrees = collections.Counter()
    graph = Components()
    for edge in edges:
        check(edge.run_high == edge.run_low, "test decision pair run mismatch")
        tasks[edge.task] += 1
        runs[edge.run_high] += 1
        degrees[edge.high] += 1
        degrees[edge.low] += 1
        graph.connect(edge.high, edge.low)
    components = collections.Counter(graph.root(edge.high) for edge in edges)
    total = len(edges)
    squared = sum(value * value for value in components.values())
    exacts = {
        "maximum_single_task_pair_share": divide(max(tasks.values()), total),
        "maximum_single_run_pair_share": divide(max(runs.values()), total),
        "maximum_single_component_pair_share": divide(max(components.values()), total),
        "component_kish_effective_count": Fraction(total * total, squared),
    }
    degree_values = sorted(degrees.values())
    return {
        "test_pairs": total,
        "test_tasks": len(tasks),
        "test_physical_runs": len(runs),
        "test_endpoints": len(degrees),
        "test_components": len(components),
        "endpoint_degree_median_nearest_rank": degree_values[(len(degree_values) - 1) // 2],
        "endpoint_degree_p90_nearest_rank": degree_values[max(0, math.ceil(len(degree_values) * 0.9) - 1)],
        "endpoint_degree_maximum": max(degree_values),
        **{name: fraction_payload(value) for name, value in exacts.items()},
    }, exacts


def category(
    integrity: dict[str, bool],
    profile: dict[str, Any],
    exacts: dict[str, Fraction],
    protocol: dict[str, Any],
) -> tuple[str, dict[str, bool]]:
    frozen = protocol["broad_support_gates"]
    gates = {
        "test_pairs": profile["test_pairs"] >= frozen["minimum_test_pairs"],
        "test_tasks": profile["test_tasks"] >= frozen["minimum_test_tasks"],
        "test_physical_runs": profile["test_physical_runs"] >= frozen["minimum_test_physical_runs"],
        "test_endpoints": profile["test_endpoints"] >= frozen["minimum_test_endpoints"],
        "test_components": profile["test_components"] >= frozen["minimum_test_components"],
        "single_task_anti_dominance": exacts["maximum_single_task_pair_share"] <= fraction_text(frozen["maximum_single_task_pair_share"]),
        "single_run_anti_dominance": exacts["maximum_single_run_pair_share"] <= fraction_text(frozen["maximum_single_run_pair_share"]),
        "single_component_anti_dominance": exacts["maximum_single_component_pair_share"] <= fraction_text(frozen["maximum_single_component_pair_share"]),
    }
    if not all(integrity.values()):
        value = "HISTORICAL_PAIR_BENCHMARK_INTEGRITY_GATE_FAIL"
    elif all(gates.values()):
        value = "HISTORICAL_RUN_ENDPOINT_DISJOINT_EXACT_TEST_PRESERVATION_BROAD_SUPPORT"
    else:
        value = "HISTORICAL_RUN_ENDPOINT_DISJOINT_EXACT_TEST_PRESERVATION_LIMITED_BREADTH"
    check(value in protocol["classification_order"], "classification drift")
    return value, gates


def recompute(args: argparse.Namespace) -> dict[str, Any]:
    protocol, protocol_sha = protocol_and_hash(args.protocol, args.protocol_sha256)
    check(args.source_commit == protocol["source"]["senior_branch_commit"], "source commit")
    input_paths = {
        "cards": args.cards,
        "run_split": args.run_split,
        "mixed": args.mixed,
        "decision": args.decision,
        "value": args.value,
        "value_hardware_time": args.value_hardware_time,
    }
    hashes = {name: digest(path) for name, path in input_paths.items()}
    for name, value in hashes.items():
        check(value == protocol["immutable_inputs"][name]["sha256"], f"input digest: {name}")
    scan = object_json(args.cards_security_receipt)
    check(scan.get("status") == "CREDENTIAL_SCAN_AND_REDACTION_PASS", "scan status")
    check(scan.get("input_sha256") == hashes["cards"] == scan.get("safe_sha256"), "scan SHA")
    check(scan.get("remaining_credential_hits") == 0 and scan.get("private_key_markers") == 0, "scan hit")
    check(scan.get("json_parsed_before_scan") is False, "scan chronology")

    all_runs, held = manifest(args.run_split, protocol)
    nodes, cards_inventory = card_index(args.cards, all_runs)
    rows: dict[str, list[Edge]] = {}
    inventories: dict[str, dict[str, Any]] = {}
    profiles: dict[str, dict[str, Any]] = {}
    for role in ("mixed", "decision", "value", "value_hardware_time"):
        edges, inventory = rows_for(input_paths[role], role, nodes, held, protocol)
        rows[role], inventories[role] = edges, inventory
        profiles[role] = integrity_profile(edges)

    mixed_test = [edge for edge in rows["mixed"] if edge.split == "test"]
    decision_test = [edge for edge in rows["decision"] if edge.split == "test"]
    test_equal = collections.Counter(edge.serialized for edge in mixed_test) == collections.Counter(
        edge.serialized for edge in decision_test
    )
    source_sets = {
        role: {edge.serialized for edge in rows[role] if edge.split == "train"}
        for role in ("decision", "value", "value_hardware_time")
    }
    multiplicity = collections.Counter(
        sum(edge.serialized in values for values in source_sets.values())
        for edge in rows["mixed"]
        if edge.split == "train"
    )
    source_support = {
        "mixed_train_rows": inventories["mixed"]["train_rows"],
        "membership_multiplicity_zero": multiplicity[0],
        "membership_multiplicity_one": multiplicity[1],
        "membership_multiplicity_two": multiplicity[2],
        "membership_multiplicity_three": multiplicity[3],
        "actual_sampling_origin_uniquely_recoverable": multiplicity[2] == 0 and multiplicity[3] == 0,
    }
    mixed_profile = profiles["mixed"]
    hard = {
        "all_input_hashes_and_reported_counts_exact": True,
        "cards_exactly_cover_frozen_run_manifest": cards_inventory["physical_runs"] == len(all_runs),
        "card_ids_unique_and_present_lineage_parents_within_run": True,
        "all_pair_endpoints_known_and_task_consistent": True,
        "all_pair_split_values_match_frozen_run_membership": True,
        "all_decision_pairs_share_recorded_parent_and_physical_run": True,
        "mixed_test_exactly_preserves_decision_test_multiset": test_equal,
        "mixed_train_rows_belong_to_declared_source_train_union": multiplicity[0] == 0,
        "mixed_train_test_unordered_pairs_disjoint": mixed_profile["train_test_unordered_pair_overlap"] == 0,
        "mixed_train_test_endpoints_disjoint": mixed_profile["train_test_endpoint_overlap"] == 0,
        "mixed_train_test_physical_runs_disjoint": mixed_profile["train_test_physical_run_overlap"] == 0,
        "mixed_test_has_no_duplicate_unordered_pairs": mixed_profile["test_duplicate_unordered_pair_rows"] == 0,
        "mixed_has_no_conflicting_pair_orientations": mixed_profile["conflicting_orientation_unordered_pairs"] == 0,
    }
    check(set(hard) == set(protocol["hard_integrity_gates"]), "hard gate schema")
    dep, dep_exacts = dependency(mixed_test)
    classification, broad = category(hard, dep, dep_exacts, protocol)
    return {
        "protocol": RESULT_PROTOCOL,
        "status": RESULT_STATUS,
        "classification": classification,
        "source_commit": args.source_commit,
        "protocol_sha256": protocol_sha,
        "input_sha256": hashes,
        "card_security_receipt_sha256": digest(args.cards_security_receipt),
        "inventory": {
            **cards_inventory,
            "manifest_all_runs": len(all_runs),
            "manifest_held_runs": len(held),
            "manifest_train_runs": len(all_runs - held),
            "datasets": inventories,
        },
        "dataset_integrity_profiles": profiles,
        "mixed_test_exact_preservation": {
            "mixed_test_rows": len(mixed_test),
            "decision_test_rows": len(decision_test),
            "canonical_multiset_equal": test_equal,
        },
        "mixed_train_source_support": source_support,
        "mixed_test_dependency": dep,
        "hard_integrity_gates": hard,
        "broad_support_gates": broad,
        "scope": {
            "historical_exploratory_proxy_dataset": True,
            "prospective_first960_or_target300_values_read": False,
            "test_accuracy_or_scaling_computed": False,
            "search_utility_computed": False,
            "raw_senior_archives_opened": False,
            "historical_card_label_fields_used_by_audit_logic": False,
            "identities_or_row_values_emitted": False,
            "gpu_jobs": 0,
            "api_calls": 0,
            "model_fits": 0,
            "base_llm_updates": 0,
        },
    }


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--protocol-sha256", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--cards", type=Path, required=True)
    parser.add_argument("--cards-security-receipt", type=Path, required=True)
    parser.add_argument("--run-split", type=Path, required=True)
    parser.add_argument("--mixed", type=Path, required=True)
    parser.add_argument("--decision", type=Path, required=True)
    parser.add_argument("--value", type=Path, required=True)
    parser.add_argument("--value-hardware-time", type=Path, required=True)
    parser.add_argument("--producer-result", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = arguments()
    check(bool(re.fullmatch(r"[0-9a-f]{40}", args.source_commit)), "source commit format")
    check(bool(re.fullmatch(r"[0-9a-f]{64}", args.protocol_sha256)), "protocol SHA format")
    expected = recompute(args)
    observed = object_json(args.producer_result)
    check(expected == observed, "independent recomputation differs from producer")
    result = {
        "protocol": "senior-0819-pair-benchmark-integrity-independent-verification-v1",
        "status": "INDEPENDENT_HISTORICAL_PAIR_BENCHMARK_INTEGRITY_VERIFIED",
        "classification": expected["classification"],
        "source_commit": args.source_commit,
        "protocol_sha256": args.protocol_sha256,
        "producer_result_sha256": digest(args.producer_result),
        "producer_imported": False,
        "all_aggregate_fields_equal": True,
        "scope": expected["scope"],
    }
    check(not args.output.exists(), "refusing verifier overwrite")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


if __name__ == "__main__":
    main()
