import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "phase1" / "incremental_archive_rejection_support_audit_v1.json"


def load_protocol():
    return json.loads(PROTOCOL.read_text(encoding="utf-8"))


def test_freeze_precedes_support_readout():
    protocol = load_protocol()
    assert protocol["protocol"] == "incremental_archive_rejection_support_audit_v1"
    assert protocol["frozen_before_target_competition_or_support_readout"] is True
    assert all(value is False for value in protocol["unknown_at_freeze"].values())
    assert protocol["target_selection"]["required_count"] == 1
    assert protocol["target_selection"]["caller_may_choose_archive_or_competition"] is False
    assert protocol["target_selection"]["registry_file_hash_only"] is True


def test_increment_is_exact_and_aliases_are_excluded():
    protocol = load_protocol()
    prior = protocol["known_before_readout"]["prior"]
    current = protocol["known_before_readout"]["current"]
    delta = protocol["known_before_readout"]["increment"]
    assert current["observed_archives"] - prior["observed_archives"] == delta["observed_archives"] == 8
    assert current["accepted_archives"] - prior["accepted_archives"] == delta["accepted_archives"] == 7
    assert current["structural_rejected_archives"] - prior["structural_rejected_archives"] == 1
    assert delta["structural_rejected_archives"] == 1
    assert current["alias_quarantined_archives"] - prior["alias_quarantined_archives"] == 0
    assert delta["alias_quarantined_archives"] == 0


def test_strong_gate_requires_temporally_prior_eligible_support():
    protocol = load_protocol()
    strong = protocol["decision_rule"]["strong"]
    partial = protocol["decision_rule"]["partial"]
    assert strong["minimum_prior_accepted_archives"] == 1
    assert strong["minimum_prior_eligible_runs"] == 1
    assert strong["minimum_prior_eligible_endpoints"] == 1
    assert strong["status"] == "INCREMENTAL_ARCHIVE_SUPPORT_PREEXISTING_STRONG"
    assert partial["prior_eligible_support_required"] is False
    assert partial["status"] == "INCREMENTAL_ARCHIVE_SUPPORT_CONTEMPORANEOUS_ONLY"


def test_access_and_claim_boundaries_are_zero_resource():
    protocol = load_protocol()
    access = protocol["access_contract"]
    assert access["target_registry_contents_opened"] is False
    assert access["archive_payloads_opened"] is False
    assert access["labels_grades_outcomes_predictions_accuracy_or_utility_read"] is False
    assert access["candidate_identities_or_profiles_read"] is False
    assert access["archive_task_run_or_candidate_identity_values_emitted"] is False
    assert access["gpu_paid_api_model_fit_base_update"] == "0/0/0/0"
    assert protocol["reporting"]["do_not_call_one_event_population_level_replication"] is True
    assert all(
        protocol["resource_matrix"][key] == 0
        for key in ("gpu_jobs", "paid_api_calls", "model_fits", "base_llm_updates")
    )
