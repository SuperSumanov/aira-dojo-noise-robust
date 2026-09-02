from __future__ import annotations

import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "phase1" / "opportunity_yield_aggregation_audit_v1.json"
DRAFT = ROOT / "phase1" / "PAPER_DRAFT_DECISION_CORPUS_20260902.md"
APPENDIX = ROOT / "phase1" / "PAPER_REPRODUCIBILITY_APPENDIX_DRAFT_20260902.md"
MAP = ROOT / "phase1" / "RELATED_WORK_CITATION_MAP_20260902.md"
BIB = ROOT / "phase1" / "DECISION_CORPUS_REFERENCES_20260902.bib"


def _normalize(values: list[float]) -> list[float]:
    total = sum(values)
    return [value / total for value in values]


def _tv(left: list[float], right: list[float]) -> float:
    return 0.5 * sum(abs(a - b) for a, b in zip(left, right))


def test_existing_frozen_contract_is_the_manuscript_authority() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert contract["status"] == "FROZEN_OUTCOME_BLIND_BEFORE_FIRST960_CLOSURE"
    assert contract["authority"]["may_rescue_failed_primary"] is False
    assert contract["entry_gate"]["zero_pair_task_action"] == (
        "emit NOT_IDENTIFIABLE_FULL_TASK_UNIVERSE and do not compute the "
        "full-cohort impact headline"
    )
    assert contract["related_work_boundary"][
        "general_cluster_vs_individual_weighting_is_prior_statistical_work"
    ] is True
    assert contract["access_and_compute"] == {
        "prospective_label_grade_outcome_or_winner_orientation_read": False,
        "prediction_values_read_or_aggregated": False,
        "accuracy_effect_or_search_utility_computed": False,
        "raw_archive_payload_read": False,
        "gpu_jobs": 0,
        "api_calls": 0,
        "new_model_fits": 0,
        "base_llm_updates": 0,
    }


def test_size_bias_and_tv_identity_on_independent_synthetic_counts() -> None:
    runs = [4.0, 2.0, 5.0]
    structural = [8.0, 2.0, 5.0]
    informative = [4.0, 2.0, 4.0]
    p = _normalize(runs)
    q = _normalize(structural)
    r = _normalize(informative)
    yields = [s / n for s, n in zip(structural, runs)]
    retention = [i / s for i, s in zip(informative, structural)]
    mean_yield = sum(weight * value for weight, value in zip(p, yields))
    mean_retention = sum(weight * value for weight, value in zip(q, retention))
    reconstructed_q = [weight * value / mean_yield for weight, value in zip(p, yields)]
    reconstructed_r = [weight * value / mean_retention for weight, value in zip(q, retention)]
    assert all(math.isclose(a, b, abs_tol=1e-12) for a, b in zip(q, reconstructed_q))
    assert all(math.isclose(a, b, abs_tol=1e-12) for a, b in zip(r, reconstructed_r))

    task_metric = [0.2, 0.7, 0.5]
    a_run = sum(weight * value for weight, value in zip(p, task_metric))
    a_struct = sum(weight * value for weight, value in zip(q, task_metric))
    metric_range = max(task_metric) - min(task_metric)
    assert abs(a_struct - a_run) <= metric_range * _tv(q, p) + 1e-12


def test_zero_support_is_not_silently_recoverable() -> None:
    runs = [4, 2, 3]
    structural = [8, 2, 0]
    informative = [4, 2, 0]
    assert any(s == 0 for s in structural)
    assert any(i == 0 for i in informative)
    assert not all(s > 0 and i > 0 for s, i in zip(structural, informative))


def test_paper_packet_cites_prior_art_and_preserves_scope() -> None:
    draft = DRAFT.read_text(encoding="utf-8")
    appendix = APPENDIX.read_text(encoding="utf-8")
    mapping = MAP.read_text(encoding="utf-8")
    bib = BIB.read_text(encoding="utf-8")
    for key in ("williamson2003informativeclusters", "kahan2023clusterestimands"):
        assert f"@{key}" in draft
        assert f"{{{key}," in bib
    assert "### 4.5 Opportunity-yield size bias" in draft
    assert "not an observed predictor bias, causal\neffect, or new statistical theorem" in draft
    assert "full-task\nimpact headline is declared not identifiable" in draft
    assert "never silently removed" in appendix
    assert "Estimand and informative-cluster-size precedent" in mapping
    assert "now binds 26 primary-source-checked entries" in mapping
