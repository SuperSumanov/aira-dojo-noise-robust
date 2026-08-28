#!/usr/bin/env python3
"""Derive an exact post-hoc depth-order corollary from one aggregate receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
from fractions import Fraction
from pathlib import Path
from typing import Any


PROTOCOL = "tree-linearization-depth-order-corollary-v1"
RECEIPT_PROTOCOL = "tree-linearization-depth-order-corollary-receipt-v1"
RECEIPT_STATUS = "TREE_LINEARIZATION_DEPTH_ORDER_COROLLARY_COMPLETE"
PASS = "VERIFIED_SHALLOW_DEPTH_STOCHASTIC_ORDER_COROLLARY"
NOT_VERIFIED = "DEPTH_ORDER_COROLLARY_NOT_VERIFIED"
SHA64 = re.compile(r"[0-9a-f]{64}")
SHA40 = re.compile(r"[0-9a-f]{40}")


class CorollaryError(RuntimeError):
    """Raised when a fixed source or exact integrity check fails."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CorollaryError(message)


def digest(path: Path) -> str:
    require(path.is_file() and not path.is_symlink(), f"unsafe file: {path.name}")
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def object_at(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"unsafe JSON: {path.name}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object expected: {path.name}")
    return value


def exact(value: Fraction) -> dict[str, Any]:
    return {
        "numerator": value.numerator,
        "denominator": value.denominator,
        "decimal_17g": format(float(value), ".17g"),
    }


def ratio(value: Any, label: str) -> Fraction:
    require(isinstance(value, str) and value, f"invalid exact value: {label}")
    try:
        result = Fraction(value)
    except (ValueError, ZeroDivisionError) as error:
        raise CorollaryError(f"invalid exact value: {label}") from error
    require(str(result) == value, f"noncanonical exact value: {label}")
    return result


