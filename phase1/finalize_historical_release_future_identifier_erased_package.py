#!/usr/bin/env python3
"""Finalize the frozen full-release overlap chain into an identity-free package."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any


class PackageError(RuntimeError):
    """Raised when any frozen binding or chain requirement fails."""


EXPECTED_GATE_NAMES = {
    "historical_fingerprint_coverage",
    "prospective_fingerprint_coverage",
    "prospective_affected_fraction",
    "cross_task_prospective_affected_fraction",
    "large_multitask_components",
    "bipartite_join_self_check",
}
PACKAGE_PROTOCOL_SHA256 = (
    "ba6a1f6e44458e65b7042fcfd6e84e95e2e2b6cec0c7d0bb494ad7e0924da2d7"
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise PackageError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PackageError(f"invalid JSON: {path}") from error
    require(isinstance(payload, dict), f"JSON root is not an object: {path}")
    return payload


def atomic_text(path: Path, value: str) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(value, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    atomic_text(
        path,
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n",
    )


def exact_root(path: Path, expected: str, label: str) -> Path:
    resolved = path.resolve()
    require(str(resolved) == expected, f"{label} root differs from frozen path")
    require(resolved.is_dir(), f"{label} root missing")
    return resolved


def verify_manifest(root: Path) -> dict[str, str]:
    manifest_path = root / "SHA256SUMS"
    require(manifest_path.is_file(), f"missing manifest: {root}")
    rows: dict[str, str] = {}
    for line_number, line in enumerate(
        manifest_path.read_text(encoding="utf-8").splitlines(), 1
    ):
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        require(match is not None, f"malformed manifest line {line_number}: {root}")
        digest, relative_text = match.groups()
        relative = Path(relative_text)
        require(not relative.is_absolute(), f"absolute manifest path: {relative_text}")
        require(".." not in relative.parts, f"escaping manifest path: {relative_text}")
        normalized = relative.as_posix()
        require(normalized not in rows, f"duplicate manifest path: {relative_text}")
        raw_candidate = root / relative
        require(not raw_candidate.is_symlink(), f"symlink manifest file: {relative_text}")
        candidate = raw_candidate.resolve()
        try:
            candidate.relative_to(root)
        except ValueError as error:
            raise PackageError(f"manifest path escapes root: {relative_text}") from error
        require(candidate.is_file(), f"missing manifest file: {relative_text}")
        require(sha256_file(candidate) == digest, f"manifest SHA mismatch: {relative_text}")
        rows[normalized] = digest
    require(rows, f"empty manifest: {root}")
    actual_files = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and not path.is_symlink() and path.name != "SHA256SUMS"
    }
    if "COMPLETE" not in rows:
        actual_files.discard("COMPLETE")
    require(set(rows) == actual_files, f"manifest membership mismatch: {root}")
    return rows


def test_counts(path: Path) -> dict[str, int]:
    require(path.is_file(), f"missing pytest output: {path}")
    summary = next(
        (line for line in reversed(path.read_text(encoding="utf-8").splitlines()) if " passed" in line),
        "",
    )
    require(summary, f"pytest summary missing: {path}")
    values = {"passed": 0, "skipped": 0, "warnings": 0}
    for key in values:
        match = re.search(rf"(\d+) {key}", summary)
        if match:
            values[key] = int(match.group(1))
    require(values["passed"] > 0, f"no passing tests recorded: {path}")
    return values


def classification_from_producer(producer: dict[str, Any]) -> tuple[str, bool, int]:
    gate = producer.get("pre_registered_gate", {})
    checks = gate.get("checks")
    require(isinstance(checks, dict), "producer gate checks missing")
    require(set(checks) == EXPECTED_GATE_NAMES, "producer gate membership drift")
    require(all(isinstance(value, bool) for value in checks.values()), "producer gate is non-boolean")
    all_passed = all(checks.values())
    require(gate.get("all_passed") is all_passed, "producer all_passed mismatch")
    primary = producer.get("primary_jaccard_0_85", {})
    links = primary.get("near_duplicate_pairs")
    require(isinstance(links, int) and links >= 0, "invalid primary link count")
    if not all_passed:
        expected = "RELEASE_SPLIT_INTEGRITY_GATE_FAIL"
    elif links == 0:
        expected = "ZERO_IDENTIFIER_ERASED_RELEASE_LINKS"
    else:
        expected = "LOW_IDENTIFIER_ERASED_RELEASE_OVERLAP_WITH_EXCEPTIONS"
    require(producer.get("classification") == expected, "producer classification rule mismatch")
    return expected, all_passed, links


def require_security(producer: dict[str, Any], verifier: dict[str, Any]) -> None:
    security = producer.get("security", {})
    require(security.get("historical_label_or_observation_fields_used") is False, "historical labels used")
    require(security.get("prospective_label_vault_opened") is False, "prospective label vault opened")
    require(security.get("prospective_outcome_files_opened") == [], "prospective outcomes opened")
    require(security.get("prediction_values_read") is False, "prediction values read")
    require(security.get("code_or_identity_values_emitted") is False, "identity payload emitted")
    require(security.get("gpu_api_model_fit_base_update") == [0, 0, 0, 0], "producer resource contract")
    require(verifier.get("raw_senior_archives_opened") is False, "raw archive opened")
    require(verifier.get("historical_label_or_observation_fields_used") is False, "verifier historical labels used")
    require(verifier.get("prospective_outcomes_read") is False, "verifier outcomes read")
    require(verifier.get("prediction_values_read") is False, "verifier predictions read")
    require(verifier.get("gpu_api_model_fit_base_update") == [0, 0, 0, 0], "verifier resource contract")


def require_static_payloads(
    protocol: dict[str, Any], producer: dict[str, Any], verifier: dict[str, Any]
) -> tuple[str, bool, int]:
    source = protocol["fixed_source"]
    population = protocol["fixed_population"]
    require(producer.get("status") == "PROVISIONAL_HISTORICAL_RELEASE_FUTURE_OVERLAP_AUDIT_COMPLETE", "producer status")
    require(verifier.get("status") == "INDEPENDENTLY_VERIFIED_HISTORICAL_RELEASE_FUTURE_OVERLAP", "verifier status")
    require(producer.get("source_commit") == source["source_commit"], "producer source commit")
    require(producer.get("snapshot_sha256") == source["snapshot_sha256"], "producer snapshot")
    historical = producer.get("historical_scope", {})
    future = producer.get("prospective_scope", {})
    require(
        (historical.get("endpoints"), historical.get("runs"), historical.get("tasks"))
        == (
            population["historical_endpoints"],
            population["historical_runs"],
            population["historical_tasks"],
        ),
        "historical population drift",
    )
    require(
        (
            future.get("observed_endpoints"),
            future.get("observed_runs"),
            future.get("observed_tasks"),
            future.get("closure_provided"),
        )
        == (
            population["future_endpoints"],
            population["future_runs"],
            population["future_tasks"],
            population["future_closure"],
        ),
        "future population drift",
    )
    require(
        (
            verifier.get("historical_endpoints"),
            verifier.get("historical_runs"),
            verifier.get("prospective_endpoints"),
            verifier.get("prospective_runs"),
        )
        == (
            population["historical_endpoints"],
            population["historical_runs"],
            population["future_endpoints"],
            population["future_runs"],
        ),
        "verifier population drift",
    )
    require(verifier.get("producer_aggregate_matches") is True, "independent aggregate mismatch")
    require(verifier.get("subset_bruteforce_matches") is True, "independent brute-force mismatch")
    require(verifier.get("imports_new_producer_code") is False, "verifier imported producer")
    classification, all_passed, links = classification_from_producer(producer)
    require(verifier.get("classification") == classification, "producer/verifier classification mismatch")
    require_security(producer, verifier)
    return classification, all_passed, links


def require_chain(
    protocol: dict[str, Any],
    formal: Path,
    postflight: Path,
    deployment: Path,
    failed_formal: Path,
    failed_deployment: Path,
) -> tuple[dict[str, str], dict[str, str], dict[str, str], dict[str, Any], dict[str, Any]]:
    for root, label in ((formal, "formal"), (postflight, "postflight"), (deployment, "deployment")):
        require((root / "COMPLETE").is_file(), f"{label} COMPLETE missing")
        require(not (root / "FAILED_RC").exists(), f"{label} FAILED_RC present")
    require((failed_formal / "FAILED_RC").read_text(encoding="utf-8").strip() == "124", "old formal rc")
    require((failed_deployment / "FAILED_RC").read_text(encoding="utf-8").strip() == "1", "old deployment rc")
    require(not (failed_formal / "producer_a.json").exists(), "old failed producer result exists")
    require((failed_formal / "producer_a.stderr").stat().st_size == 0, "old failed stderr nonempty")

    formal_manifest = verify_manifest(formal)
    postflight_manifest = verify_manifest(postflight)
    deployment_manifest = verify_manifest(deployment)
    producer_a_path = formal / "producer_a.json"
    producer_b_path = formal / "producer_b.json"
    verifier_a_path = formal / "verifier_a.json"
    verifier_b_path = formal / "verifier_b.json"
    independent_a_path = postflight / "independent_a.json"
    independent_b_path = postflight / "independent_b.json"
    require(producer_a_path.read_bytes() == producer_b_path.read_bytes(), "producer A/B byte drift")
    require(verifier_a_path.read_bytes() == verifier_b_path.read_bytes(), "formal verifier A/B byte drift")
    require(independent_a_path.read_bytes() == independent_b_path.read_bytes(), "postflight A/B byte drift")
    require(independent_a_path.read_bytes() == verifier_a_path.read_bytes(), "postflight/formal verifier byte drift")
    producer = read_json(producer_a_path)
    verifier = read_json(verifier_a_path)
    require_static_payloads(protocol, producer, verifier)
    return formal_manifest, postflight_manifest, deployment_manifest, producer, verifier


def build_payloads(
    protocol: dict[str, Any],
    formal: Path,
    postflight: Path,
    deployment: Path,
    failed_formal: Path,
    failed_deployment: Path,
    protocol_sha256: str,
    packager_source_commit: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], str]:
    formal_manifest, postflight_manifest, deployment_manifest, producer, verifier = require_chain(
        protocol, formal, postflight, deployment, failed_formal, failed_deployment
    )
    classification, all_passed, primary_links = require_static_payloads(protocol, producer, verifier)
    primary = producer["primary_jaccard_0_85"]
    strict = producer["strict_jaccard_0_95"]
    historical_fp = producer["historical_fingerprinting"]
    future_fp = producer["prospective_fingerprinting"]
    evidence_status = protocol["ordered_evidence_index_status"][classification]
    summary = {
        "protocol": protocol["protocol"],
        "status": "FORMAL_HISTORICAL_RELEASE_FUTURE_IDENTIFIER_ERASED_PACKAGE_COMPLETE",
        "classification": classification,
        "evidence_index_status": evidence_status,
        "source_commit": protocol["fixed_source"]["source_commit"],
        "packager_source_commit": packager_source_commit,
        "snapshot_sha256": protocol["fixed_source"]["snapshot_sha256"],
        "historical_endpoints": producer["historical_scope"]["endpoints"],
        "historical_runs": producer["historical_scope"]["runs"],
        "historical_tasks": producer["historical_scope"]["tasks"],
        "historical_fingerprinted_endpoints": historical_fp["fingerprinted_endpoints"],
        "historical_fingerprint_coverage": historical_fp["coverage"],
        "prospective_endpoints": producer["prospective_scope"]["observed_endpoints"],
        "prospective_runs": producer["prospective_scope"]["observed_runs"],
        "prospective_tasks": producer["prospective_scope"]["observed_tasks"],
        "prospective_fingerprinted_endpoints": future_fp["fingerprinted_endpoints"],
        "prospective_fingerprint_coverage": future_fp["coverage"],
        "primary_candidate_pairs": primary["candidate_pairs_exactly_checked"],
        "primary_near_duplicate_pairs": primary_links,
        "primary_same_task_pairs": primary["same_task_pairs"],
        "primary_cross_task_pairs": primary["cross_task_pairs"],
        "primary_historical_affected_endpoints": primary["historical_affected_endpoints"],
        "primary_prospective_affected_endpoints": primary["prospective_affected_endpoints"],
        "primary_cross_task_prospective_affected_endpoints": primary["cross_task_prospective_affected_endpoints"],
        "primary_components": primary["components"],
        "primary_largest_component_endpoints": primary["largest_component_endpoints"],
        "primary_largest_component_tasks": primary["largest_component_tasks"],
        "primary_large_multitask_components": primary["large_multitask_components"],
        "strict_near_duplicate_pairs": strict["near_duplicate_pairs"],
        "strict_prospective_affected_endpoints": strict["prospective_affected_endpoints"],
        "gate_checks": producer["pre_registered_gate"]["checks"],
        "all_pre_registered_gates_passed": all_passed,
        "producer_ab_byte_identical": True,
        "formal_verifier_ab_byte_identical": True,
        "postflight_verifier_ab_byte_identical": True,
        "postflight_equals_formal_verifier": True,
        "independent_aggregate_matches": True,
        "subset_bruteforce_matches": True,
        "focused_tests": test_counts(formal / "focused_tests.txt"),
        "full_tests": test_counts(formal / "full_tests.txt"),
        "prior_failed_formal_rc": 124,
        "prior_failed_deployment_rc": 1,
        "prior_failed_result_file_created": False,
        "prior_failed_result_values_read": False,
        "prospective_outcomes_read": False,
        "prediction_values_read": False,
        "raw_senior_archives_opened": False,
        "gpu_api_model_fit_base_update": [0, 0, 0, 0],
        "claim_boundary": protocol["claim_boundary"],
    }
    independent = {
        "protocol": "independent-historical-release-future-identifier-erased-package-recheck-v1",
        "status": "INDEPENDENT_PACKAGE_RECHECK_COMPLETE",
        "classification": classification,
        "evidence_index_status": evidence_status,
        "source_commit": protocol["fixed_source"]["source_commit"],
        "packager_source_commit": packager_source_commit,
        "snapshot_sha256": protocol["fixed_source"]["snapshot_sha256"],
        "producer_receipt_sha256": sha256_file(formal / "producer_a.json"),
        "formal_verifier_sha256": sha256_file(formal / "verifier_a.json"),
        "postflight_verifier_sha256": sha256_file(postflight / "independent_a.json"),
        "formal_postflight_verifier_byte_identical": True,
        "producer_aggregate_matches": verifier["producer_aggregate_matches"],
        "subset_bruteforce_matches": verifier["subset_bruteforce_matches"],
        "historical_endpoints": verifier["historical_endpoints"],
        "historical_runs": verifier["historical_runs"],
        "prospective_endpoints": verifier["prospective_endpoints"],
        "prospective_runs": verifier["prospective_runs"],
        "primary_candidate_pairs": verifier["primary_candidate_pairs"],
        "primary_near_duplicate_pairs": verifier["primary_near_duplicate_pairs"],
        "strict_near_duplicate_pairs": verifier["strict_near_duplicate_pairs"],
        "all_pre_registered_gates_passed": all_passed,
        "raw_senior_archives_opened": False,
        "prospective_outcomes_read": False,
        "prediction_values_read": False,
        "gpu_api_model_fit_base_update": [0, 0, 0, 0],
        "imports_packager_builder": False,
    }
    bindings = {
        "protocol": "historical-release-future-identifier-erased-package-bindings-v1",
        "status": "FORMAL_POSTFLIGHT_DEPLOYMENT_AND_FAILURE_HISTORY_BOUND",
        "package_protocol_sha256": protocol_sha256,
        "resource_r2_protocol_sha256": protocol["fixed_source"]["resource_r2_protocol_sha256"],
        "superseded_protocol_sha256": protocol["fixed_source"]["superseded_protocol_sha256"],
        "source_commit": protocol["fixed_source"]["source_commit"],
        "packager_source_commit": packager_source_commit,
        "snapshot_sha256": protocol["fixed_source"]["snapshot_sha256"],
        "formal_root": str(formal),
        "postflight_root": str(postflight),
        "deployment_root": str(deployment),
        "failed_formal_root": str(failed_formal),
        "failed_deployment_root": str(failed_deployment),
        "producer_receipt_sha256": sha256_file(formal / "producer_a.json"),
        "formal_verifier_sha256": sha256_file(formal / "verifier_a.json"),
        "postflight_verifier_sha256": sha256_file(postflight / "independent_a.json"),
        "formal_sha256sums_file_sha256": sha256_file(formal / "SHA256SUMS"),
        "postflight_sha256sums_file_sha256": sha256_file(postflight / "SHA256SUMS"),
        "deployment_sha256sums_file_sha256": sha256_file(deployment / "SHA256SUMS"),
        "formal_manifest_payload_files": len(formal_manifest),
        "postflight_manifest_payload_files": len(postflight_manifest),
        "deployment_manifest_payload_files": len(deployment_manifest),
        "prior_failed_formal_rc": 124,
        "prior_failed_deployment_rc": 1,
        "prior_failed_result_file_created": False,
        "prior_failed_stderr_bytes": 0,
        "prior_failed_result_values_read": False,
        "scientific_protocol_changed_in_r2": False,
    }
    readme = (
        "# Complete-release temporal-overlap package\n\n"
        f"Classification: `{classification}`. Evidence-index status: `{evidence_status}`.\n\n"
        "This compact package binds the fixed full-v11-release formal run, independent postflight, "
        "deployment manifests, and the preceding immutable timeout failure. It emits aggregate counts only. "
        "It does not establish semantic clone absence, unknown-pretraining decontamination, predictor effect, "
        "search utility, or first-960 closure.\n"
    )
    return summary, independent, bindings, readme


def write_package(
    output: Path,
    summary: dict[str, Any],
    independent: dict[str, Any],
    bindings: dict[str, Any],
    readme: str,
) -> None:
    require(not output.exists(), "output package already exists")
    temporary = output.with_name(output.name + ".tmp")
    require(not temporary.exists(), "temporary package already exists")
    temporary.mkdir(parents=True)
    try:
        atomic_text(temporary / "README.md", readme)
        atomic_json(temporary / "formal_summary.json", summary)
        atomic_json(temporary / "independent_recheck.json", independent)
        atomic_json(temporary / "source_bindings.json", bindings)
        atomic_text(
            temporary / "access_attestation.txt",
            "raw_senior_archives_opened=false\n"
            "historical_label_or_observation_fields_used=false\n"
            "prospective_label_grade_outcome_prediction_values_read=false\n"
            "task_run_card_code_or_edge_identities_emitted=false\n"
            "gpu_api_model_fit_base_update=0/0/0/0\n",
        )
        names = sorted(path.name for path in temporary.iterdir() if path.is_file())
        manifest = "".join(
            f"{sha256_file(temporary / name)}  {name}\n" for name in names
        )
        atomic_text(temporary / "SHA256SUMS", manifest)
        os.replace(temporary, output)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--expect-protocol-sha256", required=True)
    parser.add_argument("--packager-source-commit", required=True)
    parser.add_argument("--formal-root", required=True, type=Path)
    parser.add_argument("--postflight-root", required=True, type=Path)
    parser.add_argument("--deployment-root", required=True, type=Path)
    parser.add_argument("--failed-formal-root", required=True, type=Path)
    parser.add_argument("--failed-deployment-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    require(re.fullmatch(r"[0-9a-f]{40}", args.packager_source_commit) is not None, "packager commit shape")
    head = subprocess.check_output(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"], text=True
    ).strip()
    require(head == args.packager_source_commit, "packager source commit binding")
    require(
        not subprocess.check_output(
            ["git", "-C", str(repo_root), "status", "--porcelain", "--untracked-files=all"],
            text=True,
        ).strip(),
        "packager worktree is not clean",
    )
    protocol_path = args.protocol.resolve()
    require(protocol_path.is_relative_to(repo_root), "package protocol outside repository")
    protocol_sha = sha256_file(protocol_path)
    require(args.expect_protocol_sha256 == PACKAGE_PROTOCOL_SHA256, "unexpected package protocol selection")
    require(protocol_sha == args.expect_protocol_sha256, "package protocol SHA mismatch")
    protocol = read_json(protocol_path)
    require(protocol.get("status") == "RESULT_BLIND_PACKAGE_PROTOCOL_FROZEN", "package protocol status")
    for source_path in (Path(__file__).resolve(), protocol_path):
        relative = source_path.relative_to(repo_root).as_posix()
        committed_blob = subprocess.check_output(
            ["git", "-C", str(repo_root), "rev-parse", f"HEAD:{relative}"], text=True
        ).strip()
        working_blob = subprocess.check_output(
            ["git", "-C", str(repo_root), "hash-object", str(source_path)], text=True
        ).strip()
        require(committed_blob == working_blob, f"packager source blob drift: {relative}")
    require(
        sorted(protocol["output_contract"]["files"])
        == sorted(
            [
                "README.md",
                "formal_summary.json",
                "independent_recheck.json",
                "source_bindings.json",
                "access_attestation.txt",
                "SHA256SUMS",
            ]
        ),
        "package output membership drift",
    )
    source = protocol["fixed_source"]
    r2_protocol = (repo_root / source["resource_r2_protocol_path"]).resolve()
    require(sha256_file(r2_protocol) == source["resource_r2_protocol_sha256"], "resource-r2 protocol SHA")
    formal = exact_root(args.formal_root, source["formal_root"], "formal")
    postflight = exact_root(args.postflight_root, source["postflight_root"], "postflight")
    deployment = exact_root(args.deployment_root, source["deployment_root"], "deployment")
    failed_formal = exact_root(args.failed_formal_root, source["failed_formal_root"], "failed formal")
    failed_deployment = exact_root(args.failed_deployment_root, source["failed_deployment_root"], "failed deployment")
    output = args.output.resolve()
    expected_output = (repo_root / protocol["output_contract"]["fixed_repo_relative_root"]).resolve()
    require(output == expected_output, "output root differs from frozen path")
    summary, independent, bindings, readme = build_payloads(
        protocol,
        formal,
        postflight,
        deployment,
        failed_formal,
        failed_deployment,
        protocol_sha,
        args.packager_source_commit,
    )
    write_package(output, summary, independent, bindings, readme)
    print(summary["status"])
    print(summary["classification"])
    print(summary["evidence_index_status"])


if __name__ == "__main__":
    main()
