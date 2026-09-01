from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from phase1 import critic_scaling_confirmation_analysis as analysis
from phase1 import verify_critic_scaling_confirmation_analysis as verifier


REPO = Path(__file__).resolve().parents[2]
CONTRACT_V1 = REPO / "phase1" / "critic_scaling_confirmation_contract_v1.json"
CONTRACT_V2 = REPO / "phase1" / "critic_scaling_confirmation_contract_v2.json"


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def make_lock(path: Path, contract_path: Path, contract: dict) -> Path:
    runs = []
    for size in contract["matrix"]["model_sizes_b"]:
        for seed in contract["matrix"]["seeds"]:
            runs.append(
                {
                    "model_size_b": size,
                    "seed": seed,
                    "base_model": f"Qwen/Qwen3-{float(size):g}B-Base",
                    "model_revision": "a" * 40,
                    "checkpoint_manifest_sha256": (
                        f"{int(round(float(size) * 10)):02x}{int(seed):02x}" * 16
                    )[:64],
                    "checkpoint_locked_before_test_access": True,
                    "training_status": "COMPLETE",
                    "selected_on_dev_only": True,
                    "checkpoint_step": 10,
                    "dev_selection_metric": 0.5,
                }
            )
    lock = {
        "protocol": "critic-scaling-confirmation-lock-v1",
        "status": "LOCKED_BEFORE_TEST_ACCESS",
        "contract_sha256": analysis.sha256_file(contract_path),
        "source_commit": "b" * 40,
        "frozen_at_utc": "2026-09-02T00:00:00Z",
        "source_provenance": {
            "canonical_config_v2_sidecar_coverage": 1.0,
            "canonical_config_v2_sidecar_manifest_sha256": "c" * 64,
            "stable_public_generator_release_id": "future-generator-release-v1",
            "exact_generator_config_stratum_id": "future-exact-stratum-v1",
            "sidecars_written_before_outcome": True,
            "historical_backfill_used": False,
        },
        "dataset": {
            "split": "test",
            "truth_sha256": "d" * 64,
            "truth_rows": 300,
        },
        "baseline": {
            "id": "char_tfidf_lr",
            "fit_scope": "train_only",
            "receipt_sha256": "e" * 64,
        },
        "runs": runs,
    }
    path.write_text(json.dumps(lock, sort_keys=True), encoding="utf-8")
    return path


def test_v2_frozen_matrix_and_zero_authorization() -> None:
    contract = read(CONTRACT_V2)
    assert analysis.sha256_file(CONTRACT_V2) == verifier.EXPECTED_CONTRACT_V2_SHA256
    assert contract["protocol"] == "critic-scaling-confirmation-contract-v2"
    assert contract["matrix"]["model_sizes_b"] == [0.6, 4.0, 8.0]
    assert contract["matrix"]["seeds"] == [6, 7]
    assert contract["matrix"]["training_runs"] == 6
    assert contract["producer_provenance"]["canonical_config_v2_sidecar_required"] is True
    assert contract["producer_provenance"]["historical_archive_backfill_action"] == "forbidden"
    assert contract["access_and_compute"] == {
        "gpu_jobs_authorized": 0,
        "api_calls_authorized": 0,
        "model_fits_authorized": 0,
        "base_llm_updates_authorized": 0,
        "future_truth_reads_authorized": False,
        "long_experiment_requires_new_budget_approval": True,
    }
    analysis.validate_contract(contract)


def test_v1_remains_supported_without_mutation() -> None:
    contract = read(CONTRACT_V1)
    assert analysis.sha256_file(CONTRACT_V1) == verifier.EXPECTED_CONTRACT_SHA256
    assert contract["matrix"]["model_sizes_b"] == [0.6, 1.7, 4.0, 8.0]
    analysis.validate_contract(contract)


def test_independent_verifier_accepts_exact_v2_six_run_lock(tmp_path: Path) -> None:
    contract = read(CONTRACT_V2)
    lock_path = make_lock(tmp_path / "lock.json", CONTRACT_V2, contract)
    lock = read(lock_path)
    assert set(analysis.validate_lock(lock, contract, analysis.sha256_file(CONTRACT_V2))) == {
        (size, seed) for size in (0.6, 4.0, 8.0) for seed in (6, 7)
    }
    verified_contract, _, indexed = verifier.verify_contract_and_lock(CONTRACT_V2, lock_path)
    assert verified_contract["protocol"] == "critic-scaling-confirmation-contract-v2"
    assert set(indexed) == {
        (size, seed) for size in (0.6, 4.0, 8.0) for seed in (6, 7)
    }


