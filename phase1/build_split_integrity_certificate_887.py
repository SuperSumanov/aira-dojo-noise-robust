#!/usr/bin/env python3
"""Build the result-blind 435-run split-integrity certificate."""

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


class CertificateError(RuntimeError):
    pass


SHA_RX = re.compile(r"[0-9a-f]{64}")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def read_regular(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise CertificateError(f"unsafe or missing file: {path}")
    return path.read_bytes()


def read_json(path: Path) -> tuple[bytes, dict[str, Any]]:
    raw = read_regular(path)
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CertificateError(f"invalid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise CertificateError(f"JSON is not an object: {path}")
    return raw, value


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CertificateError(message)


def verify_manifest(package: Path) -> dict[str, str]:
    if package.is_symlink() or not package.is_dir():
        raise CertificateError("unsafe package directory")
    raw = read_regular(package / "SHA256SUMS")
    rows: dict[str, str] = {}
    for line in raw.decode("utf-8").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9_.-]+)", line)
        require(match is not None, "malformed package manifest")
        digest, name = match.groups()
        require(name not in rows, "duplicate manifest entry")
        rows[name] = digest
    require(set(rows) == schema.PACKAGE_PAYLOADS, "package payload set mismatch")
    actual = {
        path.name
        for path in package.iterdir()
        if path.is_file() and path.name != "SHA256SUMS"
    }
    require(actual == schema.PACKAGE_PAYLOADS, "unexpected package file")
    for name, expected in rows.items():
        require(sha256_bytes(read_regular(package / name)) == expected, f"hash mismatch: {name}")
    return rows


def valid_hash(value: object) -> bool:
    return isinstance(value, str) and SHA_RX.fullmatch(value) is not None


def security_attestation(package: Path) -> None:
    text = read_regular(package / "access_attestation.txt").decode("utf-8")
    required = {
        "gpu_api_model_fit_base_update=0/0/0/0",
    }
    require(required <= set(text.splitlines()), "access attestation mismatch")
    require("outcome_prediction_values_read=false" in text, "blindness attestation missing")
    require("credential" in text and "=0" in text, "credential attestation missing")


def verify_common_bindings(
    package: Path,
    manifest: dict[str, str],
    bindings: dict[str, Any],
) -> None:
    require(
        bindings.get("formal_summary_sha256") == manifest["formal_summary.json"],
        "formal summary binding mismatch",
    )
    require(
        bindings.get("independent_recheck_sha256")
        == manifest["independent_recheck.json"],
        "recheck binding mismatch",
    )
    for key, value in bindings.items():
        if key.endswith("_sha256"):
            require(valid_hash(value), f"invalid binding hash: {key}")
    security_attestation(package)


def gates_are_true(value: object) -> bool:
    return (
        isinstance(value, dict)
        and bool(value)
        and all(item is True for item in value.values())
    )


