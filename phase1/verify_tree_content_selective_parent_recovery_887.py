#!/usr/bin/env python3
"""Independent verifier for the snapshot-887 selective parent recovery audit.

This module intentionally does not import the producer.  It uses the separate
snapshot and fingerprint verifier implementations and recomputes every field.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

from phase1 import verify_prospective_fuzzy_code_clones as fingerprint_check
from phase1 import verify_tree_within_stratum_forward_target522 as snapshot_check


PROTOCOL = "tree-content-selective-parent-recovery-887-v1"
STATUS = "OUTCOME_BLIND_DEVELOPMENT_SPLIT_FROZEN_BEFORE_MARGIN_READOUT"
RESULT_STATUS = "OUTCOME_BLIND_DEVELOPMENT_SELECTIVE_PARENT_RECOVERY_COMPLETE"
VERIFY_STATUS = "INDEPENDENT_SELECTIVE_PARENT_RECOVERY_VERIFIED"
SHA_PATTERN = re.compile(r"[0-9a-f]{64}")
COMMIT_PATTERN = re.compile(r"[0-9a-f]{40}")


class SelectiveParentVerificationError(RuntimeError):
    """Raised when independent recomputation or binding comparison fails."""


@dataclass(frozen=True)
class Observation:
    task: str
    run: str
    candidate_count: int
    unique: bool
    right: bool
    best: Fraction
    gap: Fraction


def check(condition: bool, message: str) -> None:
    if not condition:
        raise SelectiveParentVerificationError(message)


def digest_file(path: Path) -> str:
    check(path.is_file() and not path.is_symlink(), f"unsafe file: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(1 << 20)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def fraction_payload(value: Fraction) -> dict[str, Any]:
    return {
        "numerator": value.numerator,
        "denominator": value.denominator,
        "decimal_17g": format(float(value), ".17g"),
    }


def quotient(part: int, whole: int) -> Fraction:
    return Fraction(part, whole) if whole else Fraction(0, 1)


def decode(value: dict[str, Any], label: str) -> Fraction:
    check(isinstance(value, dict), f"missing exact payload: {label}")
    check(set(value) == {"numerator", "denominator", "decimal_17g"}, f"bad exact keys: {label}")
    numerator, denominator = value["numerator"], value["denominator"]
    check(
        isinstance(numerator, int)
        and not isinstance(numerator, bool)
        and isinstance(denominator, int)
        and not isinstance(denominator, bool)
        and denominator > 0,
        f"bad exact fraction: {label}",
    )
    exact_value = Fraction(numerator, denominator)
    check(value["decimal_17g"] == format(float(exact_value), ".17g"), f"decimal mismatch: {label}")
    return exact_value


def order_statistic(values: list[Fraction], numerator: int, denominator: int) -> Fraction:
    check(bool(values), "empty order statistic")
    ordered = sorted(values)
    rank = max(1, (numerator * len(ordered) + denominator - 1) // denominator)
    return ordered[rank - 1]


def distribution(values: list[Fraction]) -> dict[str, Any] | None:
    if not values:
        return None
    return {
        "minimum": fraction_payload(min(values)),
        "median": fraction_payload(order_statistic(values, 1, 2)),
        "p90_nearest_rank": fraction_payload(order_statistic(values, 9, 10)),
        "maximum": fraction_payload(max(values)),
    }


def similarity(left: frozenset[int], right: frozenset[int]) -> Fraction:
    overlap = len(left & right)
    total = len(left | right)
    check(total > 0, "empty independent fingerprint union")
    return Fraction(overlap, total)


def load_protocol(path: Path, expected: str, repo_root: Path) -> tuple[dict[str, Any], str]:
    actual = digest_file(path)
    check(actual == expected, "protocol digest")
    value = json.loads(path.read_text(encoding="utf-8"))
    check(isinstance(value, dict), "protocol object")
    check(value.get("protocol") == PROTOCOL and value.get("status") == STATUS, "protocol identity")
    freeze = value.get("freeze_state", {})
    check(
        freeze.get("target522_candidate_seen") is False
        and freeze.get("margin_distribution_seen") is False
        and freeze.get("margin_correctness_profile_seen") is False
        and freeze.get("selected_margin_threshold_seen") is False
        and freeze.get("chronological_test_profile_seen") is False,
        "freeze declaration",
    )
    disclosed = value.get("disclosed_before_freeze", {})
    check(
        disclosed.get("exact_depth_unique_top_recovery") == "9196/9739"
        and disclosed.get("exact_depth_wrong_alternative_micro_false_acceptance") == "543/99039"
        and disclosed.get("child_level_adversarial_vulnerability") == "543/9739"
        and disclosed.get("margin_conditioned_or_chronological_split_values_seen") is False,
        "disclosure boundary",
    )
    root = repo_root.resolve()
    bindings = value["immutable_inputs"]
    for role in (
        "producer_snapshot_loader",
        "independent_snapshot_loader",
        "producer_fingerprint",
        "independent_fingerprint",
    ):
        relative = bindings[role]
        dependency = (root / relative).resolve()
        check(dependency.is_relative_to(root), f"dependency path: {role}")
        check(digest_file(dependency) == bindings[f"{role}_sha256"], f"dependency digest: {role}")
    return value, actual


def fingerprints(
    snapshot: snapshot_check.SnapshotView,
) -> tuple[dict[str, frozenset[int]], dict[str, list[str]]]:
    values: dict[str, frozenset[int]] = {}
    by_run: dict[str, list[str]] = collections.defaultdict(list)
    for identifier in sorted(snapshot.graph_cards):
        fingerprint = fingerprint_check.identifier_erased_shingles(
            snapshot.card_objects[identifier]["code"]
        )
        if fingerprint is None:
            continue
        values[identifier] = fingerprint
        by_run[snapshot.graph_cards[identifier]["run"]].append(identifier)
    for members in by_run.values():
        members.sort()
    return values, dict(by_run)


def observations(
    snapshot: snapshot_check.SnapshotView,
    values: dict[str, frozenset[int]],
    by_run: dict[str, list[str]],
) -> tuple[list[Observation], dict[str, int]]:
    output: list[Observation] = []
    present = eligible = consistent = 0
    for child in sorted(snapshot.graph_cards):
        child_value = snapshot.graph_cards[child]
        parent = child_value["parent"]
        if parent not in snapshot.graph_cards:
            continue
        present += 1
        if child not in values or parent not in values:
            continue
        eligible += 1
        if snapshot.graph_cards[parent]["depth"] != child_value["depth"] - 1:
            continue
        consistent += 1
        choices = [
            item
            for item in by_run[child_value["run"]]
            if snapshot.graph_cards[item]["depth"] == child_value["depth"] - 1
        ]
        check(parent in choices, "independent candidate exclusion")
        if len(choices) == 1:
            continue
        scored = [(similarity(values[child], values[item]), item) for item in choices]
        best = max(score for score, _item in scored)
        winners = sorted(item for score, item in scored if score == best)
        runner_up = max(
            (score for score, _item in scored if score < best),
            default=best,
        )
        unique = len(winners) == 1
        output.append(
            Observation(
                task=child_value["task"],
                run=child_value["run"],
                candidate_count=len(choices),
                unique=unique,
                right=unique and winners[0] == parent,
                best=best,
                gap=best - runner_up if unique else Fraction(0, 1),
            )
        )
    return output, {
        "parent_present_edges": present,
        "fingerprint_eligible_parent_edges": eligible,
        "depth_consistent_fingerprint_eligible_parent_edges": consistent,
        "ambiguous_exact_depth_edges": len(output),
    }


def threshold_choice(rows: list[Observation], protocol: dict[str, Any]) -> dict[str, Any]:
    rule = protocol["confidence_rule"]
    required_precision = Fraction(rule["train_precision_target"])
    required_count = rule["minimum_train_accepted_edges"]
    levels = sorted({row.gap for row in rows if row.unique and row.gap > 0})
    valid: list[tuple[int, Fraction, int]] = []
    for level in levels:
        accepted = [row for row in rows if row.unique and row.gap >= level]
        correct = sum(row.right for row in accepted)
        if len(accepted) >= required_count and quotient(correct, len(accepted)) >= required_precision:
            valid.append((len(accepted), level, correct))
    if not valid:
        return {
            "selected": False,
            "threshold": None,
            "candidate_thresholds": len(levels),
            "qualifying_thresholds": 0,
            "accepted_edges": 0,
            "correct_edges": 0,
            "precision": fraction_payload(Fraction(0, 1)),
        }
    count, level, correct = max(valid, key=lambda row: (row[0], -row[1]))
    return {
        "selected": True,
        "threshold": fraction_payload(level),
        "candidate_thresholds": len(levels),
        "qualifying_thresholds": len(valid),
        "accepted_edges": count,
        "correct_edges": correct,
        "precision": fraction_payload(quotient(correct, count)),
    }


def profile(rows: list[Observation], threshold: Fraction | None) -> dict[str, Any]:
    all_unique = [row for row in rows if row.unique]
    accepted = [row for row in rows if threshold is not None and row.unique and row.gap >= threshold]
    all_correct = sum(row.right for row in all_unique)
    accepted_correct = sum(row.right for row in accepted)
    sizes = [Fraction(row.candidate_count, 1) for row in rows]
    return {
        "ambiguous_edges": len(rows),
        "unique_top_edges": len(all_unique),
        "unfiltered_correct_edges": all_correct,
        "unfiltered_precision": fraction_payload(quotient(all_correct, len(all_unique))),
        "unfiltered_coverage": fraction_payload(quotient(len(all_unique), len(rows))),
        "selected_edges": len(accepted),
        "selected_correct_edges": accepted_correct,
        "selected_error_edges": len(accepted) - accepted_correct,
        "selected_precision": fraction_payload(quotient(accepted_correct, len(accepted))),
        "selected_coverage": fraction_payload(quotient(len(accepted), len(rows))),
        "candidate_size_quantiles": {
            "median": int(order_statistic(sizes, 1, 2)),
            "p90_nearest_rank": int(order_statistic(sizes, 9, 10)),
            "maximum": int(max(sizes)),
        },
        "unique_top_margin_quantiles": distribution([row.gap for row in rows if row.unique]),
    }


def breadth(
    accepted: list[Observation], field: str, minimum: int, reference: Fraction
) -> dict[str, Any]:
    groups: dict[str, list[Observation]] = collections.defaultdict(list)
    for row in accepted:
        groups[getattr(row, field)].append(row)
    supported = [rows for rows in groups.values() if len(rows) >= minimum]
    rates = [quotient(sum(row.right for row in rows), len(rows)) for rows in supported]
    all_sizes = [len(rows) for rows in groups.values()]
    return {
        "minimum_accepted_edges": minimum,
        "precision_reference": fraction_payload(reference),
        "conditionable_groups": len(supported),
        "fraction_at_or_above_reference": fraction_payload(
            quotient(sum(rate >= reference for rate in rates), len(rates))
        ),
        "maximum_accepted_contribution_share": fraction_payload(
            quotient(max(all_sizes, default=0), sum(all_sizes))
        ),
        "precision_quantiles": distribution(rates),
        "identities_emitted": False,
    }


def independently_recompute(
    protocol: dict[str, Any],
    protocol_sha: str,
    snapshot: snapshot_check.SnapshotView,
    source_commit: str,
) -> dict[str, Any]:
    immutable = protocol["immutable_inputs"]
    check(snapshot.bindings["accumulator_summary_sha256"] == immutable["accumulator_summary_sha256"], "summary binding")
    check(snapshot.bindings["registry_sha256"] == immutable["intake_registry_sha256"], "registry binding")
    check(snapshot.bindings["provisional_runs_sha256"] == immutable["provisional_runs_sha256"], "ledger binding")
    split = protocol["run_disjoint_split"]
    run_order = list(snapshot.run_objects)
    check(len(run_order) == split["train_runs"] + split["test_runs"], "split run count")
    train_ids = set(run_order[: split["train_runs"]])
    test_ids = set(run_order[split["train_runs"] :])
    check(not train_ids & test_ids, "run overlap")
    values, by_run = fingerprints(snapshot)
    rows, inventory = observations(snapshot, values, by_run)
    train = [row for row in rows if row.run in train_ids]
    test = [row for row in rows if row.run in test_ids]
    check(len(train) + len(test) == len(rows), "edge split")
    selection = threshold_choice(train, protocol)
    threshold = decode(selection["threshold"], "selected threshold") if selection["selected"] else None
    train_metrics = profile(train, threshold)
    test_metrics = profile(test, threshold)
    accepted = [row for row in test if threshold is not None and row.unique and row.gap >= threshold]
    gates = protocol["primary_gates"]
    task = breadth(
        accepted,
        "task",
        gates["task_minimum_accepted_edges"],
        Fraction(gates["task_precision_reference"]),
    )
    run = breadth(
        accepted,
        "run",
        gates["run_minimum_accepted_edges"],
        Fraction(gates["run_precision_reference"]),
    )
    wrong = [row for row in accepted if not row.right]
    wrong_total = sum(row.candidate_count - 1 for row in test)
    uniform = sum(Fraction(1, row.candidate_count - 1) for row in wrong)
    controls = {
        "confident_wrong_unique_top_children": len(wrong),
        "all_wrong_alternatives": wrong_total,
        "all_wrong_alternative_micro_false_acceptance": fraction_payload(
            quotient(len(wrong), wrong_total)
        ),
        "uniform_one_wrong_substitution_per_child_expected_false_acceptance": fraction_payload(
            uniform / len(test)
        ),
        "child_level_adversarial_vulnerability": fraction_payload(quotient(len(wrong), len(test))),
        "denominators_are_not_interchangeable": True,
    }
    hard = protocol["hard_support"]
    support = {
        "threshold_selected": bool(selection["selected"]),
        "train_ambiguous_edges": len(train) >= hard["minimum_train_ambiguous_edges"],
        "test_ambiguous_edges": len(test) >= hard["minimum_test_ambiguous_edges"],
        "test_accepted_edges": len(accepted) >= hard["minimum_test_accepted_edges"],
        "conditionable_test_tasks": task["conditionable_groups"] >= hard["minimum_conditionable_test_tasks"],
        "conditionable_test_runs": run["conditionable_groups"] >= hard["minimum_conditionable_test_runs"],
    }
    selected_precision = decode(test_metrics["selected_precision"], "test precision")
    selected_coverage = decode(test_metrics["selected_coverage"], "test coverage")
    unfiltered_error = Fraction(1, 1) - decode(test_metrics["unfiltered_precision"], "unfiltered precision")
    selected_error = Fraction(1, 1) - selected_precision
    primary = {
        "test_precision": selected_precision >= Fraction(gates["minimum_test_precision"]),
        "test_coverage": selected_coverage >= Fraction(gates["minimum_test_coverage"]),
        "selective_error_reduction": selected_error
        <= Fraction(gates["maximum_selective_error_relative_to_unfiltered_unique_top_error"])
        * unfiltered_error,
        "task_breadth": decode(task["fraction_at_or_above_reference"], "task breadth")
        >= Fraction(gates["minimum_task_fraction_at_reference"]),
        "task_anti_dominance": decode(task["maximum_accepted_contribution_share"], "task share")
        <= Fraction(gates["maximum_single_task_accepted_contribution_share"]),
        "run_breadth": decode(run["fraction_at_or_above_reference"], "run breadth")
        >= Fraction(gates["minimum_run_fraction_at_reference"]),
        "run_anti_dominance": decode(run["maximum_accepted_contribution_share"], "run share")
        <= Fraction(gates["maximum_single_run_accepted_contribution_share"]),
    }
    if all(support.values()) and all(primary.values()):
        classification = "DEVELOPMENT_TIME_SPLIT_HIGH_PRECISION_SELECTIVE_PARENT_RECOVERY"
    elif (
        selection["selected"]
        and support["train_ambiguous_edges"]
        and support["test_ambiguous_edges"]
        and support["conditionable_test_tasks"]
        and support["conditionable_test_runs"]
        and primary["test_precision"]
    ):
        classification = "DEVELOPMENT_TIME_SPLIT_PRECISION_ONLY_LOW_COVERAGE"
    else:
        classification = "DEVELOPMENT_TIME_SPLIT_SELECTIVE_RECOVERY_BELOW_GATE"
    train_bytes = b"".join(snapshot.run_lines[run_id] for run_id in run_order[: split["train_runs"]])
    test_bytes = b"".join(snapshot.run_lines[run_id] for run_id in run_order[split["train_runs"] :])
    return {
        "protocol": PROTOCOL,
        "status": RESULT_STATUS,
        "classification": classification,
        "source_commit": source_commit,
        "protocol_sha256": protocol_sha,
        "snapshot_bindings": snapshot.bindings,
        "split_bindings": {
            "train_runs": len(train_ids),
            "test_runs": len(test_ids),
            "run_overlap": 0,
            "train_run_rows_sha256": digest_bytes(train_bytes),
            "test_run_rows_sha256": digest_bytes(test_bytes),
            "identities_emitted": False,
        },
        "inventory": {
            **inventory,
            "fingerprinted_endpoints": len(values),
            "fingerprint_coverage": fraction_payload(quotient(len(values), len(snapshot.graph_cards))),
            "train_ambiguous_edges": len(train),
            "test_ambiguous_edges": len(test),
        },
        "threshold_selection": selection,
        "train_profile": train_metrics,
        "test_profile": test_metrics,
        "test_breadth": {"task": task, "physical_run": run},
        "test_wrong_pointer_controls": controls,
        "support_gates": support,
        "primary_gates": primary,
        "claim_boundary": protocol["claim_boundary"],
        "security": {
            "task_run_card_parent_code_or_per_edge_values_emitted": False,
            "prospective_label_grade_outcome_prediction_values_read": False,
            "raw_senior_archives_opened": False,
            "gpu_api_model_fit_base_update": [0, 0, 0, 0],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--expect-protocol-sha256", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--expect-result-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    check(SHA_PATTERN.fullmatch(args.snapshot) is not None, "snapshot digest syntax")
    check(SHA_PATTERN.fullmatch(args.expect_protocol_sha256) is not None, "protocol digest syntax")
    check(SHA_PATTERN.fullmatch(args.expect_result_sha256) is not None, "result digest syntax")
    check(COMMIT_PATTERN.fullmatch(args.source_commit) is not None, "commit syntax")
    protocol, protocol_sha = load_protocol(args.protocol, args.expect_protocol_sha256, args.repo_root)
    check(args.snapshot == protocol["freeze_state"]["snapshot_sha256"], "snapshot identity")
    result_sha = digest_file(args.result)
    check(result_sha == args.expect_result_sha256, "result digest")
    result = json.loads(args.result.read_text(encoding="utf-8"))
    check(isinstance(result, dict), "result object")
    snapshot = snapshot_check.collect_snapshot(args.state_root, args.snapshot)
    recomputed = independently_recompute(protocol, protocol_sha, snapshot, args.source_commit)
    check(recomputed == result, "producer result differs from independent recomputation")
    verification = {
        "protocol": "independent-tree-content-selective-parent-recovery-887-verifier-v1",
        "status": VERIFY_STATUS,
        "source_commit": args.source_commit,
        "protocol_sha256": protocol_sha,
        "result_sha256": result_sha,
        "classification": recomputed["classification"],
        "snapshot_and_split_independently_loaded": True,
        "fingerprints_candidates_threshold_and_gates_independently_recomputed": True,
        "producer_imported": False,
        "task_run_card_parent_code_or_per_edge_values_emitted": False,
        "prospective_label_grade_outcome_prediction_values_read": False,
        "raw_senior_archives_opened": False,
        "gpu_api_model_fit_base_update": [0, 0, 0, 0],
    }
    check(not args.output.exists(), "refusing to overwrite verification")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(verification, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
