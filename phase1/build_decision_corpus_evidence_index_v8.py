#!/usr/bin/env python3
"""Build Decision-Corpus Evidence Index v8 from two frozen split certificates."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any


class BuildError(RuntimeError):
    """Raised when a frozen evidence or security binding fails."""


PROTOCOL_SHA256 = "a463a6e7ede5bb9b46dbe6081ae46d26d6c2e8410e858acf9d022c642633deda"
INDEX_PROTOCOL = "decision_corpus_evidence_index_v8"
SPLIT_GATE_NAMES = {
    "historical_to_future_integrity",
    "historical_to_future_zero_links",
    "independent_postflights_passed",
    "same_future_snapshot_population",
    "same_representation_and_threshold",
    "within_future_integrity",
    "within_future_zero_cross_run_links",
}
RELEASE_GATE_NAMES = {
    "historical_fingerprint_coverage",
    "prospective_fingerprint_coverage",
    "prospective_affected_fraction",
    "cross_task_prospective_affected_fraction",
    "large_multitask_components",
    "bipartite_join_self_check",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise BuildError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalized_bytes(path: Path) -> bytes:
    try:
        text = path.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise BuildError(f"file is not UTF-8: {path}") from error
    if text.startswith("\ufeff"):
        text = text[1:]
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def normalized_sha256(path: Path) -> str:
    return hashlib.sha256(normalized_bytes(path)).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(normalized_bytes(path).decode("utf-8"))
    except json.JSONDecodeError as error:
        raise BuildError(f"invalid JSON: {path}") from error
    require(isinstance(payload, dict), f"JSON root is not an object: {path}")
    return payload


def resolve_relative(repo_root: Path, relative: str, *, suffix: str | None = None) -> Path:
    value = Path(relative)
    require(not value.is_absolute() and ".." not in value.parts, f"unsafe path: {relative}")
    raw = repo_root / value
    require(not raw.is_symlink(), f"symlink input is forbidden: {relative}")
    resolved = raw.resolve()
    try:
        resolved.relative_to(repo_root)
    except ValueError as error:
        raise BuildError(f"path escapes repository: {relative}") from error
    require(resolved.is_file() if suffix is not None else resolved.is_dir(), f"missing input: {relative}")
    if suffix is not None:
        require(resolved.suffix == suffix, f"unexpected suffix: {relative}")
    return resolved


def parse_manifest(root: Path) -> tuple[Path, dict[str, str]]:
    manifest = root / "SHA256SUMS"
    require(manifest.is_file() and not manifest.is_symlink(), f"missing manifest: {root}")
    rows: dict[str, str] = {}
    for line_number, line in enumerate(
        normalized_bytes(manifest).decode("utf-8").splitlines(), 1
    ):
        match = re.fullmatch(r"([0-9a-f]{64})  ([^/\\]+)", line)
        require(match is not None, f"malformed manifest line {line_number}: {root}")
        digest, name = match.groups()
        require(name not in rows and name != "SHA256SUMS", f"duplicate manifest member: {name}")
        candidate = root / name
        require(candidate.is_file() and not candidate.is_symlink(), f"missing manifest member: {name}")
        require(sha256_file(candidate) == digest, f"manifest hash mismatch: {name}")
        rows[name] = digest
    actual = {
        path.name
        for path in root.iterdir()
        if path.is_file() and not path.is_symlink() and path.name != "SHA256SUMS"
    }
    require(set(rows) == actual, f"manifest membership mismatch: {root}")
    return manifest, rows


def merged_without_overwrite(
    source: dict[str, Any], additions: dict[str, Any], label: str
) -> dict[str, Any]:
    overlap = set(source).intersection(additions)
    require(not overlap, f"v8 would overwrite source {label}: {sorted(overlap)}")
    return {**copy.deepcopy(source), **copy.deepcopy(additions)}


def verify_source_v7(repo_root: Path, protocol: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    frozen = protocol["source_v7"]
    path = resolve_relative(repo_root, frozen["path"], suffix=".json")
    require(sha256_file(path) == frozen["sha256"], "source v7 SHA mismatch")
    source = read_json(path)
    require(source.get("protocol") == frozen["protocol"], "source v7 protocol mismatch")
    require(source.get("status") == frozen["status"], "source v7 status mismatch")
    entries = source.get("entries")
    require(isinstance(entries, list) and len(entries) == frozen["entry_count"], "source v7 entry count")
    require(len({entry.get("name") for entry in entries}) == len(entries), "source v7 entry names")
    require(isinstance(source.get("scope"), dict), "source v7 scope missing")
    require(isinstance(source.get("reporting_contract"), dict), "source v7 reporting contract missing")
    return path, source


def verify_physical_split(
    repo_root: Path, protocol: dict[str, Any]
) -> tuple[Path, dict[str, Any], dict[str, Any], dict[str, Any], dict[str, str]]:
    frozen = protocol["physical_run_split_certificate"]
    root = resolve_relative(repo_root, frozen["root"])
    manifest, rows = parse_manifest(root)
    require(sha256_file(manifest) == frozen["manifest_sha256"], "split manifest SHA mismatch")
    require(rows == frozen["required_files"], "split package membership or SHA drift")
    certificate = read_json(root / "certificate.json")
    independent = read_json(root / "independent_verification.json")
    bindings = read_json(root / "source_bindings.json")
    require(certificate.get("protocol") == "decision-corpus-split-integrity-certificate-887-v1", "split protocol")
    require(certificate.get("status") == "PROVISIONAL_SPLIT_INTEGRITY_CERTIFICATE_BUILD_COMPLETE", "split status")
    require(certificate.get("classification") == frozen["required_classification"], "split classification")
    require(certificate.get("snapshot_sha256") == frozen["snapshot_sha256"], "split snapshot")
    split_gates = certificate.get("certificate_gates")
    require(isinstance(split_gates, dict) and set(split_gates) == SPLIT_GATE_NAMES, "split gate membership")
    require(all(value is True for value in split_gates.values()), "split certificate gate failed")
    require(certificate.get("future_population") == {"closure": False, "endpoints": 11906, "runs": 435}, "split future population")
    require(certificate.get("historical_population") == {"endpoints": 5519, "runs": 333}, "split historical population")
    security = certificate.get("security", {})
    require(security.get("prospective_label_outcome_prediction_values_read") is False, "split prospective values read")
    require(security.get("raw_corpus_or_archive_reopened") is False, "split raw corpus reopened")
    require(security.get("task_run_card_code_or_edge_identities_read") is False, "split identities read")
    require(security.get("gpu_api_model_fit_base_update") == [0, 0, 0, 0], "split resource contract")
    require(independent.get("status") == "INDEPENDENT_SPLIT_INTEGRITY_CERTIFICATE_VERIFIED", "split independent status")
    require(independent.get("classification") == certificate["classification"], "split independent classification")
    require(independent.get("snapshot_sha256") == frozen["snapshot_sha256"], "split independent snapshot")
    require(independent.get("certificate_sha256") == rows["certificate.json"], "split independent certificate SHA")
    require(independent.get("imports_builder") is False, "split verifier imported builder")
    require(independent.get("prospective_outcomes_or_prediction_values_read") is False, "split verifier values read")
    require(independent.get("gpu_api_model_fit_base_update") == [0, 0, 0, 0], "split verifier resources")
    require(bindings.get("certificate_sha256") == rows["certificate.json"], "split binding certificate SHA")
    require(bindings.get("independent_verification_sha256") == rows["independent_verification.json"], "split binding verifier SHA")
    require(bindings.get("snapshot_sha256") == frozen["snapshot_sha256"], "split binding snapshot")
    return root, certificate, independent, bindings, rows


def parse_access_attestation(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in normalized_bytes(path).decode("utf-8").splitlines():
        require(line.count("=") == 1, "malformed access attestation")
        key, value = line.split("=", 1)
        require(key and key not in values, "duplicate access attestation key")
        values[key] = value
    return values


def verify_release_package(
    repo_root: Path, protocol: dict[str, Any]
) -> tuple[Path, dict[str, Any], dict[str, Any], dict[str, Any], dict[str, str], str]:
    frozen = protocol["complete_release_temporal_package"]
    package_protocol_path = resolve_relative(
        repo_root, frozen["package_protocol_path"], suffix=".json"
    )
    require(sha256_file(package_protocol_path) == frozen["package_protocol_sha256"], "package protocol SHA")
    package_protocol = read_json(package_protocol_path)
    require(package_protocol.get("status") == "RESULT_BLIND_PACKAGE_PROTOCOL_FROZEN", "package protocol status")
    root = resolve_relative(repo_root, frozen["root"])
    manifest, rows = parse_manifest(root)
    require(set(rows) == set(frozen["required_files"]), "release package membership drift")
    summary = read_json(root / "formal_summary.json")
    independent = read_json(root / "independent_recheck.json")
    bindings = read_json(root / "source_bindings.json")
    classification = summary.get("classification")
    mapping = protocol["ordered_status_mapping"]
    require(classification in mapping, "unknown release classification")
    expected_status = mapping[classification]
    require(summary.get("status") == frozen["required_formal_status"], "release formal status")
    require(summary.get("evidence_index_status") == expected_status, "release evidence status mapping")
    require(summary.get("source_commit") == frozen["audit_source_commit"], "release source commit")
    require(summary.get("snapshot_sha256") == frozen["snapshot_sha256"], "release snapshot")
    population = protocol["fixed_population"]
    require(
        (
            summary.get("historical_endpoints"),
            summary.get("historical_runs"),
            summary.get("historical_tasks"),
            summary.get("prospective_endpoints"),
            summary.get("prospective_runs"),
            summary.get("prospective_tasks"),
        )
        == (
            population["historical_release_endpoints"],
            population["historical_release_runs"],
            population["historical_release_tasks"],
            population["future_endpoints"],
            population["future_runs"],
            population["future_tasks"],
        ),
        "release population drift",
    )
    gate_checks = summary.get("gate_checks")
    require(isinstance(gate_checks, dict) and set(gate_checks) == RELEASE_GATE_NAMES, "release gate membership")
    require(all(isinstance(value, bool) for value in gate_checks.values()), "release gate type")
    all_gates = summary.get("all_pre_registered_gates_passed")
    require(isinstance(all_gates, bool), "release gate type")
    require(all_gates is all(gate_checks.values()), "release all-gates summary mismatch")
    primary_links = summary.get("primary_near_duplicate_pairs")
    require(isinstance(primary_links, int) and primary_links >= 0, "release primary link count")
    if classification in {
        "ZERO_IDENTIFIER_ERASED_RELEASE_LINKS",
        "LOW_IDENTIFIER_ERASED_RELEASE_OVERLAP_WITH_EXCEPTIONS",
    }:
        require(all_gates, "successful release classification without all gates")
        require(
            (classification == "ZERO_IDENTIFIER_ERASED_RELEASE_LINKS")
            is (primary_links == 0),
            "release classification/link rule mismatch",
        )
    else:
        require(classification == "RELEASE_SPLIT_INTEGRITY_GATE_FAIL", "release failure classification")
        require(not all_gates, "release gate-fail classification without a failed gate")
    require(summary.get("prior_failed_formal_rc") == 124, "release prior formal rc")
    require(summary.get("prior_failed_deployment_rc") == 1, "release prior deployment rc")
    require(summary.get("prior_failed_result_file_created") is False, "release old result exists")
    require(summary.get("prior_failed_result_values_read") is False, "release old result read")
    require(summary.get("prospective_outcomes_read") is False, "release outcomes read")
    require(summary.get("prediction_values_read") is False, "release predictions read")
    require(summary.get("raw_senior_archives_opened") is False, "release raw archives opened")
    require(summary.get("gpu_api_model_fit_base_update") == [0, 0, 0, 0], "release resources")
    require(summary.get("claim_boundary") == protocol["claim_boundary"], "release claim boundary")
    require(independent.get("status") == frozen["required_independent_status"], "release independent status")
    for key in ("classification", "evidence_index_status", "source_commit", "snapshot_sha256"):
        require(independent.get(key) == summary.get(key), f"release independent mismatch: {key}")
    require(independent.get("producer_aggregate_matches") is True, "release aggregate mismatch")
    require(independent.get("subset_bruteforce_matches") is True, "release brute-force mismatch")
    require(independent.get("all_pre_registered_gates_passed") is all_gates, "release independent gate mismatch")
    for key in (
        "primary_candidate_pairs",
        "primary_near_duplicate_pairs",
        "strict_near_duplicate_pairs",
    ):
        require(independent.get(key) == summary.get(key), f"release independent mismatch: {key}")
    require(independent.get("raw_senior_archives_opened") is False, "release independent raw archive")
    require(independent.get("prospective_outcomes_read") is False, "release independent outcomes")
    require(independent.get("prediction_values_read") is False, "release independent predictions")
    require(independent.get("gpu_api_model_fit_base_update") == [0, 0, 0, 0], "release independent resources")
    require(independent.get("imports_packager_builder") is False, "release independent imported packager")
    require(bindings.get("status") == frozen["required_binding_status"], "release binding status")
    require(bindings.get("package_protocol_sha256") == frozen["package_protocol_sha256"], "release binding protocol SHA")
    require(bindings.get("source_commit") == frozen["audit_source_commit"], "release binding source")
    require(bindings.get("snapshot_sha256") == frozen["snapshot_sha256"], "release binding snapshot")
    require(bindings.get("prior_failed_formal_rc") == 124, "release binding old formal rc")
    require(bindings.get("prior_failed_deployment_rc") == 1, "release binding old deploy rc")
    require(bindings.get("prior_failed_result_file_created") is False, "release binding old result exists")
    require(bindings.get("prior_failed_result_values_read") is False, "release binding old result read")
    require(bindings.get("scientific_protocol_changed_in_r2") is False, "release science changed in r2")
    attestation = parse_access_attestation(root / "access_attestation.txt")
    require(
        attestation
        == {
            "raw_senior_archives_opened": "false",
            "historical_label_or_observation_fields_used": "false",
            "prospective_label_grade_outcome_prediction_values_read": "false",
            "task_run_card_code_or_edge_identities_emitted": "false",
            "gpu_api_model_fit_base_update": "0/0/0/0",
        },
        "release access attestation drift",
    )
    return root, summary, independent, bindings, rows, sha256_file(manifest)


def artifact(repo_root: Path, path: Path, assertions: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": path.relative_to(repo_root).as_posix(),
        "sha256_normalized_lf": normalized_sha256(path),
        "json_assertions": assertions,
    }


def build_index(repo_root: Path, protocol_path: Path, expected_protocol_sha256: str) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    protocol_path = protocol_path.resolve()
    require(protocol_path.is_relative_to(repo_root), "protocol outside repository")
    require(expected_protocol_sha256 == PROTOCOL_SHA256, "unexpected protocol selection")
    require(sha256_file(protocol_path) == expected_protocol_sha256, "v8 protocol SHA mismatch")
    protocol = read_json(protocol_path)
    require(protocol.get("status") == "RESULT_BLIND_EVIDENCE_INDEX_PROTOCOL_FROZEN", "v8 protocol status")
    source_path, source = verify_source_v7(repo_root, protocol)
    split_root, certificate, split_independent, split_bindings, split_rows = verify_physical_split(repo_root, protocol)
    release_root, release, release_independent, release_bindings, release_rows, release_manifest_sha = verify_release_package(repo_root, protocol)
    classification = release["classification"]
    status = protocol["ordered_status_mapping"][classification]
    split_entry = {
        "name": "physical_run_split_integrity_certificate",
        "estimand": "whether future lineage is physical-run local and the historical critic-train subset has zero identifier-erased links to the exact future snapshot",
        "supported_claim": "The two-axis, outcome-blind split certificate passed on the fixed 435-run prefix under the frozen identifier/literal-erased syntactic relation.",
        "does_not_prove": "The certificate does not cover the complete historical release, semantic equivalence, unknown pretraining data, predictor effect, search utility, or first-960 closure.",
        "artifacts": [
            artifact(
                repo_root,
                split_root / "certificate.json",
                {
                    "protocol": certificate["protocol"],
                    "status": certificate["status"],
                    "classification": certificate["classification"],
                    "snapshot_sha256": certificate["snapshot_sha256"],
                    "certificate_gates.historical_to_future_zero_links": True,
                    "certificate_gates.within_future_zero_cross_run_links": True,
                    "certificate_gates.historical_to_future_integrity": True,
                    "certificate_gates.within_future_integrity": True,
                    "future_population.runs": 435,
                    "future_population.endpoints": 11906,
                    "future_population.closure": False,
                    "security.prospective_label_outcome_prediction_values_read": False,
                    "security.gpu_api_model_fit_base_update": [0, 0, 0, 0],
                },
            ),
            artifact(
                repo_root,
                split_root / "independent_verification.json",
                {
                    "protocol": split_independent["protocol"],
                    "status": split_independent["status"],
                    "classification": split_independent["classification"],
                    "certificate_sha256": split_rows["certificate.json"],
                    "imports_builder": False,
                    "prospective_outcomes_or_prediction_values_read": False,
                },
            ),
            artifact(
                repo_root,
                split_root / "source_bindings.json",
                {
                    "source_commit": split_bindings["source_commit"],
                    "snapshot_sha256": split_bindings["snapshot_sha256"],
                    "certificate_sha256": split_rows["certificate.json"],
                    "independent_verification_sha256": split_rows["independent_verification.json"],
                    "formal_sha256sums_file_sha256": split_bindings["formal_sha256sums_file_sha256"],
                    "deployment_sha256sums_file_sha256": split_bindings["deployment_sha256sums_file_sha256"],
                },
            ),
        ],
    }
    if classification == "ZERO_IDENTIFIER_ERASED_RELEASE_LINKS":
        release_claim = "No links were found between the complete byte-reproducible v11 release and the fixed 435-run future prefix under the frozen identifier/literal-erased syntactic relation and primary threshold."
    elif classification == "LOW_IDENTIFIER_ERASED_RELEASE_OVERLAP_WITH_EXCEPTIONS":
        release_claim = "The complete-release temporal audit passed its integrity gates with explicit nonzero identifier/literal-erased overlap exceptions."
    else:
        release_claim = "The complete-release temporal audit artifact is preserved, but its pre-registered split-integrity gate failed."
    release_entry = {
        "name": "complete_release_temporal_overlap_certificate",
        "estimand": "identifier/literal-erased syntactic overlap between the complete byte-reproducible v11 release and the exact future snapshot",
        "supported_claim": release_claim,
        "does_not_prove": "This aggregate certificate does not prove semantic-clone absence, unknown-pretraining decontamination, all-source independence, predictor accuracy or effect, search utility, causal independence, or first-960 closure; strict sensitivity cannot rescue primary.",
        "artifacts": [
            artifact(
                repo_root,
                release_root / "formal_summary.json",
                {
                    "protocol": release["protocol"],
                    "status": release["status"],
                    "classification": classification,
                    "evidence_index_status": status,
                    "source_commit": release["source_commit"],
                    "snapshot_sha256": release["snapshot_sha256"],
                    "historical_endpoints": 16012,
                    "historical_runs": 667,
                    "historical_tasks": 25,
                    "prospective_endpoints": 11906,
                    "prospective_runs": 435,
                    "prospective_tasks": 34,
                    "all_pre_registered_gates_passed": release["all_pre_registered_gates_passed"],
                    "prior_failed_formal_rc": 124,
                    "prior_failed_deployment_rc": 1,
                    "prior_failed_result_file_created": False,
                    "prior_failed_result_values_read": False,
                    "prospective_outcomes_read": False,
                    "prediction_values_read": False,
                    "gpu_api_model_fit_base_update": [0, 0, 0, 0],
                },
            ),
            artifact(
                repo_root,
                release_root / "independent_recheck.json",
                {
                    "protocol": release_independent["protocol"],
                    "status": release_independent["status"],
                    "classification": classification,
                    "evidence_index_status": status,
                    "producer_aggregate_matches": True,
                    "subset_bruteforce_matches": True,
                    "all_pre_registered_gates_passed": release["all_pre_registered_gates_passed"],
                    "imports_packager_builder": False,
                    "prospective_outcomes_read": False,
                    "prediction_values_read": False,
                },
            ),
            artifact(
                repo_root,
                release_root / "source_bindings.json",
                {
                    "protocol": release_bindings["protocol"],
                    "status": release_bindings["status"],
                    "package_protocol_sha256": protocol["complete_release_temporal_package"]["package_protocol_sha256"],
                    "source_commit": release["source_commit"],
                    "snapshot_sha256": release["snapshot_sha256"],
                    "prior_failed_formal_rc": 124,
                    "prior_failed_deployment_rc": 1,
                    "prior_failed_result_file_created": False,
                    "prior_failed_result_values_read": False,
                    "scientific_protocol_changed_in_r2": False,
                },
            ),
        ],
    }
    additions = [split_entry, release_entry]
    require([entry["name"] for entry in additions] == protocol["append_entry_order"], "entry order drift")
    scope_additions = {
        "physical_run_split_integrity_certificate_bound": True,
        "complete_release_temporal_overlap_certificate_bound": True,
        "complete_release_temporal_classification": classification,
        "complete_release_temporal_primary_gate_passed": release["all_pre_registered_gates_passed"],
        "complete_release_population_endpoints": 16012,
        "future_snapshot_runs_for_temporal_certificate": 435,
        "first960_or_closure_completed_by_v8": False,
    }
    reporting_additions = {
        "fixed_syntactic_complete_release_zero_link_language_allowed": classification == "ZERO_IDENTIFIER_ERASED_RELEASE_LINKS",
        "qualified_complete_release_exception_language_required": classification == "LOW_IDENTIFIER_ERASED_RELEASE_OVERLAP_WITH_EXCEPTIONS",
        "complete_release_temporal_gate_failure_language_required": classification == "RELEASE_SPLIT_INTEGRITY_GATE_FAIL",
        "semantic_clone_or_pretraining_decontamination_language_allowed": False,
        "predictor_effect_or_search_utility_language_allowed_by_v8": False,
        "strict_sensitivity_can_rescue_primary": False,
    }
    return {
        "protocol": INDEX_PROTOCOL,
        "status": status,
        "source_v7_index": {
            "path": source_path.relative_to(repo_root).as_posix(),
            "sha256": sha256_file(source_path),
            "entries_inherited_without_modification": len(source["entries"]),
        },
        "v8_protocol": {
            "path": protocol_path.relative_to(repo_root).as_posix(),
            "sha256": expected_protocol_sha256,
        },
        "temporal_split_extension": {
            "classification": classification,
            "ordered_status": status,
            "snapshot_sha256": protocol["complete_release_temporal_package"]["snapshot_sha256"],
            "physical_split_manifest_sha256": protocol["physical_run_split_certificate"]["manifest_sha256"],
            "complete_release_manifest_sha256": release_manifest_sha,
            "complete_release_manifest_members": copy.deepcopy(release_rows),
            "source_v7_read_only": True,
            "source_v7_entries_removed_or_modified": False,
            "strict_sensitivity_can_rescue_primary": False,
        },
        "scope": merged_without_overwrite(source["scope"], scope_additions, "scope"),
        "reporting_contract": merged_without_overwrite(
            source["reporting_contract"], reporting_additions, "reporting contract"
        ),
        "entries": copy.deepcopy(source["entries"]) + additions,
    }


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    require(not path.exists(), f"output already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--expect-protocol-sha256", required=True)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    payload = build_index(args.repo_root, args.protocol, args.expect_protocol_sha256)
    atomic_json(args.out.resolve(), payload)
    print(payload["status"])


if __name__ == "__main__":
    main()
