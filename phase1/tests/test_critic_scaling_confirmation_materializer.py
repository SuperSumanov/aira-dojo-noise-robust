from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

import pytest

from phase1 import critic_scaling_confirmation_analysis as analysis
from phase1 import critic_scaling_confirmation_materializer as materializer


REPO = Path(__file__).resolve().parents[2]
CONTRACT = REPO / "phase1" / "critic_scaling_confirmation_contract_v1.json"
REMOTE_RECEIPT = (
    REPO
    / "phase1"
    / "results"
    / "critic_scaling_materializer_20260823_81a09d5"
    / "verification_receipt.json"
)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(materializer.canonical_bytes(value))


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(materializer.compact_line(row) for row in rows), encoding="utf-8")


def card(card_id: str, task: str, parent: str | None, grade: float | None) -> dict:
    return {
        "id": card_id,
        "task": {"name": task},
        "lineage": {"parent_id": parent},
        "label": None if grade is None else {"graded": grade},
        "code": "pass",
    }


def pair(task: str, parent: str, better: str, worse: str, run: str) -> dict:
    return {
        "task": task,
        "better": better,
        "worse": worse,
        "parent": parent,
        "intask_split": "test",
        "pair_semantics": "canonical_raw_sibling",
        "endpoint_run_ids": [run, run],
        "parent_run_id": run,
        "budget": 0,
    }


def truth_fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path, list[dict]]:
    cards = {
        "run-a": [
            card("pa", "task-a", None, None),
            card("a", "task-a", "pa", 5.0),
            card("b", "task-a", "pa", 4.0),
            card("c", "task-a", "pa", 3.0),
            card("d", "task-a", "pa", 2.0),
            card("e", "task-a", "pa", 1.0),
        ],
        "run-b": [
            card("pb", "task-b", None, None),
            card("x", "task-b", "pb", 0.1),
            card("y", "task-b", "pb", 0.2),
        ],
    }
    pairs = [
        pair("task-a", "pa", "a", "b", "run-a"),
        pair("task-a", "pa", "b", "c", "run-a"),
        pair("task-a", "pa", "d", "e", "run-a"),
        pair("task-b", "pb", "x", "y", "run-b"),
    ]
    cards_path = tmp_path / "cards.json"
    pairs_path = tmp_path / "pairs.jsonl"
    truth_path = tmp_path / "truth.jsonl"
    receipt_path = tmp_path / "truth.receipt.json"
    write_json(cards_path, cards)
    write_jsonl(pairs_path, pairs)
    return cards_path, pairs_path, truth_path, receipt_path, pairs


def truth_args(
    cards: Path, pairs: Path, truth: Path, receipt: Path
) -> argparse.Namespace:
    return argparse.Namespace(
        pairs=pairs,
        cards=cards,
        expected_pairs_sha256=materializer.sha256_file(pairs),
        expected_cards_sha256=materializer.sha256_file(cards),
        source_commit="a" * 40,
        output=truth,
        receipt=receipt,
    )


def materialized_truth(tmp_path: Path) -> tuple[Path, Path, Path, list[dict]]:
    cards, pairs, truth, receipt, source_pairs = truth_fixture(tmp_path)
    assert materializer.materialize_truth(truth_args(cards, pairs, truth, receipt)) == 0
    return truth, cards, pairs, source_pairs


def test_truth_materialization_is_deterministic_and_preserves_maximal_components(
    tmp_path: Path,
) -> None:
    truth, cards, pairs, source_pairs = materialized_truth(tmp_path / "first")
    rows = materializer.read_jsonl(truth, "truth")
    validated, components = analysis.validate_truth(
        rows, json.loads(CONTRACT.read_text(encoding="utf-8"))
    )
    assert len(validated) == 4
    assert len(components) == 3
    assert all(row["pair_id"] == analysis.pair_id(row) for row in rows)
    lower = next(row for row in rows if row["task"] == "task-b")
    assert lower["better_utility"] == -0.1
    assert lower["worse_utility"] == -0.2

    second = tmp_path / "second"
    second.mkdir()
    second_cards = second / "cards.json"
    second_pairs = second / "pairs.jsonl"
    second_truth = second / "truth.jsonl"
    second_receipt = second / "receipt.json"
    second_cards.write_bytes(cards.read_bytes())
    write_jsonl(second_pairs, list(reversed(source_pairs)))
    assert materializer.materialize_truth(
        truth_args(second_cards, second_pairs, second_truth, second_receipt)
    ) == 0
    assert second_truth.read_bytes() == truth.read_bytes()


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda rows: rows[0].update(intask_split="train"), "dedicated test"),
        (lambda rows: rows[0].update(pair_semantics="synthetic_cross_run_draft"), "canonical"),
        (lambda rows: rows[0].update(endpoint_run_ids=["wrong", "run-a"]), "run receipt"),
        (lambda rows: rows.append({**rows[0], "better": "b", "worse": "a"}), "duplicate"),
        (lambda rows: rows[1].update(better="c", worse="b"), "inconsistent grade direction"),
        (lambda rows: rows[1].update(budget=1), "exactly one budget"),
    ],
)
def test_truth_materialization_rejects_structural_or_orientation_corruption(
    tmp_path: Path, mutation, message: str
) -> None:
    cards, pairs, truth, receipt, rows = truth_fixture(tmp_path)
    mutation(rows)
    write_jsonl(pairs, rows)
    with pytest.raises(materializer.MaterializationError, match=message):
        materializer.materialize_truth(truth_args(cards, pairs, truth, receipt))
    assert not truth.exists()