def load_within(package: Path) -> dict[str, Any]:
    manifest = verify_manifest(package)
    _, summary = read_json(package / "formal_summary.json")
    _, recheck = read_json(package / "independent_recheck.json")
    _, bindings = read_json(package / "source_bindings.json")
    verify_common_bindings(package, manifest, bindings)
    require(bindings.get("source_commit") == schema.WITHIN_SOURCE_COMMIT, "within commit mismatch")
    require(bindings.get("snapshot_sha256") == schema.SNAPSHOT_SHA256, "within snapshot mismatch")
    require(
        bindings.get("protocol_sha256") == schema.WITHIN_RESULT_PROTOCOL_SHA256,
        "within protocol mismatch",
    )
    require(bindings.get("formal_root") == schema.WITHIN_FORMAL_ROOT, "within formal root mismatch")
    require(
        bindings.get("postflight_root") == schema.WITHIN_POSTFLIGHT_ROOT,
        "within postflight root mismatch",
    )
    require(
        bindings.get("postflight_logic_sha256")
        == schema.WITHIN_POSTFLIGHT_LOGIC_SHA256,
        "within postflight logic mismatch",
    )
    require(summary.get("protocol") == "prospective-identifier-erased-clone-887-formal-v1", "within result protocol mismatch")
    require(summary.get("source_commit") == schema.WITHIN_SOURCE_COMMIT, "within result commit mismatch")
    require(summary.get("snapshot_sha256") == schema.SNAPSHOT_SHA256, "within result snapshot mismatch")
    require(summary.get("observed_runs") == schema.FUTURE_RUNS, "within run count mismatch")
    require(summary.get("observed_endpoints") == schema.FUTURE_ENDPOINTS, "within endpoint count mismatch")
    coverage = summary.get("fingerprint_coverage")
    require(isinstance(coverage, (int, float)) and not isinstance(coverage, bool), "within coverage type")
    require(math.isfinite(coverage), "within coverage nonfinite")
    primary_cross_run = summary.get("primary_cross_run_pairs")
    primary_links = summary.get("primary_near_duplicate_pairs")
    strict_links = summary.get("strict_near_duplicate_pairs")
    strict_cross_run = summary.get("strict_cross_run_pairs")
    require(all(isinstance(x, int) and not isinstance(x, bool) and x >= 0 for x in (primary_cross_run, primary_links, strict_links, strict_cross_run)), "within count type")
    gate_pass = (
        coverage >= schema.MIN_COVERAGE
        and gates_are_true(summary.get("gate_checks"))
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
    expected_classification = (
        "STRICT_LINEAGE_LOCAL_PASS"
        if gate_pass and primary_cross_run == 0
        else "LOW_CROSS_RUN_ONLY"
        if gate_pass
        else "INTEGRITY_GATE_FAIL"
    )
    require(summary.get("classification") == expected_classification, "within classification mismatch")
    require(recheck.get("status") == "INDEPENDENT_RECHECK_COMPLETE", "within postflight status")
    require(recheck.get("classification") == expected_classification, "within postflight classification")
    require(recheck.get("source_commit") == schema.WITHIN_SOURCE_COMMIT, "within postflight commit")
    require(recheck.get("snapshot_sha256") == schema.SNAPSHOT_SHA256, "within postflight snapshot")
    require(recheck.get("primary_cross_run_pairs") == primary_cross_run, "within postflight primary")
    require(recheck.get("strict_cross_run_pairs") == strict_cross_run, "within postflight strict")
    require(recheck.get("producer_ab_byte_identical") is True, "within postflight producer A/B")
    require(recheck.get("verifier_ab_byte_identical") is True, "within postflight verifier A/B")
    require(recheck.get("outcomes_read") is False, "within postflight outcome access")
    require(recheck.get("prediction_values_read") is False, "within postflight prediction access")
    return {
        "package_manifest_sha256": sha256_bytes(read_regular(package / "SHA256SUMS")),
        "formal_summary_sha256": manifest["formal_summary.json"],
        "independent_recheck_sha256": manifest["independent_recheck.json"],
        "fingerprinted_endpoints": summary["fingerprinted_endpoints"],
        "fingerprint_coverage": coverage,
        "primary_links": primary_links,
        "primary_cross_run_links": primary_cross_run,
        "strict_links": strict_links,
        "strict_cross_run_links": strict_cross_run,
        "gate_pass": gate_pass,
        "zero_link_condition": gate_pass and primary_cross_run == 0,
        "source_classification": expected_classification,
    }


def load_historical(package: Path) -> dict[str, Any]:
    manifest = verify_manifest(package)
    _, summary = read_json(package / "formal_summary.json")
    _, recheck = read_json(package / "independent_recheck.json")
    _, bindings = read_json(package / "source_bindings.json")
    verify_common_bindings(package, manifest, bindings)
    require(bindings.get("source_commit") == schema.HISTORICAL_SOURCE_COMMIT, "historical commit mismatch")
    require(bindings.get("snapshot_sha256") == schema.SNAPSHOT_SHA256, "historical snapshot mismatch")
    require(
        bindings.get("protocol_sha256") == schema.HISTORICAL_RESULT_PROTOCOL_SHA256,
        "historical protocol mismatch",
    )
    require(bindings.get("formal_root") == schema.HISTORICAL_FORMAL_ROOT, "historical formal root mismatch")
    require(
        bindings.get("postflight_root") == schema.HISTORICAL_POSTFLIGHT_ROOT,
        "historical postflight root mismatch",
    )
    require(
        bindings.get("postflight_logic_sha256")
        == schema.HISTORICAL_POSTFLIGHT_LOGIC_SHA256,
        "historical postflight logic mismatch",
    )
    require(summary.get("protocol") == "historical-train-future-identifier-erased-887-extension-v1", "historical result protocol mismatch")
    require(summary.get("source_commit") == schema.HISTORICAL_SOURCE_COMMIT, "historical result commit mismatch")
    require(summary.get("snapshot_sha256") == schema.SNAPSHOT_SHA256, "historical result snapshot mismatch")
    require(summary.get("historical_endpoints") == schema.HISTORICAL_ENDPOINTS, "historical endpoint count mismatch")
    require(summary.get("historical_runs") == schema.HISTORICAL_RUNS, "historical run count mismatch")
    require(summary.get("prospective_runs") == schema.FUTURE_RUNS, "historical future run count mismatch")
    require(summary.get("prospective_endpoints") == schema.FUTURE_ENDPOINTS, "historical future endpoint mismatch")
    historical_coverage = summary.get("historical_fingerprint_coverage")
    future_coverage = summary.get("prospective_fingerprint_coverage")
    require(all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) for x in (historical_coverage, future_coverage)), "historical coverage type")
    primary_links = summary.get("primary_near_duplicate_pairs")
    strict_links = summary.get("strict_near_duplicate_pairs")
    require(all(isinstance(x, int) and not isinstance(x, bool) and x >= 0 for x in (primary_links, strict_links)), "historical count type")
    gate_pass = (
        historical_coverage >= schema.MIN_COVERAGE
        and future_coverage >= schema.MIN_COVERAGE
        and gates_are_true(summary.get("gate_checks"))
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
    expected_classification = (
        "ZERO_IDENTIFIER_ERASED_LINKS"
        if gate_pass and primary_links == 0
        else "LOW_IDENTIFIER_ERASED_OVERLAP_ONLY"
        if gate_pass
        else "INTEGRITY_GATE_FAIL"
    )
    require(summary.get("classification") == expected_classification, "historical classification mismatch")
    require(recheck.get("status") == "INDEPENDENT_RECHECK_COMPLETE", "historical postflight status")
    require(recheck.get("classification") == expected_classification, "historical postflight classification")
    require(recheck.get("source_commit") == schema.HISTORICAL_SOURCE_COMMIT, "historical postflight commit")
    require(recheck.get("snapshot_sha256") == schema.SNAPSHOT_SHA256, "historical postflight snapshot")
    require(recheck.get("primary_near_duplicate_pairs") == primary_links, "historical postflight primary")
    require(recheck.get("strict_near_duplicate_pairs") == strict_links, "historical postflight strict")
    require(recheck.get("producer_ab_byte_identical") is True, "historical postflight producer A/B")
    require(recheck.get("verifier_ab_byte_identical") is True, "historical postflight verifier A/B")
    require(recheck.get("outcomes_read") is False, "historical postflight outcome access")
    require(recheck.get("prediction_values_read") is False, "historical postflight prediction access")
    return {
        "package_manifest_sha256": sha256_bytes(read_regular(package / "SHA256SUMS")),
        "formal_summary_sha256": manifest["formal_summary.json"],
        "independent_recheck_sha256": manifest["independent_recheck.json"],
        "historical_fingerprinted_endpoints": summary["historical_fingerprinted_endpoints"],
        "historical_fingerprint_coverage": historical_coverage,
        "future_fingerprinted_endpoints": summary["prospective_fingerprinted_endpoints"],
        "future_fingerprint_coverage": future_coverage,
        "primary_links": primary_links,
        "primary_same_task_links": summary["primary_same_task_pairs"],
        "primary_cross_task_links": summary["primary_cross_task_pairs"],
        "strict_links": strict_links,
        "gate_pass": gate_pass,
        "zero_link_condition": gate_pass and primary_links == 0,
        "source_classification": expected_classification,
    }


def build(protocol_path: Path, protocol_sha: str, within: Path, historical: Path) -> dict[str, Any]:
    protocol_raw, protocol = read_json(protocol_path)
    require(sha256_bytes(protocol_raw) == protocol_sha == schema.PROTOCOL_SHA256, "certificate protocol hash mismatch")
    require(protocol.get("protocol") == schema.PROTOCOL, "certificate protocol identity mismatch")
    require(protocol.get("status") == "RESULT_BLIND_CERTIFICATE_PROTOCOL_FROZEN_INPUTS_PENDING", "certificate protocol status mismatch")
    within_result = load_within(within.resolve())
    historical_result = load_historical(historical.resolve())
    all_gates = within_result["gate_pass"] and historical_result["gate_pass"]
    both_zero = (
        all_gates
        and within_result["zero_link_condition"]
        and historical_result["zero_link_condition"]
    )
    classification = (
        schema.ZERO_CLASSIFICATION
        if both_zero
        else schema.LOW_CLASSIFICATION
        if all_gates
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
        "within_future": within_result,
        "historical_to_future": historical_result,
        "certificate_gates": {
            "within_future_integrity": within_result["gate_pass"],
            "historical_to_future_integrity": historical_result["gate_pass"],
            "within_future_zero_cross_run_links": within_result["zero_link_condition"],
            "historical_to_future_zero_links": historical_result["zero_link_condition"],
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


def write_new(path: Path, value: dict[str, Any]) -> None:
    if path.exists() or not path.parent.is_dir() or path.parent.is_symlink():
        raise CertificateError("unsafe output path")
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
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = build(
            args.protocol,
            args.expect_protocol_sha256,
            args.within_package,
            args.historical_package,
        )
        write_new(args.output.resolve(), result)
        print(json.dumps({"classification": result["classification"]}, sort_keys=True))
        return 0
    except (OSError, CertificateError, ValueError, TypeError, ZeroDivisionError) as exc:
        print(f"SPLIT_INTEGRITY_CERTIFICATE_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
