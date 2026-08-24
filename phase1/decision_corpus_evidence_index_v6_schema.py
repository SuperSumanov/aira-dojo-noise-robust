"""Frozen declarations for Decision-Corpus evidence index v6.

The schema performs no I/O and contains no producer implementation.  The new
entry binds only outcome-blind aggregate coverage receipts; pair predictions
and outcome vaults are intentionally absent from the release.
"""

PROTOCOL = "decision_corpus_evidence_index_v6"
STATUS = "PROVISIONAL_COMMON_SUPPORT_EVIDENCE_STACK_AWAITING_FIRST960"
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

SCOPE_ADDITIONS = {
    "prediction_pair_universe_identity_verified": True,
    "prediction_values_aggregated": False,
    "prediction_accuracy_computed": False,
    "common_pair_universe_is_common_effect_population": False,
    "wl_transition_activation_equated": False,
    "transition_effect_unlocked": False,
}

REPORTING_CONTRACT_ADDITIONS = {
    "exact_common_pair_universe_language_allowed": True,
    "seven_arm_effect_or_accuracy_language_allowed": False,
    "common_strict_population_language_allowed": False,
    "transition_effect_unlock_language_allowed": False,
}

COVERAGE_ENTRY = {
    "name": "prediction_escrow_common_support",
    "estimand": (
        "canonical sibling-pair identity overlap, source-specific activation "
        "strata, and explicit prediction missingness across the frozen WL/graph "
        "and transition prediction-escrow families at outcome-blind snapshot f109"
    ),
    "supported_claim": (
        "The four WL arms and three transition fields are keyed to the same 2,589 "
        "canonical structural pair identities across 324 runs and 29 tasks "
        "(intersection=union=2,589; IoU=1; zero reversed orientations). The "
        "source-specific activation cross-tab is 417 both-post, 507 post-WL but "
        "transition-support-only, and 1,665 both-support-only; missing transition "
        "parent sources remain explicit nulls rather than silently changing the pool."
    ),
    "does_not_prove": (
        "Exact structural overlap is not a common strict-effect population and does "
        "not prove predictor accuracy, pairwise effect, method superiority, search "
        "utility, runtime or query cost, first-960 closure, or transition support-gate "
        "passage. No label, grade, outcome, winner orientation, or prediction-value "
        "aggregate was read."
    ),
    "source_formal_receipt": {
        "control_commit": "2c5626ddd94f8fd21c2e4ae6fe5ec4f6cce17e7d",
        "remote_root": (
            "/research/d7/spc/yzyang4/prediction-escrow-coverage-matrix/"
            "2c5626d-f109-v1"
        ),
        "sha256s_file_sha256": (
            "e50065777f18b6167648e5d6900b5f134e6b6b14c56175c7e5540e41e344e7c7"
        ),
        "matrix_raw_sha256": (
            "056ac1582deea643be8b06339aec61a99ad1a35760be8500a20bb004c3e058c2"
        ),
        "independent_verification_raw_sha256": (
            "3ecab354839054af16ed808b0fccb92025ee4a3d397007ce88141445f5c56149"
        ),
    },
    "artifacts": [
        {
            "path": (
                "phase1/results/prediction_escrow_coverage_f109_20260825_2c5626d/"
                "matrix.json"
            ),
            "sha256_normalized_lf": (
                "056ac1582deea643be8b06339aec61a99ad1a35760be8500a20bb004c3e058c2"
            ),
            "json_assertions": {
                "protocol": "prediction-escrow-coverage-matrix-v1",
                "formal_status": "OUTCOME_BLIND_PREDICTION_COVERAGE_VERIFIED",
                "snapshot_sha256": (
                    "f109ac928ed076f83b651af3c4a98bccd11cf592a3c81da541f34f0d2b11d708"
                ),
                "arms.total": 7,
                "arms.wl": [
                    "step_only_lr",
                    "wl_graph_lr",
                    "wl_graph_static_lr",
                    "wl_graph_static_tfidf_lr",
                ],
                "arms.transition": [
                    "child_code",
                    "transition_only",
                    "child_plus_transition",
                ],
                "access_attestation.labels_grades_outcomes_or_winner_orientation_read": False,
                "access_attestation.prediction_values_aggregated": False,
                "access_attestation.accuracy_effect_or_search_utility_computed": False,
                "access_attestation.gpu_or_api_calls": 0,
                "access_attestation.base_llm_updates": 0,
                "criteria.blind_scope_verified": True,
                "criteria.duplicate_canonical_pairs_eq_0": True,
                "criteria.input_hashes_verified": True,
                "criteria.same_snapshot_verified": True,
                "criteria.seven_arm_prediction_fields_complete": True,
                "criteria.source_specific_activation_strata_preserved": True,
                "inventory.wl.pairs": 2589,
                "inventory.transition.pairs": 2589,
                "inventory.wl.runs": 324,
                "inventory.transition.runs": 324,
                "inventory.wl.tasks": 29,
                "inventory.transition.tasks": 29,
                "inventory.wl.nontie_all_arms_pairs": 2589,
                "inventory.transition.nontie_all_arms_pairs": 2244,
                "inventory.wl.strata.post_wl_activation": 924,
                "inventory.wl.strata.support_only": 1665,
                "inventory.transition.strata.post_transition_activation": 417,
                "inventory.transition.strata.support_only": 2172,
                "overlap.intersection_pairs": 2589,
                "overlap.union_pairs": 2589,
                "overlap.intersection_over_union": 1.0,
                "overlap.wl_only_pairs": 0,
                "overlap.transition_only_pairs": 0,
                "overlap.same_left_right_orientation": 2589,
                "overlap.reversed_left_right_orientation": 0,
                "overlap.intersection_mapping_sha256": (
                    "e01313687e69161317226cc4cf2d35f6127fa341b6d5dad14c895c1744fb392f"
                ),
                "overlap.joint_temporal_strata.post_wl_activation|post_transition_activation": 417,
                "overlap.joint_temporal_strata.post_wl_activation|support_only": 507,
                "overlap.joint_temporal_strata.support_only|support_only": 1665,
                "overlap.transition_effect_eligible_pairs": 363,
                "transition_support_receipts.parent_source_present_pairs": 2261,
                "cost_boundary.runtime_or_query_cost_comparison": "NOT_COMPUTED",
                "cost_boundary.shared_runtime_receipt_available": False,
            },
        },
        {
            "path": (
                "phase1/results/prediction_escrow_coverage_f109_20260825_2c5626d/"
                "independent_verification.json"
            ),
            "sha256_normalized_lf": (
                "3ecab354839054af16ed808b0fccb92025ee4a3d397007ce88141445f5c56149"
            ),
            "json_assertions": {
                "protocol": "independent-prediction-escrow-coverage-matrix-v1",
                "formal_status": "INDEPENDENT_COVERAGE_VERIFICATION_PASS",
                "canonical_matrix_sha256": (
                    "2805f62ac7e657154b34d014a61c0486c069d5b8441ff55dd30455238696858e"
                ),
                "access_attestation.labels_grades_outcomes_or_winner_orientation_read": False,
                "access_attestation.prediction_values_aggregated": False,
                "access_attestation.accuracy_effect_or_search_utility_computed": False,
                "recomputed.intersection_pairs": 2589,
                "recomputed.union_pairs": 2589,
                "recomputed.wl_pairs": 2589,
                "recomputed.transition_pairs": 2589,
                "recomputed.runs_in_intersection": 324,
                "recomputed.tasks_in_intersection": 29,
                "recomputed.intersection_mapping_sha256": (
                    "e01313687e69161317226cc4cf2d35f6127fa341b6d5dad14c895c1744fb392f"
                ),
            },
        },
    ],
}
