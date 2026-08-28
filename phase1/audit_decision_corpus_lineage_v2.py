#!/usr/bin/env python3
"""Lineage-aware, aggregate-only audit for the historical v11 decision corpus.

The v1 audit established endpoint/run consistency but did not verify that both
endpoints named the declared parent in Card lineage.  This audit adds that
relation check, separates orphan-parent siblings, and certifies a deterministic
parent-present sibling core.  It never uses pair orientation, scores, gaps,
labels, predictions, accuracy, utility, or prospective cohort values.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import os
import re
import subprocess
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable


PROTOCOL = "decision-corpus-lineage-audit-v2"
PROTOCOL_STATUS = "FROZEN_AFTER_V1_SAME_RUN_AUDIT_BEFORE_LINEAGE_READOUT"
RECEIPT = "decision-corpus-lineage-audit-v2-receipt"
CLASSES = (
    "parent_present_verified_direct_sibling",
    "lineage_verified_orphan_parent_sibling",
    "same_run_declared_context_non_sibling",
    "cross_run_declared_context",
)
PRIMARY_SETS = (
    "train:b0",
    "train:b1",
    "train:b2",
    "frozen:b0",
    "frozen:b1",
    "frozen:b2",
)
COMMIT_RE = re.compile(r"[0-9a-f]{40}")


class AuditError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AuditError(message)


def normalized_lf_sha256(path: Path) -> str:
    require(path.is_file() and not path.is_symlink(), f"unsafe input: {path}")
    raw = path.read_bytes()
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AuditError(f"expected UTF-8 input: {path}") from exc
    return hashlib.sha256(raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")).hexdigest()


def raw_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load_object(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"unsafe JSON: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def fraction(text: str) -> Fraction:
    require(bool(re.fullmatch(r"[0-9]+/[1-9][0-9]*", text)), f"invalid fraction: {text}")
    numerator, denominator = (int(piece) for piece in text.split("/"))
    return Fraction(numerator, denominator)


def ratio_payload(value: Fraction) -> dict[str, Any]:
    return {
        "numerator": value.numerator,
        "denominator": value.denominator,
        "decimal_17g": format(float(value), ".17g"),
    }


def identity_fingerprint(rows: Iterable[tuple[str, ...]]) -> str:
    material = "".join("\0".join(row) + "\n" for row in sorted(rows))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Card:
    identifier: str
    task: str
    run: str
    parent: str | None


@dataclass(frozen=True)
class PairRow:
    set_name: str
    partition: str
    budget: int
    first: str
    second: str
    parent: str
    task: str
    first_run: str
    second_run: str
    parent_run: str | None
    relation: str
    endpoint_card_tasks_match: bool
    row_task_matches_endpoints: bool
    budget_matches: bool
    split_matches: bool
    declared_run_matches: bool

    @property
    def unordered(self) -> tuple[str, str]:
        return tuple(sorted((self.first, self.second)))


class Components:
    def __init__(self) -> None:
        self.links: dict[str, str] = {}

    def root(self, value: str) -> str:
        self.links.setdefault(value, value)
        root = value
        while self.links[root] != root:
            root = self.links[root]
        while self.links[value] != value:
            successor = self.links[value]
            self.links[value] = root
            value = successor
        return root

    def connect(self, left: str, right: str) -> None:
        left_root, right_root = self.root(left), self.root(right)
        if left_root != right_root:
            self.links[max(left_root, right_root)] = min(left_root, right_root)


def load_protocol(path: Path, expected_sha: str) -> dict[str, Any]:
    require(normalized_lf_sha256(path) == expected_sha, "protocol SHA mismatch")
    value = load_object(path)
    require(value.get("protocol") == PROTOCOL, "protocol name mismatch")
    require(value.get("status") == PROTOCOL_STATUS, "protocol status mismatch")
    require(value.get("hash_mode") == "normalized_utf8_lf_v1", "hash mode mismatch")
    require(
        value["fixed_relation_taxonomy"]["class_order"] == list(CLASSES),
        "relation taxonomy drift",
    )
    require(
        value["fixed_quarantine_rule"]["keep_only"] == CLASSES[0],
        "quarantine rule drift",
    )
    known = value["known_before_freeze"]
    for key in (
        "lineage_parent_match_counts_seen",
        "relation_counts_by_set_seen",
        "parent_present_core_counts_seen",
        "strict_core_train_frozen_referenced_run_overlap_seen",
        "strict_core_support_and_concentration_seen",
        "strict_core_fingerprints_seen",
    ):
        require(known[key] is False, f"lineage result seen before freeze: {key}")
    require(tuple(value["support_gates"]["applies_to"]) == PRIMARY_SETS, "primary sets drift")
    return value


def resolve(root: Path, specification: dict[str, Any]) -> Path:
    path = Path(specification["path"])
    return path if path.is_absolute() else root / path


def check_input(path: Path, specification: dict[str, Any], role: str) -> None:
    require(normalized_lf_sha256(path) == specification["sha256"], f"input SHA mismatch: {role}")


def load_cards(path: Path, expected_rows: int) -> tuple[dict[str, Card], dict[str, int]]:
    cards: dict[str, Card] = {}
    present_parent_edges = 0
    orphan_parent_references = 0
    with path.open(encoding="utf-8") as handle:
        for number, text in enumerate(handle, 1):
            require(bool(text.strip()), f"blank Card row: {number}")
            value = json.loads(text)
            require(isinstance(value, dict), f"Card object required: {number}")
            require({"id", "task", "run_id", "lineage"} <= set(value), f"Card schema: {number}")
            identifier, task, run = str(value["id"]), str(value["task"]), str(value["run_id"])
            lineage = value["lineage"]
            require(identifier and task and run and isinstance(lineage, dict), f"Card identity: {number}")
            raw_parent = lineage.get("parent_id")
            parent = None if raw_parent is None else str(raw_parent)
            require(parent is None or parent, f"empty parent: {number}")
            require(identifier not in cards, f"duplicate Card id: {number}")
            cards[identifier] = Card(identifier, task, run, parent)
    require(len(cards) == expected_rows, "Card row count mismatch")
    for card in cards.values():
        if card.parent is None:
            continue
        if card.parent in cards:
            present_parent_edges += 1
        else:
            orphan_parent_references += 1
    return cards, {
        "cards": len(cards),
        "tasks": len({card.task for card in cards.values()}),
        "physical_runs": len({card.run for card in cards.values()}),
        "present_parent_edges": present_parent_edges,
        "orphan_parent_references": orphan_parent_references,
    }


def load_run_map(path: Path, cards: dict[str, Card], expected_entries: int) -> dict[str, str]:
    value = load_object(path)
    require(len(value) == expected_entries, "run-map entry count mismatch")
    run_map = {str(key): str(run) for key, run in value.items()}
    require(set(run_map) == set(cards), "run-map/Card key mismatch")
    require(all(run_map[key] == cards[key].run for key in cards), "run-map/Card value mismatch")
    return run_map


def present_parent_context_consistent(cards: dict[str, Card]) -> bool:
    return all(
        card.parent not in cards
        or (
            cards[card.parent].task == card.task
            and cards[card.parent].run == card.run
        )
        for card in cards.values()
        if card.parent is not None
    )


def classify_relation(first: Card, second: Card, parent_id: str, cards: dict[str, Card]) -> str:
    direct = first.parent == second.parent == parent_id
    same_context = first.task == second.task and first.run == second.run
    parent = cards.get(parent_id)
    if direct and same_context and parent is not None and parent.task == first.task and parent.run == first.run:
        return CLASSES[0]
    if direct and same_context and parent is None:
        return CLASSES[1]
    if not same_context or (
        parent is not None
        and (parent.task != first.task or parent.run != first.run)
    ):
        return CLASSES[3]
    if same_context:
        return CLASSES[2]
    raise AssertionError("unreachable relation taxonomy branch")


def load_pair_set(
    path: Path,
    set_name: str,
    specification: dict[str, Any],
    cards: dict[str, Card],
) -> list[PairRow]:
    partition, budget = specification["partition"], int(specification["budget"])
    expected_split = "train" if partition == "train" else "test"
    rows: list[PairRow] = []
    with path.open(encoding="utf-8") as handle:
        for number, text in enumerate(handle, 1):
            require(bool(text.strip()), f"blank pair row: {set_name}:{number}")
            value = json.loads(text)
            require(
                {"better", "worse", "parent", "task", "budget", "intask_split"} <= set(value),
                f"pair schema: {set_name}:{number}",
            )
            first, second = str(value["better"]), str(value["worse"])
            parent_id, task = str(value["parent"]), str(value["task"])
            require(first and second and parent_id and task and first != second, f"pair identity: {set_name}:{number}")
            require(first in cards and second in cards, f"unknown endpoint: {set_name}:{number}")
            first_card, second_card = cards[first], cards[second]
            declared_run = value.get("run_id")
            endpoint_card_tasks_match = first_card.task == second_card.task
            row_task_matches_endpoints = endpoint_card_tasks_match and first_card.task == task
            budget_matches = int(value["budget"]) == budget
            split_matches = str(value["intask_split"]) == expected_split
            declared_run_matches = declared_run is None or (
                str(declared_run) == first_card.run == second_card.run
            )
            parent_card = cards.get(parent_id)
            relation = classify_relation(first_card, second_card, parent_id, cards)
            rows.append(
                PairRow(
                    set_name,
                    partition,
                    budget,
                    first,
                    second,
                    parent_id,
                    task,
                    first_card.run,
                    second_card.run,
                    None if parent_card is None else parent_card.run,
                    relation,
                    endpoint_card_tasks_match,
                    row_task_matches_endpoints,
                    budget_matches,
                    split_matches,
                    declared_run_matches,
                )
            )
    require(len(rows) == int(specification["rows"]), f"pair row count mismatch: {set_name}")
    return rows


def dependency_profile(rows: list[PairRow]) -> dict[str, Any]:
    endpoints = collections.Counter(item for row in rows for item in row.unordered)
    parents = {row.parent for row in rows}
    tasks = collections.Counter(row.task for row in rows)
    runs: collections.Counter[str] = collections.Counter()
    for row in rows:
        for run in {row.first_run, row.second_run}:
            runs[run] += 1
    components = Components()
    for row in rows:
        components.connect(*row.unordered)
    component_counts = collections.Counter(components.root(row.unordered[0]) for row in rows)
    count = len(rows)
    maximum_task = Fraction(max(tasks.values()), count) if count else Fraction(0, 1)
    maximum_run = Fraction(max(runs.values()), count) if count else Fraction(0, 1)
    return {
        "pairs": count,
        "parents": len(parents),
        "endpoints": len(endpoints),
        "physical_runs": len(runs),
        "tasks": len(tasks),
        "components": len(component_counts),
        "maximum_single_task_pair_share": ratio_payload(maximum_task),
        "maximum_single_run_pair_share": ratio_payload(maximum_run),
    }


def set_profile(rows: list[PairRow], known: dict[str, int]) -> dict[str, Any]:
    class_counts = {name: sum(row.relation == name for row in rows) for name in CLASSES}
    core = [row for row in rows if row.relation == CLASSES[0]]
    quarantine = [row for row in rows if row.relation != CLASSES[0]]
    core_profile = dependency_profile(core)
    duplicates = len(rows) - len({row.unordered for row in rows})
    all_profile = dependency_profile(rows)
    retention = {
        "pairs": ratio_payload(Fraction(core_profile["pairs"], known["pairs"])),
        "tasks": ratio_payload(Fraction(core_profile["tasks"], known["tasks"])),
        "physical_runs": ratio_payload(Fraction(core_profile["physical_runs"], known["runs"])),
        "endpoints": ratio_payload(Fraction(core_profile["endpoints"], known["endpoints"])),
    }
    relation_rows = [
        (row.relation, row.set_name, *row.unordered, row.parent) for row in rows
    ]
    core_rows = [(row.set_name, *row.unordered, row.parent) for row in core]
    return {
        "all_rows": {
            **all_profile,
            "mapped_parent_choice_sets": len({row.parent for row in rows if row.parent_run is not None}),
            "duplicate_or_reverse_unordered_pair_rows": duplicates,
            "row_context_violation_counts": {
                "endpoint_card_task_disagreement": sum(not row.endpoint_card_tasks_match for row in rows),
                "row_task_mismatch": sum(not row.row_task_matches_endpoints for row in rows),
                "budget_mismatch": sum(not row.budget_matches for row in rows),
                "split_mismatch": sum(not row.split_matches for row in rows),
                "declared_run_mismatch": sum(not row.declared_run_matches for row in rows),
            },
        },
        "relation_counts": class_counts,
        "strict_core": core_profile,
        "quarantine_rows": len(quarantine),
        "strict_core_retention": retention,
        "relation_identity_fingerprint_sha256": identity_fingerprint(relation_rows),
        "strict_core_identity_fingerprint_sha256": identity_fingerprint(core_rows),
    }


def overlap(left: list[PairRow], right: list[PairRow], include_parent_runs: bool) -> dict[str, int]:
    left_pairs, right_pairs = ({row.unordered for row in side} for side in (left, right))
    left_endpoints = {item for row in left for item in row.unordered}
    right_endpoints = {item for row in right for item in row.unordered}
    left_parents, right_parents = ({row.parent for row in side} for side in (left, right))
    def runs(side: list[PairRow]) -> set[str]:
        values = {item for row in side for item in (row.first_run, row.second_run)}
        if include_parent_runs:
            values.update(row.parent_run for row in side if row.parent_run is not None)
        return values
    return {
        "unordered_pairs": len(left_pairs & right_pairs),
        "endpoints": len(left_endpoints & right_endpoints),
        "parents": len(left_parents & right_parents),
        "referenced_physical_runs": len(runs(left) & runs(right)),
    }


def support_gates(profile: dict[str, Any], known: dict[str, int], frozen: dict[str, Any]) -> dict[str, bool]:
    core = profile["strict_core"]
    return {
        "minimum_strict_core_pair_retention": Fraction(core["pairs"], known["pairs"])
        >= fraction(frozen["minimum_strict_core_pair_retention"]),
        "minimum_strict_core_task_retention": Fraction(core["tasks"], known["tasks"])
        >= fraction(frozen["minimum_strict_core_task_retention"]),
        "minimum_strict_core_run_retention": Fraction(core["physical_runs"], known["runs"])
        >= fraction(frozen["minimum_strict_core_run_retention"]),
        "minimum_strict_core_endpoint_retention": Fraction(core["endpoints"], known["endpoints"])
        >= fraction(frozen["minimum_strict_core_endpoint_retention"]),
        "maximum_single_task_pair_share": Fraction(
            core["maximum_single_task_pair_share"]["numerator"],
            core["maximum_single_task_pair_share"]["denominator"],
        ) <= fraction(frozen["maximum_single_task_pair_share"]),
        "maximum_single_run_pair_share": Fraction(
            core["maximum_single_run_pair_share"]["numerator"],
            core["maximum_single_run_pair_share"]["denominator"],
        ) <= fraction(frozen["maximum_single_run_pair_share"]),
    }


def classify(hard: dict[str, bool], support: dict[str, dict[str, bool]], profiles: dict[str, Any], rules: dict[str, str]) -> str:
    if not all(hard.values()):
        return rules["integrity_failure"]
    support_pass = all(all(values.values()) for values in support.values())
    total = sum(profile["all_rows"]["pairs"] for profile in profiles.values())
    core = sum(profile["relation_counts"][CLASSES[0]] for profile in profiles.values())
    lineage_direct = core + sum(profile["relation_counts"][CLASSES[1]] for profile in profiles.values())
    if support_pass and core == total:
        return rules["all_rows_parent_present_direct_and_support_pass"]
    if support_pass and lineage_direct == total:
        return rules["all_rows_lineage_direct_and_support_pass"]
    if support_pass:
        return rules["strict_core_support_pass"]
    return rules["otherwise"]


def audit(protocol: dict[str, Any], protocol_sha: str, root: Path, source_commit: str) -> dict[str, Any]:
    inputs = protocol["immutable_inputs"]
    paths = {name: resolve(root, inputs[name]) for name in ("cards", "run_map", "v1_audit_card", "v1_independent_verification")}
    for name, path in paths.items():
        check_input(path, inputs[name], name)
    pair_paths = {name: resolve(root, spec) for name, spec in inputs["pair_sets"].items()}
    for name, path in pair_paths.items():
        check_input(path, inputs["pair_sets"][name], name)

    v1_card = load_object(paths["v1_audit_card"])
    v1_verification = load_object(paths["v1_independent_verification"])
    require(v1_card.get("status") == protocol["known_before_freeze"]["v1_status"], "v1 card status")
    require(
        v1_verification.get("status") == protocol["known_before_freeze"]["v1_independent_status"],
        "v1 verification status",
    )
    require(v1_verification.get("source_card", {}).get("sha256_normalized_lf") == inputs["v1_audit_card"]["sha256"], "v1 dependency binding")

    cards, card_inventory = load_cards(paths["cards"], int(inputs["cards"]["rows"]))
    _run_map = load_run_map(paths["run_map"], cards, int(inputs["run_map"]["entries"]))
    all_rows: dict[str, list[PairRow]] = {}
    profiles: dict[str, Any] = {}
    known_sets = protocol["known_before_freeze"]["set_summaries"]
    for name in sorted(pair_paths):
        rows = load_pair_set(pair_paths[name], name, inputs["pair_sets"][name], cards)
        all_rows[name] = rows
        profiles[name] = set_profile(rows, known_sets[name])

    all_overlaps: dict[str, Any] = {}
    core_overlaps: dict[str, Any] = {}
    for budget in range(3):
        train_name, frozen_name = f"train:b{budget}", f"frozen:b{budget}"
        all_overlaps[f"b{budget}"] = overlap(all_rows[train_name], all_rows[frozen_name], False)
        train_core = [row for row in all_rows[train_name] if row.relation == CLASSES[0]]
        frozen_core = [row for row in all_rows[frozen_name] if row.relation == CLASSES[0]]
        core_overlaps[f"b{budget}"] = overlap(train_core, frozen_core, True)

    v1_counts_exact = all(
        profiles[name]["all_rows"][field] == known_sets[name][known_field]
        for name in profiles
        for field, known_field in (
            ("pairs", "pairs"),
            ("parents", "parents"),
            ("endpoints", "endpoints"),
            ("physical_runs", "runs"),
            ("tasks", "tasks"),
            ("mapped_parent_choice_sets", "mapped_parent_choice_sets"),
        )
    )
    expected_v1_overlap = v1_verification["verified_same_budget_isolation"]
    v1_overlap_exact = all(
        all_overlaps[name][field] == expected_v1_overlap[name][expected]
        for name in all_overlaps
        for field, expected in (
            ("unordered_pairs", "pairs"),
            ("endpoints", "endpoints"),
            ("parents", "parents"),
            ("referenced_physical_runs", "runs"),
        )
    )
    support = {
        name: support_gates(profiles[name], known_sets[name], protocol["support_gates"])
        for name in PRIMARY_SETS
    }

    all_card_identities = set(cards)
    all_run_identities = {card.run for card in cards.values()}
    all_task_identities = {card.task for card in cards.values()}
    duplicate_free = all(
        profile["all_rows"]["duplicate_or_reverse_unordered_pair_rows"] == 0
        for profile in profiles.values()
    )
    relation_total = sum(sum(profile["relation_counts"].values()) for profile in profiles.values())
    row_total = sum(profile["all_rows"]["pairs"] for profile in profiles.values())
    hard = {
        "all_input_hashes_and_v1_dependencies_exact": True,
        "card_ids_unique_and_run_map_exact": True,
        "present_lineage_parents_share_task_and_physical_run": present_parent_context_consistent(cards),
        "all_pair_endpoints_known_and_row_task_run_split_budget_consistent": all(
            all(count == 0 for count in profile["all_rows"]["row_context_violation_counts"].values())
            for profile in profiles.values()
        ),
        "taxonomy_exhaustive_and_mutually_exclusive": relation_total == row_total,
        "strict_core_all_endpoints_are_direct_children_of_declared_parent": all(
            cards[row.first].parent == cards[row.second].parent == row.parent
            for rows in all_rows.values()
            for row in rows
            if row.relation == CLASSES[0]
        ),
        "strict_core_all_parent_endpoint_contexts_match": all(
            row.parent_run == row.first_run == row.second_run
            and cards[row.parent].task == cards[row.first].task == cards[row.second].task
            for rows in all_rows.values()
            for row in rows
            if row.relation == CLASSES[0]
        ),
        "strict_core_and_quarantine_exhaustive_and_disjoint": all(
            profile["strict_core"]["pairs"] + profile["quarantine_rows"]
            == profile["all_rows"]["pairs"]
            for profile in profiles.values()
        ),
        "same_budget_strict_core_train_frozen_pair_overlap_zero": all(
            value["unordered_pairs"] == 0 for value in core_overlaps.values()
        ),
        "same_budget_strict_core_train_frozen_endpoint_overlap_zero": all(
            value["endpoints"] == 0 for value in core_overlaps.values()
        ),
        "same_budget_strict_core_train_frozen_parent_overlap_zero": all(
            value["parents"] == 0 for value in core_overlaps.values()
        ),
        "same_budget_strict_core_train_frozen_referenced_run_overlap_zero": all(
            value["referenced_physical_runs"] == 0 for value in core_overlaps.values()
        ),
        "within_set_unordered_duplicates_and_orientation_conflicts_zero": duplicate_free,
        "v1_set_counts_and_same_budget_overlap_exactly_reproduced": v1_counts_exact and v1_overlap_exact,
        "producer_emits_aggregate_only_without_row_identities": True,
    }
    classification = classify(hard, support, profiles, protocol["classification_rule"])
    global_relation_counts = {
        name: sum(profile["relation_counts"][name] for profile in profiles.values())
        for name in CLASSES
    }
    scientific = {
        "card_inventory": card_inventory,
        "set_profiles": profiles,
        "global_relation_counts": global_relation_counts,
        "same_budget_all_row_train_frozen_overlap": all_overlaps,
        "same_budget_strict_core_train_frozen_overlap": core_overlaps,
        "hard_integrity_gates": hard,
        "support_gates": support,
        "hard_integrity_gate_count": {"passed": sum(hard.values()), "total": len(hard)},
        "support_gate_count": {
            "passed": sum(sum(values.values()) for values in support.values()),
            "total": sum(len(values) for values in support.values()),
        },
    }
    forbidden_exact = all_card_identities | all_run_identities | all_task_identities
    for value in walk_strings(scientific):
        require(value not in forbidden_exact, "aggregate output leaked a row identity")
    return {
        "protocol": RECEIPT,
        "status": "HISTORICAL_V11_LINEAGE_AUDIT_COMPLETE",
        "classification": classification,
        "protocol_sha256": protocol_sha,
        "scientific": scientific,
        "scope": {
            "pair_orientation_used": False,
            "grade_gap_label_prediction_accuracy_or_utility_used": False,
            "prospective_values_read": False,
            "raw_senior_archives_read": False,
            "row_level_release_created": False,
            "gpu_api_model_fit_base_update": "0/0/0/0",
        },
        "provenance": {
            "source_commit": source_commit,
            "producer_script_sha256": normalized_lf_sha256(Path(__file__).resolve()),
            "input_hash_mode": "normalized_utf8_lf_v1",
        },
    }


def walk_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, child in value.items():
            yield str(key)
            yield from walk_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_strings(child)


def current_commit(root: Path) -> str:
    value = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
    ).strip()
    require(COMMIT_RE.fullmatch(value) is not None, "invalid source commit")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--protocol-sha256", required=True)
    parser.add_argument("--root", default=".")
    parser.add_argument("--source-commit")
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(args.root).resolve()
    source_commit = args.source_commit or current_commit(root)
    require(COMMIT_RE.fullmatch(source_commit) is not None, "invalid --source-commit")
    protocol_path = Path(args.protocol).resolve()
    protocol = load_protocol(protocol_path, args.protocol_sha256)
    payload = audit(protocol, args.protocol_sha256, root, source_commit)
    atomic_json(Path(args.output).resolve(), payload)
    print(payload["classification"])


if __name__ == "__main__":
    main()
