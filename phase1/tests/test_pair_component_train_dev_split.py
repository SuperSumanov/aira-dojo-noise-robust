import importlib
import hashlib
import inspect
import json
import random
from pathlib import Path

import pytest


verifier = importlib.import_module("phase1.verify_pair_component_train_dev_split")
producer = importlib.import_module("phase1.build_pair_component_train_dev_split")


def card(card_id: str, task: str) -> dict:
    return {"id": card_id, "task": {"name": task}}


def pair(task: str, parent: str, better: str, worse: str, split: str) -> dict:
    return {
        "better": better, "budget": 0, "clears_tau": None, "gap_raw": 0.1,
        "intask_split": split, "loto_fold": task, "parent": parent,
        "set_size": 2, "src": "decision", "task": task, "worse": worse,
    }


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def fixture(tmp_path: Path):
    grouped = {
        "run-a": [card("a1", "task-a"), card("a2", "task-a")],
        "run-b": [card("b1", "task-a"), card("b2", "task-a")],
        "run-c": [card("c1", "task-a")],
        "run-d": [card("d1", "task-a")],
        "run-e": [card("e1", "task-b"), card("e2", "task-b")],
        "run-f": [card("f1", "task-b"), card("f2", "task-b")],
        "run-g": [card("g1", "task-b"), card("g2", "task-b")],
        "run-test": [card("t1", "task-a"), card("t2", "task-a")],
    }
    rows = [
        pair("task-a", "pa1", "a1", "b1", "train"),
        pair("task-a", "pa2", "a2", "b2", "train"),
        pair("task-a", "pa3", "c1", "d1", "train"),
        pair("task-b", "pb1", "e1", "f1", "train"),
        pair("task-b", "pb2", "e2", "f2", "train"),
        pair("task-b", "pb3", "g1", "g2", "train"),
        pair("task-a", "ptest", "t1", "t2", "test"),
    ]
    cards_path = tmp_path / "cards.json"
    pairs_path = tmp_path / "pairs.jsonl"
    cards_path.write_text(json.dumps(grouped))
    write_jsonl(pairs_path, rows)
    paths = [tmp_path / name for name in ("train.jsonl", "dev.jsonl", "test.jsonl", "manifest.json")]
    return cards_path, pairs_path, paths


def test_component_split_keeps_all_pairs_and_is_independently_verified(tmp_path):
    cards_path, pairs_path, paths = fixture(tmp_path)
    manifest = producer.build_split(
        cards_path, pairs_path, *paths, enforce_fixed_identity=False,
    )
    assert manifest["train_pairs"] == 4
    assert manifest["dev_pairs"] == 2
    assert manifest["heldout_test_pairs"] == 1
    assert manifest["dropped_source_train_pairs"] == 0
    assert manifest["train_dev_card_overlap"] == 0
    assert manifest["train_dev_run_overlap"] == 0
    receipt = verifier.verify(
        cards_path, pairs_path, *paths, enforce_fixed_identity=False,
    )
    assert receipt["status"] == "PAIR_COMPONENT_SPLIT_INDEPENDENTLY_VERIFIED"


def test_verifier_rejects_tampered_component_receipt(tmp_path):
    cards_path, pairs_path, paths = fixture(tmp_path)
    producer.build_split(cards_path, pairs_path, *paths, enforce_fixed_identity=False)
    rows = verifier.read_rows(paths[1])
    rows[0]["pair_component_id"] = "0" * 64
    write_jsonl(paths[1], rows)
    with pytest.raises(verifier.VerificationError, match="dev.jsonl"):
        verifier.verify(cards_path, pairs_path, *paths, enforce_fixed_identity=False)


def test_single_component_task_stays_in_train():
    assert producer.choose_dev_indices([7], ["a" * 64]) == ()
    assert verifier.select_component_positions([7], ["a" * 64]) == ()


def test_verifier_does_not_import_producer():
    assert "build_pair_component_train_dev_split" not in inspect.getsource(verifier)


def test_two_subset_implementations_agree_on_weight_patterns():
    for weights in ([1, 2], [5, 5, 7], [1, 3, 8, 13], [10, 1, 1, 1, 1]):
        ids = [f"{index:064x}" for index in range(len(weights))]
        assert producer.choose_dev_indices(list(weights), ids) == verifier.select_component_positions(list(weights), ids)

    rng = random.Random(20260821)
    for component_count in range(2, 9):
        for _ in range(25):
            weights = [rng.randint(1, 40) for _ in range(component_count)]
            ids = [hashlib.sha256(f"{component_count}:{index}".encode()).hexdigest() for index in range(component_count)]
            ids.sort()
            assert producer.choose_dev_indices(weights, ids) == verifier.select_component_positions(weights, ids)
