import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_v5_is_same_monitor_after_exact_natural_completion_only():
    value = json.loads((ROOT / "phase1/outcome_blind_intake_natural_completion_renewal_v5.json").read_text())
    assert value["status"] == "RENEWED_INDEPENDENTLY_VERIFIED"
    assert value["old_pid"] == 1692885
    assert value["postflight"]["new_pid"] == 3884166
    assert value["last_poll"] == {"index": 144, "rc": 0}
    assert value["completion_sentinels"] == 16
    assert value["runner_lock_observed_free"] is True
    assert value["same_monitor_live_processes"] == 0
    assert value["chat_heartbeat_resumed"] is False
    assert value["resources"] == {
        "fixed_polls": 145, "poll_interval_seconds": 300,
        "GPU": 0, "paid_API": 0, "model_fit": 0, "base_model_update": 0,
    }
    script = (ROOT / "phase1/scripts/renew_outcome_blind_intake_after_natural_completion_20260904_v5.sh").read_text()
    verifier = (ROOT / "phase1/scripts/verify_outcome_blind_intake_renewal_20260904_v5.sh").read_text()
    for field in ("control_commit", "monitor_script_sha256", "latest_sha256", "baseline_log_sha256"):
        assert value[field] in script
        assert value[field] in verifier
    assert value["summary_sha256"] in script
    assert "2026-09-03T17:36:47Z PROSPECTIVE_CONTINUOUS_INTAKE_MONITOR_COMPLETE polls=145 outcomes_read=false" in script


def test_v5_safe_receipt_is_hash_bound_and_blind():
    value = json.loads((ROOT / "phase1/outcome_blind_intake_natural_completion_renewal_v5.json").read_text())
    raw = (ROOT / "phase1/results/global_local_accelerate_20260904/intake_renewal_v5_safe_receipt.txt").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == value["postflight"]["safe_receipt_sha256"]
    fields = dict(line.split("=", 1) for line in raw.decode().splitlines())
    assert fields["status"] == "OUTCOME_BLIND_INTAKE_NATURAL_COMPLETION_RENEWED_V5"
    assert fields["first_new_poll_rc"] == "0"
    assert fields["outcomes_read"] == fields["candidate_profile_or_private_identity_read"] == "false"
    assert fields["gpu_paid_api_model_fit_base_update"] == "0/0/0/0"
    assert fields["new_pid"] == str(value["postflight"]["new_pid"])
