from __future__ import annotations

import hashlib
from pathlib import Path

import phase1.score_channel_future_cohort as producer
import phase1.verify_score_channel_future_cohort as verifier


ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "scripts" / "run_target300_schema_v2_once_20260831.sh"
DEPLOY = ROOT / "scripts" / "deploy_target300_schema_v2_20260831.sh"
BASE_RUNNER = ROOT / "scripts" / "run_score_channel_future_cohort_20260823.sh"
WRAPPER_SHA = "1674743050c7d333476c6a88b3627f869a2bcbde9b9318641298d530e39761c5"
DEPLOY_SHA = "08fe53516b3aa3d047bd24aba0361884b65ebb5bcbbe0bf10751edf990f99306"
PATCHED_RUNNER_SHA = "0f50c1dc8d0742b688a14a4c000d66cfa4e1bf95ccb90bdf4a2135221d5edbff"
CANDIDATE = "30945550b6b12a146dadd6eda733c3b676b467aef86636ae31ac59813133104f"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_producer_and_verifier_share_the_minimal_schema_amendment() -> None:
    expected_optional = {"competition_id_source"}
    expected_values = {"explicit_journal", "archive_consensus_fallback"}
    assert producer.PROVENANCE_OPTIONAL_KEYS == expected_optional
    assert verifier.PROVENANCE_OPTIONAL_KEYS == expected_optional
    assert producer.COMPETITION_ID_SOURCES == expected_values
    assert verifier.COMPETITION_ID_SOURCES == expected_values
    assert producer.PROVENANCE_REQUIRED_KEYS == verifier.PROVENANCE_REQUIRED_KEYS
    assert "competition_id_source" not in producer.RUN_OUTPUT_KEYS
    assert "competition_id_source" not in verifier.RUN_KEYS


def test_both_readers_keep_missing_extra_and_invalid_value_fail_closed() -> None:
    producer_source = " ".join(
        (ROOT / "score_channel_future_cohort.py").read_text(encoding="utf-8").split()
    )
    verifier_source = " ".join(
        (ROOT / "verify_score_channel_future_cohort.py").read_text(encoding="utf-8").split()
    )
    assert "PROVENANCE_REQUIRED_KEYS <= set(row)" in producer_source
    assert "<= PROVENANCE_REQUIRED_KEYS | PROVENANCE_OPTIONAL_KEYS" in producer_source
    assert "invalid source provenance competition source" in producer_source
    assert "PROVENANCE_REQUIRED_KEYS <= set(row)" in verifier_source
    assert "<= PROVENANCE_REQUIRED_KEYS | PROVENANCE_OPTIONAL_KEYS" in verifier_source
    assert "provenance competition source failed" in verifier_source


def test_one_shot_wrapper_is_bound_to_failure_candidate_and_previous_prefix() -> None:
    script = WRAPPER.read_text(encoding="utf-8")
    assert _sha(WRAPPER) == WRAPPER_SHA
    assert f"readonly CANDIDATE={CANDIDATE}" in script
    assert "target300_schema_v2_attempt_1" in script
    assert "previous_runs=193" in script
    assert "v1_must_not_be_retried" in script
    assert 'test ! -e "${ANCHOR}"' in script
    assert 'flock -n 9' in script
    assert "gpu api model-fit base-update 0/0/0/0" in script
    assert "outcomes_read=false identities_read=false" in script


def test_runtime_runner_patch_is_exact_and_hash_bound() -> None:
    text = BASE_RUNNER.read_text(encoding="utf-8")
    old_worktree = (
        "worktree=/research/d7/spc/yzyang4/worktrees/"
        "future_identity_cohort_${short}_nosmudge"
    )
    new_worktree = (
        "worktree=/research/d7/spc/yzyang4/worktrees/"
        "future_identity_cohort_${short}_schema_v2_30945550_nosmudge"
    )
    latest_line = "latest_before=$(tr -d '\\r\\n' < \"${state}/LATEST\")"
    candidate_gate = latest_line + f'\ntest "${{latest_before}}" = {CANDIDATE}'
    assert text.count(old_worktree) == 1
    assert text.count(latest_line) == 1
    patched = text.replace(old_worktree, new_worktree).replace(latest_line, candidate_gate)
    assert hashlib.sha256(patched.encode("utf-8")).hexdigest() == PATCHED_RUNNER_SHA


def test_deployer_refuses_duplicate_or_changed_candidate() -> None:
    script = DEPLOY.read_text(encoding="utf-8")
    assert _sha(DEPLOY) == DEPLOY_SHA
    assert f"readonly candidate={CANDIDATE}" in script
    assert 'test ! -e "${root}"' in script
    assert 'test ! -e "${anchor}"' in script
    assert 'test "$(tr -d' in script and '"${state}/LATEST")" = "${candidate}"' in script
    assert 'test "$(git -C "${base_repo}" rev-parse fork/phase1-value-critic)" = "${release_commit}"' in script
    assert "v1_retry=false" in script
    assert "alternate_candidate=false" in script


def test_v2_scripts_remain_cpu_only_and_do_not_call_network_apis() -> None:
    combined = WRAPPER.read_text(encoding="utf-8") + DEPLOY.read_text(encoding="utf-8")
    assert "sbatch" not in combined
    assert "srun" not in combined
    assert "curl " not in combined
    assert "wget " not in combined
    assert "api.openai" not in combined
    assert "dashscope" not in combined
    assert "formal.private.stdout" in combined
