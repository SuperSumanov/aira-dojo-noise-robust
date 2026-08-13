from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from phase1 import frozen_embed_manifest as manifest_module
from phase1 import frozen_embed_rank as rank_module
from phase1 import frozen_embed_worker as worker_module
from phase1 import verify_frozen_embed_discovery as verifier_module


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )


def test_manifest_is_label_blind_deterministic_and_run_clean(tmp_path: Path) -> None:
    cards = tmp_path / "cards.jsonl"
    pairs = tmp_path / "pairs.jsonl"
    run_map = tmp_path / "run_map.json"
    card_rows = [
        {"id": "a", "code": "print('a')", "task": "task-a", "run_id": "run-1"},
        {"id": "b", "code": "print('b')", "task": "task-a", "run_id": "run-1"},
        {"id": "unused", "code": "secret outcome is irrelevant", "task": "task-z", "run_id": "run-z"},
    ]
    pair_rows = [
        {
            "better": "a",
            "worse": "b",
            "parent": "p",
            "task": "task-a",
            "run_id": "run-1",
            "budget": 0,
            "intask_split": "train",
            "gap_raw": 0.2,
        }
    ]
    write_jsonl(cards, card_rows)
    write_jsonl(pairs, pair_rows)
    run_map.write_text(json.dumps({"a": "run-1", "b": "run-1"}), encoding="utf-8")
    first, first_summary = manifest_module.build_manifest(
        cards, pairs, run_map, "train", 4
    )
    second, second_summary = manifest_module.build_manifest(
        cards, pairs, run_map, "train", 4
    )
    assert first == second
    assert first_summary == second_summary
    assert [row["card_id"] for row in first] == ["a", "b"]
    assert all(set(row) == {"card_id", "task", "run_id", "code_chars", "code_sha256", "shard"} for row in first)
    assert first_summary["pairs"] == 1
    assert first_summary["endpoints"] == 2


def test_worker_truncation_and_chunk_prefix_round_trip(tmp_path: Path) -> None:
    values = list(range(20))
    assert worker_module.truncate(values, 8, 0.25) == [0, 1, 14, 15, 16, 17, 18, 19]
    assert worker_module.truncate(values, 30, 0.25) == values
    first = tmp_path / "chunk_000000_000002.npz"
    second = tmp_path / "chunk_000002_000003.npz"
    worker_module.save_chunk(
        first,
        ["a", "b"],
        np.asarray([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32),
        np.asarray([7, 8]),
        np.asarray([9, 10]),
    )
    worker_module.save_chunk(
        second,
        ["c"],
        np.asarray([[5.0, 6.0]], dtype=np.float32),
        np.asarray([8]),
        np.asarray([11]),
    )
    consumed, dimension, records = worker_module.existing_prefix(
        tmp_path, ["a", "b", "c"]
    )
    assert consumed == 3
    assert dimension == 2
    assert [record["rows"] for record in records] == [2, 1]
    assert all(len(record["sha256"]) == 64 for record in records)


def test_rank_metrics_match_independent_implementation() -> None:
    rows = [
        {"task": "t1", "run": "r1", "parent": "p1", "better": "a", "worse": "b", "gap_raw": 2.0},
        {"task": "t1", "run": "r1", "parent": "p1", "better": "a", "worse": "c", "gap_raw": 1.0},
        {"task": "t1", "run": "r1", "parent": "p1", "better": "b", "worse": "c", "gap_raw": 0.5},
        {"task": "t2", "run": "r2", "parent": "p2", "better": "d", "worse": "e", "gap_raw": 3.0},
    ]
    scores = {"a": 3.0, "b": 2.0, "c": 1.0, "d": 0.0, "e": 1.0}
    hits = [1.0, 1.0, 1.0, 0.0]
    producer_top1, _ = rank_module.parent_top1(rows, scores)
    verifier_top1 = verifier_module.parent_top1(rows, scores)
    producer_utility = rank_module.parent_equal_gap_utility(rows, hits)
    verifier_utility = verifier_module.gap_utility(rows, hits)
    assert producer_top1 == verifier_top1
    assert producer_utility == verifier_utility
    assert producer_top1["overall"] == 0.5
    assert producer_utility["overall"] == 0.5


def test_parent_equal_weighting_differs_from_pooled_gap_weighting() -> None:
    rows = [
        {"task": "t", "run": "r", "parent": "large", "gap_raw": 100.0},
        {"task": "t", "run": "r", "parent": "small", "gap_raw": 1.0},
    ]
    result = rank_module.parent_equal_gap_utility(rows, [1.0, 0.0])
    assert result["overall"] == 0.5
