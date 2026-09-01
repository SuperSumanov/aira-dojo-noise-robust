import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "phase1" / "outcome_blind_no_fit_support_renewal_v1.json"
LAUNCHER = ROOT / "phase1" / "scripts" / "renew_outcome_blind_no_fit_support_20260901.sh"


def test_protocol_freezes_exact_no_fit_scope():
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    assert protocol["protocol_id"] == "outcome-blind-no-fit-support-renewal-v1"
    assert protocol["trigger"] == {
        "latest_snapshot_sha256": "e9e12c639fdeb54f3c18ef9d55841db60332baedfe8149774006e458ab8e8a6d",
        "latest_inventory": {
            "all_physical_runs": 543,
            "eligible_runs": 517,
            "eligible_endpoints": 13581,
            "eligible_structural_pairs": 3325,
            "eligible_tasks": 38,
        },
        "source_archives": 283,
        "prior_promoted_snapshot_sha256": "30945550b6b12a146dadd6eda733c3b676b467aef86636ae31ac59813133104f",
        "prior_promoted_eligible_runs": 494,
        "eligible_run_delta": 23,
        "wl_minimum_new_runs": 12,
        "batch_gate_crossed": True,
    }
    assert protocol["resource_matrix"]["gpu_jobs"] == 0
    assert protocol["resource_matrix"]["paid_api_calls"] == 0
    assert protocol["resource_matrix"]["model_fits"] == 0
    assert protocol["resource_matrix"]["base_llm_updates"] == 0
    assert protocol["authorized_actions"]["transition"].startswith("FORBIDDEN")
    assert all(value is False for value in protocol["blindness"].values())


def test_launcher_can_only_start_wl_and_receipt_monitors():
    script = LAUNCHER.read_text(encoding="utf-8")
    assert script.count("nohup env") == 2
    assert 'bash "${wl_script}"' in script
    assert 'bash "${receipt_script}"' in script
    assert "transition_script=" not in script
    assert "monitor_transition_snapshot_chain_20260826.sh" not in script
    assert "WL_CHAIN_MINIMUM_NEW_RUNS=12" in script
    assert "RECEIPT_SUPPORT_STABLE_POLLS=3" in script
    assert "CONFIG_V2_SIDECAR_FILENAME_COUNT" not in script
    assert "*.config_v2.jsonl" in script


def test_launcher_is_exact_commit_fail_closed():
    script = LAUNCHER.read_text(encoding="utf-8")
    required_fragments = (
        'git -C "${public_repo}" show "${public_commit}:${public_path}"',
        'git -C "${public_repo}" show "${public_commit}:${protocol_path}"',
        'test "$(tr -d \'\\r\\n\' <"${state}/LATEST")" = "${latest}"',
        'test ! -e "${action_root}"',
        'all_pid_owners_dead "${wl_root}"',
        'all_pid_owners_dead "${receipt_root}"',
        'lock_is_free "${wl_root}/monitor.lock"',
        'lock_is_free "${receipt_root}/monitor.lock"',
        'test "$(sha256sum "${transition_root}/state.tsv"',
        'test "$(sha256sum "${transition_root}/monitor.log"',
        'new_snapshot poll=1 old=${prior} new=${latest}',
    )
    for fragment in required_fragments:
        assert fragment in script
    assert 'sha256sum "${action_root}/safe_receipt.txt"' in script
    assert 'sha256sum "${action_root}/wl.stdout"' not in script
    assert 'sha256sum "${action_root}/receipt.stdout"' not in script
