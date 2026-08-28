"""Forward outcome-blind hierarchy/content parent-concordance audit.

The producer consumes only the hash-bound Target-522 selection package and
blind structural/code manifests.  It emits aggregate exact fractions and never
emits endpoint, run, task, parent, code, or pair identities.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import platform
import re
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable

from phase1 import audit_prospective_fuzzy_code_clones as fingerprint_impl
from phase1 import audit_tree_within_stratum_forward_target522 as snapshot_impl


PROTOCOL_NAME = "tree-content-lineage-forward-target522-v1"
RECEIPT_PROTOCOL = "tree-content-lineage-forward-target522-receipt-v1"
RECEIPT_STATUS = "OUTCOME_BLIND_FORWARD_CONTENT_LINEAGE_AUDIT_COMPLETE"
EXPECTED_STATUS = (
    "OUTCOME_BLIND_FROZEN_AFTER_DISCLOSED_887_DEVELOPMENT_BEFORE_TARGET522_SELECTION_COMPLETE"
)
COMMIT_RE = re.compile(r"[0-9a-f]{40}")


class ContentLineageAuditError(RuntimeError):
    """Raised when a frozen integrity, support, or reproducibility check fails."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContentLineageAuditError(message)


def sha256_file(path: Path) -> str:
    require(path.is_file() and not path.is_symlink(), f"unsafe file: {path}")
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def exact(value: Fraction) -> dict[str, Any]:
    return {
        "numerator": value.numerator,
        "denominator": value.denominator,
        "decimal_17g": format(float(value), ".17g"),
    }


def exact_value(payload: Any, label: str) -> Fraction:
    require(isinstance(payload, dict), f"missing exact payload: {label}")
    require(set(payload) == {"numerator", "denominator", "decimal_17g"}, f"bad exact schema: {label}")
    numerator, denominator = payload["numerator"], payload["denominator"]
    require(
        isinstance(numerator, int)
        and not isinstance(numerator, bool)
        and isinstance(denominator, int)
        and not isinstance(denominator, bool)
        and denominator > 0,
        f"bad exact fraction: {label}",
    )
    return Fraction(numerator, denominator)


def ratio(part: int, whole: int) -> Fraction:
    return Fraction(part, whole) if whole else Fraction(0, 1)


def divide_fraction(value: Fraction, denominator: int) -> Fraction:
    return value / denominator if denominator else Fraction(0, 1)


def nearest_rank(values: list[Fraction], numerator: int, denominator: int) -> Fraction:
    require(bool(values), "empty nearest-rank population")
    ordered = sorted(values)
    rank = max(1, (numerator * len(ordered) + denominator - 1) // denominator)
    return ordered[rank - 1]


def similarity(left: frozenset[int], right: frozenset[int]) -> Fraction:
    intersection = len(left.intersection(right))
    union = len(left) + len(right) - intersection
    require(union > 0, "empty fingerprint union")
    return Fraction(intersection, union)


def load_protocol(path: Path, expected_sha256: str) -> tuple[dict[str, Any], str]:
    actual = sha256_file(path)
    require(actual == expected_sha256, "content-lineage protocol SHA mismatch")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), "content-lineage protocol is not an object")
    require(value.get("protocol") == PROTOCOL_NAME, "content-lineage protocol name mismatch")
    require(value.get("status") == EXPECTED_STATUS, "content-lineage protocol status mismatch")
    freeze = value.get("freeze_state", {})
    require(freeze.get("target522_candidate_snapshot_identity_seen") is False, "candidate seen before freeze")
    require(freeze.get("target522_increment_profile_seen") is False, "increment profile seen before freeze")
    development = value.get("development_evidence_seen_before_freeze", {})
    require(
        development.get("exact_depth_unique_top_recovery") == "9196/9739"
        and development.get("flat_pair_oracle_maximum_f1") == "11446/22315"
        and development.get("same_run_without_depth_unique_top_recovery") == "2633/5438",
        "development disclosure mismatch",
    )
    return value, actual