def test_truth_materialization_refuses_credential_shaped_cards(tmp_path: Path) -> None:
    cards, pairs, truth, receipt, _ = truth_fixture(tmp_path)
    value = json.loads(cards.read_text(encoding="utf-8"))
    value["run-a"][0]["code"] = "sk-" + "A" * 32
    write_json(cards, value)
    with pytest.raises(materializer.MaterializationError, match="credential-shaped"):
        materializer.materialize_truth(truth_args(cards, pairs, truth, receipt))
    assert not truth.exists()


def make_lock(
    tmp_path: Path, truth: Path, cards: Path, pairs: Path
) -> tuple[Path, dict[tuple[float, int], dict[str, Path]]]:
    contract_sha = materializer.sha256_file(CONTRACT)
    runs = []
    assets: dict[tuple[float, int], dict[str, Path]] = {}
    for index, (size, seed) in enumerate(
        ((size, seed) for size in (0.6, 1.7, 4.0, 8.0) for seed in (6, 7)), 1
    ):
        name = f"qwen3-{str(size).replace('.', 'p')}b-seed{seed}"
        checkpoint_manifest = tmp_path / "checkpoints" / name / "manifest.json"
        output_path = tmp_path / f"{name}.one-shot-output.json"
        ledger_path = tmp_path / f"{name}.one-shot-ledger.json"
        manifest_value = {
            "protocol": materializer.CHECKPOINT_MANIFEST_PROTOCOL,
            "status": "LOCKED_BEFORE_TEST_ACCESS",
            "model_size_b": size,
            "seed": seed,
            "artifacts": {
                "model.safetensors": f"{index + 100:064x}",
                "rm_meta.json": f"{index + 200:064x}",
            },
        }
        write_json(checkpoint_manifest, manifest_value)
        assets[(size, seed)] = {
            "manifest": checkpoint_manifest,
            "output": output_path,
            "ledger": ledger_path,
        }
        runs.append(
            {
                "model_size_b": size,
                "seed": seed,
                "base_model": f"Qwen/Qwen3-{size:g}B-Base",
                "model_revision": f"{index:040x}",
                "checkpoint_manifest_sha256": materializer.sha256_file(checkpoint_manifest),
                "one_shot_output_path_sha256": materializer.path_identity(output_path),
                "one_shot_ledger_path_sha256": materializer.path_identity(ledger_path),
                "checkpoint_locked_before_test_access": True,
                "training_status": "COMPLETE",
                "selected_on_dev_only": True,
                "checkpoint_step": 10,
                "dev_selection_metric": 0.7,
            }
        )
    lock = {
        "protocol": materializer.LOCK_PROTOCOL,
        "status": "LOCKED_BEFORE_TEST_ACCESS",
        "contract_sha256": contract_sha,
        "source_commit": "b" * 40,
        "frozen_at_utc": "2026-08-23T00:00:00Z",
        "dataset": {
            "split": "test",
            "truth_sha256": materializer.sha256_file(truth),
            "truth_rows": len(materializer.read_jsonl(truth, "truth")),
            "pairs_sha256": materializer.sha256_file(pairs),
            "cards_sha256": materializer.sha256_file(cards),
        },
        "baseline": {
            "id": "char_tfidf_lr",
            "fit_scope": "train_only",
            "receipt_sha256": "f" * 64,
        },
        "runs": runs,
    }
    path = tmp_path / "lock.json"
    write_json(path, lock)
    return path, assets