def test_v2_rejects_legacy_extra_size_and_modified_contract(tmp_path: Path) -> None:
    contract = read(CONTRACT_V2)
    altered = copy.deepcopy(contract)
    altered["matrix"]["model_sizes_b"] = [0.6, 1.7, 4.0, 8.0]
    with pytest.raises(analysis.ConfirmationError, match="matrix differs"):
        analysis.validate_contract(altered)

    modified_contract = copy.deepcopy(contract)
    modified_contract["scientific_scope"]["paper_role"] = "tampered"
    altered_path = tmp_path / "altered-contract.json"
    altered_path.write_text(json.dumps(modified_contract, indent=2) + "\n", encoding="utf-8")
    lock_path = make_lock(tmp_path / "lock.json", altered_path, contract)
    with pytest.raises(verifier.VerificationError, match="not a frozen supported version"):
        verifier.verify_contract_and_lock(altered_path, lock_path)


def test_v2_missing_or_backfilled_source_provenance_fails_both_paths(tmp_path: Path) -> None:
    contract = read(CONTRACT_V2)
    lock_path = make_lock(tmp_path / "lock.json", CONTRACT_V2, contract)
    lock = read(lock_path)
    del lock["source_provenance"]
    lock_path.write_text(json.dumps(lock, sort_keys=True), encoding="utf-8")
    with pytest.raises(analysis.ConfirmationError, match="lacks source provenance"):
        analysis.validate_lock(lock, contract, analysis.sha256_file(CONTRACT_V2))
    with pytest.raises(verifier.VerificationError, match="source-provenance fields differ"):
        verifier.verify_contract_and_lock(CONTRACT_V2, lock_path)

    lock_path = make_lock(tmp_path / "backfilled-lock.json", CONTRACT_V2, contract)
    lock = read(lock_path)
    lock["source_provenance"]["historical_backfill_used"] = True
    lock_path.write_text(json.dumps(lock, sort_keys=True), encoding="utf-8")
    with pytest.raises(analysis.ConfirmationError, match="historical backfill"):
        analysis.validate_lock(lock, contract, analysis.sha256_file(CONTRACT_V2))
    with pytest.raises(verifier.VerificationError, match="historical backfill"):
        verifier.verify_contract_and_lock(CONTRACT_V2, lock_path)


def test_v2_added_capacity_gates_are_independently_recomputed() -> None:
    contract = read(CONTRACT_V2)
    contract["inference"]["bootstrap_draws"] = 100
    tasks = [f"task-{index:02d}" for index in range(20)]
    values = {"char_tfidf_lr": 0.50}
    for size, score in ((0.6, 0.55), (4.0, 0.60), (8.0, 0.65)):
        for seed in (6, 7):
            values[analysis.model_key(size, seed)] = score
    metrics = {
        predictor: {"task_macro_accuracy": score}
        for predictor, score in values.items()
    }
    internals = {
        predictor: {
            "per_task": {task: {"accuracy": score} for task in tasks},
            "component_task_gain": {task: score for task in tasks},
        }
        for predictor, score in values.items()
    }
    truth = {
        f"pair-{task_index:02d}-{component_index:02d}": {
            "task": task,
            "pair_semantics": "canonical_raw_sibling",
            "comparison_component_id": f"component-{task_index:02d}-{component_index:02d}",
        }
        for task_index, task in enumerate(tasks)
        for component_index in range(15)
    }
    lock = {
        "source_provenance": {
            "canonical_config_v2_sidecar_coverage": 1.0,
            "canonical_config_v2_sidecar_manifest_sha256": "c" * 64,
            "stable_public_generator_release_id": "future-generator-release-v1",
            "exact_generator_config_stratum_id": "future-exact-stratum-v1",
            "sidecars_written_before_outcome": True,
            "historical_backfill_used": False,
        }
    }
    produced = analysis.comparison_summary(contract, metrics, internals, truth, lock)
    independently_verified = verifier.decision_result(contract, metrics, internals, truth, lock)
    assert produced == independently_verified
    gates = produced["capacity_scaling"]["gates"]
    assert gates["all_leave_one_task_out_high_minus_low_deltas_positive"] is True
    assert gates["dominant_task_deleted_high_minus_low_positive"] is True
    assert produced["capacity_scaling"]["dominant_task"] == "task-00"
    assert produced["support"]["canonical_config_v2_sidecar_coverage"] == 1.0
