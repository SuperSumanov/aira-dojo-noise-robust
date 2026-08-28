#!/usr/bin/env python3
"""Independent verifier for the v11 lineage-aware decision-corpus audit.

This module deliberately does not import the producer.  It independently
reparses every frozen input, rebuilds the taxonomy/core/overlap/support fields,
and requires exact equality with the producer's aggregate scientific payload.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import os
import re
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable


PROTOCOL = "decision-corpus-lineage-audit-v2"
RECEIPT = "decision-corpus-lineage-audit-v2-receipt"
VERIFY_RECEIPT = "independent-decision-corpus-lineage-audit-v2-verification"
RELATIONS = (
    "parent_present_verified_direct_sibling",
    "lineage_verified_orphan_parent_sibling",
    "same_run_declared_context_non_sibling",
    "cross_run_declared_context",
)
PRIMARY = (
    "train:b0", "train:b1", "train:b2", "frozen:b0", "frozen:b1", "frozen:b2"
)


class VerificationError(RuntimeError):
    pass


def check(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def text_digest(path: Path) -> str:
    check(path.is_file() and not path.is_symlink(), f"unsafe file: {path}")
    raw = path.read_bytes()
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise VerificationError(f"non-UTF8 input: {path}") from exc
    normalized = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(normalized).hexdigest()


def binary_digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 << 20), b""):
            result.update(chunk)
    return result.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    check(path.is_file() and not path.is_symlink(), f"unsafe JSON: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    check(isinstance(value, dict), f"object required: {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def parse_ratio(value: str) -> Fraction:
    check(re.fullmatch(r"[0-9]+/[1-9][0-9]*", value) is not None, "bad ratio")
    left, right = value.split("/")
    return Fraction(int(left), int(right))


def packed_ratio(value: Fraction) -> dict[str, Any]:
    return {
        "numerator": value.numerator,
        "denominator": value.denominator,
        "decimal_17g": format(float(value), ".17g"),
    }


def digest_rows(rows: Iterable[tuple[str, ...]]) -> str:
    body = "".join("\0".join(parts) + "\n" for parts in sorted(rows))
    return hashlib.sha256(body.encode()).hexdigest()


def path_from(root: Path, metadata: dict[str, Any]) -> Path:
    path = Path(metadata["path"])
    return path if path.is_absolute() else root / path


class UnionFind:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def find(self, item: str) -> str:
        self.parent.setdefault(item, item)
        trail = []
        while self.parent[item] != item:
            trail.append(item)
            item = self.parent[item]
        for old in trail:
            self.parent[old] = item
        return item

    def add_edge(self, left: str, right: str) -> None:
        a, b = self.find(left), self.find(right)
        if a != b:
            self.parent[max(a, b)] = min(a, b)


def reconstruct(protocol: dict[str, Any], root: Path) -> tuple[dict[str, Any], set[str]]:
    inputs = protocol["immutable_inputs"]
    fixed_files = ("cards", "run_map", "v1_audit_card", "v1_independent_verification")
    fixed_paths = {name: path_from(root, inputs[name]) for name in fixed_files}
    for name, path in fixed_paths.items():
        check(text_digest(path) == inputs[name]["sha256"], f"hash mismatch: {name}")
    pair_paths = {name: path_from(root, spec) for name, spec in inputs["pair_sets"].items()}
    for name, path in pair_paths.items():
        check(text_digest(path) == inputs["pair_sets"][name]["sha256"], f"hash mismatch: {name}")

    cards: dict[str, tuple[str, str, str | None]] = {}
    with fixed_paths["cards"].open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            check(bool(line.strip()), f"blank Card: {line_number}")
            raw = json.loads(line)
            check(isinstance(raw, dict) and {"id", "task", "run_id", "lineage"} <= set(raw), "Card schema")
            identifier, task, run = str(raw["id"]), str(raw["task"]), str(raw["run_id"])
            lineage = raw["lineage"]
            check(identifier and task and run and isinstance(lineage, dict), "Card identity")
            parent_raw = lineage.get("parent_id")
            parent = None if parent_raw is None else str(parent_raw)
            check(identifier not in cards and (parent is None or parent), "Card duplicate/parent")
            cards[identifier] = (task, run, parent)
    check(len(cards) == inputs["cards"]["rows"], "Card count")
    run_map_raw = read_json(fixed_paths["run_map"])
    run_map = {str(key): str(value) for key, value in run_map_raw.items()}
    check(len(run_map) == inputs["run_map"]["entries"] and set(run_map) == set(cards), "run map keys")
    check(all(run_map[key] == cards[key][1] for key in cards), "run map values")

    v1_card = read_json(fixed_paths["v1_audit_card"])
    v1_check = read_json(fixed_paths["v1_independent_verification"])
    check(v1_card.get("status") == protocol["known_before_freeze"]["v1_status"], "v1 status")
    check(v1_check.get("status") == protocol["known_before_freeze"]["v1_independent_status"], "v1 verify status")
    check(v1_check["source_card"]["sha256_normalized_lf"] == inputs["v1_audit_card"]["sha256"], "v1 binding")

    # Rows are anonymous tuples within this process.  Endpoint order is canonicalized immediately.
    rows_by_set: dict[str, list[dict[str, str | int | None]]] = {}
    for name in sorted(pair_paths):
        metadata = inputs["pair_sets"][name]
        partition, budget = metadata["partition"], int(metadata["budget"])
        expected_split = "train" if partition == "train" else "test"
        rows: list[dict[str, str | int | None]] = []
        with pair_paths[name].open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                check(bool(line.strip()), f"blank pair: {name}:{line_number}")
                raw = json.loads(line)
                check({"better", "worse", "parent", "task", "budget", "intask_split"} <= set(raw), "pair schema")
                left, right = sorted((str(raw["better"]), str(raw["worse"])))
                parent, task = str(raw["parent"]), str(raw["task"])
                check(left and right and left != right and parent and task, "pair identity")
                check(left in cards and right in cards, "unknown endpoint")
                left_task, left_run, left_parent = cards[left]
                right_task, right_run, right_parent = cards[right]
                endpoint_card_tasks_match = left_task == right_task
                row_task_matches_endpoints = endpoint_card_tasks_match and left_task == task
                budget_matches = int(raw["budget"]) == budget
                split_matches = str(raw["intask_split"]) == expected_split
                declared_run_matches = raw.get("run_id") is None or (
                    str(raw["run_id"]) == left_run == right_run
                )
                parent_card = cards.get(parent)
                direct = left_parent == right_parent == parent
                same = left_task == right_task and left_run == right_run
                if direct and same and parent_card is not None and parent_card[:2] == (left_task, left_run):
                    relation = RELATIONS[0]
                elif direct and same and parent_card is None:
                    relation = RELATIONS[1]
                elif not same or (
                    parent_card is not None
                    and parent_card[:2] != (task, left_run)
                ):
                    relation = RELATIONS[3]
                elif same:
                    relation = RELATIONS[2]
                else:
                    raise AssertionError("unreachable relation taxonomy branch")
                rows.append({
                    "left": left, "right": right, "parent": parent, "task": task,
                    "left_run": left_run, "right_run": right_run,
                    "parent_run": None if parent_card is None else parent_card[1],
                    "relation": relation, "set": name,
                    "endpoint_card_tasks_match": endpoint_card_tasks_match,
                    "row_task_matches_endpoints": row_task_matches_endpoints,
                    "budget_matches": budget_matches,
                    "split_matches": split_matches,
                    "declared_run_matches": declared_run_matches,
                })
        check(len(rows) == metadata["rows"], f"pair count: {name}")
        rows_by_set[name] = rows

    def profile(rows: list[dict[str, Any]]) -> dict[str, Any]:
        endpoint_degree = collections.Counter(item for row in rows for item in (row["left"], row["right"]))
        tasks = collections.Counter(row["task"] for row in rows)
        runs: collections.Counter[str] = collections.Counter()
        for row in rows:
            for run in {str(row["left_run"]), str(row["right_run"])}:
                runs[run] += 1
        parents = {row["parent"] for row in rows}
        graph = UnionFind()
        for row in rows:
            graph.add_edge(row["left"], row["right"])
        components = {graph.find(row["left"]) for row in rows}
        n = len(rows)
        return {
            "pairs": n,
            "parents": len(parents),
            "endpoints": len(endpoint_degree),
            "physical_runs": len(runs),
            "tasks": len(tasks),
            "components": len(components),
            "maximum_single_task_pair_share": packed_ratio(Fraction(max(tasks.values()), n) if n else Fraction()),
            "maximum_single_run_pair_share": packed_ratio(Fraction(max(runs.values()), n) if n else Fraction()),
        }

    known_sets = protocol["known_before_freeze"]["set_summaries"]
    profiles: dict[str, Any] = {}
    for name, rows in rows_by_set.items():
        relation_counts = {relation: sum(row["relation"] == relation for row in rows) for relation in RELATIONS}
        core = [row for row in rows if row["relation"] == RELATIONS[0]]
        all_profile = profile(rows)
        core_profile = profile(core)
        known = known_sets[name]
        profiles[name] = {
            "all_rows": {
                **all_profile,
                "mapped_parent_choice_sets": len({row["parent"] for row in rows if row["parent_run"] is not None}),
                "duplicate_or_reverse_unordered_pair_rows": len(rows) - len({(row["left"], row["right"]) for row in rows}),
                "row_context_violation_counts": {
                    "endpoint_card_task_disagreement": sum(not row["endpoint_card_tasks_match"] for row in rows),
                    "row_task_mismatch": sum(not row["row_task_matches_endpoints"] for row in rows),
                    "budget_mismatch": sum(not row["budget_matches"] for row in rows),
                    "split_mismatch": sum(not row["split_matches"] for row in rows),
                    "declared_run_mismatch": sum(not row["declared_run_matches"] for row in rows),
                },
            },
            "relation_counts": relation_counts,
            "strict_core": core_profile,
            "quarantine_rows": len(rows) - len(core),
            "strict_core_retention": {
                "pairs": packed_ratio(Fraction(core_profile["pairs"], known["pairs"])),
                "tasks": packed_ratio(Fraction(core_profile["tasks"], known["tasks"])),
                "physical_runs": packed_ratio(Fraction(core_profile["physical_runs"], known["runs"])),
                "endpoints": packed_ratio(Fraction(core_profile["endpoints"], known["endpoints"])),
            },
            "relation_identity_fingerprint_sha256": digest_rows(
                (str(row["relation"]), str(row["set"]), str(row["left"]), str(row["right"]), str(row["parent"]))
                for row in rows
            ),
            "strict_core_identity_fingerprint_sha256": digest_rows(
                (str(row["set"]), str(row["left"]), str(row["right"]), str(row["parent"]))
                for row in core
            ),
        }

    def overlap(left: list[dict[str, Any]], right: list[dict[str, Any]], parent_runs: bool) -> dict[str, int]:
        def collect_runs(rows: list[dict[str, Any]]) -> set[str]:
            values = {str(value) for row in rows for value in (row["left_run"], row["right_run"])}
            if parent_runs:
                values.update(str(row["parent_run"]) for row in rows if row["parent_run"] is not None)
            return values
        return {
            "unordered_pairs": len({(row["left"], row["right"]) for row in left} & {(row["left"], row["right"]) for row in right}),
            "endpoints": len({value for row in left for value in (row["left"], row["right"])} & {value for row in right for value in (row["left"], row["right"])}),
            "parents": len({row["parent"] for row in left} & {row["parent"] for row in right}),
            "referenced_physical_runs": len(collect_runs(left) & collect_runs(right)),
        }

    all_overlap, core_overlap = {}, {}
    for budget in range(3):
        train, frozen = rows_by_set[f"train:b{budget}"], rows_by_set[f"frozen:b{budget}"]
        all_overlap[f"b{budget}"] = overlap(train, frozen, False)
        core_overlap[f"b{budget}"] = overlap(
            [row for row in train if row["relation"] == RELATIONS[0]],
            [row for row in frozen if row["relation"] == RELATIONS[0]],
            True,
        )

    frozen_gates = protocol["support_gates"]
    support: dict[str, dict[str, bool]] = {}
    for name in PRIMARY:
        core, known = profiles[name]["strict_core"], known_sets[name]
        support[name] = {
            "minimum_strict_core_pair_retention": Fraction(core["pairs"], known["pairs"]) >= parse_ratio(frozen_gates["minimum_strict_core_pair_retention"]),
            "minimum_strict_core_task_retention": Fraction(core["tasks"], known["tasks"]) >= parse_ratio(frozen_gates["minimum_strict_core_task_retention"]),
            "minimum_strict_core_run_retention": Fraction(core["physical_runs"], known["runs"]) >= parse_ratio(frozen_gates["minimum_strict_core_run_retention"]),
            "minimum_strict_core_endpoint_retention": Fraction(core["endpoints"], known["endpoints"]) >= parse_ratio(frozen_gates["minimum_strict_core_endpoint_retention"]),
            "maximum_single_task_pair_share": Fraction(core["maximum_single_task_pair_share"]["numerator"], core["maximum_single_task_pair_share"]["denominator"]) <= parse_ratio(frozen_gates["maximum_single_task_pair_share"]),
            "maximum_single_run_pair_share": Fraction(core["maximum_single_run_pair_share"]["numerator"], core["maximum_single_run_pair_share"]["denominator"]) <= parse_ratio(frozen_gates["maximum_single_run_pair_share"]),
        }

    v1_expected = v1_check["verified_same_budget_isolation"]
    v1_counts = all(
        profiles[name]["all_rows"][field] == known_sets[name][known]
        for name in profiles
        for field, known in (("pairs", "pairs"), ("parents", "parents"), ("endpoints", "endpoints"), ("physical_runs", "runs"), ("tasks", "tasks"), ("mapped_parent_choice_sets", "mapped_parent_choice_sets"))
    )
    v1_overlap = all(
        all_overlap[name][field] == v1_expected[name][old]
        for name in all_overlap
        for field, old in (("unordered_pairs", "pairs"), ("endpoints", "endpoints"), ("parents", "parents"), ("referenced_physical_runs", "runs"))
    )
    present_parent_ok = all(
        parent not in cards or cards[parent][:2] == (task, run)
        for task, run, parent in cards.values() if parent is not None
    )
    hard = {
        "all_input_hashes_and_v1_dependencies_exact": True,
        "card_ids_unique_and_run_map_exact": True,
        "present_lineage_parents_share_task_and_physical_run": present_parent_ok,
        "all_pair_endpoints_known_and_row_task_run_split_budget_consistent": all(
            all(count == 0 for count in item["all_rows"]["row_context_violation_counts"].values())
            for item in profiles.values()
        ),
        "taxonomy_exhaustive_and_mutually_exclusive": sum(sum(item["relation_counts"].values()) for item in profiles.values()) == sum(item["all_rows"]["pairs"] for item in profiles.values()),
        "strict_core_all_endpoints_are_direct_children_of_declared_parent": all(cards[str(row["left"])][2] == cards[str(row["right"])][2] == row["parent"] for rows in rows_by_set.values() for row in rows if row["relation"] == RELATIONS[0]),
        "strict_core_all_parent_endpoint_contexts_match": all(row["parent_run"] == row["left_run"] == row["right_run"] and cards[str(row["parent"])][0] == cards[str(row["left"])][0] == cards[str(row["right"])][0] for rows in rows_by_set.values() for row in rows if row["relation"] == RELATIONS[0]),
        "strict_core_and_quarantine_exhaustive_and_disjoint": all(item["strict_core"]["pairs"] + item["quarantine_rows"] == item["all_rows"]["pairs"] for item in profiles.values()),
        "same_budget_strict_core_train_frozen_pair_overlap_zero": all(item["unordered_pairs"] == 0 for item in core_overlap.values()),
        "same_budget_strict_core_train_frozen_endpoint_overlap_zero": all(item["endpoints"] == 0 for item in core_overlap.values()),
        "same_budget_strict_core_train_frozen_parent_overlap_zero": all(item["parents"] == 0 for item in core_overlap.values()),
        "same_budget_strict_core_train_frozen_referenced_run_overlap_zero": all(item["referenced_physical_runs"] == 0 for item in core_overlap.values()),
        "within_set_unordered_duplicates_and_orientation_conflicts_zero": all(item["all_rows"]["duplicate_or_reverse_unordered_pair_rows"] == 0 for item in profiles.values()),
        "v1_set_counts_and_same_budget_overlap_exactly_reproduced": v1_counts and v1_overlap,
        "producer_emits_aggregate_only_without_row_identities": True,
    }
    card_inventory = {
        "cards": len(cards),
        "tasks": len({item[0] for item in cards.values()}),
        "physical_runs": len({item[1] for item in cards.values()}),
        "present_parent_edges": sum(item[2] in cards for item in cards.values() if item[2] is not None),
        "orphan_parent_references": sum(item[2] not in cards for item in cards.values() if item[2] is not None),
    }
    scientific = {
        "card_inventory": card_inventory,
        "set_profiles": profiles,
        "global_relation_counts": {relation: sum(item["relation_counts"][relation] for item in profiles.values()) for relation in RELATIONS},
        "same_budget_all_row_train_frozen_overlap": all_overlap,
        "same_budget_strict_core_train_frozen_overlap": core_overlap,
        "hard_integrity_gates": hard,
        "support_gates": support,
        "hard_integrity_gate_count": {"passed": sum(hard.values()), "total": len(hard)},
        "support_gate_count": {"passed": sum(sum(values.values()) for values in support.values()), "total": sum(len(values) for values in support.values())},
    }
    identities = set(cards) | {item[0] for item in cards.values()} | {item[1] for item in cards.values()}
    for value in strings(scientific):
        check(value not in identities, "independent aggregate leaked identity")
    return scientific, identities


def strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, child in value.items():
            yield str(key)
            yield from strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from strings(child)


def expected_class(scientific: dict[str, Any], protocol: dict[str, Any]) -> str:
    rules = protocol["classification_rule"]
    hard = scientific["hard_integrity_gates"]
    if not all(hard.values()):
        return rules["integrity_failure"]
    support_pass = all(all(values.values()) for values in scientific["support_gates"].values())
    profiles = scientific["set_profiles"]
    total = sum(item["all_rows"]["pairs"] for item in profiles.values())
    core = sum(item["relation_counts"][RELATIONS[0]] for item in profiles.values())
    direct = core + sum(item["relation_counts"][RELATIONS[1]] for item in profiles.values())
    if support_pass and core == total:
        return rules["all_rows_parent_present_direct_and_support_pass"]
    if support_pass and direct == total:
        return rules["all_rows_lineage_direct_and_support_pass"]
    if support_pass:
        return rules["strict_core_support_pass"]
    return rules["otherwise"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--protocol-sha256", required=True)
    parser.add_argument("--root", default=".")
    parser.add_argument("--producer-result", required=True)
    parser.add_argument("--producer-script", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    protocol_path, root = Path(args.protocol).resolve(), Path(args.root).resolve()
    check(text_digest(protocol_path) == args.protocol_sha256, "protocol hash")
    protocol = read_json(protocol_path)
    check(protocol.get("protocol") == PROTOCOL, "protocol name")
    producer_path, script_path = Path(args.producer_result).resolve(), Path(args.producer_script).resolve()
    producer = read_json(producer_path)
    check(producer.get("protocol") == RECEIPT, "producer receipt")
    check(producer.get("protocol_sha256") == args.protocol_sha256, "producer protocol binding")
    check(producer.get("provenance", {}).get("producer_script_sha256") == text_digest(script_path), "producer script binding")
    rebuilt, _identities = reconstruct(protocol, root)
    exact = rebuilt == producer.get("scientific")
    check(exact, "producer/verifier scientific mismatch")
    classification = expected_class(rebuilt, protocol)
    check(classification == producer.get("classification"), "classification mismatch")
    scope = producer.get("scope", {})
    check(scope.get("pair_orientation_used") is False, "orientation scope")
    check(scope.get("grade_gap_label_prediction_accuracy_or_utility_used") is False, "outcome scope")
    check(scope.get("prospective_values_read") is False and scope.get("row_level_release_created") is False, "prospective/release scope")
    payload = {
        "protocol": VERIFY_RECEIPT,
        "status": "INDEPENDENTLY_VERIFIED_DECISION_CORPUS_LINEAGE_AUDIT_V2",
        "classification": classification,
        "protocol_sha256": args.protocol_sha256,
        "producer_result_sha256": binary_digest(producer_path),
        "producer_script_sha256": text_digest(script_path),
        "verifier_script_sha256": text_digest(Path(__file__).resolve()),
        "imports_producer": False,
        "all_aggregate_fields_equal": exact,
        "hard_integrity_gate_count": rebuilt["hard_integrity_gate_count"],
        "support_gate_count": rebuilt["support_gate_count"],
        "prospective_values_read": False,
        "row_level_release_created": False,
    }
    write_json(Path(args.output).resolve(), payload)
    print(classification)


if __name__ == "__main__":
    main()