def fixed_source(repo_root: Path, protocol: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    binding = protocol.get("fixed_input")
    require(isinstance(binding, dict), "missing fixed input")
    relative, expected = binding.get("path"), binding.get("sha256")
    require(isinstance(relative, str) and relative, "invalid fixed-input path")
    require(isinstance(expected, str) and SHA64.fullmatch(expected), "invalid fixed-input SHA")
    candidate = Path(relative)
    require(not candidate.is_absolute() and ".." not in candidate.parts, "unsafe fixed-input path")
    repo = repo_root.resolve()
    unresolved = repo / candidate
    require(not unresolved.is_symlink(), "fixed input is a symlink")
    source = unresolved.resolve()
    try:
        source.relative_to(repo)
    except ValueError as error:
        raise CorollaryError("fixed input escapes repository") from error
    require(digest(source) == expected, "fixed-input SHA mismatch")
    return source, binding


def depth_counts(value: Any, label: str) -> dict[int, int]:
    require(isinstance(value, dict) and value, f"missing depth counts: {label}")
    output: dict[int, int] = {}
    for raw_depth, raw_count in value.items():
        require(
            isinstance(raw_depth, str)
            and raw_depth.isdigit()
            and str(int(raw_depth)) == raw_depth,
            f"invalid depth key: {label}",
        )
        depth = int(raw_depth)
        require(
            depth > 0
            and isinstance(raw_count, int)
            and not isinstance(raw_count, bool)
            and raw_count > 0,
            f"invalid depth count: {label}",
        )
        output[depth] = raw_count
    return output


def nearest_rank(counts: dict[int, int], probability: Fraction) -> int:
    require(0 < probability <= 1, "invalid nearest-rank probability")
    total = sum(counts.values())
    target = (total * probability.numerator + probability.denominator - 1) // probability.denominator
    cumulative = 0
    for depth in sorted(counts):
        cumulative += counts[depth]
        if cumulative >= target:
            return depth
    raise CorollaryError("nearest-rank accounting failed")


def derive(canonical: dict[int, int], path_frequency: dict[int, int]) -> dict[str, Any]:
    depths = sorted(canonical)
    require(set(canonical) == set(path_frequency), "depth-key sets differ")
    require(depths == list(range(depths[0], depths[-1] + 1)), "depth support is not contiguous")
    canonical_total = sum(canonical.values())
    path_total = sum(path_frequency.values())
    canonical_sum = sum(depth * canonical[depth] for depth in depths)
    path_sum = sum(depth * path_frequency[depth] for depth in depths)
    canonical_mean = Fraction(canonical_sum, canonical_total)
    path_mean = Fraction(path_sum, path_total)
    mean_shift = path_mean - canonical_mean
    mean_ratio = path_mean / canonical_mean

    pmf_differences = [
        Fraction(path_frequency[depth], path_total) - Fraction(canonical[depth], canonical_total)
        for depth in depths
    ]
    total_variation = sum((abs(value) for value in pmf_differences), Fraction()) / 2
    cdf_gaps: list[Fraction] = []
    cumulative = Fraction()
    for difference in pmf_differences:
        cumulative += difference
        cdf_gaps.append(cumulative)
    terminal_zero = cdf_gaps[-1] == 0
    shallow_fosd = terminal_zero and all(value >= 0 for value in cdf_gaps)
    maximum_cdf_gap = max(cdf_gaps)
    maximum_cdf_depth = depths[cdf_gaps.index(maximum_cdf_gap)]
    signs = [1 if value > 0 else -1 for value in pmf_differences if value != 0]
    sign_changes = sum(left != right for left, right in zip(signs, signs[1:]))
    median_canonical = nearest_rank(canonical, Fraction(1, 2))
    median_path = nearest_rank(path_frequency, Fraction(1, 2))
    p90_canonical = nearest_rank(canonical, Fraction(9, 10))
    p90_path = nearest_rank(path_frequency, Fraction(9, 10))
    properties = {
        "shallow_first_order_stochastic_dominance": shallow_fosd,
        "strictly_negative_mean_depth_shift": mean_shift < 0,
        "exactly_one_nonzero_pmf_sign_change": sign_changes == 1,
        "maximum_cdf_gap_equals_depth_total_variation": maximum_cdf_gap == total_variation,
    }
    return {
        "inventory": {
            "minimum_logged_depth": depths[0],
            "maximum_logged_depth": depths[-1],
            "depth_levels": len(depths),
            "canonical_unique_edges": canonical_total,
            "path_edge_occurrences": path_total,
            "canonical_depth_sum": canonical_sum,
            "path_frequency_depth_sum": path_sum,
        },
        "depth_distributions": {
            "canonical_unique_edge_counts": {str(depth): canonical[depth] for depth in depths},
            "path_frequency_edge_counts": {str(depth): path_frequency[depth] for depth in depths},
        },
        "exact_order_profile": {
            "canonical_mean_depth": exact(canonical_mean),
            "path_frequency_mean_depth": exact(path_mean),
            "path_minus_canonical_mean_depth": exact(mean_shift),
            "path_to_canonical_mean_depth_ratio": exact(mean_ratio),
            "depth_total_variation": exact(total_variation),
            "cdf_path_minus_canonical": [
                {"depth": depth, "gap": exact(gap)} for depth, gap in zip(depths, cdf_gaps)
            ],
            "cdf_terminal_gap": exact(cdf_gaps[-1]),
            "maximum_cdf_gap": exact(maximum_cdf_gap),
            "maximum_cdf_gap_depth": maximum_cdf_depth,
            "nonzero_pmf_sign_changes": sign_changes,
            "canonical_nearest_rank_median_depth": median_canonical,
            "path_frequency_nearest_rank_median_depth": median_path,
            "canonical_nearest_rank_p90_depth": p90_canonical,
            "path_frequency_nearest_rank_p90_depth": p90_path,
        },
        "deterministic_properties": properties,
        "cdf_terminal_gap_is_exactly_zero": terminal_zero,
    }


def verify_seen_values(protocol: dict[str, Any], result: dict[str, Any]) -> None:
    seen = protocol.get("values_seen_before_declaration")
    require(isinstance(seen, dict), "missing seen-values disclosure")
    inventory = result["inventory"]
    profile = result["exact_order_profile"]
    expected = {
        "canonical_depth_support": [inventory["minimum_logged_depth"], inventory["maximum_logged_depth"]],
        "canonical_depth_count": inventory["canonical_unique_edges"],
        "path_frequency_depth_count": inventory["path_edge_occurrences"],
        "canonical_depth_sum": inventory["canonical_depth_sum"],
        "path_frequency_depth_sum": inventory["path_frequency_depth_sum"],
        "canonical_mean_depth": str(
            Fraction(profile["canonical_mean_depth"]["numerator"], profile["canonical_mean_depth"]["denominator"])
        ),
        "path_frequency_mean_depth": str(
            Fraction(profile["path_frequency_mean_depth"]["numerator"], profile["path_frequency_mean_depth"]["denominator"])
        ),
        "path_minus_canonical_mean_depth": str(
            Fraction(
                profile["path_minus_canonical_mean_depth"]["numerator"],
                profile["path_minus_canonical_mean_depth"]["denominator"],
            )
        ),
        "path_to_canonical_mean_depth_ratio": str(
            Fraction(
                profile["path_to_canonical_mean_depth_ratio"]["numerator"],
                profile["path_to_canonical_mean_depth_ratio"]["denominator"],
            )
        ),
        "depth_total_variation": str(
            Fraction(profile["depth_total_variation"]["numerator"], profile["depth_total_variation"]["denominator"])
        ),
        "maximum_cdf_gap": str(
            Fraction(profile["maximum_cdf_gap"]["numerator"], profile["maximum_cdf_gap"]["denominator"])
        ),
        "maximum_cdf_gap_depth": profile["maximum_cdf_gap_depth"],
        "shallow_first_order_stochastic_dominance": result["deterministic_properties"]
        ["shallow_first_order_stochastic_dominance"],
        "nonzero_pmf_sign_changes": profile["nonzero_pmf_sign_changes"],
        "canonical_nearest_rank_median_depth": profile["canonical_nearest_rank_median_depth"],
        "path_frequency_nearest_rank_median_depth": profile["path_frequency_nearest_rank_median_depth"],
        "canonical_nearest_rank_p90_depth": profile["canonical_nearest_rank_p90_depth"],
        "path_frequency_nearest_rank_p90_depth": profile["path_frequency_nearest_rank_p90_depth"],
    }
    require(seen == expected, "seen-values disclosure differs from exact recomputation")


def build(protocol_path: Path, protocol_sha: str, repo_root: Path, source_commit: str) -> dict[str, Any]:
    require(SHA40.fullmatch(source_commit) is not None, "invalid source commit")
    require(digest(protocol_path) == protocol_sha, "protocol SHA mismatch")
    protocol = object_at(protocol_path)
    require(protocol.get("protocol") == PROTOCOL, "protocol name mismatch")
    require(
        protocol.get("status")
        == "POST_HOC_DETERMINISTIC_COROLLARY_DECLARED_AFTER_EXPLORATORY_DERIVATION",
        "protocol status mismatch",
    )
    source_path, binding = fixed_source(repo_root, protocol)
    source = object_at(source_path)
    require(source.get("protocol") == binding["required_protocol"], "source protocol mismatch")
    require(source.get("status") == binding["required_status"], "source status mismatch")
    require(source.get("classification") == binding["required_classification"], "source classification mismatch")
    require(source.get("snapshot_sha256") == binding["required_snapshot_sha256"], "source snapshot mismatch")
    require(source.get("pre_registered_gate", {}).get("all_hard_gates_passed") is True, "source hard gates failed")
    diagnostic = source.get("weighting", {}).get("depth_diagnostic", {})
    require(diagnostic.get("non_rescuing") is True, "source depth diagnostic was not non-rescuing")
    canonical = depth_counts(diagnostic.get("unique_edge_counts"), "canonical")
    path_frequency = depth_counts(diagnostic.get("branch_linearized_counts"), "path-frequency")
    result = derive(canonical, path_frequency)
    inventory = result["inventory"]
    require(
        inventory["canonical_unique_edges"]
        == binding["required_observed_unique_edges"]
        == source.get("inventory", {}).get("observed_unique_edges")
        == source.get("linearization", {}).get("unique_edge_rows"),
        "canonical edge count mismatch",
    )
    require(
        inventory["path_edge_occurrences"]
        == binding["required_path_edge_occurrences"]
        == source.get("linearization", {}).get("branch_linearized_edge_occurrences"),
        "path occurrence count mismatch",
    )
    upstream_tv = diagnostic.get("total_variation")
    require(
        isinstance(upstream_tv, (int, float))
        and not isinstance(upstream_tv, bool)
        and math.isfinite(float(upstream_tv)),
        "invalid upstream depth TV",
    )
    require(
        format(float(upstream_tv), ".17g")
        == result["exact_order_profile"]["depth_total_variation"]["decimal_17g"],
        "upstream depth TV does not roundtrip",
    )
    require(result["cdf_terminal_gap_is_exactly_zero"], "terminal CDF gap is not zero")
    verify_seen_values(protocol, result)
    classification = (
        PASS if all(result["deterministic_properties"].values()) else NOT_VERIFIED
    )
    require(classification in protocol["ordered_classification"], "classification outside protocol")
    return {
        "protocol": RECEIPT_PROTOCOL,
        "status": RECEIPT_STATUS,
        "classification": classification,
        "source_commit": source_commit,
        "protocol_sha256": protocol_sha,
        "producer_source_sha256": digest(Path(__file__)),
        "snapshot_sha256": source["snapshot_sha256"],
        "input_sha256": {"linearization_receipt": binding["sha256"]},
        **result,
        "exact_integrity_checks": {
            "fixed_input_hash_and_metadata_match": True,
            "depth_keys_are_identical_contiguous_positive_integers": True,
            "all_depth_counts_are_positive_integers": True,
            "depth_count_totals_match_upstream_inventory": True,
            "upstream_float_total_variation_roundtrips_to_exact_recomputation_at_decimal_17g": True,
            "all_exact_means_cdf_gaps_total_variation_and_quantiles_recomputed": True,
            "cdf_terminal_gap_is_exactly_zero": True,
            "seen_values_disclosure_matches_exact_recomputation": True,
        },
        "design_timing": protocol["design_timing"],
        "claim_boundary": protocol["claim_boundary"],
        "security": {
            "aggregate_receipt_only": True,
            "raw_senior_archives_opened": False,
            "prospective_label_grade_outcome_prediction_values_read": False,
            "task_run_card_parent_code_or_per_edge_values_emitted": False,
            "accuracy_effect_or_search_utility_computed": False,
            "gpu_api_model_fit_base_update": [0, 0, 0, 0],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--protocol-sha256", required=True)
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    require(not output.exists(), f"output exists: {output}")
    receipt = build(
        Path(args.protocol), args.protocol_sha256, Path(args.repo_root), args.source_commit
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + f".tmp.{os.getpid()}")
    temporary.write_text(
        json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, output)
    print(receipt["classification"])


if __name__ == "__main__":
    main()
