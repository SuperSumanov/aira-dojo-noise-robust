"""Frozen declarations for the clean-provenance Decision-Corpus evidence index v7.

V7 deliberately rebuilds from the last unaffected v5 index.  It does not read
or inherit v6, the withdrawn prediction-value coverage matrices, or the v1
task-balance guard.  Replacement entries bind receipt-only and structural-only
evidence plus the immutable withdrawal registry.
"""

PROTOCOL = "decision_corpus_evidence_index_v7"
STATUS = "PROVISIONAL_CLEAN_PROVENANCE_EVIDENCE_STACK_AWAITING_FIRST960"
SOURCE_PROTOCOL = "decision_corpus_evidence_index_v5"
SOURCE_STATUS = "PROVISIONAL_SOURCE_ANSWERABILITY_EVIDENCE_STACK_AWAITING_FIRST960"
SOURCE_INDEX_RELATIVE = (
    "phase1/results/decision_corpus_evidence_index_v5_20260821/index.json"
)
SOURCE_INDEX_SHA256_NORMALIZED_LF = (
    "4bff2b9fa48f2b530de886ab6b799011e8c4aa48ed378cdee0959c8b087a1627"
)

SOURCE_ENTRY_NAMES = [
    "decision_corpus",
    "source_opportunity",
    "decision_observability",
    "status_certified_partial_order",
    "source_decision_answerability",
    "label_repeatability",
    "normalized_clone",
    "deployment_cost",
    "prospective_gate",
]

FORBIDDEN_EVIDENCE_PATH_FRAGMENTS = [
    "decision_corpus_evidence_index_v6_20260825",
    "prediction_escrow_coverage_7cda_20260825_6299865",
    "prediction_escrow_coverage_f109_20260825_2c5626d",
    "task_balance_accrual_guard_7cda_20260825",
    "task_balance_guard_forward_8579_20260826",
    "agentic_benchmark_checklist_crosswalk_v1_20260825",
]

WITHDRAWAL_REGISTRY = {
    "path": "phase1/prediction_matrix_downstream_taint_registry_v1.json",
    "sha256_normalized_lf": (
        "f15cba54aca4572cc6c515d8b0f30d614874997bc873fa5cee7698f0aeb3c13b"
    ),
}

SCOPE_ADDITIONS = {
    "clean_provenance_rebuilt_from_last_unaffected_index": True,
    "withdrawn_v6_inherited": False,
    "prediction_pair_files_opened_by_replacement_common_support": False,
    "prediction_values_read_or_aggregated_by_replacement_entries": False,
    "pair_identity_or_orientation_reopened_by_receipt_join": False,
    "receipt_certified_current_common_support_pairs": 2755,
    "structural_weighting_shift_quantified": True,
    "task_balance_source_is_structural_only_v2": True,
    "task_balance_cap_pass": False,
    "first960_closed": False,
    "prospective_accuracy_or_effect_computed": False,
}

REPORTING_CONTRACT_ADDITIONS = {
    "receipt_certified_common_support_language_allowed": True,
    "pair_orientation_tie_or_margin_language_allowed": False,
    "structural_weighting_shift_language_allowed": True,
    "single_drop_robust_magnitude_language_allowed": False,
    "task_balance_improved_but_uncleared_language_allowed": True,
    "task_balance_cap_or_producer_compliance_language_allowed": False,
    "opportunity_yield_effect_language_allowed": False,
    "prospective_predictor_effect_language_allowed": False,
}

