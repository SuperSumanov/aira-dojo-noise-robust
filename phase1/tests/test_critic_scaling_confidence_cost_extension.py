from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from phase1 import critic_scaling_confidence_cost_extension as extension
from phase1 import critic_scaling_confirmation_analysis as primary
from phase1 import verify_critic_scaling_confidence_cost_extension as independent
from phase1.tests.test_critic_scaling_confirmation_analysis import (
    artifact,
    make_fixture,
    write_json,
    write_jsonl,
)


REPO = Path(__file__).resolve().parents[2]
PRIMARY_CONTRACT = REPO / "phase1" / "critic_scaling_confirmation_contract_v1.json"
EXTENSION_CONTRACT = REPO / "phase1" / "critic_scaling_confidence_cost_extension_v1.json"


def endpoint_kind(endpoint: str) -> str:
    return endpoint.rsplit("-", 1)[-1]


def endpoint_score(endpoint: str, mode: str, utility: float) -> float:
    if mode == "high":
        return {"best": 10.0, "middle": 0.9, "worst": 1.0}[endpoint_kind(endpoint)]
    if mode == "tie":
        return 0.0
    if mode == "weak":
        return {"best": 0.2, "middle": 0.0, "worst": 0.1}[endpoint_kind(endpoint)]
    if mode == "reverse":
        return -utility
    raise AssertionError(mode)


def prediction_rows(truth: list[dict], mode: str) -> list[dict]:
    output = []
    for row in truth:
        better = endpoint_score(row["better_id"], mode, float(row["better_utility"]))
        worse = endpoint_score(row["worse_id"], mode, float(row["worse_utility"]))
        output.append(
            {
                "pair_id": row["pair_id"],
                "better_score": better,
                "worse_score": worse,
                "margin": better - worse,
            }
        )
    return output


def rewrite_primary_predictions(bundle_path: Path, *, no_primary_scaling: bool = False) -> None:
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    root = bundle_path.parent
    truth = [
        json.loads(line)
        for line in (root / bundle["truth"]["path"]).read_text(encoding="utf-8").splitlines()
    ]

    def rewrite(spec: dict, mode: str) -> None:
        path = root / spec["predictions"]["path"]
        write_jsonl(path, prediction_rows(truth, mode))
        spec["predictions"]["sha256"] = primary.sha256_file(path)
        ledger_path = root / spec["ledger"]["path"]
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        ledger["prediction_sha256"] = spec["predictions"]["sha256"]
        write_json(ledger_path, ledger)
        spec["ledger"]["sha256"] = primary.sha256_file(ledger_path)

    rewrite(bundle["baseline"], "reverse")
    mode_by_size = (
        {0.6: "weak", 1.7: "weak", 4.0: "weak", 8.0: "high"}
        if no_primary_scaling
        else {0.6: "reverse", 1.7: "tie", 4.0: "tie", 8.0: "high"}
    )
    for spec in bundle["runs"]:
        rewrite(spec, mode_by_size[float(spec["model_size_b"])])
    write_json(bundle_path, bundle)


