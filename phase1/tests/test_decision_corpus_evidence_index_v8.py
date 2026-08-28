from __future__ import annotations

import copy
import inspect
import json
import shutil
from pathlib import Path

import pytest

from phase1 import build_decision_corpus_evidence_index_v8 as builder
from phase1 import verify_decision_corpus_evidence_index_v8 as verifier


REPO_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_RELATIVE = Path("phase1/decision_corpus_evidence_index_v8_protocol_v1.json")


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def seal(root: Path) -> None:
    members = sorted(path for path in root.iterdir() if path.is_file() and path.name != "SHA256SUMS")
    (root / "SHA256SUMS").write_text(
        "".join(f"{builder.sha256_file(path)}  {path.name}\n" for path in members),
        encoding="utf-8",
        newline="\n",
    )


def release_summary(protocol: dict, classification: str) -> tuple[dict, dict, dict]:
    status = protocol["ordered_status_mapping"][classification]
    all_gates = classification != "RELEASE_SPLIT_INTEGRITY_GATE_FAIL"
    gate_checks = {
        "historical_fingerprint_coverage": True,
        "prospective_fingerprint_coverage": True,
        "prospective_affected_fraction": True,
        "cross_task_prospective_affected_fraction": True,
        "large_multitask_components": True,
        "bipartite_join_self_check": True,
    }
    if not all_gates:
        gate_checks["prospective_affected_fraction"] = False
    primary_links = 0 if classification == "ZERO_IDENTIFIER_ERASED_RELEASE_LINKS" else 2
    source = protocol["complete_release_temporal_package"]
    population = protocol["fixed_population"]
    summary = {
        "protocol": "historical-release-future-identifier-erased-package-v1",
        "status": source["required_formal_status"],
        "classification": classification,
        "evidence_index_status": status,
        "source_commit": source["audit_source_commit"],
        "packager_source_commit": "1" * 40,
        "snapshot_sha256": source["snapshot_sha256"],
        "historical_endpoints": population["historical_release_endpoints"],
        "historical_runs": population["historical_release_runs"],
        "historical_tasks": population["historical_release_tasks"],
        "prospective_endpoints": population["future_endpoints"],
        "prospective_runs": population["future_runs"],
        "prospective_tasks": population["future_tasks"],
        "primary_candidate_pairs": 17,
        "primary_near_duplicate_pairs": primary_links,
        "strict_near_duplicate_pairs": 0,
        "gate_checks": gate_checks,
        "all_pre_registered_gates_passed": all_gates,
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
        "status": source["required_independent_status"],
        "classification": classification,
        "evidence_index_status": status,
        "source_commit": source["audit_source_commit"],
        "snapshot_sha256": source["snapshot_sha256"],
        "producer_aggregate_matches": True,
        "subset_bruteforce_matches": True,
        "primary_candidate_pairs": 17,
        "primary_near_duplicate_pairs": primary_links,
        "strict_near_duplicate_pairs": 0,
        "all_pre_registered_gates_passed": all_gates,
        "raw_senior_archives_opened": False,
        "prospective_outcomes_read": False,
        "prediction_values_read": False,
        "gpu_api_model_fit_base_update": [0, 0, 0, 0],
        "imports_packager_builder": False,
    }
    bindings = {
        "protocol": "historical-release-future-identifier-erased-package-bindings-v1",
        "status": source["required_binding_status"],
        "package_protocol_sha256": source["package_protocol_sha256"],
        "source_commit": source["audit_source_commit"],
        "snapshot_sha256": source["snapshot_sha256"],
        "prior_failed_formal_rc": 124,
        "prior_failed_deployment_rc": 1,
        "prior_failed_result_file_created": False,
        "prior_failed_result_values_read": False,
        "scientific_protocol_changed_in_r2": False,
    }
    return summary, independent, bindings


