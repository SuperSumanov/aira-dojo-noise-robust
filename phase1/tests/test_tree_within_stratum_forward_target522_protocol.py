from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_PATH = (
    ROOT / "phase1" / "tree_linearization_within_stratum_forward_target522_v2.json"
)
LATCH_PATH = (
    ROOT / "phase1" / "scripts" / "latch_tree_within_stratum_forward_target522_20260828.sh"
)


def protocol() -> dict:
    value = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def first_crossing(observations: list[tuple[str, int]], target: int) -> str | None:
    return next((snapshot for snapshot, runs in observations if runs >= target), None)


def test_target_is_fixed_twenty_percent_forward_accrual() -> None:
    value = protocol()
    freeze = value["freeze_state"]
    activation = value["activation_rule"]
    assert value["status"] == (
        "OUTCOME_BLIND_PROTOCOL_AMENDED_BEFORE_TARGET522_SELECTION_OR_INCREMENT_PROFILE"
    )
    amendment = value["pre_candidate_integrity_amendment"]
    assert amendment["candidate_snapshot_identity_seen"] is False
    assert amendment["increment_profile_seen"] is False
    assert amendment["scientific_population_estimand_thresholds_or_classification_changed"] is False
    assert amendment["superseded_source_commit"] == (
        "3553744e98b75f2ee2414056cb56b1a523c0b303"
    )
    assert amendment["superseded_monitor_candidate_seen"] is False
    assert amendment["superseded_monitor_exit_receipt_missing"] is True
    assert amendment["superseded_monitor_sha256sums_sha256"] == (
        "423a595f098040f0a2169231d0a20d7c01e23e377a88b328d4579fa94ed70131"
    )
    assert freeze["baseline_counts"]["provisional_first960_runs"] == 435
    assert activation["target_total_physical_runs"] == 522
    assert activation["minimum_disjoint_increment_physical_runs"] == 87
    assert Fraction(6, 5) * 435 == 522
    assert 522 - 435 == 87
    assert freeze["candidate_snapshot_identity_counts_and_profile_seen"] is False


def test_baseline_failure_and_seen_values_are_fully_disclosed() -> None:
    freeze = protocol()["freeze_state"]
    assert freeze["baseline_formal_classification"] == (
        "WITHIN_STRATUM_DECOMPOSITION_GATE_FAIL"
    )
    assert "45605749/284435765" in freeze["baseline_failure_reason"]
    seen = freeze["baseline_scientific_values_seen_before_this_freeze"]
    assert set(seen) == {
        "task_canonical_standardized_within_tv",
        "physical_run_canonical_standardized_within_tv",
        "task_conditionable_fraction_at_or_above_reference",
        "physical_run_conditionable_fraction_at_or_above_reference",
        "task_maximum_canonical_contribution_share",
        "physical_run_maximum_canonical_contribution_share",
    }
    assert all(Fraction(text) >= 0 for text in seen.values())


def test_primary_population_is_disjoint_and_cannot_be_rescued() -> None:
    value = protocol()
    population = value["primary_population"]
    assert population["baseline_rows_in_primary_estimand"] is False
    assert population["cumulative_candidate_profile_may_rescue"] is False
    assert population["partial_physical_runs_allowed"] is False
    assert population["baseline_and_candidate_run_rows_must_be_append_only"] is True
    assert (
        population["baseline_and_candidate_endpoint_rows_must_be_byte_semantically_identical_for_old_ids"]
        is True
    )
    assert value["tree_estimand"]["secondary_may_rescue_primary"] is False


def test_all_scientific_thresholds_are_exact_ratios() -> None:
    value = protocol()
    gates = value["strong_positive_gates"]
    ratio_fields = {key: entry for key, entry in gates.items() if key != "both_axes_must_pass_for_headline"}
    assert gates["both_axes_must_pass_for_headline"] is True
    assert {key: Fraction(entry) for key, entry in ratio_fields.items()} == {
        "minimum_task_canonical_standardized_within_tv": Fraction(1, 5),
        "minimum_physical_run_canonical_standardized_within_tv": Fraction(3, 20),
        "minimum_task_fraction_at_or_above_conditional_tv_reference": Fraction(1, 2),
        "minimum_physical_run_fraction_at_or_above_conditional_tv_reference": Fraction(1, 4),
        "maximum_single_task_canonical_contribution_share": Fraction(2, 5),
        "maximum_single_physical_run_canonical_contribution_share": Fraction(1, 5),
    }
    hard = value["hard_integrity_and_support_gates"]
    assert hard["all_exact_gate_comparisons_use_fraction_numerators_and_denominators"] is True
    assert hard["decimal_strings_are_descriptive_only"] is True