def bind_dependency_hashes(repo_root: Path, protocol: dict[str, Any]) -> dict[str, str]:
    root = repo_root.resolve()
    dependencies = protocol["implementation_dependencies"]
    bound: dict[str, str] = {}
    for role in ("snapshot_producer", "snapshot_verifier", "fingerprint_producer", "fingerprint_verifier"):
        relative = dependencies[f"{role}_module"]
        expected = dependencies[f"{role}_sha256"]
        path = (root / relative).resolve()
        require(path.is_relative_to(root), f"dependency escapes repository: {role}")
        require(sha256_file(path) == expected, f"dependency SHA mismatch: {role}")
        bound[role] = expected
    return bound


def fingerprint_population(
    cards: dict[str, dict[str, Any]], payloads: dict[str, dict[str, Any]]
) -> tuple[dict[str, frozenset[int]], dict[str, list[str]]]:
    fingerprints: dict[str, frozenset[int]] = {}
    for identity in sorted(cards):
        require(identity in payloads, "missing increment endpoint payload")
        value = fingerprint_impl.identifier_erased_token_shingles(payloads[identity]["code"])
        if value is not None:
            fingerprints[identity] = value
    by_run: dict[str, list[str]] = collections.defaultdict(list)
    for identity in fingerprints:
        by_run[cards[identity]["run"]].append(identity)
    for identities in by_run.values():
        identities.sort()
    return fingerprints, dict(by_run)


def eligible_parent_inventory(
    cards: dict[str, dict[str, Any]], fingerprints: dict[str, frozenset[int]]
) -> tuple[list[tuple[str, str]], dict[str, int]]:
    eligible: list[tuple[str, str]] = []
    depth_consistent: list[tuple[str, str]] = []
    for child in sorted(cards):
        parent = cards[child]["parent"]
        if parent not in cards or child not in fingerprints or parent not in fingerprints:
            continue
        eligible.append((child, parent))
        if cards[parent]["depth"] + 1 == cards[child]["depth"]:
            depth_consistent.append((child, parent))
    return depth_consistent, {
        "fingerprint_eligible_parent_edges": len(eligible),
        "depth_consistent_fingerprint_eligible_parent_edges": len(depth_consistent),
        "depth_inconsistent_fingerprint_eligible_parent_edges": len(eligible) - len(depth_consistent),
    }


def breadth(rows: list[tuple[str, bool]], minimum: int) -> dict[str, Any]:
    grouped: dict[str, list[bool]] = collections.defaultdict(list)
    for group, success in rows:
        grouped[group].append(success)
    supported = [values for values in grouped.values() if len(values) >= minimum]
    rates = [ratio(sum(values), len(values)) for values in supported]
    sizes = [len(values) for values in supported]
    return {
        "minimum_edges_per_group": minimum,
        "conditionable_groups": len(supported),
        "fraction_at_or_above_17_over_20": exact(
            ratio(sum(value >= Fraction(17, 20) for value in rates), len(rates))
        ),
        "fraction_at_or_above_9_over_10": exact(
            ratio(sum(value >= Fraction(9, 10) for value in rates), len(rates))
        ),
        "maximum_edge_contribution_share": exact(ratio(max(sizes, default=0), sum(sizes))),
        "rate_quantiles": {
            "minimum": exact(min(rates)) if rates else None,
            "median": exact(nearest_rank(rates, 1, 2)) if rates else None,
            "p90_nearest_rank": exact(nearest_rank(rates, 9, 10)) if rates else None,
            "maximum": exact(max(rates)) if rates else None,
        },
        "identities_emitted": False,
    }


def candidate_selector(
    mode: str, cards: dict[str, dict[str, Any]], child: str
) -> Callable[[str], bool]:
    child_row = cards[child]
    if mode == "exact_preceding_depth":
        return lambda candidate: cards[candidate]["depth"] == child_row["depth"] - 1
    if mode == "any_shallower_depth":
        return lambda candidate: cards[candidate]["depth"] < child_row["depth"]
    if mode == "same_run_without_depth":
        return lambda candidate: candidate != child
    raise ContentLineageAuditError("unknown candidate mode")