PROVENANCE_REPAIR_ENTRY = {
    "name": "evidence_provenance_repair",
    "estimand": (
        "which machine evidence pointers retain strict zero-prediction-value "
        "provenance after the prediction-matrix incident"
    ),
    "supported_claim": (
        "The value-reading coverage matrices, their v6 catalog entry, the v1 "
        "task-balance chain, and affected ABC crosswalk pointers are preserved as "
        "historical-withdrawn. V7 is rebuilt from unaffected v5 and binds only "
        "replacement receipt-only or structural-only evidence."
    ),
    "does_not_prove": (
        "Withdrawal does not prove every historical number wrong, does not delete "
        "the audit trail, and cannot retroactively repair v1 provenance."
    ),
    "artifacts": [
        {
            "path": WITHDRAWAL_REGISTRY["path"],
            "sha256_normalized_lf": WITHDRAWAL_REGISTRY[
                "sha256_normalized_lf"
            ],
            "json_assertions": {
                "protocol": "prediction-matrix-downstream-taint-registry-v1",
                "root_incident.labels_or_outcomes_read": False,
                "root_incident.numeric_values_proven_wrong": False,
                "artifacts.1.status": (
                    "PARTIALLY_DEGRADED_MATRIX_DEPENDENT_ENTRY_WITHDRAWN"
                ),
                "artifacts.2.status": (
                    "HISTORICAL_WITHDRAWN_AS_STRICT_ZERO_PREDICTION_ACCESS_EVIDENCE"
                ),
                "artifacts.5.status": (
                    "PARTIALLY_DEGRADED_AFFECTED_EVIDENCE_POINTERS_WITHDRAWN"
                ),
                "replacement.formal_status": (
                    "INDEPENDENT_STRUCTURAL_ONLY_TASK_BALANCE_FORWARD_PASS"
                ),
                "replacement.v1_provenance_retroactively_repaired": False,
            },
        }
    ],
}

RECEIPT_COMMON_SUPPORT_ENTRY = {
    "name": "prediction_receipt_common_support",
    "estimand": (
        "receipt-certified equality of the canonical structural-pair population "
        "reconstructed by frozen WL and transition independent verifiers"
    ),
    "supported_claim": (
        "At immutable snapshot 8579, the two frozen verifier chains independently "
        "certify the same 2,755-pair canonical population. The join opens no pair "
        "prediction file and accesses no prediction value."
    ),
    "does_not_prove": (
        "Receipt equality does not reopen pair identity or orientation and does not "
        "support tie, margin, activation, accuracy, effect, utility, runtime, or "
        "first-960 closure claims."
    ),
    "artifacts": [
        {
            "path": (
                "phase1/results/prediction_receipt_common_support_8579_20260826_"
                "9f2cbe9/receipt.json"
            ),
            "sha256_normalized_lf": (
                "3b2d0200cf8982a69837a65ca0511fcb35534c94ee440f6bf17789c09c721263"
            ),
            "json_assertions": {
                "protocol": "prediction-receipt-common-support-v1",
                "status": "RECEIPT_CERTIFIED_EXACT_CANONICAL_COMMON_SUPPORT",
                "snapshot_sha256": (
                    "8579d7cd32091a11089b935217f7189e321b1d623dbaa69233182ba2fedd9248"
                ),
                "families.wl.pairs": 2755,
                "families.transition.pairs": 2755,
                "input_policy.prediction_pair_files_opened": False,
                "input_policy.artifact_summary_content_parsed": False,
                "receipt_certified_common_support.pairs": 2755,
                "receipt_certified_common_support.same_canonical_pair_population_certified": True,
                "receipt_certified_common_support.pair_identity_or_orientation_reopened": False,
                "scope.prediction_values_accessed": False,
                "scope.prediction_value_aggregates_computed": [],
                "scope.labels_grades_outcomes_or_winner_orientation_read": False,
                "scope.accuracy_effect_or_search_utility_computed": False,
            },
        },
        {
            "path": (
                "phase1/results/prediction_receipt_common_support_8579_20260826_"
                "9f2cbe9/independent_verification.json"
            ),
            "sha256_normalized_lf": (
                "24a7ff758d391f4fd506236df97f1a9d6692ddb965cab490e6e92475e2cb012e"
            ),
            "json_assertions": {
                "protocol": "prediction-receipt-common-support-v1",
                "status": "INDEPENDENT_PREDICTION_RECEIPT_COMMON_SUPPORT_VERIFIED",
                "candidate_exact": True,
                "pairs": 2755,
                "prediction_pair_files_opened": False,
                "prediction_values_accessed": False,
                "same_canonical_pair_population_certified": True,
                "prospective_outcomes_read": False,
                "effect_metrics_computed": [],
                "producer_imported": False,
            },
        },
    ],
}

