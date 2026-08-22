from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from phase1 import critic_scaling_confirmation_analysis as analysis
from phase1 import verify_critic_scaling_confirmation_analysis as verifier


REPO = Path(__file__).resolve().parents[2]
FROZEN_CONTRACT = REPO / "phase1" / "critic_scaling_confirmation_contract_v1.json"


def write_json(path: Path, value: object) -> None:
    path.write_bytes(analysis.canonical_bytes(value))


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


def artifact(path: Path, rows: int) -> dict:
    return {"path": path.name, "sha256": analysis.sha256_file(path), "rows": rows}


def make_fixture(
    tmp_path: Path, *, strong: bool = True, compact_contract: bool = True
) -> tuple[Path, Path, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    contract = json.loads(FROZEN_CONTRACT.read_text(encoding="utf-8"))
    if compact_contract:
        contract["cohort"]["minimum_primary_tasks"] = 2
        contract["cohort"]["minimum_primary_components"] = 2
        contract["cohort"]["maximum_dominant_task_pair_share"] = 0.6
        contract["inference"]["bootstrap_draws"] = 200
    contract_path = tmp_path / "contract.json"
    write_json(contract_path, contract)

    truth: list[dict] = []
    for task_index, task in enumerate(("task-a", "task-b")):
        component = f"component-{task_index}"
        parent = f"parent-{task_index}"
        run = f"run-{task_index}"
        endpoint_utilities = {
            f"{task}-best": 3.0,
            f"{task}-middle": 2.0,
            f"{task}-worst": 1.0,
        }
        for better, worse in (
            (f"{task}-best", f"{task}-middle"),
            (f"{task}-middle", f"{task}-worst"),
            (f"{task}-best", f"{task}-worst"),
        ):
            row = {
                "split": "test",
                "task": task,
                "pair_semantics": "canonical_raw_sibling",
                "parent_id": parent,
                "parent_run_id": run,
                "comparison_component_id": component,
                "better_id": better,
                "worse_id": worse,
                "better_run_id": run,
                "worse_run_id": run,
                "better_utility": endpoint_utilities[better],
                "worse_utility": endpoint_utilities[worse],
            }
            row["pair_id"] = analysis.pair_id(row)
            truth.append(row)
    truth_path = tmp_path / "truth.jsonl"
    write_jsonl(truth_path, truth)

    checkpoint_hashes: dict[tuple[float, int], str] = {}
    runs = []
    for index, (size, seed) in enumerate(analysis.expected_matrix(contract), 1):
        checkpoint_hash = hashlib_hex(index)
        checkpoint_hashes[(size, seed)] = checkpoint_hash
        runs.append(
            {
                "model_size_b": size,
                "seed": seed,
                "base_model": f"Qwen/Qwen3-{size:g}B-Base",
                "model_revision": f"{index:040x}",
                "checkpoint_manifest_sha256": checkpoint_hash,
                "checkpoint_locked_before_test_access": True,
                "training_status": "COMPLETE",
                "selected_on_dev_only": True,
                "checkpoint_step": 10,
                "dev_selection_metric": 0.75,
            }
        )
    lock = {
        "protocol": analysis.LOCK_PROTOCOL,
        "status": "LOCKED_BEFORE_TEST_ACCESS",
        "contract_sha256": analysis.sha256_file(contract_path),
        "source_commit": "1" * 40,
        "frozen_at_utc": "2026-08-23T00:00:00Z",
        "dataset": {
            "split": "test",
            "truth_sha256": analysis.sha256_file(truth_path),
            "truth_rows": len(truth),
        },
        "baseline": {
            "id": "char_tfidf_lr",
            "fit_scope": "train_only",
            "receipt_sha256": "2" * 64,
        },
        "runs": runs,
    }
    lock_path = tmp_path / "lock.json"
    write_json(lock_path, lock)
    lock_sha = analysis.sha256_file(lock_path)

    utility_by_endpoint = {
        endpoint: utility
        for row in truth
        for endpoint, utility in (
            (row["better_id"], row["better_utility"]),
            (row["worse_id"], row["worse_utility"]),
        )
    }

    def prediction_rows(multiplier: float) -> list[dict]:
        output = []
        for row in truth:
            better_score = multiplier * utility_by_endpoint[row["better_id"]]
            worse_score = multiplier * utility_by_endpoint[row["worse_id"]]
            output.append(
                {
                    "pair_id": row["pair_id"],
                    "better_score": better_score,
                    "worse_score": worse_score,
                    "margin": better_score - worse_score,
                }
            )
        return output

    def make_ledger(
        name: str, prediction_path: Path, checkpoint_hash: str | None
    ) -> tuple[Path, str]:
        prediction_sha = analysis.sha256_file(prediction_path)
        ledger = {
            "status": "COMPLETE",
            "test_attempts": 1,
            "lock_sha256": lock_sha,
            "truth_sha256": analysis.sha256_file(truth_path),
            "prediction_sha256": prediction_sha,
        }
        if checkpoint_hash is not None:
            ledger["checkpoint_manifest_sha256"] = checkpoint_hash
        ledger_path = tmp_path / f"{name}.ledger.json"
        write_json(ledger_path, ledger)
        return ledger_path, prediction_sha

    baseline_path = tmp_path / "baseline.jsonl"
    write_jsonl(baseline_path, prediction_rows(-1.0 if strong else 1.0))
    baseline_ledger, _ = make_ledger("baseline", baseline_path, None)
    bundle_runs = []
    multiplier_by_size = {0.6: -1.0, 1.7: 0.0, 4.0: 1.0, 8.0: 2.0}
    for size, seed in analysis.expected_matrix(contract):
        multiplier = multiplier_by_size[size] if strong else -1.0
        name = analysis.model_key(size, seed)
        prediction_path = tmp_path / f"{name}.jsonl"
        write_jsonl(prediction_path, prediction_rows(multiplier))
        ledger_path, _ = make_ledger(name, prediction_path, checkpoint_hashes[(size, seed)])
        bundle_runs.append(
            {
                "model_size_b": size,
                "seed": seed,
                "checkpoint_manifest_sha256": checkpoint_hashes[(size, seed)],
                "predictions": artifact(prediction_path, len(truth)),
                "ledger": {"path": ledger_path.name, "sha256": analysis.sha256_file(ledger_path)},
            }
        )
    bundle = {
        "protocol": analysis.BUNDLE_PROTOCOL,
        "status": "COMPLETE",
        "lock_sha256": lock_sha,
        "truth": artifact(truth_path, len(truth)),
        "baseline": {
            "id": "char_tfidf_lr",
            "receipt_sha256": "2" * 64,
            "predictions": artifact(baseline_path, len(truth)),
            "ledger": {
                "path": baseline_ledger.name,
                "sha256": analysis.sha256_file(baseline_ledger),
            },
        },
        "runs": bundle_runs,
    }
    bundle_path = tmp_path / "bundle.json"
    write_json(bundle_path, bundle)
    return contract_path, lock_path, bundle_path


def hashlib_hex(index: int) -> str:
    return f"{index:064x}"


def test_frozen_contract_never_authorizes_compute_or_historical_checkpoints() -> None:
    contract = json.loads(FROZEN_CONTRACT.read_text(encoding="utf-8"))
    analysis.validate_contract(contract)
    assert analysis.sha256_file(FROZEN_CONTRACT) == verifier.EXPECTED_CONTRACT_SHA256
    assert contract["matrix"]["model_sizes_b"] == [0.6, 1.7, 4.0, 8.0]
    assert contract["matrix"]["seeds"] == [6, 7]
    assert contract["scientific_scope"]["historical_test_touched_checkpoints_allowed"] is False
    assert contract["access_and_compute"]["gpu_jobs_authorized"] == 0
    assert contract["access_and_compute"]["future_truth_reads_authorized"] is False
    verifier_source = Path(verifier.__file__).read_text(encoding="utf-8")
    assert "import critic_scaling_confirmation_analysis" not in verifier_source


def test_strong_synthetic_bundle_passes_all_three_effect_layers(tmp_path: Path) -> None:
    contract, lock, bundle = make_fixture(tmp_path)
    summary, metrics, components, internals = analysis.analyze(contract, lock, bundle)
    assert summary["status"] == "STRONG_CLEAN_SCALING_BASELINE_AND_UTILITY_PASS"
    assert summary["decision"]["support"]["pass"] is True
    assert summary["decision"]["capacity_scaling"]["pass"] is True
    assert summary["decision"]["high_size_vs_baseline"]["pass"] is True
    assert summary["decision"]["utility_conversion"]["pass"] is True
    assert metrics["qwen3_8b_seed6"]["task_macro_accuracy"] == 1.0
    assert len(components["qwen3_8b_seed6"]) == 2
    assert set(internals["char_tfidf_lr"]["per_task"]) == {"task-a", "task-b"}


def test_negative_synthetic_bundle_is_valid_but_does_not_confirm(tmp_path: Path) -> None:
    contract, lock, bundle = make_fixture(tmp_path, strong=False)
    summary, *_ = analysis.analyze(contract, lock, bundle)
    assert summary["status"] == "VALID_NO_CLEAN_SCALING_CONFIRMATION"
    assert summary["decision"]["capacity_scaling"]["pass"] is False


def test_margin_tamper_and_second_test_attempt_fail_closed(tmp_path: Path) -> None:
    contract, lock, bundle_path = make_fixture(tmp_path)
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    run = bundle["runs"][0]
    prediction_path = tmp_path / run["predictions"]["path"]
    rows = [json.loads(line) for line in prediction_path.read_text(encoding="utf-8").splitlines()]
    rows[0]["margin"] += 1.0
    write_jsonl(prediction_path, rows)
    run["predictions"]["sha256"] = analysis.sha256_file(prediction_path)
    ledger_path = tmp_path / run["ledger"]["path"]
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    ledger["prediction_sha256"] = run["predictions"]["sha256"]
    write_json(ledger_path, ledger)
    run["ledger"]["sha256"] = analysis.sha256_file(ledger_path)
    write_json(bundle_path, bundle)
    with pytest.raises(analysis.ConfirmationError, match="margin disagrees"):
        analysis.analyze(contract, lock, bundle_path)

    contract, lock, bundle_path = make_fixture(tmp_path / "attempt")
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    ledger_path = bundle_path.parent / bundle["runs"][0]["ledger"]["path"]
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    ledger["test_attempts"] = 2
    write_json(ledger_path, ledger)
    bundle["runs"][0]["ledger"]["sha256"] = analysis.sha256_file(ledger_path)
    write_json(bundle_path, bundle)
    with pytest.raises(analysis.ConfirmationError, match="test_attempts"):
        analysis.analyze(contract, lock, bundle_path)


def test_missing_run_and_cross_run_primary_fail_closed(tmp_path: Path) -> None:
    contract, lock, bundle_path = make_fixture(tmp_path)
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    bundle["runs"].pop()
    write_json(bundle_path, bundle)
    with pytest.raises(analysis.ConfirmationError, match="matrix is incomplete"):
        analysis.analyze(contract, lock, bundle_path)

    contract, _, bundle_path = make_fixture(tmp_path / "cross-run")
    contract_value = json.loads(contract.read_text(encoding="utf-8"))
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    truth_path = bundle_path.parent / bundle["truth"]["path"]
    rows = [json.loads(line) for line in truth_path.read_text(encoding="utf-8").splitlines()]
    rows[0]["worse_run_id"] = "foreign-run"
    with pytest.raises(analysis.ConfirmationError, match="crosses physical runs"):
        analysis.validate_truth(rows, contract_value)


def test_cli_outputs_are_hash_seed_independent(tmp_path: Path) -> None:
    contract, lock, bundle = make_fixture(tmp_path / "input")
    outputs = []
    for hash_seed in ("11", "29"):
        out_dir = tmp_path / f"out-{hash_seed}"
        environment = dict(os.environ)
        environment["PYTHONHASHSEED"] = hash_seed
        subprocess.run(
            [
                sys.executable,
                "-m",
                "phase1.critic_scaling_confirmation_analysis",
                "--contract", str(contract),
                "--lock", str(lock),
                "--bundle", str(bundle),
                "--out-dir", str(out_dir),
            ],
            cwd=REPO,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )
        outputs.append(
            {
                path.name: path.read_bytes()
                for path in out_dir.iterdir()
                if path.is_file()
            }
        )
    assert outputs[0] == outputs[1]


def test_independent_verifier_rebuilds_release_and_rejects_tamper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    contract, lock, bundle = make_fixture(tmp_path / "input", compact_contract=False)
    summary, metrics, components, internals = analysis.analyze(contract, lock, bundle)
    result_dir = tmp_path / "result"
    analysis.write_outputs(result_dir, summary, metrics, components, internals)
    monkeypatch.setattr(verifier, "EXPECTED_CONTRACT_SHA256", analysis.sha256_file(contract))
    receipt = verifier.verify(contract, lock, bundle, result_dir)
    assert receipt["status"] == "INDEPENDENT_VERIFICATION_PASS"
    assert receipt["analysis_status"] == "VALID_NO_CLEAN_SCALING_CONFIRMATION"
    assert receipt["predictors"] == 9

    released = json.loads((result_dir / "summary.json").read_text(encoding="utf-8"))
    released["decision"]["capacity_scaling"]["high_minus_low_task_macro_delta"] = 0.0
    write_json(result_dir / "summary.json", released)
    with pytest.raises(verifier.VerificationError, match="numeric value differs"):
        verifier.verify(contract, lock, bundle, result_dir)
