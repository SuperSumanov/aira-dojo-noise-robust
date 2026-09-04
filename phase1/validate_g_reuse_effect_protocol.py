from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


PROTOCOL_NAME = "g-reuse-effect-v1"
STATUS = "FROZEN_AWAITING_SOURCE_G0_AND_GPU_APPROVAL"
ARM_IDS = [
    "L1",
    "Lbudget",
    "G-reuse-budget",
    "G-reuse-to-L-full",
    "Ghash-reuse-to-L-full",
]
SEEDS = [6, 7, 8]
FIXED_ACROSS = [
    "pivot checkpoint",
    "tokenizer prompt serialization and context length",
    "optimizer learning-rate schedule warmup and weight decay",
    "effective pair batch and gradient normalization",
    "seed set",
    "eligible local and global row identities",
    "common valid-token cap",
    "final-checkpoint evaluation policy",
]
PENDING_FALSE_FIELDS = [
    "same_producer_cards_global_local_split_source_received",
    "whole_experiment_train_dev_frozen_closed",
    "pair_card_physical_run_overlap_zero_verified",
    "exact_generator_config_stratum_verified",
    "g0_walltime_peak_memory_checkpoint_receipt_verified",
    "core_manifests_producer_ab_and_independent_verifier_passed",
    "explicit_gpu_hour_approval_received",
]
PENDING_NULL_FIELDS = [
    "exact_pivot_checkpoint",
    "exact_common_valid_token_cap",
    "exact_gpu_hours",
]
ROOT_FIELDS = {
    "protocol",
    "status",
    "frozen_at_utc",
    "supersedes_for_effect_execution",
    "question",
    "claim_scope",
    "evidence_timing",
    "authorization",
    "pending_contract",
    "fixed_across_compute_matched_arms",
    "forbidden_inputs",
    "core_stage",
    "core_gates",
    "hash_control",
    "conditional_cost_stage",
    "failure_policy",
}


class ProtocolError(ValueError):
    pass


