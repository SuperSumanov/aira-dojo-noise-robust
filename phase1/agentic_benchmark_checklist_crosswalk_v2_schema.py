"""Frozen migration declarations for the clean-provenance ABC crosswalk v2."""

PROTOCOL = "agentic_benchmark_checklist_crosswalk_v2"
STATUS = "CLEAN_PROVENANCE_HUMAN_ASSESSMENT_AWAITING_FIRST960"
SOURCE_PATH = (
    "phase1/results/agentic_benchmark_checklist_crosswalk_v1_20260825/"
    "crosswalk.json"
)
SOURCE_SHA256_NORMALIZED_LF = (
    "fb622cd16e95d6e340ce6fba4bf6661329ec005ec43b184b5ef3cbf29d179b1b"
)
SOURCE_PROTOCOL = "agentic_benchmark_checklist_crosswalk_v1"
SOURCE_STATUS = "HUMAN_ASSESSMENT_WITH_HASH_BOUND_EVIDENCE_AWAITING_FIRST960"

EXPECTED_ITEM_IDS = (
    "O.i.1",
    "T.1",
    "T.2",
    "T.3",
    "T.4",
    "T.5",
    "T.6",
    "T.7",
    "T.8",
    "T.9",
    "T.10",
    "R.1",
    "R.2",
    "R.3",
    "R.4",
    "R.5",
    "R.6",
    "R.7",
    "R.8",
    "R.9",
    "R.10",
    "R.11",
    "R.12",
    "R.13",
)

ALLOWED_STATUSES = (
    "PASS_LOCAL",
    "PARTIAL",
    "INHERITED_UPSTREAM",
    "NOT_APPLICABLE",
)

LOCKED_CONSERVATIVE_STATUSES = {
    "O.i.1": "INHERITED_UPSTREAM",
    "T.1": "PARTIAL",
    "T.6": "PARTIAL",
    "T.10": "PARTIAL",
    "R.1": "PARTIAL",
    "R.3": "PARTIAL",
    "R.10": "PARTIAL",
    "R.12": "PARTIAL",
    "R.13": "NOT_APPLICABLE",
}

REMOVED_EVIDENCE_IDS = (
    "evidence_index_v6",
    "evidence_index_v6_independent",
    "coverage_7cda",
    "coverage_7cda_independent",
    "balance_guard",
    "balance_guard_independent",
)

FORBIDDEN_EVIDENCE_PATH_FRAGMENTS = (
    "decision_corpus_evidence_index_v6_20260825",
    "prediction_escrow_coverage_7cda_20260825_6299865",
    "prediction_escrow_coverage_f109_20260825_2c5626d",
    "task_balance_accrual_guard_7cda_20260825",
    "task_balance_guard_forward_8579_20260826",
)

EVIDENCE_ID_REPLACEMENTS = {
    "evidence_index_v6": "evidence_index_v7",
    "evidence_index_v6_independent": "evidence_index_v7_independent",
    "coverage_7cda": "receipt_common_support",
    "coverage_7cda_independent": "receipt_common_support_independent",
    "balance_guard": "task_balance_v2",
    "balance_guard_independent": "task_balance_v2_independent",
}

ADDED_EVIDENCE = {
    "evidence_index_v7": {
        "path": (
            "phase1/results/decision_corpus_evidence_index_v7_20260826_a83bebf/"
            "index.json"
        ),
        "sha256_normalized_lf": (
            "d8cc9c60900ab41ff1df0e3aae3add29bbb922d5a32157957dcac5675fa31674"
        ),
        "role": "Clean-provenance machine index for fourteen audit assets and claim boundaries.",
    },
    "evidence_index_v7_independent": {
        "path": (
            "phase1/results/decision_corpus_evidence_index_v7_20260826_a83bebf/"
            "independent_verification.json"
        ),
        "sha256_normalized_lf": (
            "b0bcd3213be641dcf6832b08d6a47720189bcfacc72dca15276ed01fe191d128"
        ),
        "role": "Independent reconstruction of the clean-provenance v7 evidence index.",
    },
    "receipt_common_support": {
        "path": (
            "phase1/results/prediction_receipt_common_support_8579_20260826_"
            "9f2cbe9/receipt.json"
        ),
        "sha256_normalized_lf": (
            "3b2d0200cf8982a69837a65ca0511fcb35534c94ee440f6bf17789c09c721263"
        ),
        "role": "Receipt-certified 2,755-pair common support without prediction-pair access.",
    },
    "receipt_common_support_independent": {
        "path": (
            "phase1/results/prediction_receipt_common_support_8579_20260826_"
            "9f2cbe9/independent_verification.json"
        ),
        "sha256_normalized_lf": (
            "24a7ff758d391f4fd506236df97f1a9d6692ddb965cab490e6e92475e2cb012e"
        ),
        "role": "Independent receipt-only common-support verification.",
    },
    "provenance_taint_registry": {
        "path": "phase1/prediction_matrix_downstream_taint_registry_v1.json",
        "sha256_normalized_lf": (
            "f15cba54aca4572cc6c515d8b0f30d614874997bc873fa5cee7698f0aeb3c13b"
        ),
        "role": "Immutable propagation registry for all withdrawn strict-zero-value pointers.",
    },
    "structural_weight_trajectory": {
        "path": (
            "phase1/results/structural_weight_trajectory_7cda_20260826/"
            "headline_metrics.json"
        ),
        "sha256_normalized_lf": (
            "8d4041994f8998e5a04df0e2e18508ebf97915221303c14f62d9abb8d0e6b2b2"
        ),
        "role": "Outcome-blind run-to-pair task-weight trajectory with all robustness gates.",
    },
    "structural_weight_trajectory_independent": {
        "path": (
            "phase1/results/structural_weight_trajectory_7cda_20260826/"
            "independent_verification.json"
        ),
        "sha256_normalized_lf": (
            "8094e21acde877a67cdcc295c6decaaaf9e650c06fd55a91ed69026f877f9420"
        ),
        "role": "Independent recomputation of the structural weighting trajectory.",
    },
    "opportunity_yield_audit": {
        "path": (
            "phase1/results/opportunity_yield_aggregation_audit_v1_20260826/"
            "formal_summary.json"
        ),
        "sha256_normalized_lf": (
            "ec0671e8fb4d17faa53603fc53c4a8a98069e27a86feeac203a89e932d61e053"
        ),
        "role": "Frozen closure-time opportunity-yield aggregation interpretation contract.",
    },
    "opportunity_yield_audit_independent": {
        "path": (
            "phase1/results/opportunity_yield_aggregation_audit_v1_20260826/"
            "independent_verification.json"
        ),
        "sha256_normalized_lf": (
            "0054e5fceaf326b67f773d44109841ce576db59c9efd959671e97b6b3357e973"
        ),
        "role": "Independent verification of the no-rescue aggregation contract.",
    },
    "task_balance_v2": {
        "path": (
            "phase1/results/task_balance_structural_only_v2_8579_20260826_"
            "1b9b836/forward_validation.json"
        ),
        "sha256_normalized_lf": (
            "fca979bb912c61bb14385638069a64aefcb8a7b9bc41cb77c260d07075ea0fb1"
        ),
        "role": "Structural-only task-balance forward accounting; cap and adherence failures retained.",
    },
    "task_balance_v2_independent": {
        "path": (
            "phase1/results/task_balance_structural_only_v2_8579_20260826_"
            "1b9b836/forward_independent_verification.json"
        ),
        "sha256_normalized_lf": (
            "00f8fec272705d0d5dfe072f2e0e59efa170913900249a506c829b693f102146"
        ),
        "role": "Independent structural-only task-balance reconstruction.",
    },
}