def one_shot_fixture(
    tmp_path: Path,
    truth: Path,
    lock: Path,
    asset: dict[str, Path],
    *,
    inconsistent_endpoint: bool = False,
) -> tuple[argparse.Namespace, list[dict]]:
    truth_rows = materializer.read_jsonl(truth, "truth")
    scores = {
        endpoint: utility
        for row in truth_rows
        for endpoint, utility in (
            (row["better_id"], row["better_utility"]),
            (row["worse_id"], row["worse_utility"]),
        )
    }
    predictions = []
    for index, row in enumerate(reversed(truth_rows)):
        better_score = scores[row["better_id"]]
        worse_score = scores[row["worse_id"]]
        if inconsistent_endpoint and index == 1:
            better_score += 0.25
        predictions.append(
            {
                "pair_index": index,
                "task": row["task"],
                "pair_semantics": row["pair_semantics"],
                "parent": row["parent_id"],
                "parent_run_id": row["parent_run_id"],
                "better": row["better_id"],
                "worse": row["worse_id"],
                "endpoint_run_ids": [row["better_run_id"], row["worse_run_id"]],
                "better_score": better_score,
                "worse_score": worse_score,
                "margin": better_score - worse_score,
            }
        )
    lock_value = json.loads(lock.read_text(encoding="utf-8"))
    checkpoint_manifest = json.loads(asset["manifest"].read_text(encoding="utf-8"))
    artifacts = {
        "pairs": lock_value["dataset"]["pairs_sha256"],
        "cards": lock_value["dataset"]["cards_sha256"],
        **checkpoint_manifest["artifacts"],
    }
    output_value = {
        "protocol": materializer.ONE_SHOT_PROTOCOL,
        "split": "test",
        "n_pairs": len(predictions),
        "accuracy": 1.0,
        "artifacts": artifacts,
        "pair_predictions": predictions,
    }
    source_output = asset["output"]
    source_ledger = asset["ledger"]
    write_json(source_output, output_value)
    write_json(
        source_ledger,
        {
            "protocol": materializer.ONE_SHOT_PROTOCOL,
            "status": "COMPLETE",
            "expected_artifacts": artifacts,
            "observed_artifacts": artifacts,
            "output": str(source_output.resolve()),
            "result": {
                "n_pairs": len(predictions),
                "accuracy": 1.0,
                "output_sha256": materializer.sha256_file(source_output),
            },
        },
    )
    normalized = tmp_path / "normalized.jsonl"
    derived_ledger = tmp_path / "derived-ledger.json"
    args = argparse.Namespace(
        truth=truth,
        expected_truth_sha256=materializer.sha256_file(truth),
        lock=lock,
        expected_lock_sha256=materializer.sha256_file(lock),
        one_shot_output=source_output,
        expected_one_shot_output_sha256=materializer.sha256_file(source_output),
        one_shot_ledger=source_ledger,
        expected_one_shot_ledger_sha256=materializer.sha256_file(source_ledger),
        checkpoint_manifest=asset["manifest"],
        checkpoint_manifest_sha256=materializer.sha256_file(asset["manifest"]),
        output=normalized,
        ledger=derived_ledger,
    )
    return args, truth_rows


def test_model_prediction_normalization_binds_one_shot_receipt_and_exact_pool(
    tmp_path: Path,
) -> None:
    truth, cards, pairs, _ = materialized_truth(tmp_path)
    lock, assets = make_lock(tmp_path, truth, cards, pairs)
    args, truth_rows = one_shot_fixture(tmp_path, truth, lock, assets[(0.6, 6)])
    assert materializer.normalize_model_prediction(args) == 0
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    truth_index, _ = analysis.validate_truth(truth_rows, contract)
    normalized = materializer.read_jsonl(args.output, "normalized")
    analysis.validate_predictions(normalized, truth_index, contract, "model")
    ledger = json.loads(args.ledger.read_text(encoding="utf-8"))
    assert ledger["protocol"] == materializer.MODEL_LEDGER_PROTOCOL
    assert ledger["test_attempts"] == 1
    assert ledger["prediction_sha256"] == materializer.sha256_file(args.output)
    assert ledger["source_one_shot"]["output_sha256"] == materializer.sha256_file(
        args.one_shot_output
    )


def test_model_prediction_rejects_inconsistent_reused_endpoint_score(tmp_path: Path) -> None:
    truth, cards, pairs, _ = materialized_truth(tmp_path)
    lock, assets = make_lock(tmp_path, truth, cards, pairs)
    args, _ = one_shot_fixture(
        tmp_path, truth, lock, assets[(0.6, 6)], inconsistent_endpoint=True
    )
    with pytest.raises(materializer.MaterializationError, match="endpoint score is inconsistent"):
        materializer.normalize_model_prediction(args)
    assert not args.output.exists()


