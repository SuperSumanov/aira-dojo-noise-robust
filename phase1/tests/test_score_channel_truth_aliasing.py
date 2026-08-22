from __future__ import annotations

import json
from pathlib import Path

import pytest

from phase1 import score_channel_truth_aliasing as producer
from phase1 import verify_score_channel_truth_aliasing as verifier


def fixture_rows():
    selected = [
        {
            "candidate_card_ids": ["a", "b"],
            "task": "task-a",
            "run_id": "run-1",
            "parent_id": "parent-1",
        },
        {
            "candidate_card_ids": ["c", "d"],
            "task": "task-a",
            "run_id": "run-2",
            "parent_id": "parent-2",
        },
        {
            "candidate_card_ids": ["e", "f"],
            "task": "task-b",
            "run_id": "run-3",
            "parent_id": "parent-3",
        },
        {
            "candidate_card_ids": ["g", "h"],
            "task": "task-b",
            "run_id": "run-4",
            "parent_id": "parent-4",
        },
    ]
    labels_dict = {
        "a": {"graded": 0.1, "y_norm": 0.0},
        "b": {"graded": 0.2, "y_norm": 0.0},
        "c": {"graded": 0.3, "y_norm": 0.2},
        "d": {"graded": 0.4, "y_norm": 0.3},
        "e": {"graded": 0.5, "y_norm": 1.0},
        "f": {"graded": 0.5, "y_norm": 1.0},
        "g": {"graded": 0.6, "y_norm": 0.5},
        "h": {"graded": 0.6, "y_norm": 0.5},
    }
    labels_tuple = {card: (row["graded"], row["y_norm"]) for card, row in labels_dict.items()}
    results = {
        card: {"sub_exists": False, "sub_score": None, "val_how": "none", "stdout_val": None}
        for card in labels_dict
    }
    results["a"] = {"sub_exists": True, "sub_score": 0.1, "val_how": "keyed", "stdout_val": 0.9}
    results["b"] = {"sub_exists": True, "sub_score": 0.2, "val_how": "keyed", "stdout_val": 0.1}
    return selected, labels_dict, labels_tuple, results, {"task-a": 1, "task-b": -1}


def test_aliasing_and_raw_common_credit_are_reconstructed_independently() -> None:
    selected, labels_dict, labels_tuple, results, orientation = fixture_rows()
    actual = producer.summarize(selected, labels_dict, results, orientation, 1, 1)
    independent = verifier.independent_summary(selected, labels_tuple, results, orientation, 1, 1)
    assert actual == independent
    assert actual["truth_support"] == {
        "raw_tied_parents": 2,
        "raw_nontied_parents": 2,
        "normalized_tied_parents": 3,
        "normalized_nontied_parents": 1,
        "alias_parents": 1,
        "alias_tasks": 1,
        "impossible_direction_parents": 0,
        "normalized_tied_boundary_counts": {"all_zero": 1, "all_one": 1, "interior": 1},
        "official_five_decimal_grid_violations": 0,
    }
    assert actual["common_channel_support"] == {
        "comparative_parents": 1,
        "raw_nontied_parents": 1,
        "normalized_nontied_parents": 0,
        "raw_truth_descriptive_credit": {
            "parents": 1,
            "external_top1_credit": 1.0,
            "stdout_top1_credit": 0.0,
            "delta": 1.0,
        },
    }
    assert actual["material_aliasing_gate"]["status"] == "MATERIAL_Y_NORM_ALIASING"


def test_impossible_raw_tie_normalized_order_fails_closed() -> None:
    selected, labels_dict, labels_tuple, results, orientation = fixture_rows()
    labels_dict["f"]["y_norm"] = 0.9
    labels_tuple["f"] = (0.5, 0.9)
    with pytest.raises(producer.AliasingError):
        producer.summarize(selected, labels_dict, results, orientation, 1, 1)
    with pytest.raises(verifier.VerificationError):
        verifier.independent_summary(selected, labels_tuple, results, orientation, 1, 1)


def test_candidate_reuse_fails_closed() -> None:
    selected, labels_dict, labels_tuple, results, orientation = fixture_rows()
    selected[1]["candidate_card_ids"][0] = "a"
    with pytest.raises(producer.AliasingError):
        producer.summarize(selected, labels_dict, results, orientation, 1, 1)
    with pytest.raises(verifier.VerificationError):
        verifier.independent_summary(selected, labels_tuple, results, orientation, 1, 1)


def test_five_decimal_grid_violation_is_counted() -> None:
    selected, labels_dict, labels_tuple, results, orientation = fixture_rows()
    labels_dict["a"]["graded"] = 0.123456
    labels_tuple["a"] = (0.123456, 0.0)
    a = producer.summarize(selected, labels_dict, results, orientation, 1, 1)
    b = verifier.independent_summary(selected, labels_tuple, results, orientation, 1, 1)
    assert a == b
    assert a["truth_support"]["official_five_decimal_grid_violations"] == 1


def test_frozen_protocol_declares_post_hoc_limits() -> None:
    path = Path("phase1/score_channel_truth_aliasing_protocol_v1.json")
    value = json.loads(path.read_text(encoding="utf-8"))
    assert value["status"] == "FROZEN_POST_HOC_RAW_GRADE_NOT_READ"
    assert value["timing_and_evidence"]["old_primary_outcomes_already_known"] is True
    assert value["timing_and_evidence"]["raw_graded_alias_counts_read_before_freeze"] is False
    assert value["interpretation_limits"]["may_reverse_old_machine_verdict"] is False
    assert value["scope"] == {
        "gpu_jobs": 0,
        "api_calls": 0,
        "model_fits": 0,
        "base_llm_update": False,
    }
