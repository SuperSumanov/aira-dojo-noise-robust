from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "target300_continuous_schema_v2_continuation_v1.json"
MONITOR = ROOT / "scripts" / "monitor_target300_continuous_schema_v2_20260831.sh"
DEPLOY = ROOT / "scripts" / "deploy_target300_continuous_schema_v2_20260831.sh"
PROTOCOL_SHA = "8a499b626c5e88549af6d9e797c36cef7f02e4461d7a3c2c9c66c3c6ccfa6a23"
MONITOR_SHA = "1111950030bb2b1d93e7ed9a5e7a22fcd5ee1d58e74ed90c53a267e33e7a599d"
DEPLOY_SHA = "3d67dd076d89f276780e0405797a7f0b680f2c6a3631222923c72957681760bb"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_chain_starts_from_the_verified_219_run_formal_prefix() -> None:
    value = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    assert value["protocol"] == "target300_continuous_schema_v2_continuation_v1"
    assert value["status"] == "FROZEN_BEFORE_ANY_POST_309_SUCCESSOR"
    initial = value["initial_state"]
    assert initial["previous_selected_runs"] == 219
    assert initial["previous_selected_archives"] == 69
    assert initial["remaining_runs"] == 81
    assert initial["previous_exact_prefix_survived"] is True
    assert initial["first_closed_anchor_absent"] is True
    assert _sha(PROTOCOL) == PROTOCOL_SHA


def test_successor_rule_cannot_skip_or_choose_a_snapshot() -> None:
    value = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    rule = value["successor_rule"]
    assert rule["stable_observations_required"] == 5
    assert rule["poll_interval_seconds"] == 300
    assert rule["minimum_first_to_fifth_observation_seconds"] == 1200
    assert rule["candidate_change_resets_stability_count"] is True
    assert rule["caller_snapshot_argument_allowed"] is False
    assert rule["alternate_candidate_selection_allowed"] is False
    assert rule["maximum_polls"] == 2016


def test_each_collecting_result_becomes_the_next_exact_prefix() -> None:
    value = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    chain = value["chain_rule"]
    assert chain["process_candidates_in_observed_order"] is True
    assert chain["formal_collecting_result_becomes_next_previous_prefix"] is True
    assert chain["previous_prefix_must_survive_exactly"] is True
    assert chain["formal_failure_stops_entire_chain"] is True
    assert chain["failed_candidate_retry_allowed"] is False
    monitor = MONITOR.read_text(encoding="utf-8")
    assert monitor.index("previous=${formal}/producer_a") < monitor.index("base=${candidate}")
    assert monitor.index("base=${candidate}") < monitor.index("attempt=$((attempt + 1))")
    assert 'if (( rc != 0 )); then\n        exit "${rc}"' in monitor


def test_monitor_patches_only_worktree_isolation_and_candidate_gate() -> None:
    monitor = MONITOR.read_text(encoding="utf-8")
    assert _sha(MONITOR) == MONITOR_SHA
    assert f"readonly CHAIN_PROTOCOL_SHA={PROTOCOL_SHA}" in monitor
    assert "^worktree=/research/d7/spc/yzyang4/worktrees/future_identity_cohort_" in monitor
    assert "^latest_before=" in monitor
    assert "grep -c '^@@'" in monitor and '" = 2' in monitor
    assert "grep -c '^[-+]worktree='" in monitor
    assert "exact_prefix_survived" in monitor
    assert "formal_roots" in monitor


def test_deployer_is_exact_head_singleton_and_anchor_safe() -> None:
    deploy = DEPLOY.read_text(encoding="utf-8")
    assert _sha(DEPLOY) == DEPLOY_SHA
    assert 'test ! -e "${root}"' in deploy
    assert 'test ! -e "${anchor}"' in deploy
    assert 'test "$(tr -d' in deploy and '"${state}/LATEST")" = "${base_latest}"' in deploy
    assert 'rev-parse fork/phase1-value-critic)" = "${release_commit}"' in deploy
    assert "no_change poll=1" in deploy
    assert "ordered_chain=true" in deploy
    assert "failed_candidate_retry=false" in deploy
    assert "alternate_candidate=false" in deploy


def test_continuous_chain_is_cpu_only_and_keeps_private_values_private() -> None:
    combined = MONITOR.read_text(encoding="utf-8") + DEPLOY.read_text(encoding="utf-8")
    for forbidden in ("sbatch", "srun", "curl ", "wget ", "api.openai", "dashscope"):
        assert forbidden not in combined
    assert "private.stdout" in combined
    assert "cohort_runs.jsonl" not in combined
    assert "cohort_archives.jsonl" not in combined
    assert "outcomes_read=false identities_read=false" in combined
    assert "gpu api model-fit base-update 0/0/0/0" in combined
