#!/usr/bin/env python3
"""Independent verifier for the post-hoc tree depth-order corollary."""

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
VERIFY_PROTOCOL = "independent-tree-linearization-depth-order-verification-v1"
PASS = "VERIFIED_SHALLOW_DEPTH_STOCHASTIC_ORDER_COROLLARY"
NOT_VERIFIED = "DEPTH_ORDER_COROLLARY_NOT_VERIFIED"
SHA64 = re.compile(r"[0-9a-f]{64}")
SHA40 = re.compile(r"[0-9a-f]{40}")


class VerificationError(RuntimeError):
    """Raised when independent reconstruction does not match the receipt."""


def check(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def file_hash(path: Path) -> str:
    check(path.is_file() and not path.is_symlink(), f"unsafe file: {path.name}")
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(1 << 20)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def read_object(path: Path) -> dict[str, Any]:
    check(path.is_file() and not path.is_symlink(), f"unsafe JSON: {path.name}")
    parsed = json.loads(path.read_text(encoding="utf-8"))
    check(isinstance(parsed, dict), f"JSON object expected: {path.name}")
    return parsed


def encoded(value: Fraction) -> dict[str, Any]:
    return {
        "numerator": value.numerator,
        "denominator": value.denominator,
        "decimal_17g": format(float(value), ".17g"),
    }


def resolve_source(repo_root: Path, binding: dict[str, Any]) -> Path:
    check(isinstance(binding, dict), "missing fixed input")
    relative, expected = binding.get("path"), binding.get("sha256")
    check(isinstance(relative, str) and relative, "invalid fixed-input path")
    check(isinstance(expected, str) and SHA64.fullmatch(expected), "invalid fixed-input SHA")
    fragment = Path(relative)
    check(not fragment.is_absolute() and ".." not in fragment.parts, "unsafe fixed-input path")
    repo = repo_root.resolve()
    unresolved = repo / fragment
    check(not unresolved.is_symlink(), "fixed input is a symlink")
    resolved = unresolved.resolve()
    try:
        resolved.relative_to(repo)
    except ValueError as error:
        raise VerificationError("fixed input escapes repository") from error
    check(file_hash(resolved) == expected, "fixed-input SHA mismatch")
    return resolved


def read_counts(value: Any, label: str) -> list[tuple[int, int]]:
    check(isinstance(value, dict) and value, f"missing counts: {label}")
    rows: list[tuple[int, int]] = []
    for key, count in value.items():
        check(
            isinstance(key, str) and key.isdigit() and str(int(key)) == key and int(key) > 0,
            f"invalid depth: {label}",
        )
        check(
            isinstance(count, int) and not isinstance(count, bool) and count > 0,
            f"invalid count: {label}",
        )
        rows.append((int(key), count))
    rows.sort()
    return rows


def rank_from_rows(rows: list[tuple[int, int]], numerator: int, denominator: int) -> int:
    total = sum(count for _, count in rows)
    target = (total * numerator + denominator - 1) // denominator
    running = 0
    for depth, count in rows:
        running += count
        if running >= target:
            return depth
    raise VerificationError("nearest-rank accounting failed")


def independent_result(
    protocol: dict[str, Any],
    protocol_sha: str,
    source_commit: str,
    producer_sha: str,
    source: dict[str, Any],
) -> dict[str, Any]:
    binding = protocol["fixed_input"]
    check(source.get("protocol") == binding["required_protocol"], "source protocol mismatch")
    check(source.get("status") == binding["required_status"], "source status mismatch")
    check(source.get("classification") == binding["required_classification"], "source classification mismatch")
    check(source.get("snapshot_sha256") == binding["required_snapshot_sha256"], "source snapshot mismatch")
    check(source.get("pre_registered_gate", {}).get("all_hard_gates_passed") is True, "source hard gates failed")
    diagnostic = source.get("weighting", {}).get("depth_diagnostic", {})
    check(diagnostic.get("non_rescuing") is True, "source diagnostic is not non-rescuing")
    canonical_rows = read_counts(diagnostic.get("unique_edge_counts"), "canonical")
    path_rows = read_counts(diagnostic.get("branch_linearized_counts"), "path-frequency")
    depths = [depth for depth, _ in canonical_rows]
    check(depths == [depth for depth, _ in path_rows], "depth-key sets differ")
    check(depths == list(range(depths[0], depths[-1] + 1)), "depth support is not contiguous")
    canonical_counts = [count for _, count in canonical_rows]
    path_counts = [count for _, count in path_rows]
    canonical_total, path_total = sum(canonical_counts), sum(path_counts)
    canonical_sum = sum(depth * count for depth, count in canonical_rows)
    path_sum = sum(depth * count for depth, count in path_rows)
    check(
        canonical_total
        == binding["required_observed_unique_edges"]
        == source.get("inventory", {}).get("observed_unique_edges")
        == source.get("linearization", {}).get("unique_edge_rows"),
        "canonical count mismatch",
    )
    check(
        path_total
        == binding["required_path_edge_occurrences"]
        == source.get("linearization", {}).get("branch_linearized_edge_occurrences"),
        "path count mismatch",
    )

    denominator = canonical_total * path_total
    pmf_numerators = [
        path_count * canonical_total - canonical_count * path_total
        for canonical_count, path_count in zip(canonical_counts, path_counts)
    ]
    absolute_sum = sum(abs(value) for value in pmf_numerators)
    tv = Fraction(absolute_sum, 2 * denominator)
    cumulative_numerator = 0
    cdf: list[Fraction] = []
    for value in pmf_numerators:
        cumulative_numerator += value
        cdf.append(Fraction(cumulative_numerator, denominator))
    check(cdf[-1] == 0, "terminal CDF gap is not zero")
    maximum = max(cdf)
    maximum_depth = depths[cdf.index(maximum)]
    nonzero_signs = [1 if value > 0 else -1 for value in pmf_numerators if value != 0]
    crossings = sum(left != right for left, right in zip(nonzero_signs, nonzero_signs[1:]))
    canonical_mean = Fraction(canonical_sum, canonical_total)
    path_mean = Fraction(path_sum, path_total)
    shift = path_mean - canonical_mean
    mean_ratio = path_mean / canonical_mean
    shallow_fosd = all(value >= 0 for value in cdf)
    properties = {
        "shallow_first_order_stochastic_dominance": shallow_fosd,
        "strictly_negative_mean_depth_shift": shift < 0,
        "exactly_one_nonzero_pmf_sign_change": crossings == 1,
        "maximum_cdf_gap_equals_depth_total_variation": maximum == tv,
    }
    profile = {
        "canonical_mean_depth": encoded(canonical_mean),
        "path_frequency_mean_depth": encoded(path_mean),
        "path_minus_canonical_mean_depth": encoded(shift),
        "path_to_canonical_mean_depth_ratio": encoded(mean_ratio),
        "depth_total_variation": encoded(tv),
        "cdf_path_minus_canonical": [
            {"depth": depth, "gap": encoded(value)} for depth, value in zip(depths, cdf)
        ],
        "cdf_terminal_gap": encoded(cdf[-1]),
        "maximum_cdf_gap": encoded(maximum),
        "maximum_cdf_gap_depth": maximum_depth,
        "nonzero_pmf_sign_changes": crossings,
        "canonical_nearest_rank_median_depth": rank_from_rows(canonical_rows, 1, 2),
        "path_frequency_nearest_rank_median_depth": rank_from_rows(path_rows, 1, 2),
        "canonical_nearest_rank_p90_depth": rank_from_rows(canonical_rows, 9, 10),
        "path_frequency_nearest_rank_p90_depth": rank_from_rows(path_rows, 9, 10),
    }
    seen_expected = {
        "canonical_depth_support": [depths[0], depths[-1]],
        "canonical_depth_count": canonical_total,
        "path_frequency_depth_count": path_total,
        "canonical_depth_sum": canonical_sum,
        "path_frequency_depth_sum": path_sum,
        "canonical_mean_depth": str(canonical_mean),
        "path_frequency_mean_depth": str(path_mean),
        "path_minus_canonical_mean_depth": str(shift),
        "path_to_canonical_mean_depth_ratio": str(mean_ratio),
        "depth_total_variation": str(tv),
        "maximum_cdf_gap": str(maximum),
        "maximum_cdf_gap_depth": maximum_depth,
        "shallow_first_order_stochastic_dominance": shallow_fosd,
        "nonzero_pmf_sign_changes": crossings,
        "canonical_nearest_rank_median_depth": profile["canonical_nearest_rank_median_depth"],
        "path_frequency_nearest_rank_median_depth": profile["path_frequency_nearest_rank_median_depth"],
        "canonical_nearest_rank_p90_depth": profile["canonical_nearest_rank_p90_depth"],
        "path_frequency_nearest_rank_p90_depth": profile["path_frequency_nearest_rank_p90_depth"],
    }
    check(protocol.get("values_seen_before_declaration") == seen_expected, "seen-values disclosure mismatch")
    upstream_tv = diagnostic.get("total_variation")
    check(
        isinstance(upstream_tv, (int, float))
        and not isinstance(upstream_tv, bool)
        and math.isfinite(float(upstream_tv))
        and format(float(upstream_tv), ".17g") == encoded(tv)["decimal_17g"],
        "upstream depth TV does not roundtrip",
    )
    classification = PASS if all(properties.values()) else NOT_VERIFIED
    check(classification in protocol["ordered_classification"], "classification outside protocol")
    return {
        "protocol": RECEIPT_PROTOCOL,
        "status": "TREE_LINEARIZATION_DEPTH_ORDER_COROLLARY_COMPLETE",
        "classification": classification,
        "source_commit": source_commit,
        "protocol_sha256": protocol_sha,
        "producer_source_sha256": producer_sha,
        "snapshot_sha256": source["snapshot_sha256"],
        "input_sha256": {"linearization_receipt": binding["sha256"]},
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
            "canonical_unique_edge_counts": {str(depth): count for depth, count in canonical_rows},
            "path_frequency_edge_counts": {str(depth): count for depth, count in path_rows},
        },
        "exact_order_profile": profile,
        "deterministic_properties": properties,
        "cdf_terminal_gap_is_exactly_zero": True,
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


def verify(
    protocol_path: Path,
    protocol_sha: str,
    repo_root: Path,
    receipt_path: Path,
    receipt_sha: str,
    producer_source: Path,
    producer_sha: str,
    source_commit: str,
) -> dict[str, Any]:
    check(SHA40.fullmatch(source_commit) is not None, "invalid source commit")
    check(file_hash(protocol_path) == protocol_sha, "protocol SHA mismatch")
    check(file_hash(receipt_path) == receipt_sha, "receipt SHA mismatch")
    check(file_hash(producer_source) == producer_sha, "producer source SHA mismatch")
    protocol = read_object(protocol_path)
    check(protocol.get("protocol") == PROTOCOL, "protocol name mismatch")
    check(
        protocol.get("status")
        == "POST_HOC_DETERMINISTIC_COROLLARY_DECLARED_AFTER_EXPLORATORY_DERIVATION",
        "protocol status mismatch",
    )
    source_path = resolve_source(repo_root, protocol["fixed_input"])
    expected = independent_result(
        protocol,
        protocol_sha,
        source_commit,
        producer_sha,
        read_object(source_path),
    )
    observed = read_object(receipt_path)
    check(observed == expected, "receipt differs from independent derivation")
    return {
        "protocol": VERIFY_PROTOCOL,
        "status": "INDEPENDENT_TREE_LINEARIZATION_DEPTH_ORDER_PASS",
        "classification": observed["classification"],
        "source_commit": source_commit,
        "protocol_sha256": protocol_sha,
        "receipt_sha256": receipt_sha,
        "producer_source_sha256": producer_sha,
        "snapshot_sha256": observed["snapshot_sha256"],
        "path_minus_canonical_mean_depth": observed["exact_order_profile"]
        ["path_minus_canonical_mean_depth"],
        "depth_total_variation": observed["exact_order_profile"]["depth_total_variation"],
        "maximum_cdf_gap": observed["exact_order_profile"]["maximum_cdf_gap"],
        "all_verification_checks_passed": True,
        "security": {
            "imports_producer": False,
            "aggregate_receipt_only": True,
            "prospective_label_grade_outcome_prediction_values_read": False,
            "raw_senior_archives_opened": False,
            "identity_code_or_per_edge_values_written": False,
            "gpu_api_model_fit_base_update": [0, 0, 0, 0],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--protocol-sha256", required=True)
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--receipt-sha256", required=True)
    parser.add_argument("--producer-source", required=True)
    parser.add_argument("--producer-source-sha256", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    check(not output.exists(), f"output exists: {output}")
    result = verify(
        Path(args.protocol),
        args.protocol_sha256,
        Path(args.repo_root),
        Path(args.receipt),
        args.receipt_sha256,
        Path(args.producer_source),
        args.producer_source_sha256,
        args.source_commit,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + f".tmp.{os.getpid()}")
    temporary.write_text(
        json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, output)
    print(result["status"])


if __name__ == "__main__":
    main()
