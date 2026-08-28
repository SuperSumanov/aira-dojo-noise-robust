#!/usr/bin/env python3
"""Aggregate-only integrity audit for the senior 0819 historical pair benchmark.

This audit deliberately does not score a model.  It verifies the physical-run split,
endpoint separation, exact decision-test preservation, source-pool support, and the
dependency structure of the already reported mixed benchmark.  No task, run, Card,
parent, code, label, or pair identity is emitted.
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


PROTOCOL_NAME = "senior-0819-pair-benchmark-integrity-v1"
PROTOCOL_STATUS = (
    "FROZEN_AFTER_REPORT_AND_SCHEMA_BEFORE_OVERLAP_COMPONENT_AND_RUN_AUDIT"
)
RECEIPT_PROTOCOL = "senior-0819-pair-benchmark-integrity-receipt-v1"
RECEIPT_STATUS = "HISTORICAL_PAIR_BENCHMARK_INTEGRITY_AUDIT_COMPLETE"
COMMIT_RE = re.compile(r"[0-9a-f]{40}")

DECISION_FIELDS = frozenset(
    {
        "better",
        "budget",
        "clears_tau",
        "gap_raw",
        "intask_split",
        "loto_fold",
        "parent",
        "set_size",
        "src",
        "task",
        "worse",
    }
)
VALUE_FIELDS = frozenset(
    {
        "agrees_with_quality",
        "better",
        "budget_secs",
        "budget_steps",
        "clears_tau",
        "gap_raw",
        "intask_split",
        "loto_fold",
        "src",
        "steps_to_best",
        "subtree_sizes",
        "task",
        "worse",
    }
)


class PairIntegrityError(RuntimeError):
    """Raised when an immutable input or integrity invariant fails."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise PairIntegrityError(message)