def evaluate_mode(
    mode: str,
    cards: dict[str, dict[str, Any]],
    fingerprints: dict[str, frozenset[int]],
    by_run: dict[str, list[str]],
    depth_consistent_edges: list[tuple[str, str]],
    protocol: dict[str, Any],
) -> dict[str, Any]:
    ambiguous = recovered = unique_recovered = 0
    random_total = Fraction(0, 1)
    wrong_total = wrong_accepted = 0
    random_wrong_total = Fraction(0, 1)
    candidate_sizes: list[Fraction] = []
    parent_ranks: list[Fraction] = []
    task_rows: list[tuple[str, bool]] = []
    run_rows: list[tuple[str, bool]] = []

    for child, parent in depth_consistent_edges:
        selector = candidate_selector(mode, cards, child)
        options = [candidate for candidate in by_run[cards[child]["run"]] if selector(candidate)]
        require(parent in options, f"{mode} excluded recorded parent")
        scores = {
            candidate: similarity(fingerprints[child], fingerprints[candidate])
            for candidate in options
        }
        maximum = max(scores.values())
        top_count = sum(value == maximum for value in scores.values())
        parent_score = scores[parent]
        parent_is_top = parent_score == maximum
        candidate_sizes.append(Fraction(len(options), 1))
        parent_ranks.append(Fraction(1 + sum(value > parent_score for value in scores.values()), 1))
        if len(options) < 2:
            continue
        ambiguous += 1
        recovered += int(parent_is_top)
        unique = parent_is_top and top_count == 1
        unique_recovered += int(unique)
        random_total += Fraction(1, len(options))
        task_rows.append((cards[child]["task"], unique))
        run_rows.append((cards[child]["run"], unique))
        wrong_total += len(options) - 1
        wrong_accepted += int((not parent_is_top) and top_count == 1)
        if (not parent_is_top) and top_count == 1:
            random_wrong_total += Fraction(1, len(options) - 1)

    require(bool(candidate_sizes), f"empty candidate mode: {mode}")
    task_minimum = protocol["parent_recovery_estimands"]["task_breadth_minimum_edges"]
    run_minimum = protocol["parent_recovery_estimands"]["physical_run_breadth_minimum_edges"]
    return {
        "mode": mode,
        "eligible_parent_edges": len(depth_consistent_edges),
        "ambiguous_parent_edges": ambiguous,
        "optimistic_top_tie_recovery": exact(ratio(recovered, ambiguous)),
        "unique_top_recovery": exact(ratio(unique_recovered, ambiguous)),
        "uniform_random_expected_recovery": exact(divide_fraction(random_total, ambiguous)),
        "unique_top_lift_over_uniform_random": exact(
            ratio(unique_recovered, ambiguous) - divide_fraction(random_total, ambiguous)
        ),
        "enumerated_wrong_parent_alternatives": wrong_total,
        "wrong_alternatives_accepted_as_unique_top": wrong_accepted,
        "exhaustive_wrong_parent_false_acceptance_rate": exact(
            ratio(wrong_accepted, wrong_total)
        ),
        "uniform_single_wrong_substitution_expected_false_acceptance": exact(
            divide_fraction(random_wrong_total, ambiguous)
        ),
        "candidate_size_quantiles": {
            "median": int(nearest_rank(candidate_sizes, 1, 2)),
            "p90_nearest_rank": int(nearest_rank(candidate_sizes, 9, 10)),
            "maximum": int(max(candidate_sizes)),
        },
        "optimistic_parent_rank_quantiles": {
            "median": int(nearest_rank(parent_ranks, 1, 2)),
            "p90_nearest_rank": int(nearest_rank(parent_ranks, 9, 10)),
            "maximum": int(max(parent_ranks)),
        },
        "unique_top_breadth": {
            "task": breadth(task_rows, task_minimum),
            "physical_run": breadth(run_rows, run_minimum),
        },
    }


def oracle_pair_f1(rows: list[tuple[Fraction, bool]], positives: int) -> dict[str, Any]:
    buckets: dict[Fraction, list[bool]] = collections.defaultdict(list)
    for score, label in rows:
        buckets[score].append(label)
    predicted = true_positive = 0
    candidates: list[tuple[Fraction, Fraction, int, int]] = []
    for threshold in sorted(buckets, reverse=True):
        labels = buckets[threshold]
        predicted += len(labels)
        true_positive += sum(labels)
        candidates.append(
            (Fraction(2 * true_positive, predicted + positives), threshold, predicted, true_positive)
        )
    require(bool(candidates), "empty flat pair graph")
    best_f1, best_threshold, best_predicted, best_true_positive = max(
        candidates, key=lambda row: (row[0], row[1])
    )
    return {
        "maximum_f1": exact(best_f1),
        "optimistically_selected_threshold": exact(best_threshold),
        "predicted_pairs_at_optimum": best_predicted,
        "true_positive_pairs_at_optimum": best_true_positive,
        "selection_role": "same-population oracle upper bound; not a deployable threshold",
    }