ITEM_EXTRA_EVIDENCE = {
    "T.10": ("provenance_taint_registry",),
    "R.7": ("provenance_taint_registry",),
    "R.8": (
        "structural_weight_trajectory",
        "structural_weight_trajectory_independent",
    ),
    "R.9": (
        "structural_weight_trajectory",
        "structural_weight_trajectory_independent",
        "opportunity_yield_audit",
        "opportunity_yield_audit_independent",
    ),
}

ITEM_RATIONALE_REPLACEMENTS = {
    "T.5": (
        "The confirmatory pipeline is outcome-blind, keeps the vault sealed, "
        "verifies train/frozen physical-run isolation, and now binds those claims "
        "through the clean-provenance v7 index."
    ),
    "T.10": (
        "Run leakage, fragmentary choice sets, clone risk, structural invalidity, "
        "task concentration, and the prediction-matrix provenance incident are "
        "explicitly audited with fail-closed handling and preserved retractions."
    ),
    "R.2": (
        "The public repository contains reconstruction, audit, predictor, escrow, "
        "and independent-verification code; v7 and the receipt-only join bind "
        "representative outputs without opening prediction values."
    ),
    "R.5": (
        "The estimand is execution-free ranking of same-decision physical-run "
        "siblings before candidate execution; cost, post-execution self-report, "
        "receipt-certified support, structural weighting, and accuracy remain "
        "distinct constructs."
    ),
    "R.6": (
        "The benchmark evaluates independent critics and predictors over frozen "
        "sibling decisions; receipt-certified support does not evaluate or update "
        "the base agent LLM."
    ),
    "R.7": (
        "The project preserves retractions, independently reconstructs physical "
        "runs, rejects invalid archives without outcomes, and rebuilds tainted "
        "machine pointers from unaffected sources rather than rewriting history."
    ),
    "R.8": (
        "Every v7 asset carries an explicit does-not-prove boundary; fragmentary "
        "choice sets, missing outcomes, task-weight transformation, batch-sensitive "
        "magnitude, task concentration, and public-task exposure remain visible."
    ),
    "R.9": (
        "The clean evidence stack quantifies label repeatability, observability "
        "loss, clone isolation, archive rejection, receipt-certified support, "
        "deployment cost, run-to-pair weighting shift, and structural balance debt."
    ),
    "R.10": (
        "Retrospective same-pool suites use task- and parent-clustered intervals, "
        "while the clean v7 stack forbids any prospective first-960 effect before "
        "closure."
    ),
    "R.11": (
        "V7 forbids translating receipt-certified support or structural weighting "
        "into accuracy, effect, or search utility and freezes an explicit "
        "opportunity-yield interpretation contract."
    ),
    "R.12": (
        "Upstream MLE-bench reports human Kaggle performance, and the local suite "
        "includes random and static non-neural comparators. The final closed "
        "common-support predictor table still does not exist."
    ),
    "R.13": (
        "A do-nothing agent is not the evaluated object in a predictor benchmark. "
        "The correct analogue is an orientation-independent random predictor; "
        "receipt-certified support does not convert that analogue into a literal pass."
    ),
}

ACCESS_ATTESTATION = {
    "prospective_labels_grades_outcomes_or_winner_orientation_read": False,
    "prediction_pair_files_opened_by_v2": False,
    "prediction_values_read_or_aggregated_by_v2": False,
    "withdrawn_artifacts_used_as_v2_evidence": False,
    "accuracy_effect_or_search_utility_computed": False,
    "gpu_or_api_calls": 0,
    "base_llm_updates": 0,
}
