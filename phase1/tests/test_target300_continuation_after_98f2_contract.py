from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "target300_continuation_after_98f2_v1.json"
MONITOR_PATH = ROOT / "scripts" / "monitor_target300_after_98f2_20260831.sh"
DEPLOY_PATH = ROOT / "scripts" / "deploy_target300_continuation_after_98f2_20260831.sh"
PROTOCOL_SHA = "3a9027792d9d0b6a5466788007b363a9472b62f26409f2fc13eff88987670f97"
MONITOR_SHA = "e35ea6e2ed7cb243e93e20acc1edecbd655155033fb9c5fa4b86ffc453a1be7b"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_protocol_is_frozen_before_successor_identity_readout() -> None:
    value = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    assert value["protocol"] == "target300_continuation_after_98f2_v1"
    assert value["status"] == "FROZEN_BEFORE_SUCCESSOR_TARGET300_IDENTITY_READOUT"
    disclosure = value["pre_readout_disclosure"]
    assert disclosure["target300_selected_runs_on_current_successor_read"] is False
    assert disclosure["target300_boundary_overshoot_read"] is False
    assert disclosure["target300_candidate_identities_or_profile_read"] is False
    assert disclosure["target300_private_selection_read"] is False
    assert disclosure["target300_truth_outcome_prediction_accuracy_or_utility_read"] is False
    assert _sha(PROTOCOL_PATH) == PROTOCOL_SHA


def test_previous_prefix_and_runner_are_exactly_bound() -> None:
    value = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    science = value["fixed_science"]
    assert science["base_latest_snapshot_sha256"].startswith("98f2cba9")
    assert science["previous_selected_runs"] == 193
    assert science["previous_selected_archives"] == 60
    assert science["previous_remaining_runs"] == 107
    assert science["previous_exact_prefix_survived"] is True
    assert science["previous_summary_sha256"].startswith("01d67cec")
    assert science["previous_verification_sha256"].startswith("59624c59")
    assert science["runner_sha256"].startswith("c6f6ed7a")
    assert value["continuity_contract"][
        "previous_193_runs_and_60_archives_must_survive_as_exact_prefix"
    ] is True


def test_trigger_is_fixed_and_caller_cannot_choose_snapshot() -> None:
    value = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    trigger = value["trigger"]
    assert trigger["stable_observations_required"] == 5
    assert trigger["poll_interval_seconds"] == 300
    assert trigger["minimum_first_to_fifth_observation_seconds"] == 1200
    assert trigger["maximum_polls"] == 144
    assert trigger["candidate_change_resets_stability_count"] is True
    assert trigger["no_manual_snapshot_argument"] is True
    assert trigger["no_retry_or_alternate_candidate_after_formal_failure"] is True
    monitor = MONITOR_PATH.read_text(encoding="utf-8")
    assert "readonly STABLE_POLLS=5" in monitor
    assert "readonly POLL_SECONDS=300" in monitor
    assert "stable_count >= STABLE_POLLS" in monitor
    assert monitor.index("stable_count >= STABLE_POLLS") < monitor.index(
        'bash "${patched}" "${SCIENCE_COMMIT}" "${PREVIOUS}"'
    )


def test_monitor_and_deployer_preserve_blindness_and_resource_scope() -> None:
    monitor = MONITOR_PATH.read_text(encoding="utf-8")
    deploy = DEPLOY_PATH.read_text(encoding="utf-8")
    combined = monitor + deploy
    assert _sha(MONITOR_PATH) == MONITOR_SHA
    assert f"readonly CONTINUATION_PROTOCOL_SHA={PROTOCOL_SHA}" in monitor
    assert f"readonly protocol_sha={PROTOCOL_SHA}" in deploy
    assert f"readonly monitor_sha={MONITOR_SHA}" in deploy
    assert "formal.private.stdout" in monitor
    assert "cohort_runs.jsonl" not in combined
    assert "cohort_archives.jsonl" not in combined
    assert "sbatch" not in combined
    assert "curl " not in combined
    assert "wget " not in combined
    assert "gpu api model-fit base-update 0/0/0/0" in monitor
    assert "outcomes_read=false identities_read=false" in monitor


def test_deployer_refuses_duplicate_monitor_or_existing_anchor() -> None:
    deploy = DEPLOY_PATH.read_text(encoding="utf-8")
    assert 'test ! -e "${root}"' in deploy
    assert 'test ! -e "${anchor}"' in deploy
    assert 'flock -n -s 8' in deploy
    assert 'test "$(git -C "${base_repo}" rev-parse fork/phase1-value-critic)" = "${release_commit}"' in deploy
    assert "previous_summary_sha=01d67cec" in deploy
    assert "previous_verification_sha=59624c59" in deploy
