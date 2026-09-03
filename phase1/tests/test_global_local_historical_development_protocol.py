import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "phase1" / "global_local_historical_development_protocol_v1.json"
FROZEN = ROOT / "phase1" / "global_local_calibration_candidate_protocol_v2.json"
FROZEN_SHA = "3e0785a13f9d9fc3638a222e78fd74010757b1201249ebd0ad7a5597c224a2e9"


def load():
    return json.loads(PROTOCOL.read_text(encoding="utf-8"))


def test_successor_approves_only_implementation_and_preserves_frozen_v2():
    value = load()
    assert value["status"] == "APPROVED_PROTOCOL_IMPLEMENTATION_EFFECT_BUDGET_BLOCKED"
    assert hashlib.sha256(FROZEN.read_bytes()).hexdigest() == FROZEN_SHA
    assert value["relationship_to_frozen_v2"] == {
        "path": "phase1/global_local_calibration_candidate_protocol_v2.json",
        "sha256": FROZEN_SHA,
        "modified_or_superseded": False,
        "scope": "historical development only; never confirmatory",
        "reason_for_successor": "real pair lengths make strict whole-pair valid-token and fixed-step equality jointly unreachable under the six predeclared diagnostic orders",
    }
    assert value["scope"] == {
        "gpu_jobs_authorized": 0,
        "api_calls": 0,
        "model_fits_authorized": 0,
        "base_llm_update": False,
        "frozen_or_prospective_outcome_access_authorized": False,
        "first960_target300_target522_access_authorized": False,
        "effect_submission_authorized": False,
    }


def test_real_historical_counts_and_common_token_cap_are_bound():
    value = load()
    inputs = value["historical_inputs"]
    assert inputs["local_train"]["pairs"] == 4689
    assert inputs["global_source"]["identity_projected_candidate_pairs"] == 9392
    assert inputs["combined_pairs_once"] == 14081
    assert inputs["combined_valid_tokens_once"] == 104863947
    assert inputs["local_train"]["valid_tokens_once"] == 32187742
    assert inputs["global_source"]["candidate_valid_tokens_once"] == 72676205
    assert value["budget"]["common_valid_token_cap"] == 104863947
    assert inputs["global_source"]["status"].startswith("identity-only candidate")


def test_budget_revision_does_not_overclaim_compute_matching():
    value = load()
    budget = value["budget"]
    assert budget["whole_pairs_only"]
    assert budget["optimizer_steps_may_differ_between_arms"]
    assert budget["token_step_and_gpu_compute_all_claimed_exactly_equal"] is False
    assert budget["real_pairs_dropped"] is False
    assert budget["real_pairs_repeated_for_batch_padding"] is False
    assert budget["synthetic_zero_loss_placeholders"] is False
    assert budget["remainder_smaller_than_world_size_action"] == "fail closed under v1"


def test_order_lr_and_cross_arm_controls_are_fixed_before_effects():
    value = load()
    assert value["ordering"]["seeds"] == [6, 7, 8]
    assert value["ordering"]["label_or_winner_orientation_used"] is False
    assert value["ordering"]["the_earlier_simplified_diagnostic_order_is_adopted"] is False
    optimizer = value["optimizer"]
    assert optimizer["peak_learning_rate_decimal"] == "0.00001"
    assert optimizer["warmup_valid_tokens"] == 3145919
    assert optimizer["warmup_fraction_rational"] == [3, 100]
    assert optimizer["after_warmup"] == "constant peak learning rate"
    assert optimizer["stage_or_arm_restart"] is False
    assert "first complete L source pass" in optimizer["L1_relation"]
    control = value["hash_control"]
    assert control["G_and_Ghash_inputs_order_tokens_updates_LR_and_save_point_identical"]
    assert control["true_global_labels_read_by_hash_arm"] is False


def test_five_arms_and_original_effect_gates_are_retained():
    value = load()
    assert {row["id"] for row in value["arms"]} == {
        "L1", "Lbudget", "Gbudget", "G_to_L", "Ghash_to_L"
    }
    gates = value["evaluation_and_claim_gates"]
    assert gates["inherits_without_relaxation_from_frozen_v2_sha256"] == FROZEN_SHA
    assert gates["G_to_L_minus_Lbudget_point_minimum"] == 0.02
    assert gates["G_to_L_minus_Lbudget_task_ci_lower_strictly_positive"]
    assert gates["G_to_L_minus_Ghash_to_L_tested_only_after_deployment_gain"]
    assert gates["G_to_L_minus_Ghash_to_L_task_ci_lower_strictly_positive"]
    assert gates["final_step_checkpoint_only"]

