import hashlib
import json
from pathlib import Path


EXPECTED_SHA256 = "54187f386ee18f009b57ccd04f851083160db3e607a4e8a760e070b276ac377d"


def test_future_identifiability_protocol_is_outcome_blind_and_fail_closed():
    path = Path(__file__).parents[1] / "score_channel_future_identifiability_protocol_v1.json"
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == EXPECTED_SHA256
    value = json.loads(raw)
    assert value["status"] == "FROZEN_OUTCOME_UNREAD_WAITING_COHORT"
    temporal = value["temporal_attestation"]
    assert temporal["ready_archives"] == 0
    assert temporal["initial_0821_intake_directories"] == 0
    assert temporal["initial_0821_archive_payloads_opened"] is False
    assert temporal["initial_0821_labels_or_outcomes_read"] is False

    archives = value["initial_archives"]
    assert len(archives) == 12
    assert len({row["relative_path"] for row in archives}) == 12
    assert archives == sorted(
        archives, key=lambda row: (row["mtime_ns"], row["relative_path"].encode())
    )
    closure = value["cohort_closure"]
    assert min(row["mtime_ns"] for row in archives) > closure["start_after_archive_mtime_ns"]
    assert closure["accepted_unique_physical_run_target"] == 300
    assert closure["include_complete_boundary_archive"] is True
    assert closure["partial_archive_salvage_allowed"] is False
    assert closure["label_or_score_may_affect_closure"] is False
    assert closure["append_only_survival_required"] is True

    selection = value["parent_selection"]
    assert selection["score_magnitude_used_for_eligibility_or_lottery"] is False
    assert selection["max_parents_per_physical_run"] == 2
    assert selection["seed"] == 20260813
    assert selection["old_assignments_may_reshuffle"] is False
    assert value["truth_support"]["fixed_gap_edges"] == [
        0.0,
        0.0001,
        0.0003,
        0.001,
        0.003,
        0.01,
        0.03,
        0.1,
        0.3,
        "infinity",
    ]
    gates = value["eligibility_gates_for_requesting_replay_design"]
    assert gates["nontied_selected_parents_minimum"] == 80
    assert gates["tasks_with_nontied_parent_minimum"] == 8
    assert gates["dominant_nontied_task_share_maximum"] == 0.25
    assert gates["selected_physical_runs_minimum"] == 60
    assert gates["all_must_pass"] is True
    assert value["scope"]["gpu_jobs_authorized"] == 0
    assert value["future_replay_constraints"][
        "user_approval_of_exact_matrix_and_gpu_hours_required"
    ] is True
