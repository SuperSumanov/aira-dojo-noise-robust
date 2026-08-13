from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from phase1 import task_parent_support_audit as audit_module


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )


def pair(better: str, worse: str, parent: str, task: str, run: str, size: int) -> dict:
    return {
        "better": better,
        "worse": worse,
        "parent": parent,
        "task": task,
        "run_id": run,
        "budget": 0,
        "intask_split": "train",
        "gap_raw": 0.1,
        "set_size": size,
    }


def write_oof(path: Path, rows: list[dict], folds: list[int]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["row_index", "task", "run", "parent", "better", "worse", "fold"],
        )
        writer.writeheader()
        for index, (row, fold) in enumerate(zip(rows, folds)):
            writer.writerow(
                {
                    "row_index": index,
                    "task": row["task"],
                    "run": row["run_id"],
                    "parent": row["parent"],
                    "better": row["better"],
                    "worse": row["worse"],
                    "fold": fold,
                }
            )


def test_audit_recognizes_complete_multiway_order_and_locked_run_folds(tmp_path: Path) -> None:
    train = tmp_path / "decision_train.jsonl"
    oof = tmp_path / "oof_predictions.csv"
    rows = [
        pair("a", "b", "p1", "t1", "r1", 3),
        pair("a", "c", "p1", "t1", "r1", 3),
        pair("b", "c", "p1", "t1", "r1", 3),
        pair("d", "e", "p2", "t2", "r2", 2),
        pair("f", "g", "p3", "t2", "r3", 2),
    ]
    write_jsonl(train, rows)
    write_oof(oof, rows, [0, 0, 0, 1, 2])
    result = audit_module.audit(train, oof)
    assert result["status"] == "AUDIT_COMPLETE"
    assert result["frozen_read"] is False
    assert result["global"]["parents"] == 3
    assert result["global"]["complete_parents"] == 3
    assert result["global"]["strict_total_order_parents"] == 3
    assert result["global"]["multiway_parents"] == 1
    assert result["global"]["multiway_pairs"] == 3
    assert result["global"]["candidate_count_histogram"] == {2: 2, 3: 1}
    task2 = next(item for item in result["per_task"] if item["task"] == "t2")
    assert task2["runs"] == 2
    assert task2["outer_active_folds"] == 2


def test_audit_rejects_frozen_path_and_cross_fold_run(tmp_path: Path) -> None:
    frozen = tmp_path / "decision_frozen.jsonl"
    frozen.write_text("", encoding="utf-8")
    with pytest.raises(audit_module.IntegrityError, match="forbidden"):
        audit_module.load_pairs(frozen)

    train = tmp_path / "decision_train.jsonl"
    oof = tmp_path / "oof_predictions.csv"
    rows = [
        pair("a", "b", "p1", "t", "r", 2),
        pair("c", "d", "p2", "t", "r", 2),
    ]
    write_jsonl(train, rows)
    write_oof(oof, rows, [0, 1])
    clean = audit_module.load_pairs(train)
    with pytest.raises(audit_module.IntegrityError, match="spans folds"):
        audit_module.load_locked_folds(oof, clean)
