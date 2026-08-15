import json
import sys
from pathlib import Path

import pytest

from phase1 import score_frozen_decision_checkpoint as scorer


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def fixture_files(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    cards = tmp_path / "cards.jsonl"
    run_map = tmp_path / "run_map.json"
    pairs = tmp_path / "pairs.jsonl"
    scores = tmp_path / "scores.json"
    write_jsonl(
        cards,
        [
            {"id": "a", "task": {"name": "task-x"}, "code": "print('a')"},
            {"id": "b", "task": {"name": "task-x"}, "code": "print('b')"},
        ],
    )
    run_map.write_text(json.dumps({"a": "run-1", "b": "run-1"}), encoding="utf-8")
    write_jsonl(
        pairs,
        [
            {
                "better": "a",
                "worse": "b",
                "parent": "p",
                "task": "task-x",
                "intask_split": "test",
            }
        ],
    )
    scores.write_text(json.dumps({"a": 1.0, "b": 0.0}), encoding="utf-8")
    return cards, run_map, pairs, scores


def test_pair_specs_and_expectations_fail_closed() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        scorer.parse_pair_specs(["b0=a.jsonl", "b0=b.jsonl"])
    with pytest.raises(ValueError, match="SHA256"):
        scorer.parse_pair_expectations(["b0=1:not-a-digest"])
    with pytest.raises(ValueError, match="positive"):
        scorer.parse_pair_expectations([f"b0=0:{'a' * 64}"])


def test_validate_pairs_rejects_non_test_and_reverse_duplicate(tmp_path: Path) -> None:
    cards, run_map_path, pairs, _ = fixture_files(tmp_path)
    code, task = scorer.load_cards(cards)
    run_map = json.loads(run_map_path.read_text(encoding="utf-8"))

    bad_split = json.loads(pairs.read_text(encoding="utf-8").strip())
    bad_split["intask_split"] = "train"
    write_jsonl(pairs, [bad_split])
    with pytest.raises(RuntimeError, match="non-test"):
        scorer.validate_pairs({"b0": pairs}, code, task, run_map)

    first = {**bad_split, "intask_split": "test"}
    reverse = {**first, "better": "b", "worse": "a"}
    write_jsonl(pairs, [first, reverse])
    with pytest.raises(RuntimeError, match="duplicate or reversed"):
        scorer.validate_pairs({"b0": pairs}, code, task, run_map)


def test_validate_pairs_rejects_cross_run_and_empty_code(tmp_path: Path) -> None:
    cards, run_map_path, pairs, _ = fixture_files(tmp_path)
    code, task = scorer.load_cards(cards)
    with pytest.raises(RuntimeError, match="crosses physical runs"):
        scorer.validate_pairs(
            {"b0": pairs}, code, task, {"a": "run-1", "b": "run-2"}
        )
    code["b"] = ""
    run_map = json.loads(run_map_path.read_text(encoding="utf-8"))
    with pytest.raises(RuntimeError, match="empty code"):
        scorer.validate_pairs({"b0": pairs}, code, task, run_map)


def test_cpu_audit_writes_tie_aware_outputs_and_refuses_overwrite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cards, run_map, pairs, scores = fixture_files(tmp_path)
    output = tmp_path / "output"
    argv = [
        "score_frozen_decision_checkpoint.py",
        "--cards", str(cards),
        "--run-map", str(run_map),
        "--pairs", f"frozen_b0={pairs}",
        "--scores-json", str(scores),
        "--bootstrap", "100",
        "--seed", "7",
        "--out-dir", str(output),
    ]
    monkeypatch.setattr(sys, "argv", argv)
    scorer.main()
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["results"]["frozen_b0"]["accuracy"] == 1.0
    assert summary["results"]["frozen_b0"]["pairs"] == 1
    predictions = json.loads((output / "predictions.json").read_text(encoding="utf-8"))
    assert predictions == {"frozen_b0": {"a|b": 1}}
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        scorer.main()


def test_checkpoint_mode_requires_all_frozen_hash_locks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cards, run_map, pairs, _ = fixture_files(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "score_frozen_decision_checkpoint.py",
            "--cards", str(cards),
            "--run-map", str(run_map),
            "--pairs", f"frozen_b0={pairs}",
            "--checkpoint", str(tmp_path / "checkpoint"),
            "--base-model", "Qwen/Qwen3-4B-Base",
            "--checkpoint-locked-before-frozen",
            "--out-dir", str(tmp_path / "output"),
        ],
    )
    with pytest.raises(ValueError, match="requires locked cards/run-map SHA256"):
        scorer.main()


def test_exact_run_sign_excludes_tied_runs() -> None:
    result = scorer.exact_run_sign(
        [
            {"run_id": "positive", "pair_accuracy": 1.0},
            {"run_id": "negative", "pair_accuracy": 0.0},
            {"run_id": "tied", "pair_accuracy": 0.5},
        ]
    )
    assert result == {
        "positive": 1,
        "negative": 1,
        "tied": 1,
        "exact_p_two_sided": 1.0,
    }