def test_model_prediction_rejects_hash_or_orientation_substitution(tmp_path: Path) -> None:
    truth, cards, pairs, _ = materialized_truth(tmp_path)
    lock, assets = make_lock(tmp_path, truth, cards, pairs)
    args, _ = one_shot_fixture(tmp_path, truth, lock, assets[(0.6, 6)])
    bad_hash = copy.copy(args)
    bad_hash.expected_one_shot_output_sha256 = "0" * 64
    with pytest.raises(materializer.MaterializationError, match="SHA256 mismatch"):
        materializer.normalize_model_prediction(bad_hash)

    output = json.loads(args.one_shot_output.read_text(encoding="utf-8"))
    row = output["pair_predictions"][0]
    row["better"], row["worse"] = row["worse"], row["better"]
    row["better_score"], row["worse_score"] = row["worse_score"], row["better_score"]
    row["endpoint_run_ids"] = list(reversed(row["endpoint_run_ids"]))
    row["margin"] = row["better_score"] - row["worse_score"]
    write_json(args.one_shot_output, output)
    source_ledger = json.loads(args.one_shot_ledger.read_text(encoding="utf-8"))
    source_ledger["result"]["output_sha256"] = materializer.sha256_file(args.one_shot_output)
    write_json(args.one_shot_ledger, source_ledger)
    args.expected_one_shot_output_sha256 = materializer.sha256_file(args.one_shot_output)
    args.expected_one_shot_ledger_sha256 = materializer.sha256_file(args.one_shot_ledger)
    with pytest.raises(materializer.MaterializationError, match="absent or reversed"):
        materializer.normalize_model_prediction(args)


def test_model_prediction_requires_the_prelocked_exclusive_ledger_path(tmp_path: Path) -> None:
    truth, cards, pairs, _ = materialized_truth(tmp_path)
    lock, assets = make_lock(tmp_path, truth, cards, pairs)
    args, _ = one_shot_fixture(tmp_path, truth, lock, assets[(0.6, 6)])
    alternate = tmp_path / "alternate-one-shot-ledger.json"
    alternate.write_bytes(args.one_shot_ledger.read_bytes())
    args.one_shot_ledger = alternate
    args.expected_one_shot_ledger_sha256 = materializer.sha256_file(alternate)
    with pytest.raises(materializer.MaterializationError, match="ledger path was not pre-locked"):
        materializer.normalize_model_prediction(args)


def test_model_prediction_links_one_shot_weights_to_checkpoint_manifest(tmp_path: Path) -> None:
    truth, cards, pairs, _ = materialized_truth(tmp_path)
    lock, assets = make_lock(tmp_path, truth, cards, pairs)
    args, _ = one_shot_fixture(tmp_path, truth, lock, assets[(0.6, 6)])
    manifest = json.loads(args.checkpoint_manifest.read_text(encoding="utf-8"))
    manifest["artifacts"]["model.safetensors"] = "e" * 64
    write_json(args.checkpoint_manifest, manifest)
    new_manifest_sha = materializer.sha256_file(args.checkpoint_manifest)
    lock_value = json.loads(lock.read_text(encoding="utf-8"))
    lock_value["runs"][0]["checkpoint_manifest_sha256"] = new_manifest_sha
    write_json(lock, lock_value)
    args.checkpoint_manifest_sha256 = new_manifest_sha
    args.expected_lock_sha256 = materializer.sha256_file(lock)
    with pytest.raises(materializer.MaterializationError, match="differs from checkpoint manifest"):
        materializer.normalize_model_prediction(args)


