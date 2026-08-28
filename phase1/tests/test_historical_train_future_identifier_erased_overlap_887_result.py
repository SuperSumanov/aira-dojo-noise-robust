from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = (
    Path(__file__).parents[1]
    / "results"
    / "historical_train_future_identifier_erased_overlap_887_20260828_ec67d1a"
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(name: str) -> dict[str, object]:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def test_435_run_extension_is_exactly_bound_and_has_zero_links() -> None:
    bindings = _json("source_bindings.json")
    summary = _json("formal_summary.json")
    assert _sha(ROOT / "formal_summary.json") == bindings["formal_summary_sha256"]
    assert summary["classification"] == "ZERO_IDENTIFIER_ERASED_LINKS"
    assert summary["historical_endpoints"] == 5519
    assert summary["historical_runs"] == 333
    assert summary["historical_fingerprinted_endpoints"] == 5519
    assert summary["historical_fingerprint_coverage"] == 1.0
    assert summary["prospective_runs"] == 435
    assert summary["prospective_endpoints"] == 11906
    assert summary["prospective_fingerprinted_endpoints"] == 11894
    assert summary["prospective_fingerprint_coverage"] == 0.9989921048210986
    assert summary["primary_candidate_pairs"] == 6172443
    assert summary["primary_near_duplicate_pairs"] == 0
    assert summary["primary_same_task_pairs"] == 0
    assert summary["primary_cross_task_pairs"] == 0
    assert summary["primary_historical_affected_endpoints"] == 0
    assert summary["primary_prospective_affected_endpoints"] == 0
    assert summary["primary_components"] == 0
    assert summary["strict_near_duplicate_pairs"] == 0
    assert summary["strong_low_identifier_erased_overlap_support"] is True
    assert all(summary["gate_checks"].values())
    assert summary["focused_tests"] == {"passed": 32, "skipped": 0, "warnings": 0}
    assert summary["full_tests"] == {"passed": 1247, "skipped": 0, "warnings": 47}


def test_435_run_independent_postflight_and_claim_boundary_are_preserved() -> None:
    bindings = _json("source_bindings.json")
    recheck = _json("independent_recheck.json")
    assert _sha(ROOT / "independent_recheck.json") == bindings[
        "independent_recheck_sha256"
    ]
    assert recheck["status"] == "INDEPENDENT_RECHECK_COMPLETE"
    assert recheck["classification"] == "ZERO_IDENTIFIER_ERASED_LINKS"
    assert recheck["manifest_payload_files"] == 20
    assert recheck["producer_ab_byte_identical"] is True
    assert recheck["verifier_ab_byte_identical"] is True
    assert recheck["forbidden_path_hits"] == 0
    assert recheck["credential_file_hits"] == 0
    assert recheck["outcomes_read"] is False
    assert recheck["prediction_values_read"] is False
    assert recheck["gpu_api_model_fit_base_update"] == [0, 0, 0, 0]
    summary = _json("formal_summary.json")
    assert summary["semantic_equivalence_proven"] is False
    assert summary["pretraining_contamination_absence_proven"] is False
    assert summary["closure_rerun_required"] is True
    assert summary["historical_label_or_observation_fields_used"] is False
    assert summary["prospective_outcomes_read"] is False
    assert summary["prediction_values_read"] is False
    assert summary["gpu_api_model_fit_base_update"] == [0, 0, 0, 0]
