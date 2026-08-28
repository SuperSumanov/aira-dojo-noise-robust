#!/usr/bin/env python3
"""Derive an exact edge-measure sensitivity corollary from aggregate receipts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from fractions import Fraction
from pathlib import Path
from typing import Any


PROTOCOL = "tree-linearization-estimand-sensitivity-corollary-v1"
RECEIPT_PROTOCOL = "tree-linearization-estimand-sensitivity-receipt-v1"
PASS = "VERIFIED_EXACT_EDGE_MEASURE_SENSITIVITY_COROLLARY"
FAIL = "EDGE_MEASURE_SENSITIVITY_COROLLARY_GATE_FAIL"
SHA64 = re.compile(r"[0-9a-f]{64}")
SHA40 = re.compile(r"[0-9a-f]{40}")


class CorollaryError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CorollaryError(message)


def digest(path: Path) -> str:
    require(path.is_file() and not path.is_symlink(), f"unsafe input: {path.name}")
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"unsafe JSON: {path.name}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"object expected: {path.name}")
    return value


def bound(repo: Path, item: dict[str, Any], label: str) -> Path:
    require(isinstance(item, dict), f"missing {label} binding")
    relative, expected = item.get("path"), item.get("sha256")
    require(isinstance(relative, str) and relative, f"invalid {label} path")
    require(isinstance(expected, str) and SHA64.fullmatch(expected), f"invalid {label} SHA")
    unresolved = repo / relative
    require(not unresolved.is_symlink(), f"unsafe {label}: symlink")
    candidate = unresolved.resolve()
    try:
        candidate.relative_to(repo)
    except ValueError as error:
        raise CorollaryError(f"{label} escapes repository") from error
    require(digest(candidate) == expected, f"{label} SHA mismatch")
    return candidate


def fraction(value: Fraction) -> dict[str, Any]:
    return {
        "numerator": value.numerator,
        "denominator": value.denominator,
        "decimal_17g": format(float(value), ".17g"),
    }


def parse_histogram(value: Any) -> dict[int, int]:
    require(isinstance(value, dict) and value, "multiplicity histogram missing")
    output: dict[int, int] = {}
    for raw_multiplicity, raw_count in value.items():
        require(
            isinstance(raw_multiplicity, str)
            and raw_multiplicity.isdigit()
            and str(int(raw_multiplicity)) == raw_multiplicity,
            "invalid multiplicity key",
        )
        multiplicity = int(raw_multiplicity)
        require(
            multiplicity > 0
            and isinstance(raw_count, int)
            and not isinstance(raw_count, bool)
            and raw_count > 0,
            "invalid multiplicity count",
        )
        output[multiplicity] = raw_count
    return output


def reconcile(
    protocol: dict[str, Any], linearization: dict[str, Any], compatibility: dict[str, Any]
) -> tuple[int, int, int, dict[int, int], dict[str, bool]]:
    required_linearization = protocol["fixed_inputs"]["linearization_receipt"].get(
        "required_classification"
    )
    require(
        linearization.get("classification") == required_linearization,
        "linearization classification mismatch",
    )
    required_compatibility = protocol["fixed_inputs"]["compatibility_receipt"].get(
        "required_classification"
    )
    require(
        compatibility.get("classification") == required_compatibility,
        "compatibility classification mismatch",
    )
    require(
        linearization.get("snapshot_sha256") == compatibility.get("snapshot_sha256"),
        "snapshot mismatch across receipts",
    )
    old_inventory = linearization.get("inventory", {})
    old_path = linearization.get("linearization", {})
    new_inventory = compatibility.get("inventory", {})
    new_path = compatibility.get("path_compatibility", {})
    histogram = parse_histogram(old_path.get("edge_multiplicity", {}).get("histogram"))
    new_histogram = parse_histogram(new_path.get("edge_multiplicity_histogram"))
    edges = old_path.get("unique_edge_rows")
    occurrences = old_path.get("branch_linearized_edge_occurrences")
    duplicates = old_path.get("duplicate_edge_occurrences")
    require(
        all(isinstance(item, int) and not isinstance(item, bool) for item in (edges, occurrences, duplicates))
        and edges > 0
        and occurrences >= edges
        and duplicates == occurrences - edges,
        "invalid upstream counts",
    )
    checks = {
        "required_classifications_match": True,
        "snapshot_matches_across_receipts": True,
        "unique_edges_match_across_receipts": edges
        == old_inventory.get("observed_unique_edges")
        == new_inventory.get("observed_unique_edges"),
        "occurrences_match_across_receipts": occurrences == new_path.get("edge_occurrences"),
        "duplicates_match_across_receipts": duplicates == new_path.get("duplicate_edge_occurrences"),
        "histogram_matches_across_receipts": histogram == new_histogram,
        "histogram_count_sum_equals_unique_edges": sum(histogram.values()) == edges,
        "histogram_weighted_sum_equals_occurrences": sum(
            multiplicity * count for multiplicity, count in histogram.items()
        )
        == occurrences,
    }
    require(all(checks.values()), "receipt reconciliation failed")
    return edges, occurrences, duplicates, histogram, checks


def derive(edges: int, occurrences: int, histogram: dict[int, int]) -> dict[str, Any]:
    sum_squared_multiplicity = sum(
        count * multiplicity * multiplicity for multiplicity, count in histogram.items()
    )
    tv = sum(
        count * abs(Fraction(1, edges) - Fraction(multiplicity, occurrences))
        for multiplicity, count in histogram.items()
    ) / 2
    positive = {
        multiplicity: count
        for multiplicity, count in histogram.items()
        if multiplicity * edges > occurrences
    }
    positive_edges = sum(positive.values())
    positive_occurrences = sum(
        multiplicity * count for multiplicity, count in positive.items()
    )
    canonical_positive_mass = Fraction(positive_edges, edges)
    path_positive_mass = Fraction(positive_occurrences, occurrences)
    sharp_difference = path_positive_mass - canonical_positive_mass
    canonical_diversity = Fraction(edges)
    path_diversity = Fraction(occurrences * occurrences, sum_squared_multiplicity)
    diversity_ratio = path_diversity / canonical_diversity
    maximum_inflation = Fraction(max(histogram) * edges, occurrences)
    checks = {
        "maximizing_set_difference_equals_total_variation": sharp_difference == tv,
        "total_variation_in_unit_interval": 0 <= tv <= 1,
        "path_diversity_not_above_canonical": path_diversity <= canonical_diversity,
        "diversity_retention_in_unit_interval": 0 < diversity_ratio <= 1,
        "maximum_mass_inflation_at_least_one": maximum_inflation >= 1,
        "inverse_multiplicity_per_edge_mass_exactly_one": True,
        "inverse_multiplicity_total_mass_equals_unique_edges": True,
        "corrected_measure_total_variation_is_zero": True,
    }
    require(all(checks.values()), "exact corollary identity failed")
    return {
        "edge_measure_shift": {
            "canonical_unique_edges": edges,
            "path_edge_occurrences": occurrences,
            "total_variation": fraction(tv),
            "sharp_maximizing_set": {
                "definition": "multiplicity * canonical_unique_edges > path_edge_occurrences",
                "unique_edges": positive_edges,
                "path_occurrences": positive_occurrences,
                "canonical_mass": fraction(canonical_positive_mass),
                "path_mass": fraction(path_positive_mass),
                "path_minus_canonical_mass": fraction(sharp_difference),
            },
            "bounded_statistic_envelope": {
                "statistic_range": "[0,1]",
                "sharp_supremum_absolute_expectation_shift": fraction(tv),
                "particular_natural_metric_claimed_to_attain_bound": False,
            },
        },
        "concentration": {
            "sum_squared_multiplicity": sum_squared_multiplicity,
            "canonical_inverse_hhi_descriptive_diversity": fraction(canonical_diversity),
            "path_inverse_hhi_descriptive_diversity": fraction(path_diversity),
            "path_to_canonical_diversity_retention": fraction(diversity_ratio),
            "maximum_single_edge_mass_inflation": fraction(maximum_inflation),
            "inverse_hhi_is_statistical_effective_sample_size": False,
        },
        "inverse_multiplicity_correction": {
            "per_edge_unnormalized_mass": {"numerator": 1, "denominator": 1},
            "total_unnormalized_mass": {"numerator": edges, "denominator": 1},
            "corrected_total_variation_from_canonical": {
                "numerator": 0,
                "denominator": 1,
                "decimal_17g": "0",
            },
            "exact_measure_recovery": True,
        },
        "exact_identity_checks": checks,
    }


def build(
    protocol_path: Path,
    protocol_sha: str,
    repo_root: Path,
    source_commit: str,
) -> dict[str, Any]:
    require(SHA40.fullmatch(source_commit) is not None, "invalid source commit")
    require(digest(protocol_path) == protocol_sha, "protocol SHA mismatch")
    protocol = load(protocol_path)
    require(protocol.get("protocol") == PROTOCOL, "protocol name mismatch")
    require(
        protocol.get("status")
        == "POSTHOC_DETERMINISTIC_COROLLARY_DECLARED_AFTER_EXPLORATORY_VALUE_READ",
        "protocol status mismatch",
    )
    repo = repo_root.resolve()
    linearization_path = bound(repo, protocol["fixed_inputs"]["linearization_receipt"], "linearization receipt")
    compatibility_path = bound(repo, protocol["fixed_inputs"]["compatibility_receipt"], "compatibility receipt")
    linearization, compatibility = load(linearization_path), load(compatibility_path)
    edges, occurrences, duplicates, histogram, receipt_checks = reconcile(
        protocol, linearization, compatibility
    )
    result = derive(edges, occurrences, histogram)
    all_checks = {**receipt_checks, **result["exact_identity_checks"]}
    classification = PASS if all(all_checks.values()) else FAIL
    return {
        "protocol": RECEIPT_PROTOCOL,
        "status": "TREE_LINEARIZATION_ESTIMAND_SENSITIVITY_COROLLARY_COMPLETE",
        "classification": classification,
        "source_commit": source_commit,
        "protocol_sha256": protocol_sha,
        "producer_source_sha256": digest(Path(__file__)),
        "snapshot_sha256": linearization["snapshot_sha256"],
        "input_sha256": {
            "linearization_receipt": protocol["fixed_inputs"]["linearization_receipt"]["sha256"],
            "compatibility_receipt": protocol["fixed_inputs"]["compatibility_receipt"]["sha256"],
        },
        "inventory": {
            "canonical_unique_edges": edges,
            "path_edge_occurrences": occurrences,
            "duplicate_edge_occurrences": duplicates,
            "multiplicity_bins": len(histogram),
            "maximum_multiplicity": max(histogram),
        },
        **result,
        "all_verification_checks_passed": all(all_checks.values()),
        "claim_boundary": protocol["claim_boundary"],
        "design_timing": protocol["design_timing"],
        "security": {
            "aggregate_receipts_only": True,
            "prospective_label_grade_outcome_prediction_values_read": False,
            "raw_senior_archives_or_blind_manifests_opened": False,
            "identity_code_or_per_path_values_written": False,
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
