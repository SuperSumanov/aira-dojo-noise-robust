from __future__ import annotations

import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
PROTOCOL = REPO / "phase1" / "global_local_calibration_candidate_protocol_v2.json"


def load() -> dict:
    return json.loads(PROTOCOL.read_text(encoding="utf-8"))


def test_candidate_is_effect_blocked_and_never_authorizes_compute() -> None:
    value = load()
    assert value["protocol"] == "global-local-calibration-candidate-v2"
    assert value["status"] == "ARMS_FROZEN_IDENTITY_G0_BUDGET_EFFECT_BLOCKED"
    assert value["common_contract_pending"]["exact_model_checkpoint"] is None
    assert value["common_contract_pending"]["exact_optimizer_token_budget"] is None
    assert value["common_contract_pending"]["exact_gpu_hours"] is None
    assert value["common_contract_pending"]["user_budget_approval_required"] is True
    assert value["scope"] == {
        "gpu_jobs_authorized": 0,
        "api_calls": 0,
        "model_fits_authorized": 0,
        "base_llm_update": False,
        "replay_or_effect_submission_authorized": False,
    }


def test_five_arms_isolate_repeat_global_calibration_and_label_information() -> None:
    value = load()
    arms = {row["id"]: row for row in value["arms"]}
    assert set(arms) == {"L1", "Lbudget", "Gbudget", "G_to_L", "Ghash_to_L"}
    assert arms["L1"]["common_optimizer_token_budget"] is False
    assert all(arms[name]["common_optimizer_token_budget"] for name in arms if name != "L1")
    assert arms["G_to_L"]["true_global_labels_used"] is True
    assert arms["Ghash_to_L"]["true_global_labels_used"] is False
    assert arms["Ghash_to_L"]["true_local_labels_used"] is True
    assert value["removed_arm"]["may_be_added_after_results_on_same_frozen_test"] is False


def test_hash_control_is_endpoint_consistent_and_grade_independent() -> None:
    control = load()["hash_control"]
    assert control["seed"] == 20260823
    assert control["pair_level_independent_flips"] is False
    assert control["shared_endpoint_order_is_transitive"] is True
    assert control["global_endpoint_rows_order_tokens_steps_match_G_to_L"] is True
    assert control["local_phase_byte_identical_to_G_to_L"] is True
    assert control["true_grade_may_affect_hash_orientation"] is False
    assert control["sha_collision_action"] == "fail closed"


def test_claim_ladder_requires_label_control_and_local_one_pass_control() -> None:
    gates = load()["hierarchical_gates"]
    assert gates["deployment_gain"]["G_to_L_minus_Lbudget_point_minimum"] == 0.02
    assert gates["quality_label_information"]["tested_only_if_deployment_gain_passes"] is True
    assert gates["quality_label_information"]["G_to_L_minus_Ghash_to_L_task_ci_lower_strictly_positive"] is True
    local = gates["local_repeat_confound"]
    assert local["comparison"] == "L1 minus Lbudget"
    assert local["if_L1_strictly_better_require_G_to_L_minus_L1_task_ci_lower_strictly_positive_for_transfer_claim"] is True


def test_single_pivot_cannot_be_mislabeled_as_scaling_confirmation() -> None:
    value = load()
    assert value["claim_scope"]["single_pivot_effect_stage_confirms_capacity_scaling"] is False
    extension = value["capacity_extension"]
    assert extension["status"] == "NOT_FROZEN_NOT_AUTHORIZED"
    assert extension["same_frozen_test_may_be_reopened_for_post_result_size_extension"] is False