def file_sha256(path: Path) -> str:
    require(path.is_file() and not path.is_symlink(), f"unsafe file: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def exact(value: Fraction) -> dict[str, Any]:
    return {
        "numerator": value.numerator,
        "denominator": value.denominator,
        "decimal_17g": format(float(value), ".17g"),
    }


def ratio(numerator: int, denominator: int) -> Fraction:
    return Fraction(numerator, denominator) if denominator else Fraction(0, 1)


def parse_fraction(value: Any, label: str) -> Fraction:
    require(isinstance(value, str) and re.fullmatch(r"[0-9]+/[1-9][0-9]*", value), label)
    numerator, denominator = map(int, value.split("/"))
    return Fraction(numerator, denominator)


def load_json_object(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"unsafe JSON: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"object required: {path}")
    return value


class JsonObjectStream:
    """Incrementally yield key/value pairs from one top-level JSON object."""

    def __init__(self, path: Path, chunk_size: int = 1 << 20) -> None:
        require(path.is_file() and not path.is_symlink(), f"unsafe streamed JSON: {path}")
        self.handle = path.open(encoding="utf-8")
        self.chunk_size = chunk_size
        self.buffer = ""
        self.position = 0
        self.eof = False
        self.decoder = json.JSONDecoder()

    def close(self) -> None:
        self.handle.close()

    def _fill(self) -> None:
        if self.position:
            self.buffer = self.buffer[self.position :]
            self.position = 0
        text = self.handle.read(self.chunk_size)
        if text:
            self.buffer += text
        else:
            self.eof = True

    def _skip_space(self) -> None:
        while True:
            while self.position < len(self.buffer) and self.buffer[self.position].isspace():
                self.position += 1
            if self.position < len(self.buffer) or self.eof:
                return
            self._fill()

    def _peek(self) -> str:
        self._skip_space()
        require(self.position < len(self.buffer), "unexpected JSON EOF")
        return self.buffer[self.position]

    def _consume(self, token: str) -> None:
        require(self._peek() == token, f"expected JSON token {token!r}")
        self.position += 1

    def _decode(self) -> Any:
        while True:
            self._skip_space()
            try:
                value, end = self.decoder.raw_decode(self.buffer, self.position)
            except json.JSONDecodeError as error:
                require(not self.eof, f"invalid streamed JSON: {error}")
                self._fill()
                continue
            self.position = end
            return value

    def __iter__(self) -> Iterator[tuple[str, Any]]:
        self._fill()
        self._consume("{")
        first = True
        while True:
            if self._peek() == "}":
                self.position += 1
                break
            if not first:
                self._consume(",")
            key = self._decode()
            require(isinstance(key, str) and key, "invalid top-level run identity")
            self._consume(":")
            yield key, self._decode()
            first = False
        self._skip_space()
        while not self.eof:
            self._fill()
            self._skip_space()
        require(self.position == len(self.buffer), "trailing JSON content")


@dataclass(frozen=True)
class CardRef:
    run: str
    task: str
    parent: str | None


@dataclass(frozen=True)
class PairRef:
    better: str
    worse: str
    task: str
    split: str
    better_run: str
    worse_run: str
    parent: str | None
    signature: str

    @property
    def unordered(self) -> tuple[str, str]:
        return tuple(sorted((self.better, self.worse)))

    @property
    def ordered(self) -> tuple[str, str]:
        return (self.better, self.worse)


def canonical_row(row: dict[str, Any]) -> str:
    try:
        return json.dumps(
            row,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as error:
        raise PairIntegrityError("row is not finite canonical JSON") from error


def load_protocol(path: Path, expected_sha256: str) -> tuple[dict[str, Any], str]:
    observed = file_sha256(path)
    require(observed == expected_sha256, "protocol SHA mismatch")
    protocol = load_json_object(path)
    require(protocol.get("protocol") == PROTOCOL_NAME, "protocol name mismatch")
    require(protocol.get("status") == PROTOCOL_STATUS, "protocol status mismatch")
    known = protocol["known_before_freeze"]
    require(known["report_accuracy_and_scaling_values_seen"] is True, "history disclosure")
    for key in (
        "train_test_pair_overlap_seen",
        "train_test_endpoint_overlap_seen",
        "train_test_physical_run_overlap_seen",
        "mixed_test_exact_preservation_seen",
        "test_component_or_task_concentration_seen",
        "mixed_source_membership_reconstructability_seen",
    ):
        require(known[key] is False, f"result seen before freeze: {key}")
    return protocol, observed


def verify_input_bindings(
    protocol: dict[str, Any], paths: dict[str, Path]
) -> dict[str, str]:
    observed: dict[str, str] = {}
    for role, path in paths.items():
        digest = file_sha256(path)
        require(digest == protocol["immutable_inputs"][role]["sha256"], f"SHA mismatch: {role}")
        observed[role] = digest
    return observed


def load_run_split(path: Path, protocol: dict[str, Any]) -> tuple[set[str], set[str]]:
    value = load_json_object(path)
    require(set(value) == {"all", "hold"}, "run split schema mismatch")
    all_rows, hold_rows = value["all"], value["hold"]
    require(isinstance(all_rows, list) and isinstance(hold_rows, list), "run split lists")
    require(all(isinstance(item, str) and item for item in all_rows + hold_rows), "run IDs")
    all_runs, held_runs = set(all_rows), set(hold_rows)
    require(len(all_runs) == len(all_rows), "duplicate all-run identity")
    require(len(held_runs) == len(hold_rows), "duplicate held-run identity")
    require(held_runs <= all_runs, "held run outside all runs")
    binding = protocol["immutable_inputs"]["run_split"]
    require(len(all_runs) == binding["all_runs_reported"], "all-run count mismatch")
    require(len(held_runs) == binding["held_runs_reported"], "held-run count mismatch")
    return all_runs, held_runs


def load_cards(
    path: Path, all_runs: set[str]
) -> tuple[dict[str, CardRef], dict[str, int]]:
    cards: dict[str, CardRef] = {}
    run_count = card_count = present_parent_edges = orphan_parent_edges = 0
    streamed = JsonObjectStream(path)
    try:
        for run, rows in streamed:
            run_count += 1
            require(run in all_runs, "Card run outside frozen manifest")
            require(isinstance(rows, list) and rows, "run must contain Cards")
            for row in rows:
                require(isinstance(row, dict), "Card object required")
                card = row.get("id")
                task = row.get("task")
                lineage = row.get("lineage")
                require(isinstance(card, str) and card and card not in cards, "duplicate/bad Card ID")
                require(isinstance(task, dict), "Card task object required")
                task_name = task.get("name")
                require(isinstance(task_name, str) and task_name, "Card task name required")
                require(isinstance(lineage, dict), "Card lineage object required")
                parent = lineage.get("parent_id")
                require(parent is None or (isinstance(parent, str) and parent), "bad parent ID")
                cards[card] = CardRef(run=run, task=task_name, parent=parent)
                card_count += 1
    finally:
        streamed.close()
    require(run_count == len(all_runs), "Card run count mismatch")
    require({card.run for card in cards.values()} == all_runs, "Card runs do not cover manifest")
    for card in cards.values():
        if card.parent is None:
            continue
        if card.parent in cards:
            present_parent_edges += 1
            require(cards[card.parent].run == card.run, "present lineage parent crosses run")
            require(cards[card.parent].task == card.task, "present lineage parent crosses task")
        else:
            orphan_parent_edges += 1
    return cards, {
        "physical_runs": run_count,
        "cards": card_count,
        "present_lineage_parent_edges": present_parent_edges,
        "orphan_lineage_parent_edges": orphan_parent_edges,
    }


def expected_schema(role: str, row: dict[str, Any]) -> frozenset[str]:
    fields = frozenset(row)
    if role == "decision":
        require(fields == DECISION_FIELDS, "decision schema mismatch")
    elif role in {"value", "value_hardware_time"}:
        require(fields == VALUE_FIELDS, f"{role} schema mismatch")
    elif role == "mixed":
        require(fields in {DECISION_FIELDS, VALUE_FIELDS}, "mixed schema mismatch")
    else:
        raise PairIntegrityError(f"unknown pair role: {role}")
    return fields


def load_pairs(
    path: Path,
    role: str,
    cards: dict[str, CardRef],
    held_runs: set[str],
    protocol: dict[str, Any],
) -> tuple[list[PairRef], dict[str, Any]]:
    rows: list[PairRef] = []
    split_counts: collections.Counter[str] = collections.Counter()
    schema_counts: collections.Counter[str] = collections.Counter()
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            require(bool(line.strip()), f"blank JSONL row: {role}:{line_number}")
            value = json.loads(line)
            require(isinstance(value, dict), f"pair object required: {role}:{line_number}")
            schema = expected_schema(role, value)
            schema_counts["decision" if schema == DECISION_FIELDS else "value"] += 1
            better, worse = value.get("better"), value.get("worse")
            task, split = value.get("task"), value.get("intask_split")
            require(
                isinstance(better, str)
                and isinstance(worse, str)
                and better
                and worse
                and better != worse,
                f"bad pair endpoints: {role}:{line_number}",
            )
            require(better in cards and worse in cards, f"unknown pair endpoint: {role}:{line_number}")
            require(isinstance(task, str) and task, f"bad pair task: {role}:{line_number}")
            require(split in {"train", "test"}, f"bad pair split: {role}:{line_number}")
            better_card, worse_card = cards[better], cards[worse]
            require(
                better_card.task == worse_card.task == task,
                f"pair/Card task mismatch: {role}:{line_number}",
            )
            in_hold = (better_card.run in held_runs, worse_card.run in held_runs)
            require(in_hold[0] == in_hold[1], f"cross-split pair survived: {role}:{line_number}")
            require(split == ("test" if in_hold[0] else "train"), f"split assignment mismatch: {role}:{line_number}")
            parent: str | None = None
            if schema == DECISION_FIELDS:
                parent = value.get("parent")
                require(isinstance(parent, str) and parent in cards, f"unknown decision parent: {role}:{line_number}")
                require(
                    better_card.parent == worse_card.parent == parent,
                    f"decision pair does not share recorded parent: {role}:{line_number}",
                )
                parent_card = cards[parent]
                require(
                    better_card.run == worse_card.run == parent_card.run,
                    f"decision pair crosses physical run: {role}:{line_number}",
                )
                require(parent_card.task == task, f"decision parent task mismatch: {role}:{line_number}")
            rows.append(
                PairRef(
                    better=better,
                    worse=worse,
                    task=task,
                    split=split,
                    better_run=better_card.run,
                    worse_run=worse_card.run,
                    parent=parent,
                    signature=canonical_row(value),
                )
            )
            split_counts[split] += 1
    binding = protocol["immutable_inputs"][role]
    require(len(rows) == binding["rows"], f"row count mismatch: {role}")
    require(split_counts["train"] == binding["train_rows"], f"train count mismatch: {role}")
    require(split_counts["test"] == binding["test_rows"], f"test count mismatch: {role}")
    return rows, {
        "rows": len(rows),
        "train_rows": split_counts["train"],
        "test_rows": split_counts["test"],
        "decision_schema_rows": schema_counts["decision"],
        "value_schema_rows": schema_counts["value"],
    }


def pair_profile(rows: list[PairRef]) -> dict[str, Any]:
    by_split = {split: [row for row in rows if row.split == split] for split in ("train", "test")}
    pair_sets = {split: {row.unordered for row in values} for split, values in by_split.items()}
    endpoint_sets = {
        split: {endpoint for row in values for endpoint in (row.better, row.worse)}
        for split, values in by_split.items()
    }
    run_sets = {
        split: {run for row in values for run in (row.better_run, row.worse_run)}
        for split, values in by_split.items()
    }
    orientations: dict[tuple[str, str], set[tuple[str, str]]] = collections.defaultdict(set)
    for row in rows:
        orientations[row.unordered].add(row.ordered)
    return {
        "unique_unordered_pairs": len({row.unordered for row in rows}),
        "duplicate_unordered_pair_rows": len(rows) - len({row.unordered for row in rows}),
        "conflicting_orientation_unordered_pairs": sum(
            len(values) > 1 for values in orientations.values()
        ),
        "train_unique_endpoints": len(endpoint_sets["train"]),
        "test_unique_endpoints": len(endpoint_sets["test"]),
        "train_physical_runs": len(run_sets["train"]),
        "test_physical_runs": len(run_sets["test"]),
        "train_test_unordered_pair_overlap": len(pair_sets["train"] & pair_sets["test"]),
        "train_test_endpoint_overlap": len(endpoint_sets["train"] & endpoint_sets["test"]),
        "train_test_physical_run_overlap": len(run_sets["train"] & run_sets["test"]),
        "test_duplicate_unordered_pair_rows": len(by_split["test"]) - len(pair_sets["test"]),
    }


class UnionFind:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def find(self, item: str) -> str:
        self.parent.setdefault(item, item)
        root = item
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[item] != item:
            next_item = self.parent[item]
            self.parent[item] = root
            item = next_item
        return root

    def union(self, left: str, right: str) -> None:
        left_root, right_root = self.find(left), self.find(right)
        if left_root != right_root:
            self.parent[max(left_root, right_root)] = min(left_root, right_root)


def dependency_profile(test_rows: list[PairRef]) -> tuple[dict[str, Any], dict[str, Fraction]]:
    require(bool(test_rows), "empty mixed test")
    task_pairs = collections.Counter(row.task for row in test_rows)
    run_pairs: collections.Counter[str] = collections.Counter()
    degrees: collections.Counter[str] = collections.Counter()
    graph = UnionFind()
    for row in test_rows:
        require(row.better_run == row.worse_run, "mixed decision test pair crosses run")
        run_pairs[row.better_run] += 1
        degrees[row.better] += 1
        degrees[row.worse] += 1
        graph.union(row.better, row.worse)
    component_pairs: collections.Counter[str] = collections.Counter()
    for row in test_rows:
        component_pairs[graph.find(row.better)] += 1
    pair_count = len(test_rows)
    component_square_sum = sum(count * count for count in component_pairs.values())
    exact_values = {
        "maximum_single_task_pair_share": ratio(max(task_pairs.values()), pair_count),
        "maximum_single_run_pair_share": ratio(max(run_pairs.values()), pair_count),
        "maximum_single_component_pair_share": ratio(max(component_pairs.values()), pair_count),
        "component_kish_effective_count": Fraction(pair_count * pair_count, component_square_sum),
    }
    ordered_degrees = sorted(degrees.values())
    median_degree = ordered_degrees[(len(ordered_degrees) - 1) // 2]
    p90_degree = ordered_degrees[max(0, math.ceil(0.9 * len(ordered_degrees)) - 1)]
    return {
        "test_pairs": pair_count,
        "test_tasks": len(task_pairs),
        "test_physical_runs": len(run_pairs),
        "test_endpoints": len(degrees),
        "test_components": len(component_pairs),
        "endpoint_degree_median_nearest_rank": median_degree,
        "endpoint_degree_p90_nearest_rank": p90_degree,
        "endpoint_degree_maximum": max(degrees.values()),
        **{key: exact(value) for key, value in exact_values.items()},
    }, exact_values


def classify(
    hard: dict[str, bool],
    dependency: dict[str, Any],
    exact_values: dict[str, Fraction],
    protocol: dict[str, Any],
) -> tuple[str, dict[str, bool]]:
    broad = protocol["broad_support_gates"]
    gates = {
        "test_pairs": dependency["test_pairs"] >= broad["minimum_test_pairs"],
        "test_tasks": dependency["test_tasks"] >= broad["minimum_test_tasks"],
        "test_physical_runs": dependency["test_physical_runs"]
        >= broad["minimum_test_physical_runs"],
        "test_endpoints": dependency["test_endpoints"] >= broad["minimum_test_endpoints"],
        "test_components": dependency["test_components"] >= broad["minimum_test_components"],
        "single_task_anti_dominance": exact_values["maximum_single_task_pair_share"]
        <= parse_fraction(broad["maximum_single_task_pair_share"], "task cap"),
        "single_run_anti_dominance": exact_values["maximum_single_run_pair_share"]
        <= parse_fraction(broad["maximum_single_run_pair_share"], "run cap"),
        "single_component_anti_dominance": exact_values[
            "maximum_single_component_pair_share"
        ]
        <= parse_fraction(broad["maximum_single_component_pair_share"], "component cap"),
    }
    if not all(hard.values()):
        classification = "HISTORICAL_PAIR_BENCHMARK_INTEGRITY_GATE_FAIL"
    elif all(gates.values()):
        classification = (
            "HISTORICAL_RUN_ENDPOINT_DISJOINT_EXACT_TEST_PRESERVATION_BROAD_SUPPORT"
        )
    else:
        classification = (
            "HISTORICAL_RUN_ENDPOINT_DISJOINT_EXACT_TEST_PRESERVATION_LIMITED_BREADTH"
        )
    require(classification in protocol["classification_order"], "classification not frozen")
    return classification, gates


def audit(args: argparse.Namespace) -> dict[str, Any]:
    protocol, protocol_sha = load_protocol(args.protocol, args.protocol_sha256)
    require(args.source_commit == protocol["source"]["senior_branch_commit"], "source commit")
    paths = {
        "cards": args.cards,
        "run_split": args.run_split,
        "mixed": args.mixed,
        "decision": args.decision,
        "value": args.value,
        "value_hardware_time": args.value_hardware_time,
    }
    hashes = verify_input_bindings(protocol, paths)
    security = load_json_object(args.cards_security_receipt)
    require(security.get("status") == "CREDENTIAL_SCAN_AND_REDACTION_PASS", "Card scan status")
    require(security.get("input_sha256") == hashes["cards"], "Card scan input SHA")
    require(security.get("safe_sha256") == hashes["cards"], "Card safe SHA")
    require(security.get("remaining_credential_hits") == 0, "Card credential hit")
    require(security.get("private_key_markers") == 0, "Card private key marker")
    require(security.get("json_parsed_before_scan") is False, "Card parsed before scan")

    all_runs, held_runs = load_run_split(args.run_split, protocol)
    cards, card_inventory = load_cards(args.cards, all_runs)
    rows: dict[str, list[PairRef]] = {}
    inventories: dict[str, dict[str, Any]] = {}
    profiles: dict[str, dict[str, Any]] = {}
    for role in ("mixed", "decision", "value", "value_hardware_time"):
        role_rows, inventory = load_pairs(paths[role], role, cards, held_runs, protocol)
        rows[role] = role_rows
        inventories[role] = inventory
        profiles[role] = pair_profile(role_rows)

    mixed_test = [row for row in rows["mixed"] if row.split == "test"]
    decision_test = [row for row in rows["decision"] if row.split == "test"]
    exact_test_preservation = collections.Counter(row.signature for row in mixed_test) == collections.Counter(
        row.signature for row in decision_test
    )

    source_train_signatures = {
        role: {row.signature for row in rows[role] if row.split == "train"}
        for role in ("decision", "value", "value_hardware_time")
    }
    membership_counts: collections.Counter[int] = collections.Counter()
    for row in rows["mixed"]:
        if row.split != "train":
            continue
        membership_counts[
            sum(row.signature in signatures for signatures in source_train_signatures.values())
        ] += 1
    source_support = {
        "mixed_train_rows": inventories["mixed"]["train_rows"],
        "membership_multiplicity_zero": membership_counts[0],
        "membership_multiplicity_one": membership_counts[1],
        "membership_multiplicity_two": membership_counts[2],
        "membership_multiplicity_three": membership_counts[3],
        "actual_sampling_origin_uniquely_recoverable": membership_counts[2] == 0
        and membership_counts[3] == 0,
    }

    mixed_profile = profiles["mixed"]
    hard = {
        "all_input_hashes_and_reported_counts_exact": True,
        "cards_exactly_cover_frozen_run_manifest": card_inventory["physical_runs"] == len(all_runs),
        "card_ids_unique_and_present_lineage_parents_within_run": True,
        "all_pair_endpoints_known_and_task_consistent": True,
        "all_pair_split_values_match_frozen_run_membership": True,
        "all_decision_pairs_share_recorded_parent_and_physical_run": True,
        "mixed_test_exactly_preserves_decision_test_multiset": exact_test_preservation,
        "mixed_train_rows_belong_to_declared_source_train_union": membership_counts[0] == 0,
        "mixed_train_test_unordered_pairs_disjoint": mixed_profile[
            "train_test_unordered_pair_overlap"
        ]
        == 0,
        "mixed_train_test_endpoints_disjoint": mixed_profile["train_test_endpoint_overlap"] == 0,
        "mixed_train_test_physical_runs_disjoint": mixed_profile[
            "train_test_physical_run_overlap"
        ]
        == 0,
        "mixed_test_has_no_duplicate_unordered_pairs": mixed_profile[
            "test_duplicate_unordered_pair_rows"
        ]
        == 0,
        "mixed_has_no_conflicting_pair_orientations": mixed_profile[
            "conflicting_orientation_unordered_pairs"
        ]
        == 0,
    }
    require(set(hard) == set(protocol["hard_integrity_gates"]), "hard gate schema drift")

    dependency, dependency_exact = dependency_profile(mixed_test)
    classification, broad_gates = classify(hard, dependency, dependency_exact, protocol)
    return {
        "protocol": RECEIPT_PROTOCOL,
        "status": RECEIPT_STATUS,
        "classification": classification,
        "source_commit": args.source_commit,
        "protocol_sha256": protocol_sha,
        "input_sha256": hashes,
        "card_security_receipt_sha256": file_sha256(args.cards_security_receipt),
        "inventory": {
            **card_inventory,
            "manifest_all_runs": len(all_runs),
            "manifest_held_runs": len(held_runs),
            "manifest_train_runs": len(all_runs - held_runs),
            "datasets": inventories,
        },
        "dataset_integrity_profiles": profiles,
        "mixed_test_exact_preservation": {
            "mixed_test_rows": len(mixed_test),
            "decision_test_rows": len(decision_test),
            "canonical_multiset_equal": exact_test_preservation,
        },
        "mixed_train_source_support": source_support,
        "mixed_test_dependency": dependency,
        "hard_integrity_gates": hard,
        "broad_support_gates": broad_gates,
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


def parse_args() -> argparse.Namespace:
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
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    require(COMMIT_RE.fullmatch(args.source_commit) is not None, "bad source commit")
    require(re.fullmatch(r"[0-9a-f]{64}", args.protocol_sha256) is not None, "bad protocol SHA")
    result = audit(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    require(not args.output.exists(), "refusing to overwrite output")
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


if __name__ == "__main__":
    main()