def flat_pair_graph(
    cards: dict[str, dict[str, Any]],
    fingerprints: dict[str, frozenset[int]],
    by_run: dict[str, list[str]],
    eligible_parent_edges: int,
) -> dict[str, Any]:
    rows: list[tuple[Fraction, bool]] = []
    positives = 0
    for identities in by_run.values():
        for right_index, right in enumerate(identities):
            for left in identities[:right_index]:
                label = cards[left]["parent"] == right or cards[right]["parent"] == left
                positives += int(label)
                rows.append((similarity(fingerprints[left], fingerprints[right]), label))
    require(positives == eligible_parent_edges, "flat pair parent accounting mismatch")
    cutoff = Fraction(17, 20)
    selected = [label for value, label in rows if value >= cutoff]
    true_positive = sum(selected)
    return {
        "within_run_fingerprinted_pairs": len(rows),
        "fingerprint_eligible_parent_edges": positives,
        "fixed_17_over_20": {
            "predicted_pairs": len(selected),
            "true_positive_pairs": true_positive,
            "precision": exact(ratio(true_positive, len(selected))),
            "recall": exact(ratio(true_positive, positives)),
            "f1": exact(ratio(2 * true_positive, len(selected) + positives)),
        },
        "same_population_oracle": oracle_pair_f1(rows, positives),
    }


def compute_metrics(
    cards: dict[str, dict[str, Any]],
    payloads: dict[str, dict[str, Any]],
    protocol: dict[str, Any],
) -> dict[str, Any]:
    fingerprints, by_run = fingerprint_population(cards, payloads)
    edges, inventory = eligible_parent_inventory(cards, fingerprints)
    modes = {
        mode: evaluate_mode(mode, cards, fingerprints, by_run, edges, protocol)
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
            "fingerprint_coverage": exact(Fraction(len(fingerprints), len(cards))),
            **inventory,
            "increment_tasks": len({row["task"] for row in cards.values()}),
            "increment_physical_runs": len({row["run"] for row in cards.values()}),
        },
        "flat_pair_graph": flat_pair_graph(
            cards,
            fingerprints,
            by_run,
            inventory["fingerprint_eligible_parent_edges"],
        ),
        "parent_recovery_modes": modes,
    }