STRUCTURAL_WEIGHTING_ENTRY = {
    "name": "structural_weighting_shift",
    "estimand": (
        "how chronological physical-run task weights are transformed into derived "
        "sibling-pair benchmark weights by task-specific opportunity yield"
    ),
    "supported_claim": (
        "At the 339-run 7cda prefix, run-to-pair task-weight TV is "
        "0.337082500713674. Run HHI fell while pair HHI rose; the direction is "
        "temporally persistent and task-deletion robust, and opportunity yield "
        "explains most of the measured HHI/TV shift."
    ),
    "does_not_prove": (
        "The shift is not observed predictor bias or effect. One drop explains "
        "0.9641733656841007 of the pair-HHI change, so robust magnitude and causal "
        "producer-behavior claims are forbidden."
    ),
    "artifacts": [
        {
            "path": (
                "phase1/results/structural_dependency_atlas_7cda_20260825/"
                "headline_metrics.json"
            ),
            "sha256_normalized_lf": (
                "f6db60ae066323ff3e65944ab24d3c30e18074765f080d4f2618de4bfc86814f"
            ),
            "json_assertions": {
                "status": "OUTCOME_BLIND_STRUCTURAL_DEPENDENCY_ATLAS_READY",
                "snapshot_sha256": (
                    "7cdaefcf2be7786442e1af1f4d0b4012edee708932f1fad31e174c0dcaf803a1"
                ),
                "current_runs": 339,
                "current_pairs": 2635,
                "current_tasks": 30,
                "run_to_pair_total_variation": 0.337082500713674,
                "current_pair_max_share": 0.31233396584440226,
                "chronological_flags.run_max_share_fell_while_pair_max_share_rose": True,
                "chronological_flags.pair_inverse_hhi_diversity_fell_despite_more_tasks": True,
            },
        },
        {
            "path": (
                "phase1/results/structural_dependency_atlas_7cda_20260825/"
                "independent_verification.json"
            ),
            "sha256_normalized_lf": (
                "634c57840667d4cd9a301fb3d8c8d39e37c161ea1d11872a57ac740d951c150f"
            ),
            "json_assertions": {
                "status": "INDEPENDENT_STRUCTURAL_DEPENDENCY_ATLAS_PASS",
                "checks.all_task_concentration_metrics_recomputed": True,
                "checks.all_weighting_shifts_recomputed": True,
                "checks.chronological_comparison_recomputed": True,
                "checks.input_hashes_bound": True,
                "security.label_grade_outcome_prediction_or_winner_orientation_read": False,
                "security.accuracy_effect_or_search_utility_computed": False,
                "security.gpu_or_api_calls": 0,
            },
        },
        {
            "path": (
                "phase1/results/structural_weight_trajectory_7cda_20260826/"
                "headline_metrics.json"
            ),
            "sha256_normalized_lf": (
                "8d4041994f8998e5a04df0e2e18508ebf97915221303c14f62d9abb8d0e6b2b2"
            ),
            "json_assertions": {
                "status": "OUTCOME_BLIND_STRUCTURAL_WEIGHT_TRAJECTORY_READY",
                "runs": 339,
                "structural_pairs": 2635,
                "tasks": 30,
                "run_hhi_delta": -0.007095167549882084,
                "pair_hhi_delta": 0.05270955007531816,
                "pair_hhi_yield_fraction": 0.6446576519060645,
                "run_to_pair_tv_yield_fraction": 0.5951060527094302,
                "maximum_single_drop_attribution": 0.9641733656841007,
                "claim_gates.G1_temporal_persistence": True,
                "claim_gates.G2_no_single_drop_artifact": False,
                "claim_gates.G3_single_task_robustness": True,
                "claim_gates.G4_yield_is_primary_mechanism": True,
            },
        },
        {
            "path": (
                "phase1/results/structural_weight_trajectory_7cda_20260826/"
                "independent_verification.json"
            ),
            "sha256_normalized_lf": (
                "8094e21acde877a67cdcc295c6decaaaf9e650c06fd55a91ed69026f877f9420"
            ),
            "json_assertions": {
                "status": "INDEPENDENT_STRUCTURAL_WEIGHT_TRAJECTORY_PASS",
                "checks.all_339_prefixes_recomputed": True,
                "checks.all_claim_gates_recomputed": True,
                "checks.drop_and_task_deletions_recomputed": True,
                "checks.security_contract_exact": True,
                "security.label_outcome_prediction_or_raw_archive_opened": False,
                "security.gpu_or_api_calls": 0,
                "recomputed_key_findings.claim_gates.G2_no_single_drop_artifact": False,
            },
        },
    ],
}

