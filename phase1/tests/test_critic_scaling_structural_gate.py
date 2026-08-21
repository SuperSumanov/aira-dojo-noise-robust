import json
from pathlib import Path

import pytest

from phase1 import critic_scaling_structural_gate as gate


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def pair(task: str, parent: str, better: str, worse: str, split: str) -> dict:
    return {
        "better": better, "budget": 0, "clears_tau": None, "gap_raw": 0.1,
        "intask_split": split, "loto_fold": task, "parent": parent,
        "set_size": 2, "src": "decision", "task": task, "worse": worse,
    }


def test_pair_key_is_orientation_free():
    left = pair("task", "parent", "a", "b", "train")
    right = pair("task", "parent", "b", "a", "train")
    assert gate.pair_key(left) == gate.pair_key(right)


def test_source_form_requires_outer_train_receipt():
    row = pair("task", "parent", "a", "b", "dev")
    with pytest.raises(gate.GateError, match="outer-train"):
        gate.source_form(row)
    row |= {
        "outer_intask_split": "train",
        "train_dev_protocol": "physical-run-train-dev-split-v1",
        "train_dev_seed": 20260821,
    }
    assert gate.source_form(row)["intask_split"] == "train"


def test_source_form_accepts_and_strips_component_receipt():
    row = pair("task", "parent", "a", "b", "dev")
    row |= {
        "outer_intask_split": "train",
        "train_dev_protocol": "pair-graph-component-train-dev-split-v1",
        "train_dev_seed": 20260821,
        "train_dev_target_numerator": 1,
        "train_dev_target_denominator": 10,
        "pair_component_id": "a" * 64,
    }
    assert gate.source_form(row) == pair("task", "parent", "a", "b", "train")


def test_keyed_rejects_reversed_duplicate(tmp_path):
    rows = [
        pair("task", "parent", "a", "b", "train"),
        pair("task", "parent", "b", "a", "train"),
    ]
    path = tmp_path / "pairs.jsonl"
    write_jsonl(path, rows)
    with pytest.raises(gate.GateError, match="duplicate"):
        gate.keyed(gate.read_jsonl(path), "fixture")


def test_card_maps_reject_missing_endpoint(tmp_path):
    cards = {
        "run-a": [{"id": "a", "task": {"name": "task"}}],
    }
    path = tmp_path / "cards.json"
    path.write_text(json.dumps(cards))
    with pytest.raises(gate.GateError, match="missing"):
        gate.load_card_maps(path, {"a", "b"})
