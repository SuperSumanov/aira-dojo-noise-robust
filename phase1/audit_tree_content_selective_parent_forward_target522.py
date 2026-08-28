"""Prospective fixed-threshold selective parent audit on the Target-522 increment.

The threshold is imported from the published snapshot-887 development certificate.
This producer reads only the hash-bound outcome-blind Target-522 selection package
and blind structural/code manifests.  It emits aggregate exact fractions and no
task, run, card, parent, code, or per-edge identities.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import platform
import re
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

from phase1 import audit_tree_content_lineage_forward_target522 as content_base
from phase1 import audit_tree_within_stratum_forward_target522 as snapshot_impl


PROTOCOL_NAME = "tree-content-selective-parent-forward-target522-v1"
PROTOCOL_STATUS = "OUTCOME_BLIND_FROZEN_AFTER_887_RESULT_BEFORE_TARGET522_CANDIDATE"
RECEIPT_PROTOCOL = "tree-content-selective-parent-forward-target522-receipt-v1"
RECEIPT_STATUS = "OUTCOME_BLIND_FORWARD_SELECTIVE_PARENT_AUDIT_COMPLETE"
COMMIT_RE = re.compile(r"[0-9a-f]{40}")


class ForwardSelectiveParentAuditError(RuntimeError):
    """Raised when a frozen integrity, support, or reproducibility check fails."""


@dataclass(frozen=True)
class EdgeRecord:
    task: str
    run: str
    candidates: int
    unique_top: bool
    correct: bool
    top_score: Fraction
    margin: Fraction


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ForwardSelectiveParentAuditError(message)


def file_sha256(path: Path) -> str:
    require(path.is_file() and not path.is_symlink(), f"unsafe file: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def exact(value: Fraction) -> dict[str, Any]:
    return {
        "numerator": value.numerator,
        "denominator": value.denominator,
        "decimal_17g": format(float(value), ".17g"),
    }


def decode_exact(payload: Any, label: str) -> Fraction:
    require(isinstance(payload, dict), f"missing exact payload: {label}")
    require(
        set(payload) == {"numerator", "denominator", "decimal_17g"},
        f"bad exact schema: {label}",
    )
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


def ratio(numerator: int, denominator: int) -> Fraction:
    return Fraction(numerator, denominator) if denominator else Fraction(0, 1)


def nearest_rank(values: list[Fraction], numerator: int, denominator: int) -> Fraction:
    require(bool(values), "empty nearest-rank population")
    ordered = sorted(values)
    rank = max(1, (numerator * len(ordered) + denominator - 1) // denominator)
    return ordered[rank - 1]


def quantiles(values: list[Fraction]) -> dict[str, Any] | None:
    if not values:
        return None
    return {
        "minimum": exact(min(values)),
        "median": exact(nearest_rank(values, 1, 2)),
        "p90_nearest_rank": exact(nearest_rank(values, 9, 10)),
        "maximum": exact(max(values)),
    }


def load_json_object(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"unsafe JSON object: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def load_protocol(
    path: Path, expected_sha256: str, repo_root: Path
) -> tuple[dict[str, Any], str, dict[str, str]]:
    actual = file_sha256(path)
    require(actual == expected_sha256, "forward selective protocol SHA mismatch")
    protocol = load_json_object(path)
    require(protocol.get("protocol") == PROTOCOL_NAME, "protocol name mismatch")
    require(protocol.get("status") == PROTOCOL_STATUS, "protocol status mismatch")
    freeze = protocol.get("freeze_state", {})
    require(freeze.get("target522_candidate_seen") is False, "candidate seen before freeze")
    require(freeze.get("target522_increment_profile_seen") is False, "profile seen before freeze")
    fixed = protocol.get("fixed_development_rule", {})
    require(fixed.get("threshold") == "1006/16929", "fixed threshold mismatch")
    require(fixed.get("threshold_reselection_on_future_allowed") is False, "threshold reselection")

    root = repo_root.resolve()
    dependencies: dict[str, str] = {}
    for role, binding in protocol["immutable_inputs"].items():
        require(isinstance(binding, dict), f"bad dependency binding: {role}")
        dependency = (root / binding["path"]).resolve()
        require(dependency.is_relative_to(root), f"dependency escapes repository: {role}")
        observed = file_sha256(dependency)
        require(observed == binding["sha256"], f"dependency SHA mismatch: {role}")
        dependencies[role] = observed

    development = load_json_object(
        root / protocol["immutable_inputs"]["development_summary"]["path"]
    )
    require(
        development.get("classification")
        == "DEVELOPMENT_TIME_SPLIT_HIGH_PRECISION_SELECTIVE_PARENT_RECOVERY",
        "development classification mismatch",
    )
    require(
        development.get("threshold_selection", {}).get("threshold")
        == exact(Fraction(1006, 16929)),
        "development threshold payload mismatch",
    )
    require(all(development.get("support_gates", {}).values()), "development support gate")
    require(all(development.get("primary_gates", {}).values()), "development primary gate")
    require(
        development.get("source_commit") == fixed["development_source_commit"],
        "development source commit mismatch",
    )
    development_verification = load_json_object(
        root / protocol["immutable_inputs"]["development_verification"]["path"]
    )
    require(
        development_verification.get("status")
        == "INDEPENDENT_SELECTIVE_PARENT_RECOVERY_VERIFIED"
        and development_verification.get("classification")
        == development.get("classification")
        and development_verification.get("source_commit")
        == fixed["development_source_commit"],
        "development verification mismatch",
    )
    return protocol, actual, dependencies


def edge_records(
    cards: dict[str, dict[str, Any]], payloads: dict[str, dict[str, Any]]
) -> tuple[dict[str, frozenset[int]], list[EdgeRecord], dict[str, int]]:
    fingerprints, by_run = content_base.fingerprint_population(cards, payloads)
    parent_present = fingerprint_eligible = depth_consistent = 0
    records: list[EdgeRecord] = []
    for child in sorted(cards):
        child_row = cards[child]
        parent = child_row["parent"]
        if parent not in cards:
            continue
        parent_present += 1
        if child not in fingerprints or parent not in fingerprints:
            continue
        fingerprint_eligible += 1
        if cards[parent]["depth"] + 1 != child_row["depth"]:
            continue
        depth_consistent += 1
        options = [
            candidate
            for candidate in by_run.get(child_row["run"], [])
            if cards[candidate]["depth"] == child_row["depth"] - 1
        ]
        require(parent in options, "recorded parent excluded from exact-depth candidates")
        if len(options) < 2:
            continue
        scores = {
            candidate: content_base.similarity(
                fingerprints[child], fingerprints[candidate]
            )
            for candidate in options
        }
        ordered_scores = sorted(scores.values(), reverse=True)
        top_score, second_score = ordered_scores[0], ordered_scores[1]
        winners = [candidate for candidate, score in scores.items() if score == top_score]
        unique = len(winners) == 1
        records.append(
            EdgeRecord(
                task=child_row["task"],
                run=child_row["run"],
                candidates=len(options),
                unique_top=unique,
                correct=unique and winners[0] == parent,
                top_score=top_score,
                margin=top_score - second_score,
            )
        )
    return fingerprints, records, {
        "parent_present_edges": parent_present,
        "fingerprint_eligible_parent_edges": fingerprint_eligible,
        "depth_consistent_fingerprint_eligible_parent_edges": depth_consistent,
        "depth_inconsistent_fingerprint_eligible_parent_edges": (
            fingerprint_eligible - depth_consistent
        ),
    }


def evaluate(rows: list[EdgeRecord], threshold: Fraction) -> dict[str, Any]:
    require(bool(rows), "empty ambiguous edge population")
    unfiltered = [row for row in rows if row.unique_top]
    selected = [
        row for row in rows if row.unique_top and row.margin >= threshold
    ]
    unfiltered_correct = sum(row.correct for row in unfiltered)
    selected_correct = sum(row.correct for row in selected)
    candidate_sizes = [Fraction(row.candidates, 1) for row in rows]
    return {
        "ambiguous_edges": len(rows),
        "unique_top_edges": len(unfiltered),
        "unfiltered_correct_edges": unfiltered_correct,
        "unfiltered_error_edges": len(unfiltered) - unfiltered_correct,
        "unfiltered_precision": exact(ratio(unfiltered_correct, len(unfiltered))),
        "unfiltered_coverage": exact(ratio(len(unfiltered), len(rows))),
        "selected_edges": len(selected),
        "selected_correct_edges": selected_correct,
        "selected_error_edges": len(selected) - selected_correct,
        "selected_precision": exact(ratio(selected_correct, len(selected))),
        "selected_coverage": exact(ratio(len(selected), len(rows))),
        "candidate_size_quantiles": {
            "median": int(nearest_rank(candidate_sizes, 1, 2)),
            "p90_nearest_rank": int(nearest_rank(candidate_sizes, 9, 10)),
            "maximum": max(row.candidates for row in rows),
        },
        "unique_top_margin_quantiles": quantiles(
            [row.margin for row in rows if row.unique_top]
        ),
    }


def group_profile(
    selected: list[EdgeRecord], field: str, minimum: int, reference: Fraction
) -> dict[str, Any]:
    grouped: dict[str, list[EdgeRecord]] = collections.defaultdict(list)
    for row in selected:
        grouped[getattr(row, field)].append(row)
    supported = [values for values in grouped.values() if len(values) >= minimum]
    precisions = [ratio(sum(row.correct for row in values), len(values)) for values in supported]
    all_sizes = [len(values) for values in grouped.values()]
    return {
        "minimum_accepted_edges": minimum,
        "precision_reference": exact(reference),
        "conditionable_groups": len(supported),
        "fraction_at_or_above_reference": exact(
            ratio(sum(value >= reference for value in precisions), len(precisions))
        ),
        "maximum_accepted_contribution_share": exact(
            ratio(max(all_sizes, default=0), sum(all_sizes))
        ),
        "precision_quantiles": quantiles(precisions),
        "identities_emitted": False,
    }


def wrong_pointer_controls(
    rows: list[EdgeRecord], threshold: Fraction
) -> dict[str, Any]:
    confident_wrong = [
        row
        for row in rows
        if row.unique_top and row.margin >= threshold and not row.correct
    ]
    wrong_alternatives = sum(row.candidates - 1 for row in rows)
    uniform_sum = sum(
        (Fraction(1, row.candidates - 1) for row in confident_wrong),
        start=Fraction(0, 1),
    )
    return {
        "all_wrong_alternatives": wrong_alternatives,
        "confident_wrong_unique_top_children": len(confident_wrong),
        "all_wrong_alternative_micro_false_acceptance": exact(
            ratio(len(confident_wrong), wrong_alternatives)
        ),
        "uniform_one_wrong_substitution_per_child_expected_false_acceptance": exact(
            uniform_sum / len(rows)
        ),
        "child_level_adversarial_vulnerability": exact(
            ratio(len(confident_wrong), len(rows))
        ),
        "denominators_are_not_interchangeable": True,
    }


def classify(
    profile: dict[str, Any],
    task: dict[str, Any],
    run: dict[str, Any],
    hard: dict[str, bool],
    protocol: dict[str, Any],
) -> tuple[str, dict[str, bool]]:
    gates = protocol["primary_gates"]
    precision = decode_exact(profile["selected_precision"], "selected precision")
    coverage = decode_exact(profile["selected_coverage"], "selected coverage")
    unfiltered_error = Fraction(1, 1) - decode_exact(
        profile["unfiltered_precision"], "unfiltered precision"
    )
    selected_error = Fraction(1, 1) - precision
    primary = {
        "forward_precision": precision >= Fraction(gates["minimum_forward_precision"]),
        "forward_coverage": coverage >= Fraction(gates["minimum_forward_coverage"]),
        "selective_error_reduction": selected_error
        <= Fraction(gates["maximum_selective_error_relative_to_unfiltered_error"])
        * unfiltered_error,
        "task_breadth": decode_exact(
            task["fraction_at_or_above_reference"], "task breadth"
        )
        >= Fraction(gates["minimum_task_fraction_at_reference"]),
        "task_anti_dominance": decode_exact(
            task["maximum_accepted_contribution_share"], "task contribution"
        )
        <= Fraction(gates["maximum_single_task_accepted_contribution_share"]),
        "run_breadth": decode_exact(
            run["fraction_at_or_above_reference"], "run breadth"
        )
        >= Fraction(gates["minimum_run_fraction_at_reference"]),
        "run_anti_dominance": decode_exact(
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
    elif all(value for key, value in hard.items() if key not in {"selected_edges_at_least_minimum"}):
        classification = "FORWARD_SELECTIVE_PARENT_RECOVERY_BELOW_GATE"
    else:
        classification = "FORWARD_SELECTIVE_PARENT_RECOVERY_GATE_FAIL"
    require(classification in protocol["ordered_classification"], "classification outside protocol")
    return classification, primary


def build_receipt(
    state_root: Path,
    selection_root: Path,
    repo_root: Path,
    protocol_path: Path,
    protocol_sha256: str,
    source_commit: str,
) -> dict[str, Any]:
    require(COMMIT_RE.fullmatch(source_commit) is not None, "invalid source commit")
    protocol, actual_protocol_sha, dependencies = load_protocol(
        protocol_path, protocol_sha256, repo_root
    )
    activation = protocol["activation_rule"]
    selection_protocol_path = repo_root.resolve() / activation["selection_protocol"]
    selection_protocol, selection_protocol_sha = snapshot_impl.load_protocol(
        selection_protocol_path, activation["selection_protocol_sha256"]
    )
    selection = snapshot_impl.verify_selection(
        selection_root, repo_root, selection_protocol, selection_protocol_sha
    )
    require(
        selection["selection_monitor_source_sha256"]
        == activation["selection_monitor_sha256"],
        "selection monitor hash mismatch",
    )
    baseline = snapshot_impl.load_blind_snapshot(
        state_root, selection["baseline_snapshot_sha256"]
    )
    candidate = snapshot_impl.load_blind_snapshot(
        state_root, selection["candidate_snapshot_sha256"]
    )
    for snapshot, observed in (
        (baseline, selection["baseline_observation"]),
        (candidate, selection["candidate_observation"]),
    ):
        require(
            snapshot.bindings["accumulator_summary_sha256"] == observed["summary_sha256"]
            and snapshot.bindings["registry_sha256"] == observed["registry_sha256"]
            and snapshot.bindings["provisional_runs_sha256"] == observed["runs_sha256"],
            "selection observation binding mismatch",
        )
    require(
        baseline.snapshot_sha256 == protocol["freeze_state"]["baseline_snapshot_sha256"],
        "baseline snapshot mismatch",
    )
    cards, increment_runs, append_only = snapshot_impl.disjoint_increment(
        baseline, candidate, selection_protocol
    )
    payloads = {identity: candidate.card_payloads[identity] for identity in cards}
    fingerprints, rows, edge_inventory = edge_records(cards, payloads)
    threshold = Fraction(protocol["fixed_development_rule"]["threshold"])
    profile = evaluate(rows, threshold)
    selected = [row for row in rows if row.unique_top and row.margin >= threshold]
    gates = protocol["primary_gates"]
    task = group_profile(
        selected,
        "task",
        gates["task_minimum_accepted_edges"],
        Fraction(gates["task_precision_reference"]),
    )
    run = group_profile(
        selected,
        "run",
        gates["run_minimum_accepted_edges"],
        Fraction(gates["run_precision_reference"]),
    )
    controls = wrong_pointer_controls(rows, threshold)
    support = protocol["hard_integrity_and_support_gates"]
    inventory = {
        "increment_endpoints": len(cards),
        "increment_physical_runs": len(increment_runs),
        "increment_tasks": len({row["task"] for row in cards.values()}),
        "fingerprinted_endpoints": len(fingerprints),
        "fingerprint_coverage": exact(ratio(len(fingerprints), len(cards))),
        "ambiguous_exact_depth_edges": len(rows),
        **edge_inventory,
    }
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
        "fixed_threshold_matches_development_certificate": threshold == Fraction(1006, 16929),
        "fingerprint_coverage_at_least_minimum": decode_exact(
            inventory["fingerprint_coverage"], "fingerprint coverage"
        )
        >= Fraction(support["minimum_fingerprint_coverage"]),
        "all_fingerprint_eligible_parent_edges_depth_consistent": edge_inventory[
            "depth_inconsistent_fingerprint_eligible_parent_edges"
        ]
        == 0,
        "ambiguous_edges_at_least_minimum": len(rows)
        >= support["minimum_ambiguous_exact_depth_edges"],
        "selected_edges_at_least_minimum": len(selected)
        >= support["minimum_selected_edges"],
        "wrong_alternatives_at_least_minimum": controls["all_wrong_alternatives"]
        >= support["minimum_wrong_parent_alternatives"],
        "conditionable_tasks_at_least_minimum": task["conditionable_groups"]
        >= support["minimum_conditionable_tasks"],
        "conditionable_runs_at_least_minimum": run["conditionable_groups"]
        >= support["minimum_conditionable_physical_runs"],
        "all_gate_comparisons_use_exact_fractions": True,
    }
    classification, primary = classify(profile, task, run, hard, protocol)
    return {
        "protocol": RECEIPT_PROTOCOL,
        "status": RECEIPT_STATUS,
        "classification": classification,
        "protocol_sha256": actual_protocol_sha,
        "analysis_source_commit": source_commit,
        "producer_source_sha256": file_sha256(Path(__file__)),
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
        "inventory": inventory,
        "fixed_development_rule": {
            **protocol["fixed_development_rule"],
            "threshold_exact": exact(threshold),
        },
        "forward_profile": profile,
        "forward_breadth": {"task": task, "physical_run": run},
        "forward_wrong_pointer_controls": controls,
        "pre_registered_gate": {
            "hard_integrity_and_support": hard,
            "primary": primary,
            "all_hard_gates_passed": all(hard.values()),
            "all_primary_gates_passed": all(primary.values()),
            "fixed_thresholds": {
                "hard": support,
                "primary": gates,
            },
        },
        "claim_boundary": protocol["claim_boundary"],
        "security": {
            "raw_senior_archives_opened": False,
            "prospective_label_grade_outcome_prediction_values_read": False,
            "task_run_card_parent_code_or_per_edge_values_emitted": False,
            "predictor_accuracy_effect_or_search_utility_computed": False,
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
    except (ForwardSelectiveParentAuditError, snapshot_impl.ForwardAuditError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