OPPORTUNITY_YIELD_AUDIT_ENTRY = {
    "name": "opportunity_yield_aggregation_audit",
    "estimand": (
        "a closure-time decomposition of run-to-informative-pair aggregation into "
        "structural opportunity yield and informative retention"
    ),
    "supported_claim": (
        "Before closure, the two-stage decomposition, full task-universe gate, "
        "common-support gate, range-times-TV bounds, and no-rescue reporting rule "
        "were frozen and independently checked."
    ),
    "does_not_prove": (
        "This is an interpretation contract, not a measured predictor effect; it "
        "cannot supersede a frozen primary, rescue a failed primary with alternate "
        "weighting, or claim informative-cluster-size theory as novel."
    ),
    "artifacts": [
        {
            "path": (
                "phase1/results/opportunity_yield_aggregation_audit_v1_20260826/"
                "formal_summary.json"
            ),
            "sha256_normalized_lf": (
                "ec0671e8fb4d17faa53603fc53c4a8a98069e27a86feeac203a89e932d61e053"
            ),
            "json_assertions": {
                "status": "FORMAL_OPPORTUNITY_YIELD_AGGREGATION_AUDIT_PASS",
                "source_commit": "f97026221e099c11fa1ca8f2c13a95c389bea743",
                "formal_execution.independent_checks_passed": 18,
                "formal_execution.verifier_a_b_byte_identical": True,
                "security.prospective_label_grade_outcome_or_orientation_read": False,
                "security.prediction_values_read_or_aggregated": False,
                "security.accuracy_effect_or_search_utility_computed": False,
                "security.gpu_jobs": 0,
                "security.api_calls": 0,
                "security.new_model_fits": 0,
                "claim_boundary.closure_time_audit_frozen": True,
                "claim_boundary.existing_primary_or_inference_superseded": False,
                "claim_boundary.alternate_weighting_can_rescue_primary": False,
                "claim_boundary.effect_result": False,
            },
        },
        {
            "path": (
                "phase1/results/opportunity_yield_aggregation_audit_v1_20260826/"
                "independent_verification.json"
            ),
            "sha256_normalized_lf": (
                "0054e5fceaf326b67f773d44109841ce576db59c9efd959671e97b6b3357e973"
            ),
            "json_assertions": {
                "status": "INDEPENDENT_OPPORTUNITY_YIELD_AUDIT_CONTRACT_PASS",
                "checks.access_attestation_exact": True,
                "checks.closure_and_common_support_gate_exact": True,
                "checks.panel_forbids_rescue": True,
                "checks.reporting_firewall_exact": True,
                "checks.weight_identity_exact": True,
                "access_and_compute.prediction_values_read_or_aggregated": False,
                "access_and_compute.prospective_label_grade_outcome_or_winner_orientation_read": False,
                "access_and_compute.accuracy_effect_or_search_utility_computed": False,
            },
        },
    ],
}

