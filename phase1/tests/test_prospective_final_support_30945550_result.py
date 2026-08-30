import hashlib
import json
from pathlib import Path


ROOT = (
    Path(__file__).resolve().parents[1]
    / "results"
    / "prospective_final_support_30945550_20260831"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_final_outcome_blind_support_receipt_is_bound_and_narrow() -> None:
    value = json.loads((ROOT / "receipt.json").read_text(encoding="utf-8"))
    assert value["status"] == "FINAL_OUTCOME_BLIND_STRUCTURAL_SUPPORT_CERTIFIED"
    assert value["snapshot"]["sha256"] == (
        "30945550b6b12a146dadd6eda733c3b676b467aef86636ae31ac59813133104f"
    )
    assert value["snapshot"]["transactions"] == 126
    assert value["snapshot"]["inventory"] == {
        "physical_runs": 520,
        "eligible_runs": 494,
        "provisional_first960_runs": 494,
        "endpoints": 13098,
        "structural_pairs": 3230,
        "tasks": 34,
    }
    assert value["snapshot"]["closure_provided"] is False
    assert value["snapshot"]["all_scheduled_runs_uploaded"] is None

    assert value["transition"]["selected_runs"] == 494
    assert value["transition"]["added_runs"] == 20
    assert value["transition"]["removed_runs"] == 0
    assert value["wl"]["selected_runs"] == 494
    assert value["wl"]["added_runs"] == value["wl"]["minimum_new_runs_gate"] == 12
    assert value["wl"]["removed_runs"] == 0
    assert value["receipt_support"]["receipt_certified_common_support_pairs"] == 3230
    assert value["receipt_support"]["builder_ab_byte_identical"] is True
    assert value["receipt_support"]["verifier_ab_byte_identical"] is True

    scope = value["scope"]
    for key in (
        "prediction_pair_files_opened",
        "prediction_values_accessed",
        "labels_read",
        "prospective_outcomes_read",
        "accuracy_computed",
        "utility_computed",
        "candidate_identity_read",
    ):
        assert scope[key] is False
    assert scope["effect_metrics_computed"] == []
    assert scope["config_v2_filename_count"] == 0
    assert scope["gpu_jobs"] == 0
    assert scope["paid_api_calls"] == 0
    assert scope["model_fits"] == 0
    assert scope["base_llm_updates"] == 0
    assert "not evidence" in value["claim_boundary"]["forbidden"].lower()


def test_final_support_result_manifest_matches_exact_files() -> None:
    expected = {}
    for line in (ROOT / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        digest, name = line.split("  ", 1)
        expected[name] = digest
    assert expected == {
        "README.md": "84d1f3004cd2fc426533839b2ea0c3bb46ba44ef3df31a8c3f60f89f75e796a0",
        "receipt.json": "24205a1ef27f65dec3911764e2c6bde336e677c63f625c17b78b799b5dd9c24c",
    }
    for name, digest in expected.items():
        assert sha256(ROOT / name) == digest
