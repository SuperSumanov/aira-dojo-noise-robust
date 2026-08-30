from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RESULT_ROOT = ROOT / "phase1/results/foreagent_loeo_graph_denoising_v1_20260830_9429577"
RESULT = RESULT_ROOT / "result.json"
VERIFICATION = RESULT_ROOT / "verification.json"
RECEIPT = ROOT / "phase1/foreagent_loeo_graph_denoising_formal_receipt_20260830.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_canonical_artifacts_match_formal_hashes() -> None:
    assert sha256(RESULT) == "b00ab6b786a83e04255904845a010d5278e838e9d3c3d15ab9e743dc8831e96b"
    assert sha256(VERIFICATION) == (
        "a69128906fe330d1d3b90f035c0fbe1e49c5ec49d16c124086e181d792eac524"
    )


def test_frozen_classification_does_not_claim_denoising_gain() -> None:
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    assert result["classification"] == "NO_DENOISING_GAIN_MODEL_COMPARISON_REMAINS_STABLE"
    gates = result["frozen_gates"]
    assert gates == {
        "at_least_one_task_macro_gain_ci_lower_gt_zero": False,
        "both_model_task_macro_gain_points_nonnegative": False,
        "coverage_pass": True,
        "hybrid_model_comparison_ci_lower_gt_zero": True,
        "minimum_pair_coverage": 0.9,
    }
    assert result["metrics"]["deepseek"]["task_bootstrap_ci"][
        "hybrid_minus_raw_task_macro"
    ] == [-0.0043703959864033895, 0.00991932144534674]
    assert result["metrics"]["gpt"]["point"]["hybrid_minus_raw_task_macro"] == (
        -0.0014593090007331022
    )


def test_graph_corrected_model_comparison_is_task_robust() -> None:
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    paired = result["paired_deepseek_minus_gpt"]
    assert paired["raw_task_macro_delta_ci"][0] == -0.00020939006472648432
    assert paired["hybrid_task_macro_delta_ci"] == [
        0.006733984687049144,
        0.05938772182771875,
    ]
    assert paired["hybrid_loto_positive"] == paired["loto_total"] == 26
    assert result["claim_boundary"]["algorithmic_novelty_claimed"] is False
    assert result["claim_boundary"]["prospective_confirmation"] is False


def test_receipt_and_independent_verification_are_consistent() -> None:
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    verification = json.loads(VERIFICATION.read_text(encoding="utf-8"))
    assert receipt["status"] == "FORMAL_COMPLETE_AND_INDEPENDENT_POSTFLIGHT_PASS"
    assert receipt["source_commit"] == "942957757fd0c8464b1670ab3e35da64f4cccebf"
    assert receipt["tests"] == {
        "preflight_items_passed": 13,
        "focused_passed": 16,
        "full_phase1_passed": 1789,
        "full_phase1_warnings": 48,
        "full_phase1_seconds": 134.14,
    }
    assert receipt["security"]["network_hits"] == 0
    assert receipt["security"]["credential_content_hits"] == 0
    assert receipt["security"]["prospective_sources_read"] is False
    assert verification["status"] == "PASS"
    assert verification["checked_numeric_fields"] == 45
    assert verification["maximum_absolute_numeric_difference"] == 0.0