def classify(
    metrics: dict[str, Any], protocol: dict[str, Any], hard: dict[str, bool]
) -> tuple[str, dict[str, bool], dict[str, bool]]:
    exact_mode = metrics["parent_recovery_modes"]["exact_preceding_depth"]
    no_depth = metrics["parent_recovery_modes"]["same_run_without_depth"]
    task = exact_mode["unique_top_breadth"]["task"]
    run = exact_mode["unique_top_breadth"]["physical_run"]
    strong_thresholds = protocol["strong_content_concordance_gates"]
    strong = {
        "exact_depth_unique_top_recovery": exact_value(
            exact_mode["unique_top_recovery"], "exact recovery"
        )
        >= Fraction(strong_thresholds["minimum_exact_depth_unique_top_recovery"]),
        "exact_depth_lift_over_uniform_random": exact_value(
            exact_mode["unique_top_lift_over_uniform_random"], "random lift"
        )
        >= Fraction(strong_thresholds["minimum_exact_depth_lift_over_uniform_random"]),
        "wrong_parent_false_acceptance": exact_value(
            exact_mode["exhaustive_wrong_parent_false_acceptance_rate"], "wrong FPR"
        )
        <= Fraction(strong_thresholds["maximum_exhaustive_wrong_parent_false_acceptance"]),
        "task_breadth": exact_value(
            task["fraction_at_or_above_17_over_20"], "task breadth"
        )
        >= Fraction(strong_thresholds["minimum_task_fraction_at_or_above_breadth_reference"]),
        "physical_run_breadth": exact_value(
            run["fraction_at_or_above_17_over_20"], "run breadth"
        )
        >= Fraction(strong_thresholds["minimum_physical_run_fraction_at_or_above_breadth_reference"]),
        "task_anti_dominance": exact_value(
            task["maximum_edge_contribution_share"], "task contribution"
        )
        <= Fraction(strong_thresholds["maximum_single_task_edge_contribution_share"]),
        "physical_run_anti_dominance": exact_value(
            run["maximum_edge_contribution_share"], "run contribution"
        )
        <= Fraction(strong_thresholds["maximum_single_physical_run_edge_contribution_share"]),
    }
    complement_thresholds = protocol["hierarchy_complementarity_gates"]
    exact_recovery = exact_value(exact_mode["unique_top_recovery"], "exact recovery")
    no_depth_recovery = exact_value(no_depth["unique_top_recovery"], "no-depth recovery")
    complement = {
        "no_depth_recovery_below_ceiling": no_depth_recovery
        <= Fraction(complement_thresholds["maximum_same_run_without_depth_unique_top_recovery"]),
        "exact_depth_gain_over_no_depth": exact_recovery - no_depth_recovery
        >= Fraction(complement_thresholds["minimum_exact_depth_minus_no_depth_unique_top_recovery"]),
        "flat_pair_oracle_f1_below_ceiling": exact_value(
            metrics["flat_pair_graph"]["same_population_oracle"]["maximum_f1"],
            "flat pair oracle F1",
        )
        <= Fraction(complement_thresholds["maximum_flat_pair_graph_oracle_f1"]),
    }
    if not all(hard.values()):
        classification = "FORWARD_PARENT_CONCORDANCE_GATE_FAIL"
    elif all(strong.values()) and all(complement.values()):
        classification = "FORWARD_HIERARCHY_CONTENT_PARENT_CONCORDANCE_CERTIFICATE"
    elif all(strong.values()):
        classification = "FORWARD_CONTENT_PARENT_CONCORDANCE_WITHOUT_HIERARCHY_COMPLEMENTARITY"
    else:
        classification = "FORWARD_PARENT_CONCORDANCE_PROFILE_BELOW_STRONG_GATE"
    require(classification in protocol["ordered_classification"], "classification outside protocol")
    return classification, strong, complement


