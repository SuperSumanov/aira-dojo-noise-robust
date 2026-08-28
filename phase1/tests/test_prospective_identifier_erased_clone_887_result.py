from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = (
    Path(__file__).parents[1]
    / "results"
    / "prospective_identifier_erased_clone_887_20260828_519815d"
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(name: str) -> dict[str, object]:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def test_formal_summary_is_exactly_bound_and_strictly_lineage_local() -> None:
    bindings = _json("source_bindings.json")
    summary = _json("formal_summary.json")
    assert _sha(ROOT / "formal_summary.json") == bindings["formal_summary_sha256"]
    assert summary["classification"] == "STRICT_LINEAGE_LOCAL_PASS"
    assert summary["observed_runs"] == 435
    assert summary["observed_endpoints"] == 11906
    assert summary["fingerprinted_endpoints"] == 11894
    assert summary["fingerprint_coverage"] == 0.9989921048210986
    assert summary["primary_candidate_pairs"] == 7990766
    assert summary["primary_near_duplicate_pairs"] == 11421
    assert summary["primary_relation_pair_counts"] == {
        "cross_run_cross_task": 0,
        "cross_run_same_task": 0,
        "parent_child": 5713,
        "same_parent_siblings": 235,
        "same_run_other": 5473,
    }
    assert summary["primary_cross_run_pairs"] == 0
    assert summary["strict_near_duplicate_pairs"] == 4068
    assert summary["strict_cross_run_pairs"] == 0
    assert summary["strict_lineage_local_support"] is True
    assert all(summary["gate_checks"].values())
    assert summary["focused_tests"] == {
        "passed": 27,
        "skipped": 0,
        "warnings": 0,
    }
    assert summary["full_tests"] == {
        "passed": 1240,
        "skipped": 0,
        "warnings": 47,
    }


def test_independent_postflight_and_claim_boundary_are_preserved() -> None:
    bindings = _json("source_bindings.json")
    recheck = _json("independent_recheck.json")
    assert _sha(ROOT / "independent_recheck.json") == bindings[
        "independent_recheck_sha256"
    ]
    assert recheck["status"] == "INDEPENDENT_RECHECK_COMPLETE"
    assert recheck["classification"] == "STRICT_LINEAGE_LOCAL_PASS"
    assert recheck["producer_ab_byte_identical"] is True
    assert recheck["verifier_ab_byte_identical"] is True
    assert recheck["forbidden_path_hits"] == 0
    assert recheck["credential_file_hits"] == 0
    assert recheck["outcomes_read"] is False
    assert recheck["prediction_values_read"] is False
    assert recheck["gpu_api_model_fit_base_update"] == [0, 0, 0, 0]
    summary = _json("formal_summary.json")
    assert summary["semantic_equivalence_proven"] is False
    assert summary["closure_rerun_required"] is True
    assert summary["prospective_outcomes_read"] is False
    assert summary["prediction_values_read"] is False
    assert summary["gpu_api_model_fit_base_update"] == [0, 0, 0, 0]
