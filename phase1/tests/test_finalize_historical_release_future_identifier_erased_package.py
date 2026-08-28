from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from phase1 import finalize_historical_release_future_identifier_erased_package as packager


def protocol(tmp_path: Path) -> dict:
    return {
        "protocol": "historical-release-future-identifier-erased-package-v1",
        "fixed_source": {
            "source_commit": "8" * 40,
            "snapshot_sha256": "7" * 64,
            "resource_r2_protocol_sha256": "6" * 64,
            "superseded_protocol_sha256": "5" * 64,
        },
        "fixed_population": {
            "historical_endpoints": 16012,
            "historical_runs": 667,
            "historical_tasks": 25,
            "future_endpoints": 11906,
            "future_runs": 435,
            "future_tasks": 34,
            "future_closure": False,
        },
        "ordered_evidence_index_status": {
            "ZERO_IDENTIFIER_ERASED_RELEASE_LINKS": "ZERO_STATUS",
            "LOW_IDENTIFIER_ERASED_RELEASE_OVERLAP_WITH_EXCEPTIONS": "LOW_STATUS",
            "RELEASE_SPLIT_INTEGRITY_GATE_FAIL": "FAIL_STATUS",
        },
        "claim_boundary": {
            "semantic_clone_absence_proven": False,
            "strict_sensitivity_can_rescue_primary": False,
        },
    }


def producer(classification: str, links: int, failed_gate: str | None = None) -> dict:
    checks = {name: True for name in packager.EXPECTED_GATE_NAMES}
    if failed_gate is not None:
        checks[failed_gate] = False
    return {
        "status": "PROVISIONAL_HISTORICAL_RELEASE_FUTURE_OVERLAP_AUDIT_COMPLETE",
        "classification": classification,
        "source_commit": "8" * 40,
        "snapshot_sha256": "7" * 64,
        "historical_scope": {"endpoints": 16012, "runs": 667, "tasks": 25},
        "prospective_scope": {
            "observed_endpoints": 11906,
            "observed_runs": 435,
            "observed_tasks": 34,
            "closure_provided": False,
        },
        "historical_fingerprinting": {
            "fingerprinted_endpoints": 16000,
            "coverage": 16000 / 16012,
        },
        "prospective_fingerprinting": {
            "fingerprinted_endpoints": 11894,
            "coverage": 11894 / 11906,
        },
        "primary_jaccard_0_85": {
            "candidate_pairs_exactly_checked": 123,
            "near_duplicate_pairs": links,
            "same_task_pairs": links,
            "cross_task_pairs": 0,
            "historical_affected_endpoints": links,
            "prospective_affected_endpoints": links,
            "cross_task_prospective_affected_endpoints": 0,
            "components": links,
            "largest_component_endpoints": 2 if links else 0,
            "largest_component_tasks": 1 if links else 0,
            "large_multitask_components": 0,
        },
        "strict_jaccard_0_95": {
            "near_duplicate_pairs": 0,
            "prospective_affected_endpoints": 0,
        },
        "pre_registered_gate": {"checks": checks, "all_passed": all(checks.values())},
        "security": {
            "historical_label_or_observation_fields_used": False,
            "prospective_label_vault_opened": False,
            "prospective_outcome_files_opened": [],
            "prediction_values_read": False,
            "code_or_identity_values_emitted": False,
            "gpu_api_model_fit_base_update": [0, 0, 0, 0],
        },
    }


def verifier(classification: str, links: int) -> dict:
    return {
        "status": "INDEPENDENTLY_VERIFIED_HISTORICAL_RELEASE_FUTURE_OVERLAP",
        "classification": classification,
        "historical_endpoints": 16012,
        "historical_runs": 667,
        "prospective_endpoints": 11906,
        "prospective_runs": 435,
        "primary_candidate_pairs": 123,
        "primary_near_duplicate_pairs": links,
        "strict_near_duplicate_pairs": 0,
        "producer_aggregate_matches": True,
        "subset_bruteforce_matches": True,
        "imports_new_producer_code": False,
        "raw_senior_archives_opened": False,
        "historical_label_or_observation_fields_used": False,
        "prospective_outcomes_read": False,
        "prediction_values_read": False,
        "gpu_api_model_fit_base_update": [0, 0, 0, 0],
    }


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")


def seal(root: Path, include_complete: bool = False) -> None:
    (root / "COMPLETE").touch()
    paths = sorted(
        path
        for path in root.rglob("*")
        if path.is_file()
        and path.name != "SHA256SUMS"
        and (include_complete or path.name != "COMPLETE")
    )
    (root / "SHA256SUMS").write_text(
        "".join(
            f"{packager.sha256_file(path)}  {path.relative_to(root).as_posix()}\n"
            for path in paths
        ),
        encoding="utf-8",
    )


