from __future__ import annotations

import hashlib
import importlib
import inspect
import json
import math
from pathlib import Path

import numpy as np
import pytest


pytest.importorskip("sklearn")

producer = importlib.import_module("phase1.critic_transition_static_component_oof")
verifier = importlib.import_module("phase1.verify_critic_transition_static_component_oof")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def component(name: str) -> str:
    return hashlib.sha256(name.encode()).hexdigest()


def pair(task: str, parent: str, better: str, worse: str, split: str, component_id: str):
    return {
        "better": better,
        "intask_split": split,
        "outer_intask_split": "train",
        "pair_component_id": component_id,
        "parent": parent,
        "src": "decision",
        "task": task,
        "train_dev_protocol": "pair-graph-component-train-dev-split-v1",
        "train_dev_seed": 20260821,
        "train_dev_target_denominator": 10,
        "train_dev_target_numerator": 1,
        "worse": worse,
        "grade": 123.0,
        "gap_raw": -456.0,
    }


def card(card_id: str, task: str, code: str, ordinal: int):
    return {
        "id": card_id,
        "task": {"name": task},
        "code": code,
        "lineage": {"depth": ordinal % 3, "step": ordinal, "n_siblings": 2},
        "client": "client",
        "hardware": "gpu",
        "time_limit": 120,
        "execution_timeout": 120,
        "obs": {"stdout": "must be ignored"},
        "parent_val": 999.0,
    }


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


def fixture(tmp_path: Path):
    rows = []
    groups = {}
    parents_written = set()
    for index in range(12):
        task = "task-a" if index < 7 else "task-b"
        split = "train" if index < 8 else "dev"
        parent = "shared-parent" if index in (0, 1) else f"parent-{index}"
        better, worse = f"better-{index}", f"worse-{index}"
        rows.append(pair(task, parent, better, worse, split, component(f"component-{index}")))
        parent_task = "task-a" if parent == "shared-parent" else task
        if parent not in parents_written:
            groups[f"run-{parent}"] = [
                card(parent, parent_task, f"import pandas\nprint('parent-{index}')\n", 100 + index)
            ]
            parents_written.add(parent)
        groups[f"run-{better}"] = [
            card(
                better,
                task,
                f"import sklearn\nfrom xgboost import XGBClassifier\nseed random_state\n# {index}\n",
                index,
            )
        ]
        groups[f"run-{worse}"] = [
            card(worse, task, f"import pandas\nprint('baseline-{index}')\n", index + 20)
        ]

    train = tmp_path / "train.jsonl"
    dev = tmp_path / "dev.jsonl"
    draft = tmp_path / "draft.jsonl"
    improve = tmp_path / "improve.jsonl"
    cards = tmp_path / "cards.json"
    write_jsonl(train, [row for row in rows if row["intask_split"] == "train"])
    write_jsonl(dev, [row for row in rows if row["intask_split"] == "dev"])
    write_jsonl(draft, rows[::2])
    write_jsonl(improve, rows[1::2])
    cards.write_text(json.dumps(groups, sort_keys=True), encoding="utf-8")
    expected = {
        "cards": (digest(cards), cards.stat().st_size),
        "train": (digest(train), train.stat().st_size),
        "dev": (digest(dev), dev.stat().st_size),
    }
    semantic_expected = {
        "draft": (digest(draft), draft.stat().st_size),
        "improve": (digest(improve), improve.stat().st_size),
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
    return cards, train, dev, draft, improve, expected, semantic_expected, counts


def configure(monkeypatch, expected, semantic_expected, counts):
    monkeypatch.setattr(producer.base, "EXPECTED", expected)
    monkeypatch.setattr(producer.base, "EXPECTED_COUNTS", counts)
    monkeypatch.setattr(verifier.independent_base, "EXPECTED", expected)
    monkeypatch.setattr(verifier.independent_base, "EXPECTED_COUNTS", counts)
    monkeypatch.setattr(producer, "EXPECTED_SEMANTIC", semantic_expected)
    monkeypatch.setattr(verifier, "EXPECTED_SEMANTIC", semantic_expected)
    monkeypatch.setattr(producer, "EXPECTED_SEMANTIC_COUNTS", {"Draft": 6, "Improve": 6})
    monkeypatch.setattr(verifier, "EXPECTED_SEMANTIC_COUNTS", {"Draft": 6, "Improve": 6})
    monkeypatch.setattr(producer, "REPS", 30)
    monkeypatch.setattr(verifier, "REPS", 30)


def test_edit_shape_contract_is_exact():
    values = producer.edit_shape("a\nb\n", "a\nc\nd\n")
    assert values[:3].tolist() == [2.0, 1.0, 1.0]
    assert values[3] == .5
    assert values[4] == pytest.approx(1 / 3)
    assert values[5] == pytest.approx(abs(math.log1p(6) - math.log1p(4)))


def test_pair_transition_difference_is_antisymmetric():
    rows = [{"parent": "p", "better": "a", "worse": "b"}]
    vectors = {
        "p": np.zeros(31),
        "a": np.arange(31, dtype=float),
        "b": np.arange(31, dtype=float)[::-1],
    }
    sources = {"p": "x\n", "a": "x\ny\n", "b": "z\n"}
    forward, _ = producer.feature_matrices(rows, vectors, sources)
    rows[0]["better"], rows[0]["worse"] = rows[0]["worse"], rows[0]["better"]
    reverse, _ = producer.feature_matrices(rows, vectors, sources)
    assert all(np.array_equal(forward[name], -reverse[name]) for name in producer.ARMS)


def test_producer_and_independent_full_refit_match(tmp_path, monkeypatch):
    cards, train, dev, draft, improve, expected, semantic_expected, counts = fixture(tmp_path)
    configure(monkeypatch, expected, semantic_expected, counts)
    result = producer.analyze(cards, train, dev, draft, improve)
    artifact = tmp_path / "artifact"
    producer.write_outputs(artifact, *result)
    receipt = verifier.verify(cards, train, dev, draft, improve, artifact)
    assert receipt["producer_imported"] is False
    assert receipt["full_refit"] is True
    assert receipt["all_fields_exact"] is True


def test_artifact_tamper_is_rejected(tmp_path, monkeypatch):
    cards, train, dev, draft, improve, expected, semantic_expected, counts = fixture(tmp_path)
    configure(monkeypatch, expected, semantic_expected, counts)
    result = producer.analyze(cards, train, dev, draft, improve)
    artifact = tmp_path / "artifact"
    producer.write_outputs(artifact, *result)
    summary = json.loads((artifact / "summary.json").read_text())
    summary["semantic_counts"]["Draft"] += 1
    (artifact / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    with pytest.raises(verifier.TransitionVerificationError, match="manifest mismatch"):
        verifier.verify(cards, train, dev, draft, improve, artifact)


def test_verifier_does_not_import_transition_producer_and_cli_has_no_test_argument():
    source = inspect.getsource(verifier)
    assert "critic_transition_static_component_oof" not in source
    main_source = inspect.getsource(producer.main)
    assert 'add_argument("test"' not in main_source
    assert 'add_argument("tfidf"' not in main_source
    assert 'add_argument("prospective"' not in main_source
