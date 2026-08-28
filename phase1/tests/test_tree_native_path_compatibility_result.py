from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = (
    ROOT
    / "phase1"
    / "results"
    / "tree_native_path_compatibility_887_20260828_cdc90e4"
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def verify_manifest(directory: Path) -> str:
    manifest_path = directory / "SHA256SUMS"
    rows: dict[str, str] = {}
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        relative = relative.removeprefix("./")
        assert relative not in rows
        rows[relative] = expected
    actual_files = {
        path.relative_to(directory).as_posix()
        for path in directory.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    }
    assert set(rows) == actual_files
    for relative, expected in rows.items():
        assert digest(directory / relative) == expected
    return digest(manifest_path)


def test_source_and_manifest_bindings_are_exact() -> None:
    bindings = load(PACKAGE / "source_bindings.json")
    assert bindings["preregistration_commit"] == "0deb5b6e9161547bff7c2ec3566a90c5ab324fad"
    assert bindings["formal_source_commit"] == "cdc90e472eb57189a939187399d6b5fb5ec9a5c1"
    assert digest(ROOT / "phase1" / "tree_native_path_compatibility_contract_v1.json") == bindings[
        "source_sha256"
    ]["protocol"]
    assert digest(ROOT / "phase1" / "certify_tree_native_path_compatibility.py") == bindings[
        "source_sha256"
    ]["producer"]
    assert digest(ROOT / "phase1" / "verify_tree_native_path_compatibility.py") == bindings[
        "source_sha256"
    ]["verifier"]
    assert digest(ROOT / "phase1" / "tests" / "test_tree_native_path_compatibility.py") == bindings[
        "source_sha256"
    ]["tests"]
    assert verify_manifest(PACKAGE / "formal") == bindings["formal_sha256"]["formal_manifest"]
    assert verify_manifest(PACKAGE / "postflight") == bindings["formal_sha256"][
        "postflight_manifest"
    ]
    assert verify_manifest(PACKAGE / "failed_launcher_preworktree") == bindings[
        "formal_sha256"
    ]["failed_launcher_manifest"]


def test_formal_certificate_and_independent_receipts_match() -> None:
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
    assert receipt["classification"] == "VERIFIED_LOSSLESS_TREE_NATIVE_PATH_COMPATIBILITY"
    assert verification["status"] == "INDEPENDENT_TREE_NATIVE_PATH_COMPATIBILITY_PASS"
    assert receipt["all_verification_gates_passed"] is True


def test_exact_recovery_and_claim_boundary_are_preserved() -> None:
    receipt = load(PACKAGE / "formal" / "final_receipt.json")
    assert receipt["inventory"] == {
        "eligible_endpoints": 11906,
        "fragment_leaves": 3599,
        "fragment_roots": 1011,
        "maximum_observed_sibling_group_size": 3,
        "multi_child_observed_sibling_groups": 2565,
        "observed_fragments": 1011,
        "observed_sibling_groups": 8307,
        "observed_unique_edges": 10895,
        "physical_runs": 435,
        "single_node_fragments": 142,
        "tasks": 34,
    }
    assert receipt["path_compatibility"]["path_records"] == 3599
    assert receipt["path_compatibility"]["edge_occurrences"] == 26107
    assert receipt["path_compatibility"]["duplicate_edge_occurrences"] == 15212
    recovery = receipt["exact_recovery"]
    assert recovery["recovered_total_edge_mass"] == {"numerator": 10895, "denominator": 1}
    assert recovery["maximum_per_edge_mass_error"] == {"numerator": 0, "denominator": 1}
    assert recovery["task_clusters_checked"] == 34
    assert recovery["physical_run_clusters_checked"] == 435
    assert recovery["depth_clusters_checked"] == 37
    assert recovery["task_mass_exact"] is True
    assert recovery["physical_run_mass_exact"] is True
    assert recovery["depth_mass_exact"] is True
    boundary = receipt["claim_boundary"]
    assert boundary["elementary_inverse_weight_identity_is_algorithmic_novelty"] is False
    assert boundary["complete_source_tree_or_choice_set_proven"] is False
    assert boundary["predictor_accuracy_effect_or_search_utility_computed"] is False
    assert boundary["first960_or_closure_completed"] is False


def test_security_and_failure_history_are_not_dropped() -> None:
    formal = PACKAGE / "formal"
    postflight = PACKAGE / "postflight"
    failure = PACKAGE / "failed_launcher_preworktree"
    receipt = load(formal / "final_receipt.json")
    assert (formal / "forbidden_open_hits.txt").read_bytes() == b""
    assert (postflight / "forbidden_open_hits.txt").read_bytes() == b""
    assert (formal / "credential_filename_hits.txt").read_text().strip() == "0"
    assert (formal / "credential_content_file_hits.txt").read_text().strip() == "0"
    assert (postflight / "credential_filename_hits.txt").read_text().strip() == "0"
    assert (postflight / "credential_content_file_hits.txt").read_text().strip() == "0"
    assert receipt["security"]["prospective_label_grade_outcome_prediction_values_read"] is False
    assert receipt["security"]["identity_code_or_per_path_values_written"] is False
    failure_receipt = (failure / "failure_receipt.txt").read_text(encoding="utf-8")
    assert "status=FAILED_BEFORE_WORKTREE_AND_BEFORE_SCIENTIFIC_INPUT_READ" in failure_receipt
    assert "formal_output_created=false" in failure_receipt
    assert "prospective_truth_or_prediction_values_read=false" in failure_receipt


def test_formal_test_counts_are_recorded_verbatim() -> None:
    focused = (PACKAGE / "formal" / "focused_tests.txt").read_text(encoding="utf-8")
    full = (PACKAGE / "formal" / "full_tests.txt").read_text(encoding="utf-8")
    assert "31 passed" in focused
    assert "1314 passed, 47 warnings" in full
