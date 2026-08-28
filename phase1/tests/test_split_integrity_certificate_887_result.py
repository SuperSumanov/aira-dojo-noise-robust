from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = (
    Path(__file__).parents[1]
    / "results"
    / "split_integrity_certificate_887_20260828_25efd3a"
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(name: str) -> dict[str, object]:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def test_certificate_is_exactly_bound_and_all_seven_gates_pass() -> None:
    bindings = _json("source_bindings.json")
    certificate = _json("certificate.json")
    assert _sha(ROOT / "certificate.json") == bindings["certificate_sha256"]
    assert certificate["classification"] == (
        "PROVISIONAL_ZERO_LINK_SPLIT_INTEGRITY_CERTIFICATE"
    )
    assert certificate["snapshot_sha256"] == (
        "887491a021d75d889c00a5af672a11b8b06e249d98e84fd91288534080f62697"
    )
    assert certificate["future_population"] == {
        "closure": False,
        "endpoints": 11906,
        "runs": 435,
    }
    assert certificate["historical_population"] == {"endpoints": 5519, "runs": 333}
    assert all(certificate["certificate_gates"].values())
    within = certificate["within_future"]
    assert within["fingerprinted_endpoints"] == 11894
    assert within["primary_links"] == 11421
    assert within["primary_cross_run_links"] == 0
    assert within["strict_links"] == 4068
    assert within["strict_cross_run_links"] == 0
    historical = certificate["historical_to_future"]
    assert historical["historical_fingerprinted_endpoints"] == 5519
    assert historical["future_fingerprinted_endpoints"] == 11894
    assert historical["primary_links"] == 0
    assert historical["primary_same_task_links"] == 0
    assert historical["primary_cross_task_links"] == 0
    assert historical["strict_links"] == 0


def test_independent_verification_and_claim_boundary_are_preserved() -> None:
    bindings = _json("source_bindings.json")
    receipt = _json("independent_verification.json")
    assert _sha(ROOT / "independent_verification.json") == bindings[
        "independent_verification_sha256"
    ]
    assert receipt["status"] == (
        "INDEPENDENT_SPLIT_INTEGRITY_CERTIFICATE_VERIFIED"
    )
    assert receipt["classification"] == (
        "PROVISIONAL_ZERO_LINK_SPLIT_INTEGRITY_CERTIFICATE"
    )
    assert receipt["certificate_sha256"] == bindings["certificate_sha256"]
    assert receipt["imports_builder"] is False
    assert receipt["raw_corpus_or_archive_reopened"] is False
    assert receipt["identity_values_read"] is False
    assert receipt["prospective_outcomes_or_prediction_values_read"] is False
    assert receipt["gpu_api_model_fit_base_update"] == [0, 0, 0, 0]
    boundary = _json("certificate.json")["claim_boundary"]
    assert boundary == {
        "all_possible_historical_training_sources_covered": False,
        "new_clone_detection_method_claimed": False,
        "predictor_effect_accuracy_or_search_utility_computed": False,
        "pretraining_contamination_absence_proven": False,
        "provisional_until_first960_and_closure": True,
        "semantic_clone_absence_proven": False,
        "unfingerprintable_endpoints_certified": False,
    }