def make_bundle_artifacts(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    truth, cards, pairs, _ = materialized_truth(tmp_path)
    lock, _ = make_lock(tmp_path, truth, cards, pairs)
    lock_value = json.loads(lock.read_text(encoding="utf-8"))
    truth_rows = materializer.read_jsonl(truth, "truth")
    predictions = [
        {
            "pair_id": row["pair_id"],
            "better_score": row["better_utility"],
            "worse_score": row["worse_utility"],
            "margin": row["better_utility"] - row["worse_utility"],
        }
        for row in truth_rows
    ]
    root = tmp_path / "bundle-root"
    root.mkdir()
    root_truth = root / "truth.jsonl"
    root_truth.write_bytes(truth.read_bytes())
    lock_sha = materializer.sha256_file(lock)
    truth_sha = materializer.sha256_file(root_truth)

    baseline_predictions = root / "baseline.jsonl"
    baseline_ledger = root / "baseline.ledger.json"
    write_jsonl(baseline_predictions, predictions)
    write_json(
        baseline_ledger,
        {
            "status": "COMPLETE",
            "test_attempts": 1,
            "lock_sha256": lock_sha,
            "truth_sha256": truth_sha,
            "prediction_sha256": materializer.sha256_file(baseline_predictions),
        },
    )
    runs = []
    for locked_run in lock_value["runs"]:
        name = f"qwen3_{locked_run['model_size_b']:g}b_seed{locked_run['seed']}"
        prediction_path = root / f"{name}.jsonl"
        ledger_path = root / f"{name}.ledger.json"
        write_jsonl(prediction_path, predictions)
        write_json(
            ledger_path,
            {
                "status": "COMPLETE",
                "test_attempts": 1,
                "lock_sha256": lock_sha,
                "truth_sha256": truth_sha,
                "prediction_sha256": materializer.sha256_file(prediction_path),
                "checkpoint_manifest_sha256": locked_run["checkpoint_manifest_sha256"],
            },
        )
        runs.append(
            {
                "model_size_b": locked_run["model_size_b"],
                "seed": locked_run["seed"],
                "checkpoint_manifest_sha256": locked_run["checkpoint_manifest_sha256"],
                "predictions": prediction_path.name,
                "ledger": ledger_path.name,
            }
        )
    inputs = root / "inputs.json"
    write_json(
        inputs,
        {
            "protocol": materializer.BUNDLE_INPUTS_PROTOCOL,
            "truth": root_truth.name,
            "baseline": {
                "predictions": baseline_predictions.name,
                "ledger": baseline_ledger.name,
            },
            "runs": runs,
        },
    )
    return truth, lock, root, inputs


def bundle_args(lock: Path, root: Path, inputs: Path) -> argparse.Namespace:
    return argparse.Namespace(
        contract=CONTRACT,
        expected_contract_sha256=materializer.sha256_file(CONTRACT),
        lock=lock,
        expected_lock_sha256=materializer.sha256_file(lock),
        root=root,
        inputs=inputs,
        expected_inputs_sha256=materializer.sha256_file(inputs),
        output=root / "bundle.json",
    )


def test_bundle_assembly_is_accepted_by_frozen_analysis(tmp_path: Path) -> None:
    _, lock, root, inputs = make_bundle_artifacts(tmp_path)
    args = bundle_args(lock, root, inputs)
    assert materializer.assemble_bundle(args) == 0
    summary, metrics, components, _ = analysis.analyze(CONTRACT, lock, args.output)
    assert summary["decision"]["support"]["pairs"] == 4
    assert len(metrics) == 9
    assert len(components) == 9


def test_bundle_assembly_rejects_path_escape_and_incomplete_matrix(tmp_path: Path) -> None:
    _, lock, root, inputs = make_bundle_artifacts(tmp_path)
    value = json.loads(inputs.read_text(encoding="utf-8"))
    value["baseline"]["predictions"] = "../outside.jsonl"
    write_json(inputs, value)
    args = bundle_args(lock, root, inputs)
    with pytest.raises(materializer.MaterializationError, match="escapes bundle root"):
        materializer.assemble_bundle(args)

    value["baseline"]["predictions"] = "baseline.jsonl"
    value["runs"].pop()
    write_json(inputs, value)
    args = bundle_args(lock, root, inputs)
    with pytest.raises(materializer.MaterializationError, match="incomplete"):
        materializer.assemble_bundle(args)


def test_exact_commit_remote_receipt_preserves_truth_and_compute_boundary() -> None:
    receipt = json.loads(REMOTE_RECEIPT.read_text(encoding="utf-8"))
    assert receipt["code_commit"] == "81a09d53f3b935c019a0126365ce4e76fa3940a1"
    assert receipt["remote_verification"]["focused_tests_passed"] == 25
    assert receipt["remote_verification"]["full_tests_passed"] == 848
    assert receipt["remote_verification"]["full_warnings"] == 33
    assert receipt["remote_verification"]["filename_credential_hits"] == 0
    assert receipt["remote_verification"]["content_credential_hits"] == 0
    assert receipt["access_attestation"] == {
        "api_calls": 0,
        "future_truth_opened": False,
        "gpu_jobs": 0,
        "model_fits": 0,
    }