def make_extension_fixture(
    tmp_path: Path, *, primary_support: bool = True
) -> tuple[Path, Path, Path, Path, Path]:
    primary_contract_path, primary_lock_path, primary_bundle_path = make_fixture(
        tmp_path / "primary", strong=True, compact_contract=True
    )
    rewrite_primary_predictions(primary_bundle_path, no_primary_scaling=not primary_support)
    extension_value = json.loads(EXTENSION_CONTRACT.read_text(encoding="utf-8"))
    extension_value["binding"]["primary_contract_sha256"] = primary.sha256_file(primary_contract_path)
    extension_value["calibration_lock"]["minimum_dev_pairs"] = 2
    extension_value["calibration_lock"]["minimum_dev_tasks"] = 2
    extension_value["calibration_lock"]["maximum_dominant_dev_task_pair_share"] = 0.6
    extension_value["metrics"]["bootstrap_draws"] = 200
    # Each synthetic task has only three pairs; 0.5 target rounds to 2/3.
    extension_value["hierarchical_gates"]["selective_confidence"]["realized_coverage_min"] = 0.6
    extension_value["hierarchical_gates"]["selective_confidence"]["realized_coverage_max"] = 0.7
    extension_path = tmp_path / "extension.json"
    write_json(extension_path, extension_value)

    dev_truth: list[dict] = []
    for task_index, task in enumerate(("task-a", "task-b")):
        component = f"dev-component-{task_index}"
        parent = f"dev-parent-{task_index}"
        run = f"dev-run-{task_index}"
        utilities = {
            f"{task}-dev-best": 3.0,
            f"{task}-dev-middle": 2.0,
            f"{task}-dev-worst": 1.0,
        }
        for better, worse in (
            (f"{task}-dev-best", f"{task}-dev-middle"),
            (f"{task}-dev-middle", f"{task}-dev-worst"),
            (f"{task}-dev-best", f"{task}-dev-worst"),
        ):
            row = {
                "split": "dev",
                "task": task,
                "pair_semantics": "canonical_raw_sibling",
                "parent_id": parent,
                "parent_run_id": run,
                "comparison_component_id": component,
                "better_id": better,
                "worse_id": worse,
                "better_run_id": run,
                "worse_run_id": run,
                "better_utility": utilities[better],
                "worse_utility": utilities[worse],
            }
            row["pair_id"] = extension.dev_pair_id(row)
            dev_truth.append(row)
    dev_root = tmp_path / "dev"
    dev_root.mkdir()
    truth_path = dev_root / "truth.jsonl"
    write_jsonl(truth_path, dev_truth)
    primary_lock = json.loads(primary_lock_path.read_text(encoding="utf-8"))

    baseline_path = dev_root / "baseline.jsonl"
    write_jsonl(baseline_path, prediction_rows(dev_truth, "reverse"))
    baseline = {
        "id": "char_tfidf_lr",
        "receipt_sha256": primary_lock["baseline"]["receipt_sha256"],
        "predictions": artifact(baseline_path, len(dev_truth)),
    }
    runs = []
    mode_by_size = (
        {0.6: "weak", 1.7: "weak", 4.0: "weak", 8.0: "high"}
        if not primary_support
        else {0.6: "reverse", 1.7: "tie", 4.0: "tie", 8.0: "high"}
    )
    for row in primary_lock["runs"]:
        predictor = extension.matrix_key(float(row["model_size_b"]), int(row["seed"]))
        path = dev_root / f"{predictor}.jsonl"
        write_jsonl(path, prediction_rows(dev_truth, mode_by_size[float(row["model_size_b"])]))
        runs.append(
            {
                "model_size_b": row["model_size_b"],
                "seed": row["seed"],
                "checkpoint_manifest_sha256": row["checkpoint_manifest_sha256"],
                "predictions": artifact(path, len(dev_truth)),
            }
        )
    calibration_lock = {
        "protocol": extension.CALIBRATION_LOCK_PROTOCOL,
        "status": "LOCKED_BEFORE_TEST_ACCESS",
        "extension_contract_sha256": extension.sha256_file(extension_path),
        "primary_contract_sha256": primary.sha256_file(primary_contract_path),
        "primary_lock_sha256": primary.sha256_file(primary_lock_path),
        "frozen_at_utc": "2026-08-23T00:00:01Z",
        "locked_before_test_access": True,
        "dev_truth": artifact(truth_path, len(dev_truth)),
        "baseline": baseline,
        "runs": runs,
    }
    calibration_lock_path = dev_root / "calibration_lock.json"
    write_json(calibration_lock_path, calibration_lock)
    return (
        primary_contract_path,
        extension_path,
        primary_lock_path,
        calibration_lock_path,
        primary_bundle_path,
    )


