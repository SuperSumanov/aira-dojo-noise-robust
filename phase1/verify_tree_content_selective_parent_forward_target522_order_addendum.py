#!/usr/bin/env python3
"""Independent verifier for the Target-522 order-baseline addendum.

This module does not import the addendum producer.  It uses the independent
selection, snapshot, fingerprint, and upstream selective-parent verifier stack.
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

from phase1 import verify_prospective_fuzzy_code_clones as fingerprint_check
from phase1 import verify_tree_content_lineage_forward_target522 as content_check
from phase1 import verify_tree_content_selective_parent_forward_target522 as upstream_check
from phase1 import verify_tree_within_stratum_forward_target522 as snapshot_check


PROTOCOL_NAME = "tree-content-selective-parent-forward-target522-order-addendum-v1"
PROTOCOL_STATUS = (
    "OUTCOME_BLIND_FROZEN_AFTER_DEVELOPMENT_ORDER_READOUT_BEFORE_TARGET522_CANDIDATE"
)
PROTOCOL_SHA256 = "81df44e9194fb194611d6ffb7f3fba6c0a3fd1d7d2c0aa1ba6be19d33f84ce87"
RECEIPT_PROTOCOL = "tree-content-selective-parent-forward-target522-order-addendum-receipt-v1"
RECEIPT_STATUS = "OUTCOME_BLIND_FORWARD_ORDER_BASELINE_ADDENDUM_COMPLETE"
COMMIT_RE = re.compile(r"[0-9a-f]{40}")
MANIFEST_RE = re.compile(r"([0-9a-f]{64}) [ *](.+)")


class ForwardOrderAddendumVerificationError(RuntimeError):
    """Raised when independent reconstruction differs or a binding drifts."""


@dataclass(frozen=True)
class IndependentRow:
    task: str
    run: str
    parent: str
    candidates: int
    content: str | None
    margin: Fraction
    step: str | None


def check(condition: bool, message: str) -> None:
    if not condition:
        raise ForwardOrderAddendumVerificationError(message)


def digest_file(path: Path) -> str:
    check(path.is_file() and not path.is_symlink(), f"unsafe file: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1 << 20):
            digest.update(block)
    return digest.hexdigest()


def object_file(path: Path) -> dict[str, Any]:
    check(path.is_file() and not path.is_symlink(), f"unsafe object: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    check(isinstance(value, dict), f"object required: {path}")
    return value


def encode(value: Fraction) -> dict[str, Any]:
    return {
        "numerator": value.numerator,
        "denominator": value.denominator,
        "decimal_17g": format(float(value), ".17g"),
    }


def quotient(part: int, whole: int) -> Fraction:
    return Fraction(part, whole) if whole else Fraction(0, 1)


def optional_quotient(part: int, whole: int) -> dict[str, Any] | None:
    return encode(Fraction(part, whole)) if whole else None


def repository_member(repo: Path, relative: str, *, directory: bool = False) -> Path:
    part = Path(relative)
    check(not part.is_absolute() and ".." not in part.parts, f"unsafe path: {relative}")
    raw = repo / part
    check(not raw.is_symlink(), f"symlink input: {relative}")
    resolved = raw.resolve()
    check(resolved.is_relative_to(repo), f"path escapes repository: {relative}")
    check(resolved.is_dir() if directory else resolved.is_file(), f"missing input: {relative}")
    return resolved


def manifest_receipt(root: Path, filename: str = "SHA256SUMS") -> tuple[str, int]:
    check(root.is_dir() and not root.is_symlink(), f"unsafe formal root: {root}")
    manifest = root / filename
    check(manifest.is_file() and not manifest.is_symlink(), "formal manifest missing")
    members: dict[str, str] = {}
    for number, line in enumerate(manifest.read_text(encoding="utf-8").splitlines(), 1):
        match = MANIFEST_RE.fullmatch(line)
        check(match is not None, f"manifest syntax line {number}")
        expected, raw_name = match.groups()
        name = raw_name.removeprefix("./")
        part = Path(name)
        check(name and not part.is_absolute() and ".." not in part.parts, "unsafe member")
        check(name not in members and name not in {filename, "COMPLETE"}, "duplicate member")
        member = root / part
        check(member.is_file() and not member.is_symlink(), f"missing member: {name}")
        check(digest_file(member) == expected, f"member digest: {name}")
        members[name] = expected
    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.name not in {filename, "COMPLETE"}
    }
    check(set(members) == actual, "formal manifest membership")
    check((root / "COMPLETE").is_file(), "formal COMPLETE missing")
    check(not (root / "FAILED_RC").exists(), "formal FAILED_RC present")
    return digest_file(manifest), len(members)


def development_evidence(repo: Path, protocol: dict[str, Any]) -> dict[str, Any]:
    binding = protocol["known_development_evidence"]
    root = repository_member(repo, binding["package_root"], directory=True)
    manifest = root / binding["package_manifest"]
    check(digest_file(manifest) == binding["package_manifest_sha256"], "development manifest")
    result_path = root / binding["formal_result"]
    verification_path = root / binding["independent_verification"]
    check(digest_file(result_path) == binding["formal_result_sha256"], "development result")
    check(
        digest_file(verification_path) == binding["independent_verification_sha256"],
        "development verification",
    )
    result = object_file(result_path)
    verification = object_file(verification_path)
    check(result["classification"] == binding["formal_classification"], "development class")
    step = result["selected_population_primary_comparisons"]["max_prior_step"]
    check(
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
        "development step values",
    )
    check(verification.get("all_aggregate_fields_equal") is True, "development equality")
    check(verification.get("producer_imported") is False, "development verifier independence")
    return {
        "package_manifest_sha256": binding["package_manifest_sha256"],
        "formal_result_sha256": binding["formal_result_sha256"],
        "independent_verification_sha256": binding["independent_verification_sha256"],
        "formal_classification": binding["formal_classification"],
        "valid_control": binding["valid_control"],
        "development_result_is_post_result_falsification": True,
    }


def load_protocol(path: Path, expected_sha: str, repo: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    actual = digest_file(path)
    check(actual == expected_sha == PROTOCOL_SHA256, "protocol digest")
    protocol = object_file(path)
    check(protocol.get("protocol") == PROTOCOL_NAME, "protocol identity")
    check(protocol.get("status") == PROTOCOL_STATUS, "protocol status")
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
    check(all(freeze[name] is False for name in unseen), "future readout seen at freeze")
    upstream = protocol["upstream_target522_contract"]
    for role in (
        "selection_protocol",
        "selection_monitor",
        "selective_protocol",
        "selective_producer",
        "selective_verifier",
    ):
        member = repository_member(repo, upstream[role])
        check(digest_file(member) == upstream[f"{role}_sha256"], f"upstream drift: {role}")
    for role, binding in protocol["immutable_helpers"].items():
        member = repository_member(repo, binding["path"])
        check(digest_file(member) == binding["sha256"], f"helper drift: {role}")
    security = protocol["security"]
    check(security["prospective_first960_or_target300_values_read"] is False, "prospective boundary")
    check(security["target522_candidate_or_profile_read_before_freeze"] is False, "Target-522 boundary")
    check(security["raw_senior_archives_opened"] is False, "raw archive boundary")
    check(security["task_run_card_parent_code_or_per_edge_values_emitted"] is False, "identity boundary")
    check(security["gpu_api_model_fit_base_update"] == [0, 0, 0, 0], "resource boundary")
    return protocol, development_evidence(repo, protocol)


def sole_maximum(candidates: list[str], key: Callable[[str], int]) -> str | None:
    if not candidates:
        return None
    maximum = max(key(candidate) for candidate in candidates)
    winners = [candidate for candidate in candidates if key(candidate) == maximum]
    return winners[0] if len(winners) == 1 else None


def observations(
    cards: dict[str, dict[str, Any]], objects: dict[str, dict[str, Any]]
) -> tuple[list[IndependentRow], dict[str, int]]:
    steps: dict[str, int] = {}
    for identity in sorted(cards):
        lineage = objects[identity].get("lineage")
        check(isinstance(lineage, dict), "lineage object missing")
        step = lineage.get("step")
        check(isinstance(step, int) and not isinstance(step, bool), "integer step required")
        steps[identity] = step
    fingerprints, by_run = content_check.independently_fingerprint(cards, objects)
    rows: list[IndependentRow] = []
    parent_present = fingerprint_ready = depth_ready = bad_step = 0
    for child in sorted(cards):
        child_meta = cards[child]
        parent = child_meta["parent"]
        if parent not in cards:
            continue
        parent_present += 1
        bad_step += not steps[parent] < steps[child]
        if child not in fingerprints or parent not in fingerprints:
            continue
        fingerprint_ready += 1
        if cards[parent]["depth"] != child_meta["depth"] - 1:
            continue
        depth_ready += 1
        choices = sorted(
            candidate
            for candidate in by_run.get(child_meta["run"], [])
            if cards[candidate]["depth"] == child_meta["depth"] - 1
        )
        check(parent in choices, "recorded parent excluded from candidate set")
        if len(choices) < 2:
            continue
        scores = {
            candidate: content_check.set_jaccard(
                fingerprints[child], fingerprints[candidate]
            )
            for candidate in choices
        }
        ordered = sorted(scores.values(), reverse=True)
        best, second = ordered[0], ordered[1]
        winners = [candidate for candidate in choices if scores[candidate] == best]
        content = winners[0] if len(winners) == 1 else None
        margin = best - second if content is not None else Fraction(0, 1)
        prior = [candidate for candidate in choices if steps[candidate] < steps[child]]
        rows.append(
            IndependentRow(
                task=child_meta["task"],
                run=child_meta["run"],
                parent=parent,
                candidates=len(choices),
                content=content,
                margin=margin,
                step=sole_maximum(prior, steps.__getitem__),
            )
        )
    return rows, {
        "parent_present_edges": parent_present,
        "fingerprint_eligible_parent_edges": fingerprint_ready,
        "depth_consistent_fingerprint_eligible_parent_edges": depth_ready,
        "depth_inconsistent_fingerprint_eligible_parent_edges": fingerprint_ready - depth_ready,
        "ambiguous_exact_depth_edges": len(rows),
        "recorded_parent_not_prior_step": bad_step,
        "fingerprinted_endpoints": len(fingerprints),
    }


def paired_profile(rows: list[IndependentRow]) -> tuple[dict[str, Any], list[IndependentRow]]:
    common = [row for row in rows if row.step is not None]
    content_correct = sum(row.content == row.parent for row in common)
    step_correct = sum(row.step == row.parent for row in common)
    both = sum(row.content == row.parent and row.step == row.parent for row in common)
    content_only = sum(row.content == row.parent and row.step != row.parent for row in common)
    step_only = sum(row.content != row.parent and row.step == row.parent for row in common)
    neither = len(common) - both - content_only - step_only
    content_errors = len(common) - content_correct
    step_errors = len(common) - step_correct
    check(content_correct == both + content_only, "content accounting")
    check(step_correct == both + step_only, "step accounting")
    return {
        "content_selected_rows": len(rows),
        "comparable_rows": len(common),
        "comparable_coverage": encode(quotient(len(common), len(rows))),
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
        "content_to_step_error_ratio": optional_quotient(content_errors, step_errors),
        "content_only_to_step_only_win_ratio": optional_quotient(content_only, step_only),
    }, common


def raw_step(rows: list[IndependentRow]) -> dict[str, Any]:
    predicted = [row for row in rows if row.step is not None]
    correct = sum(row.step == row.parent for row in predicted)
    return {
        "rows": len(rows),
        "predicted_rows": len(predicted),
        "coverage": encode(quotient(len(predicted), len(rows))),
        "correct": correct,
        "errors": len(predicted) - correct,
        "precision": encode(quotient(correct, len(predicted))),
    }


def breadth(rows: list[IndependentRow], field: str, minimum: int) -> dict[str, Any]:
    discordant = [
        row for row in rows if (row.content == row.parent) != (row.step == row.parent)
    ]
    grouped: dict[str, list[IndependentRow]] = collections.defaultdict(list)
    for row in discordant:
        grouped[getattr(row, field)].append(row)
    supported = [group for group in grouped.values() if len(group) >= minimum]
    positive = 0
    for group in supported:
        content_wins = sum(row.content == row.parent and row.step != row.parent for row in group)
        positive += content_wins > len(group) - content_wins
    sizes = [len(group) for group in grouped.values()]
    return {
        "discordant_rows": len(discordant),
        "conditionable_groups": len(supported),
        "fraction_net_content_positive": encode(quotient(positive, len(supported))),
        "maximum_discordance_contribution_share": encode(
            quotient(max(sizes, default=0), sum(sizes))
        ),
        "identities_emitted": False,
    }


def classify(
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
    breadth_gate = {
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
    elif all(aggregate.values()) and all(breadth_gate.values()):
        classification = "FORWARD_CONTENT_ADDS_BROADLY_BEYOND_MAX_PRIOR_STEP"
    elif all(aggregate.values()):
        classification = "FORWARD_CONTENT_ADDS_AGGREGATELY_BUT_BREADTH_UNSUPPORTED"
    else:
        classification = "FORWARD_MAX_PRIOR_STEP_NOT_RULED_OUT"
    check(classification in protocol["ordered_classification"], "classification outside protocol")
    return classification, support, aggregate, breadth_gate


def reconstruct(
    state_root: Path,
    selection_root: Path,
    repo_root: Path,
    protocol_path: Path,
    protocol_sha: str,
    source_commit: str,
    producer_source: Path,
    producer_source_sha: str,
) -> dict[str, Any]:
    check(COMMIT_RE.fullmatch(source_commit) is not None, "source commit syntax")
    repo = repo_root.resolve()
    protocol, development = load_protocol(protocol_path, protocol_sha, repo)
    check(digest_file(producer_source) == producer_source_sha, "producer source digest")
    producer_text = producer_source.read_text(encoding="utf-8")
    check("verify_tree_content_selective_parent_forward_target522_order_addendum" not in producer_text, "producer imports verifier")
    verifier_text = Path(__file__).read_text(encoding="utf-8")
    producer_module = "audit_tree_content_selective_parent_forward_target522_order_addendum"
    check(producer_module not in verifier_text, "verifier imports producer")

    upstream_contract = protocol["upstream_target522_contract"]
    check(str(selection_root) == upstream_contract["selection_root"], "selection root differs")
    upstream_root = Path(upstream_contract["selective_formal_root"])
    upstream_manifest_sha, upstream_manifest_members = manifest_receipt(upstream_root)
    upstream_receipt_path = upstream_root / "producer_a.json"
    upstream_verifier_path = upstream_root / "verifier_a.json"
    upstream_receipt_sha = digest_file(upstream_receipt_path)
    upstream_receipt = object_file(upstream_receipt_path)
    upstream_verification = upstream_check.verify(
        state_root,
        selection_root,
        repo,
        repo / upstream_contract["selective_protocol"],
        upstream_contract["selective_protocol_sha256"],
        upstream_receipt_path,
        upstream_receipt_sha,
        repo / upstream_contract["selective_producer"],
        upstream_contract["selective_producer_sha256"],
        upstream_contract["selective_source_commit"],
    )
    check(upstream_verification["classification"] == upstream_receipt["classification"], "upstream class")
    published_upstream_verification = object_file(upstream_verifier_path)
    check(published_upstream_verification == upstream_verification, "upstream verifier rebuild")

    selection_protocol_path = repo / upstream_contract["selection_protocol"]
    selection_monitor_path = repo / upstream_contract["selection_monitor"]
    selection_protocol, selection_protocol_sha = snapshot_check.protocol_file(
        selection_protocol_path, upstream_contract["selection_protocol_sha256"]
    )
    selection = snapshot_check.inspect_selection(
        selection_root,
        selection_protocol_path,
        selection_monitor_path,
        selection_protocol,
        selection_protocol_sha,
    )
    check(
        selection["monitor_source_sha256"] == upstream_contract["selection_monitor_sha256"],
        "selection monitor digest",
    )
    baseline = snapshot_check.collect_snapshot(state_root, selection["baseline"])
    candidate = snapshot_check.collect_snapshot(state_root, selection["candidate"])
    cards, run_objects, append_only = snapshot_check.incremental_population(
        baseline, candidate, selection_protocol
    )
    objects = {identity: candidate.card_objects[identity] for identity in cards}
    upstream_protocol = object_file(repo / upstream_contract["selective_protocol"])
    upstream_metrics, _upstream_rows = upstream_check.independently_compute(
        cards, objects, upstream_protocol
    )
    for key, value in upstream_metrics.items():
        check(upstream_receipt[key] == value, f"upstream aggregate: {key}")

    rows, inventory = observations(cards, objects)
    threshold = Fraction(protocol["fixed_content_rule"]["threshold"])
    selected = [row for row in rows if row.content is not None and row.margin >= threshold]
    selected_correct = sum(row.content == row.parent for row in selected)
    upstream_profile = upstream_receipt["forward_profile"]
    profile_exact = (
        len(rows) == upstream_profile["ambiguous_edges"]
        and len(selected) == upstream_profile["selected_edges"]
        and selected_correct == upstream_profile["selected_correct_edges"]
        and len(selected) - selected_correct == upstream_profile["selected_error_edges"]
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
    paired, common = paired_profile(selected)
    task = breadth(common, "task", protocol["hard_support"]["task_minimum_discordant_rows"])
    run = breadth(common, "run", protocol["hard_support"]["run_minimum_discordant_rows"])
    integrity = {
        **selection["checks"],
        "complete_hash_bound_upstream_selective_formal": True,
        "candidate_and_baseline_append_only_contract_exact": all(
            value is True for value in append_only.values() if isinstance(value, bool)
        ),
        "fixed_content_profile_exactly_matches_upstream_formal": profile_exact,
        "recorded_parent_strictly_precedes_child_step_for_every_parent_present_increment_edge": inventory[
            "recorded_parent_not_prior_step"
        ]
        == 0,
        "candidate_set_content_threshold_and_step_rule_unchanged": inventory_exact,
        "aggregate_only_output_without_identities": True,
    }
    classification, support, aggregate, breadth_gate = classify(
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
        "producer_source_sha256": producer_source_sha,
        "known_development_evidence": development,
        "upstream_target522_binding": {
            "source_commit": upstream_contract["selective_source_commit"],
            "formal_root": upstream_contract["selective_formal_root"],
            "formal_manifest_sha256": upstream_manifest_sha,
            "formal_manifest_members": upstream_manifest_members,
            "receipt_sha256": upstream_receipt_sha,
            "independent_verification_sha256": digest_file(upstream_verifier_path),
            "classification": upstream_receipt["classification"],
            "receipt_rebuilt_exactly": True,
        },
        "snapshot_bindings": {
            "baseline": baseline.bindings,
            "candidate": candidate.bindings,
            "selection_support": {
                "sha256sums_sha256": selection["manifest_sha256"],
                "selection_protocol_sha256": selection_protocol_sha,
                "monitor_source_sha256": selection["monitor_source_sha256"],
            },
        },
        "append_only_and_increment": append_only,
        "inventory": {
            "increment_endpoints": len(cards),
            "increment_physical_runs": len(run_objects),
            "increment_tasks": len({row["task"] for row in cards.values()}),
            **inventory,
        },
        "fixed_content_rule": {
            **protocol["fixed_content_rule"],
            "threshold_exact": encode(threshold),
            "selected_rows": len(selected),
            "selected_correct": selected_correct,
            "selected_errors": len(selected) - selected_correct,
            "matches_upstream_formal": profile_exact,
        },
        "selected_population_paired_comparison": paired,
        "all_ambiguous_max_prior_step_supplementary": raw_step(rows),
        "anonymous_disagreement_breadth": {"task": task, "physical_run": run},
        "pre_registered_gate": {
            "integrity": integrity,
            "upstream_primary_confirmed": upstream_receipt["classification"]
            == upstream_contract["required_upstream_classification_for_positive_addendum"],
            "support": support,
            "aggregate_advantage": aggregate,
            "breadth": breadth_gate,
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


def verify(
    state_root: Path,
    selection_root: Path,
    repo_root: Path,
    protocol_path: Path,
    protocol_sha: str,
    receipt_path: Path,
    receipt_sha: str,
    producer_source: Path,
    producer_source_sha: str,
    source_commit: str,
) -> dict[str, Any]:
    check(digest_file(receipt_path) == receipt_sha, "receipt digest")
    expected = reconstruct(
        state_root,
        selection_root,
        repo_root,
        protocol_path,
        protocol_sha,
        source_commit,
        producer_source,
        producer_source_sha,
    )
    candidate = object_file(receipt_path)
    check(candidate == expected, "candidate differs from independent reconstruction")
    return {
        "protocol": "independent-tree-content-selective-parent-forward-target522-order-addendum-v1",
        "status": "INDEPENDENT_FORWARD_ORDER_BASELINE_ADDENDUM_PASS",
        "classification": candidate["classification"],
        "protocol_sha256": protocol_sha,
        "receipt_sha256": receipt_sha,
        "analysis_source_commit": source_commit,
        "producer_source_sha256": producer_source_sha,
        "producer_imported": False,
        "upstream_selective_receipt_independently_verified": True,
        "selection_snapshot_fingerprint_candidate_content_step_pairing_and_gates_independently_recomputed": True,
        "all_aggregate_fields_equal": True,
        "task_run_card_parent_code_or_per_edge_values_emitted": False,
        "prospective_first960_or_target300_values_read": False,
        "raw_senior_archives_opened": False,
        "row_level_release_created": False,
        "gpu_api_model_fit_base_update": [0, 0, 0, 0],
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
        ForwardOrderAddendumVerificationError,
        snapshot_check.ForwardVerificationError,
        upstream_check.ForwardSelectiveParentVerificationError,
    ) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
