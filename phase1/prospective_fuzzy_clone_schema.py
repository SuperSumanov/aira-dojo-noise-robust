"""Frozen schema for the outcome-blind prospective fuzzy-clone audit."""

from __future__ import annotations


PROTOCOL = "prospective_fuzzy_code_clone_audit_v1"
INDEPENDENT_PROTOCOL = "independent_prospective_fuzzy_code_clone_verifier_v1"
FROZEN_COHORT_RUN_TARGET = 960

# The Stack reports five-token shingles and exact Jaccard filtering around 0.85.
# This audit freezes the same primary cutoff before reading real similarities.
SHINGLE_SIZE = 5
MIN_DISTINCT_SHINGLES = 20
PRIMARY_JACCARD_NUMERATOR = 17
PRIMARY_JACCARD_DENOMINATOR = 20
STRICT_JACCARD_NUMERATOR = 19
STRICT_JACCARD_DENOMINATOR = 20
SHINGLE_HASH_BITS = 128
SELF_CHECK_DOCUMENTS = 384

# These are corpus-quality gates, not statistical tests or method-effect gates.
MIN_FINGERPRINT_COVERAGE = 0.99
MAX_CROSS_RUN_AFFECTED_ENDPOINT_FRACTION = 0.01
MAX_CROSS_TASK_AFFECTED_ENDPOINT_FRACTION = 0.005
MAX_LARGE_MULTITASK_COMPONENTS = 0
LARGE_COMPONENT_MIN_ENDPOINTS = 10
LARGE_COMPONENT_MIN_TASKS = 3

BLIND_KEYS = {
    "card_id",
    "task",
    "run_id",
    "code",
    "code_sha256",
    "lineage",
    "generation_started_at_utc",
    "source_sha256",
}
LINEAGE_KEYS = {"depth", "step", "n_siblings", "op", "parent"}
RUN_KEYS = {
    "run_id",
    "task",
    "drop_id",
    "flow_status",
    "endpoints",
    "generation_started_at_utc",
    "source_sha256",
}

RELATIONS = (
    "same_parent_siblings",
    "parent_child",
    "same_run_other",
    "cross_run_same_task",
    "cross_run_cross_task",
)
