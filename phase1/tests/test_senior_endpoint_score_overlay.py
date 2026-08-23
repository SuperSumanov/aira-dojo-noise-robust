from __future__ import annotations

import hashlib
import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
PATCH = REPO / "phase1" / "upstream_patches" / "0004-Emit-endpoint-score-receipts.patch"
RECEIPT = (
    REPO
    / "phase1"
    / "results"
    / "senior_endpoint_score_overlay_20260823_ac008af"
    / "verification_receipt.json"
)
EXPECTED_SHA = "237bbffe1130af74527d1a3febcfdcc3330b49a13b785c31039a79a1ac091242"


def test_overlay_patch_has_frozen_identity() -> None:
    assert hashlib.sha256(PATCH.read_bytes()).hexdigest() == EXPECTED_SHA


def test_overlay_only_changes_evaluator_receipt_and_its_test() -> None:
    text = PATCH.read_text(encoding="utf-8")
    changed = [
        line.removeprefix("diff --git a/").split(" b/", 1)[0]
        for line in text.splitlines()
        if line.startswith("diff --git a/")
    ]
    assert changed == [
        "src/mle_critic/src/evaluation/bradley_terry_evaluation.py",
        "src/mle_critic/test/test_one_shot_evaluation_contract.py",
    ]
    assert '+            "better_score": better_score,' in text
    assert '+            "worse_score": worse_score,' in text
    assert "margin disagrees with endpoint scores" in text
    assert "src/mle_critic/src/train/" not in "\n".join(changed)


def test_receipt_is_effect_blocked_and_records_unrelated_collection_failure() -> None:
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    assert value["base_commit"] == "ac008af8b907d319b694f26b0ba9cf4053b3bf69"
    assert value["patches"][-1] == EXPECTED_SHA
    assert value["formal_status"] == "ENDPOINT_RECEIPT_OVERLAY_READY_EFFECT_ASSETS_PENDING"
    assert value["remote_verification"]["focused_tests_passed"] == 36
    assert value["remote_verification"]["expanded_suite"]["tests_failed"] == 0
    assert value["access_attestation"] == {
        "api_calls": 0,
        "future_truth_opened": False,
        "gpu_jobs": 0,
        "model_fits": 0,
    }
