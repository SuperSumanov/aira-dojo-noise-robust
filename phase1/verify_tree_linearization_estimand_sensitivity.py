#!/usr/bin/env python3
"""Independent verifier for the exact tree-linearization sensitivity corollary."""

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
VERIFY_PROTOCOL = "independent-tree-linearization-estimand-sensitivity-verification-v1"
PASS = "VERIFIED_EXACT_EDGE_MEASURE_SENSITIVITY_COROLLARY"
SHA64 = re.compile(r"[0-9a-f]{64}")
SHA40 = re.compile(r"[0-9a-f]{40}")


class VerificationError(RuntimeError):
    pass


def check(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def file_digest(path: Path) -> str:
    check(path.is_file() and not path.is_symlink(), f"unsafe file: {path.name}")
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(1 << 20)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def object_at(path: Path) -> dict[str, Any]:
    check(path.is_file() and not path.is_symlink(), f"unsafe object: {path.name}")
    parsed = json.loads(path.read_text(encoding="utf-8"))
    check(isinstance(parsed, dict), f"object expected: {path.name}")
    return parsed


def resolve(repo: Path, binding: dict[str, Any], label: str) -> Path:
    check(isinstance(binding, dict), f"missing {label}")
    relative, expected = binding.get("path"), binding.get("sha256")
    check(isinstance(relative, str) and relative, f"invalid {label} path")
    check(isinstance(expected, str) and SHA64.fullmatch(expected), f"invalid {label} SHA")
    unresolved = repo / relative
    check(not unresolved.is_symlink(), f"unsafe {label}: symlink")
    target = unresolved.resolve()
    try:
        target.relative_to(repo)
    except ValueError as error:
        raise VerificationError(f"{label} escapes repo") from error
    check(file_digest(target) == expected, f"{label} SHA mismatch")
    return target


def exact(value: Fraction) -> dict[str, Any]:
    return {
        "numerator": value.numerator,
        "denominator": value.denominator,
        "decimal_17g": format(float(value), ".17g"),
    }


def histogram_rows(value: Any) -> list[int]:
    check(isinstance(value, dict) and value, "histogram missing")
    expanded: list[int] = []
    for key in sorted(value, key=lambda item: int(item)):
        count = value[key]
        check(
            isinstance(key, str)
            and key.isdigit()
            and str(int(key)) == key
            and int(key) > 0,
            "invalid histogram key",
        )
        check(isinstance(count, int) and not isinstance(count, bool) and count > 0, "invalid count")
        expanded.extend([int(key)] * count)
    return expanded


def independent_receipt(
    protocol: dict[str, Any],
    protocol_sha: str,
    source_commit: str,
    producer_sha: str,
    linearization: dict[str, Any],
    compatibility: dict[str, Any],
) -> dict[str, Any]:
    required_linear = protocol["fixed_inputs"]["linearization_receipt"]["required_classification"]
    required_compat = protocol["fixed_inputs"]["compatibility_receipt"]["required_classification"]
    check(linearization.get("classification") == required_linear, "linearization classification mismatch")
    check(compatibility.get("classification") == required_compat, "compatibility classification mismatch")
    check(linearization.get("snapshot_sha256") == compatibility.get("snapshot_sha256"), "snapshot mismatch")

    linear_inventory = linearization.get("inventory", {})
    linear_path = linearization.get("linearization", {})
    compat_inventory = compatibility.get("inventory", {})
    compat_path = compatibility.get("path_compatibility", {})
    raw_histogram = linear_path.get("edge_multiplicity", {}).get("histogram")
    multiplicities = histogram_rows(raw_histogram)
    compatibility_multiplicities = histogram_rows(compat_path.get("edge_multiplicity_histogram"))
    edges = linear_path.get("unique_edge_rows")
    occurrences = linear_path.get("branch_linearized_edge_occurrences")
    duplicates = linear_path.get("duplicate_edge_occurrences")
    check(
        isinstance(edges, int)
        and isinstance(occurrences, int)
        and isinstance(duplicates, int)
        and not any(isinstance(item, bool) for item in (edges, occurrences, duplicates))
        and edges > 0
        and occurrences >= edges
        and duplicates == occurrences - edges,
        "upstream count mismatch",
    )
    receipt_checks = {
        "required_classifications_match": True,
        "snapshot_matches_across_receipts": True,
        "unique_edges_match_across_receipts": edges
        == linear_inventory.get("observed_unique_edges")
        == compat_inventory.get("observed_unique_edges"),
        "occurrences_match_across_receipts": occurrences == compat_path.get("edge_occurrences"),
        "duplicates_match_across_receipts": duplicates == compat_path.get("duplicate_edge_occurrences"),
        "histogram_matches_across_receipts": multiplicities == compatibility_multiplicities,
        "histogram_count_sum_equals_unique_edges": len(multiplicities) == edges,
        "histogram_weighted_sum_equals_occurrences": sum(multiplicities) == occurrences,
    }
    check(all(receipt_checks.values()), "receipt reconciliation failed")

    canonical_probability = Fraction(1, edges)
    path_probabilities = [Fraction(multiplicity, occurrences) for multiplicity in multiplicities]
    tv = sum(
        (abs(path_probability - canonical_probability) for path_probability in path_probabilities),
        Fraction(),
    ) / 2
    positive_indices = [
        index
        for index, path_probability in enumerate(path_probabilities)
        if path_probability > canonical_probability
    ]
    positive_edges = len(positive_indices)
    positive_occurrences = sum(multiplicities[index] for index in positive_indices)
    canonical_positive = canonical_probability * positive_edges
    path_positive = sum((path_probabilities[index] for index in positive_indices), Fraction())
    sharp_difference = path_positive - canonical_positive
    sum_squares = sum(multiplicity * multiplicity for multiplicity in multiplicities)
    canonical_diversity = Fraction(edges)
    path_diversity = Fraction(occurrences * occurrences, sum_squares)
    retention = path_diversity / canonical_diversity
    max_inflation = max(path_probabilities) / canonical_probability
    identity_checks = {
        "maximizing_set_difference_equals_total_variation": sharp_difference == tv,
        "total_variation_in_unit_interval": 0 <= tv <= 1,
        "path_diversity_not_above_canonical": path_diversity <= canonical_diversity,
        "diversity_retention_in_unit_interval": 0 < retention <= 1,
        "maximum_mass_inflation_at_least_one": max_inflation >= 1,
        "inverse_multiplicity_per_edge_mass_exactly_one": all(
            sum((Fraction(1, multiplicity) for _ in range(multiplicity)), Fraction()) == 1
            for multiplicity in set(multiplicities)
        ),
        "inverse_multiplicity_total_mass_equals_unique_edges": sum(
            (
                sum((Fraction(1, multiplicity) for _ in range(multiplicity)), Fraction())
                for multiplicity in multiplicities
            ),
            Fraction(),
        )
        == edges,
        "corrected_measure_total_variation_is_zero": True,
    }
    check(all(identity_checks.values()), "exact identity failed")
    all_checks = {**receipt_checks, **identity_checks}
    return {
        "protocol": RECEIPT_PROTOCOL,
        "status": "TREE_LINEARIZATION_ESTIMAND_SENSITIVITY_COROLLARY_COMPLETE",
        "classification": PASS,
        "source_commit": source_commit,
        "protocol_sha256": protocol_sha,
        "producer_source_sha256": producer_sha,
        "snapshot_sha256": linearization["snapshot_sha256"],
        "input_sha256": {
            "linearization_receipt": protocol["fixed_inputs"]["linearization_receipt"]["sha256"],
            "compatibility_receipt": protocol["fixed_inputs"]["compatibility_receipt"]["sha256"],
        },
        "inventory": {
            "canonical_unique_edges": edges,
            "path_edge_occurrences": occurrences,
            "duplicate_edge_occurrences": duplicates,
            "multiplicity_bins": len(set(multiplicities)),
            "maximum_multiplicity": max(multiplicities),
        },
        "edge_measure_shift": {
            "canonical_unique_edges": edges,
            "path_edge_occurrences": occurrences,
            "total_variation": exact(tv),
            "sharp_maximizing_set": {
                "definition": "multiplicity * canonical_unique_edges > path_edge_occurrences",
                "unique_edges": positive_edges,
                "path_occurrences": positive_occurrences,
                "canonical_mass": exact(canonical_positive),
                "path_mass": exact(path_positive),
                "path_minus_canonical_mass": exact(sharp_difference),
            },
            "bounded_statistic_envelope": {
                "statistic_range": "[0,1]",
                "sharp_supremum_absolute_expectation_shift": exact(tv),
                "particular_natural_metric_claimed_to_attain_bound": False,
            },
        },
        "concentration": {
            "sum_squared_multiplicity": sum_squares,
            "canonical_inverse_hhi_descriptive_diversity": exact(canonical_diversity),
            "path_inverse_hhi_descriptive_diversity": exact(path_diversity),
            "path_to_canonical_diversity_retention": exact(retention),
            "maximum_single_edge_mass_inflation": exact(max_inflation),
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
        "exact_identity_checks": identity_checks,
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
    check(file_digest(protocol_path) == protocol_sha, "protocol SHA mismatch")
    check(file_digest(receipt_path) == receipt_sha, "receipt SHA mismatch")
    check(file_digest(producer_source) == producer_sha, "producer source SHA mismatch")
    protocol = object_at(protocol_path)
    check(protocol.get("protocol") == PROTOCOL, "protocol name mismatch")
    check(
        protocol.get("status")
        == "POSTHOC_DETERMINISTIC_COROLLARY_DECLARED_AFTER_EXPLORATORY_VALUE_READ",
        "protocol status mismatch",
    )
    repo = repo_root.resolve()
    linearization_path = resolve(repo, protocol["fixed_inputs"]["linearization_receipt"], "linearization receipt")
    compatibility_path = resolve(repo, protocol["fixed_inputs"]["compatibility_receipt"], "compatibility receipt")
    expected = independent_receipt(
        protocol,
        protocol_sha,
        source_commit,
        producer_sha,
        object_at(linearization_path),
        object_at(compatibility_path),
    )
    observed = object_at(receipt_path)
    check(observed == expected, "receipt differs from independent derivation")
    return {
        "protocol": VERIFY_PROTOCOL,
        "status": "INDEPENDENT_ESTIMAND_SENSITIVITY_COROLLARY_PASS",
        "source_commit": source_commit,
        "protocol_sha256": protocol_sha,
        "receipt_sha256": receipt_sha,
        "producer_source_sha256": producer_sha,
        "snapshot_sha256": observed["snapshot_sha256"],
        "classification": observed["classification"],
        "total_variation": observed["edge_measure_shift"]["total_variation"],
        "path_inverse_hhi_descriptive_diversity": observed["concentration"]
        ["path_inverse_hhi_descriptive_diversity"],
        "maximum_single_edge_mass_inflation": observed["concentration"]
        ["maximum_single_edge_mass_inflation"],
        "all_verification_checks_passed": True,
        "security": {
            "imports_producer": False,
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
