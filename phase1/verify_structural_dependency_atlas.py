#!/usr/bin/env python3
"""Independently recompute and verify a structural-dependency atlas."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import statistics
import sys
from pathlib import Path
from typing import Any


class AtlasVerificationError(RuntimeError):
    """Raised when an atlas or source receipt fails independent verification."""


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read_bound(path: Path, expected_sha: str) -> tuple[bytes, dict[str, Any]]:
    if path.is_symlink() or not path.is_file():
        raise AtlasVerificationError(f"unsafe or absent input: {path.name}")
    raw = path.read_bytes()
    if digest(raw) != expected_sha:
        raise AtlasVerificationError(f"SHA mismatch: {path.name}")
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AtlasVerificationError(f"invalid JSON: {path.name}") from exc
    if not isinstance(value, dict):
        raise AtlasVerificationError(f"non-object input: {path.name}")
    return raw, value


def counts(source: Any, label: str) -> dict[str, int]:
    if not isinstance(source, dict) or not source:
        raise AtlasVerificationError(f"missing counts: {label}")
    result: dict[str, int] = {}
    for task, value in source.items():
        if not isinstance(task, str) or not task:
            raise AtlasVerificationError(f"invalid task in {label}")
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise AtlasVerificationError(f"invalid value in {label}")
        result[task] = value
    return result


def stats(weights: dict[str, int]) -> dict[str, Any]:
    ordered = sorted((value for value in weights.values() if value), reverse=True)
    total = sum(ordered)
    if not ordered or total <= 0:
        raise AtlasVerificationError("zero-weight distribution")
    probability = [value / total for value in ordered]
    hhi = math.fsum(item**2 for item in probability)
    entropy = -math.fsum(item * math.log(item) for item in probability)
    ascending = ordered[::-1]
    n = len(ordered)
    gini = math.fsum(
        (2 * rank - n - 1) * value for rank, value in enumerate(ascending, 1)
    ) / (n * total)
    return {
        "positive_clusters": n,
        "zero_weight_clusters": len(weights) - n,
        "total_weight": total,
        "maximum_count": ordered[0],
        "maximum_share": probability[0],
        "top3_share": math.fsum(probability[:3]),
        "top5_share": math.fsum(probability[:5]),
        "hhi": hhi,
        "inverse_hhi_descriptive_diversity": 1 / hhi,
        "shannon_entropy": entropy,
        "exponential_shannon_descriptive_diversity": math.exp(entropy),
        "normalized_entropy": entropy / math.log(n) if n > 1 else None,
        "gini": gini,
        "median_count": statistics.median(ordered),
        "counts_descending": ordered,
    }


def shift(base: dict[str, int], alternate: dict[str, int]) -> dict[str, Any]:
    task_names = sorted(set(base) | set(alternate))
    base_total = sum(base.get(task, 0) for task in task_names)
    alternate_total = sum(alternate.get(task, 0) for task in task_names)
    if base_total <= 0 or alternate_total <= 0:
        raise AtlasVerificationError("invalid weighting totals")
    base_share = {task: base.get(task, 0) / base_total for task in task_names}
    alternate_share = {
        task: alternate.get(task, 0) / alternate_total for task in task_names
    }
    base_stats, alternate_stats = stats(base), stats(alternate)
    base_max, alternate_max = max(base.values()), max(alternate.values())
    base_leaders = {task for task, value in base.items() if value == base_max}
    alternate_leaders = {
        task for task, value in alternate.items() if value == alternate_max
    }
    amplifications = [
        alternate_share[task] / base_share[task]
        for task in task_names
        if base_share[task] > 0
    ]
    leader_ratios = [
        alternate_share[task] / base_share[task] for task in alternate_leaders
    ]
    return {
        "total_variation_distance": math.fsum(
            abs(base_share[task] - alternate_share[task]) for task in task_names
        )
        / 2,
        "maximum_share_ratio": alternate_stats["maximum_share"]
        / base_stats["maximum_share"],
        "hhi_ratio": alternate_stats["hhi"] / base_stats["hhi"],
        "inverse_hhi_diversity_ratio": alternate_stats[
            "inverse_hhi_descriptive_diversity"
        ]
        / base_stats["inverse_hhi_descriptive_diversity"],
        "maximum_same_task_share_amplification": max(amplifications),
        "median_same_task_share_amplification": statistics.median(amplifications),
        "comparison_dominant_task_reference_share": max(
            base_share[task] for task in alternate_leaders
        ),
        "comparison_dominant_task_comparison_share": max(
            alternate_share[task] for task in alternate_leaders
        ),
        "comparison_dominant_task_share_amplification": max(leader_ratios),
        "reference_dominant_tie_count": len(base_leaders),
        "comparison_dominant_tie_count": len(alternate_leaders),
        "dominant_task_sets_overlap": bool(base_leaders & alternate_leaders),
    }


def reconstruct_scope(source: Any, name: str) -> dict[str, Any]:
    if not isinstance(source, dict):
        raise AtlasVerificationError(f"missing scope: {name}")
    run_counts = counts(source.get("run_counts"), f"{name}/runs")
    endpoint_counts = counts(source.get("endpoint_counts"), f"{name}/endpoints")
    pair_counts = counts(source.get("structural_pair_counts"), f"{name}/pairs")
    task_names = set(run_counts)
    if set(endpoint_counts) != task_names or not set(pair_counts).issubset(task_names):
        raise AtlasVerificationError(f"scope task support mismatch: {name}")
    pair_counts = {task: pair_counts.get(task, 0) for task in task_names}
    run_total = sum(run_counts.values())
    endpoint_total = sum(endpoint_counts.values())
    pair_total = sum(pair_counts.values())
    if pair_total <= 0:
        raise AtlasVerificationError(f"scope has no pairs: {name}")
    inventory = {
        "runs": run_total,
        "tasks": len(task_names),
        "endpoints": endpoint_total,
        "structural_pairs": pair_total,
        "pair_tasks": sum(value > 0 for value in pair_counts.values()),
    }
    for key in ("runs", "tasks", "endpoints", "structural_pairs"):
        if source.get(key) != inventory[key]:
            raise AtlasVerificationError(f"scope inventory mismatch: {name}/{key}")
    reported = (
        ("dominant_run_task_share", max(run_counts.values()) / run_total),
        ("dominant_endpoint_task_share", max(endpoint_counts.values()) / endpoint_total),
        ("dominant_structural_pair_task_share", max(pair_counts.values()) / pair_total),
    )
    if any(
        isinstance(source.get(key), bool)
        or not isinstance(source.get(key), (int, float))
        or not math.isclose(float(source[key]), expected, rel_tol=1e-12, abs_tol=1e-12)
        for key, expected in reported
    ):
        raise AtlasVerificationError(f"scope dominant-share mismatch: {name}")
    rows = []
    for task in sorted(task_names):
        run_value = run_counts[task]
        endpoint_value = endpoint_counts[task]
        pair_value = pair_counts[task]
        if run_value <= 0 or endpoint_value <= 0:
            raise AtlasVerificationError(f"scope has nonpositive support: {name}")
        rows.append(
            {
                "task": task,
                "runs": run_value,
                "endpoints": endpoint_value,
                "structural_pairs": pair_value,
                "run_share": run_value / run_total,
                "endpoint_share": endpoint_value / endpoint_total,
                "pair_share": pair_value / pair_total,
                "endpoints_per_run": endpoint_value / run_value,
                "pairs_per_run": pair_value / run_value,
            }
        )
    return {
        "inventory": inventory,
        "task_concentration_by_weighting": {
            "runs": stats(run_counts),
            "endpoints": stats(endpoint_counts),
            "structural_pairs": stats(pair_counts),
        },
        "weighting_shift": {
            "runs_to_endpoints": shift(run_counts, endpoint_counts),
            "runs_to_structural_pairs": shift(run_counts, pair_counts),
            "endpoints_to_structural_pairs": shift(endpoint_counts, pair_counts),
        },
        "per_task": rows,
    }


def compare(expected: Any, observed: Any, path: str = "root") -> None:
    if isinstance(expected, float):
        if (
            isinstance(observed, bool)
            or not isinstance(observed, (int, float))
            or not math.isclose(expected, float(observed), rel_tol=1e-12, abs_tol=1e-12)
        ):
            raise AtlasVerificationError(f"numeric mismatch at {path}")
        return
    if isinstance(expected, dict):
        if not isinstance(observed, dict) or set(expected) != set(observed):
            raise AtlasVerificationError(f"mapping mismatch at {path}")
        for key in expected:
            compare(expected[key], observed[key], f"{path}.{key}")
        return
    if isinstance(expected, list):
        if not isinstance(observed, list) or len(expected) != len(observed):
            raise AtlasVerificationError(f"list mismatch at {path}")
        for index, (left, right) in enumerate(zip(expected, observed)):
            compare(left, right, f"{path}[{index}]")
        return
    if expected != observed:
        raise AtlasVerificationError(f"value mismatch at {path}")


def recompute_chronology(first: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "status": "DESCRIPTIVE_POST_HOC_AUDIT_NOT_A_PREREGISTERED_EFFECT_TEST",
        "inventory_change": {
            key: current["inventory"][key] - first["inventory"][key]
            for key in ("runs", "tasks", "endpoints", "structural_pairs", "pair_tasks")
        },
        "weighting_metrics": {},
    }
    for label in ("runs", "endpoints", "structural_pairs"):
        old = first["task_concentration_by_weighting"][label]
        new = current["task_concentration_by_weighting"][label]
        result["weighting_metrics"][label] = {
            "maximum_share_delta": new["maximum_share"] - old["maximum_share"],
            "maximum_share_ratio": new["maximum_share"] / old["maximum_share"],
            "hhi_delta": new["hhi"] - old["hhi"],
            "hhi_ratio": new["hhi"] / old["hhi"],
            "inverse_hhi_diversity_delta": new["inverse_hhi_descriptive_diversity"]
            - old["inverse_hhi_descriptive_diversity"],
            "inverse_hhi_diversity_ratio": new["inverse_hhi_descriptive_diversity"]
            / old["inverse_hhi_descriptive_diversity"],
        }
    result["descriptive_flags"] = {
        "run_max_share_fell_while_pair_max_share_rose": (
            result["weighting_metrics"]["runs"]["maximum_share_delta"] < 0
            and result["weighting_metrics"]["structural_pairs"]["maximum_share_delta"] > 0
        ),
        "pair_inverse_hhi_diversity_fell_despite_more_tasks": (
            result["inventory_change"]["tasks"] > 0
            and result["weighting_metrics"]["structural_pairs"][
                "inverse_hhi_diversity_delta"
            ]
            < 0
        ),
    }
    return result


def verify(
    accumulator_path: Path,
    accumulator_sha: str,
    structural_gate_path: Path,
    structural_gate_sha: str,
    atlas_path: Path,
    atlas_sha: str,
    producer_source_path: Path,
    producer_source_sha: str,
) -> dict[str, Any]:
    _, accumulator = read_bound(accumulator_path, accumulator_sha)
    _, gate = read_bound(structural_gate_path, structural_gate_sha)
    atlas_raw, atlas = read_bound(atlas_path, atlas_sha)
    if producer_source_path.is_symlink() or not producer_source_path.is_file():
        raise AtlasVerificationError("producer source is absent or unsafe")
    actual_source_sha = digest(producer_source_path.read_bytes())
    if actual_source_sha != producer_source_sha:
        raise AtlasVerificationError("producer source SHA mismatch")
    if atlas.get("protocol") != "prospective_structural_dependency_atlas_v1":
        raise AtlasVerificationError("atlas protocol mismatch")
    if atlas.get("status") != "OUTCOME_BLIND_STRUCTURAL_DEPENDENCY_ATLAS_READY":
        raise AtlasVerificationError("atlas status mismatch")
    if atlas.get("inputs") != {
        "accumulator_summary_sha256": accumulator_sha,
        "structural_gate_sha256": structural_gate_sha,
    }:
        raise AtlasVerificationError("atlas input binding mismatch")
    if gate.get("inputs", {}).get("accumulator_summary_sha256") != accumulator_sha:
        raise AtlasVerificationError("gate/accumulator binding mismatch")
    if atlas.get("snapshot_sha256") != gate.get("snapshot_sha256"):
        raise AtlasVerificationError("snapshot mismatch")
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
        raise AtlasVerificationError("source receipt is not outcome-blind")
    reproducibility = atlas.get("reproducibility")
    if (
        not isinstance(reproducibility, dict)
        or reproducibility.get("source_sha256") != producer_source_sha
        or reproducibility.get("randomness_used") is not False
        or not isinstance(reproducibility.get("source_commit"), str)
        or len(reproducibility["source_commit"]) != 40
    ):
        raise AtlasVerificationError("atlas source binding mismatch")

    task_support = accumulator.get("task_support")
    if not isinstance(task_support, dict):
        raise AtlasVerificationError("accumulator task support missing")
    first = reconstruct_scope(task_support.get("provisional_first240"), "first240")
    current = reconstruct_scope(task_support.get("provisional_first960"), "first960")
    expected_scopes = {
        "provisional_first240": first,
        "provisional_first960_prefix": current,
    }
    compare(expected_scopes, atlas.get("scopes"), "scopes")
    expected_chronology = recompute_chronology(first, current)
    compare(expected_chronology, atlas.get("chronological_comparison"), "chronology")

    inventory = gate.get("independent_inventory", {}).get("provisional_first960")
    support = gate.get("asset_quality", {}).get("decision_support")
    if not isinstance(inventory, dict) or not isinstance(support, dict):
        raise AtlasVerificationError("gate structural support missing")
    for key, expected in current["inventory"].items():
        if key in inventory and inventory[key] != expected:
            raise AtlasVerificationError(f"gate inventory mismatch: {key}")
    pairs = current["inventory"]["structural_pairs"]
    parents = support.get("decision_parent_groups")
    runs = support.get("runs_with_finite_decision")
    tasks = support.get("tasks_with_finite_decision")
    median_pairs = support.get("median_pairs_per_decision_run")
    if not all(isinstance(value, int) and not isinstance(value, bool) and value > 0 for value in (parents, runs, tasks)):
        raise AtlasVerificationError("invalid gate funnel counts")
    expected_funnel = {
        "canonical_sibling_pairs": pairs,
        "decision_parent_groups": parents,
        "decision_runs": runs,
        "pair_tasks": tasks,
        "pairs_above_one_per_parent_group": pairs - parents,
        "pairs_per_parent_group": pairs / parents,
        "excess_pair_fraction_above_one_per_parent_group": (pairs - parents) / pairs,
        "parent_groups_per_decision_run": parents / runs,
        "pairs_per_decision_run_mean": pairs / runs,
        "pairs_per_decision_run_median": median_pairs,
        "pairs_per_pair_task_mean": pairs / tasks,
        "interpretation": (
            "Nested support counts are descriptive clustering units, not mutually "
            "independent observations or a statistical effective sample size."
        ),
    }
    compare(expected_funnel, atlas.get("dependency_funnel"), "dependency_funnel")
    expected_contract = {
        "primary_point_estimate": "task_macro",
        "primary_uncertainty": "task_clustered_bootstrap_plus_leave_one_task_out",
        "secondary_point_estimates": ["run_macro", "pair_micro"],
        "secondary_uncertainty": "physical_run_clustered",
        "raw_pair_count_is_an_independence_claim": False,
        "inverse_hhi_is_descriptive_diversity_not_effective_sample_size": True,
        "chronological_comparison_is_descriptive_not_preregistered": True,
        "accrual_guard_uses_observed_pair_yield_without_reordering_first960": True,
    }
    compare(expected_contract, atlas.get("estimand_contract"), "estimand_contract")
    expected_security = {
        "accepted_input_basenames": ["structural_gate.json", "summary.json"],
        "label_grade_outcome_or_winner_orientation_read": False,
        "prediction_values_read_or_aggregated": False,
        "accuracy_effect_or_search_utility_computed": False,
        "task_identities_emitted": True,
        "gpu_calls": 0,
        "api_calls": 0,
        "base_llm_updates": 0,
    }
    compare(expected_security, atlas.get("security"), "security")
    return {
        "protocol": "independent_prospective_structural_dependency_atlas_v1",
        "status": "INDEPENDENT_STRUCTURAL_DEPENDENCY_ATLAS_PASS",
        "atlas_sha256": digest(atlas_raw),
        "producer_source_sha256": producer_source_sha,
        "inputs": {
            "accumulator_summary_sha256": accumulator_sha,
            "structural_gate_sha256": structural_gate_sha,
        },
        "checks": {
            "input_hashes_bound": True,
            "source_hash_bound": True,
            "scope_inventories_recomputed": True,
            "all_task_concentration_metrics_recomputed": True,
            "all_weighting_shifts_recomputed": True,
            "chronological_comparison_recomputed": True,
            "dependency_funnel_recomputed": True,
            "estimand_contract_exact": True,
            "outcome_blind_attestations_exact": True,
        },
        "recomputed_key_findings": {
            "current_runs": current["inventory"]["runs"],
            "current_pairs": pairs,
            "current_pair_inverse_hhi_diversity": current[
                "task_concentration_by_weighting"
            ]["structural_pairs"]["inverse_hhi_descriptive_diversity"],
            "current_pair_dominant_share": current["task_concentration_by_weighting"][
                "structural_pairs"
            ]["maximum_share"],
            "pairs_per_parent_group": pairs / parents,
        },
        "security": {
            "label_grade_outcome_prediction_or_winner_orientation_read": False,
            "accuracy_effect_or_search_utility_computed": False,
            "gpu_or_api_calls": 0,
        },
    }


def write_new(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise AtlasVerificationError("refusing to overwrite verification output")
    if not path.parent.is_dir() or path.parent.is_symlink():
        raise AtlasVerificationError("verification output parent is unsafe")
    temporary = path.with_name(path.name + f".tmp-{os.getpid()}")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
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
    parser.add_argument("--atlas", required=True, type=Path)
    parser.add_argument("--expect-atlas-sha256", required=True)
    parser.add_argument("--producer-source", required=True, type=Path)
    parser.add_argument("--expect-producer-source-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = verify(
            args.accumulator_summary,
            args.expect_accumulator_summary_sha256,
            args.structural_gate,
            args.expect_structural_gate_sha256,
            args.atlas,
            args.expect_atlas_sha256,
            args.producer_source,
            args.expect_producer_source_sha256,
        )
        write_new(args.output.resolve(), result)
        print(json.dumps(result["recomputed_key_findings"], sort_keys=True, separators=(",", ":")))
        return 0
    except (AtlasVerificationError, OSError, ValueError, ZeroDivisionError) as exc:
        print(f"STRUCTURAL_DEPENDENCY_ATLAS_VERIFY_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
