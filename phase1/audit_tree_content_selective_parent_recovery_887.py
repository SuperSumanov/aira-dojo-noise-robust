#!/usr/bin/env python3
"""Run-disjoint selective recovery audit for recorded tree parent pointers.

This development-only producer reads the already disclosed, outcome-blind
snapshot 887.  It never emits card, run, task, parent, code, or per-edge data.
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

from phase1 import audit_prospective_fuzzy_code_clones as fingerprint_impl
from phase1 import audit_tree_within_stratum_forward_target522 as snapshot_impl


PROTOCOL = "tree-content-selective-parent-recovery-887-v1"
STATUS = "OUTCOME_BLIND_DEVELOPMENT_SPLIT_FROZEN_BEFORE_MARGIN_READOUT"
RESULT_STATUS = "OUTCOME_BLIND_DEVELOPMENT_SELECTIVE_PARENT_RECOVERY_COMPLETE"
SHA_RE = re.compile(r"[0-9a-f]{64}")
COMMIT_RE = re.compile(r"[0-9a-f]{40}")


class SelectiveParentAuditError(RuntimeError):
    """Raised when a frozen input, split, rule, or output invariant fails."""


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
        raise SelectiveParentAuditError(message)


def sha256_file(path: Path) -> str:
    require(path.is_file() and not path.is_symlink(), f"unsafe file: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def exact(value: Fraction) -> dict[str, Any]:
    return {
        "numerator": value.numerator,
        "denominator": value.denominator,
        "decimal_17g": format(float(value), ".17g"),
    }


def ratio(part: int, whole: int) -> Fraction:
    return Fraction(part, whole) if whole else Fraction(0, 1)


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


def jaccard(left: frozenset[int], right: frozenset[int]) -> Fraction:
    intersection = len(left.intersection(right))
    union = len(left) + len(right) - intersection
    require(union > 0, "empty fingerprint union")
    return Fraction(intersection, union)


def read_protocol(path: Path, expected_sha256: str, repo_root: Path) -> tuple[dict[str, Any], str]:
    actual = sha256_file(path)
    require(actual == expected_sha256, "protocol SHA mismatch")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), "protocol root is not an object")
    require(value.get("protocol") == PROTOCOL, "protocol identity mismatch")
    require(value.get("status") == STATUS, "protocol status mismatch")
    freeze = value.get("freeze_state", {})
    require(
        freeze.get("target522_candidate_seen") is False
        and freeze.get("margin_distribution_seen") is False
        and freeze.get("margin_correctness_profile_seen") is False
        and freeze.get("selected_margin_threshold_seen") is False
        and freeze.get("chronological_test_profile_seen") is False,
        "result-blind freeze declaration mismatch",
    )
    disclosed = value.get("disclosed_before_freeze", {})
    require(
        disclosed.get("exact_depth_unique_top_recovery") == "9196/9739"
        and disclosed.get("exact_depth_wrong_alternative_micro_false_acceptance") == "543/99039"
        and disclosed.get("child_level_adversarial_vulnerability") == "543/9739"
        and disclosed.get("margin_conditioned_or_chronological_split_values_seen") is False,
        "prior disclosure mismatch",
    )
    root = repo_root.resolve()
    require(root.is_dir(), "repository root missing")
    bindings = value.get("immutable_inputs", {})
    for role in (
        "producer_snapshot_loader",
        "independent_snapshot_loader",
        "producer_fingerprint",
        "independent_fingerprint",
    ):
        relative = bindings.get(role)
        expected = bindings.get(f"{role}_sha256")
        require(isinstance(relative, str) and isinstance(expected, str), f"missing dependency: {role}")
        dependency = (root / relative).resolve()
        require(dependency.is_relative_to(root), f"dependency escapes repository: {role}")
        require(sha256_file(dependency) == expected, f"dependency SHA mismatch: {role}")
    return value, actual


def fingerprint_population(
    snapshot: snapshot_impl.BlindSnapshot,
) -> tuple[dict[str, frozenset[int]], dict[str, list[str]]]:
    fingerprints: dict[str, frozenset[int]] = {}
    by_run: dict[str, list[str]] = collections.defaultdict(list)
    for card_id in sorted(snapshot.cards):
        value = fingerprint_impl.identifier_erased_token_shingles(
            snapshot.card_payloads[card_id]["code"]
        )
        if value is None:
            continue
        fingerprints[card_id] = value
        by_run[snapshot.cards[card_id]["run"]].append(card_id)
    for members in by_run.values():
        members.sort()
    return fingerprints, dict(by_run)


def edge_records(
    snapshot: snapshot_impl.BlindSnapshot,
    fingerprints: dict[str, frozenset[int]],
    by_run: dict[str, list[str]],
) -> tuple[list[EdgeRecord], dict[str, int]]:
    records: list[EdgeRecord] = []
    parent_present = fingerprint_eligible = depth_consistent = 0
    for child in sorted(snapshot.cards):
        child_row = snapshot.cards[child]
        parent = child_row["parent"]
        if parent not in snapshot.cards:
            continue
        parent_present += 1
        if child not in fingerprints or parent not in fingerprints:
            continue
        fingerprint_eligible += 1
        if snapshot.cards[parent]["depth"] + 1 != child_row["depth"]:
            continue
        depth_consistent += 1
        options = [
            candidate
            for candidate in by_run[child_row["run"]]
            if snapshot.cards[candidate]["depth"] == child_row["depth"] - 1
        ]
        require(parent in options, "recorded parent excluded from exact-depth candidates")
        if len(options) < 2:
            continue
        scores = sorted(
            ((jaccard(fingerprints[child], fingerprints[candidate]), candidate) for candidate in options),
            key=lambda item: (item[0], item[1]),
            reverse=True,
        )
        top_score = scores[0][0]
        top = [candidate for score, candidate in scores if score == top_score]
        second_score = scores[len(top)][0] if len(top) < len(scores) else top_score
        unique = len(top) == 1
        records.append(
            EdgeRecord(
                task=child_row["task"],
                run=child_row["run"],
                candidates=len(options),
                unique_top=unique,
                correct=unique and top[0] == parent,
                top_score=top_score,
                margin=top_score - second_score if unique else Fraction(0, 1),
            )
        )
    return records, {
        "parent_present_edges": parent_present,
        "fingerprint_eligible_parent_edges": fingerprint_eligible,
        "depth_consistent_fingerprint_eligible_parent_edges": depth_consistent,
        "ambiguous_exact_depth_edges": len(records),
    }


def select_threshold(rows: list[EdgeRecord], protocol: dict[str, Any]) -> dict[str, Any]:
    rule = protocol["confidence_rule"]
    target = Fraction(rule["train_precision_target"])
    minimum = rule["minimum_train_accepted_edges"]
    thresholds = sorted({row.margin for row in rows if row.unique_top and row.margin > 0})
    qualifying: list[tuple[int, Fraction, int]] = []
    for threshold in thresholds:
        accepted = [row for row in rows if row.unique_top and row.margin >= threshold]
        correct = sum(row.correct for row in accepted)
        if len(accepted) >= minimum and ratio(correct, len(accepted)) >= target:
            qualifying.append((len(accepted), threshold, correct))
    if not qualifying:
        return {
            "selected": False,
            "threshold": None,
            "candidate_thresholds": len(thresholds),
            "qualifying_thresholds": 0,
            "accepted_edges": 0,
            "correct_edges": 0,
            "precision": exact(Fraction(0, 1)),
        }
    accepted_count, threshold, correct_count = max(
        qualifying, key=lambda item: (item[0], -item[1])
    )
    return {
        "selected": True,
        "threshold": exact(threshold),
        "candidate_thresholds": len(thresholds),
        "qualifying_thresholds": len(qualifying),
        "accepted_edges": accepted_count,
        "correct_edges": correct_count,
        "precision": exact(ratio(correct_count, accepted_count)),
    }


def evaluate(rows: list[EdgeRecord], threshold: Fraction | None) -> dict[str, Any]:
    unfiltered = [row for row in rows if row.unique_top]
    selected = [
        row
        for row in rows
        if threshold is not None and row.unique_top and row.margin >= threshold
    ]
    unfiltered_correct = sum(row.correct for row in unfiltered)
    selected_correct = sum(row.correct for row in selected)
    return {
        "ambiguous_edges": len(rows),
        "unique_top_edges": len(unfiltered),
        "unfiltered_correct_edges": unfiltered_correct,
        "unfiltered_precision": exact(ratio(unfiltered_correct, len(unfiltered))),
        "unfiltered_coverage": exact(ratio(len(unfiltered), len(rows))),
        "selected_edges": len(selected),
        "selected_correct_edges": selected_correct,
        "selected_error_edges": len(selected) - selected_correct,
        "selected_precision": exact(ratio(selected_correct, len(selected))),
        "selected_coverage": exact(ratio(len(selected), len(rows))),
        "candidate_size_quantiles": {
            "median": int(nearest_rank([Fraction(row.candidates, 1) for row in rows], 1, 2)),
            "p90_nearest_rank": int(
                nearest_rank([Fraction(row.candidates, 1) for row in rows], 9, 10)
            ),
            "maximum": max(row.candidates for row in rows),
        },
        "unique_top_margin_quantiles": quantiles(
            [row.margin for row in rows if row.unique_top]
        ),
    }


def group_profile(
    selected: list[EdgeRecord],
    field: str,
    minimum: int,
    reference: Fraction,
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


def decode_exact(payload: dict[str, Any]) -> Fraction:
    return Fraction(payload["numerator"], payload["denominator"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--expect-protocol-sha256", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    require(SHA_RE.fullmatch(args.snapshot) is not None, "invalid snapshot SHA")
    require(SHA_RE.fullmatch(args.expect_protocol_sha256) is not None, "invalid protocol SHA")
    require(COMMIT_RE.fullmatch(args.source_commit) is not None, "invalid source commit")
    protocol, protocol_sha = read_protocol(
        args.protocol, args.expect_protocol_sha256, args.repo_root
    )
    require(args.snapshot == protocol["freeze_state"]["snapshot_sha256"], "snapshot mismatch")
    snapshot = snapshot_impl.load_blind_snapshot(args.state_root, args.snapshot)
    immutable = protocol["immutable_inputs"]
    require(
        snapshot.bindings["accumulator_summary_sha256"]
        == immutable["accumulator_summary_sha256"],
        "summary binding mismatch",
    )
    require(snapshot.bindings["registry_sha256"] == immutable["intake_registry_sha256"], "registry binding mismatch")
    require(
        snapshot.bindings["provisional_runs_sha256"] == immutable["provisional_runs_sha256"],
        "run-ledger binding mismatch",
    )
    split = protocol["run_disjoint_split"]
    run_order = list(snapshot.runs)
    require(len(run_order) == split["train_runs"] + split["test_runs"], "run split size mismatch")
    train_runs = set(run_order[: split["train_runs"]])
    test_runs = set(run_order[split["train_runs"] :])
    require(not train_runs.intersection(test_runs), "run split overlap")

    fingerprints, by_run = fingerprint_population(snapshot)
    records, inventory = edge_records(snapshot, fingerprints, by_run)
    train = [row for row in records if row.run in train_runs]
    test = [row for row in records if row.run in test_runs]
    require(len(train) + len(test) == len(records), "edge split accounting mismatch")
    selection = select_threshold(train, protocol)
    threshold = decode_exact(selection["threshold"]) if selection["selected"] else None
    train_profile = evaluate(train, threshold)
    test_profile = evaluate(test, threshold)
    selected_test = [
        row
        for row in test
        if threshold is not None and row.unique_top and row.margin >= threshold
    ]
    gates = protocol["primary_gates"]
    task_profile = group_profile(
        selected_test,
        "task",
        gates["task_minimum_accepted_edges"],
        Fraction(gates["task_precision_reference"]),
    )
    run_profile = group_profile(
        selected_test,
        "run",
        gates["run_minimum_accepted_edges"],
        Fraction(gates["run_precision_reference"]),
    )

    confident_wrong = sum(not row.correct for row in selected_test)
    wrong_alternatives = sum(row.candidates - 1 for row in test)
    uniform_wrong = sum(
        (
            Fraction(1, row.candidates - 1)
            if threshold is not None
            and row.unique_top
            and row.margin >= threshold
            and not row.correct
            else Fraction(0, 1)
        )
        for row in test
    )
    wrong_controls = {
        "confident_wrong_unique_top_children": confident_wrong,
        "all_wrong_alternatives": wrong_alternatives,
        "all_wrong_alternative_micro_false_acceptance": exact(
            ratio(confident_wrong, wrong_alternatives)
        ),
        "uniform_one_wrong_substitution_per_child_expected_false_acceptance": exact(
            uniform_wrong / len(test)
        ),
        "child_level_adversarial_vulnerability": exact(ratio(confident_wrong, len(test))),
        "denominators_are_not_interchangeable": True,
    }

    hard = protocol["hard_support"]
    support_gates = {
        "threshold_selected": bool(selection["selected"]),
        "train_ambiguous_edges": len(train) >= hard["minimum_train_ambiguous_edges"],
        "test_ambiguous_edges": len(test) >= hard["minimum_test_ambiguous_edges"],
        "test_accepted_edges": len(selected_test) >= hard["minimum_test_accepted_edges"],
        "conditionable_test_tasks": task_profile["conditionable_groups"]
        >= hard["minimum_conditionable_test_tasks"],
        "conditionable_test_runs": run_profile["conditionable_groups"]
        >= hard["minimum_conditionable_test_runs"],
    }
    selected_precision = decode_exact(test_profile["selected_precision"])
    selected_coverage = decode_exact(test_profile["selected_coverage"])
    unfiltered_error = Fraction(1, 1) - decode_exact(test_profile["unfiltered_precision"])
    selected_error = Fraction(1, 1) - selected_precision
    primary_gates = {
        "test_precision": selected_precision >= Fraction(gates["minimum_test_precision"]),
        "test_coverage": selected_coverage >= Fraction(gates["minimum_test_coverage"]),
        "selective_error_reduction": selected_error
        <= Fraction(gates["maximum_selective_error_relative_to_unfiltered_unique_top_error"])
        * unfiltered_error,
        "task_breadth": decode_exact(task_profile["fraction_at_or_above_reference"])
        >= Fraction(gates["minimum_task_fraction_at_reference"]),
        "task_anti_dominance": decode_exact(task_profile["maximum_accepted_contribution_share"])
        <= Fraction(gates["maximum_single_task_accepted_contribution_share"]),
        "run_breadth": decode_exact(run_profile["fraction_at_or_above_reference"])
        >= Fraction(gates["minimum_run_fraction_at_reference"]),
        "run_anti_dominance": decode_exact(run_profile["maximum_accepted_contribution_share"])
        <= Fraction(gates["maximum_single_run_accepted_contribution_share"]),
    }
    if all(support_gates.values()) and all(primary_gates.values()):
        classification = "DEVELOPMENT_TIME_SPLIT_HIGH_PRECISION_SELECTIVE_PARENT_RECOVERY"
    elif (
        selection["selected"]
        and support_gates["train_ambiguous_edges"]
        and support_gates["test_ambiguous_edges"]
        and support_gates["conditionable_test_tasks"]
        and support_gates["conditionable_test_runs"]
        and primary_gates["test_precision"]
    ):
        classification = "DEVELOPMENT_TIME_SPLIT_PRECISION_ONLY_LOW_COVERAGE"
    else:
        classification = "DEVELOPMENT_TIME_SPLIT_SELECTIVE_RECOVERY_BELOW_GATE"

    train_raw = b"".join(snapshot.run_raw_rows[run] for run in run_order[: split["train_runs"]])
    test_raw = b"".join(snapshot.run_raw_rows[run] for run in run_order[split["train_runs"] :])
    result = {
        "protocol": PROTOCOL,
        "status": RESULT_STATUS,
        "classification": classification,
        "source_commit": args.source_commit,
        "protocol_sha256": protocol_sha,
        "snapshot_bindings": snapshot.bindings,
        "split_bindings": {
            "train_runs": len(train_runs),
            "test_runs": len(test_runs),
            "run_overlap": 0,
            "train_run_rows_sha256": sha256_bytes(train_raw),
            "test_run_rows_sha256": sha256_bytes(test_raw),
            "identities_emitted": False,
        },
        "inventory": {
            **inventory,
            "fingerprinted_endpoints": len(fingerprints),
            "fingerprint_coverage": exact(ratio(len(fingerprints), len(snapshot.cards))),
            "train_ambiguous_edges": len(train),
            "test_ambiguous_edges": len(test),
        },
        "threshold_selection": selection,
        "train_profile": train_profile,
        "test_profile": test_profile,
        "test_breadth": {"task": task_profile, "physical_run": run_profile},
        "test_wrong_pointer_controls": wrong_controls,
        "support_gates": support_gates,
        "primary_gates": primary_gates,
        "claim_boundary": protocol["claim_boundary"],
        "security": {
            "task_run_card_parent_code_or_per_edge_values_emitted": False,
            "prospective_label_grade_outcome_prediction_values_read": False,
            "raw_senior_archives_opened": False,
            "gpu_api_model_fit_base_update": [0, 0, 0, 0],
        },
    }
    require(not args.output.exists(), "refusing to overwrite output")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
