from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).parents[2]
RESULT = ROOT / "phase1" / "results" / "decision_predictor_estimand_panel_v1_20260825"
CONTRACT = ROOT / "phase1" / "decision_predictor_estimand_panel_v1.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_committed_estimand_panel_receipt_hashes() -> None:
    assert sha256(CONTRACT) == "4f394d0e0437992eb9d3e5f3aa56f83df86ffcbda68a752ebada4e306bf7adea"
    receipt_path = RESULT / "independent_verification.json"
    assert sha256(receipt_path) == "fcb74182271d186993538a6d6517fe45e7f8ae6e6f2ccd1eaf5975ea559426de"
    receipt = load(receipt_path)
    assert receipt["status"] == "INDEPENDENT_ESTIMAND_PANEL_PASS"
    assert all(receipt["checks"].values())
    formal = load(RESULT / "formal_summary.json")
    assert formal["status"] == "FORMAL_DECISION_PREDICTOR_ESTIMAND_PANEL_PASS"
    assert formal["contract_sha256"] == sha256(CONTRACT)
    assert formal["independent_verification_sha256"] == sha256(receipt_path)


def test_committed_panel_preserves_existing_authority_and_blindness() -> None:
    contract = load(CONTRACT)
    assert contract["authority"]["supersedes_existing_experiment_primary"] is False
    assert contract["authority"]["panel_metric_may_rescue_failed_experiment_primary"] is False
    assert contract["generic_headline"]["id"] == "task_macro_parent_macro_pair_accuracy"
    assert [row["id"] for row in contract["required_nonrescuing_panel"]] == [
        "task_macro_pair_macro_accuracy",
        "task_macro_run_macro_parent_macro_pair_accuracy",
        "pair_micro_accuracy",
    ]
    assert contract["access_and_compute"] == {
        "prospective_label_grade_outcome_or_winner_orientation_read": False,
        "prediction_values_read_or_aggregated": False,
        "accuracy_effect_or_search_utility_computed": False,
        "gpu_jobs": 0,
        "api_calls": 0,
        "new_model_fits": 0,
        "base_llm_updates": 0,
    }
