import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "phase1" / "outcome_blind_no_fit_support_renewal_v2.json"
V1 = ROOT / "phase1" / "scripts" / "renew_outcome_blind_no_fit_support_20260901.sh"
V2 = ROOT / "phase1" / "scripts" / "renew_outcome_blind_no_fit_support_20260901_v2.sh"
WL_MONITOR = ROOT / "phase1" / "scripts" / "monitor_wl_snapshot_chain_20260826.sh"


def test_v2_preserves_no_fit_scope_and_corrects_resource_estimate():
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    assert protocol["protocol_id"] == "outcome-blind-no-fit-support-renewal-v2"
    assert protocol["scientific_scope_changed"] is False
    assert protocol["v1_failure_chain"]["v1_wl_state_promoted"] is False
    assert protocol["v1_failure_chain"]["v1_receipt_state_promoted"] is False
    assert protocol["authorized_actions"]["transition"].startswith("FORBIDDEN")
    assert protocol["resource_matrix"]["model_fits"] == 0
    assert protocol["resource_matrix"]["expected_active_compute_minutes"] == "45-70"
    assert all(value is False for value in protocol["blindness"].values())


def test_v1_required_an_event_the_monitor_does_not_emit():
    v1 = V1.read_text(encoding="utf-8")
    monitor = WL_MONITOR.read_text(encoding="utf-8")
    assert "new_snapshot poll=1 old=${prior} new=${latest}" in v1
    assert "new_snapshot" not in monitor


def test_v2_uses_matrix_receipt_and_process_groups():
    script = V2.read_text(encoding="utf-8")
    assert script.count("setsid env") == 2
    assert script.count("nohup env") == 0
    assert 'kill -TERM -- "-${pid}"' in script
    assert 'kill -KILL -- "-${pid}"' in script
    assert "new_snapshot poll=1" not in script
    for field in (
        "protocol=wl-snapshot-chain-monitor-v1",
        "prior_snapshot=${prior}",
        "current_snapshot=${latest}",
        "prior_all_runs=494",
        "current_all_runs=517",
        "minimum_new_runs=12",
        "gpu_jobs=0",
        "api_calls=0",
        "base_llm_updates=0",
        "effect_metrics=0",
    ):
        assert field in script
    assert "v1_partial_output_reused=false" in script
    assert "transition_script=" not in script
    assert "monitor_transition_snapshot_chain_20260826.sh" not in script


def test_v2_binds_failed_chain_and_fresh_root():
    script = V2.read_text(encoding="utf-8")
    assert "outcome-blind-no-fit-support-renewal-20260901-v2" in script
    assert "20260901T122214Z_e9e12c639fde" in script
    assert "45d186e7f0d8581820a928e26aed9d1497d6037f02dbbba34cf4a60b96518618" in script
    assert 'test ! -e "${action_root}"' in script
    assert 'git -C "${public_repo}" show "${public_commit}:${public_path}"' in script
    assert 'git -C "${public_repo}" show "${public_commit}:${protocol_path}"' in script
