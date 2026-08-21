import hashlib
import importlib
import inspect
import json
from pathlib import Path

import pytest


pytest.importorskip("scipy")
pytest.importorskip("sklearn")

verifier = importlib.import_module("phase1.verify_critic_component_tfidf_baseline")
producer = importlib.import_module("phase1.critic_component_tfidf_baseline")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def card(card_id: str, task: str, code: str) -> dict:
    return {
        "id": card_id, "task": {"name": task}, "code": code,
        "client": "client", "hardware": "gpu", "time_limit": 100,
        "execution_timeout": 100,
    }


def pair(task: str, parent: str, better: str, worse: str, split: str, component: str | None = None) -> dict:
    row = {
        "better": better, "budget": 0, "clears_tau": None, "gap_raw": .1,
        "intask_split": split, "loto_fold": task, "parent": parent,
        "set_size": 2, "src": "decision", "task": task, "worse": worse,
    }
    if split in {"train", "dev"}:
        row |= {
            "outer_intask_split": "train",
            "train_dev_protocol": "pair-graph-component-train-dev-split-v1",
            "train_dev_seed": 20260821,
            "train_dev_target_numerator": 1,
            "train_dev_target_denominator": 10,
            "pair_component_id": component,
        }
    return row


def source_form(row: dict) -> dict:
    output = dict(row)
    for key in (
        "outer_intask_split", "train_dev_protocol", "train_dev_seed",
        "train_dev_target_numerator", "train_dev_target_denominator", "pair_component_id",
    ):
        output.pop(key, None)
    if row["intask_split"] == "dev":
        output["intask_split"] = "train"
    return output


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows))


def build_fixture(tmp_path: Path):
    rows = {
        "train": [
            pair("task-a", "p1", "a1", "a2", "train", "a" * 64),
            pair("task-a", "p2", "a3", "a4", "train", "a" * 64),
            pair("task-b", "p3", "b1", "b2", "train", "b" * 64),
            pair("task-b", "p4", "b3", "b4", "train", "b" * 64),
        ],
        "dev": [
            pair("task-a", "p5", "c1", "c2", "dev", "c" * 64),
            pair("task-b", "p6", "d1", "d2", "dev", "d" * 64),
        ],
        "test": [
            pair("task-a", "p7", "e1", "e2", "test"),
            pair("task-b", "p8", "f1", "f2", "test"),
        ],
    }
    grouped = {}
    for split_rows in rows.values():
        for row in split_rows:
            task = row["task"]
            for role in ("better", "worse"):
                card_id = row[role]
                favorable = role == "better"
                code = (
                    "feature engineering ensemble validation robust model " * 4
                    if favorable else "simple error baseline weak model " * 4
                ) + card_id
                grouped[f"run-{card_id}"] = [card(card_id, task, code)]
    paths = {name: tmp_path / f"{name}.jsonl" for name in rows}
    for name, path in paths.items():
        write_jsonl(path, rows[name])
    cards_path = tmp_path / "cards.json"
    cards_path.write_text(json.dumps(grouped, sort_keys=True))
    all_source = [source_form(row) for name in ("train", "dev", "test") for row in rows[name]]
    draft_path, improve_path = tmp_path / "draft.jsonl", tmp_path / "improve.jsonl"
    write_jsonl(draft_path, all_source[::2])
    write_jsonl(improve_path, all_source[1::2])
    input_paths = {
        "cards": cards_path, "train": paths["train"], "dev": paths["dev"], "test": paths["test"],
        "draft": draft_path, "improve": improve_path,
    }
    expected = {role: (sha(path), path.stat().st_size) for role, path in input_paths.items()}
    return input_paths, expected


def test_producer_and_independent_full_refit_agree(tmp_path, monkeypatch):
    inputs, expected = build_fixture(tmp_path)
    monkeypatch.setattr(producer, "EXPECTED", expected)
    monkeypatch.setattr(verifier, "EXPECTED", expected)
    monkeypatch.setattr(producer, "BOOTSTRAP_REPS", 100)
    monkeypatch.setattr(verifier, "REPS", 100)
    summary, pairs, tasks = producer.analyze(
        inputs["cards"], inputs["train"], inputs["dev"], inputs["test"],
        inputs["draft"], inputs["improve"],
    )
    output = tmp_path / "output"
    producer.write_outputs(output, summary, pairs, tasks)
    receipt = verifier.verify(
        inputs["cards"], inputs["train"], inputs["dev"], inputs["test"],
        inputs["draft"], inputs["improve"], output,
    )
    assert receipt["status"] == "BASELINE_INDEPENDENTLY_VERIFIED"
    assert receipt["max_abs_margin_difference"] == 0.0
    assert receipt["max_abs_metric_difference"] == 0.0


def test_verifier_rejects_tampered_margin(tmp_path, monkeypatch):
    inputs, expected = build_fixture(tmp_path)
    monkeypatch.setattr(producer, "EXPECTED", expected)
    monkeypatch.setattr(verifier, "EXPECTED", expected)
    monkeypatch.setattr(producer, "BOOTSTRAP_REPS", 100)
    monkeypatch.setattr(verifier, "REPS", 100)
    summary, pairs, tasks = producer.analyze(
        inputs["cards"], inputs["train"], inputs["dev"], inputs["test"],
        inputs["draft"], inputs["improve"],
    )
    output = tmp_path / "output"
    producer.write_outputs(output, summary, pairs, tasks)
    pair_rows = verifier.read_jsonl(output / "per_pair.jsonl")
    pair_rows[0]["margin"] += 0.1
    write_jsonl(output / "per_pair.jsonl", pair_rows)
    with pytest.raises(verifier.VerificationError, match="margin"):
        verifier.verify(
            inputs["cards"], inputs["train"], inputs["dev"], inputs["test"],
            inputs["draft"], inputs["improve"], output,
        )


def test_verifier_source_does_not_import_producer():
    assert "critic_component_tfidf_baseline" not in inspect.getsource(verifier)
