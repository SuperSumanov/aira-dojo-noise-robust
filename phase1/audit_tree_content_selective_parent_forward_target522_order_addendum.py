#!/usr/bin/env python3
"""Prospective Target-522 max-prior-step falsification addendum.

This producer is intentionally aggregate-only.  It activates only after the
already-fixed Target-522 selection and selective-parent formal outputs are
complete, and it cannot rescue a failed upstream primary result.
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
from typing import Any, Callable

from phase1 import audit_prospective_fuzzy_code_clones as fingerprint_impl
from phase1 import audit_tree_content_selective_parent_forward_target522 as upstream_impl
from phase1 import audit_tree_within_stratum_forward_target522 as snapshot_impl


PROTOCOL_NAME = "tree-content-selective-parent-forward-target522-order-addendum-v1"
PROTOCOL_STATUS = (
    "OUTCOME_BLIND_FROZEN_AFTER_DEVELOPMENT_ORDER_READOUT_BEFORE_TARGET522_CANDIDATE"
)
PROTOCOL_SHA256 = "81df44e9194fb194611d6ffb7f3fba6c0a3fd1d7d2c0aa1ba6be19d33f84ce87"
RECEIPT_PROTOCOL = "tree-content-selective-parent-forward-target522-order-addendum-receipt-v1"
RECEIPT_STATUS = "OUTCOME_BLIND_FORWARD_ORDER_BASELINE_ADDENDUM_COMPLETE"
COMMIT_RE = re.compile(r"[0-9a-f]{40}")
MANIFEST_RE = re.compile(r"([0-9a-f]{64}) [ *](.+)")


class ForwardOrderAddendumError(RuntimeError):
    """Raised when a frozen dependency, selection, or formal binding drifts."""


@dataclass(frozen=True)
class PairedRow:
    task: str
    run: str
    parent: str
    candidates: int
    content_prediction: str | None
    content_margin: Fraction
    step_prediction: str | None


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ForwardOrderAddendumError(message)


def sha256_file(path: Path) -> str:
    require(path.is_file() and not path.is_symlink(), f"unsafe file: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def read_object(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"unsafe object: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"object required: {path}")
    return value


def exact(value: Fraction) -> dict[str, Any]:
    return {
        "numerator": value.numerator,
        "denominator": value.denominator,
        "decimal_17g": format(float(value), ".17g"),
    }


def ratio(part: int, whole: int) -> Fraction:
    return Fraction(part, whole) if whole else Fraction(0, 1)


def optional_ratio(part: int, whole: int) -> dict[str, Any] | None:
    return exact(Fraction(part, whole)) if whole else None


def safe_repo_member(repo: Path, relative: str, *, directory: bool = False) -> Path:
    part = Path(relative)
    require(not part.is_absolute() and ".." not in part.parts, f"unsafe path: {relative}")
    raw = repo / part
    require(not raw.is_symlink(), f"symlink input: {relative}")
    resolved = raw.resolve()
    require(resolved.is_relative_to(repo), f"path escapes repository: {relative}")
    require(resolved.is_dir() if directory else resolved.is_file(), f"missing input: {relative}")
    return resolved


def verify_manifest(root: Path, filename: str = "SHA256SUMS") -> tuple[str, int]:
    require(root.is_dir() and not root.is_symlink(), f"unsafe formal root: {root}")
    manifest = root / filename
    require(manifest.is_file() and not manifest.is_symlink(), "formal manifest missing")
    members: dict[str, str] = {}
    for number, line in enumerate(manifest.read_text(encoding="utf-8").splitlines(), 1):
        match = MANIFEST_RE.fullmatch(line)
        require(match is not None, f"malformed manifest line {number}")
        digest, raw_name = match.groups()
        name = raw_name.removeprefix("./")
        part = Path(name)
        require(name and not part.is_absolute() and ".." not in part.parts, "unsafe member")
        require(name not in members and name not in {filename, "COMPLETE"}, "duplicate member")
        member = root / part
        require(member.is_file() and not member.is_symlink(), f"missing member: {name}")
        require(sha256_file(member) == digest, f"manifest hash drift: {name}")
        members[name] = digest
    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.name not in {filename, "COMPLETE"}
    }
    require(set(members) == actual, "formal manifest membership drift")
    require((root / "COMPLETE").is_file(), "formal COMPLETE missing")
    require(not (root / "FAILED_RC").exists(), "formal FAILED_RC present")
    return sha256_file(manifest), len(members)


def verify_development_evidence(repo: Path, protocol: dict[str, Any]) -> dict[str, Any]:
    binding = protocol["known_development_evidence"]
    root = safe_repo_member(repo, binding["package_root"], directory=True)
    manifest = root / binding["package_manifest"]
    require(sha256_file(manifest) == binding["package_manifest_sha256"], "development manifest")
    result_path = root / binding["formal_result"]
    verifier_path = root / binding["independent_verification"]
    require(sha256_file(result_path) == binding["formal_result_sha256"], "development result")
    require(
        sha256_file(verifier_path) == binding["independent_verification_sha256"],
        "development verifier",
    )
    result = read_object(result_path)
    verification = read_object(verifier_path)
    require(result["classification"] == binding["formal_classification"], "development class")
    step = result["selected_population_primary_comparisons"]["max_prior_step"]
    require(
        (
            step["comparable_rows"],
            step["content_errors"],
            step["order_errors"],
            step["paired_correctness"]["content_only_correct"],
            step["paired_correctness"]["order_only_correct"],
        )
        == (
            binding["development_selected_rows"],
            binding["development_content_errors"],
            binding["development_max_prior_step_errors"],
            binding["development_content_only_correct"],
            binding["development_step_only_correct"],
        ),
        "development step evidence drift",
    )
    require(verification.get("all_aggregate_fields_equal") is True, "development verifier")
    require(verification.get("producer_imported") is False, "development independence")
    return {
        "package_manifest_sha256": binding["package_manifest_sha256"],
        "formal_result_sha256": binding["formal_result_sha256"],
        "independent_verification_sha256": binding["independent_verification_sha256"],
        "formal_classification": binding["formal_classification"],
        "valid_control": binding["valid_control"],
        "development_result_is_post_result_falsification": True,
    }


def load_protocol(path: Path, expected_sha: str, repo: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    actual = sha256_file(path)
    require(actual == expected_sha == PROTOCOL_SHA256, "protocol SHA drift")
    protocol = read_object(path)
    require(protocol.get("protocol") == PROTOCOL_NAME, "protocol identity")
    require(protocol.get("status") == PROTOCOL_STATUS, "protocol status")
    freeze = protocol["freeze_state"]
    unseen = (
        "target522_selection_complete_present",
        "target522_candidate_seen",
        "target522_increment_profile_seen",
        "target522_content_result_seen",
        "target522_max_prior_step_values_seen",
        "target522_paired_disagreement_seen",
        "target522_task_or_run_disagreement_breadth_seen",
    )
    require(all(freeze[name] is False for name in unseen), "future readout seen at freeze")
    upstream = protocol["upstream_target522_contract"]
    for role in ("selection_protocol", "selection_monitor", "selective_protocol", "selective_producer", "selective_verifier"):
        member = safe_repo_member(repo, upstream[role])
        require(sha256_file(member) == upstream[f"{role}_sha256"], f"upstream drift: {role}")
    for role, binding in protocol["immutable_helpers"].items():
        member = safe_repo_member(repo, binding["path"])
        require(sha256_file(member) == binding["sha256"], f"helper drift: {role}")
    security = protocol["security"]
    require(security["prospective_first960_or_target300_values_read"] is False, "prospective boundary")
    require(security["target522_candidate_or_profile_read_before_freeze"] is False, "Target-522 boundary")
    require(security["raw_senior_archives_opened"] is False, "raw archive boundary")
    require(security["task_run_card_parent_code_or_per_edge_values_emitted"] is False, "identity boundary")
    require(security["gpu_api_model_fit_base_update"] == [0, 0, 0, 0], "resource boundary")
    return protocol, verify_development_evidence(repo, protocol)


def unique_maximum(candidates: list[str], key: Callable[[str], int]) -> str | None:
    if not candidates:
        return None
    maximum = max(key(candidate) for candidate in candidates)
    winners = [candidate for candidate in candidates if key(candidate) == maximum]
    return winners[0] if len(winners) == 1 else None


def jaccard(left: frozenset[int], right: frozenset[int]) -> Fraction:
    overlap = len(left & right)
    union = len(left) + len(right) - overlap
    require(union > 0, "empty fingerprint union")
    return Fraction(overlap, union)


def build_rows(
    cards: dict[str, dict[str, Any]], payloads: dict[str, dict[str, Any]]
) -> tuple[list[PairedRow], dict[str, int]]:
    steps: dict[str, int] = {}
    fingerprints: dict[str, frozenset[int]] = {}
    by_run: dict[str, list[str]] = collections.defaultdict(list)
    for identity in sorted(cards):
        lineage = payloads[identity].get("lineage")
        require(isinstance(lineage, dict), "lineage object missing")
        step = lineage.get("step")
        require(isinstance(step, int) and not isinstance(step, bool), "integer step required")
        steps[identity] = step
        code = payloads[identity].get("code")
        require(isinstance(code, str), "code string required")
        fingerprint = fingerprint_impl.identifier_erased_token_shingles(code)
        if fingerprint is not None:
            fingerprints[identity] = fingerprint
            by_run[cards[identity]["run"]].append(identity)

    rows: list[PairedRow] = []
    parent_present = fingerprint_eligible = depth_consistent = parent_not_prior_step = 0
    for child in sorted(cards):
        child_meta = cards[child]
        parent = child_meta["parent"]
        if parent not in cards:
            continue
        parent_present += 1
        parent_not_prior_step += not steps[parent] < steps[child]
        if child not in fingerprints or parent not in fingerprints:
            continue
        fingerprint_eligible += 1
        if cards[parent]["depth"] + 1 != child_meta["depth"]:
            continue
        depth_consistent += 1
        options = sorted(
            candidate
            for candidate in by_run.get(child_meta["run"], [])
            if cards[candidate]["depth"] == child_meta["depth"] - 1
        )
        require(parent in options, "recorded parent excluded from candidate set")
        if len(options) < 2:
            continue
        scores = {
            candidate: jaccard(fingerprints[child], fingerprints[candidate])
            for candidate in options
        }
        ordered = sorted(scores.values(), reverse=True)
        top, second = ordered[0], ordered[1]
        content_winners = [candidate for candidate in options if scores[candidate] == top]
        content_prediction = content_winners[0] if len(content_winners) == 1 else None
        margin = top - second if content_prediction is not None else Fraction(0, 1)
        prior = [candidate for candidate in options if steps[candidate] < steps[child]]
        step_prediction = unique_maximum(prior, steps.__getitem__)
        rows.append(
            PairedRow(
                task=child_meta["task"],
                run=child_meta["run"],
                parent=parent,
                candidates=len(options),
                content_prediction=content_prediction,
                content_margin=margin,
                step_prediction=step_prediction,
            )
        )
    return rows, {
        "parent_present_edges": parent_present,
        "fingerprint_eligible_parent_edges": fingerprint_eligible,
        "depth_consistent_fingerprint_eligible_parent_edges": depth_consistent,
        "depth_inconsistent_fingerprint_eligible_parent_edges": fingerprint_eligible - depth_consistent,
        "ambiguous_exact_depth_edges": len(rows),
        "recorded_parent_not_prior_step": parent_not_prior_step,
        "fingerprinted_endpoints": len(fingerprints),
    }


def paired_profile(rows: list[PairedRow]) -> tuple[dict[str, Any], list[PairedRow]]:
    common = [row for row in rows if row.step_prediction is not None]
    content_correct = sum(row.content_prediction == row.parent for row in common)
    step_correct = sum(row.step_prediction == row.parent for row in common)
    both = sum(
        row.content_prediction == row.parent and row.step_prediction == row.parent
        for row in common
    )
    content_only = sum(
        row.content_prediction == row.parent and row.step_prediction != row.parent
        for row in common
    )
    step_only = sum(
        row.content_prediction != row.parent and row.step_prediction == row.parent
        for row in common
    )
    neither = len(common) - both - content_only - step_only
    content_errors = len(common) - content_correct
    step_errors = len(common) - step_correct
    require(content_correct == both + content_only, "content paired accounting")
    require(step_correct == both + step_only, "step paired accounting")
    return {
        "content_selected_rows": len(rows),
        "comparable_rows": len(common),
        "comparable_coverage": exact(ratio(len(common), len(rows))),
        "content_correct": content_correct,
        "content_errors": content_errors,
        "step_correct": step_correct,
        "step_errors": step_errors,
        "paired_correctness": {
            "both_correct": both,
            "both_wrong": neither,
            "content_only_correct": content_only,
            "step_only_correct": step_only,
        },
        "content_to_step_error_ratio": optional_ratio(content_errors, step_errors),
        "content_only_to_step_only_win_ratio": optional_ratio(content_only, step_only),
    }, common


def raw_step_profile(rows: list[PairedRow]) -> dict[str, Any]:
    predicted = [row for row in rows if row.step_prediction is not None]
    correct = sum(row.step_prediction == row.parent for row in predicted)
    return {
        "rows": len(rows),
        "predicted_rows": len(predicted),
        "coverage": exact(ratio(len(predicted), len(rows))),
        "correct": correct,
        "errors": len(predicted) - correct,
        "precision": exact(ratio(correct, len(predicted))),
    }


def anonymous_breadth(
    rows: list[PairedRow], attribute: str, minimum: int
) -> dict[str, Any]:
    discordant = [
        row
        for row in rows
        if (row.content_prediction == row.parent) != (row.step_prediction == row.parent)
    ]
    grouped: dict[str, list[PairedRow]] = collections.defaultdict(list)
    for row in discordant:
        grouped[getattr(row, attribute)].append(row)
    supported = [group for group in grouped.values() if len(group) >= minimum]
    net_positive = 0
    for group in supported:
        content_wins = sum(
            row.content_prediction == row.parent and row.step_prediction != row.parent
            for row in group
        )
        net_positive += content_wins > len(group) - content_wins
    sizes = [len(group) for group in grouped.values()]
    return {
        "discordant_rows": len(discordant),
        "conditionable_groups": len(supported),
        "fraction_net_content_positive": exact(ratio(net_positive, len(supported))),
        "maximum_discordance_contribution_share": exact(
            ratio(max(sizes, default=0), sum(sizes))
        ),
        "identities_emitted": False,
    }


def decisions(
    protocol: dict[str, Any],
    upstream_classification: str,
    integrity: dict[str, bool],
    selected_rows: int,
    paired: dict[str, Any],
    task: dict[str, Any],
    run: dict[str, Any],
) -> tuple[str, dict[str, bool], dict[str, bool], dict[str, bool]]:
    support_rule = protocol["hard_support"]
    aggregate_rule = protocol["aggregate_advantage_gates"]
    breadth_rule = protocol["breadth_gates"]
    coverage = Fraction(
        paired["comparable_coverage"]["numerator"],
        paired["comparable_coverage"]["denominator"],
    )
    support = {
        "minimum_content_selected_rows": selected_rows >= support_rule["minimum_content_selected_rows"],
        "minimum_comparable_rows": paired["comparable_rows"] >= support_rule["minimum_comparable_rows"],
        "minimum_comparable_coverage": coverage >= Fraction(support_rule["minimum_comparable_coverage"]),
    }
    content_only = paired["paired_correctness"]["content_only_correct"]
    step_only = paired["paired_correctness"]["step_only_correct"]
    aggregate = {
        "step_errors_nonzero": paired["step_errors"] > 0,
        "content_error_at_most_half_step_error": (
            paired["step_errors"] > 0
            and Fraction(paired["content_errors"], paired["step_errors"])
            <= Fraction(aggregate_rule["maximum_content_to_step_error_ratio"])
        ),
        "content_only_wins_at_least_twice_step_only_wins": (
            (step_only == 0 and content_only > 0)
            or (
                step_only > 0
                and Fraction(content_only, step_only)
                >= Fraction(aggregate_rule["minimum_content_only_to_step_only_win_ratio"])
            )
        ),
    }
    task_fraction = Fraction(
        task["fraction_net_content_positive"]["numerator"],
        task["fraction_net_content_positive"]["denominator"],
    )
    run_fraction = Fraction(
        run["fraction_net_content_positive"]["numerator"],
        run["fraction_net_content_positive"]["denominator"],
    )
    task_share = Fraction(
        task["maximum_discordance_contribution_share"]["numerator"],
        task["maximum_discordance_contribution_share"]["denominator"],
    )
    run_share = Fraction(
        run["maximum_discordance_contribution_share"]["numerator"],
        run["maximum_discordance_contribution_share"]["denominator"],
    )
    breadth = {
        "minimum_conditionable_tasks": task["conditionable_groups"]
        >= support_rule["minimum_conditionable_tasks_for_strong_breadth"],
        "minimum_conditionable_runs": run["conditionable_groups"]
        >= support_rule["minimum_conditionable_runs_for_strong_breadth"],
        "task_net_content_positive_fraction": task_fraction
        >= Fraction(
            breadth_rule["minimum_task_fraction_with_more_content_only_than_step_only_wins"]
        ),
        "run_net_content_positive_fraction": run_fraction
        >= Fraction(
            breadth_rule["minimum_run_fraction_with_more_content_only_than_step_only_wins"]
        ),
        "task_disagreement_anti_dominance": task_share
        <= Fraction(breadth_rule["maximum_single_task_discordance_contribution_share"]),
        "run_disagreement_anti_dominance": run_share
        <= Fraction(breadth_rule["maximum_single_run_discordance_contribution_share"]),
    }
    required_upstream = protocol["upstream_target522_contract"][
        "required_upstream_classification_for_positive_addendum"
    ]
    if not all(integrity.values()):
        classification = "FORWARD_ORDER_BASELINE_ADDENDUM_INTEGRITY_FAIL"
    elif upstream_classification != required_upstream:
        classification = "FORWARD_SELECTIVE_PARENT_PRIMARY_NOT_CONFIRMED"
    elif not all(support.values()):
        classification = "FORWARD_ORDER_BASELINE_SUPPORT_INSUFFICIENT"
    elif all(aggregate.values()) and all(breadth.values()):
        classification = "FORWARD_CONTENT_ADDS_BROADLY_BEYOND_MAX_PRIOR_STEP"
    elif all(aggregate.values()):
        classification = "FORWARD_CONTENT_ADDS_AGGREGATELY_BUT_BREADTH_UNSUPPORTED"
    else:
        classification = "FORWARD_MAX_PRIOR_STEP_NOT_RULED_OUT"
    require(classification in protocol["ordered_classification"], "classification outside protocol")
    return classification, support, aggregate, breadth


def build_receipt(
    state_root: Path,
    selection_root: Path,
    repo_root: Path,
    protocol_path: Path,
    protocol_sha: str,
    source_commit: str,
) -> dict[str, Any]:
    require(COMMIT_RE.fullmatch(source_commit) is not None, "source commit syntax")
    repo = repo_root.resolve()
    protocol, development = load_protocol(protocol_path, protocol_sha, repo)
    upstream_contract = protocol["upstream_target522_contract"]
    require(str(selection_root) == upstream_contract["selection_root"], "selection root differs")
    upstream_root = Path(upstream_contract["selective_formal_root"])
    upstream_manifest_sha, upstream_manifest_members = verify_manifest(upstream_root)
    upstream_receipt_path = upstream_root / "producer_a.json"
    upstream_verifier_path = upstream_root / "verifier_a.json"
    upstream_receipt = read_object(upstream_receipt_path)
    upstream_verification = read_object(upstream_verifier_path)
    require(
        upstream_receipt.get("analysis_source_commit") == upstream_contract["selective_source_commit"],
        "upstream source commit",
    )
    require(
        upstream_receipt.get("protocol_sha256") == upstream_contract["selective_protocol_sha256"],
        "upstream protocol binding",
    )
    require(upstream_verification.get("producer_imported") is False, "upstream verifier independence")
    require(
        upstream_verification.get("classification") == upstream_receipt.get("classification"),
        "upstream classification disagreement",
    )
    recomputed_upstream = upstream_impl.build_receipt(
        state_root,
        selection_root,
        repo,
        repo / upstream_contract["selective_protocol"],
        upstream_contract["selective_protocol_sha256"],
        upstream_contract["selective_source_commit"],
    )
    require(recomputed_upstream == upstream_receipt, "upstream receipt rebuild mismatch")

    selection_protocol, selection_protocol_sha = snapshot_impl.load_protocol(
        repo / upstream_contract["selection_protocol"],
        upstream_contract["selection_protocol_sha256"],
    )
    selection = snapshot_impl.verify_selection(
        selection_root, repo, selection_protocol, selection_protocol_sha
    )
    require(
        selection["selection_monitor_source_sha256"]
        == upstream_contract["selection_monitor_sha256"],
        "selection monitor binding",
    )
    baseline = snapshot_impl.load_blind_snapshot(
        state_root, selection["baseline_snapshot_sha256"]
    )
    candidate = snapshot_impl.load_blind_snapshot(
        state_root, selection["candidate_snapshot_sha256"]
    )
    cards, increment_runs, append_only = snapshot_impl.disjoint_increment(
        baseline, candidate, selection_protocol
    )
    payloads = {identity: candidate.card_payloads[identity] for identity in cards}
    rows, inventory = build_rows(cards, payloads)
    threshold = Fraction(protocol["fixed_content_rule"]["threshold"])
    selected = [
        row
        for row in rows
        if row.content_prediction is not None and row.content_margin >= threshold
    ]
    selected_correct = sum(row.content_prediction == row.parent for row in selected)
    upstream_profile = upstream_receipt["forward_profile"]
    content_profile_exact = (
        len(rows) == upstream_profile["ambiguous_edges"]
        and len(selected) == upstream_profile["selected_edges"]
        and selected_correct == upstream_profile["selected_correct_edges"]
        and len(selected) - selected_correct == upstream_profile["selected_error_edges"]
    )
    paired, comparable = paired_profile(selected)
    task = anonymous_breadth(
        comparable,
        "task",
        protocol["hard_support"]["task_minimum_discordant_rows"],
    )
    run = anonymous_breadth(
        comparable,
        "run",
        protocol["hard_support"]["run_minimum_discordant_rows"],
    )
    inventory_exact = (
        inventory["ambiguous_exact_depth_edges"]
        == upstream_receipt["inventory"]["ambiguous_exact_depth_edges"]
        and inventory["parent_present_edges"]
        == upstream_receipt["inventory"]["parent_present_edges"]
        and inventory["fingerprint_eligible_parent_edges"]
        == upstream_receipt["inventory"]["fingerprint_eligible_parent_edges"]
        and inventory["depth_consistent_fingerprint_eligible_parent_edges"]
        == upstream_receipt["inventory"]["depth_consistent_fingerprint_eligible_parent_edges"]
    )
    integrity = {
        **selection["checks"],
        "complete_hash_bound_upstream_selective_formal": True,
        "candidate_and_baseline_append_only_contract_exact": all(
            value is True for value in append_only.values() if isinstance(value, bool)
        ),
        "fixed_content_profile_exactly_matches_upstream_formal": content_profile_exact,
        "recorded_parent_strictly_precedes_child_step_for_every_parent_present_increment_edge": inventory[
            "recorded_parent_not_prior_step"
        ]
        == 0,
        "candidate_set_content_threshold_and_step_rule_unchanged": inventory_exact,
        "aggregate_only_output_without_identities": True,
    }
    classification, support, aggregate, breadth = decisions(
        protocol,
        upstream_receipt["classification"],
        integrity,
        len(selected),
        paired,
        task,
        run,
    )
    return {
        "protocol": RECEIPT_PROTOCOL,
        "status": RECEIPT_STATUS,
        "classification": classification,
        "protocol_sha256": protocol_sha,
        "analysis_source_commit": source_commit,
        "producer_source_sha256": sha256_file(Path(__file__)),
        "known_development_evidence": development,
        "upstream_target522_binding": {
            "source_commit": upstream_contract["selective_source_commit"],
            "formal_root": upstream_contract["selective_formal_root"],
            "formal_manifest_sha256": upstream_manifest_sha,
            "formal_manifest_members": upstream_manifest_members,
            "receipt_sha256": sha256_file(upstream_receipt_path),
            "independent_verification_sha256": sha256_file(upstream_verifier_path),
            "classification": upstream_receipt["classification"],
            "receipt_rebuilt_exactly": True,
        },
        "snapshot_bindings": {
            "baseline": baseline.bindings,
            "candidate": candidate.bindings,
            "selection_support": {
                "sha256sums_sha256": selection["selection_support_sha256sums_sha256"],
                "selection_protocol_sha256": selection_protocol_sha,
                "monitor_source_sha256": selection["selection_monitor_source_sha256"],
            },
        },
        "append_only_and_increment": append_only,
        "inventory": {
            "increment_endpoints": len(cards),
            "increment_physical_runs": len(increment_runs),
            "increment_tasks": len({row["task"] for row in cards.values()}),
            **inventory,
        },
        "fixed_content_rule": {
            **protocol["fixed_content_rule"],
            "threshold_exact": exact(threshold),
            "selected_rows": len(selected),
            "selected_correct": selected_correct,
            "selected_errors": len(selected) - selected_correct,
            "matches_upstream_formal": content_profile_exact,
        },
        "selected_population_paired_comparison": paired,
        "all_ambiguous_max_prior_step_supplementary": raw_step_profile(rows),
        "anonymous_disagreement_breadth": {"task": task, "physical_run": run},
        "pre_registered_gate": {
            "integrity": integrity,
            "upstream_primary_confirmed": upstream_receipt["classification"]
            == upstream_contract["required_upstream_classification_for_positive_addendum"],
            "support": support,
            "aggregate_advantage": aggregate,
            "breadth": breadth,
            "fixed_thresholds": {
                "support": protocol["hard_support"],
                "aggregate_advantage": protocol["aggregate_advantage_gates"],
                "breadth": protocol["breadth_gates"],
            },
        },
        "claim_boundary": protocol["claim_boundary"],
        "security": {
            "prospective_first960_or_target300_values_read": False,
            "raw_senior_archives_opened": False,
            "task_run_card_parent_code_or_per_edge_values_emitted": False,
            "predictor_accuracy_effect_scaling_or_search_utility_computed": False,
            "row_level_release_created": False,
            "gpu_api_model_fit_base_update": [0, 0, 0, 0],
        },
        "reproducibility": {
            "randomness_used": False,
            "decimal_values_used_for_gates": False,
            "upstream_receipt_rebuilt_before_addendum": True,
        },
    }


def write_once(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
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
    except (ForwardOrderAddendumError, snapshot_impl.ForwardAuditError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
