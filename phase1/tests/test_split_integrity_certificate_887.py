from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from phase1.build_split_integrity_certificate_887 import (
    CertificateError,
    build,
)
from phase1.split_integrity_certificate_887_schema import (
    FAIL_CLASSIFICATION,
    HISTORICAL_FORMAL_ROOT,
    HISTORICAL_POSTFLIGHT_LOGIC_SHA256,
    HISTORICAL_POSTFLIGHT_ROOT,
    HISTORICAL_RESULT_PROTOCOL_SHA256,
    HISTORICAL_SOURCE_COMMIT,
    LOW_CLASSIFICATION,
    PROTOCOL_SHA256,
    SNAPSHOT_SHA256,
    ZERO_CLASSIFICATION,
)
from phase1.verify_split_integrity_certificate_887 import verify


PHASE1 = Path(__file__).parents[1]
PROTOCOL = PHASE1 / "split_integrity_certificate_887_protocol_v1.json"
WITHIN = (
    PHASE1
    / "results"
    / "prospective_identifier_erased_clone_887_20260828_519815d"
)
HISTORICAL = (
    PHASE1
    / "results"
    / "historical_train_future_identifier_erased_overlap_887_20260828_ec67d1a"
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _historical_package(
    root: Path, *, primary_links: int = 0, gate_pass: bool = True
) -> Path:
    root.mkdir()
    classification = (
        "ZERO_IDENTIFIER_ERASED_LINKS"
        if gate_pass and primary_links == 0
        else "LOW_IDENTIFIER_ERASED_OVERLAP_ONLY"
        if gate_pass
        else "INTEGRITY_GATE_FAIL"
    )
    summary = {
        "protocol": "historical-train-future-identifier-erased-887-extension-v1",
        "status": "FORMAL_PROVISIONAL_IDENTIFIER_ERASED_OVERLAP_887_COMPLETE",
        "classification": classification,
        "source_commit": HISTORICAL_SOURCE_COMMIT,
        "snapshot_sha256": SNAPSHOT_SHA256,
        "historical_endpoints": 5519,
        "historical_runs": 333,
        "historical_fingerprinted_endpoints": 5519,
        "historical_fingerprint_coverage": 1.0,
        "prospective_runs": 435,
        "prospective_endpoints": 11906,
        "prospective_fingerprinted_endpoints": 11894,
        "prospective_fingerprint_coverage": 11894 / 11906,
        "primary_candidate_pairs": 6000000,
        "primary_near_duplicate_pairs": primary_links,
        "primary_same_task_pairs": primary_links // 2,
        "primary_cross_task_pairs": primary_links - primary_links // 2,
        "primary_historical_affected_endpoints": primary_links,
        "primary_prospective_affected_endpoints": primary_links,
        "primary_cross_task_prospective_affected_endpoints": (
            primary_links - primary_links // 2
        ),
        "primary_components": primary_links,
        "primary_largest_component_endpoints": 2 if primary_links else 0,
        "primary_largest_component_tasks": 2 if primary_links else 0,
        "primary_large_multitask_components": 0,
        "strict_near_duplicate_pairs": 0,
        "strict_prospective_affected_endpoints": 0,
        "gate_checks": {
            "historical_fingerprint_coverage": gate_pass,
            "prospective_fingerprint_coverage": gate_pass,
            "prospective_affected_endpoint_fraction": gate_pass,
            "cross_task_prospective_affected_endpoint_fraction": gate_pass,
            "large_multitask_components": gate_pass,
            "bipartite_join_self_check": gate_pass,
        },
        "strong_low_identifier_erased_overlap_support": gate_pass,
        "producer_ab_byte_identical": True,
        "verifier_ab_byte_identical": True,
        "independent_aggregate_matches": True,
        "subset_bruteforce_matches": True,
        "historical_label_or_observation_fields_used": False,
        "prospective_outcomes_read": False,
        "prediction_values_read": False,
        "gpu_api_model_fit_base_update": [0, 0, 0, 0],
        "semantic_equivalence_proven": False,
        "pretraining_contamination_absence_proven": False,
        "closure_rerun_required": True,
    }
    recheck = {
        "protocol": "historical_identifier_erased_887_independent_recheck_v1",
        "status": "INDEPENDENT_RECHECK_COMPLETE",
        "classification": classification,
        "source_commit": HISTORICAL_SOURCE_COMMIT,
        "snapshot_sha256": SNAPSHOT_SHA256,
        "primary_near_duplicate_pairs": primary_links,
        "strict_near_duplicate_pairs": 0,
        "producer_ab_byte_identical": True,
        "verifier_ab_byte_identical": True,
        "outcomes_read": False,
        "prediction_values_read": False,
        "gpu_api_model_fit_base_update": [0, 0, 0, 0],
    }
    _write(root / "formal_summary.json", summary)
    _write(root / "independent_recheck.json", recheck)
    bindings = {
        "source_commit": HISTORICAL_SOURCE_COMMIT,
        "snapshot_sha256": SNAPSHOT_SHA256,
        "protocol_sha256": HISTORICAL_RESULT_PROTOCOL_SHA256,
        "formal_root": HISTORICAL_FORMAL_ROOT,
        "formal_summary_sha256": _sha(root / "formal_summary.json"),
        "postflight_root": HISTORICAL_POSTFLIGHT_ROOT,
        "postflight_logic_sha256": HISTORICAL_POSTFLIGHT_LOGIC_SHA256,
        "independent_recheck_sha256": _sha(root / "independent_recheck.json"),
    }
    _write(root / "source_bindings.json", bindings)
    (root / "README.md").write_text("synthetic fixture\n", encoding="utf-8")
    (root / "access_attestation.txt").write_text(
        "boundary_aware_credential_file_hits=0\n"
        "prospective_label_outcome_prediction_values_read=false\n"
        "gpu_api_model_fit_base_update=0/0/0/0\n",
        encoding="utf-8",
        newline="\n",
    )
    names = [
        "README.md",
        "access_attestation.txt",
        "formal_summary.json",
        "independent_recheck.json",
        "source_bindings.json",
    ]
    (root / "SHA256SUMS").write_text(
        "".join(f"{_sha(root / name)}  {name}\n" for name in names),
        encoding="utf-8",
        newline="\n",
    )
    return root


@pytest.mark.parametrize(
    ("primary_links", "gate_pass", "expected"),
    [
        (0, True, ZERO_CLASSIFICATION),
        (2, True, LOW_CLASSIFICATION),
        (0, False, FAIL_CLASSIFICATION),
    ],
)
def test_three_ordered_certificate_outcomes(
    tmp_path: Path, primary_links: int, gate_pass: bool, expected: str
) -> None:
    historical = _historical_package(
        tmp_path / "historical", primary_links=primary_links, gate_pass=gate_pass
    )
    certificate = build(PROTOCOL, PROTOCOL_SHA256, WITHIN, historical)
    assert certificate["classification"] == expected
    assert certificate["security"] == {
        "raw_corpus_or_archive_reopened": False,
        "task_run_card_code_or_edge_identities_read": False,
        "prospective_label_outcome_prediction_values_read": False,
        "gpu_api_model_fit_base_update": [0, 0, 0, 0],
        "randomness_used": False,
    }
    result_path = tmp_path / "certificate.json"
    _write(result_path, certificate)
    receipt = verify(
        PROTOCOL,
        PROTOCOL_SHA256,
        WITHIN,
        historical,
        result_path,
        _sha(result_path),
    )
    assert receipt["classification"] == expected
    assert receipt["imports_builder"] is False


def test_package_manifest_tampering_fails_closed(tmp_path: Path) -> None:
    historical = _historical_package(tmp_path / "historical")
    summary = historical / "formal_summary.json"
    summary.write_text(summary.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(CertificateError, match="hash mismatch"):
        build(PROTOCOL, PROTOCOL_SHA256, WITHIN, historical)


def test_actual_two_axis_packages_build_the_zero_link_certificate(
    tmp_path: Path,
) -> None:
    certificate = build(PROTOCOL, PROTOCOL_SHA256, WITHIN, HISTORICAL)
    assert certificate["classification"] == ZERO_CLASSIFICATION
    assert certificate["certificate_gates"] == {
        "historical_to_future_integrity": True,
        "historical_to_future_zero_links": True,
        "independent_postflights_passed": True,
        "same_future_snapshot_population": True,
        "same_representation_and_threshold": True,
        "within_future_integrity": True,
        "within_future_zero_cross_run_links": True,
    }
    result_path = tmp_path / "certificate.json"
    _write(result_path, certificate)
    receipt = verify(
        PROTOCOL,
        PROTOCOL_SHA256,
        WITHIN,
        HISTORICAL,
        result_path,
        _sha(result_path),
    )
    assert receipt["classification"] == ZERO_CLASSIFICATION


def test_independent_verifier_does_not_import_builder() -> None:
    source = (PHASE1 / "verify_split_integrity_certificate_887.py").read_text(
        encoding="utf-8"
    )
    assert "from phase1.build_split_integrity_certificate_887" not in source
    assert "import phase1.build_split_integrity_certificate_887" not in source


def test_formal_runner_rebinds_both_remote_formal_and_postflight_roots() -> None:
    source = (
        PHASE1 / "scripts" / "run_split_integrity_certificate_887_20260828.sh"
    ).read_text(encoding="utf-8")
    for name in (
        "within_formal",
        "within_postflight",
        "historical_formal",
        "historical_postflight",
    ):
        assert f"readonly {name}=" in source
        assert f'"${{{name}}}"' in source
    assert 'test -f "${root}/COMPLETE"' in source
    assert 'test ! -e "${root}/FAILED_RC"' in source
    assert source.count("sha256sum -c SHA256SUMS") >= 1
    assert source.count("formal_summary.json\"") >= 4
    assert source.count("independent_recheck.json\"") >= 4
    assert source.count("formal_sha256sums_file_sha256") == 2
    assert source.count("postflight_sha256sums_file_sha256") == 2
