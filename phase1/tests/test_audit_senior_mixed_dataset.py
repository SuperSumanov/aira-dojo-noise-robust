from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "audit_senior_mixed_dataset.py"
SPEC = importlib.util.spec_from_file_location("audit_senior_mixed_dataset", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def pair(better: str, worse: str, split: str, source: str = "decision") -> dict[str, object]:
    return {
        "better": better,
        "worse": worse,
        "task": "task-a",
        "intask_split": split,
        "src": source,
    }


def test_pair_summary_detects_overlap_and_unordered_duplicates(tmp_path: Path) -> None:
    path = tmp_path / "pairs.jsonl"
    records = [
        pair("a", "b", "train"),
        pair("b", "a", "train"),
        pair("a", "c", "test"),
    ]
    write_jsonl(path, records)
    summary = MODULE.pair_summary(path, MODULE.read_pairs(path))
    assert summary["rows"] == 3
    assert summary["oriented_duplicate_excess"] == 0
    assert summary["unordered_duplicate_excess"] == 1
    assert summary["train_test_endpoint_overlap"] == 1
    assert summary["self_pairs"] == 0


def test_launcher_audit_fails_closed_on_missing_reference(tmp_path: Path) -> None:
    launcher = tmp_path / "launch.sh"
    launcher.write_text(
        'run --train_pairs "$DATA_DIR/missing.jsonl" '
        '--test_pairs "$DATA_DIR/missing.jsonl" --eval_steps 10\n',
        encoding="utf-8",
    )
    audit = MODULE.launcher_audit(launcher, tmp_path)
    assert audit["same_train_test_reference_per_run"] is True
    assert audit["referenced_pair_files_exist"] == {"missing.jsonl": False}
    assert audit["eval_steps"] == [10]


def test_read_pairs_rejects_unknown_split(tmp_path: Path) -> None:
    path = tmp_path / "bad.jsonl"
    write_jsonl(path, [pair("a", "b", "dev")])
    with pytest.raises(ValueError, match="unsupported split"):
        MODULE.read_pairs(path)