def test_first_crossing_rule_keeps_boundary_overshoot() -> None:
    observations = [("baseline", 435), ("below", 519), ("first", 527), ("later", 540)]
    assert first_crossing(observations, 522) == "first"
    assert first_crossing(observations[:2], 522) is None
    activation = protocol()["activation_rule"]
    assert activation["boundary_overshoot_included"] is True
    assert activation["manual_snapshot_choice_allowed"] is False
    assert activation["skip_an_observed_eligible_crossing_allowed"] is False
    assert activation["profile_values_used_for_selection"] is False


def test_classification_order_and_claim_boundary_do_not_overstate_independence() -> None:
    value = protocol()
    assert value["ordered_classification"] == [
        "FORWARD_INCREMENT_BROAD_NONCOMPOSITIONAL_LINEARIZATION_DISTORTION",
        "FORWARD_INCREMENT_TASK_ONLY_BROAD_NONCOMPOSITIONAL_LINEARIZATION_DISTORTION",
        "FORWARD_INCREMENT_RUN_ONLY_BROAD_NONCOMPOSITIONAL_LINEARIZATION_DISTORTION",
        "FORWARD_INCREMENT_PROFILE_BELOW_STRONG_GATE",
        "FORWARD_INCREMENT_NO_OBSERVED_WITHIN_STRATUM_DISTORTION",
        "FORWARD_INCREMENT_WITHIN_STRATUM_GATE_FAIL",
    ]
    boundary = value["claim_boundary"]
    assert boundary["independent_runs_not_independent_tasks"] is True
    assert boundary["cumulative_cohort_independent_replication"] is False
    assert boundary["predictor_accuracy_effect_or_search_utility_computed"] is False


def test_latch_is_selection_only_stable_and_fail_closed_on_resume_gap() -> None:
    source = LATCH_PATH.read_text(encoding="utf-8")
    assert "readonly target_runs=522" in source
    assert "readonly minimum_increment_runs=87" in source
    assert "readonly stable_polls_required=6" in source
    assert "sleep 5" in source
    assert "profile_values_read_for_selection=false" in source
    assert "manual_snapshot_choice=false" in source
    assert "earlier_observed_target_crossing_skipped=false" in source
    assert "status=CONTINUITY_GAP_FAIL_CLOSED" in source
    assert 'if test "$latest" != "$last_observed"' in source
    assert 'candidate_record=$(cat "$root/candidate.tsv")' in source
    assert 'if (!found && $2 >= target && $1 != candidate) exit 1' in source
    assert 'END {if (found != 1) exit 1}' in source
    assert 'NR > 1 && $2 >= target {exit 1}' in source
    assert "phase1.decompose_tree_linearization" not in source
    assert "phase1.verify_tree_linearization" not in source
    assert "nvidia-smi" not in source
    assert "sbatch" not in source
    assert "trap 'exit 143' TERM" in source
    assert "trap 'exit 130' INT" in source
    assert "trap 'exit 129' HUP" in source


def test_latch_installs_failure_receipt_before_initializing_state() -> None:
    source = LATCH_PATH.read_text(encoding="utf-8")
    trap = source.index("trap 'rc=$?")
    initialize = source.index('git -C "$repo" show "${source_commit}:${protocol_path}"')
    assert trap < initialize
    assert '.inventory.provisional_first960_runs == (.inventory.provisional_first960_runs | floor)' in source
    assert '.inventory.provisional_first960_endpoints == (.inventory.provisional_first960_endpoints | floor)' in source


def test_security_contract_is_zero_resource_and_identity_free() -> None:
    security = protocol()["security"]
    assert security["gpu_api_model_fit_base_update"] == [0, 0, 0, 0]
    assert security["prospective_label_grade_outcome_prediction_values_read"] is False
    assert security["raw_senior_archives_opened"] is False
    assert security["task_run_card_parent_code_or_per_edge_values_emitted"] is False
    assert set(security["corpus_input_basenames"]) == {
        "LATEST",
        "eligible_blind_manifest.jsonl",
        "intake_registry.jsonl",
        "provisional_runs.jsonl",
        "summary.json",
    }
    assert {
        "READY",
        "SHA256SUMS",
        "candidate.tsv",
        "observed.tsv",
        "protocol.json",
        "source_script.sh",
    } <= set(security["selection_support_input_basenames"])
