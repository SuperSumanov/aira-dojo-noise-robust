"""Frozen declarations for Decision-Corpus evidence index v5.

The schema performs no I/O and contains no producer implementation. The
independent verifier imports only these declarations.
"""

PROTOCOL = "decision_corpus_evidence_index_v5"
STATUS = "PROVISIONAL_SOURCE_ANSWERABILITY_EVIDENCE_STACK_AWAITING_FIRST960"
SOURCE_PROTOCOL = "decision_corpus_evidence_index_v4"
SOURCE_STATUS = "PROVISIONAL_FAILURE_AWARE_EVIDENCE_STACK_AWAITING_FIRST960"
SOURCE_INDEX_RELATIVE = (
    "phase1/results/decision_corpus_evidence_index_v4_20260821/index.json"
)
SOURCE_INDEX_SHA256_NORMALIZED_LF = (
    "80450de3528fcaf2dc5edb5f54109ba30189f81e66c5715fbe755012d5de391b"
)

SOURCE_ENTRY_NAMES = [
    "decision_corpus",
    "source_opportunity",
    "decision_observability",
    "status_certified_partial_order",
    "label_repeatability",
    "normalized_clone",
    "deployment_cost",
    "prospective_gate",
]

SCOPE = {
    "estimands_merged": False,
    "source_choice_set_complete": False,
    "missing_at_random_assumed": False,
    "prospective_outcomes_read": False,
    "prospective_vault_open_allowed": False,
    "frozen_accuracy_computed_by_deployment_cost": False,
    "release_complete": False,
    "observability_is_actual_agent_comparison_log": False,
    "observability_establishes_predictor_or_search_utility": False,
    "status_partial_order_is_numeric_quality_order": False,
    "status_partial_order_is_complete_choice_set": False,
    "status_partial_order_establishes_predictor_or_search_utility": False,
    "status_unknown_imputed": False,
    "grade_absent_required_for_materiality": False,
    "source_winner_answerability_is_predictor_accuracy": False,
    "source_winner_answerability_is_search_utility": False,
    "source_winner_answerability_is_complete_total_order": False,
    "source_identity_unavailable_imputed": False,
    "transitive_relations_are_logged_comparisons": False,
}

REPORTING_CONTRACT = {
    "first_or_only_claim_allowed": False,
    "complete_choice_set_language_allowed": False,
    "missing_at_random_language_allowed": False,
    "self_report_classification": "post_execution_signal",
    "prospective_effect_claim_allowed": False,
    "decision_point_disappearance_language_allowed": False,
    "actual_agent_comparison_count_language_allowed": False,
    "numeric_quality_total_order_language_allowed": False,
    "explicit_validity_edge_count_language_allowed": True,
    "source_winner_answerability_language_allowed": True,
    "source_winner_predictor_performance_language_allowed": False,
}

PARENT_HEADER = [
    "role",
    "task",
    "run_id_sha256",
    "parent_sha256",
    "source_children",
    "finite_children",
    "source_identity_available",
    "missing_identity_children",
    "certified_invalid_children",
    "unknown_source_children",
    "published_direct_relations",
    "status_direct_relations",
    "execution_only_direct_relations",
    "published_transitive_relations",
    "status_transitive_relations",
    "execution_only_transitive_relations",
    "published_top_set_size",
    "status_top_set_size",
    "execution_only_top_set_size",
    "published_winner_identified",
    "status_winner_identified",
    "execution_only_winner_identified",
    "newly_identified_by_status",
    "newly_identified_execution_only",
]