def fixture_repo(tmp_path: Path, classification: str) -> tuple[Path, Path]:
    root = tmp_path / "repo"
    root.mkdir()
    protocol_source = REPO_ROOT / PROTOCOL_RELATIVE
    protocol_path = root / PROTOCOL_RELATIVE
    protocol_path.parent.mkdir(parents=True)
    shutil.copy2(protocol_source, protocol_path)
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    source_spec = protocol["source_v7"]
    source_target = root / source_spec["path"]
    source_target.parent.mkdir(parents=True)
    shutil.copy2(REPO_ROOT / source_spec["path"], source_target)
    split_spec = protocol["physical_run_split_certificate"]
    shutil.copytree(REPO_ROOT / split_spec["root"], root / split_spec["root"])
    package_protocol_spec = protocol["complete_release_temporal_package"]
    package_protocol_target = root / package_protocol_spec["package_protocol_path"]
    package_protocol_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(REPO_ROOT / package_protocol_spec["package_protocol_path"], package_protocol_target)
    package_root = root / package_protocol_spec["root"]
    package_root.mkdir(parents=True)
    summary, independent, bindings = release_summary(protocol, classification)
    write_json(package_root / "formal_summary.json", summary)
    write_json(package_root / "independent_recheck.json", independent)
    write_json(package_root / "source_bindings.json", bindings)
    (package_root / "README.md").write_text("fixture\n", encoding="utf-8", newline="\n")
    (package_root / "access_attestation.txt").write_text(
        "raw_senior_archives_opened=false\n"
        "historical_label_or_observation_fields_used=false\n"
        "prospective_label_grade_outcome_prediction_values_read=false\n"
        "task_run_card_code_or_edge_identities_emitted=false\n"
        "gpu_api_model_fit_base_update=0/0/0/0\n",
        encoding="utf-8",
        newline="\n",
    )
    seal(package_root)
    return root, protocol_path


@pytest.mark.parametrize(
    ("classification", "expected_status"),
    [
        (
            "ZERO_IDENTIFIER_ERASED_RELEASE_LINKS",
            "PROVISIONAL_TEMPORAL_SPLIT_CERTIFIED_EVIDENCE_STACK_AWAITING_FIRST960",
        ),
        (
            "LOW_IDENTIFIER_ERASED_RELEASE_OVERLAP_WITH_EXCEPTIONS",
            "PROVISIONAL_QUALIFIED_TEMPORAL_SPLIT_EVIDENCE_STACK_AWAITING_FIRST960",
        ),
        ("RELEASE_SPLIT_INTEGRITY_GATE_FAIL", "TEMPORAL_SPLIT_EVIDENCE_STACK_GATE_FAIL"),
    ],
)
def test_three_way_status_is_frozen_and_independently_verified(
    tmp_path: Path, classification: str, expected_status: str
) -> None:
    root, protocol_path = fixture_repo(tmp_path, classification)
    payload = builder.build_index(root, protocol_path, builder.PROTOCOL_SHA256)
    assert payload["status"] == expected_status
    assert payload["entries"][-1]["name"] == "complete_release_temporal_overlap_certificate"
    candidate = root / "candidate.json"
    write_json(candidate, payload)
    receipt = verifier.verify_candidate(root, protocol_path, candidate)
    assert receipt["index_status"] == expected_status
    assert receipt["classification"] == classification
    assert receipt["entry_count"] == 16
    assert receipt["inherited_entry_count"] == 14
    assert receipt["appended_entry_count"] == 2
    assert receipt["producer_function_imported"] is False


def test_source_v7_entries_are_inherited_byte_semantically(tmp_path: Path) -> None:
    root, protocol_path = fixture_repo(tmp_path, "ZERO_IDENTIFIER_ERASED_RELEASE_LINKS")
    payload = builder.build_index(root, protocol_path, builder.PROTOCOL_SHA256)
    source = json.loads((root / payload["source_v7_index"]["path"]).read_text(encoding="utf-8"))
    assert payload["entries"][:14] == source["entries"]
    assert payload["source_v7_index"]["entries_inherited_without_modification"] == 14


