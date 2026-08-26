from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
RESULT = (
    REPO_ROOT
    / "phase1/results/prospective_fuzzy_code_clone_audit_8579_20260826_cb368f9"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest(path: Path) -> dict[str, str]:
    rows: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64}) [ *](.+)", line)
        assert match is not None
        rows[match.group(2).removeprefix("./")] = match.group(1)
    return rows


def test_published_package_manifest_covers_every_payload() -> None:
    expected = manifest(RESULT / "SHA256SUMS")
    actual = {
        path.name for path in RESULT.iterdir() if path.is_file() and path.name != "SHA256SUMS"
    }
    assert set(expected) == actual
    assert len(expected) == 11
    for name, expected_sha in expected.items():
        assert sha256(RESULT / name) == expected_sha


def test_formal_summary_records_the_preregistered_positive_result() -> None:
    summary = json.loads((RESULT / "formal_summary.json").read_text(encoding="utf-8"))
    assert summary["source_commit"] == "cb368f95c5374fd2ab7448455b3ba3af054d02ec"
    assert (summary["observed_runs"], summary["observed_endpoints"]) == (366, 10683)
    assert summary["fingerprinted_endpoints"] == 10674
    assert summary["fingerprint_coverage"] == 0.9991575400168492
    assert summary["primary_candidate_pairs"] == 61070
    assert summary["primary_near_duplicate_pairs"] == 7069
    assert summary["primary_relation_pair_counts"] == {
        "cross_run_cross_task": 0,
        "cross_run_same_task": 0,
        "parent_child": 4078,
        "same_parent_siblings": 50,
        "same_run_other": 2941,
    }
    assert sum(summary["primary_relation_pair_counts"].values()) == 7069
    assert summary["primary_cross_run_affected_endpoints"] == 0
    assert summary["primary_cross_task_affected_endpoints"] == 0
    assert summary["strict_near_duplicate_pairs"] == 2758
    assert summary["strict_cross_run_affected_endpoints"] == 0
    assert all(summary["gate_checks"].values())
    assert summary["strong_low_fuzzy_clone_support"] is True
    assert summary["full_tests"] == {"passed": 1163, "skipped": 0, "warnings": 47}


def test_producer_and_independent_receipts_bind_the_same_result() -> None:
    producer = json.loads((RESULT / "producer_a.json").read_text(encoding="utf-8"))
    independent = json.loads(
        (RESULT / "verification_a.json").read_text(encoding="utf-8")
    )
    assert sha256(RESULT / "producer_a.json") == (
        "f07454fdaacfc5ace8ef8b7f6630ed824b80acd0666bc549a2f6e53bc29ccbdc"
    )
    assert sha256(RESULT / "verification_a.json") == (
        "9c6d4bd0938e3cb2517b1c317a8eaa89628bff04eb9d537ac35ec9e4b7c10cf4"
    )
    assert independent["producer_receipt_sha256"] == sha256(RESULT / "producer_a.json")
    assert independent["primary_edge_digest_sha256"] == producer[
        "primary_jaccard_0_85"
    ]["edge_digest_sha256"]
    assert independent["strict_edge_digest_sha256"] == producer[
        "strict_jaccard_0_95"
    ]["edge_digest_sha256"]
    assert independent["producer_aggregate_matches"] is True
    assert independent["subset_bruteforce_matches"] is True
    assert independent["imports_producer_code"] is False


def test_remote_manifest_binds_every_copied_formal_file() -> None:
    remote = manifest(RESULT / "remote_formal_SHA256SUMS")
    copied = (
        "producer_a.json",
        "verification_a.json",
        "formal_summary.json",
        "access_attestation.txt",
        "preflight_13.txt",
        "focused_tests.txt",
        "full_tests.txt",
        "producer_a.time.txt",
        "verifier_a.time.txt",
    )
    for name in copied:
        assert remote[name] == sha256(RESULT / name)
    assert sha256(RESULT / "remote_formal_SHA256SUMS") == (
        "88c6309bc0b4694a4bcc962915a68374e87df3a852c9bad5f29bf320a3f46204"
    )


def test_result_retains_provisional_and_nonsemantic_boundaries() -> None:
    producer = json.loads((RESULT / "producer_a.json").read_text(encoding="utf-8"))
    assert producer["interpretation_contract"] == {
        "exact_means_threshold_join_over_hashed_token_shingle_sets": True,
        "near_duplicate_algorithm_novelty_claimed": False,
        "predictor_accuracy_or_effect_computed": False,
        "provisional_prefix_requires_closure_rerun": True,
        "semantic_clone_absence_claimed": False,
    }
    assert producer["security"]["code_values_emitted"] is False
    assert producer["security"]["task_card_or_run_values_emitted"] is False
    assert producer["security"]["label_vault_opened"] is False
    assert producer["security"]["outcome_files_opened"] == []
    assert producer["security"]["scorer_prediction_files_opened"] == []
    readme = (RESULT / "README.md").read_text(encoding="utf-8")
    assert "严格\nlineage-local" in readme
    assert "不证明\nsemantic equivalence absence" in readme
    assert "first-960+closure 后必须原协议重跑" in readme
