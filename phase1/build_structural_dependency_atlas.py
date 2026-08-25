#!/usr/bin/env python3
"""Build an outcome-blind atlas of task weighting and structural dependence.

The atlas consumes only two aggregate, SHA-bound receipts: the prospective
accumulator summary and the independently rebuilt structural-gate receipt.  It
does not accept a label vault, outcome file, prediction registry, or score file.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import statistics
import sys
from pathlib import Path
from typing import Any


PROTOCOL = "prospective_structural_dependency_atlas_v1"
STATUS = "OUTCOME_BLIND_STRUCTURAL_DEPENDENCY_ATLAS_READY"


class AtlasError(RuntimeError):
    """Raised when an input or structural invariant fails closed."""


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read_bound_object(path: Path, expected_sha256: str) -> tuple[bytes, dict[str, Any]]:
    if path.is_symlink() or not path.is_file():
        raise AtlasError(f"input is absent, non-regular, or symlinked: {path.name}")
    raw = path.read_bytes()
    if sha256_bytes(raw) != expected_sha256:
        raise AtlasError(f"input hash mismatch: {path.name}")
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AtlasError(f"cannot parse input: {path.name}") from exc
    if not isinstance(value, dict):
        raise AtlasError(f"input is not an object: {path.name}")
    return raw, value


def checked_counts(value: Any, label: str) -> dict[str, int]:
    if not isinstance(value, dict) or not value:
        raise AtlasError(f"{label} is absent or empty")
    output: dict[str, int] = {}
    for name, count in value.items():
        if not isinstance(name, str) or not name:
            raise AtlasError(f"{label} has an invalid task name")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise AtlasError(f"{label} has an invalid count")
        output[name] = count
    return output


def concentration(counts: dict[str, int]) -> dict[str, Any]:
    positive = sorted((count for count in counts.values() if count > 0), reverse=True)
    total = sum(positive)
    if not positive or total <= 0:
        raise AtlasError("concentration requires positive support")
    shares = [count / total for count in positive]
    hhi = sum(share * share for share in shares)
    entropy = -sum(share * math.log(share) for share in shares)
    ascending = sorted(positive)
    n = len(ascending)
    gini_numerator = sum((2 * index - n - 1) * count for index, count in enumerate(ascending, 1))
    return {
        "positive_clusters": n,
        "zero_weight_clusters": len(counts) - n,
        "total_weight": total,
        "maximum_count": positive[0],
        "maximum_share": shares[0],
        "top3_share": sum(shares[:3]),
        "top5_share": sum(shares[:5]),
        "hhi": hhi,
        "inverse_hhi_descriptive_diversity": 1.0 / hhi,
        "shannon_entropy": entropy,
        "exponential_shannon_descriptive_diversity": math.exp(entropy),
        "normalized_entropy": entropy / math.log(n) if n > 1 else None,
        "gini": gini_numerator / (n * total),
        "median_count": statistics.median(positive),
        "counts_descending": positive,
    }


def normalized_shares(counts: dict[str, int], keys: list[str]) -> dict[str, float]:
    total = sum(counts.get(key, 0) for key in keys)
    if total <= 0:
        raise AtlasError("share normalization has zero total")
    return {key: counts.get(key, 0) / total for key in keys}


def weighting_shift(reference: dict[str, int], comparison: dict[str, int]) -> dict[str, Any]:
    keys = sorted(set(reference) | set(comparison))
    reference_shares = normalized_shares(reference, keys)
    comparison_shares = normalized_shares(comparison, keys)
    ref_concentration = concentration(reference)
    cmp_concentration = concentration(comparison)
    ref_max = max(reference.values())
    cmp_max = max(comparison.values())
    ref_dominants = {key for key, value in reference.items() if value == ref_max}
    cmp_dominants = {key for key, value in comparison.items() if value == cmp_max}
    same_task_amplifications = [
        comparison_shares[key] / reference_shares[key]
        for key in keys
        if reference_shares[key] > 0
    ]
    comparison_dominant_reference_shares = [reference_shares[key] for key in cmp_dominants]
    comparison_dominant_comparison_shares = [comparison_shares[key] for key in cmp_dominants]
    return {
        "total_variation_distance": 0.5
        * sum(abs(reference_shares[key] - comparison_shares[key]) for key in keys),
        "maximum_share_ratio": cmp_concentration["maximum_share"]
        / ref_concentration["maximum_share"],
        "hhi_ratio": cmp_concentration["hhi"] / ref_concentration["hhi"],
        "inverse_hhi_diversity_ratio": cmp_concentration[
            "inverse_hhi_descriptive_diversity"
        ]
        / ref_concentration["inverse_hhi_descriptive_diversity"],
        "maximum_same_task_share_amplification": max(same_task_amplifications),
        "median_same_task_share_amplification": statistics.median(same_task_amplifications),
        "comparison_dominant_task_reference_share": max(
            comparison_dominant_reference_shares
        ),
        "comparison_dominant_task_comparison_share": max(
            comparison_dominant_comparison_shares
        ),
        "comparison_dominant_task_share_amplification": max(
            comparison_shares[key] / reference_shares[key] for key in cmp_dominants
        ),
        "reference_dominant_tie_count": len(ref_dominants),
        "comparison_dominant_tie_count": len(cmp_dominants),
        "dominant_task_sets_overlap": bool(ref_dominants & cmp_dominants),
    }


def scope_summary(value: Any, scope_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AtlasError(f"missing task support scope: {scope_name}")
    run_counts = checked_counts(value.get("run_counts"), f"{scope_name}.run_counts")
    endpoint_counts = checked_counts(
        value.get("endpoint_counts"), f"{scope_name}.endpoint_counts"
    )
    pair_counts = checked_counts(
        value.get("structural_pair_counts"), f"{scope_name}.structural_pair_counts"
    )
    tasks = set(run_counts)
    if set(endpoint_counts) != tasks or not set(pair_counts).issubset(tasks):
        raise AtlasError(f"task support mismatch in {scope_name}")
    for task in tasks:
        pair_counts.setdefault(task, 0)
    runs = sum(run_counts.values())
    endpoints = sum(endpoint_counts.values())
    pairs = sum(pair_counts.values())
    if runs <= 0 or endpoints <= 0 or pairs <= 0:
        raise AtlasError(f"nonpositive scope total in {scope_name}")
    if (
        value.get("runs") != runs
        or value.get("endpoints") != endpoints
        or value.get("structural_pairs") != pairs
        or value.get("tasks") != len(tasks)
    ):
        raise AtlasError(f"inventory mismatch in {scope_name}")
    reported_dominant = {
        "dominant_run_task_share": max(run_counts.values()) / runs,
        "dominant_endpoint_task_share": max(endpoint_counts.values()) / endpoints,
        "dominant_structural_pair_task_share": max(pair_counts.values()) / pairs,
    }
    if any(
        not isinstance(value.get(key), (int, float))
        or isinstance(value.get(key), bool)
        or not math.isclose(float(value[key]), expected, rel_tol=1e-12, abs_tol=1e-12)
        for key, expected in reported_dominant.items()
    ):
        raise AtlasError(f"reported dominant share mismatch in {scope_name}")
    per_task = []
    for task in sorted(tasks):
        run_count = run_counts[task]
        endpoint_count = endpoint_counts[task]
        pair_count = pair_counts[task]
        if run_count <= 0 or endpoint_count <= 0:
            raise AtlasError(f"nonpositive run or endpoint support in {scope_name}")
        per_task.append(
            {
                "task": task,
                "runs": run_count,
                "endpoints": endpoint_count,
                "structural_pairs": pair_count,
                "run_share": run_count / runs,
                "endpoint_share": endpoint_count / endpoints,
                "pair_share": pair_count / pairs if pairs else 0.0,
                "endpoints_per_run": endpoint_count / run_count,
                "pairs_per_run": pair_count / run_count,
            }
        )
    return {
        "inventory": {
            "runs": runs,
            "tasks": len(tasks),
            "endpoints": endpoints,
            "structural_pairs": pairs,
            "pair_tasks": sum(count > 0 for count in pair_counts.values()),
        },
        "task_concentration_by_weighting": {
            "runs": concentration(run_counts),
            "endpoints": concentration(endpoint_counts),
            "structural_pairs": concentration(pair_counts),
        },
        "weighting_shift": {
            "runs_to_endpoints": weighting_shift(run_counts, endpoint_counts),
            "runs_to_structural_pairs": weighting_shift(run_counts, pair_counts),
            "endpoints_to_structural_pairs": weighting_shift(endpoint_counts, pair_counts),
        },
        "per_task": per_task,
    }


def chronological_comparison(first240: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    first_concentration = first240["task_concentration_by_weighting"]
    current_concentration = current["task_concentration_by_weighting"]
    inventory_first = first240["inventory"]
    inventory_current = current["inventory"]
    comparison: dict[str, Any] = {
        "status": "DESCRIPTIVE_POST_HOC_AUDIT_NOT_A_PREREGISTERED_EFFECT_TEST",
        "inventory_change": {
            key: inventory_current[key] - inventory_first[key]
            for key in ("runs", "tasks", "endpoints", "structural_pairs", "pair_tasks")
        },
        "weighting_metrics": {},
    }
    for weighting in ("runs", "endpoints", "structural_pairs"):
        before = first_concentration[weighting]
        after = current_concentration[weighting]
        comparison["weighting_metrics"][weighting] = {
            "maximum_share_delta": after["maximum_share"] - before["maximum_share"],
            "maximum_share_ratio": after["maximum_share"] / before["maximum_share"],
            "hhi_delta": after["hhi"] - before["hhi"],
            "hhi_ratio": after["hhi"] / before["hhi"],
            "inverse_hhi_diversity_delta": after["inverse_hhi_descriptive_diversity"]
            - before["inverse_hhi_descriptive_diversity"],
            "inverse_hhi_diversity_ratio": after[
                "inverse_hhi_descriptive_diversity"
            ]
            / before["inverse_hhi_descriptive_diversity"],
        }
    comparison["descriptive_flags"] = {
        "run_max_share_fell_while_pair_max_share_rose": (
            comparison["weighting_metrics"]["runs"]["maximum_share_delta"] < 0
            and comparison["weighting_metrics"]["structural_pairs"][
                "maximum_share_delta"
            ]
            > 0
        ),
        "pair_inverse_hhi_diversity_fell_despite_more_tasks": (
            comparison["inventory_change"]["tasks"] > 0
            and comparison["weighting_metrics"]["structural_pairs"][
                "inverse_hhi_diversity_delta"
            ]
            < 0
        ),
    }
    return comparison


def build_atlas(
    accumulator_path: Path,
    accumulator_sha256: str,
    structural_gate_path: Path,
    structural_gate_sha256: str,
    source_commit: str,
) -> dict[str, Any]:
    if len(source_commit) != 40 or any(character not in "0123456789abcdef" for character in source_commit):
        raise AtlasError("source commit is not a lowercase full Git SHA")
    _, accumulator = read_bound_object(accumulator_path, accumulator_sha256)
    _, gate = read_bound_object(structural_gate_path, structural_gate_sha256)
    if accumulator.get("protocol") != "prospective_accumulator_v1":
        raise AtlasError("accumulator protocol mismatch")
    if gate.get("protocol") != "prospective_structural_gate_independent_verifier_v5":
        raise AtlasError("structural gate protocol mismatch")
    accumulator_security = accumulator.get("security")
    gate_security = gate.get("security")
    if (
        not isinstance(accumulator_security, dict)
        or accumulator_security.get("label_vault_opened") is not False
        or accumulator_security.get("outcome_files_opened") != []
        or accumulator_security.get("scorer_prediction_files_opened") != []
        or not isinstance(gate_security, dict)
        or gate_security.get("label_vault_opened") is not False
        or gate_security.get("outcome_files_opened") != []
        or gate_security.get("scorer_prediction_files_opened") != []
    ):
        raise AtlasError("input receipts are not outcome-blind")
    snapshot = gate.get("snapshot_sha256")
    if (
        not isinstance(snapshot, str)
        or len(snapshot) != 64
        or any(character not in "0123456789abcdef" for character in snapshot)
    ):
        raise AtlasError("structural gate snapshot identity is invalid")
    gate_inputs = gate.get("inputs")
    if (
        not isinstance(gate_inputs, dict)
        or gate_inputs.get("accumulator_summary_sha256") != accumulator_sha256
    ):
        raise AtlasError("structural gate does not bind the supplied accumulator summary")

    task_support = accumulator.get("task_support")
    if not isinstance(task_support, dict):
        raise AtlasError("accumulator task support is missing")
    first240 = scope_summary(task_support.get("provisional_first240"), "provisional_first240")
    current = scope_summary(task_support.get("provisional_first960"), "provisional_first960")
    gate_inventory = gate.get("independent_inventory", {}).get("provisional_first960")
    decision_support = gate.get("asset_quality", {}).get("decision_support")
    if not isinstance(gate_inventory, dict) or not isinstance(decision_support, dict):
        raise AtlasError("structural gate inventory is missing")
    expected_gate_values = {
        "runs": current["inventory"]["runs"],
        "tasks": current["inventory"]["tasks"],
        "endpoints": current["inventory"]["endpoints"],
        "structural_pairs": current["inventory"]["structural_pairs"],
        "pair_tasks": current["inventory"]["pair_tasks"],
    }
    for key, expected in expected_gate_values.items():
        if gate_inventory.get(key) != expected:
            raise AtlasError(f"structural gate cross-check failed: {key}")
    pairs = current["inventory"]["structural_pairs"]
    parent_groups = decision_support.get("decision_parent_groups")
    decision_runs = decision_support.get("runs_with_finite_decision")
    pair_tasks = decision_support.get("tasks_with_finite_decision")
    median_pairs = decision_support.get("median_pairs_per_decision_run")
    if not all(
        isinstance(value, int) and not isinstance(value, bool) and value > 0
        for value in (parent_groups, decision_runs, pair_tasks)
    ) or not isinstance(median_pairs, (int, float)):
        raise AtlasError("invalid dependency-funnel support")
    if pair_tasks != current["inventory"]["pair_tasks"] or parent_groups > pairs:
        raise AtlasError("dependency-funnel accounting mismatch")

    pair_excess = pairs - parent_groups
    dependency_funnel = {
        "canonical_sibling_pairs": pairs,
        "decision_parent_groups": parent_groups,
        "decision_runs": decision_runs,
        "pair_tasks": pair_tasks,
        "pairs_above_one_per_parent_group": pair_excess,
        "pairs_per_parent_group": pairs / parent_groups,
        "excess_pair_fraction_above_one_per_parent_group": pair_excess / pairs,
        "parent_groups_per_decision_run": parent_groups / decision_runs,
        "pairs_per_decision_run_mean": pairs / decision_runs,
        "pairs_per_decision_run_median": median_pairs,
        "pairs_per_pair_task_mean": pairs / pair_tasks,
        "interpretation": (
            "Nested support counts are descriptive clustering units, not mutually "
            "independent observations or a statistical effective sample size."
        ),
    }

    return {
        "protocol": PROTOCOL,
        "status": STATUS,
        "snapshot_sha256": snapshot,
        "inputs": {
            "accumulator_summary_sha256": accumulator_sha256,
            "structural_gate_sha256": structural_gate_sha256,
        },
        "reproducibility": {
            "source_commit": source_commit,
            "source_sha256": sha256_bytes(Path(__file__).read_bytes()),
            "python_version": platform.python_version(),
            "randomness_used": False,
        },
        "scopes": {
            "provisional_first240": first240,
            "provisional_first960_prefix": current,
        },
        "chronological_comparison": chronological_comparison(first240, current),
        "dependency_funnel": dependency_funnel,
        "estimand_contract": {
            "primary_point_estimate": "task_macro",
            "primary_uncertainty": "task_clustered_bootstrap_plus_leave_one_task_out",
            "secondary_point_estimates": ["run_macro", "pair_micro"],
            "secondary_uncertainty": "physical_run_clustered",
            "raw_pair_count_is_an_independence_claim": False,
            "inverse_hhi_is_descriptive_diversity_not_effective_sample_size": True,
            "chronological_comparison_is_descriptive_not_preregistered": True,
            "accrual_guard_uses_observed_pair_yield_without_reordering_first960": True,
        },
        "security": {
            "accepted_input_basenames": ["structural_gate.json", "summary.json"],
            "label_grade_outcome_or_winner_orientation_read": False,
            "prediction_values_read_or_aggregated": False,
            "accuracy_effect_or_search_utility_computed": False,
            "task_identities_emitted": True,
            "gpu_calls": 0,
            "api_calls": 0,
            "base_llm_updates": 0,
        },
    }


def write_new(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise AtlasError("refusing to overwrite output")
    if not path.parent.is_dir() or path.parent.is_symlink():
        raise AtlasError("output parent is absent or unsafe")
    temporary = path.with_name(path.name + f".tmp-{os.getpid()}")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--accumulator-summary", required=True, type=Path)
    parser.add_argument("--expect-accumulator-summary-sha256", required=True)
    parser.add_argument("--structural-gate", required=True, type=Path)
    parser.add_argument("--expect-structural-gate-sha256", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = build_atlas(
            args.accumulator_summary,
            args.expect_accumulator_summary_sha256,
            args.structural_gate,
            args.expect_structural_gate_sha256,
            args.source_commit,
        )
        write_new(args.output.resolve(), result)
        print(
            json.dumps(
                {
                    "status": result["status"],
                    "snapshot_sha256": result["snapshot_sha256"],
                    "runs": result["scopes"]["provisional_first960_prefix"]["inventory"][
                        "runs"
                    ],
                    "pairs": result["dependency_funnel"]["canonical_sibling_pairs"],
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 0
    except (AtlasError, OSError, ValueError, ZeroDivisionError) as exc:
        print(f"STRUCTURAL_DEPENDENCY_ATLAS_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