def _reject_duplicate_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ProtocolError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_protocol(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    try:
        value = json.loads(raw, object_pairs_hook=_reject_duplicate_object)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ProtocolError(f"invalid protocol JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ProtocolError("protocol root must be an object")
    return value, raw


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ProtocolError(message)


def validate_protocol(value: dict[str, Any]) -> dict[str, Any]:
    _require(set(value) == ROOT_FIELDS, "root schema drift")
    _require(value.get("protocol") == PROTOCOL_NAME, "wrong protocol name")
    _require(value.get("status") == STATUS, "wrong or prematurely unlocked status")

    timing = value.get("evidence_timing", {})
    _require(set(timing) == {
        "protocol_frozen_before_authoritative_source_delivery",
        "protected_evaluation_values_opened",
        "new_model_effect_opened",
        "historical_structural_development_results_known",
        "historical_outer_test_touched",
    }, "evidence timing schema drift")
    _require(timing.get("protocol_frozen_before_authoritative_source_delivery") is True, "protocol timing changed")
    _require(timing.get("protected_evaluation_values_opened") is False, "protected values opened")
    _require(timing.get("new_model_effect_opened") is False, "model effect opened before authorization")

    authorization = value.get("authorization")
    _require(isinstance(authorization, dict), "authorization must be an object")
    _require(set(authorization) == {
        "gpu_jobs",
        "paid_api_calls",
        "model_fits",
        "base_llm_updates",
        "effect_or_replay_submissions",
    }, "authorization schema drift")
    _require(all(type(item) is int and item == 0 for item in authorization.values()), "compute or effect authorization must remain zero")

    pending = value.get("pending_contract")
    _require(isinstance(pending, dict), "pending_contract must be an object")
    _require(set(pending) == set(PENDING_FALSE_FIELDS + PENDING_NULL_FIELDS), "pending_contract schema drift")
    for key in PENDING_FALSE_FIELDS:
        _require(pending.get(key) is False, f"template must not self-attest pending field: {key}")
    for key in PENDING_NULL_FIELDS:
        _require(pending.get(key) is None, f"template must not fill pending field: {key}")
    _require(value.get("fixed_across_compute_matched_arms") == FIXED_ACROSS, "fixed-across-arm contract changed")

    core = value.get("core_stage")
    _require(isinstance(core, dict), "core_stage must be an object")
    _require(set(core) == {
        "seeds",
        "arms",
        "planned_fits",
        "checkpoint_policy",
        "primary_metric",
        "primary_uncertainty",
        "secondary_uncertainty",
        "same_pool_tfidf_required",
        "draft_improve_reported_separately",
    }, "core stage schema drift")
    _require(core.get("seeds") == SEEDS, "core seeds changed")
    arms = core.get("arms")
    _require(isinstance(arms, list), "core arms must be a list")
    _require([arm.get("id") for arm in arms if isinstance(arm, dict)] == ARM_IDS, "core arms or order changed")
    _require(len(arms) == len(ARM_IDS), "core arm count changed")
    arm_schema = {
        "id",
        "role",
        "uses_true_global_orientation",
        "uses_true_local_orientation",
        "common_valid_token_cap",
    }
    _require(all(set(arm) == arm_schema for arm in arms), "core arm schema drift")
    _require(core.get("planned_fits") == len(ARM_IDS) * len(SEEDS) == 15, "core fit count mismatch")
    _require(arms[0].get("common_valid_token_cap") is False, "L1 must remain non-headline one-pass diagnostic")
    _require(all(arm.get("common_valid_token_cap") is True for arm in arms[1:]), "compute-matched arm lost common cap")
    _require(arms[3].get("uses_true_global_orientation") is True, "full arm lost true global orientation")
    _require(arms[4].get("uses_true_global_orientation") is False, "hash arm may not read true global orientation")

    gates = value.get("core_gates", {})
    _require(set(gates) == {
        "full_minus_lbudget_point_minimum",
        "full_minus_lbudget_task_ci_lower_strictly_positive",
        "full_minus_lbudget_all_seed_signs_positive",
        "full_minus_g_reuse_budget_task_ci_lower_strictly_positive",
        "full_minus_tfidf_task_ci_lower_strictly_positive",
        "quality_hash_control_tested_only_after_deployment_gates",
        "full_minus_hash_task_ci_lower_strictly_positive",
        "leave_one_task_out_sign_must_not_flip",
        "single_task_correct_difference_share_maximum",
        "nan_oom_incomplete_or_access_violation_allowed",
    }, "core gate schema drift")
    _require(gates.get("full_minus_lbudget_point_minimum") == 0.02, "deployment point gate changed")
    _require(gates.get("full_minus_lbudget_task_ci_lower_strictly_positive") is True, "task CI gate changed")
    _require(gates.get("full_minus_lbudget_all_seed_signs_positive") is True, "seed sign gate changed")
    _require(gates.get("leave_one_task_out_sign_must_not_flip") is True, "LOTO gate changed")
    _require(gates.get("single_task_correct_difference_share_maximum") == 0.35, "single-task gate changed")
    _require(gates.get("nan_oom_incomplete_or_access_violation_allowed") is False, "failure gate changed")

    hash_control = value.get("hash_control", {})
    _require(set(hash_control) == {
        "seed",
        "endpoint_utility",
        "pair_level_independent_flips",
        "shared_endpoint_order_is_transitive",
        "global_rows_order_tokens_updates_match_full",
        "local_phase_byte_identical_to_full",
        "true_global_orientation_read",
        "collision_action",
    }, "hash-control schema drift")
    _require(hash_control.get("seed") == 20260823, "hash-control seed changed")
    _require(hash_control.get("pair_level_independent_flips") is False, "pair-level random flips enabled")
    _require(hash_control.get("shared_endpoint_order_is_transitive") is True, "hash order lost transitivity")
    _require(hash_control.get("global_rows_order_tokens_updates_match_full") is True, "hash global schedule mismatch allowed")
    _require(hash_control.get("local_phase_byte_identical_to_full") is True, "hash local phase mismatch allowed")
    _require(hash_control.get("true_global_orientation_read") is False, "hash control may read true global orientation")
    _require(hash_control.get("collision_action") == "fail closed", "hash collision no longer fails closed")

    cost = value.get("conditional_cost_stage", {})
    _require(set(cost) == {
        "enabled_only_if_all_core_gates_pass",
        "arm",
        "seeds",
        "planned_additional_fits",
        "selection_reads_train_structure_and_token_cost_only",
        "selected_identity_manifest_public",
        "selected_identity_manifest_hash_and_counts_public",
        "try_other_budget_points_after_failure",
        "g_valid_token_reduction_minimum",
        "total_valid_token_reduction_minimum",
        "spectral_minus_full_task_ci_lower_strictly_greater_than",
        "each_seed_point_difference_minimum",
        "leave_one_task_out_point_difference_minimum",
        "single_task_absolute_difference_share_maximum",
    }, "cost stage schema drift")
    _require(cost.get("enabled_only_if_all_core_gates_pass") is True, "cost stage may not run before core")
    _require(cost.get("arm") == "G-reuse-to-L-spectral50", "cost arm changed")
    _require(cost.get("seeds") == SEEDS, "cost seeds changed")
    _require(cost.get("planned_additional_fits") == len(SEEDS) == 3, "cost fit count mismatch")
    _require(cost.get("try_other_budget_points_after_failure") is False, "post-result budget rescue enabled")
    _require(cost.get("g_valid_token_reduction_minimum") == 0.25, "G cost gate changed")
    _require(cost.get("total_valid_token_reduction_minimum") == 0.10, "total cost gate changed")
    _require(cost.get("spectral_minus_full_task_ci_lower_strictly_greater_than") == -0.01, "noninferiority gate changed")
    _require(cost.get("each_seed_point_difference_minimum") == -0.02, "seed noninferiority gate changed")
    _require(cost.get("leave_one_task_out_point_difference_minimum") == -0.01, "LOTO noninferiority gate changed")

    failure = value.get("failure_policy", {})
    _require(set(failure) == {
        "any_pending_contract_field_blocks_fit",
        "unknown_duplicate_hash_drift_or_access_violation",
        "gate_thresholds_may_not_be_lowered_after_results",
        "failed_spectral50_may_not_be_rescued_with_25_or_75_percent",
        "structural_results_do_not_substitute_for_model_effect",
    }, "failure policy schema drift")
    _require(failure.get("any_pending_contract_field_blocks_fit") is True, "pending inputs no longer block fit")
    _require(failure.get("gate_thresholds_may_not_be_lowered_after_results") is True, "threshold mutation allowed")
    _require(failure.get("failed_spectral50_may_not_be_rescued_with_25_or_75_percent") is True, "budget rescue allowed")
    _require(failure.get("structural_results_do_not_substitute_for_model_effect") is True, "structure substituted for effect")

    blockers = PENDING_FALSE_FIELDS + PENDING_NULL_FIELDS + ["explicit GPU job and GPU-hour authorization"]
    return {
        "protocol": PROTOCOL_NAME,
        "status": STATUS,
        "ready_for_fit": False,
        "core_arms": len(ARM_IDS),
        "core_seeds": len(SEEDS),
        "core_planned_fits": 15,
        "conditional_cost_planned_fits": 3,
        "blockers": blockers,
        "protected_values_opened": False,
        "gpu_paid_api_model_fit_base_update": [0, 0, 0, 0],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    value, raw = load_protocol(args.protocol)
    receipt = validate_protocol(value)
    receipt["protocol_sha256"] = hashlib.sha256(raw).hexdigest()
    rendered = json.dumps(receipt, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(rendered, end="")
    else:
        args.output.write_text(rendered, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
