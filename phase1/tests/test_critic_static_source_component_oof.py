import hashlib
import importlib
import inspect
import json
import random
from pathlib import Path

import numpy as np
import pytest


pytest.importorskip("sklearn")

producer = importlib.import_module("phase1.critic_static_source_component_oof")
verifier = importlib.import_module("phase1.verify_critic_static_source_component_oof")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def component(name: str) -> str:
    return hashlib.sha256(name.encode()).hexdigest()


def pair(task: str, parent: str, better: str, worse: str, split: str, component_id: str) -> dict:
    return {
        "better": better,
        "budget": 0,
        "clears_tau": None,
        "gap_raw": .1,
        "intask_split": split,
        "loto_fold": task,
        "outer_intask_split": "train",
        "pair_component_id": component_id,
        "parent": parent,
        "set_size": 2,
        "src": "decision",
        "task": task,
        "train_dev_protocol": "pair-graph-component-train-dev-split-v1",
        "train_dev_seed": 20260821,
        "train_dev_target_denominator": 10,
        "train_dev_target_numerator": 1,
        "worse": worse,
    }


def card(card_id: str, task: str, favorable: bool, ordinal: int) -> dict:
    code = (
        "import sklearn\nfrom xgboost import XGBClassifier\n"
        "seed random_state kfold cross_val ensemble blend stack mean( early_stop "
        "optuna param_grid augment transform try: print( cuda # robust\n"
        f"n_splits={3 + ordinal % 3}\nepochs={5 + ordinal % 5}\n"
        if favorable
        else f"import pandas\nprint('baseline-{ordinal}')\n"
    )
    return {
        "id": card_id,
        "task": {"name": task},
        "code": code,
        "lineage": {"depth": 2 + favorable, "step": ordinal + favorable, "n_siblings": 2},
        "client": "client",
        "hardware": "gpu",
        "time_limit": 120,
        "execution_timeout": 120,
        "obs": {"stdout": "forbidden"},
        "label": "forbidden",
        "parent_val": 1.0,
    }


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


def build_fixture(tmp_path: Path):
    rows = []
    grouped = {}
    component_ids = [component(f"component-{index}") for index in range(12)]
    for index, component_id in enumerate(component_ids):
        task = "task-a" if index < 7 else "task-b"
        split = "train" if index < 8 else "dev"
        parent = "shared-parent" if index in (0, 1) else f"parent-{index}"
        better, worse = f"better-{index}", f"worse-{index}"
        rows.append(pair(task, parent, better, worse, split, component_id))
        grouped[f"run-{better}"] = [card(better, task, True, index)]
        grouped[f"run-{worse}"] = [card(worse, task, False, index)]
    train = tmp_path / "train.jsonl"
    dev = tmp_path / "dev.jsonl"
    cards = tmp_path / "cards.json"
    write_jsonl(train, [row for row in rows if row["intask_split"] == "train"])
    write_jsonl(dev, [row for row in rows if row["intask_split"] == "dev"])
    cards.write_text(json.dumps(grouped, sort_keys=True), encoding="utf-8")
    expected = {
        "cards": (sha(cards), cards.stat().st_size),
        "train": (sha(train), train.stat().st_size),
        "dev": (sha(dev), dev.stat().st_size),
    }
    counts = {
        "pairs": 12,
        "tasks": 2,
        "original_components": 12,
        "cross_component_parents": 1,
        "supercomponents": 11,
        "merged_supercomponents": 1,
        "maximum_original_components_per_supercomponent": 2,
    }
    return cards, train, dev, rows, expected, counts


def patch_fixture(monkeypatch, expected, counts):
    monkeypatch.setattr(producer, "EXPECTED", expected)
    monkeypatch.setattr(verifier, "EXPECTED", expected)
    monkeypatch.setattr(producer, "EXPECTED_COUNTS", counts)
    monkeypatch.setattr(verifier, "EXPECTED_COUNTS", counts)
    monkeypatch.setattr(producer, "BOOTSTRAP_REPS", 30)
    monkeypatch.setattr(verifier, "REPS", 30)


def test_feature_groups_are_exact_and_ignore_forbidden_fields():
    example = card("id", "task", True, 3)
    example["obs"] = object()
    example["label"] = object()
    example["parent_val"] = object()
    observed = producer.feature_dict(example)
    assert tuple(sorted(observed)) == producer.FEATURE_NAMES
    assert len(observed) == 34
    assert set(producer.LINEAGE_FEATURES) == {"depth", "step", "n_sibs"}
    assert len(producer.CODE_FEATURES) == 31
    assert not ({"obs", "label", "parent_val", "runtime", "stdout"} & set(observed))