TASK_HEADER = [
    "stratum_type",
    "stratum",
    "parents",
    "runs",
    "source_pair_capacity",
    "source_identity_available_parents",
    "published_direct_relations",
    "status_direct_relations",
    "execution_only_direct_relations",
    "published_transitive_relations",
    "status_transitive_relations",
    "execution_only_transitive_relations",
    "published_winners",
    "status_winners",
    "execution_only_winners",
    "newly_identified_by_status",
    "newly_identified_execution_only",
    "published_winner_rate",
    "status_winner_rate",
    "execution_only_winner_rate",
    "status_winner_rate_gain",
    "execution_only_winner_rate_gain",
    "status_unanswered_gap_recovery",
    "execution_only_unanswered_gap_recovery",
    "published_relation_coverage",
    "status_direct_relation_coverage",
    "status_transitive_relation_coverage",
    "execution_only_transitive_relation_coverage",
]

ANSWERABILITY_ENTRY = {
    "name": "source_decision_answerability",
    "estimand": (
        "fraction of all frozen natural source-parent choice sets for which the "
        "released provenance-bound partial order certifies a unique winner"
    ),
    "supported_claim": (
        "Published finite orientations certify 2,344 of 3,252 source winners; "
        "status-certified validity raises this to 3,001, adds 657, and reaches "
        "a 0.9228167281672817 all-parent answerability rate."
    ),
    "does_not_prove": (
        "Source-winner answerability is not predictor accuracy, search utility, "
        "a complete numeric total order, or a prospective effect; transitive "
        "relations are implications of the released partial order rather than "
        "logged agent comparisons, and identity-unavailable parents remain "
        "unanswered."
    ),
    "bound_files": [
        {
            "path": (
                "phase1/results/source_decision_answerability_v1_20260821_e9f6f69/"
                "per_parent.csv"
            ),
            "sha256_normalized_lf": (
                "b2488d059ce4fafacc321e98fb4f4e82b5f0b4d4abc86a413d9e6f80da0cb4d4"
            ),
            "format": "csv",
            "line_count": 3253,
            "data_row_count": 3252,
            "header": PARENT_HEADER,
        },
        {
            "path": (
                "phase1/results/source_decision_answerability_v1_20260821_e9f6f69/"
                "per_task.csv"
            ),
            "sha256_normalized_lf": (
                "7c1669f101706efc76c0894c76f5abc382eb842401141b01037505404d168fb5"
            ),
            "format": "csv",
            "line_count": 24,
            "data_row_count": 23,
            "header": TASK_HEADER,
        },
    ],
    "artifacts": [
        {
            "path": (
                "phase1/results/source_decision_answerability_v1_20260821_e9f6f69/"
                "summary.json"
            ),
            "sha256_normalized_lf": (
                "048f18cc2769df4c9cc4836c491c2917b2e8b051a847da20bdce454dd6592326"
            ),
            "json_assertions": {
                "protocol": "source-decision-answerability-v1",
                "status": "VERIFIED_MATERIAL_SOURCE_WINNER_ANSWERABILITY_RECOVERY",
                "source_commit": "e9f6f69ebb1364e14bd97ce0a140be6579977f33",
                "claim_allowed": True,
                "overall.parents": 3252,
                "overall.runs": 440,
                "overall.source_pair_capacity": 9755,
                "overall.source_identity_available_parents": 3103,
                "overall.published_winners": 2344,
                "overall.status_winners": 3001,
                "overall.newly_identified_by_status": 657,
                "overall.published_winner_rate": 0.7207872078720787,
                "overall.status_winner_rate": 0.9228167281672817,
                "overall.status_winner_rate_gain": 0.20202952029520296,
                "overall.status_unanswered_gap_recovery": 0.723568281938326,
                "overall.execution_only_winners": 2993,
                "overall.newly_identified_execution_only": 649,
                "overall.execution_only_winner_rate": 0.9203567035670357,
                "overall.execution_only_winner_rate_gain": 0.19956949569495694,
                "overall.execution_only_unanswered_gap_recovery": 0.7147577092511013,
                "roles.train.newly_identified_by_status": 496,
                "roles.train.status_winner_rate_gain": 0.21631051024858264,
                "roles.frozen.newly_identified_by_status": 150,
                "roles.frozen.status_winner_rate_gain": 0.17751479289940827,
                "roles.extension.newly_identified_by_status": 11,
                "roles.extension.status_winner_rate_gain": 0.09649122807017543,
                "support.supported_tasks": 14,
                "support.tasks_with_positive_gain": 11,
                "support.dominant_added_winner_task_share": 0.2800608828006088,
                "support.execution_only_tasks_with_positive_gain": 11,
                "support.execution_only_dominant_added_winner_task_share": 0.28197226502311246,
                "criteria.newly_identified_parents_ge_material_minimum": True,
                "criteria.overall_winner_rate_gain_ge_material_minimum": True,
                "criteria.train_winner_rate_gain_ge_material_minimum": True,
                "criteria.frozen_winner_rate_gain_ge_material_minimum": True,
                "criteria.status_winner_rate_ge_material_minimum": True,
                "criteria.supported_tasks_ge_minimum": True,
                "criteria.tasks_with_positive_gain_ge_minimum": True,
                "criteria.dominant_added_winner_task_share_le_maximum": True,
                "execution_error_only_sensitivity_criteria.newly_identified_parents_ge_material_minimum": True,
                "execution_error_only_sensitivity_criteria.overall_winner_rate_gain_ge_material_minimum": True,
                "execution_error_only_sensitivity_criteria.train_winner_rate_gain_ge_material_minimum": True,
                "execution_error_only_sensitivity_criteria.frozen_winner_rate_gain_ge_material_minimum": True,
                "execution_error_only_sensitivity_criteria.status_winner_rate_ge_material_minimum": True,
                "execution_error_only_sensitivity_criteria.tasks_with_positive_gain_ge_minimum": True,
                "execution_error_only_sensitivity_criteria.dominant_added_winner_task_share_le_maximum": True,
                "scope.code_or_observation_used": False,
                "scope.numeric_grade_used": False,
                "scope.gap_used": False,
                "scope.prospective_outcome_used": False,
                "scope.inferred_relations_are_logged_comparisons": False,
                "scope.complete_total_order_claim_allowed": False,
                "scope.predictor_or_search_utility_claim_allowed": False,
            },
        },
        {
            "path": (
                "phase1/results/source_decision_answerability_v1_20260821_e9f6f69/"
                "independent_verification.json"
            ),
            "sha256_normalized_lf": (
                "05e4398e65ba9b19559247cf084359eba0d6ec18753b72dbe6fb8f780e1c845e"
            ),
            "json_assertions": {
                "protocol": "independent-source-decision-answerability-verifier-v1",
                "status": "INDEPENDENT_SOURCE_DECISION_ANSWERABILITY_VERIFIED",
                "producer_imported": False,
                "producer_status": "VERIFIED_MATERIAL_SOURCE_WINNER_ANSWERABILITY_RECOVERY",
                "parents": 3252,
                "published_winners": 2344,
                "status_winners": 3001,
                "newly_identified_by_status": 657,
                "summary_sha256": (
                    "048f18cc2769df4c9cc4836c491c2917b2e8b051a847da20bdce454dd6592326"
                ),
            },
        },
        {
            "path": (
                "phase1/results/source_decision_answerability_v1_20260821_e9f6f69/"
                "producer_sha256_manifest.json"
            ),
            "sha256_normalized_lf": (
                "674405276e61abba1971b6e68dda26d2edcef400466b6beb7b50430a39d3de18"
            ),
            "json_assertions": {
                "per_parent.csv": (
                    "b2488d059ce4fafacc321e98fb4f4e82b5f0b4d4abc86a413d9e6f80da0cb4d4"
                ),
                "per_task.csv": (
                    "7c1669f101706efc76c0894c76f5abc382eb842401141b01037505404d168fb5"
                ),
                "summary.json": (
                    "048f18cc2769df4c9cc4836c491c2917b2e8b051a847da20bdce454dd6592326"
                ),
            },
        },
    ],
}
