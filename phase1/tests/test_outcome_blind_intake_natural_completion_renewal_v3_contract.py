from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "phase1/outcome_blind_intake_natural_completion_renewal_v3.json"
PREFLIGHT = ROOT / "phase1/OUTCOME_BLIND_INTAKE_NATURAL_RENEWAL_V3_PREFLIGHT_20260902.md"
RUNNER = (
    ROOT
    / "phase1/scripts/renew_outcome_blind_intake_after_natural_completion_20260902_v3.sh"
)
VERIFIER = ROOT / "phase1/scripts/verify_outcome_blind_intake_renewal_20260902_v3.sh"
DIRECTION = ROOT / "phase1/CURRENT_DIRECTION.md"


def load_contract() -> dict:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def test_contract_binds_the_exact_natural_completion_baseline() -> None:
    contract = load_contract()
    frozen = contract["frozen_preconditions"]
    assert contract["protocol"] == "outcome-blind-intake-natural-completion-renewal-v3"
    assert frozen["control_commit"] == "b20dd2682d609c0236c138c08797678cf31a2fc0"
    assert frozen["monitor_script_sha256"] == (
        "ef6584493de0f5e14a08bde4cc9501f268e43fb04bfd889af438666b1948eead"
    )
    assert frozen["latest_sha256"] == (
        "bf7674a4a3aec4cde8eec3e3fec31f1410e0445e0096f8e9fada3fae8b0ce0d6"
    )
    assert frozen["summary_sha256"] == (
        "5c00320bae7b97c3c69212a545c5f7658ede9f37e5c8d7f8b41e3cb4be050b6f"
    )
    assert frozen["eligible_source_archive_count"] == 296
    assert frozen["provisional_first960_runs"] == 559
    assert frozen["old_pid"] == 4181149
    assert frozen["monitor_log_sha256"] == (
        "24127e6a3882699ad29aa6395c27d0b2a516387b1e223aa407a4ad19d9ff47d5"
    )
    assert frozen["monitor_log_bytes"] == 516823
    assert frozen["monitor_log_lines"] == 7740
    assert frozen["normal_completion_sentinels"] == 14


def test_contract_has_fixed_cpu_only_resources_and_no_scientific_change() -> None:
    contract = load_contract()
    resources = contract["resources"]
    assert resources == {
        "fixed_polls": 145,
        "poll_interval_seconds": 300,
        "maximum_nominal_runtime_seconds": 43500,
        "cpu_only": True,
        "gpu": 0,
        "paid_api": 0,
        "model_fit": 0,
        "base_model_update": 0,
    }
    forbidden = "\n".join(contract["forbidden_changes"])
    for phrase in (
        "labels, outcomes, predictions, accuracy, utility",
        "candidate profile, or private selection",
        "GPU work, paid API calls, model fitting, or a base-model update",
        "overwriting prior logs",
    ):
        assert phrase in forbidden


def test_preflight_has_all_eleven_ordered_items_and_eta() -> None:
    text = PREFLIGHT.read_text(encoding="utf-8")
    offsets = [text.index(f"{number}. **") for number in range(1, 12)]
    assert offsets == sorted(offsets)
    assert "43,500 seconds" in text
    assert "145 fixed polls at 300 seconds" in text
    assert "first-poll deployment gate" in text
    assert "GPU/paid API/model-fit/base-update=`0/0/0/0`" in text


def test_runner_rechecks_every_frozen_boundary_before_initialize() -> None:
    text = RUNNER.read_text(encoding="utf-8")
    preflight, launch = text.split("if [[ \"${mode}\" == check ]]", maxsplit=1)
    for fragment in (
        'git -C "${control}" rev-parse HEAD',
        'git -C "${control}" status --porcelain --untracked-files=all',
        'sha256sum "${monitor}"',
        '"${state}/LATEST"',
        '"${state}/snapshots/${latest}/accumulator/summary.json"',
        'find "${source_root}"',
        'test ! -e "${state}/BASELINE_INVALID"',
        '! kill -0 "${old_pid}"',
        "lock_is_free",
        'sha256sum "${log}"',
        'stat -c %s "${log}"',
        'wc -l <"${log}"',
        "PROSPECTIVE_CONTINUOUS_INTAKE_MONITOR_COMPLETE",
        'test ! -e "${result_root}"',
    ):
        assert fragment in preflight
    assert launch.count('bash "${monitor}" --initialize "${control}" "${commit}"') == 1
    assert text.count("PREFLIGHT_01_DIRECTION=") == 1
    assert text.count("PREFLIGHT_11_STOP=") == 1


def test_runner_is_append_only_and_fails_closed_on_first_poll_drift() -> None:
    text = RUNNER.read_text(encoding="utf-8")
    assert 'mkdir -m 0700 "${result_root}"' in text
    assert 'test ! -e "${result_root}"' in text
    assert 'tail -n "+$((before_lines + 1))" "${log}"' in text
    assert "poll_end=0 rc=0" in text
    assert 'head -c "${before_bytes}" "${log}"' in text
    assert 'test "$(tr -d \'\\r\\n\' <"${state}/LATEST")" = "${latest}"' in text
    assert 'kill "${new_pid}"' in text
    assert 'printf \'%s\\n\' "${rc}" >"${result_root}/FAILED_RC"' in text
    assert ">\"${log}\"" not in text
    assert 'gpu_paid_api_model_fit_base_update=0/0/0/0' in text
    assert 'outcomes_read=false' in text
    assert 'candidate_profile_or_private_identity_read=false' in text


def test_independent_verifier_does_not_source_or_import_runner() -> None:
    runner = RUNNER.read_text(encoding="utf-8")
    verifier = VERIFIER.read_text(encoding="utf-8")
    assert RUNNER.name not in verifier
    assert "source " not in verifier
    assert "python" not in verifier.lower()
    assert runner != verifier
    for fragment in (
        "sha256sum -c SHA256SUMS",
        'git -C "${control}" rev-parse HEAD',
        'sha256sum "${monitor}"',
        'kill -0 "${new_pid}"',
        'head -c "${before_bytes}" "${log}"',
        "poll_end=0 rc=0",
        '"${state}/LATEST"',
        'find "${source_root}"',
        "first960_runs=559",
        "outcomes_read=false",
        "candidate_profile_or_private_identity_read=false",
        "gpu_paid_api_model_fit_base_update=0/0/0/0",
    ):
        assert fragment in verifier


def test_direction_records_frozen_not_yet_executed_status() -> None:
    text = DIRECTION.read_text(encoding="utf-8")
    section = text.split("## 0L0r.", maxsplit=1)[1].split("\n## ", maxsplit=1)[0]
    assert "FROZEN_NOT_EXECUTED" in section
    assert "145" in section
    assert "43,500" in section
    assert "82e10e290016dd1205a899df1937d81dc80a7236" in section
    assert "prospective value/identity read=`false/false`" in section