def test_parent_closure_is_transitive(monkeypatch):
    components = [component(f"chain-{index}") for index in range(3)]
    rows = [
        pair("task", "parent-a", "b0", "w0", "train", components[0]),
        pair("task", "parent-a", "b1", "w1", "train", components[1]),
        pair("task", "parent-b", "b2", "w2", "train", components[1]),
        pair("task", "parent-b", "b3", "w3", "train", components[2]),
    ]
    endpoints = {row[side] for row in rows for side in ("better", "worse")}
    runs = {endpoint: f"run-{endpoint}" for endpoint in endpoints}
    tasks = {endpoint: "task" for endpoint in endpoints}
    configs = {endpoint: ("task", "client", "gpu", 120, 120) for endpoint in endpoints}
    monkeypatch.setattr(producer, "EXPECTED_COUNTS", {
        "pairs": 4,
        "tasks": 1,
        "original_components": 3,
        "cross_component_parents": 2,
        "supercomponents": 1,
        "merged_supercomponents": 1,
        "maximum_original_components_per_supercomponent": 3,
    })
    mapping, receipt = producer.validate_and_close_components(rows, runs, tasks, configs)
    assert len(set(mapping.values())) == 1
    assert receipt["maximum_original_components_per_supercomponent"] == 3


def test_fold_assignment_is_order_invariant_and_parent_isolated(tmp_path, monkeypatch):
    cards_path, train_path, dev_path, rows, expected, counts = build_fixture(tmp_path)
    patch_fixture(monkeypatch, expected, counts)
    endpoints = {row[side] for row in rows for side in ("better", "worse")}
    _, runs, tasks, configs, _ = producer.load_cards(cards_path, endpoints)
    mapping, _ = producer.validate_and_close_components(rows, runs, tasks, configs)
    folds, _ = producer.assign_folds(rows, mapping)
    isolation = producer.fold_isolation(rows, folds, runs, mapping)
    shuffled = list(rows)
    random.Random(17).shuffle(shuffled)
    shuffled_mapping, _ = producer.validate_and_close_components(shuffled, runs, tasks, configs)
    shuffled_folds, _ = producer.assign_folds(shuffled, shuffled_mapping)
    original = {producer.pair_key(row): int(fold) for row, fold in zip(rows, folds)}
    reordered = {producer.pair_key(row): int(fold) for row, fold in zip(shuffled, shuffled_folds)}
    assert original == reordered
    assert all(value == 0 for receipt in isolation for key, value in receipt.items() if key.endswith("_overlap"))


def test_oof_predictions_are_complete_and_antisymmetric():
    rng = np.random.default_rng(7)
    values = rng.normal(size=(60, 34))
    folds = np.arange(60, dtype=np.int8) % 5
    margins, receipts, anti = producer.oof_margins(values, folds)
    assert set(margins) == set(producer.LEARNED)
    assert all(np.isfinite(value).all() for value in margins.values())
    assert all(len(receipts[name]) == 5 for name in producer.LEARNED)
    assert max(anti.values()) <= 1e-12


def test_producer_and_independent_full_refit_agree(tmp_path, monkeypatch):
    cards_path, train_path, dev_path, _, expected, counts = build_fixture(tmp_path)
    patch_fixture(monkeypatch, expected, counts)
    result = producer.analyze(cards_path, train_path, dev_path)
    output = tmp_path / "output"
    producer.write_outputs(output, *result)
    receipt = verifier.verify(cards_path, train_path, dev_path, output)
    assert receipt["full_refit"] is True
    assert receipt["producer_imported"] is False
    assert receipt["max_abs_summary_difference"] == 0.0
    assert receipt["max_abs_pair_difference"] == 0.0
    assert receipt["verification_gates"]["all_fold_rows_exact"] is True


def test_artifact_tamper_is_detected(tmp_path, monkeypatch):
    cards_path, train_path, dev_path, _, expected, counts = build_fixture(tmp_path)
    patch_fixture(monkeypatch, expected, counts)
    result = producer.analyze(cards_path, train_path, dev_path)
    output = tmp_path / "output"
    producer.write_outputs(output, *result)
    rows = [json.loads(line) for line in (output / "per_pair.jsonl").read_text().splitlines()]
    rows[0]["margin"] += .25
    write_jsonl(output / "per_pair.jsonl", rows)
    with pytest.raises(verifier.VerificationError):
        verifier.verify(cards_path, train_path, dev_path, output)


def test_input_hash_tamper_is_detected(tmp_path, monkeypatch):
    cards_path, train_path, dev_path, _, expected, counts = build_fixture(tmp_path)
    patch_fixture(monkeypatch, expected, counts)
    train_path.write_text(train_path.read_text() + "\n")
    with pytest.raises(producer.AuditError, match="byte count mismatch"):
        producer.analyze(cards_path, train_path, dev_path)


def test_verifier_does_not_import_current_producer_and_cli_has_no_test_input():
    source = inspect.getsource(verifier)
    assert "from phase1.critic_static_source_component_oof" not in source
    assert "import phase1.critic_static_source_component_oof" not in source
    main_source = inspect.getsource(producer.main)
    assert 'add_argument("test"' not in main_source
    assert 'add_argument("tfidf' not in main_source
    assert 'add_argument("semantic' not in main_source
