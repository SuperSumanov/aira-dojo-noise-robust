"""Frozen declarations for Decision-Corpus evidence index v4.

The schema performs no I/O and contains no producer implementation.  The
independent verifier imports only these declarations.
"""

PROTOCOL = "decision_corpus_evidence_index_v4"
STATUS = "PROVISIONAL_FAILURE_AWARE_EVIDENCE_STACK_AWAITING_FIRST960"
SOURCE_PROTOCOL = "decision_corpus_evidence_index_v3"
SOURCE_STATUS = "PROVISIONAL_OBSERVABILITY_AWARE_EVIDENCE_STACK_AWAITING_FIRST960"
SOURCE_INDEX_RELATIVE = (
    "phase1/results/decision_corpus_evidence_index_v3_20260821/index.json"
)
SOURCE_INDEX_SHA256_NORMALIZED_LF = (
    "424f06b161086972fedf55d5e8e06e22d92c21e1558a04b2dd6c55e3cb637b49"
)

SOURCE_ENTRY_NAMES = [
    "decision_corpus",
    "source_opportunity",
    "decision_observability",
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
}

PARTIAL_ORDER_ENTRY = {
    "name": "status_certified_partial_order",
    "estimand": (
        "provenance-certified validity-dominance relation coverage among "
        "natural same-parent MLE-agent source candidates"
    ),
    "supported_claim": (
        "The release contains 2,079 explicit status-certified validity edges; "
        "the stricter execution-error-only subset retains 2,060 edges and "
        "passes every original material and support gate."
    ),
    "does_not_prove": (
        "Validity dominance is not a numeric-quality total order, unresolved "
        "relations remain unknown, and the release does not establish a "
        "complete choice set, missing-at-random, predictor accuracy, search "
        "utility, or algorithmic novelty."
    ),
    "bound_files": [
        {
            "path": (
                "phase1/results/status_certified_edge_manifest_v1_20260821_c9bfc21/"
                "producer_a/edges.jsonl"
            ),
            "sha256_normalized_lf": (
                "dda9f121dc32a1ef309992b0bec61934864e35ec337385bb2f5c0c548b258a3d"
            ),
            "format": "jsonl",
            "line_count": 2079,
        }
    ],
    "artifacts": [
        {
            "path": (
                "phase1/results/status_certified_edge_manifest_v1_20260821_c9bfc21/"
                "producer_a/summary.json"
            ),
            "sha256_normalized_lf": (
                "5dd53823ca6e432e4ab593a1267c9a73bce954be977deceb6de63c4ed90ea84b"
            ),
            "json_assertions": {
                "protocol": "status-certified-edge-export-v1",
                "status": "VERIFIED_STATUS_CERTIFIED_EDGE_MANIFEST",
                "source_commit": "c9bfc21c1e8428787caf4e70db404a18990910bc",
                "edge_count": 2079,
                "unique_invalid_children": 902,
                "unique_valid_children": 1498,
                "parents": 658,
                "tasks": 14,
                "by_category.EXECUTION_ERROR": 2060,
                "by_category.OFFICIAL_GRADE_ABSENT": 19,
                "by_role.train": 1633,
                "by_role.frozen": 424,
                "by_role.extension": 22,
                "execution_error_only_sensitivity.overall.validity_dominance_edges": 2060,
                "execution_error_only_sensitivity.overall.source_pair_capacity": 9755,
                "execution_error_only_sensitivity.overall.published_unique_edges": 5897,
                "execution_error_only_sensitivity.overall.certified_relations": 7957,
                "execution_error_only_sensitivity.overall.certified_coverage": 0.815684264479754,
                "execution_error_only_sensitivity.overall.coverage_gain": 0.21117375704766786,
                "execution_error_only_sensitivity.overall.lost_relation_recovery": 0.5339554173146708,
                "execution_error_only_sensitivity.roles.train.coverage_gain": 0.22004357298474944,
                "execution_error_only_sensitivity.roles.frozen.coverage_gain": 0.18819351975144252,
                "execution_error_only_sensitivity.roles.extension.coverage_gain": 0.12658227848101267,
                "execution_error_only_sensitivity.support.supported_tasks": 14,
                "execution_error_only_sensitivity.support.tasks_with_positive_gain": 11,
                "execution_error_only_sensitivity.support.dominant_added_relation_task": "spooky-author-identification",
                "execution_error_only_sensitivity.support.dominant_added_relation_task_share": 0.1883495145631068,
                "execution_error_only_sensitivity.preserves_all_original_material_gates": True,
                "execution_error_only_sensitivity.criteria.added_relations_ge_material_minimum": True,
                "execution_error_only_sensitivity.criteria.overall_coverage_gain_ge_material_minimum": True,
                "execution_error_only_sensitivity.criteria.gap_recovery_ge_material_minimum": True,
                "execution_error_only_sensitivity.criteria.train_coverage_gain_ge_material_minimum": True,
                "execution_error_only_sensitivity.criteria.frozen_coverage_gain_ge_material_minimum": True,
                "execution_error_only_sensitivity.criteria.supported_tasks_ge_minimum": True,
                "execution_error_only_sensitivity.criteria.tasks_with_positive_gain_ge_minimum": True,
                "execution_error_only_sensitivity.criteria.dominant_task_share_le_maximum": True,
                "execution_error_only_sensitivity.criteria.relation_accounting_exact": True,
                "execution_error_only_sensitivity.criteria.unknown_status_not_promoted": True,
                "scope.post_result_release_export": True,
                "scope.published_pair_files_read_for_endpoint_identity": True,
                "scope.published_pair_orientation_direction_used": False,
                "scope.gap_or_numeric_score_used": False,
                "scope.candidate_code_read": False,
                "scope.prospective_outcome_read": False,
                "scope.complete_choice_set_claim": False,
                "scope.numeric_quality_order_claim": False,
            },
        },
        {
            "path": (
                "phase1/results/status_certified_edge_manifest_v1_20260821_c9bfc21/"
                "verification_a.json"
            ),
            "sha256_normalized_lf": (
                "ae280675707b38fad4da3042296b90c7a2fd3c744f484ba482703c542d0e5abf"
            ),
            "json_assertions": {
                "status": "INDEPENDENT_STATUS_CERTIFIED_EDGE_MANIFEST_VERIFIED",
                "producer_status": "VERIFIED_STATUS_CERTIFIED_EDGE_MANIFEST",
                "imports_producer": False,
                "edge_count": 2079,
                "unique_invalid_children": 902,
                "execution_error_only_preserves_all_original_material_gates": True,
                "maximum_reconstruction_difference": 0,
                "pair_orientation_direction_used": False,
                "prospective_outcome_read": False,
                "artifact_summary_sha256": (
                    "5dd53823ca6e432e4ab593a1267c9a73bce954be977deceb6de63c4ed90ea84b"
                ),
                "artifact_manifest_sha256": (
                    "e843720791e51501e07e556acaa05cd8624c1334d74879e4a6df8a61e1780323"
                ),
            },
        },
        {
            "path": (
                "phase1/results/status_certified_edge_manifest_v1_20260821_c9bfc21/"
                "producer_a/sha256_manifest.json"
            ),
            "sha256_normalized_lf": (
                "e843720791e51501e07e556acaa05cd8624c1334d74879e4a6df8a61e1780323"
            ),
            "json_assertions": {
                "edges.jsonl": (
                    "dda9f121dc32a1ef309992b0bec61934864e35ec337385bb2f5c0c548b258a3d"
                ),
                "summary.json": (
                    "5dd53823ca6e432e4ab593a1267c9a73bce954be977deceb6de63c4ed90ea84b"
                ),
            },
        },
    ],
}
