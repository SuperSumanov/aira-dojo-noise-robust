from __future__ import annotations

import hashlib
import json
from pathlib import Path


RESULT = (
    Path(__file__).parents[1]
    / "results"
    / "structural_dependency_atlas_7cda_20260825"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(name: str) -> dict:
    value = json.loads((RESULT / name).read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_committed_atlas_hashes_and_formal_binding() -> None:
    expected = {
        "atlas.json": "1c3e5c34afe82a236e4f242373ee7b71fd44d90207eb2d74b9177fb6776db1a5",
        "independent_verification.json": "634c57840667d4cd9a301fb3d8c8d39e37c161ea1d11872a57ac740d951c150f",
        "headline_metrics.json": "f6db60ae066323ff3e65944ab24d3c30e18074765f080d4f2618de4bfc86814f",
    }
    assert {name: sha256(RESULT / name) for name in expected} == expected
    formal = load("formal_summary.json")
    assert formal["status"] == "FORMAL_STRUCTURAL_DEPENDENCY_ATLAS_PASS"
    assert formal["outputs"] == {
        "atlas_sha256": expected["atlas.json"],
        "independent_verification_sha256": expected["independent_verification.json"],
        "headline_metrics_sha256": expected["headline_metrics.json"],
    }
    assert formal["source_commit"] == "b8ea5f7e3d30ced33043167ecaffcb363bb4e320"
    assert len(formal["failure_history"]) == 4
    assert formal["security"] == {
        "filename_secret_hits": 0,
        "content_secret_hits": 0,
        "forbidden_open_trace_hits": 0,
        "label_grade_outcome_prediction_or_winner_orientation_read": False,
        "accuracy_effect_or_search_utility_computed": False,
        "gpu_calls": 0,
        "api_calls": 0,
        "base_llm_updates": 0,
    }


def test_committed_atlas_key_findings_and_claim_limits() -> None:
    atlas = load("atlas.json")
    verification = load("independent_verification.json")
    headline = load("headline_metrics.json")
    current = atlas["scopes"]["provisional_first960_prefix"]
    first = atlas["scopes"]["provisional_first240"]
    assert first["inventory"]["runs"] == 240
    assert current["inventory"] == {
        "runs": 339,
        "tasks": 30,
        "endpoints": 10196,
        "structural_pairs": 2635,
        "pair_tasks": 30,
    }
    assert headline["current_pair_inverse_hhi_diversity"] == 7.366637206731296
    assert headline["pair_dominant_task_share_amplification_vs_its_run_share"] == 5.041962591488208
    assert headline["pairs_per_parent_group"] == 1.0161974546856922
    assert headline["chronological_flags"] == {
        "pair_inverse_hhi_diversity_fell_despite_more_tasks": True,
        "run_max_share_fell_while_pair_max_share_rose": True,
    }
    assert verification["status"] == "INDEPENDENT_STRUCTURAL_DEPENDENCY_ATLAS_PASS"
    assert all(verification["checks"].values())
    assert atlas["estimand_contract"][
        "inverse_hhi_is_descriptive_diversity_not_effective_sample_size"
    ] is True
    assert atlas["security"]["accuracy_effect_or_search_utility_computed"] is False
