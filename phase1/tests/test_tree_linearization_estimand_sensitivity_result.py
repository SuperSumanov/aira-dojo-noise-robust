from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = (
    ROOT
    / "phase1"
    / "results"
    / "tree_linearization_estimand_sensitivity_887_20260828_5a96d92"
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def verify_manifest(directory: Path) -> str:
    manifest = directory / "SHA256SUMS"
    rows: dict[str, str] = {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        relative = relative.removeprefix("./")
        assert relative not in rows
        rows[relative] = expected
    actual = {
        path.relative_to(directory).as_posix()
        for path in directory.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    }
    assert set(rows) == actual
    for relative, expected in rows.items():
        assert digest(directory / relative) == expected
    return digest(manifest)


def test_source_and_manifest_bindings_are_exact() -> None:
    bindings = load(PACKAGE / "source_bindings.json")
    assert bindings["declaration_commit"] == "d8214ce0a1aecdc184ef6909fc2542c3e1506719"
    assert bindings["formal_source_commit"] == "5a96d92e0d638af6dba6f65c5f4a96e1ab37e9b4"
    sources = bindings["source_sha256"]
    assert digest(
        ROOT / "phase1" / "tree_linearization_estimand_sensitivity_corollary_v1.json"
    ) == sources["protocol"]
    assert digest(
        ROOT / "phase1" / "derive_tree_linearization_estimand_sensitivity.py"
    ) == sources["producer"]
    assert digest(
        ROOT / "phase1" / "verify_tree_linearization_estimand_sensitivity.py"
    ) == sources["verifier"]
    assert digest(
        ROOT / "phase1" / "tests" / "test_tree_linearization_estimand_sensitivity.py"
    ) == sources["tests"]
    assert verify_manifest(PACKAGE / "formal") == bindings["formal_sha256"]["formal_manifest"]
    assert verify_manifest(PACKAGE / "postflight") == bindings["formal_sha256"][
        "postflight_manifest"
    ]


def test_formal_and_independent_receipts_match() -> None:
    formal = PACKAGE / "formal"
    postflight = PACKAGE / "postflight"
    bindings = load(PACKAGE / "source_bindings.json")
    receipt = load(formal / "final_receipt.json")
    verification = load(formal / "independent_verification.json")
    assert digest(formal / "final_receipt.json") == bindings["formal_sha256"]["final_receipt"]
    assert digest(formal / "independent_verification.json") == bindings["formal_sha256"][
        "independent_verification"
    ]
    assert digest(formal / "formal_summary.json") == bindings["formal_sha256"]["formal_summary"]
    assert (formal / "producer_a.json").read_bytes() == (formal / "producer_b.json").read_bytes()
    assert (formal / "verifier_a.json").read_bytes() == (formal / "verifier_b.json").read_bytes()
    assert (formal / "independent_verification.json").read_bytes() == (
        postflight / "verifier_a.json"
    ).read_bytes()
    assert (postflight / "verifier_a.json").read_bytes() == (
        postflight / "verifier_b.json"
    ).read_bytes()
    assert receipt["classification"] == "VERIFIED_EXACT_EDGE_MEASURE_SENSITIVITY_COROLLARY"
    assert verification["status"] == "INDEPENDENT_ESTIMAND_SENSITIVITY_COROLLARY_PASS"
    assert receipt["all_verification_checks_passed"] is True
    assert verification["all_verification_checks_passed"] is True


def test_exact_sensitivity_and_boundaries_are_preserved() -> None:
    receipt = load(PACKAGE / "formal" / "final_receipt.json")
    assert receipt["inventory"] == {
        "canonical_unique_edges": 10895,
        "duplicate_edge_occurrences": 15212,
        "maximum_multiplicity": 144,
        "multiplicity_bins": 47,
        "path_edge_occurrences": 26107,
    }
    assert receipt["edge_measure_shift"]["total_variation"] == {
        "decimal_17g": "0.38618771447395162",
        "denominator": 284435765,
        "numerator": 109845598,
    }
    sharp = receipt["edge_measure_shift"]["sharp_maximizing_set"]
    assert sharp["unique_edges"] == 2286
    assert sharp["path_occurrences"] == 15560
    assert sharp["path_minus_canonical_mass"] == receipt["edge_measure_shift"][
        "total_variation"
    ]
    concentration = receipt["concentration"]
    assert concentration["path_inverse_hhi_descriptive_diversity"] == {
        "decimal_17g": "2300.1564169453659",
        "denominator": 296317,
        "numerator": 681575449,
    }
    assert concentration["path_to_canonical_diversity_retention"] == {
        "decimal_17g": "0.2111203686962245",
        "denominator": 3228373715,
        "numerator": 681575449,
    }
    assert concentration["maximum_single_edge_mass_inflation"] == {
        "decimal_17g": "60.094227601792625",
        "denominator": 26107,
        "numerator": 1568880,
    }
    assert concentration["inverse_hhi_is_statistical_effective_sample_size"] is False
    assert receipt["inverse_multiplicity_correction"]["corrected_total_variation_from_canonical"] == {
        "decimal_17g": "0",
        "denominator": 1,
        "numerator": 0,
    }
    boundary = receipt["claim_boundary"]
    assert boundary["actual_predictor_accuracy_shift_observed"] is False
    assert boundary["particular_natural_metric_attains_bound"] is False
    assert boundary["independent_confirmatory_discovery"] is False
    assert boundary["algorithmic_novelty"] is False
    assert receipt["design_timing"]["exploratory_values_seen_before_this_declaration"] is True


def test_security_and_test_counts_are_preserved() -> None:
    formal = PACKAGE / "formal"
    postflight = PACKAGE / "postflight"
    receipt = load(formal / "final_receipt.json")
    assert (formal / "forbidden_open_hits.txt").read_bytes() == b""
    assert (postflight / "forbidden_open_hits.txt").read_bytes() == b""
    assert (formal / "credential_filename_hits.txt").read_text().strip() == "0"
    assert (formal / "credential_content_file_hits.txt").read_text().strip() == "0"
    assert (postflight / "credential_filename_hits.txt").read_text().strip() == "0"
    assert (postflight / "credential_content_file_hits.txt").read_text().strip() == "0"
    assert receipt["security"]["prospective_label_grade_outcome_prediction_values_read"] is False
    assert receipt["security"]["raw_senior_archives_or_blind_manifests_opened"] is False
    assert receipt["security"]["identity_code_or_per_path_values_written"] is False
    assert receipt["security"]["gpu_api_model_fit_base_update"] == [0, 0, 0, 0]
    assert "27 passed" in (formal / "focused_tests.txt").read_text(encoding="utf-8")
    assert "1330 passed, 47 warnings" in (formal / "full_tests.txt").read_text(encoding="utf-8")
    assert "16 passed" in (postflight / "focused_tests.txt").read_text(encoding="utf-8")