def chain(tmp_path: Path, classification: str, links: int, failed_gate: str | None = None):
    roots = {name: tmp_path / name for name in ("formal", "postflight", "deployment", "failed-formal", "failed-deployment")}
    for root in roots.values():
        root.mkdir()
    p = producer(classification, links, failed_gate)
    v = verifier(classification, links)
    for name in ("producer_a.json", "producer_b.json"):
        write_json(roots["formal"] / name, p)
    for name in ("verifier_a.json", "verifier_b.json"):
        write_json(roots["formal"] / name, v)
    for name in ("independent_a.json", "independent_b.json"):
        write_json(roots["postflight"] / name, v)
    (roots["formal"] / "focused_tests.txt").write_text("19 passed in 1.0s\n", encoding="utf-8")
    (roots["formal"] / "full_tests.txt").write_text("1269 passed, 47 warnings in 2.0s\n", encoding="utf-8")
    (roots["deployment"] / "deployment_summary.txt").write_text("status=pass\n", encoding="utf-8")
    seal(roots["formal"])
    seal(roots["postflight"])
    seal(roots["deployment"], include_complete=True)
    (roots["failed-formal"] / "FAILED_RC").write_text("124\n", encoding="utf-8")
    (roots["failed-formal"] / "producer_a.stderr").write_bytes(b"")
    (roots["failed-deployment"] / "FAILED_RC").write_text("1\n", encoding="utf-8")
    return roots


@pytest.mark.parametrize(
    ("classification", "links", "failed_gate", "expected_status"),
    [
        ("ZERO_IDENTIFIER_ERASED_RELEASE_LINKS", 0, None, "ZERO_STATUS"),
        ("LOW_IDENTIFIER_ERASED_RELEASE_OVERLAP_WITH_EXCEPTIONS", 2, None, "LOW_STATUS"),
        ("RELEASE_SPLIT_INTEGRITY_GATE_FAIL", 2, "prospective_affected_fraction", "FAIL_STATUS"),
    ],
)
def test_frozen_three_way_mapping(tmp_path: Path, classification: str, links: int, failed_gate: str | None, expected_status: str) -> None:
    roots = chain(tmp_path, classification, links, failed_gate)
    summary, independent, bindings, _ = packager.build_payloads(
        protocol(tmp_path),
        roots["formal"],
        roots["postflight"],
        roots["deployment"],
        roots["failed-formal"],
        roots["failed-deployment"],
        "4" * 64,
        "3" * 40,
    )
    assert summary["classification"] == classification
    assert summary["evidence_index_status"] == expected_status
    assert independent["evidence_index_status"] == expected_status
    assert bindings["prior_failed_formal_rc"] == 124


def test_gate_failure_cannot_be_rescued_by_zero_links() -> None:
    payload = producer(
        "RELEASE_SPLIT_INTEGRITY_GATE_FAIL", 0, "historical_fingerprint_coverage"
    )
    classification, all_passed, links = packager.classification_from_producer(payload)
    assert classification == "RELEASE_SPLIT_INTEGRITY_GATE_FAIL"
    assert all_passed is False
    assert links == 0


def test_classification_drift_fails_closed() -> None:
    payload = producer("ZERO_IDENTIFIER_ERASED_RELEASE_LINKS", 1)
    with pytest.raises(packager.PackageError, match="classification"):
        packager.classification_from_producer(payload)


def test_manifest_omission_fails_closed(tmp_path: Path) -> None:
    root = tmp_path / "manifest"
    root.mkdir()
    (root / "one.txt").write_text("one\n", encoding="utf-8")
    (root / "two.txt").write_text("two\n", encoding="utf-8")
    (root / "SHA256SUMS").write_text(
        f"{packager.sha256_file(root / 'one.txt')}  one.txt\n", encoding="utf-8"
    )
    with pytest.raises(packager.PackageError, match="membership"):
        packager.verify_manifest(root)


def test_output_is_atomic_hash_bound_and_non_overwriting(tmp_path: Path) -> None:
    output = tmp_path / "package"
    packager.write_package(output, {"a": 1}, {"b": 2}, {"c": 3}, "readme\n")
    assert packager.verify_manifest(output)
    with pytest.raises(packager.PackageError, match="already exists"):
        packager.write_package(output, {"a": 1}, {"b": 2}, {"c": 3}, "readme\n")


def test_security_drift_fails_closed(tmp_path: Path) -> None:
    roots = chain(tmp_path, "ZERO_IDENTIFIER_ERASED_RELEASE_LINKS", 0)
    changed = json.loads(
        (roots["formal"] / "producer_a.json").read_text(encoding="utf-8")
    )
    changed["security"]["prediction_values_read"] = True
    for name in ("producer_a.json", "producer_b.json"):
        write_json(roots["formal"] / name, changed)
    (roots["formal"] / "SHA256SUMS").unlink()
    seal(roots["formal"])
    with pytest.raises(packager.PackageError, match="prediction values"):
        packager.build_payloads(
            protocol(tmp_path),
            roots["formal"],
            roots["postflight"],
            roots["deployment"],
            roots["failed-formal"],
            roots["failed-deployment"],
            "4" * 64,
            "3" * 40,
        )
