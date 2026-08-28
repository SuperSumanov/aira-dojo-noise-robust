#!/usr/bin/env python3
"""Independent verifier for the 435-run split-integrity certificate."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
from pathlib import Path
from typing import Any

from phase1 import split_integrity_certificate_887_schema as schema


class VerificationError(RuntimeError):
    pass


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def regular(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise VerificationError(f"unsafe file: {path}")
    return path.read_bytes()


def object_at(path: Path) -> tuple[bytes, dict[str, Any]]:
    raw = regular(path)
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VerificationError(f"invalid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise VerificationError(f"non-object JSON: {path}")
    return raw, value


def check(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def package(package_path: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], str]:
    root = package_path.resolve()
    check(root.is_dir() and not root.is_symlink(), "unsafe package")
    manifest_raw = regular(root / "SHA256SUMS")
    manifest: dict[str, str] = {}
    for line in manifest_raw.decode("utf-8").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9_.-]+)", line)
        check(match is not None, "bad manifest row")
        value, name = match.groups()
        check(name not in manifest, "duplicate manifest row")
        manifest[name] = value
    check(set(manifest) == schema.PACKAGE_PAYLOADS, "manifest payload mismatch")
    actual = {
        path.name
        for path in root.iterdir()
        if path.is_file() and path.name != "SHA256SUMS"
    }
    check(actual == schema.PACKAGE_PAYLOADS, "package files mismatch")
    for name, expected in manifest.items():
        check(digest(regular(root / name)) == expected, f"package hash mismatch: {name}")
    _, summary = object_at(root / "formal_summary.json")
    _, recheck = object_at(root / "independent_recheck.json")
    _, bindings = object_at(root / "source_bindings.json")
    check(bindings.get("formal_summary_sha256") == manifest["formal_summary.json"], "summary binding mismatch")
    check(bindings.get("independent_recheck_sha256") == manifest["independent_recheck.json"], "recheck binding mismatch")
    access = regular(root / "access_attestation.txt").decode("utf-8")
    check("outcome_prediction_values_read=false" in access, "outcome access attestation missing")
    check("gpu_api_model_fit_base_update=0/0/0/0" in access, "resource attestation missing")
    check("credential" in access and "=0" in access, "credential attestation missing")
    return summary, recheck, bindings, digest(manifest_raw)


def all_true(value: object) -> bool:
    return isinstance(value, dict) and bool(value) and all(v is True for v in value.values())


def nonnegative_integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def finite_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def within_view(root: Path) -> dict[str, Any]:
    summary, recheck, bindings, manifest_sha = package(root)
    check(bindings.get("source_commit") == schema.WITHIN_SOURCE_COMMIT, "within binding commit")
    check(bindings.get("snapshot_sha256") == schema.SNAPSHOT_SHA256, "within binding snapshot")
    check(bindings.get("protocol_sha256") == schema.WITHIN_RESULT_PROTOCOL_SHA256, "within binding protocol")
    check(bindings.get("formal_root") == schema.WITHIN_FORMAL_ROOT, "within binding formal root")
    check(bindings.get("postflight_root") == schema.WITHIN_POSTFLIGHT_ROOT, "within binding postflight root")
    check(bindings.get("postflight_logic_sha256") == schema.WITHIN_POSTFLIGHT_LOGIC_SHA256, "within binding postflight logic")
    check(summary.get("protocol") == "prospective-identifier-erased-clone-887-formal-v1", "within protocol")
    check(summary.get("source_commit") == schema.WITHIN_SOURCE_COMMIT, "within commit")
    check(summary.get("snapshot_sha256") == schema.SNAPSHOT_SHA256, "within snapshot")
    check(summary.get("observed_runs") == schema.FUTURE_RUNS, "within runs")
    check(summary.get("observed_endpoints") == schema.FUTURE_ENDPOINTS, "within endpoints")
    coverage = summary.get("fingerprint_coverage")
    primary = summary.get("primary_near_duplicate_pairs")
    cross_run = summary.get("primary_cross_run_pairs")
    strict = summary.get("strict_near_duplicate_pairs")
    strict_cross = summary.get("strict_cross_run_pairs")
    check(finite_number(coverage), "within coverage")
    check(all(nonnegative_integer(value) for value in (primary, cross_run, strict, strict_cross)), "within counts")
    passed = (
        coverage >= schema.MIN_COVERAGE
        and all_true(summary.get("gate_checks"))
        and summary.get("strong_low_fuzzy_clone_support") is True
        and summary.get("producer_ab_byte_identical") is True
        and summary.get("verifier_ab_byte_identical") is True
        and summary.get("independent_aggregate_matches") is True
        and summary.get("subset_bruteforce_matches") is True
        and summary.get("prospective_outcomes_read") is False
        and summary.get("prediction_values_read") is False
        and summary.get("semantic_equivalence_proven") is False
        and summary.get("gpu_api_model_fit_base_update") == [0, 0, 0, 0]
    )
    classification = (
        "STRICT_LINEAGE_LOCAL_PASS"
        if passed and cross_run == 0
        else "LOW_CROSS_RUN_ONLY"
        if passed
        else "INTEGRITY_GATE_FAIL"
    )
    check(summary.get("classification") == classification, "within classification")
    check(recheck.get("status") == "INDEPENDENT_RECHECK_COMPLETE", "within recheck status")
    check(recheck.get("classification") == classification, "within recheck class")
    check(recheck.get("source_commit") == schema.WITHIN_SOURCE_COMMIT, "within recheck commit")
    check(recheck.get("snapshot_sha256") == schema.SNAPSHOT_SHA256, "within recheck snapshot")
    check(recheck.get("primary_cross_run_pairs") == cross_run, "within recheck primary")
    check(recheck.get("strict_cross_run_pairs") == strict_cross, "within recheck strict")
    check(recheck.get("producer_ab_byte_identical") is True, "within recheck producer")
    check(recheck.get("verifier_ab_byte_identical") is True, "within recheck verifier")
    check(recheck.get("outcomes_read") is False, "within recheck outcome access")
    check(recheck.get("prediction_values_read") is False, "within recheck prediction access")
    return {
        "package_manifest_sha256": manifest_sha,
        "formal_summary_sha256": bindings["formal_summary_sha256"],
        "independent_recheck_sha256": bindings["independent_recheck_sha256"],
        "fingerprinted_endpoints": summary["fingerprinted_endpoints"],
        "fingerprint_coverage": coverage,
        "primary_links": primary,
        "primary_cross_run_links": cross_run,
        "strict_links": strict,
        "strict_cross_run_links": strict_cross,
        "gate_pass": passed,
        "zero_link_condition": passed and cross_run == 0,
        "source_classification": classification,
    }


def historical_view(root: Path) -> dict[str, Any]:
    summary, recheck, bindings, manifest_sha = package(root)
    check(bindings.get("source_commit") == schema.HISTORICAL_SOURCE_COMMIT, "historical binding commit")
    check(bindings.get("snapshot_sha256") == schema.SNAPSHOT_SHA256, "historical binding snapshot")
    check(bindings.get("protocol_sha256") == schema.HISTORICAL_RESULT_PROTOCOL_SHA256, "historical binding protocol")
    check(bindings.get("formal_root") == schema.HISTORICAL_FORMAL_ROOT, "historical binding formal root")
    check(bindings.get("postflight_root") == schema.HISTORICAL_POSTFLIGHT_ROOT, "historical binding postflight root")
    check(bindings.get("postflight_logic_sha256") == schema.HISTORICAL_POSTFLIGHT_LOGIC_SHA256, "historical binding postflight logic")
    check(summary.get("protocol") == "historical-train-future-identifier-erased-887-extension-v1", "historical protocol")
    check(summary.get("source_commit") == schema.HISTORICAL_SOURCE_COMMIT, "historical commit")
    check(summary.get("snapshot_sha256") == schema.SNAPSHOT_SHA256, "historical snapshot")
    check(summary.get("historical_endpoints") == schema.HISTORICAL_ENDPOINTS, "historical endpoints")
    check(summary.get("historical_runs") == schema.HISTORICAL_RUNS, "historical runs")
    check(summary.get("prospective_runs") == schema.FUTURE_RUNS, "historical future runs")
    check(summary.get("prospective_endpoints") == schema.FUTURE_ENDPOINTS, "historical future endpoints")
    historical_coverage = summary.get("historical_fingerprint_coverage")
    future_coverage = summary.get("prospective_fingerprint_coverage")
    primary = summary.get("primary_near_duplicate_pairs")
    strict = summary.get("strict_near_duplicate_pairs")
    check(finite_number(historical_coverage) and finite_number(future_coverage), "historical coverage")
    check(nonnegative_integer(primary) and nonnegative_integer(strict), "historical counts")
    passed = (
        historical_coverage >= schema.MIN_COVERAGE
        and future_coverage >= schema.MIN_COVERAGE
        and all_true(summary.get("gate_checks"))
        and summary.get("strong_low_identifier_erased_overlap_support") is True
        and summary.get("producer_ab_byte_identical") is True
        and summary.get("verifier_ab_byte_identical") is True
        and summary.get("independent_aggregate_matches") is True
        and summary.get("subset_bruteforce_matches") is True
        and summary.get("historical_label_or_observation_fields_used") is False
        and summary.get("prospective_outcomes_read") is False
        and summary.get("prediction_values_read") is False
        and summary.get("semantic_equivalence_proven") is False
        and summary.get("pretraining_contamination_absence_proven") is False
        and summary.get("gpu_api_model_fit_base_update") == [0, 0, 0, 0]
    )
    classification = (
        "ZERO_IDENTIFIER_ERASED_LINKS"
        if passed and primary == 0
        else "LOW_IDENTIFIER_ERASED_OVERLAP_ONLY"
        if passed
        else "INTEGRITY_GATE_FAIL"
    )
    check(summary.get("classification") == classification, "historical classification")
    check(recheck.get("status") == "INDEPENDENT_RECHECK_COMPLETE", "historical recheck status")
    check(recheck.get("classification") == classification, "historical recheck class")
    check(recheck.get("source_commit") == schema.HISTORICAL_SOURCE_COMMIT, "historical recheck commit")
    check(recheck.get("snapshot_sha256") == schema.SNAPSHOT_SHA256, "historical recheck snapshot")
    check(recheck.get("primary_near_duplicate_pairs") == primary, "historical recheck primary")
    check(recheck.get("strict_near_duplicate_pairs") == strict, "historical recheck strict")
    check(recheck.get("producer_ab_byte_identical") is True, "historical recheck producer")
    check(recheck.get("verifier_ab_byte_identical") is True, "historical recheck verifier")
    check(recheck.get("outcomes_read") is False, "historical recheck outcome access")
    check(recheck.get("prediction_values_read") is False, "historical recheck prediction access")
    return {
        "package_manifest_sha256": manifest_sha,
        "formal_summary_sha256": bindings["formal_summary_sha256"],
        "independent_recheck_sha256": bindings["independent_recheck_sha256"],
        "historical_fingerprinted_endpoints": summary["historical_fingerprinted_endpoints"],
        "historical_fingerprint_coverage": historical_coverage,
        "future_fingerprinted_endpoints": summary["prospective_fingerprinted_endpoints"],
        "future_fingerprint_coverage": future_coverage,
        "primary_links": primary,
        "primary_same_task_links": summary["primary_same_task_pairs"],
        "primary_cross_task_links": summary["primary_cross_task_pairs"],
        "strict_links": strict,
        "gate_pass": passed,
        "zero_link_condition": passed and primary == 0,
        "source_classification": classification,
    }


def expected_certificate(within: dict[str, Any], historical: dict[str, Any]) -> dict[str, Any]:
    both_pass = within["gate_pass"] and historical["gate_pass"]
    both_zero = both_pass and within["zero_link_condition"] and historical["zero_link_condition"]
    classification = (
        schema.ZERO_CLASSIFICATION
        if both_zero
        else schema.LOW_CLASSIFICATION
        if both_pass
        else schema.FAIL_CLASSIFICATION
    )
    return {
        "protocol": schema.PROTOCOL,
        "status": schema.STATUS,
        "classification": classification,
        "snapshot_sha256": schema.SNAPSHOT_SHA256,
        "representation": schema.REPRESENTATION,
        "primary_jaccard": [17, 20],
        "strict_sensitivity_jaccard": [19, 20],
        "future_population": {
            "runs": schema.FUTURE_RUNS,
            "endpoints": schema.FUTURE_ENDPOINTS,
            "closure": False,
        },
        "historical_population": {
            "runs": schema.HISTORICAL_RUNS,
            "endpoints": schema.HISTORICAL_ENDPOINTS,
        },
        "within_future": within,
        "historical_to_future": historical,
        "certificate_gates": {
            "within_future_integrity": within["gate_pass"],
            "historical_to_future_integrity": historical["gate_pass"],
            "within_future_zero_cross_run_links": within["zero_link_condition"],
            "historical_to_future_zero_links": historical["zero_link_condition"],
            "same_future_snapshot_population": True,
            "same_representation_and_threshold": True,
            "independent_postflights_passed": True,
        },
        "claim_boundary": {
            "provisional_until_first960_and_closure": True,
            "semantic_clone_absence_proven": False,
            "pretraining_contamination_absence_proven": False,
            "all_possible_historical_training_sources_covered": False,
            "unfingerprintable_endpoints_certified": False,
            "predictor_effect_accuracy_or_search_utility_computed": False,
            "new_clone_detection_method_claimed": False,
        },
        "security": {
            "raw_corpus_or_archive_reopened": False,
            "task_run_card_code_or_edge_identities_read": False,
            "prospective_label_outcome_prediction_values_read": False,
            "gpu_api_model_fit_base_update": [0, 0, 0, 0],
            "randomness_used": False,
        },
    }


def verify(
    protocol_path: Path,
    protocol_sha: str,
    within_package: Path,
    historical_package: Path,
    result_path: Path,
    result_sha: str,
) -> dict[str, Any]:
    protocol_raw, protocol = object_at(protocol_path)
    check(digest(protocol_raw) == protocol_sha == schema.PROTOCOL_SHA256, "protocol hash")
    check(protocol.get("protocol") == schema.PROTOCOL, "protocol identity")
    result_raw, result = object_at(result_path)
    check(digest(result_raw) == result_sha, "result hash")
    within = within_view(within_package)
    historical = historical_view(historical_package)
    expected = expected_certificate(within, historical)
    check(result == expected, "certificate differs from independent reconstruction")
    return {
        "protocol": "independent-decision-corpus-split-integrity-certificate-887-v1",
        "status": "INDEPENDENT_SPLIT_INTEGRITY_CERTIFICATE_VERIFIED",
        "classification": expected["classification"],
        "snapshot_sha256": schema.SNAPSHOT_SHA256,
        "certificate_sha256": result_sha,
        "within_package_manifest_sha256": within["package_manifest_sha256"],
        "historical_package_manifest_sha256": historical["package_manifest_sha256"],
        "imports_builder": False,
        "raw_corpus_or_archive_reopened": False,
        "identity_values_read": False,
        "prospective_outcomes_or_prediction_values_read": False,
        "gpu_api_model_fit_base_update": [0, 0, 0, 0],
        "randomness_used": False,
    }


def write_new(path: Path, value: dict[str, Any]) -> None:
    if path.exists() or not path.parent.is_dir() or path.parent.is_symlink():
        raise VerificationError("unsafe output")
    temporary = path.with_name(path.name + f".tmp-{os.getpid()}")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--expect-protocol-sha256", required=True)
    parser.add_argument("--within-package", required=True, type=Path)
    parser.add_argument("--historical-package", required=True, type=Path)
    parser.add_argument("--certificate", required=True, type=Path)
    parser.add_argument("--expect-certificate-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        receipt = verify(
            args.protocol,
            args.expect_protocol_sha256,
            args.within_package,
            args.historical_package,
            args.certificate,
            args.expect_certificate_sha256,
        )
        write_new(args.output.resolve(), receipt)
        print(json.dumps({"classification": receipt["classification"]}, sort_keys=True))
        return 0
    except (OSError, VerificationError, ValueError, TypeError, ZeroDivisionError) as exc:
        print(f"SPLIT_INTEGRITY_CERTIFICATE_VERIFY_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
