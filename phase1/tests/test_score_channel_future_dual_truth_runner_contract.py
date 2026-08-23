from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "phase1" / "scripts" / "run_score_channel_future_dual_truth_20260823.sh"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assignments() -> dict[str, str]:
    return dict(
        re.findall(
            r"^([a-z][a-z0-9_]*)=([0-9a-f]{40,64})$",
            SCRIPT.read_text(encoding="utf-8"),
            flags=re.MULTILINE,
        )
    )


def test_frozen_protocol_and_implementation_hashes_match_sources() -> None:
    values = assignments()
    expected = {
        "base_protocol_sha": ROOT / "phase1" / "score_channel_future_identifiability_protocol_v1.json",
        "base_producer_sha": ROOT / "phase1" / "score_channel_future_truth_support.py",
        "base_verifier_sha": ROOT / "phase1" / "verify_score_channel_future_truth_support.py",
        "raw_protocol_sha": ROOT / "phase1" / "score_channel_future_raw_grade_support_protocol_v1.json",
        "raw_producer_sha": ROOT / "phase1" / "score_channel_future_raw_grade_support.py",
        "raw_verifier_sha": ROOT / "phase1" / "verify_score_channel_future_raw_grade_support.py",
    }
    assert set(expected) <= set(values)
    for name, path in expected.items():
        assert values[name] == digest(path)


def test_closed_cohort_guard_precedes_every_production_truth_invocation() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    guard = text.index("CLOSED_COHORT_GUARD_PASS_TRUTH_STILL_UNREAD")
    first_base = text.index('"${clean_python[@]}" -m phase1.score_channel_future_truth_support')
    first_raw = text.index('"${clean_python[@]}" -m phase1.score_channel_future_raw_grade_support')
    assert guard < first_base < first_raw
    assert "FUTURE_COHORT_IDENTITY_CLOSED_TRUTH_UNREAD" in text[:first_base]
    assert "remaining_runs_to_target\") != 0" in text[:first_base]
    assert 'test ! -L "${cohort_dir}/summary.json"' in text[:first_base]
    assert 'test ! -L "${cohort_dir}/cohort_runs.jsonl"' in text[:first_base]
    assert 'test ! -L "${cohort_dir}/cohort_archives.jsonl"' in text[:first_base]


def test_base_and_raw_each_use_two_producers_and_two_independent_verifiers() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert text.count("for replica in a b; do") == 4
    assert text.count("base_producer_reproducibility.diff") == 1
    assert text.count("base_verifier_reproducibility.diff") == 1
    assert text.count("raw_producer_reproducibility.diff") == 1
    assert text.count("raw_verifier_reproducibility.diff") == 1
    assert text.index("base_verifier_reproducibility.diff") < text.index("raw_common=(")


def test_runner_cannot_submit_replay_gpu_or_api_work() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    lowered = text.lower()
    assert "replay_submission_authorized\": false" in lowered
    assert "gpu_jobs_authorized\": 0" in lowered
    for forbidden in ("sbatch ", "srun ", "qsub ", "curl ", "litellm", "openai"):
        assert forbidden not in lowered
    monitor = (ROOT / "phase1" / "scripts" / "run_prospective_continuous_intake_monitor_20260821.sh").read_text(
        encoding="utf-8"
    )
    assert SCRIPT.name not in monitor


def test_file_open_audit_allows_only_the_intended_truth_input() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    audit = text[text.index("forbidden_open_count=") : text.index("filename_count=")]
    assert "label_vault" not in audit
    assert r"\.tar\.gz" in audit
    assert "/scores/" in audit
    assert "all_blind_views" in audit


def test_shell_syntax() -> None:
    if os.name != "posix":
        pytest.skip("POSIX shell syntax is verified on the Linux experiment host")
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("bash unavailable on this platform")
    completed = subprocess.run([bash, "-n", str(SCRIPT)], capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stderr
