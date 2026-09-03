import hashlib
import json
from pathlib import Path
import shutil

import pytest

from phase1.verify_global_local_accelerate_cpu_state import verify


ROOT = Path(__file__).resolve().parents[2]
RESULT = ROOT / "phase1" / "results" / "global_local_accelerate_20260904"
SUMMARY_SHA = "a16b7d3a7935d65a6fdb1de1a56c725f68941f6cbe0d15ec8b8a7c8e20fb7d4a"
SOURCE_BRIDGE_SHA = "c8e3a8fc903431403f2af9e35b51cd6fc8d5f245c72923dd4bec01a6e48a2b17"


def test_exact_saved_accelerate_artifacts_reverify():
    receipt = verify(RESULT, SUMMARY_SHA)
    assert receipt == json.loads((RESULT / "independent_receipt.json").read_text())
    assert sum(row["verified_forward_receipts"] for row in receipt["trials"]) == 204


def test_saved_context_binds_current_source_bytes():
    context = json.loads((RESULT / "execution_context.json").read_text())
    summary = json.loads((RESULT / "summary.json").read_text())
    bridge = json.loads((RESULT / "source_loss_bridge.json").read_text())
    bindings = {
        "validation_script_sha256": "global_local_accelerate_cpu_validation.py",
        "adapter_sha256": "global_local_accelerate_update_adapter.py",
        "independent_verifier_sha256": "verify_global_local_accelerate_cpu_state.py",
        "source_bridge_script_sha256": "global_local_source_loss_bridge_validation.py",
    }
    for key, name in bindings.items():
        assert context[key] == hashlib.sha256((ROOT / "phase1" / name).read_bytes()).hexdigest()
    assert summary["script_sha256"] == context["validation_script_sha256"]
    assert summary["adapter_sha256"] == context["adapter_sha256"]
    assert bridge["script_sha256"] == context["source_bridge_script_sha256"]


def test_summary_byte_drift_is_rejected(tmp_path):
    shutil.copytree(RESULT, tmp_path / "copy")
    path = tmp_path / "copy" / "summary.json"
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="summary_hash_mismatch"):
        verify(tmp_path / "copy", SUMMARY_SHA)


def test_source_bridge_is_exact_and_does_not_claim_real_model_execution():
    raw = (RESULT / "source_loss_bridge.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == SOURCE_BRIDGE_SHA
    value = json.loads(raw)
    assert value["status"] == "PASS_SOURCE_BOUND_LOSS_AND_POOLING_BRIDGE_NOT_REAL_MODEL"
    assert value["source_sha256"] == "d3cfd12602dc399a456810d4f706124df7117834ebba124813233f77ba043977"
    assert value["loss_gradient_case_count"] == len(value["loss_gradient_cases"]) == 48
    assert value["canonical_sign_vs_winner_first_loss_and_gradient_match"] is True
    assert value["unadapted_canonical_orientation_negative_control_detected"] is True
    assert value["pooling_rows"] == 8
    assert value["last_valid_token_pooling_exact"] is value["pooling_padding_change_invariant"] is True
    assert value["source_logits_dtype"] == "torch.float32"
    assert value["real_model_constructor_called"] is value["real_data_opened"] is value["gpu_context_created"] is False
    assert value["model_fits"] == value["api_calls"] == value["credential_shape_hits"] == 0


@pytest.mark.parametrize("case,expected", [
    ("missing-rank", "rank_set_mismatch"),
    ("wrong-sync", "invalid_sync_boundary"),
    ("target-read", "true_target_access_count_mismatch"),
])
def test_semantic_faults_rejected_even_with_rehashed_files(tmp_path, case, expected):
    destination = tmp_path / "copy"
    shutil.copytree(RESULT, destination)
    summary = json.loads((destination / "summary.json").read_text())
    trial = summary["trials"][0]
    if case == "missing-rank":
        trial["states"].pop()
    elif case == "wrong-sync":
        trial["states"][0]["sync_sequences"][0][0] = True
    else:
        trial["states"][0]["true_target_reads"] += 1
    manifest = {key: value for key, value in trial.items() if key != "manifest_sha256"}
    manifest_path = destination / f"w{trial['world']}-{trial['arm']}" / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True))
    trial["manifest_sha256"] = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    summary_path = destination / "summary.json"
    summary_path.write_text(json.dumps(summary, sort_keys=True))
    new_sha = hashlib.sha256(summary_path.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match=expected):
        verify(destination, new_sha)
