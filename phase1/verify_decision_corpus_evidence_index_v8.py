#!/usr/bin/env python3
"""Independently verify Decision-Corpus Evidence Index v8."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any


class VerificationError(RuntimeError):
    """Raised when the candidate differs from the frozen v8 contract."""


PROTOCOL_SHA256 = "a463a6e7ede5bb9b46dbe6081ae46d26d6c2e8410e858acf9d022c642633deda"
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
        raise VerificationError(message)


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
        raise VerificationError(f"file is not UTF-8: {path}") from error
    if text.startswith("\ufeff"):
        text = text[1:]
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def normalized_sha256(path: Path) -> str:
    return hashlib.sha256(normalized_bytes(path)).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(normalized_bytes(path).decode("utf-8"))
    except json.JSONDecodeError as error:
        raise VerificationError(f"invalid JSON: {path}") from error
    require(isinstance(value, dict), f"JSON root is not an object: {path}")
    return value


def safe_file(repo_root: Path, relative: str, suffix: str) -> Path:
    value = Path(relative)
    require(not value.is_absolute() and ".." not in value.parts, f"unsafe path: {relative}")
    raw = repo_root / value
    require(not raw.is_symlink(), f"symlink input: {relative}")
    path = raw.resolve()
    try:
        path.relative_to(repo_root)
    except ValueError as error:
        raise VerificationError(f"path escapes repository: {relative}") from error
    require(path.is_file() and path.suffix == suffix, f"missing input: {relative}")
    return path


def safe_root(repo_root: Path, relative: str) -> Path:
    value = Path(relative)
    require(not value.is_absolute() and ".." not in value.parts, f"unsafe root: {relative}")
    raw = repo_root / value
    require(not raw.is_symlink(), f"symlink root: {relative}")
    path = raw.resolve()
    try:
        path.relative_to(repo_root)
    except ValueError as error:
        raise VerificationError(f"root escapes repository: {relative}") from error
    require(path.is_dir(), f"missing root: {relative}")
    return path


def manifest_rows(root: Path) -> tuple[Path, dict[str, str]]:
    path = root / "SHA256SUMS"
    require(path.is_file() and not path.is_symlink(), "manifest missing")
    rows: dict[str, str] = {}
    for line in normalized_bytes(path).decode("utf-8").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  ([^/\\]+)", line)
        require(match is not None, "manifest syntax")
        digest, name = match.groups()
        require(name not in rows and name != "SHA256SUMS", "manifest duplicate")
        candidate = root / name
        require(candidate.is_file() and not candidate.is_symlink(), "manifest member missing")
        require(sha256_file(candidate) == digest, "manifest member hash")
        rows[name] = digest
    actual = {
        item.name
        for item in root.iterdir()
        if item.is_file() and not item.is_symlink() and item.name != "SHA256SUMS"
    }
    require(set(rows) == actual, "manifest membership")
    return path, rows


def asserted_value(payload: Any, path: str) -> Any:
    if isinstance(payload, dict) and path in payload:
        return payload[path]
    current = payload
    for component in path.split("."):
        if isinstance(current, dict) and component in current:
            current = current[component]
        elif isinstance(current, list) and component.isdigit() and int(component) < len(current):
            current = current[int(component)]
        else:
            raise VerificationError(f"missing assertion path: {path}")
    return current


def verify_artifact(repo_root: Path, specification: dict[str, Any]) -> int:
    require(set(specification) == {"path", "sha256_normalized_lf", "json_assertions"}, "artifact schema")
    path = safe_file(repo_root, specification["path"], ".json")
    require(normalized_sha256(path) == specification["sha256_normalized_lf"], "artifact SHA")
    assertions = specification["json_assertions"]
    require(isinstance(assertions, dict) and assertions, "artifact assertions")
    payload = read_json(path)
    for assertion_path, expected in assertions.items():
        require(asserted_value(payload, assertion_path) == expected, f"assertion mismatch: {assertion_path}")
    return len(assertions)


def verify_candidate(repo_root: Path, protocol_path: Path, index_path: Path) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    protocol_path = protocol_path.resolve()
    index_path = index_path.resolve()
    require(protocol_path.is_relative_to(repo_root), "protocol outside repository")
    require(index_path.is_file(), "candidate missing")
    require(sha256_file(protocol_path) == PROTOCOL_SHA256, "protocol SHA mismatch")
    protocol = read_json(protocol_path)
    require(protocol.get("status") == "RESULT_BLIND_EVIDENCE_INDEX_PROTOCOL_FROZEN", "protocol status")
    source_spec = protocol["source_v7"]
    source_path = safe_file(repo_root, source_spec["path"], ".json")
    require(sha256_file(source_path) == source_spec["sha256"], "source v7 SHA")
    source = read_json(source_path)
    require(source.get("protocol") == source_spec["protocol"], "source v7 protocol")
    require(source.get("status") == source_spec["status"], "source v7 status")
    require(len(source.get("entries", [])) == source_spec["entry_count"], "source v7 entries")

    split_spec = protocol["physical_run_split_certificate"]
    split_root = safe_root(repo_root, split_spec["root"])
    split_manifest, split_rows = manifest_rows(split_root)
    require(sha256_file(split_manifest) == split_spec["manifest_sha256"], "split manifest SHA")
    require(split_rows == split_spec["required_files"], "split manifest frozen membership")
    split_certificate = read_json(split_root / "certificate.json")
    split_independent = read_json(split_root / "independent_verification.json")
    require(split_certificate.get("classification") == split_spec["required_classification"], "split classification")
    split_gates = split_certificate.get("certificate_gates")
    require(isinstance(split_gates, dict) and set(split_gates) == SPLIT_GATE_NAMES, "split gate membership")
    require(all(value is True for value in split_gates.values()), "split gates")
    require(split_independent.get("certificate_sha256") == split_rows["certificate.json"], "split verifier binding")
    require(split_independent.get("imports_builder") is False, "split verifier independence")

    release_spec = protocol["complete_release_temporal_package"]
    package_protocol_path = safe_file(repo_root, release_spec["package_protocol_path"], ".json")
    require(sha256_file(package_protocol_path) == release_spec["package_protocol_sha256"], "package protocol SHA")
    release_root = safe_root(repo_root, release_spec["root"])
    release_manifest, release_rows = manifest_rows(release_root)
    require(set(release_rows) == set(release_spec["required_files"]), "release membership")
    release = read_json(release_root / "formal_summary.json")
    release_independent = read_json(release_root / "independent_recheck.json")
    release_bindings = read_json(release_root / "source_bindings.json")
    classification = release.get("classification")
    mapping = protocol["ordered_status_mapping"]
    require(classification in mapping, "classification not frozen")
    status = mapping[classification]
    require(release.get("status") == release_spec["required_formal_status"], "release status")
    require(release.get("evidence_index_status") == status, "release status mapping")
    require(release.get("source_commit") == release_spec["audit_source_commit"], "release source")
    require(release.get("snapshot_sha256") == release_spec["snapshot_sha256"], "release snapshot")
    gate_checks = release.get("gate_checks")
    require(isinstance(gate_checks, dict) and set(gate_checks) == RELEASE_GATE_NAMES, "release gate membership")
    require(all(isinstance(value, bool) for value in gate_checks.values()), "release gate type")
    all_gates = release.get("all_pre_registered_gates_passed")
    require(isinstance(all_gates, bool), "release gate type")
    require(all_gates is all(gate_checks.values()), "release all-gates summary")
    primary_links = release.get("primary_near_duplicate_pairs")
    require(isinstance(primary_links, int) and primary_links >= 0, "release primary links")
    if classification != "RELEASE_SPLIT_INTEGRITY_GATE_FAIL":
        require(all_gates, "successful classification without gates")
        require(
            (classification == "ZERO_IDENTIFIER_ERASED_RELEASE_LINKS")
            is (primary_links == 0),
            "release classification/link rule",
        )
    else:
        require(not all_gates, "gate-fail classification without failed gate")
    require(release.get("prospective_outcomes_read") is False, "release outcomes")
    require(release.get("prediction_values_read") is False, "release predictions")
    require(release.get("gpu_api_model_fit_base_update") == [0, 0, 0, 0], "release resources")
    require(release.get("claim_boundary") == protocol["claim_boundary"], "release claim boundary")
    require(release_independent.get("status") == release_spec["required_independent_status"], "independent status")
    require(release_independent.get("classification") == classification, "independent classification")
    require(release_independent.get("evidence_index_status") == status, "independent evidence status")
    require(release_independent.get("producer_aggregate_matches") is True, "independent aggregate")
    require(release_independent.get("subset_bruteforce_matches") is True, "independent brute force")
    require(release_independent.get("imports_packager_builder") is False, "independent imported packager")
    for key in (
        "primary_candidate_pairs",
        "primary_near_duplicate_pairs",
        "strict_near_duplicate_pairs",
    ):
        require(release_independent.get(key) == release.get(key), f"independent mismatch: {key}")
    require(release_bindings.get("status") == release_spec["required_binding_status"], "binding status")
    require(release_bindings.get("package_protocol_sha256") == release_spec["package_protocol_sha256"], "binding protocol")
    require(release_bindings.get("prior_failed_formal_rc") == 124, "binding old formal rc")
    require(release_bindings.get("prior_failed_deployment_rc") == 1, "binding old deployment rc")
    require(release_bindings.get("prior_failed_result_values_read") is False, "binding old result read")
    require(release_bindings.get("scientific_protocol_changed_in_r2") is False, "binding science revision")
    attestation = normalized_bytes(release_root / "access_attestation.txt").decode("utf-8").splitlines()
    require(
        attestation
        == [
            "raw_senior_archives_opened=false",
            "historical_label_or_observation_fields_used=false",
            "prospective_label_grade_outcome_prediction_values_read=false",
            "task_run_card_code_or_edge_identities_emitted=false",
            "gpu_api_model_fit_base_update=0/0/0/0",
        ],
        "release access attestation",
    )

    candidate = read_json(index_path)
    require(candidate.get("protocol") == "decision_corpus_evidence_index_v8", "candidate protocol")
    require(candidate.get("status") == status, "candidate status")
    require(
        candidate.get("source_v7_index")
        == {
            "path": source_spec["path"],
            "sha256": source_spec["sha256"],
            "entries_inherited_without_modification": source_spec["entry_count"],
        },
        "candidate source binding",
    )
    require(
        candidate.get("v8_protocol")
        == {
            "path": protocol_path.relative_to(repo_root).as_posix(),
            "sha256": PROTOCOL_SHA256,
        },
        "candidate protocol binding",
    )
    entries = candidate.get("entries")
    require(isinstance(entries, list), "candidate entries")
    require(entries[: source_spec["entry_count"]] == source["entries"], "source entries changed")
    additions = entries[source_spec["entry_count"] :]
    require([entry.get("name") for entry in additions] == protocol["append_entry_order"], "append order")
    require(len(additions) == 2, "append count")
    expected_paths = [
        f"{split_spec['root']}/certificate.json",
        f"{split_spec['root']}/independent_verification.json",
        f"{split_spec['root']}/source_bindings.json",
        f"{release_spec['root']}/formal_summary.json",
        f"{release_spec['root']}/independent_recheck.json",
        f"{release_spec['root']}/source_bindings.json",
    ]
    actual_paths = [artifact["path"] for entry in additions for artifact in entry.get("artifacts", [])]
    require(actual_paths == expected_paths, "new artifact membership or order")
    required_assertion_paths = {
        expected_paths[0]: {
            "protocol",
            "status",
            "classification",
            "snapshot_sha256",
            "certificate_gates.historical_to_future_zero_links",
            "certificate_gates.within_future_zero_cross_run_links",
            "certificate_gates.historical_to_future_integrity",
            "certificate_gates.within_future_integrity",
            "future_population.runs",
            "future_population.endpoints",
            "future_population.closure",
            "security.prospective_label_outcome_prediction_values_read",
            "security.gpu_api_model_fit_base_update",
        },
        expected_paths[1]: {
            "protocol",
            "status",
            "classification",
            "certificate_sha256",
            "imports_builder",
            "prospective_outcomes_or_prediction_values_read",
        },
        expected_paths[2]: {
            "source_commit",
            "snapshot_sha256",
            "certificate_sha256",
            "independent_verification_sha256",
            "formal_sha256sums_file_sha256",
            "deployment_sha256sums_file_sha256",
        },
        expected_paths[3]: {
            "protocol",
            "status",
            "classification",
            "evidence_index_status",
            "source_commit",
            "snapshot_sha256",
            "historical_endpoints",
            "historical_runs",
            "historical_tasks",
            "prospective_endpoints",
            "prospective_runs",
            "prospective_tasks",
            "all_pre_registered_gates_passed",
            "prior_failed_formal_rc",
            "prior_failed_deployment_rc",
            "prior_failed_result_file_created",
            "prior_failed_result_values_read",
            "prospective_outcomes_read",
            "prediction_values_read",
            "gpu_api_model_fit_base_update",
        },
        expected_paths[4]: {
            "protocol",
            "status",
            "classification",
            "evidence_index_status",
            "producer_aggregate_matches",
            "subset_bruteforce_matches",
            "all_pre_registered_gates_passed",
            "imports_packager_builder",
            "prospective_outcomes_read",
            "prediction_values_read",
        },
        expected_paths[5]: {
            "protocol",
            "status",
            "package_protocol_sha256",
            "source_commit",
            "snapshot_sha256",
            "prior_failed_formal_rc",
            "prior_failed_deployment_rc",
            "prior_failed_result_file_created",
            "prior_failed_result_values_read",
            "scientific_protocol_changed_in_r2",
        },
    }
    for entry in additions:
        for specification in entry.get("artifacts", []):
            require(
                set(specification.get("json_assertions", {}))
                == required_assertion_paths[specification["path"]],
                "new artifact assertion membership",
            )
    if classification == "ZERO_IDENTIFIER_ERASED_RELEASE_LINKS":
        expected_claim = "No links were found between the complete byte-reproducible v11 release and the fixed 435-run future prefix under the frozen identifier/literal-erased syntactic relation and primary threshold."
    elif classification == "LOW_IDENTIFIER_ERASED_RELEASE_OVERLAP_WITH_EXCEPTIONS":
        expected_claim = "The complete-release temporal audit passed its integrity gates with explicit nonzero identifier/literal-erased overlap exceptions."
    else:
        expected_claim = "The complete-release temporal audit artifact is preserved, but its pre-registered split-integrity gate failed."
    require(additions[1].get("supported_claim") == expected_claim, "release claim mapping")
    require(
        additions[0].get("supported_claim")
        == "The two-axis, outcome-blind split certificate passed on the fixed 435-run prefix under the frozen identifier/literal-erased syntactic relation.",
        "split claim mapping",
    )
    for entry in additions:
        require(all(entry.get(key) for key in ("name", "estimand", "supported_claim", "does_not_prove")), "new entry boundary")

    source_scope = source["scope"]
    candidate_scope = candidate.get("scope")
    require(isinstance(candidate_scope, dict), "candidate scope")
    require(all(candidate_scope.get(key) == value for key, value in source_scope.items()), "source scope changed")
    scope_additions = {
        "physical_run_split_integrity_certificate_bound": True,
        "complete_release_temporal_overlap_certificate_bound": True,
        "complete_release_temporal_classification": classification,
        "complete_release_temporal_primary_gate_passed": all_gates,
        "complete_release_population_endpoints": 16012,
        "future_snapshot_runs_for_temporal_certificate": 435,
        "first960_or_closure_completed_by_v8": False,
    }
    require(candidate_scope == {**copy.deepcopy(source_scope), **scope_additions}, "candidate scope extension")
    source_reporting = source["reporting_contract"]
    reporting_additions = {
        "fixed_syntactic_complete_release_zero_link_language_allowed": classification == "ZERO_IDENTIFIER_ERASED_RELEASE_LINKS",
        "qualified_complete_release_exception_language_required": classification == "LOW_IDENTIFIER_ERASED_RELEASE_OVERLAP_WITH_EXCEPTIONS",
        "complete_release_temporal_gate_failure_language_required": classification == "RELEASE_SPLIT_INTEGRITY_GATE_FAIL",
        "semantic_clone_or_pretraining_decontamination_language_allowed": False,
        "predictor_effect_or_search_utility_language_allowed_by_v8": False,
        "strict_sensitivity_can_rescue_primary": False,
    }
    require(candidate.get("reporting_contract") == {**copy.deepcopy(source_reporting), **reporting_additions}, "reporting extension")
    temporal = candidate.get("temporal_split_extension")
    require(
        temporal
        == {
            "classification": classification,
            "ordered_status": status,
            "snapshot_sha256": release_spec["snapshot_sha256"],
            "physical_split_manifest_sha256": split_spec["manifest_sha256"],
            "complete_release_manifest_sha256": sha256_file(release_manifest),
            "complete_release_manifest_members": release_rows,
            "source_v7_read_only": True,
            "source_v7_entries_removed_or_modified": False,
            "strict_sensitivity_can_rescue_primary": False,
        },
        "temporal extension",
    )
    assertion_count = 0
    for entry in additions:
        for specification in entry["artifacts"]:
            assertion_count += verify_artifact(repo_root, specification)
    inherited_artifacts = sum(len(entry.get("artifacts", [])) for entry in source["entries"])
    inherited_bound = sum(len(entry.get("bound_files", [])) for entry in source["entries"])
    inherited_assertions = sum(
        len(artifact.get("json_assertions", {}))
        for entry in source["entries"]
        for artifact in entry.get("artifacts", [])
    )
    return {
        "protocol": "independent-decision-corpus-evidence-index-v8-verifier-v1",
        "status": "INDEPENDENTLY_VERIFIED_TEMPORAL_SPLIT_EVIDENCE_INDEX",
        "index_status": status,
        "classification": classification,
        "index_sha256_normalized_lf": normalized_sha256(index_path),
        "protocol_sha256": PROTOCOL_SHA256,
        "source_v7_sha256": source_spec["sha256"],
        "entry_count": len(entries),
        "inherited_entry_count": source_spec["entry_count"],
        "appended_entry_count": len(additions),
        "artifact_count": inherited_artifacts + len(actual_paths),
        "bound_file_count": inherited_bound,
        "json_assertion_count": inherited_assertions + assertion_count,
        "complete_release_manifest_sha256": sha256_file(release_manifest),
        "source_v7_entries_exact": True,
        "producer_function_imported": False,
        "prospective_label_grade_outcome_or_prediction_values_read": False,
        "accuracy_effect_or_search_utility_computed": False,
        "raw_senior_archives_opened": False,
        "gpu_api_model_fit_base_update": [0, 0, 0, 0],
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
    parser.add_argument("--index", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    receipt = verify_candidate(args.repo_root, args.protocol, args.index)
    atomic_json(args.out.resolve(), receipt)
    print(receipt["status"])


if __name__ == "__main__":
    main()