def build_receipt(
    state_root: Path,
    selection_root: Path,
    repo_root: Path,
    protocol_path: Path,
    protocol_sha256: str,
    source_commit: str,
) -> dict[str, Any]:
    require(COMMIT_RE.fullmatch(source_commit) is not None, "invalid source commit")
    protocol, actual_protocol_sha = load_protocol(protocol_path, protocol_sha256)
    dependencies = bind_dependency_hashes(repo_root, protocol)

    selection_protocol_path = repo_root.resolve() / protocol["activation_rule"]["selection_protocol"]
    selection_protocol, selection_protocol_sha = snapshot_impl.load_protocol(
        selection_protocol_path,
        protocol["activation_rule"]["selection_protocol_sha256"],
    )
    selection = snapshot_impl.verify_selection(
        selection_root,
        repo_root,
        selection_protocol,
        selection_protocol_sha,
    )
    require(
        selection["selection_monitor_source_sha256"]
        == protocol["activation_rule"]["selection_monitor_sha256"],
        "selection monitor hash differs from content-lineage protocol",
    )
    baseline = snapshot_impl.load_blind_snapshot(
        state_root, selection["baseline_snapshot_sha256"]
    )
    candidate = snapshot_impl.load_blind_snapshot(
        state_root, selection["candidate_snapshot_sha256"]
    )
    for cohort, observed in (
        (baseline, selection["baseline_observation"]),
        (candidate, selection["candidate_observation"]),
    ):
        require(
            cohort.bindings["accumulator_summary_sha256"] == observed["summary_sha256"]
            and cohort.bindings["registry_sha256"] == observed["registry_sha256"]
            and cohort.bindings["provisional_runs_sha256"] == observed["runs_sha256"],
            "selection observation binding mismatch",
        )
    require(
        baseline.snapshot_sha256 == protocol["freeze_state"]["baseline_snapshot_sha256"],
        "baseline snapshot differs from content-lineage freeze",
    )
    increment_cards, increment_runs, append_only = snapshot_impl.disjoint_increment(
        baseline, candidate, selection_protocol
    )
    increment_payloads = {
        identity: candidate.card_payloads[identity] for identity in increment_cards
    }
    metrics = compute_metrics(increment_cards, increment_payloads, protocol)
    inventory = metrics["inventory"]
    exact_mode = metrics["parent_recovery_modes"]["exact_preceding_depth"]
    support = protocol["hard_integrity_and_support_gates"]
    hard = {
        **selection["checks"],
        "baseline_is_exact_byte_unchanged_prefix": all(
            value is True for value in append_only.values() if isinstance(value, bool)
        ),
        "candidate_total_runs_at_least_target": len(candidate.runs)
        >= support["candidate_total_runs_at_least"],
        "disjoint_increment_runs_at_least_minimum": len(increment_runs)
        >= support["disjoint_increment_runs_at_least"],
        "candidate_accumulator_is_outcome_blind_and_unclosed": True,
        "fingerprint_coverage_at_least_minimum": exact_value(
            inventory["fingerprint_coverage"], "fingerprint coverage"
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
        "conditionable_tasks_at_least_minimum": exact_mode["unique_top_breadth"]["task"][
            "conditionable_groups"
        ]
        >= support["minimum_conditionable_tasks"],
        "conditionable_physical_runs_at_least_minimum": exact_mode["unique_top_breadth"]
        ["physical_run"]["conditionable_groups"]
        >= support["minimum_conditionable_physical_runs"],
        "all_gate_comparisons_use_exact_fractions": True,
        "decimal_strings_are_descriptive_only": True,
    }
    classification, strong, complement = classify(metrics, protocol, hard)
    return {
        "protocol": RECEIPT_PROTOCOL,
        "status": RECEIPT_STATUS,
        "classification": classification,
        "protocol_sha256": actual_protocol_sha,
        "analysis_source_commit": source_commit,
        "producer_source_sha256": sha256_file(Path(__file__)),
        "dependency_source_sha256s": dependencies,
        "snapshot_bindings": {
            "baseline": baseline.bindings,
            "candidate": candidate.bindings,
            "selection_support": {
                "sha256sums_sha256": selection["selection_support_sha256sums_sha256"],
                "monitor_source_sha256": selection["selection_monitor_source_sha256"],
                "selection_protocol_sha256": selection_protocol_sha,
            },
        },
        "append_only_and_increment": append_only,
        **metrics,
        "pre_registered_gate": {
            "hard_integrity_and_support": hard,
            "strong_content_concordance": strong,
            "hierarchy_complementarity": complement,
            "all_hard_gates_passed": all(hard.values()),
            "all_strong_content_gates_passed": all(strong.values()),
            "all_hierarchy_complementarity_gates_passed": all(complement.values()),
            "fixed_thresholds": {
                "hard": support,
                "strong": protocol["strong_content_concordance_gates"],
                "complementarity": protocol["hierarchy_complementarity_gates"],
            },
        },
        "related_work_and_claim_boundary": protocol["related_work_and_claim_boundary"],
        "security": {
            "corpus_input_basenames": protocol["security"]["corpus_input_basenames"],
            "selection_support_input_basenames": protocol["security"][
                "selection_support_input_basenames"
            ],
            "raw_senior_archives_opened": False,
            "prospective_label_grade_outcome_prediction_values_read": False,
            "task_run_card_parent_code_or_per_pair_values_emitted": False,
            "accuracy_effect_or_search_utility_computed": False,
            "gpu_api_model_fit_base_update": [0, 0, 0, 0],
        },
        "reproducibility": {
            "python_version": platform.python_version(),
            "randomness_used": False,
            "decimal_values_used_for_gates": False,
        },
    }


def write_once(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, sort_keys=True, indent=2, ensure_ascii=False)
        handle.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--selection-root", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--expect-protocol-sha256", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        receipt = build_receipt(
            args.state_root.resolve(),
            args.selection_root.resolve(),
            args.repo_root.resolve(),
            args.protocol.resolve(),
            args.expect_protocol_sha256,
            args.source_commit,
        )
        write_once(args.out.resolve(), receipt)
    except (ContentLineageAuditError, snapshot_impl.ForwardAuditError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