def test_frozen_extension_is_no_compute_no_rescue_and_binds_primary() -> None:
    value = json.loads(EXTENSION_CONTRACT.read_text(encoding="utf-8"))
    extension.validate_extension_contract(
        value,
        extension.sha256_file(EXTENSION_CONTRACT),
        primary.sha256_file(PRIMARY_CONTRACT),
    )
    assert extension.sha256_file(EXTENSION_CONTRACT) == independent.EXPECTED_EXTENSION_CONTRACT_SHA256
    assert value["binding"]["secondary_result_may_not_rescue_failed_primary"] is True
    assert value["scientific_scope"]["method_novelty_claimed"] is False
    assert value["selective_execution"]["primary_coverage_target"] == 0.5
    assert value["access_and_compute"]["gpu_jobs_authorized"] == 0
    assert value["access_and_compute"]["future_truth_reads_authorized"] is False


def test_strong_synthetic_extension_passes_proper_score_and_selective_layers(
    tmp_path: Path,
) -> None:
    paths = make_extension_fixture(tmp_path)
    summary, metrics, internals, coverage = extension.analyze(*paths)
    assert summary["status"] == "PRIMARY_CONFIRMED_SECONDARY_CONFIDENCE_COST_AND_BASELINE_PASS"
    assert summary["decision"]["proper_score_scaling"]["pass"] is True
    assert summary["decision"]["selective_confidence"]["pass"] is True
    assert summary["decision"]["high_size_vs_baseline"]["pass"] is True
    assert summary["decision"]["secondary_can_rescue_primary"] is False
    high = metrics["qwen3_8b_seed6"]
    assert high["task_macro_log_loss"] < metrics["qwen3_0.6b_seed6"]["task_macro_log_loss"]
    assert high["coverage"]["0.5"]["task_macro_accepted_error"] == 0.0
    assert len(internals) == 9
    assert len(coverage) == 36


def test_positive_secondary_cannot_rescue_primary_support_failure(tmp_path: Path) -> None:
    paths = make_extension_fixture(tmp_path, primary_support=False)
    summary, *_ = extension.analyze(*paths)
    assert summary["status"] == "SECONDARY_SIGNAL_PRESENT_PRIMARY_NOT_RESCUED"
    assert summary["decision"]["primary_clean_scaling_confirmed"] is False
    assert summary["decision"]["secondary_can_rescue_primary"] is False


def test_dev_test_endpoint_overlap_and_late_lock_fail_closed(tmp_path: Path) -> None:
    paths = make_extension_fixture(tmp_path / "overlap")
    calibration_path = paths[3]
    calibration = json.loads(calibration_path.read_text(encoding="utf-8"))
    truth_path = calibration_path.parent / calibration["dev_truth"]["path"]
    dev_rows = [json.loads(line) for line in truth_path.read_text(encoding="utf-8").splitlines()]
    primary_bundle = json.loads(paths[4].read_text(encoding="utf-8"))
    test_truth_path = paths[4].parent / primary_bundle["truth"]["path"]
    test_row = json.loads(test_truth_path.read_text(encoding="utf-8").splitlines()[0])
    dev_rows[0]["better_id"] = test_row["better_id"]
    dev_rows[0]["pair_id"] = extension.dev_pair_id(dev_rows[0])
    old_pair_id = json.loads(truth_path.read_text(encoding="utf-8").splitlines()[0])["pair_id"]
    new_pair_id = dev_rows[0]["pair_id"]
    write_jsonl(truth_path, dev_rows)
    calibration["dev_truth"] = artifact(truth_path, len(dev_rows))
    for spec in [calibration["baseline"], *calibration["runs"]]:
        prediction_path = calibration_path.parent / spec["predictions"]["path"]
        prediction_rows_value = [
            json.loads(line) for line in prediction_path.read_text(encoding="utf-8").splitlines()
        ]
        for row in prediction_rows_value:
            if row["pair_id"] == old_pair_id:
                row["pair_id"] = new_pair_id
        write_jsonl(prediction_path, prediction_rows_value)
        spec["predictions"] = artifact(prediction_path, len(prediction_rows_value))
    write_json(calibration_path, calibration)
    with pytest.raises(extension.ConfidenceCostError, match="identity overlap"):
        extension.analyze(*paths)

    paths = make_extension_fixture(tmp_path / "late")
    calibration = json.loads(paths[3].read_text(encoding="utf-8"))
    calibration["locked_before_test_access"] = False
    write_json(paths[3], calibration)
    with pytest.raises(extension.ConfidenceCostError, match="not frozen before test"):
        extension.analyze(*paths)