TASK_BALANCE_V2_ENTRY = {
    "name": "task_balance_structural_only_v2",
    "estimand": (
        "forward accounting of a frozen structural-pair task-balance debt using "
        "only snapshot-bound accumulator summaries, ledgers, structural gates, and "
        "receipt-only total-count certification"
    ),
    "supported_claim": (
        "From 2,635 to 2,755 pairs, frozen debt changed from 657 to 645 exactly "
        "because dominant/non-dominant increments were 27/93. The debt improved by "
        "12 but remains uncleared."
    ),
    "does_not_prove": (
        "The current 0.308529945553539 dominant share still fails the 25% cap and "
        "dominant pairs accrued before debt clearance, so producer compliance, "
        "causal acquisition effect, predictor effect, and v1 provenance repair are "
        "forbidden claims."
    ),
    "artifacts": [
        {
            "path": (
                "phase1/results/task_balance_structural_only_v2_8579_20260826_"
                "1b9b836/forward_validation.json"
            ),
            "sha256_normalized_lf": (
                "fca979bb912c61bb14385638069a64aefcb8a7b9bc41cb77c260d07075ea0fb1"
            ),
            "json_assertions": {
                "protocol": "task_balance_guard_forward_validation_v2",
                "status": "STRUCTURAL_ONLY_FORWARD_ACCOUNTING_EXACT",
                "source_validation.prediction_matrix_input_used": False,
                "source_validation.baseline_summary_and_ledger_revalidated": True,
                "source_validation.current_summary_and_ledger_revalidated": True,
                "source_validation.current_total_cross_checked_by_receipt_only_independent_verifier": True,
                "access_attestation.prediction_pair_files_opened": [],
                "access_attestation.prediction_values_read_or_aggregated": False,
                "access_attestation.labels_grades_outcomes_or_winner_orientation_read": False,
                "chronology_audit.old_run_set_preserved": True,
                "chronology_audit.old_run_order_preserved_as_subsequence": True,
                "frozen_guard_forward_result.baseline_debt": 657,
                "frozen_guard_forward_result.observed_current_debt": 645,
                "frozen_guard_forward_result.debt_delta": -12,
                "frozen_guard_forward_result.future_dominant_pairs": 27,
                "frozen_guard_forward_result.future_nondominant_pairs": 93,
                "frozen_guard_forward_result.current_cap_pass": False,
                "frozen_guard_forward_result.current_dominant_share": 0.308529945553539,
                "frozen_guard_forward_result.immediate_action_adherence": (
                    "DEFINITELY_NOT_ADHERED_BEFORE_DEBT_CLEARANCE"
                ),
                "claim_boundary.producer_compliance_claimed": False,
                "claim_boundary.predictor_accuracy_effect_or_search_utility_computed": False,
            },
        },
        {
            "path": (
                "phase1/results/task_balance_structural_only_v2_8579_20260826_"
                "1b9b836/forward_independent_verification.json"
            ),
            "sha256_normalized_lf": (
                "00f8fec272705d0d5dfe072f2e0e59efa170913900249a506c829b693f102146"
            ),
            "json_assertions": {
                "protocol": "independent_task_balance_guard_forward_validation_v2",
                "status": "INDEPENDENT_STRUCTURAL_ONLY_TASK_BALANCE_FORWARD_PASS",
                "checks.no_prediction_matrix_input": True,
                "checks.both_accumulator_sources_recomputed": True,
                "checks.current_total_receipt_cross_check_exact": True,
                "checks.debt_accounting_identity_exact": True,
                "checks.cap_failure_preserved": True,
                "checks.causal_and_effect_claims_forbidden": True,
                "access_attestation.outcomes_or_prediction_values_read": False,
                "recomputed.baseline_pairs": 2635,
                "recomputed.current_pairs": 2755,
                "recomputed.baseline_debt": 657,
                "recomputed.current_debt": 645,
                "recomputed.debt_delta": -12,
                "recomputed.current_dominant_share": 0.308529945553539,
            },
        },
    ],
}

REPLACEMENT_ENTRIES = [
    PROVENANCE_REPAIR_ENTRY,
    RECEIPT_COMMON_SUPPORT_ENTRY,
    STRUCTURAL_WEIGHTING_ENTRY,
    OPPORTUNITY_YIELD_AUDIT_ENTRY,
    TASK_BALANCE_V2_ENTRY,
]
