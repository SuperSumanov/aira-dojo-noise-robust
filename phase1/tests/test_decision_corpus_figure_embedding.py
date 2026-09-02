from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DRAFT = ROOT / "phase1" / "PAPER_DRAFT_DECISION_CORPUS_20260902.md"
FIGURES = ROOT / "phase1" / "figures" / "decision_corpus_20260902"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_embedded_figure_assets_match_hash_receipts() -> None:
    for receipt_name in ("figure1_receipt.json", "figure2_receipt.json"):
        receipt = json.loads((FIGURES / receipt_name).read_text(encoding="utf-8"))
        assert receipt["status"] == "PASS"
        for name, expected in receipt["outputs"].items():
            assert _sha256(FIGURES / name) == expected


def test_each_png_is_embedded_exactly_once_and_exists() -> None:
    text = DRAFT.read_text(encoding="utf-8")
    for name in (
        "figure1_corpus_and_sealed_protocol.png",
        "figure2_run_to_pair_weighting.png",
    ):
        relative = f"figures/decision_corpus_20260902/{name}"
        assert text.count(relative) == 1
        assert (ROOT / "phase1" / relative).is_file()


def test_captions_preserve_claim_boundaries() -> None:
    text = DRAFT.read_text(encoding="utf-8")
    assert "protocol structure only—not predictor performance" in text
    assert "not\ntask-deletion-robust" in text
    assert "outcome-blind structural weighting diagnostic—not\npredictor bias" in text
    assert "search utility, or a causal estimate of producer\nbehavior" in text


def test_figure_receipts_attest_no_gpu_api_or_sealed_value_reads() -> None:
    figure1 = json.loads((FIGURES / "figure1_receipt.json").read_text(encoding="utf-8"))
    figure2 = json.loads((FIGURES / "figure2_receipt.json").read_text(encoding="utf-8"))

    assert figure1["gpu_api_model_fit_base_update"] == "0/0/0/0"
    assert figure1["outcome_label_prediction_accuracy_utility_read"] is False
    assert figure1["prospective_identity_profile_read"] is False

    security = figure2["security"]
    assert security["gpu_calls"] == 0
    assert security["api_calls"] == 0
    assert security["base_llm_updates"] == 0
    assert security["label_vault_opened"] is False
    assert security["score_or_prediction_values_opened"] is False
    assert security["outcome_grade_winner_orientation_opened"] is False
    assert security["eligible_blind_manifest_opened"] is False