def test_release_manifest_omission_fails_closed(tmp_path: Path) -> None:
    root, protocol_path = fixture_repo(tmp_path, "ZERO_IDENTIFIER_ERASED_RELEASE_LINKS")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    package_root = root / protocol["complete_release_temporal_package"]["root"]
    (package_root / "README.md").unlink()
    with pytest.raises(builder.BuildError, match="manifest"):
        builder.build_index(root, protocol_path, builder.PROTOCOL_SHA256)


def test_security_drift_fails_closed(tmp_path: Path) -> None:
    root, protocol_path = fixture_repo(tmp_path, "ZERO_IDENTIFIER_ERASED_RELEASE_LINKS")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    package_root = root / protocol["complete_release_temporal_package"]["root"]
    summary = json.loads((package_root / "formal_summary.json").read_text(encoding="utf-8"))
    summary["prediction_values_read"] = True
    write_json(package_root / "formal_summary.json", summary)
    (package_root / "SHA256SUMS").unlink()
    seal(package_root)
    with pytest.raises(builder.BuildError, match="predictions read"):
        builder.build_index(root, protocol_path, builder.PROTOCOL_SHA256)


def test_independent_classification_drift_fails_closed(tmp_path: Path) -> None:
    root, protocol_path = fixture_repo(tmp_path, "ZERO_IDENTIFIER_ERASED_RELEASE_LINKS")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    package_root = root / protocol["complete_release_temporal_package"]["root"]
    independent = json.loads((package_root / "independent_recheck.json").read_text(encoding="utf-8"))
    independent["classification"] = "LOW_IDENTIFIER_ERASED_RELEASE_OVERLAP_WITH_EXCEPTIONS"
    write_json(package_root / "independent_recheck.json", independent)
    (package_root / "SHA256SUMS").unlink()
    seal(package_root)
    with pytest.raises(builder.BuildError, match="classification"):
        builder.build_index(root, protocol_path, builder.PROTOCOL_SHA256)


def test_verifier_rejects_result_dependent_claim_drift(tmp_path: Path) -> None:
    root, protocol_path = fixture_repo(tmp_path, "ZERO_IDENTIFIER_ERASED_RELEASE_LINKS")
    payload = builder.build_index(root, protocol_path, builder.PROTOCOL_SHA256)
    payload["entries"][-1]["supported_claim"] = "Semantic decontamination proven."
    candidate = root / "candidate.json"
    write_json(candidate, payload)
    with pytest.raises(verifier.VerificationError, match="claim mapping"):
        verifier.verify_candidate(root, protocol_path, candidate)


def test_verifier_rejects_deleted_critical_assertion(tmp_path: Path) -> None:
    root, protocol_path = fixture_repo(tmp_path, "ZERO_IDENTIFIER_ERASED_RELEASE_LINKS")
    payload = builder.build_index(root, protocol_path, builder.PROTOCOL_SHA256)
    del payload["entries"][-1]["artifacts"][0]["json_assertions"][
        "all_pre_registered_gates_passed"
    ]
    candidate = root / "candidate.json"
    write_json(candidate, payload)
    with pytest.raises(verifier.VerificationError, match="assertion membership"):
        verifier.verify_candidate(root, protocol_path, candidate)


def test_protocol_hash_drift_fails_closed(tmp_path: Path) -> None:
    root, protocol_path = fixture_repo(tmp_path, "ZERO_IDENTIFIER_ERASED_RELEASE_LINKS")
    protocol_path.write_text(protocol_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(builder.BuildError, match="protocol SHA"):
        builder.build_index(root, protocol_path, builder.PROTOCOL_SHA256)


def test_verifier_does_not_import_builder() -> None:
    source = inspect.getsource(verifier)
    assert "build_decision_corpus_evidence_index_v8" not in source
    assert "from phase1 import build" not in source
