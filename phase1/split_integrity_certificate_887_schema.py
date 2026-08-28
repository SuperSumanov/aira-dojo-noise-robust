"""Frozen constants for the 435-run split-integrity certificate."""

from __future__ import annotations


PROTOCOL = "decision-corpus-split-integrity-certificate-887-v1"
STATUS = "PROVISIONAL_SPLIT_INTEGRITY_CERTIFICATE_BUILD_COMPLETE"
PROTOCOL_SHA256 = (
    "779ac3f1f5aef522a305b22b578dace2c0a8462fe748a7cd1b30dd20037ef5da"
)
SNAPSHOT_SHA256 = (
    "887491a021d75d889c00a5af672a11b8b06e249d98e84fd91288534080f62697"
)
REPRESENTATION = "python_token_identifier_erased_v1"
FUTURE_RUNS = 435
FUTURE_ENDPOINTS = 11906
HISTORICAL_ENDPOINTS = 5519
HISTORICAL_RUNS = 333
MIN_COVERAGE = 0.99

ZERO_CLASSIFICATION = "PROVISIONAL_ZERO_LINK_SPLIT_INTEGRITY_CERTIFICATE"
LOW_CLASSIFICATION = "PROVISIONAL_LOW_OVERLAP_CERTIFICATE_WITH_EXCEPTIONS"
FAIL_CLASSIFICATION = "NO_SPLIT_INTEGRITY_CERTIFICATE"

WITHIN_SOURCE_COMMIT = "519815df29ef1f7073e93aa1835dd7df06a7a035"
WITHIN_RESULT_PROTOCOL_SHA256 = (
    "a0c5e73c2e6bde6eed920c69909d13d6b0207271758e327b30eb0b346e654f52"
)
WITHIN_FORMAL_ROOT = (
    "/research/d7/spc/yzyang4/prospective-identifier-erased-clone-887/"
    "formal-519815d-887491a-v1"
)
WITHIN_POSTFLIGHT_ROOT = (
    "/research/d7/spc/yzyang4/prospective-identifier-erased-clone-887/"
    "postflight-519815d-887491a-v1"
)
WITHIN_POSTFLIGHT_LOGIC_SHA256 = (
    "1b4ee9dd0841d537ba0ec6769d10e1898cd9148e852b243ea310cc2d888720ee"
)

HISTORICAL_SOURCE_COMMIT = "ec67d1a6f31bde898631019867408687bac1fa99"
HISTORICAL_RESULT_PROTOCOL_SHA256 = (
    "aa3b232c732c53bb24bf2fbac6932276d458f2e6a6ae20321edee0ff2d04ca1b"
)
HISTORICAL_FORMAL_ROOT = (
    "/research/d7/spc/yzyang4/historical-train-future-identifier-erased-overlap/"
    "formal-ec67d1a-887491a-v1"
)
HISTORICAL_POSTFLIGHT_ROOT = (
    "/research/d7/spc/yzyang4/historical-train-future-identifier-erased-overlap/"
    "postflight-ec67d1a-887491a-v1"
)
HISTORICAL_POSTFLIGHT_LOGIC_SHA256 = (
    "0ce8df4d2ecee8f102a2780e743bc17335fb8778be06772526ca12ccac1496dc"
)

PACKAGE_PAYLOADS = {
    "README.md",
    "access_attestation.txt",
    "formal_summary.json",
    "independent_recheck.json",
    "source_bindings.json",
}
