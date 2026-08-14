from __future__ import annotations

import json
from pathlib import Path

import pytest

from phase1 import decision_corpus_audit as audit_module
from phase1 import verify_decision_corpus_audit as verifier_module


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )


def pair(
    better: str,
    worse: str,
    parent: str,
    task: str,
    budget: int,
    split: str,
    size: int = 2,
    gap: float = 0.01,
) -> dict:
    return {
        "better": better,
        "worse": worse,
        "parent": parent,
        "task": task,
        "budget": budget,
        "intask_split": split,
        "gap_raw": gap,
        "set_size": size,
    }


def test_complete_choice_sets_and_split_isolation(tmp_path: Path) -> None:
    train = tmp_path / "train.jsonl"
    frozen = tmp_path / "frozen.jsonl"
    run_map = tmp_path / "run_map.json"
    train_rows = [
        pair("a", "b", "p", "t", 0, "train", 3, 0.00001),
        pair("a", "c", "p", "t", 0, "train", 3, 0.1),
        pair("b", "c", "p", "t", 0, "train", 3, 0.01),
    ]
    frozen_rows = [pair("d", "e", "q", "t", 0, "test", 2, 0.02)]
    write_jsonl(train, train_rows)
    write_jsonl(frozen, frozen_rows)
    write_json(run_map, {"a": "r1", "b": "r1", "c": "r1", "p": "r1", "d": "r2", "e": "r2", "q": "r2"})

    result = audit_module.audit(
        [("train", 0, train), ("frozen", 0, frozen)], run_map
    )
    assert result["status"] == "VERIFIED_DECISION_CORPUS_AUDIT"
    assert result["sets"]["train:b0"]["parents"] == 1
    assert result["sets"]["train:b0"]["complete_parents"] == 1
    assert result["sets"]["train:b0"]["strict_total_order_parents"] == 1
    assert result["sets"]["train:b0"]["hard_pairs"] == 1
    assert result["same_budget_train_frozen_isolation"]["b0"]["passed"] is True


def test_rejects_cross_run_sibling_and_reverse_duplicate(tmp_path: Path) -> None:
    path = tmp_path / "train.jsonl"
    run_map = {"a": "r1", "b": "r2", "p": "r1"}
    write_jsonl(path, [pair("a", "b", "p", "t", 0, "train")])
    with pytest.raises(audit_module.IntegrityError, match="not a true physical-run sibling"):
        audit_module.load_pair_set("train", 0, path, run_map)

    run_map["b"] = "r1"
    write_jsonl(
        path,
        [
            pair("a", "b", "p", "t", 0, "train"),
            pair("b", "a", "p", "t", 0, "train"),
        ],
    )
    with pytest.raises(audit_module.IntegrityError, match="duplicates or reverses"):
        audit_module.load_pair_set("train", 0, path, run_map)


def test_missing_pruned_parent_is_audited_not_treated_as_cross_run(tmp_path: Path) -> None:
    path = tmp_path / "train.jsonl"
    write_jsonl(path, [pair("a", "b", "pruned-parent", "t", 0, "train")])
    rows = audit_module.load_pair_set("train", 0, path, {"a": "r1", "b": "r1"})
    choices = audit_module.choice_set_records(rows)
    summary = audit_module.summarize_set(rows, choices)
    assert summary["mapped_parent_choice_sets"] == 0
    assert summary["orphan_parent_choice_sets"] == 1


def test_mapped_parent_in_another_run_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "train.jsonl"
    write_jsonl(path, [pair("a", "b", "p", "t", 0, "train")])
    with pytest.raises(audit_module.IntegrityError, match="mapped parent run"):
        audit_module.load_pair_set(
            "train", 0, path, {"a": "r1", "b": "r1", "p": "r2"}
        )


def test_train_frozen_run_overlap_fails_closed(tmp_path: Path) -> None:
    train = tmp_path / "train.jsonl"
    frozen = tmp_path / "frozen.jsonl"
    run_map_path = tmp_path / "run_map.json"
    write_jsonl(train, [pair("a", "b", "p", "t", 0, "train")])
    write_jsonl(frozen, [pair("c", "d", "q", "t", 0, "test")])
    write_json(
        run_map_path,
        {"a": "r", "b": "r", "p": "r", "c": "r", "d": "r", "q": "r"},
    )
    result = audit_module.audit(
        [("train", 0, train), ("frozen", 0, frozen)], run_map_path
    )
    assert result["status"] == "FAILED_SPLIT_ISOLATION"
    assert result["same_budget_train_frozen_isolation"]["b0"]["runs"] == 1


def test_pair_set_parser_preserves_windows_drive_colon() -> None:
    partition, budget, path = audit_module.parse_pair_set("train:2:C:/x/pairs.jsonl")
    assert partition == "train"
    assert budget == 2
    assert str(path).replace("\\", "/") == "C:/x/pairs.jsonl"


def test_independent_verifier_recomputes_card_and_rejects_tampering(tmp_path: Path) -> None:
    train = tmp_path / "train.jsonl"
    frozen = tmp_path / "frozen.jsonl"
    run_map = tmp_path / "run_map.json"
    write_jsonl(train, [pair("a", "b", "p", "t", 0, "train", gap=0.001)])
    write_jsonl(frozen, [pair("c", "d", "q", "t", 0, "test", gap=0.1)])
    write_json(
        run_map,
        {"a": "r1", "b": "r1", "p": "r1", "c": "r2", "d": "r2", "q": "r2"},
    )
    result = audit_module.audit(
        [("train", 0, train), ("frozen", 0, frozen)], run_map
    )
    for record in result["inputs"].values():
        record["path"] = str((tmp_path / Path(record["path"]).name).resolve())
    card = tmp_path / "audit_card.json"
    write_json(card, result)
    verified = verifier_module.verify(card, Path.cwd())
    assert verified["status"] == "INDEPENDENTLY_VERIFIED_DECISION_CORPUS_AUDIT"

    result["sets"]["train:b0"]["pairs"] += 1
    write_json(card, result)
    with pytest.raises(verifier_module.VerificationError, match="metrics differ"):
        verifier_module.verify(card, Path.cwd())


def test_verifier_does_not_import_producer() -> None:
    source = Path(verifier_module.__file__).read_text(encoding="utf-8")
    forbidden = (
        "import decision_corpus_audit",
        "from phase1 import decision_corpus_audit",
    )
    assert not any(token in source for token in forbidden)
