from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RESULT = ROOT / "phase1/results/prediction_escrow_coverage_7cda_20260825_6299865"


def _read(name: str) -> dict[str, object]:
    return json.loads((RESULT / name).read_text(encoding="utf-8"))


def test_coverage_matrix_is_the_exact_formal_artifact() -> None:
    raw = (RESULT / "matrix.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == (
        "be63fbe02c63c306bb488aa30416de7260e83e4701bdce3ed3f1d8843fd6f6b7"
    )
    matrix = json.loads(raw)
    assert matrix["snapshot_sha256"] == (
        "7cdaefcf2be7786442e1af1f4d0b4012edee708932f1fad31e174c0dcaf803a1"
    )
    assert matrix["formal_status"] == "OUTCOME_BLIND_PREDICTION_COVERAGE_VERIFIED"
    assert matrix["arms"]["total"] == 7
    assert matrix["access_attestation"] == {
        "accuracy_effect_or_search_utility_computed": False,
        "base_llm_updates": 0,
        "gpu_or_api_calls": 0,
        "labels_grades_outcomes_or_winner_orientation_read": False,
        "prediction_values_aggregated": False,
    }


def test_seven_arms_share_one_exact_pair_population() -> None:
    matrix = _read("matrix.json")
    for source in ("wl", "transition"):
        assert matrix["inventory"][source]["pairs"] == 2635
        assert matrix["inventory"][source]["runs"] == 334
        assert matrix["inventory"][source]["tasks"] == 30
    assert matrix["overlap"] == {
        "intersection_mapping_sha256": (
            "ca1b2b558671f4b77e2b70f4824a6fa4b2a8bd452023f4eb345b79cf383bef15"
        ),
        "intersection_over_union": 1.0,
        "intersection_pairs": 2635,
        "joint_temporal_strata": {
            "post_wl_activation|post_transition_activation": 463,
            "post_wl_activation|support_only": 507,
            "support_only|support_only": 1665,
        },
        "reversed_left_right_orientation": 0,
        "same_left_right_orientation": 2635,
        "transition_covered_by_wl": 1.0,
        "transition_effect_eligible_pairs": 399,
        "transition_only_pairs": 0,
        "union_pairs": 2635,
        "wl_covered_by_transition": 1.0,
        "wl_only_pairs": 0,
    }


def test_independent_receipt_recomputes_common_support() -> None:
    raw = (RESULT / "independent_verification.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == (
        "61e33d69816a0c33c69ab955d1de4c4e0bd6c8a7c10b0a43938f1ee033b999ef"
    )
    receipt = json.loads(raw)
    assert receipt["formal_status"] == "INDEPENDENT_COVERAGE_VERIFICATION_PASS"
    assert receipt["recomputed"] == {
        "intersection_mapping_sha256": (
            "ca1b2b558671f4b77e2b70f4824a6fa4b2a8bd452023f4eb345b79cf383bef15"
        ),
        "intersection_pairs": 2635,
        "runs_in_intersection": 334,
        "tasks_in_intersection": 30,
        "transition_pairs": 2635,
        "union_pairs": 2635,
        "wl_pairs": 2635,
    }
    assert not any(receipt["access_attestation"].values())