def test_calibration_lock_checkpoint_and_matrix_attacks_fail_closed(tmp_path: Path) -> None:
    paths = make_extension_fixture(tmp_path)
    calibration = json.loads(paths[3].read_text(encoding="utf-8"))
    calibration["runs"][0]["checkpoint_manifest_sha256"] = "f" * 64
    write_json(paths[3], calibration)
    with pytest.raises(extension.ConfidenceCostError, match="checkpoint differs"):
        extension.analyze(*paths)

    paths = make_extension_fixture(tmp_path / "missing")
    calibration = json.loads(paths[3].read_text(encoding="utf-8"))
    calibration["runs"].pop()
    write_json(paths[3], calibration)
    with pytest.raises(extension.ConfidenceCostError, match="matrix is incomplete"):
        extension.analyze(*paths)


def test_cli_outputs_are_hash_seed_independent(tmp_path: Path) -> None:
    paths = make_extension_fixture(tmp_path / "input")
    outputs = []
    for hash_seed in ("17", "43"):
        out_dir = tmp_path / f"out-{hash_seed}"
        environment = dict(os.environ)
        environment["PYTHONHASHSEED"] = hash_seed
        subprocess.run(
            [
                sys.executable,
                "-m",
                "phase1.critic_scaling_confidence_cost_extension",
                "--primary-contract", str(paths[0]),
                "--extension-contract", str(paths[1]),
                "--primary-lock", str(paths[2]),
                "--calibration-lock", str(paths[3]),
                "--primary-bundle", str(paths[4]),
                "--out-dir", str(out_dir),
            ],
            cwd=REPO,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )
        outputs.append({path.name: path.read_bytes() for path in out_dir.iterdir()})
    assert outputs[0] == outputs[1]


def test_independent_verifier_rebuilds_source_and_rejects_derived_tamper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = make_extension_fixture(tmp_path / "input")
    summary, _, internals, coverage = extension.analyze(*paths)
    result_dir = tmp_path / "result"
    extension.write_outputs(result_dir, summary, internals, coverage)
    monkeypatch.setattr(
        independent,
        "EXPECTED_EXTENSION_CONTRACT_SHA256",
        extension.sha256_file(paths[1]),
    )
    receipt = independent.verify(*paths, result_dir)
    assert receipt["status"] == "INDEPENDENT_VERIFICATION_PASS"
    assert receipt["predictors"] == 9
    verifier_source = Path(independent.__file__).read_text(encoding="utf-8")
    assert "import critic_scaling_confidence_cost_extension" not in verifier_source

    released = json.loads((result_dir / "summary.json").read_text(encoding="utf-8"))
    released["predictors"]["qwen3_8b_seed6"]["task_macro_log_loss"] += 0.1
    write_json(result_dir / "summary.json", released)
    manifest_path = result_dir / "artifact_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    summary_path = result_dir / "summary.json"
    manifest["summary.json"] = {
        "bytes": summary_path.stat().st_size,
        "sha256": primary.sha256_file(summary_path),
    }
    write_json(manifest_path, manifest)
    with pytest.raises(independent.VerificationError, match="numeric value differs"):
        independent.verify(*paths, result_dir)
