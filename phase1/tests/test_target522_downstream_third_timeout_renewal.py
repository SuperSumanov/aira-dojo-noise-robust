from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "phase1/target522_downstream_third_timeout_renewal_v1.json"
SCRIPT = ROOT / "phase1/scripts/renew_target522_downstream_after_third_timeout_20260902.sh"
RECEIPT = ROOT / "phase1/target522_downstream_third_timeout_postdeploy_receipt_20260902.json"


def test_protocol_binds_observed_third_timeout_state() -> None:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    frozen = protocol["frozen_preconditions"]
    assert frozen["selection_runs"] == 517
    assert frozen["selection_target_runs"] == 522
    assert frozen["selection_remaining_runs"] == 5
    assert frozen["selection_pid"] == 2930562
    assert frozen["stage_a"]["old_pid"] == 3451204
    assert frozen["contrast_rank"]["old_pid"] == 3451299
    assert frozen["stage_a"]["timeout_rc"] == 124
    assert frozen["contrast_rank"]["timeout_rc"] == 124
    assert frozen["stage_a"]["last_wait_poll"] == 720
    assert frozen["contrast_rank"]["last_wait_poll"] == 720


def test_protocol_preserves_blindness_and_zero_compute_contract() -> None:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    post = protocol["postconditions"]
    resources = protocol["resources"]
    assert post["prospective_values_read"] is False
    assert post["candidate_profile_or_private_identity_read"] is False
    assert resources == {
        "cpu_metadata_waiters_only": True,
        "gpu": 0,
        "paid_api": 0,
        "model_fit": 0,
        "base_model_update": 0,
    }


def test_script_only_launches_the_two_current_downstream_waiters() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert text.count("nohup bash") == 2
    assert "tree-within-stratum-forward-target522/formal-monitor" not in text
    assert "tree-content-lineage-forward-target522/formal-monitor" not in text
    assert "tree-content-selective-parent-forward-target522/formal-monitor" not in text
    assert "lookahead" not in text.lower()
    assert "GPU_API_MODEL_FIT_BASE_UPDATE=0/0/0/0" in text


def test_script_checks_both_prior_contexts_and_never_deletes_them() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "initial_context_sha" in text
    assert "renewal1_context_sha" in text
    assert "post_gap_repeat_timeout_renewal_2_context.txt" in text
    assert "rm " not in text
    assert "FAILED_RC" in text
    assert "preflight_13.txt" in text


def test_script_binds_itself_to_a_public_exact_commit() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "TARGET522_THIRD_TIMEOUT_PUBLIC_COMMIT" in text
    assert "git -C \"${repo}\" cat-file -e" in text
    assert "git -C \"${repo}\" show \"${public_commit}:${public_path}\"" in text
    assert "git -C \"${repo}\" merge-base --is-ancestor" in text
    assert "d6f6719b9b5ce8182c4473ee82f56b1b2533cd2f904f2db025653cd48392077d" in text


def test_postdeploy_receipt_records_independent_pass_and_harness_failure() -> None:
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    assert receipt["status"] == (
        "TARGET522_DOWNSTREAM_THIRD_TIMEOUT_RENEWAL_INDEPENDENTLY_VERIFIED"
    )
    assert receipt["selection"]["runs"] == 517
    assert receipt["selection"]["remaining_runs"] == 5
    assert receipt["stage_a"]["new_pid_live"] is True
    assert receipt["contrast_rank"]["new_pid_live"] is True
    post = receipt["independent_postdeploy"]
    assert post["v1_status"].startswith("ZERO_HIT_CREDENTIAL_GREP_RC_")
    assert post["v1_mutated_remote_state"] is False
    assert post["v2_status"] == "PASS"
    assert post["credential_filename_hits"] == 0
    assert post["credential_content_hits"] == 0
    assert receipt["scope"]["outcomes_or_prediction_values_read"] is False
    assert receipt["scope"]["gpu_paid_api_model_fit_base_update"] == "0/0/0/0"
