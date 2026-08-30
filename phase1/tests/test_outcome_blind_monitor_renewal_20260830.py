from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "phase1" / "scripts"
BASELINE = "887491a021d75d889c00a5af672a11b8b06e249d98e84fd91288534080f62697"
GUARD = "guard_outcome_blind_continuity_887_20260830_v5.sh"
RENEWAL = "renew_outcome_blind_monitors_887_20260830_v5.sh"


def read(name: str) -> str:
    return (SCRIPTS / name).read_text(encoding="utf-8")


def test_guard_is_fixed_six_hour_outcome_blind_window() -> None:
    text = read(GUARD)
    assert BASELINE in text
    assert "OUTCOME_BLIND_GUARD_CONTROL_COMMIT" in text
    assert "git -C \"${repo}\" show \"${control_commit}:${public_path}\"" in text
    assert "for poll in $(seq 0 72)" in text
    assert "sleep 300" in text
    assert "SUCCESSOR_IDENTITY_OBSERVED_HANDOFF" in text
    assert "CONFIG_V2_SIDECAR_METADATA_OBSERVED_STOP" in text
    assert "contents_opened=false" in text
    assert "prospective_values_read=false" in text


def test_renewal_binds_old_engineering_failure_before_restart() -> None:
    text = read(RENEWAL)
    assert BASELINE in text
    assert "PROSPECTIVE_CONTINUOUS_INTAKE_MONITOR_COMPLETE polls=145 outcomes_read=false" in text
    assert '"${old_guard}/FAILED_RC"' in text
    assert "poll=71 latest=${baseline}" in text
    assert "old_guard_failure=rc1_after_poll71_and_intake_normal_145_poll_completion" in text
    assert "test \"${intake_pid}\" != \"${old_intake_pid}\"" in text


def test_renewal_binds_all_scripts_and_states() -> None:
    text = read(RENEWAL)
    for digest in (
        "b88eda114aa360a0f53b3ff5fca9180c6db7e4624362461a7c1cde76be4af841",
        "87ed6fa645de2fad25695b212434bd1dd64b6f1a44a34f6232c941ad8d8b9161",
        "458b50a3ac4499abd80c951881f69ab15f82af15a8b2bc51c950cf425d906533",
        "4cec4fd7cb2382f6e7f4e071b31212cfa45901de9dcfcc7730f18cad4e619daa",
        "e04137ae801f25debc4168bdadd4a3eb4dd068ff6a17982e1d780d14d22bac45",
        "fb393ef06c29728afa0da2f7ca26c748eb5b85bd6c065b66e5ba4f2f1cbdc0d7",
        "d675dbd92a244bb9d55b1c3377bcbb0590e91f4ce4bf5321ca8ce38284629a25",
        "ee837edf88a5a8d316a7a11664ed4090f8c681cf6982df1df69abb041e234f8c",
        "c80e94c8cc9ca25f7d5db2243ec0878443e4ceac4e0f7b41bae6b4a4d6922154",
    ):
        assert digest in text
    assert "monitor_20260830_v9" in text
    assert "resume_20260830_887_v5.pid" in text
    assert "renew_20260830_887_v3.pid" in text


def test_launch_order_is_intake_then_support_then_guard() -> None:
    text = read(RENEWAL)
    intake = text.index('bash "${intake_launcher}" --initialize')
    transition = text.index("nohup env SNAPSHOT_CHAIN_STATE_ROOT")
    receipt = text.index("nohup env RECEIPT_SUPPORT_STATE_ROOT")
    wl = text.index("nohup env WL_CHAIN_STATE_ROOT")
    guard = text.index("nohup env OUTCOME_BLIND_GUARD_CONTROL_COMMIT")
    assert intake < transition < receipt < wl < guard
    assert 'grep -Fq "latest=${baseline}" "${guard_root}/status.log"' in text


def test_read_only_locks_and_filename_only_sidecar_probe() -> None:
    for name in (GUARD, RENEWAL):
        text = read(name)
        assert "lock_is_free()" in text
        assert 'exec 8<"${lock_path}"' in text
        assert "flock -n -s 8" in text
        assert "-name '*.config_v2.jsonl' -printf '.'" in text
        assert "cat *.config_v2.jsonl" not in text
        assert "< *.config_v2.jsonl" not in text


def test_no_gpu_api_training_or_scheduler_action() -> None:
    forbidden = ("curl ", "wget ", "sbatch", "srun ", "torchrun", "deepspeed")
    for name in (GUARD, RENEWAL):
        text = read(name)
        for token in forbidden:
            assert token not in text
        assert "gpu_api_model_fit_base_update=0/0/0/0" in text or (
            "GPU API model-fit base-update 0/0/0/0" in text
        )


def test_both_scripts_require_thirteen_preflight_lines() -> None:
    for name in (GUARD, RENEWAL):
        text = read(name)
        for index in range(1, 14):
            assert f"{index:02d}_" in text
        assert 'test "$(wc -l <"${root}/preflight_13.txt")" = 13' in text
