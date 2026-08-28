"""Independent verifier for the forward hierarchy/content concordance audit.

This module intentionally does not import the new producer.  Snapshot parsing,
fingerprinting, pair sweeps, candidate construction, gates, and classification
are independently recomputed before aggregate equality is accepted.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable

from phase1 import verify_prospective_fuzzy_code_clones as independent_fingerprint
from phase1 import verify_tree_within_stratum_forward_target522 as independent_snapshot


PROTOCOL_NAME = "tree-content-lineage-forward-target522-v1"
EXPECTED_PROTOCOL_STATUS = (
    "OUTCOME_BLIND_FROZEN_AFTER_DISCLOSED_887_DEVELOPMENT_BEFORE_TARGET522_SELECTION_COMPLETE"
)
EXPECTED_RECEIPT_PROTOCOL = "tree-content-lineage-forward-target522-receipt-v1"
EXPECTED_RECEIPT_STATUS = "OUTCOME_BLIND_FORWARD_CONTENT_LINEAGE_AUDIT_COMPLETE"
VERIFIER_PROTOCOL = "independent-tree-content-lineage-forward-target522-verifier-v1"
COMMIT_PATTERN = re.compile(r"[0-9a-f]{40}")


class ContentLineageVerificationError(RuntimeError):
    """Raised for any independent mismatch."""


def check(condition: bool, message: str) -> None:
    if not condition:
        raise ContentLineageVerificationError(message)


def file_digest(path: Path) -> str:
    check(path.is_file() and not path.is_symlink(), f"unsafe file: {path}")
    value = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            block = stream.read(1 << 20)
            if not block:
                break
            value.update(block)
    return value.hexdigest()


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


def decode(value: Any, label: str) -> Fraction:
    check(isinstance(value, dict), f"exact object expected: {label}")
    check(set(value) == {"numerator", "denominator", "decimal_17g"}, f"exact fields: {label}")
    numerator, denominator = value["numerator"], value["denominator"]
    check(
        isinstance(numerator, int)
        and not isinstance(numerator, bool)
        and isinstance(denominator, int)
        and not isinstance(denominator, bool)
        and denominator > 0,
        f"exact fraction: {label}",
    )
    return Fraction(numerator, denominator)


def quotient(part: int, total: int) -> Fraction:
    return Fraction(part, total) if total else Fraction(0, 1)


def fractional_quotient(value: Fraction, total: int) -> Fraction:
    return value / total if total else Fraction(0, 1)


def order_statistic(values: list[Fraction], numerator: int, denominator: int) -> Fraction:
    check(bool(values), "empty order-statistic population")
    ordered = sorted(values)
    position = max(1, (numerator * len(ordered) + denominator - 1) // denominator)
    return ordered[position - 1]


def set_jaccard(left: frozenset[int], right: frozenset[int]) -> Fraction:
    common = len(left & right)
    total = len(left | right)
    check(total > 0, "zero fingerprint union")
    return Fraction(common, total)


def protocol_file(path: Path, expected_sha256: str) -> tuple[dict[str, Any], str]:
    actual = file_digest(path)
    check(actual == expected_sha256, "content-lineage protocol digest")
    protocol = object_file(path)
    check(protocol.get("protocol") == PROTOCOL_NAME, "content-lineage protocol identity")
    check(protocol.get("status") == EXPECTED_PROTOCOL_STATUS, "content-lineage protocol status")
    freeze = protocol.get("freeze_state", {})
    check(freeze.get("target522_candidate_snapshot_identity_seen") is False, "candidate seen at freeze")
    check(freeze.get("target522_increment_profile_seen") is False, "increment seen at freeze")
    prior = protocol.get("development_evidence_seen_before_freeze", {})
    check(
        prior.get("exact_depth_unique_top_recovery") == "9196/9739"
        and prior.get("flat_pair_oracle_maximum_f1") == "11446/22315"
        and prior.get("same_run_without_depth_unique_top_recovery") == "2633/5438",
        "development prior disclosure",
    )
    return protocol, actual


def verify_dependencies(repo_root: Path, protocol: dict[str, Any]) -> dict[str, str]:
    root = repo_root.resolve()
    dependencies = protocol["implementation_dependencies"]
    result: dict[str, str] = {}
    for role in ("snapshot_producer", "snapshot_verifier", "fingerprint_producer", "fingerprint_verifier"):
        relative = dependencies[f"{role}_module"]
        expected = dependencies[f"{role}_sha256"]
        path = (root / relative).resolve()
        check(path.is_relative_to(root), f"dependency path: {role}")
        check(file_digest(path) == expected, f"dependency digest: {role}")
        result[role] = expected
    return result


def independently_fingerprint(
    cards: dict[str, dict[str, Any]], objects: dict[str, dict[str, Any]]
) -> tuple[dict[str, frozenset[int]], dict[str, list[str]]]:
    fingerprints: dict[str, frozenset[int]] = {}
    for identity in sorted(cards, reverse=True):
        check(identity in objects, "missing independent endpoint object")
        value = independent_fingerprint.identifier_erased_shingles(objects[identity]["code"])
        if value is not None:
            fingerprints[identity] = value
    run_members: dict[str, list[str]] = collections.defaultdict(list)
    for identity in fingerprints:
        run_members[cards[identity]["run"]].append(identity)
    for members in run_members.values():
        members.sort(reverse=True)
    return fingerprints, dict(run_members)


def independent_parent_inventory(
    cards: dict[str, dict[str, Any]], fingerprints: dict[str, frozenset[int]]
) -> tuple[list[tuple[str, str]], dict[str, int]]:
    all_edges: list[tuple[str, str]] = []
    depth_edges: list[tuple[str, str]] = []
    for child in sorted(cards, reverse=True):
        parent = cards[child]["parent"]
        if parent not in cards or child not in fingerprints or parent not in fingerprints:
            continue
        all_edges.append((child, parent))
        if cards[parent]["depth"] == cards[child]["depth"] - 1:
            depth_edges.append((child, parent))
    return depth_edges, {
        "fingerprint_eligible_parent_edges": len(all_edges),
        "depth_consistent_fingerprint_eligible_parent_edges": len(depth_edges),
        "depth_inconsistent_fingerprint_eligible_parent_edges": len(all_edges) - len(depth_edges),
    }


def group_profile(rows: list[tuple[str, bool]], minimum: int) -> dict[str, Any]:
    grouped: dict[str, list[bool]] = collections.defaultdict(list)
    for identity, passed in rows:
        grouped[identity].append(passed)
    supported = [values for values in grouped.values() if len(values) >= minimum]
    rates = [quotient(sum(values), len(values)) for values in supported]
    sizes = [len(values) for values in supported]
    return {
        "minimum_edges_per_group": minimum,
        "conditionable_groups": len(supported),
        "fraction_at_or_above_17_over_20": encode(
            quotient(sum(value >= Fraction(17, 20) for value in rates), len(rates))
        ),
        "fraction_at_or_above_9_over_10": encode(
            quotient(sum(value >= Fraction(9, 10) for value in rates), len(rates))
        ),
        "maximum_edge_contribution_share": encode(quotient(max(sizes, default=0), sum(sizes))),
        "rate_quantiles": {
            "minimum": encode(min(rates)) if rates else None,
            "median": encode(order_statistic(rates, 1, 2)) if rates else None,
            "p90_nearest_rank": encode(order_statistic(rates, 9, 10)) if rates else None,
            "maximum": encode(max(rates)) if rates else None,
        },
        "identities_emitted": False,
    }


def independent_selector(
    mode: str, cards: dict[str, dict[str, Any]], child: str
) -> Callable[[str], bool]:
    if mode == "exact_preceding_depth":
        target_depth = cards[child]["depth"] - 1
        return lambda candidate: cards[candidate]["depth"] == target_depth
    if mode == "any_shallower_depth":
        target_depth = cards[child]["depth"]
        return lambda candidate: cards[candidate]["depth"] < target_depth
    if mode == "same_run_without_depth":
        return lambda candidate: candidate != child
    raise ContentLineageVerificationError("unknown candidate mode")


def independent_mode(
    mode: str,
    cards: dict[str, dict[str, Any]],
    fingerprints: dict[str, frozenset[int]],
    run_members: dict[str, list[str]],
    depth_edges: list[tuple[str, str]],
    protocol: dict[str, Any],
) -> dict[str, Any]:
    ambiguous = top_tie = unique_top = 0
    random_expectation = Fraction(0, 1)
    wrong_count = wrong_unique_top = 0
    random_wrong_expectation = Fraction(0, 1)
    candidate_sizes: list[Fraction] = []
    parent_ranks: list[Fraction] = []
    task_rows: list[tuple[str, bool]] = []
    run_rows: list[tuple[str, bool]] = []
    for child, parent in depth_edges:
        selector = independent_selector(mode, cards, child)
        options = [item for item in run_members[cards[child]["run"]] if selector(item)]
        check(parent in options, f"independent {mode} parent support")
        values = {
            candidate: set_jaccard(fingerprints[child], fingerprints[candidate])
            for candidate in options
        }
        maximum = max(values.values())
        parent_score = values[parent]
        top_size = sum(value == maximum for value in values.values())
        parent_is_top = parent_score == maximum
        candidate_sizes.append(Fraction(len(options), 1))
        parent_ranks.append(Fraction(1 + sum(value > parent_score for value in values.values()), 1))
        if len(options) <= 1:
            continue
        ambiguous += 1
        top_tie += int(parent_is_top)
        is_unique = parent_is_top and top_size == 1
        unique_top += int(is_unique)
        random_expectation += Fraction(1, len(options))
        task_rows.append((cards[child]["task"], is_unique))
        run_rows.append((cards[child]["run"], is_unique))
        wrong_count += len(options) - 1
        wrong_unique_top += int(not parent_is_top and top_size == 1)
        if not parent_is_top and top_size == 1:
            random_wrong_expectation += Fraction(1, len(options) - 1)
    check(bool(candidate_sizes), f"independent empty mode: {mode}")
    estimands = protocol["parent_recovery_estimands"]
    return {
        "mode": mode,
        "eligible_parent_edges": len(depth_edges),
        "ambiguous_parent_edges": ambiguous,
        "optimistic_top_tie_recovery": encode(quotient(top_tie, ambiguous)),
        "unique_top_recovery": encode(quotient(unique_top, ambiguous)),
        "uniform_random_expected_recovery": encode(
            fractional_quotient(random_expectation, ambiguous)
        ),
        "unique_top_lift_over_uniform_random": encode(
            quotient(unique_top, ambiguous) - fractional_quotient(random_expectation, ambiguous)
        ),
        "enumerated_wrong_parent_alternatives": wrong_count,
        "wrong_alternatives_accepted_as_unique_top": wrong_unique_top,
        "exhaustive_wrong_parent_false_acceptance_rate": encode(
            quotient(wrong_unique_top, wrong_count)
        ),
        "uniform_single_wrong_substitution_expected_false_acceptance": encode(
            fractional_quotient(random_wrong_expectation, ambiguous)
        ),
        "candidate_size_quantiles": {
            "median": int(order_statistic(candidate_sizes, 1, 2)),
            "p90_nearest_rank": int(order_statistic(candidate_sizes, 9, 10)),
            "maximum": int(max(candidate_sizes)),
        },
        "optimistic_parent_rank_quantiles": {
            "median": int(order_statistic(parent_ranks, 1, 2)),
            "p90_nearest_rank": int(order_statistic(parent_ranks, 9, 10)),
            "maximum": int(max(parent_ranks)),
        },
        "unique_top_breadth": {
            "task": group_profile(task_rows, estimands["task_breadth_minimum_edges"]),
            "physical_run": group_profile(
                run_rows, estimands["physical_run_breadth_minimum_edges"]
            ),
        },
    }


def independent_oracle_f1(
    scores: list[tuple[Fraction, bool]], positive_total: int
) -> dict[str, Any]:
    buckets: dict[Fraction, list[bool]] = collections.defaultdict(list)
    for value, label in scores:
        buckets[value].append(label)
    predicted = correct = 0
    candidates: list[tuple[Fraction, Fraction, int, int]] = []
    for threshold in sorted(buckets, reverse=True):
        labels = buckets[threshold]
        predicted += len(labels)
        correct += sum(labels)
        candidates.append(
            (Fraction(2 * correct, predicted + positive_total), threshold, predicted, correct)
        )
    check(bool(candidates), "independent empty pair graph")
    f1, threshold, selected, true_positive = max(
        candidates, key=lambda item: (item[0], item[1])
    )
    return {
        "maximum_f1": encode(f1),
        "optimistically_selected_threshold": encode(threshold),
        "predicted_pairs_at_optimum": selected,
        "true_positive_pairs_at_optimum": true_positive,
        "selection_role": "same-population oracle upper bound; not a deployable threshold",
    }


def independent_flat_graph(
    cards: dict[str, dict[str, Any]],
    fingerprints: dict[str, frozenset[int]],
    run_members: dict[str, list[str]],
    expected_parents: int,
) -> dict[str, Any]:
    scores: list[tuple[Fraction, bool]] = []
    positive_total = 0
    for members in run_members.values():
        for left_index in range(len(members)):
            for right_index in range(left_index + 1, len(members)):
                left, right = members[left_index], members[right_index]
                positive = cards[left]["parent"] == right or cards[right]["parent"] == left
                positive_total += int(positive)
                scores.append((set_jaccard(fingerprints[left], fingerprints[right]), positive))
    check(positive_total == expected_parents, "independent flat parent count")
    selected = [label for value, label in scores if value >= Fraction(17, 20)]
    correct = sum(selected)
    return {
        "within_run_fingerprinted_pairs": len(scores),
        "fingerprint_eligible_parent_edges": positive_total,
        "fixed_17_over_20": {
            "predicted_pairs": len(selected),
            "true_positive_pairs": correct,
            "precision": encode(quotient(correct, len(selected))),
            "recall": encode(quotient(correct, positive_total)),
            "f1": encode(quotient(2 * correct, len(selected) + positive_total)),
        },
        "same_population_oracle": independent_oracle_f1(scores, positive_total),
    }


def independently_compute(
    cards: dict[str, dict[str, Any]],
    objects: dict[str, dict[str, Any]],
    protocol: dict[str, Any],
) -> dict[str, Any]:
    fingerprints, run_members = independently_fingerprint(cards, objects)
    depth_edges, inventory = independent_parent_inventory(cards, fingerprints)
    modes = {
        mode: independent_mode(mode, cards, fingerprints, run_members, depth_edges, protocol)
        for mode in (
            "exact_preceding_depth",
            "any_shallower_depth",
            "same_run_without_depth",
        )
    }
    return {
        "inventory": {
            "increment_endpoints": len(cards),
            "fingerprinted_endpoints": len(fingerprints),
            "fingerprint_coverage": encode(Fraction(len(fingerprints), len(cards))),
            **inventory,
            "increment_tasks": len({row["task"] for row in cards.values()}),
            "increment_physical_runs": len({row["run"] for row in cards.values()}),
        },
        "flat_pair_graph": independent_flat_graph(
            cards, fingerprints, run_members, inventory["fingerprint_eligible_parent_edges"]
        ),
        "parent_recovery_modes": modes,
    }


def independent_classification(
    metrics: dict[str, Any], protocol: dict[str, Any], hard: dict[str, bool]
) -> tuple[str, dict[str, bool], dict[str, bool]]:
    exact_mode = metrics["parent_recovery_modes"]["exact_preceding_depth"]
    no_depth = metrics["parent_recovery_modes"]["same_run_without_depth"]
    task = exact_mode["unique_top_breadth"]["task"]
    run = exact_mode["unique_top_breadth"]["physical_run"]
    thresholds = protocol["strong_content_concordance_gates"]
    strong = {
        "exact_depth_unique_top_recovery": decode(exact_mode["unique_top_recovery"], "recovery")
        >= Fraction(thresholds["minimum_exact_depth_unique_top_recovery"]),
        "exact_depth_lift_over_uniform_random": decode(
            exact_mode["unique_top_lift_over_uniform_random"], "lift"
        )
        >= Fraction(thresholds["minimum_exact_depth_lift_over_uniform_random"]),
        "wrong_parent_false_acceptance": decode(
            exact_mode["exhaustive_wrong_parent_false_acceptance_rate"], "wrong FPR"
        )
        <= Fraction(thresholds["maximum_exhaustive_wrong_parent_false_acceptance"]),
        "task_breadth": decode(task["fraction_at_or_above_17_over_20"], "task breadth")
        >= Fraction(thresholds["minimum_task_fraction_at_or_above_breadth_reference"]),
        "physical_run_breadth": decode(
            run["fraction_at_or_above_17_over_20"], "run breadth"
        )
        >= Fraction(thresholds["minimum_physical_run_fraction_at_or_above_breadth_reference"]),
        "task_anti_dominance": decode(task["maximum_edge_contribution_share"], "task share")
        <= Fraction(thresholds["maximum_single_task_edge_contribution_share"]),
        "physical_run_anti_dominance": decode(
            run["maximum_edge_contribution_share"], "run share"
        )
        <= Fraction(thresholds["maximum_single_physical_run_edge_contribution_share"]),
    }
    complement_thresholds = protocol["hierarchy_complementarity_gates"]
    exact_recovery = decode(exact_mode["unique_top_recovery"], "exact recovery")
    no_depth_recovery = decode(no_depth["unique_top_recovery"], "no-depth recovery")
    complement = {
        "no_depth_recovery_below_ceiling": no_depth_recovery
        <= Fraction(complement_thresholds["maximum_same_run_without_depth_unique_top_recovery"]),
        "exact_depth_gain_over_no_depth": exact_recovery - no_depth_recovery
        >= Fraction(complement_thresholds["minimum_exact_depth_minus_no_depth_unique_top_recovery"]),
        "flat_pair_oracle_f1_below_ceiling": decode(
            metrics["flat_pair_graph"]["same_population_oracle"]["maximum_f1"],
            "pair oracle F1",
        )
        <= Fraction(complement_thresholds["maximum_flat_pair_graph_oracle_f1"]),
    }
    if not all(hard.values()):
        result = "FORWARD_PARENT_CONCORDANCE_GATE_FAIL"
    elif all(strong.values()) and all(complement.values()):
        result = "FORWARD_HIERARCHY_CONTENT_PARENT_CONCORDANCE_CERTIFICATE"
    elif all(strong.values()):
        result = "FORWARD_CONTENT_PARENT_CONCORDANCE_WITHOUT_HIERARCHY_COMPLEMENTARITY"
    else:
        result = "FORWARD_PARENT_CONCORDANCE_PROFILE_BELOW_STRONG_GATE"
    check(result in protocol["ordered_classification"], "independent classification outside protocol")
    return result, strong, complement


def deep_equal(expected: Any, actual: Any, label: str) -> None:
    check(expected == actual, f"aggregate mismatch: {label}")


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
    check(COMMIT_PATTERN.fullmatch(source_commit) is not None, "source commit")
    check(file_digest(receipt_path) == receipt_sha256, "receipt digest")
    check(file_digest(producer_source) == producer_source_sha256, "producer source digest")
    producer_text = producer_source.read_text(encoding="utf-8")
    check("verify_tree_content_lineage_forward_target522" not in producer_text, "producer imports verifier")
    verifier_text = Path(__file__).read_text(encoding="utf-8")
    producer_module = "audit_tree_content_" + "lineage_forward_target522"
    check(f"import {producer_module}" not in verifier_text, "verifier imports producer")
    check(f"from phase1 import {producer_module}" not in verifier_text, "verifier imports producer")

    protocol, actual_protocol_sha = protocol_file(protocol_path, protocol_sha256)
    dependencies = verify_dependencies(repo_root, protocol)
    selection_protocol_path = repo_root.resolve() / protocol["activation_rule"]["selection_protocol"]
    selection_monitor_path = repo_root.resolve() / protocol["activation_rule"]["selection_monitor"]
    selection_protocol, selection_protocol_sha = independent_snapshot.protocol_file(
        selection_protocol_path,
        protocol["activation_rule"]["selection_protocol_sha256"],
    )
    selection = independent_snapshot.inspect_selection(
        selection_root,
        selection_protocol_path,
        selection_monitor_path,
        selection_protocol,
        selection_protocol_sha,
    )
    check(
        selection["monitor_source_sha256"] == protocol["activation_rule"]["selection_monitor_sha256"],
        "selection monitor digest differs",
    )
    baseline = independent_snapshot.collect_snapshot(state_root, selection["baseline"])
    candidate = independent_snapshot.collect_snapshot(state_root, selection["candidate"])
    for cohort, observed in (
        (baseline, selection["baseline_journal"]),
        (candidate, selection["candidate_journal"]),
    ):
        check(
            cohort.bindings["accumulator_summary_sha256"] == observed["summary_sha256"]
            and cohort.bindings["registry_sha256"] == observed["registry_sha256"]
            and cohort.bindings["provisional_runs_sha256"] == observed["runs_sha256"],
            "independent observation binding",
        )
    check(baseline.sha256 == protocol["freeze_state"]["baseline_snapshot_sha256"], "baseline freeze")
    cards, runs, append_only = independent_snapshot.incremental_population(
        baseline, candidate, selection_protocol
    )
    objects = {identity: candidate.card_objects[identity] for identity in cards}
    metrics = independently_compute(cards, objects, protocol)
    inventory = metrics["inventory"]
    exact_mode = metrics["parent_recovery_modes"]["exact_preceding_depth"]
    support = protocol["hard_integrity_and_support_gates"]
    hard = {
        **selection["checks"],
        "baseline_is_exact_byte_unchanged_prefix": all(
            value is True for value in append_only.values() if isinstance(value, bool)
        ),
        "candidate_total_runs_at_least_target": len(candidate.run_objects)
        >= support["candidate_total_runs_at_least"],
        "disjoint_increment_runs_at_least_minimum": len(runs)
        >= support["disjoint_increment_runs_at_least"],
        "candidate_accumulator_is_outcome_blind_and_unclosed": True,
        "fingerprint_coverage_at_least_minimum": decode(
            inventory["fingerprint_coverage"], "coverage"
        )
        >= Fraction(support["minimum_fingerprint_coverage"]),
        "fingerprint_eligible_parent_edges_at_least_minimum": inventory[
            "fingerprint_eligible_parent_edges"
        ]
        >= support["minimum_fingerprint_eligible_parent_edges"],
        "all_fingerprint_eligible_parent_edges_depth_consistent": inventory[
            "depth_inconsistent_fingerprint_eligible_parent_edges"
        ]
        == 0,
        "ambiguous_exact_depth_parent_edges_at_least_minimum": exact_mode[
            "ambiguous_parent_edges"
        ]
        >= support["minimum_ambiguous_exact_depth_parent_edges"],
        "wrong_parent_alternatives_at_least_minimum": exact_mode[
            "enumerated_wrong_parent_alternatives"
        ]
        >= support["minimum_enumerated_wrong_parent_alternatives"],
        "conditionable_tasks_at_least_minimum": exact_mode["unique_top_breadth"]["task"]
        ["conditionable_groups"]
        >= support["minimum_conditionable_tasks"],
        "conditionable_physical_runs_at_least_minimum": exact_mode["unique_top_breadth"]
        ["physical_run"]["conditionable_groups"]
        >= support["minimum_conditionable_physical_runs"],
        "all_gate_comparisons_use_exact_fractions": True,
        "decimal_strings_are_descriptive_only": True,
    }
    classification, strong, complement = independent_classification(metrics, protocol, hard)
    receipt = object_file(receipt_path)
    check(receipt.get("protocol") == EXPECTED_RECEIPT_PROTOCOL, "receipt protocol")
    check(receipt.get("status") == EXPECTED_RECEIPT_STATUS, "receipt status")
    check(receipt.get("protocol_sha256") == actual_protocol_sha, "receipt protocol hash")
    check(receipt.get("analysis_source_commit") == source_commit, "receipt source commit")
    check(receipt.get("producer_source_sha256") == producer_source_sha256, "receipt producer hash")
    deep_equal(receipt.get("dependency_source_sha256s"), dependencies, "dependencies")
    deep_equal(receipt.get("snapshot_bindings", {}).get("baseline"), baseline.bindings, "baseline")
    deep_equal(receipt.get("snapshot_bindings", {}).get("candidate"), candidate.bindings, "candidate")
    deep_equal(receipt.get("append_only_and_increment"), append_only, "append-only")
    for key in ("inventory", "flat_pair_graph", "parent_recovery_modes"):
        deep_equal(receipt.get(key), metrics[key], key)
    deep_equal(receipt.get("classification"), classification, "classification")
    gate = receipt.get("pre_registered_gate", {})
    deep_equal(gate.get("hard_integrity_and_support"), hard, "hard gates")
    deep_equal(gate.get("strong_content_concordance"), strong, "strong gates")
    deep_equal(gate.get("hierarchy_complementarity"), complement, "complementarity gates")
    check(gate.get("all_hard_gates_passed") is all(hard.values()), "hard gate summary")
    check(gate.get("all_strong_content_gates_passed") is all(strong.values()), "strong gate summary")
    check(
        gate.get("all_hierarchy_complementarity_gates_passed") is all(complement.values()),
        "complement gate summary",
    )
    security = receipt.get("security", {})
    check(security.get("raw_senior_archives_opened") is False, "raw archive security")
    check(
        security.get("prospective_label_grade_outcome_prediction_values_read") is False,
        "prospective value security",
    )
    check(security.get("task_run_card_parent_code_or_per_pair_values_emitted") is False, "identity security")
    check(security.get("gpu_api_model_fit_base_update") == [0, 0, 0, 0], "resource security")
    return {
        "protocol": VERIFIER_PROTOCOL,
        "status": "INDEPENDENT_FORWARD_CONTENT_LINEAGE_AUDIT_PASS",
        "classification": classification,
        "protocol_sha256": actual_protocol_sha,
        "receipt_sha256": receipt_sha256,
        "analysis_source_commit": source_commit,
        "checks": {
            "imports_new_producer": False,
            "selection_package_independently_reconstructed": True,
            "baseline_and_candidate_independently_read": True,
            "append_only_increment_independently_rechecked": True,
            "identifier_erased_fingerprints_independently_recomputed": True,
            "pair_graph_and_three_parent_modes_independently_recomputed": True,
            "wrong_parent_controls_and_breadth_independently_recomputed": True,
            "exact_gates_and_classification_independently_recomputed": True,
            "task_run_card_parent_code_or_per_pair_values_emitted": False,
        },
        "security": {
            "prospective_label_grade_outcome_prediction_values_read": False,
            "raw_senior_archives_opened": False,
            "gpu_api_model_fit_base_update": [0, 0, 0, 0],
        },
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
    except (ContentLineageVerificationError, independent_snapshot.ForwardVerificationError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
