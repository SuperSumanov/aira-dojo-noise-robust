"""Independent verifier for the prospective Target-522 selective parent audit.

This module intentionally does not import the new producer.  It uses the
independent snapshot and fingerprint implementations and recomputes every
candidate set, margin, aggregate, gate, and classification.
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

from phase1 import verify_tree_content_lineage_forward_target522 as content_check
from phase1 import verify_tree_within_stratum_forward_target522 as snapshot_check


PROTOCOL_NAME = "tree-content-selective-parent-forward-target522-v1"
PROTOCOL_STATUS = "OUTCOME_BLIND_FROZEN_AFTER_887_RESULT_BEFORE_TARGET522_CANDIDATE"
RECEIPT_PROTOCOL = "tree-content-selective-parent-forward-target522-receipt-v1"
RECEIPT_STATUS = "OUTCOME_BLIND_FORWARD_SELECTIVE_PARENT_AUDIT_COMPLETE"
COMMIT_RE = re.compile(r"[0-9a-f]{40}")


class ForwardSelectiveParentVerificationError(RuntimeError):
    """Raised when independent reconstruction disagrees with the receipt."""


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
        raise ForwardSelectiveParentVerificationError(message)


def digest_file(path: Path) -> str:
    check(path.is_file() and not path.is_symlink(), f"unsafe file: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def object_file(path: Path) -> dict[str, Any]:
    check(path.is_file() and not path.is_symlink(), f"unsafe object: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    check(isinstance(value, dict), f"object expected: {path}")
    return value


def encode(value: Fraction) -> dict[str, Any]:
    return {
        "numerator": value.numerator,
        "denominator": value.denominator,
        "decimal_17g": format(float(value), ".17g"),
    }


def decode(payload: Any, label: str) -> Fraction:
    check(isinstance(payload, dict), f"missing exact payload: {label}")
    check(
        set(payload) == {"numerator", "denominator", "decimal_17g"},
        f"bad exact schema: {label}",
    )
    numerator, denominator = payload["numerator"], payload["denominator"]
    check(
        isinstance(numerator, int)
        and not isinstance(numerator, bool)
        and isinstance(denominator, int)
        and not isinstance(denominator, bool)
        and denominator > 0,
        f"bad exact fraction: {label}",
    )
    return Fraction(numerator, denominator)


def quotient(numerator: int, denominator: int) -> Fraction:
    return Fraction(numerator, denominator) if denominator else Fraction(0, 1)


def order_statistic(values: list[Fraction], numerator: int, denominator: int) -> Fraction:
    check(bool(values), "empty order statistic")
    ordered = sorted(values)
    rank = max(1, (numerator * len(ordered) + denominator - 1) // denominator)
    return ordered[rank - 1]


def distribution(values: list[Fraction]) -> dict[str, Any] | None:
    if not values:
        return None
    return {
        "minimum": encode(min(values)),
        "median": encode(order_statistic(values, 1, 2)),
        "p90_nearest_rank": encode(order_statistic(values, 9, 10)),
        "maximum": encode(max(values)),
    }


def load_protocol(
    path: Path, expected_sha256: str, repo_root: Path
) -> tuple[dict[str, Any], str, dict[str, str]]:
    actual = digest_file(path)
    check(actual == expected_sha256, "protocol digest mismatch")
    protocol = object_file(path)
    check(protocol.get("protocol") == PROTOCOL_NAME, "protocol name mismatch")
    check(protocol.get("status") == PROTOCOL_STATUS, "protocol status mismatch")
    freeze = protocol.get("freeze_state", {})
    check(freeze.get("target522_candidate_seen") is False, "candidate seen before freeze")
    check(freeze.get("target522_increment_profile_seen") is False, "profile seen before freeze")
    fixed = protocol.get("fixed_development_rule", {})
    check(fixed.get("threshold") == "1006/16929", "fixed threshold mismatch")
    check(fixed.get("threshold_reselection_on_future_allowed") is False, "threshold reselection")

    root = repo_root.resolve()
    dependencies: dict[str, str] = {}
    for role, binding in protocol["immutable_inputs"].items():
        check(isinstance(binding, dict), f"bad dependency binding: {role}")
        dependency = (root / binding["path"]).resolve()
        check(dependency.is_relative_to(root), f"dependency escapes repository: {role}")
        observed = digest_file(dependency)
        check(observed == binding["sha256"], f"dependency digest mismatch: {role}")
        dependencies[role] = observed
    development = object_file(
        root / protocol["immutable_inputs"]["development_summary"]["path"]
    )
    check(
        development.get("classification")
        == "DEVELOPMENT_TIME_SPLIT_HIGH_PRECISION_SELECTIVE_PARENT_RECOVERY",
        "development classification mismatch",
    )
    check(
        development.get("threshold_selection", {}).get("threshold")
        == encode(Fraction(1006, 16929)),
        "development threshold payload mismatch",
    )
    check(all(development.get("support_gates", {}).values()), "development support gate")
    check(all(development.get("primary_gates", {}).values()), "development primary gate")
    check(
        development.get("source_commit") == fixed["development_source_commit"],
        "development source commit mismatch",
    )
    development_verification = object_file(
        root / protocol["immutable_inputs"]["development_verification"]["path"]
    )
    check(
        development_verification.get("status")
        == "INDEPENDENT_SELECTIVE_PARENT_RECOVERY_VERIFIED"
        and development_verification.get("classification")
        == development.get("classification")
        and development_verification.get("source_commit")
        == fixed["development_source_commit"],
        "development verification mismatch",
    )
    return protocol, actual, dependencies


def observations(
    cards: dict[str, dict[str, Any]], objects: dict[str, dict[str, Any]]
) -> tuple[dict[str, frozenset[int]], list[Observation], dict[str, int]]:
    fingerprints, by_run = content_check.independently_fingerprint(cards, objects)
    parent_present = fingerprint_eligible = depth_consistent = 0
    rows: list[Observation] = []
    for child in sorted(cards):
        child_value = cards[child]
        parent = child_value["parent"]
        if parent not in cards:
            continue
        parent_present += 1
        if child not in fingerprints or parent not in fingerprints:
            continue
        fingerprint_eligible += 1
        if cards[parent]["depth"] != child_value["depth"] - 1:
            continue
        depth_consistent += 1
        choices = [
            candidate
            for candidate in by_run.get(child_value["run"], [])
            if cards[candidate]["depth"] == child_value["depth"] - 1
        ]
        check(parent in choices, "independent recorded parent candidate exclusion")
        if len(choices) < 2:
            continue
        scores = {
            candidate: content_check.set_jaccard(
                fingerprints[child], fingerprints[candidate]
            )
            for candidate in choices
        }
        values = sorted(scores.values(), reverse=True)
        best, second = values[0], values[1]
        winners = [candidate for candidate, value in scores.items() if value == best]
        unique = len(winners) == 1
        rows.append(
            Observation(
                task=child_value["task"],
                run=child_value["run"],
                candidate_count=len(choices),
                unique=unique,
                right=unique and winners[0] == parent,
                best=best,
                gap=best - second,
            )
        )
    return fingerprints, rows, {
        "parent_present_edges": parent_present,
        "fingerprint_eligible_parent_edges": fingerprint_eligible,
        "depth_consistent_fingerprint_eligible_parent_edges": depth_consistent,
        "depth_inconsistent_fingerprint_eligible_parent_edges": (
            fingerprint_eligible - depth_consistent
        ),
    }


def profile(rows: list[Observation], threshold: Fraction) -> dict[str, Any]:
    check(bool(rows), "independent empty ambiguous population")
    unfiltered = [row for row in rows if row.unique]
    selected = [row for row in rows if row.unique and row.gap >= threshold]
    unfiltered_correct = sum(row.right for row in unfiltered)
    selected_correct = sum(row.right for row in selected)
    candidate_sizes = [Fraction(row.candidate_count, 1) for row in rows]
    return {
        "ambiguous_edges": len(rows),
        "unique_top_edges": len(unfiltered),
        "unfiltered_correct_edges": unfiltered_correct,
        "unfiltered_error_edges": len(unfiltered) - unfiltered_correct,
        "unfiltered_precision": encode(quotient(unfiltered_correct, len(unfiltered))),
        "unfiltered_coverage": encode(quotient(len(unfiltered), len(rows))),
        "selected_edges": len(selected),
        "selected_correct_edges": selected_correct,
        "selected_error_edges": len(selected) - selected_correct,
        "selected_precision": encode(quotient(selected_correct, len(selected))),
        "selected_coverage": encode(quotient(len(selected), len(rows))),
        "candidate_size_quantiles": {
            "median": int(order_statistic(candidate_sizes, 1, 2)),
            "p90_nearest_rank": int(order_statistic(candidate_sizes, 9, 10)),
            "maximum": max(row.candidate_count for row in rows),
        },
        "unique_top_margin_quantiles": distribution(
            [row.gap for row in rows if row.unique]
        ),
    }


def breadth(
    selected: list[Observation], field: str, minimum: int, reference: Fraction
) -> dict[str, Any]:
    grouped: dict[str, list[Observation]] = collections.defaultdict(list)
    for row in selected:
        grouped[getattr(row, field)].append(row)
    supported = [values for values in grouped.values() if len(values) >= minimum]
    rates = [quotient(sum(row.right for row in values), len(values)) for values in supported]
    sizes = [len(values) for values in grouped.values()]
    return {
        "minimum_accepted_edges": minimum,
        "precision_reference": encode(reference),
        "conditionable_groups": len(supported),
        "fraction_at_or_above_reference": encode(
            quotient(sum(value >= reference for value in rates), len(rates))
        ),
        "maximum_accepted_contribution_share": encode(
            quotient(max(sizes, default=0), sum(sizes))
        ),
        "precision_quantiles": distribution(rates),
        "identities_emitted": False,
    }


def controls(rows: list[Observation], threshold: Fraction) -> dict[str, Any]:
    wrong = [
        row for row in rows if row.unique and row.gap >= threshold and not row.right
    ]
    alternatives = sum(row.candidate_count - 1 for row in rows)
    uniform = sum(
        (Fraction(1, row.candidate_count - 1) for row in wrong),
        start=Fraction(0, 1),
    )
    return {
        "all_wrong_alternatives": alternatives,
        "confident_wrong_unique_top_children": len(wrong),
        "all_wrong_alternative_micro_false_acceptance": encode(
            quotient(len(wrong), alternatives)
        ),
        "uniform_one_wrong_substitution_per_child_expected_false_acceptance": encode(
            uniform / len(rows)
        ),
        "child_level_adversarial_vulnerability": encode(
            quotient(len(wrong), len(rows))
        ),
        "denominators_are_not_interchangeable": True,
    }


def independent_classification(
    result_profile: dict[str, Any],
    task: dict[str, Any],
    run: dict[str, Any],
    hard: dict[str, bool],
    protocol: dict[str, Any],
) -> tuple[str, dict[str, bool]]:
    gates = protocol["primary_gates"]
    precision = decode(result_profile["selected_precision"], "precision")
    coverage = decode(result_profile["selected_coverage"], "coverage")
    unfiltered_error = Fraction(1, 1) - decode(
        result_profile["unfiltered_precision"], "unfiltered precision"
    )
    selected_error = Fraction(1, 1) - precision
    primary = {
        "forward_precision": precision >= Fraction(gates["minimum_forward_precision"]),
        "forward_coverage": coverage >= Fraction(gates["minimum_forward_coverage"]),
        "selective_error_reduction": selected_error
        <= Fraction(gates["maximum_selective_error_relative_to_unfiltered_error"])
        * unfiltered_error,
        "task_breadth": decode(task["fraction_at_or_above_reference"], "task breadth")
        >= Fraction(gates["minimum_task_fraction_at_reference"]),
        "task_anti_dominance": decode(
            task["maximum_accepted_contribution_share"], "task contribution"
        )
        <= Fraction(gates["maximum_single_task_accepted_contribution_share"]),
        "run_breadth": decode(run["fraction_at_or_above_reference"], "run breadth")
        >= Fraction(gates["minimum_run_fraction_at_reference"]),
        "run_anti_dominance": decode(
            run["maximum_accepted_contribution_share"], "run contribution"
        )
        <= Fraction(gates["maximum_single_run_accepted_contribution_share"]),
    }
    if all(hard.values()) and all(primary.values()):
        classification = "FORWARD_TIME_GENERALIZED_HIGH_PRECISION_SELECTIVE_PARENT_RECOVERY"
    elif (
        all(value for key, value in hard.items() if key != "selected_edges_at_least_minimum")
        and primary["forward_precision"]
    ):
        classification = "FORWARD_TIME_GENERALIZED_HIGH_PRECISION_WITHOUT_FULL_PRIMARY_GATE"
    elif all(value for key, value in hard.items() if key != "selected_edges_at_least_minimum"):
        classification = "FORWARD_SELECTIVE_PARENT_RECOVERY_BELOW_GATE"
    else:
        classification = "FORWARD_SELECTIVE_PARENT_RECOVERY_GATE_FAIL"
    check(classification in protocol["ordered_classification"], "classification outside protocol")
    return classification, primary


def independently_compute(
    cards: dict[str, dict[str, Any]],
    objects: dict[str, dict[str, Any]],
    protocol: dict[str, Any],
) -> tuple[dict[str, Any], list[Observation]]:
    fingerprints, rows, edge_inventory = observations(cards, objects)
    threshold = Fraction(protocol["fixed_development_rule"]["threshold"])
    result_profile = profile(rows, threshold)
    selected = [row for row in rows if row.unique and row.gap >= threshold]
    gates = protocol["primary_gates"]
    task = breadth(
        selected,
        "task",
        gates["task_minimum_accepted_edges"],
        Fraction(gates["task_precision_reference"]),
    )
    run = breadth(
        selected,
        "run",
        gates["run_minimum_accepted_edges"],
        Fraction(gates["run_precision_reference"]),
    )
    inventory = {
        "increment_endpoints": len(cards),
        "increment_physical_runs": len({value["run"] for value in cards.values()}),
        "increment_tasks": len({value["task"] for value in cards.values()}),
        "fingerprinted_endpoints": len(fingerprints),
        "fingerprint_coverage": encode(quotient(len(fingerprints), len(cards))),
        "ambiguous_exact_depth_edges": len(rows),
        **edge_inventory,
    }
    return {
        "inventory": inventory,
        "fixed_development_rule": {
            **protocol["fixed_development_rule"],
            "threshold_exact": encode(threshold),
        },
        "forward_profile": result_profile,
        "forward_breadth": {"task": task, "physical_run": run},
        "forward_wrong_pointer_controls": controls(rows, threshold),
    }, rows


def verify(
    state_root: Path,
    selection_root: Path,
    repo_root: Path,
    protocol_path: Path,
    protocol_sha256: str,
    receipt_path: Path,
    receipt_sha256: str,
    producer_source: Path,
    producer_source_sha256: str,
    source_commit: str,
) -> dict[str, Any]:
    check(COMMIT_RE.fullmatch(source_commit) is not None, "source commit")
    check(digest_file(receipt_path) == receipt_sha256, "receipt digest")
    check(digest_file(producer_source) == producer_source_sha256, "producer source digest")
    producer_text = producer_source.read_text(encoding="utf-8")
    check("verify_tree_content_selective_parent_forward_target522" not in producer_text, "producer imports verifier")
    verifier_text = Path(__file__).read_text(encoding="utf-8")
    producer_module = "audit_tree_content_" + "selective_parent_forward_target522"
    check(f"import {producer_module}" not in verifier_text, "verifier imports producer")
    check(f"from phase1 import {producer_module}" not in verifier_text, "verifier imports producer")

    protocol, actual_protocol_sha, dependencies = load_protocol(
        protocol_path, protocol_sha256, repo_root
    )
    activation = protocol["activation_rule"]
    selection_protocol_path = repo_root.resolve() / activation["selection_protocol"]
    selection_monitor_path = repo_root.resolve() / activation["selection_monitor"]
    selection_protocol, selection_protocol_sha = snapshot_check.protocol_file(
        selection_protocol_path, activation["selection_protocol_sha256"]
    )
    selection = snapshot_check.inspect_selection(
        selection_root,
        selection_protocol_path,
        selection_monitor_path,
        selection_protocol,
        selection_protocol_sha,
    )
    check(
        selection["monitor_source_sha256"] == activation["selection_monitor_sha256"],
        "selection monitor digest mismatch",
    )
    baseline = snapshot_check.collect_snapshot(state_root, selection["baseline"])
    candidate = snapshot_check.collect_snapshot(state_root, selection["candidate"])
    for snapshot, observed in (
        (baseline, selection["baseline_journal"]),
        (candidate, selection["candidate_journal"]),
    ):
        check(
            snapshot.bindings["accumulator_summary_sha256"] == observed["summary_sha256"]
            and snapshot.bindings["registry_sha256"] == observed["registry_sha256"]
            and snapshot.bindings["provisional_runs_sha256"] == observed["runs_sha256"],
            "independent observation binding",
        )
    check(
        baseline.sha256 == protocol["freeze_state"]["baseline_snapshot_sha256"],
        "baseline freeze mismatch",
    )
    cards, run_objects, append_only = snapshot_check.incremental_population(
        baseline, candidate, selection_protocol
    )
    objects = {identity: candidate.card_objects[identity] for identity in cards}
    metrics, rows = independently_compute(cards, objects, protocol)
    inventory = metrics["inventory"]
    result_profile = metrics["forward_profile"]
    task = metrics["forward_breadth"]["task"]
    run = metrics["forward_breadth"]["physical_run"]
    wrong = metrics["forward_wrong_pointer_controls"]
    threshold = Fraction(protocol["fixed_development_rule"]["threshold"])
    selected = [row for row in rows if row.unique and row.gap >= threshold]
    support = protocol["hard_integrity_and_support_gates"]
    hard = {
        **selection["checks"],
        "baseline_is_exact_byte_unchanged_prefix": all(
            value is True for value in append_only.values() if isinstance(value, bool)
        ),
        "candidate_total_runs_at_least_target": len(candidate.run_objects)
        >= support["candidate_total_runs_at_least"],
        "disjoint_increment_runs_at_least_minimum": len(run_objects)
        >= support["disjoint_increment_runs_at_least"],
        "candidate_accumulator_is_outcome_blind_and_unclosed": True,
        "fixed_threshold_matches_development_certificate": threshold == Fraction(1006, 16929),
        "fingerprint_coverage_at_least_minimum": decode(
            inventory["fingerprint_coverage"], "fingerprint coverage"
        )
        >= Fraction(support["minimum_fingerprint_coverage"]),
        "all_fingerprint_eligible_parent_edges_depth_consistent": inventory[
            "depth_inconsistent_fingerprint_eligible_parent_edges"
        ]
        == 0,
        "ambiguous_edges_at_least_minimum": len(rows)
        >= support["minimum_ambiguous_exact_depth_edges"],
        "selected_edges_at_least_minimum": len(selected)
        >= support["minimum_selected_edges"],
        "wrong_alternatives_at_least_minimum": wrong["all_wrong_alternatives"]
        >= support["minimum_wrong_parent_alternatives"],
        "conditionable_tasks_at_least_minimum": task["conditionable_groups"]
        >= support["minimum_conditionable_tasks"],
        "conditionable_runs_at_least_minimum": run["conditionable_groups"]
        >= support["minimum_conditionable_physical_runs"],
        "all_gate_comparisons_use_exact_fractions": True,
    }
    classification, primary = independent_classification(
        result_profile, task, run, hard, protocol
    )
    receipt = object_file(receipt_path)
    check(receipt.get("protocol") == RECEIPT_PROTOCOL, "receipt protocol")
    check(receipt.get("status") == RECEIPT_STATUS, "receipt status")
    check(receipt.get("classification") == classification, "classification mismatch")
    check(receipt.get("protocol_sha256") == actual_protocol_sha, "protocol binding")
    check(receipt.get("analysis_source_commit") == source_commit, "source commit binding")
    check(receipt.get("producer_source_sha256") == producer_source_sha256, "producer binding")
    check(receipt.get("dependency_source_sha256s") == dependencies, "dependency bindings")
    check(receipt.get("snapshot_bindings", {}).get("baseline") == baseline.bindings, "baseline binding")
    check(receipt.get("snapshot_bindings", {}).get("candidate") == candidate.bindings, "candidate binding")
    check(
        receipt.get("snapshot_bindings", {}).get("selection_support")
        == {
            "sha256sums_sha256": selection["manifest_sha256"],
            "monitor_source_sha256": selection["monitor_source_sha256"],
            "selection_protocol_sha256": selection_protocol_sha,
        },
        "selection support binding",
    )
    check(receipt.get("append_only_and_increment") == append_only, "append-only mismatch")
    for key, value in metrics.items():
        check(receipt.get(key) == value, f"aggregate mismatch: {key}")
    gate = receipt.get("pre_registered_gate", {})
    check(gate.get("hard_integrity_and_support") == hard, "hard gates mismatch")
    check(gate.get("primary") == primary, "primary gates mismatch")
    check(gate.get("all_hard_gates_passed") is all(hard.values()), "hard gate summary")
    check(gate.get("all_primary_gates_passed") is all(primary.values()), "primary gate summary")
    security = receipt.get("security", {})
    check(security.get("raw_senior_archives_opened") is False, "raw archive security")
    check(
        security.get("prospective_label_grade_outcome_prediction_values_read") is False,
        "prospective value security",
    )
    check(
        security.get("task_run_card_parent_code_or_per_edge_values_emitted") is False,
        "identity security",
    )
    check(security.get("gpu_api_model_fit_base_update") == [0, 0, 0, 0], "resource security")
    return {
        "protocol": "independent-tree-content-selective-parent-forward-target522-verifier-v1",
        "status": "INDEPENDENT_FORWARD_SELECTIVE_PARENT_AUDIT_PASS",
        "classification": classification,
        "protocol_sha256": actual_protocol_sha,
        "receipt_sha256": receipt_sha256,
        "analysis_source_commit": source_commit,
        "producer_source_sha256": producer_source_sha256,
        "producer_imported": False,
        "selection_snapshot_fingerprint_candidates_margin_and_gates_independently_recomputed": True,
        "task_run_card_parent_code_or_per_edge_values_emitted": False,
        "prospective_label_grade_outcome_prediction_values_read": False,
        "raw_senior_archives_opened": False,
        "gpu_api_model_fit_base_update": [0, 0, 0, 0],
    }


def write_once(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, sort_keys=True, indent=2, ensure_ascii=False)
        stream.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--selection-root", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--expect-protocol-sha256", required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--expect-receipt-sha256", required=True)
    parser.add_argument("--producer-source", type=Path, required=True)
    parser.add_argument("--expect-producer-source-sha256", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = verify(
            args.state_root.resolve(),
            args.selection_root.resolve(),
            args.repo_root.resolve(),
            args.protocol.resolve(),
            args.expect_protocol_sha256,
            args.receipt.resolve(),
            args.expect_receipt_sha256,
            args.producer_source.resolve(),
            args.expect_producer_source_sha256,
            args.source_commit,
        )
        write_once(args.out.resolve(), result)
    except (
        ForwardSelectiveParentVerificationError,
        snapshot_check.ForwardVerificationError,
        content_check.ContentLineageVerificationError,
    ) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
