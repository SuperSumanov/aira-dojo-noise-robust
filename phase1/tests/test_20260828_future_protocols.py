from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).parents[2]
PHASE1 = ROOT / "phase1"
SNAPSHOT_887 = (
    "887491a021d75d889c00a5af672a11b8b06e249d98e84fd91288534080f62697"
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_historical_identifier_erased_887_protocol_and_runner_are_bound() -> None:
    protocol_path = (
        PHASE1 / "historical_train_future_identifier_erased_887_protocol_v1.json"
    )
    protocol = _json(protocol_path)
    assert _sha(protocol_path) == (
        "aa3b232c732c53bb24bf2fbac6932276d458f2e6a6ae20321edee0ff2d04ca1b"
    )
    assert protocol["status"] == "RESULT_BLIND_PROTOCOL_FROZEN"
    assert protocol["fixed_future_population"] == {
        "snapshot_sha256": SNAPSHOT_887,
        "intake_registry_sha256": (
            "37e41460c85661fd9afc6f8789a065088a9da88dde027b955ff4bc366d5bbcd8"
        ),
        "provisional_first960_runs_sha256": (
            "510d81820d7825fc6baa6db562b2371e50eb7d71d04cb1cc0bd17d095d6cdbca"
        ),
        "accumulator_summary_sha256": (
            "2f28b5b53cca5d6ea5ebf16f746a70f9c1de0e3197487a6ed78d41b4cb611302"
        ),
        "runs": 435,
        "endpoints": 11906,
        "structural_pairs": 3053,
        "tasks": 34,
        "closure": False,
    }
    assert [row["status"] for row in protocol["ordered_classification"]] == [
        "ZERO_IDENTIFIER_ERASED_LINKS",
        "LOW_IDENTIFIER_ERASED_OVERLAP_ONLY",
        "INTEGRITY_GATE_FAIL",
    ]
    assert protocol["prior_result_disclosure"]["new_435_run_result_was_read_before_freeze"] is False
    assert protocol["thresholds"]["strict_sensitivity_can_rescue_primary"] is False
    assert list(protocol["resources"].values()) == [0, 0, 0, 0]

    runner = (
        PHASE1
        / "scripts"
        / "run_historical_train_future_identifier_erased_887_20260828.sh"
    ).read_text(encoding="utf-8")
    assert f"readonly snapshot_sha={SNAPSHOT_887}" in runner
    assert (
        "readonly protocol_sha="
        "aa3b232c732c53bb24bf2fbac6932276d458f2e6a6ae20321edee0ff2d04ca1b"
    ) in runner
    assert "ZERO_IDENTIFIER_ERASED_LINKS" in runner
    assert "LOW_IDENTIFIER_ERASED_OVERLAP_ONLY" in runner
    assert "INTEGRITY_GATE_FAIL" in runner
    assert "gpu_api_model_fit_base_update=0/0/0/0" in runner


def test_task_balance_v3_is_future_only_and_cannot_rescue_887() -> None:
    protocol = _json(PHASE1 / "task_balance_forward_v3_future_protocol_v1.json")
    assert protocol["status"] == (
        "IMPLEMENTATION_FROZEN_FIRST_UNSEEN_SUCCESSOR_PENDING"
    )
    assert protocol["freeze_state"]["latest_snapshot_when_protocol_was_written"] == SNAPSHOT_887
    assert protocol["activation_rule"]["forbidden_current_snapshots"] == [
        SNAPSHOT_887
    ]
    assert protocol["activation_rule"]["manual_snapshot_choice_allowed"] is False
    assert protocol["activation_rule"]["skip_an_earlier_eligible_successor_allowed"] is False
    contract = protocol["v3_task_universe_contract"]
    assert contract["baseline_pair_task_set_must_be_subset_of_current"] is True
    assert contract["new_tasks_receive_explicit_baseline_pair_and_run_count_zero"] is True
    assert contract["removed_tasks_allowed"] is False
    assert contract["negative_pair_or_run_accrual_allowed"] is False
    assert contract["dominant_task_change_allowed"] is False
    assert contract["same_887_snapshot_v2_kill_can_be_rescued"] is False
    assert [row["status"] for row in protocol["primary_interpretation"]] == [
        "CAP_PASS",
        "CAP_FAIL",
    ]
    assert protocol["secondary_cannot_rescue_primary"] is True
    assert list(protocol["resources"].values()) == [0, 0, 0, 0]


def test_task_balance_v3_runner_consumes_only_the_automatic_latch() -> None:
    latch_path = (
        PHASE1
        / "scripts"
        / "latch_task_balance_v3_first_successor_after_887_20260828.sh"
    )
    assert _sha(latch_path) == (
        "4afef04396684844e3755e7769b420c5a42e7ded8f50395122f974e454381598"
    )
    latch = latch_path.read_text(encoding="utf-8")
    assert "latch-ab55510-after-887-v3" in latch
    assert "manual_snapshot_choice=false" in latch
    assert "earlier_successor_skipped=false" in latch
    assert "balance_values_or_classification_read=false" in latch
    assert "sleep 10" in latch

    continuation = (
        PHASE1
        / "scripts"
        / "resume_task_balance_v3_first_successor_after_887_20260828.sh"
    ).read_text(encoding="utf-8")
    assert "latch-continuation-after-887-v4" in continuation
    assert "PREVIOUS_TIMEOUT_CONTIGUOUS_WITH_CURRENT_BASELINE" in continuation
    assert "newest_snapshot_dir" in continuation
    assert "continuity_snapshot_tokens" not in continuation
    assert '"${root}/${name}_continuity_snapshot_ids.txt"' in continuation
    assert "previous_latch_timeout_continuity=true" in continuation
    assert "manual_snapshot_choice=false" in continuation
    assert "earlier_successor_skipped=false" in continuation
    assert "balance_values_or_classification_read=false" in continuation
    assert "trap 'exit 143' TERM" in continuation
    assert "sleep 10" in continuation

    runner = (
        PHASE1
        / "scripts"
        / "run_task_balance_forward_v3_first_successor_20260828.sh"
    ).read_text(encoding="utf-8")
    assert "latch-continuation-after-887-v4" in runner
    assert "latch-continuation-after-887-v5" in runner
    assert "latch-continuation-after-887-v5-r2" in runner
    assert "heartbeat_race_repair" in runner
    assert "failed_v5_fileset_sha" in runner
    assert "no unique completed authoritative latch generation" in runner
    assert "continuation_source_from_git.sh" in runner
    assert "previous_latch_timeout_continuity" in runner
    assert f"readonly forbidden_snapshot={SNAPSHOT_887}" in runner
    assert "candidate_snapshot_sha256" in runner
    assert "manual_snapshot_choice" in runner
    assert "earlier_successor_skipped" in runner
    assert "task_balance_guard_forward_validation_v3" in runner
    assert "verify_task_balance_guard_forward_validation_v3" in runner
    assert runner.count("producer_a.json") >= 4
    assert runner.count("producer_b.json") >= 2
    assert runner.count("verification_a.json") >= 4
    assert runner.count("verification_b.json") >= 2
    assert "pair_predictions\\.jsonl" in runner
    assert "gpu_api_model_fit_base_update=0/0/0/0" in runner


def test_task_balance_second_timeout_handoff_preserves_selection() -> None:
    handoff = (
        PHASE1
        / "scripts"
        / "resume_task_balance_v3_first_successor_after_v4_20260828.sh"
    ).read_text(encoding="utf-8")
    assert "latch-continuation-after-887-v4" in handoff
    assert "latch-continuation-after-887-v5" in handoff
    assert "latch-continuation-after-887-v5-r2" in handoff
    assert "PRE_CANDIDATE_POST_TIMEOUT_HEARTBEAT_RACE_BOUND" in handoff
    assert "failed_attempt_fileset_sha" in handoff
    assert "PRE_CANDIDATE_CONTIGUOUS_HANDOFF_AFTER_HEARTBEAT_RACE_REPAIR" in handoff
    assert 'if test ! -s "${root}/${name}_handoff_snapshot_ids.txt"; then' in handoff
    assert 'test -s "${root}/${name}_handoff_snapshot_ids.txt"' not in handoff
    assert '"${root}/${name}_handoff_snapshot_ids.unsorted" || true' in handoff
    assert 'test "${observed}" = "${baseline}" || test "${observed}" = "${current_latest}"' in handoff
    assert "heartbeat_race_state_fallbacks.tsv" in handoff
    assert 'test -f "${previous}/TIMEOUT_RC"' in handoff
    assert 'test ! -e "${previous}/FAILED_RC"' in handoff
    assert 'test ! -e "${previous}/READY"' in handoff
    assert 'test ! -e "${previous}/COMPLETE"' in handoff
    assert 'cmp "$0" "${root}/source_script.sh"' in handoff
    assert 'cmp "${previous}/source_script.sh"' in handoff
    assert "CANDIDATE_PRESERVED_FROM_PREVIOUS_TIMEOUT" in handoff
    assert "PRE_CANDIDATE_CONTIGUOUS_HANDOFF" in handoff
    assert "RECOVERED_SINGLE_SUCCESSOR_ACROSS_TIMEOUT_GAP" in handoff
    assert "assert_only_successor_since" in handoff
    assert '-newermt "${previous_final_stamp}"' in handoff
    assert 'test "$(tr -d \'\\r\\n\' < "${state_root}/LATEST")" = "${current_latest}"' in handoff
    assert 'test "${nonbaseline_count}" -le 1' in handoff
    assert 'test "${observed}" = "${baseline}" || test "${observed}" = "${candidate}"' in handoff
    assert "support_skipped_candidate" in handoff
    assert "timeout_handoff_generation=2" in handoff
    assert "manual_snapshot_choice=false" in handoff
    assert "earlier_successor_skipped=false" in handoff
    assert "balance_values_or_classification_read=false" in handoff
    assert "trap 'exit 143' TERM" in handoff
    assert "sleep 10" in handoff

    supervisor = (
        PHASE1
        / "scripts"
        / "supervise_task_balance_v3_v4_to_v5_20260828.sh"
    ).read_text(encoding="utf-8")
    assert "supervisor-v4-to-v5-v1" in supervisor
    assert 'test -f "${previous}/COMPLETE"' in supervisor
    assert 'test -f "${previous}/TIMEOUT_RC"' in supervisor
    assert 'test ! -e "${next}"' in supervisor
    assert "TASK_BALANCE_HANDOFF_CONTROL_COMMIT" in supervisor
    assert 'kill -0 "${launched_pid}"' in supervisor
    assert '! flock -n "${next}/monitor.lock" true' in supervisor
    assert "finish_success" in supervisor
    assert "SHA256SUMS" in supervisor
    assert "balance_values_or_classification_read=false" in supervisor
    assert "gpu_api_model_fit_base_update=0/0/0/0" in supervisor


def test_task_balance_887_failure_package_is_byte_bound() -> None:
    result = PHASE1 / "results" / "task_balance_structural_extension_887_20260828_1e5f949"
    bindings = _json(result / "source_bindings.json")
    assert _sha(result / "verification.json") == bindings["verification_json_sha256"]
    assert _sha(result / "access_attestation.txt") == bindings["access_attestation_sha256"]
    verification = _json(result / "verification.json")
    assert verification["status"] == "TASK_UNIVERSE_CHANGE_KILL_INDEPENDENTLY_VERIFIED"
    assert verification["claim"] == {
        "cap_or_directional_balance_adjudicated": False,
        "post_hoc_task_padding_used": False,
        "rerun_on_same_snapshot_authorized": False,
    }
    assert verification["task_universe"]["baseline_tasks"] == 30
    assert verification["task_universe"]["current_tasks"] == 34
    assert verification["task_universe"]["added_tasks"] == 4
    assert verification["task_universe"]["removed_tasks"] == 0


def test_split_integrity_certificate_is_result_blind_and_zero_link_ordered() -> None:
    protocol_path = PHASE1 / "split_integrity_certificate_887_protocol_v1.json"
    protocol = _json(protocol_path)
    assert _sha(protocol_path) == (
        "779ac3f1f5aef522a305b22b578dace2c0a8462fe748a7cd1b30dd20037ef5da"
    )
    assert protocol["status"] == (
        "RESULT_BLIND_CERTIFICATE_PROTOCOL_FROZEN_INPUTS_PENDING"
    )
    assert protocol["fixed_representation"] == "python_token_identifier_erased_v1"
    assert protocol["fixed_population"]["future_snapshot_sha256"] == SNAPSHOT_887
    assert protocol["fixed_population"]["future_runs"] == 435
    assert protocol["fixed_population"]["future_endpoints"] == 11906
    assert protocol["fixed_population"]["future_closure"] is False
    assert [row["status"] for row in protocol["ordered_classification"]] == [
        "PROVISIONAL_ZERO_LINK_SPLIT_INTEGRITY_CERTIFICATE",
        "PROVISIONAL_LOW_OVERLAP_CERTIFICATE_WITH_EXCEPTIONS",
        "NO_SPLIT_INTEGRITY_CERTIFICATE",
    ]
    inputs = protocol["required_inputs"]
    assert inputs["within_future"]["pre_result_postflight_logic_sha256"] == (
        "1b4ee9dd0841d537ba0ec6769d10e1898cd9148e852b243ea310cc2d888720ee"
    )
    assert inputs["historical_to_future"][
        "pre_result_postflight_logic_sha256"
    ] == "0ce8df4d2ecee8f102a2780e743bc17335fb8778be06772526ca12ccac1496dc"
    assert protocol["verification"]["raw_corpus_or_archive_recomputation_allowed"] is False
    assert protocol["claim_boundary"]["semantic_clone_absence_proven"] is False
    assert protocol["claim_boundary"]["pretraining_contamination_absence_proven"] is False
    assert protocol["claim_boundary"][
        "predictor_effect_accuracy_or_search_utility_computed"
    ] is False
    assert list(protocol["resources"].values()) == [0, 0, 0, 0]
