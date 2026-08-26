import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RESULT = ROOT / "phase1/results/prediction_receipt_common_support_8579_20260826_9f2cbe9"
SNAPSHOT = "8579d7cd32091a11089b935217f7189e321b1d623dbaa69233182ba2fedd9248"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_safe_projection_receipts_are_exact() -> None:
    formal = json.loads((RESULT / "formal_summary.json").read_text(encoding="utf-8"))
    receipt = json.loads((RESULT / "receipt.json").read_text(encoding="utf-8"))
    verification = json.loads((RESULT / "independent_verification.json").read_text(encoding="utf-8"))
    assert formal["status"] == "INDEPENDENT_PREDICTION_RECEIPT_COMMON_SUPPORT_VERIFIED"
    assert receipt["status"] == "RECEIPT_CERTIFIED_EXACT_CANONICAL_COMMON_SUPPORT"
    assert verification["status"] == formal["status"]
    assert formal["snapshot_sha256"] == receipt["snapshot_sha256"] == verification["snapshot_sha256"] == SNAPSHOT
    assert formal["receipt_certified_common_support_pairs"] == 2755
    assert receipt["receipt_certified_common_support"]["pairs"] == verification["pairs"] == 2755
    assert sha(RESULT / "receipt.json") == formal["receipt_sha256"]
    assert sha(RESULT / "independent_verification.json") == formal["verification_sha256"]


def test_result_preserves_strict_blindness_boundary() -> None:
    formal = json.loads((RESULT / "formal_summary.json").read_text(encoding="utf-8"))
    receipt = json.loads((RESULT / "receipt.json").read_text(encoding="utf-8"))
    verification = json.loads((RESULT / "independent_verification.json").read_text(encoding="utf-8"))
    assert formal["prediction_pair_files_opened"] is False
    assert formal["prediction_values_accessed"] is False
    assert formal["prediction_value_aggregates_computed"] == []
    assert formal["pair_identity_or_orientation_reopened"] is False
    assert formal["prospective_outcomes_read"] is False
    assert formal["effect_metrics_computed"] == []
    assert receipt["scope"]["prediction_values_accessed"] is False
    assert receipt["scope"]["prediction_value_aggregates_computed"] == []
    assert receipt["input_policy"]["prediction_pair_files_opened"] is False
    assert verification["prediction_pair_files_opened"] is False
    assert verification["prediction_values_accessed"] is False
    assert verification["prospective_outcomes_read"] is False


def test_deployment_and_supersession_receipts_preserve_artifacts() -> None:
    deployment = (RESULT / "deployment_receipt.txt").read_text(encoding="utf-8")
    supersession = (RESULT / "supersession_receipt.txt").read_text(encoding="utf-8")
    formal_security = (RESULT / "formal_security.txt").read_text(encoding="utf-8")
    runtime_security = (RESULT / "runtime_security.txt").read_text(encoding="utf-8")
    assert "monitor_pid=2374760" in deployment
    assert "prediction_pair_files_opened=false" in deployment
    assert "prediction_values_accessed=false" in deployment
    assert "old_artifacts_deleted=false" in supersession
    assert "old_artifacts_preserved=true" in supersession
    assert "replacement_validated_before_retirement=true" in supersession
    assert "credential_content_file_hits=0" in formal_security
    assert "prediction_pair_file_open_hits=0" in runtime_security
    assert "outcome_path_open_hits=0" in runtime_security


def test_package_contains_no_prediction_pair_payloads() -> None:
    names = {path.name for path in RESULT.rglob("*") if path.is_file()}
    assert "pair_predictions.jsonl" not in names
    assert "pairs.jsonl" not in names
    assert names == {
        "README.md",
        "SHA256SUMS",
        "deployment_receipt.txt",
        "formal_security.txt",
        "formal_summary.json",
        "independent_verification.json",
        "receipt.json",
        "runtime_security.txt",
        "supersession_receipt.txt",
    }


def test_package_manifest_binds_every_safe_projection_file() -> None:
    rows = (RESULT / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    observed = {}
    for row in rows:
        digest = row[:64]
        relative = row[64:].lstrip(" *")
        observed[relative.removeprefix("./")] = digest
    files = {path.name for path in RESULT.iterdir() if path.is_file() and path.name != "SHA256SUMS"}
    assert set(observed) == files
    for name, expected in observed.items():
        assert sha(RESULT / name) == expected
