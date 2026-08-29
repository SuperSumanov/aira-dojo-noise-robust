import os
from pathlib import Path
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "phase1" / "scripts"
BASELINE = "887491a021d75d889c00a5af672a11b8b06e249d98e84fd91288534080f62697"


def read(name: str) -> str:
    return (SCRIPTS / name).read_text(encoding="utf-8")


def test_guard_is_fixed_public_outcome_blind_window() -> None:
    text = read("guard_outcome_blind_continuity_887_20260829_v4.sh")
    assert BASELINE in text
    assert "OUTCOME_BLIND_GUARD_CONTROL_COMMIT" in text
    assert "git -C \"${repo}\" show \"${control_commit}:${public_path}\"" in text
    assert "for poll in $(seq 0 72)" in text
    assert "sleep 300" in text
    assert "SUCCESSOR_IDENTITY_OBSERVED_HANDOFF" in text
    assert "CONFIG_V2_SIDECAR_METADATA_OBSERVED_STOP" in text
    assert "contents_opened=false" in text
    assert "prospective_values_read=false" in text


def test_renewal_requires_normal_completion_and_preserves_contracts() -> None:
    text = read("renew_outcome_blind_monitors_887_20260829_v4.sh")
    assert BASELINE in text
    assert "OUTCOME_BLIND_RENEWAL_CONTROL_COMMIT" in text
    assert "monitor_complete prior_snapshot=${baseline}" in text
    assert "monitor_complete prior=${baseline}" in text
    assert "monitor_complete_without_quiescent_new_snapshot baseline=${baseline}" in text
    assert "resume_20260829_887_v4.pid" in text
    assert "resume_20260829_887_v3.pid" in text
    assert "CONFIG_V2_MAX_POLLS=72" in text
    assert "target300_polls=144x300s" in text
    assert "test ! -e \"${target_root}/formal_rc.txt\"" in text
    assert "sidecar_contents_opened=false" in text


def test_supervisor_orders_guard_before_support_renewal() -> None:
    text = read("supervise_outcome_blind_continuity_887_20260829_v2.sh")
    assert BASELINE in text
    assert "OUTCOME_BLIND_SUPERVISOR_CONTROL_COMMIT" in text
    guard_launch = text.index("OUTCOME_BLIND_GUARD_CONTROL_COMMIT")
    renewal_launch = text.index("OUTCOME_BLIND_RENEWAL_CONTROL_COMMIT")
    assert guard_launch < renewal_launch
    assert "${guard_launched} = true" in text
    assert "${transition_done} = true" in text
    assert "${receipt_done} = true" in text
    assert "${config_done} = true" in text
    assert "${target_done} = true" in text
    assert "for poll in $(seq 1 480)" in text
    assert "contents_opened=false" in text
    assert "prospective_values_read=false" in text
    assert "20260829-supervisor-v2" in text
    assert "20260829-supervisor-v1" in text
    assert "8febae8ee4397f5f9ec5b0a00da98f1a778acb138fe1d24a00aa41fc19b337e9" in text


def test_all_lock_probes_support_read_only_completed_roots() -> None:
    for name in (
        "guard_outcome_blind_continuity_887_20260829_v4.sh",
        "renew_outcome_blind_monitors_887_20260829_v4.sh",
        "supervise_outcome_blind_continuity_887_20260829_v2.sh",
    ):
        text = read(name)
        assert "lock_is_free()" in text
        assert 'exec 8< "${lock_path}"' in text
        assert "flock -n -s 8" in text
        assert 'flock -n "${root_path}/monitor.lock" -c true' not in text
        for direct_path_probe in (
            'flock -n "${old_guard}/guard.lock" -c true',
            'flock -n "${transition_root}/monitor.lock" -c true',
            'flock -n "${receipt_root}/monitor.lock" -c true',
            'flock -n "${config_old}/monitor.lock" -c true',
            'flock -n "${target_root}/monitor.lock" -c true',
        ):
            assert direct_path_probe not in text


@pytest.mark.skipif(os.name != "posix", reason="flock semantics are Linux-specific")
def test_read_only_shared_probe_distinguishes_free_and_exclusive_lock(tmp_path: Path) -> None:
    import fcntl

    lock = tmp_path / "monitor.lock"
    lock.write_bytes(b"")
    lock.chmod(0o400)
    probe = ['bash', '-c', 'exec 8< "$1"; flock -n -s 8', '_', str(lock)]
    assert subprocess.run(probe, check=False).returncode == 0
    with lock.open("rb") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert subprocess.run(probe, check=False).returncode != 0
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def test_scripts_have_no_network_training_or_scheduler_actions() -> None:
    forbidden = ("curl ", "wget ", "sbatch", "srun ", "torchrun", "deepspeed")
    for name in (
        "guard_outcome_blind_continuity_887_20260829_v4.sh",
        "renew_outcome_blind_monitors_887_20260829_v4.sh",
        "supervise_outcome_blind_continuity_887_20260829_v2.sh",
    ):
        text = read(name)
        for token in forbidden:
            assert token not in text


def test_sidecar_payload_is_never_opened() -> None:
    for name in (
        "guard_outcome_blind_continuity_887_20260829_v4.sh",
        "renew_outcome_blind_monitors_887_20260829_v4.sh",
        "supervise_outcome_blind_continuity_887_20260829_v2.sh",
    ):
        text = read(name)
        assert "-name '*.config_v2.jsonl' -printf '.'" in text
        assert "cat *.config_v2.jsonl" not in text
        assert "< *.config_v2.jsonl" not in text
