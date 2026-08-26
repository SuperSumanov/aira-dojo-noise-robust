"""Frozen schema for identifier-erased historical-to-future overlap audit."""

from __future__ import annotations


PROTOCOL = "historical_train_to_prospective_identifier_erased_overlap_v1"
INDEPENDENT_PROTOCOL = (
    "independent_historical_train_to_prospective_identifier_erased_overlap_v1"
)
REPRESENTATION = "python_token_identifier_erased_v1"
FROZEN_COHORT_RUN_TARGET = 960
SHINGLE_SIZE = 5
SHINGLE_HASH_BITS = 128
MIN_DISTINCT_SHINGLES = 20
PRIMARY_NUMERATOR = 17
PRIMARY_DENOMINATOR = 20
STRICT_NUMERATOR = 19
STRICT_DENOMINATOR = 20
SELF_CHECK_PER_SIDE = 256

MIN_HISTORICAL_COVERAGE = 0.99
MIN_PROSPECTIVE_COVERAGE = 0.99
MAX_PROSPECTIVE_AFFECTED_FRACTION = 0.01
MAX_CROSS_TASK_PROSPECTIVE_AFFECTED_FRACTION = 0.005
MAX_LARGE_MULTITASK_COMPONENTS = 0
LARGE_COMPONENT_MIN_ENDPOINTS = 10
LARGE_COMPONENT_MIN_TASKS = 3

IDENTIFIER_TOKEN = "<IDENT>"
NUMBER_TOKEN = "<NUMBER>"
STRING_TOKEN = "<STRING>"

HISTORICAL_CARDS_PATH = "phase1/cards_current_v11.jsonl"
HISTORICAL_CARDS_SHA256 = (
    "6794acbf1dbc21ca75bed5899f4dd071b4b0d1a5b092c2e60bc634a8c5701b75"
)
HISTORICAL_PAIR_FILES = (
    (
        "phase1/v11_decision/decision_train_v11_b0.jsonl",
        "bd31b4679c7b4405703b976921df0bc63acba4fc0c4a002f4b8f36d171251fca",
        4263,
    ),
    (
        "phase1/v11_decision/decision_train_v11_b1.jsonl",
        "5053bb3825c5d6a420491cdb056594b306b4850c2b3c179361031becade5d528",
        861,
    ),
    (
        "phase1/v11_decision/decision_train_v11_b2.jsonl",
        "f0cb83c41b1e45d198384726194b3a2bd013132957d71aa2d81aea318dd7c881",
        692,
    ),
)
HISTORICAL_UNION_ROWS = 5816
HISTORICAL_UNION_ENDPOINTS = 5519
HISTORICAL_UNION_RUNS = 333
HISTORICAL_UNION_TASKS = 23
HISTORICAL_UNION_PARENTS = 2302
