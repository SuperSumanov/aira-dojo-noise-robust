"""Frozen protocol schema for Decision-Corpus evidence index v2.

This module contains declarations only.  It performs no I/O and exposes no
producer logic, so the independent verifier does not import the builder.
"""

PROTOCOL = "decision_corpus_evidence_index_v2"
STATUS = "PROVISIONAL_SOURCE_AWARE_EVIDENCE_STACK_AWAITING_FIRST960"
SOURCE_PROTOCOL = "decision_corpus_evidence_index_v1"
SOURCE_STATUS = "PROVISIONAL_EVIDENCE_STACK_AWAITING_FIRST960"
SOURCE_INDEX_RELATIVE = (
    "phase1/results/decision_corpus_evidence_index_v1_20260820/index.json"
)
SOURCE_INDEX_SHA256_NORMALIZED_LF = (
    "cfbe749f84114a633d902a358f8ef8243c4c4fe71433961c94e18494ca93769d"
)

SCOPE = {
    "estimands_merged": False,
    "source_choice_set_complete": False,
    "missing_at_random_assumed": False,
    "prospective_outcomes_read": False,
    "prospective_vault_open_allowed": False,
    "frozen_accuracy_computed_by_deployment_cost": False,
    "release_complete": False,
}

REPORTING_CONTRACT = {
    "first_or_only_claim_allowed": False,
    "complete_choice_set_language_allowed": False,
    "missing_at_random_language_allowed": False,
    "self_report_classification": "post_execution_signal",
    "prospective_effect_claim_allowed": False,
}

SUPPORTED_CLAIMS = {
    "decision_corpus": (
        "Published pairs are context-consistent physical-run siblings with "
        "same-budget train/frozen isolation inside the audited release."
    ),
    "source_opportunity": (
        "The release is a labeled sibling fragment with a high-coverage, "
        "parent-linked registry of missing generated identities and statuses."
    ),
    "label_repeatability": (
        "Pair ordering is highly repeatable on the independently regraded "
        "ten-task subset under the recorded regrade protocol."
    ),
    "normalized_clone": (
        "No cross-run or cross-task duplicates were observed among endpoints "
        "covered by the preregistered token and AST normalizations."
    ),
    "deployment_cost": (
        "The audited lightweight predictors have online query latency far below "
        "recorded candidate execution time under the pinned CPU protocol."
    ),
    "prospective_gate": (
        "The preregistered confirmatory cohort is accruing outcome-blind and "
        "remains sealed until its run target and independent closure are met."
    ),
}

SOURCE_ENTRY = {
    "name": "source_opportunity",
    "estimand": (
        "retention boundary plus parent-linked identity and journal-status "
        "coverage for generated siblings absent from the labeled release"
    ),
    "supported_claim": SUPPORTED_CLAIMS["source_opportunity"],
    "does_not_prove": (
        "The registry does not recover missing numeric outcomes, establish "
        "missing-at-random, make the labeled fragment a complete choice set, "
        "or demonstrate a censor-aware selector's utility."
    ),
    "artifacts": [
        {
            "path": (
                "phase1/results/raw_choice_set_completeness_v11_20260815_6610618/"
                "verification_summary.json"
            ),
            "json_assertions": {
                "status": "VERIFIED_RAW_CHOICE_SET_COMPLETENESS_AUDIT",
                "labeled_sibling_fragment_claim_allowed": True,
                "choice_set_faithful_claim_allowed": False,
                "parents": 3252,
                "reads_first960": False,
                "reads_pair_orientation": False,
                "uses_numeric_outcome_magnitude": False,
            },
        },
        {
            "path": (
                "phase1/results/"
                "source_opportunity_identity_recovery_v11_20260815_3faf001/"
                "verification_summary.json"
            ),
            "json_assertions": {
                "status": "VERIFIED_SOURCE_OPPORTUNITY_IDENTITY_RECOVERY",
                "opportunity_identity_registry_claim_allowed": True,
                "complete_labeled_choice_set_claim_allowed": False,
                "source_incomplete_parents": 870,
                "exact_identity_recoverable_parents": 721,
                "exact_identity_recovery_rate": 0.828735632183908,
                "recovered_missing_identities": 996,
                "nonorphan_unrecoverable_incomplete_parents": 0,
                "reads_first960": False,
                "reads_numeric_outcomes": False,
            },
        },
        {
            "path": (
                "phase1/results/"
                "source_opportunity_journal_status_v11_20260815_42cb6b1/"
                "verification_summary.json"
            ),
            "json_assertions": {
                "status": "VERIFIED_SOURCE_OPPORTUNITY_JOURNAL_STATUS",
                "missing_status_registry_claim_allowed": True,
                "complete_labeled_choice_set_claim_allowed": False,
                "missing_at_random_claim_allowed": False,
                "target_missing_identities": 996,
                "unique_nodes_recovered": 902,
                "node_recovery_rate": 0.9056224899598394,
                "categories.EXECUTION_ERROR": 893,
                "categories.OFFICIAL_GRADE_ABSENT": 9,
                "source_journal_collisions": 0,
                "journal_parent_mismatches": 0,
                "reads_first960": False,
                "reads_numeric_grade": False,
            },
        },
    ],
}
