import hashlib
import importlib
import inspect
import json
from pathlib import Path

import numpy as np
import pytest


pytest.importorskip("sklearn")

producer = importlib.import_module("phase1.critic_component_static_suite")
verifier = importlib.import_module("phase1.verify_critic_component_static_suite")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


def pair(task: str, parent: str, better: str, worse: str, split: str, component: str | None = None) -> dict:
    output = {
        "better": better, "worse": worse, "task": task, "parent": parent,
        "budget": 0, "clears_tau": None, "gap_raw": .1, "intask_split": split,
        "loto_fold": task, "set_size": 2, "src": "decision",
    }
    if split in {"train", "dev"}:
        output |= {
            "outer_intask_split": "train",
            "train_dev_protocol": "pair-graph-component-train-dev-split-v1",
            "train_dev_seed": 20260821,
            "train_dev_target_numerator": 1,
            "train_dev_target_denominator": 10,
            "pair_component_id": component,
        }
    return output


def source_form(row: dict) -> dict:
    output = dict(row)
    for name in (
        "outer_intask_split", "train_dev_protocol", "train_dev_seed",
        "train_dev_target_numerator", "train_dev_target_denominator", "pair_component_id",
    ):
        output.pop(name, None)
    if output["intask_split"] == "dev":
        output["intask_split"] = "train"
    return output


def make_card(card_id: str, task: str, favorable: bool, ordinal: int) -> dict:
    if favorable:
        code = (
            "import sklearn\nfrom xgboost import XGBClassifier\n"
            "seed random_state ensemble blend stack mean( kfold cross_val early_stop "
            "optuna param_grid augment transform try: print( cuda # robust\n"
            f"n_splits={3 + ordinal % 4}\nepochs={5 + ordinal % 7}\n"
        )
    else:
        code = f"import pandas\nprint('baseline-{ordinal}')\n"
    return {
        "id": card_id, "task": {"name": task}, "code": code,
        "lineage": {"depth": 2 + favorable, "step": ordinal + favorable, "n_siblings": 2},
        "client": "client", "hardware": "gpu", "time_limit": 120,
        "execution_timeout": 120,
        "obs": {"stdout": "must-not-be-read"}, "label": "must-not-be-read",
        "runtime": 999, "parent_val": 1.0,
    }


def build_fixture(tmp_path: Path):
    rows = {"train": [], "dev": [], "test": []}
    grouped = {}
    ordinal = 0
    for task_index, task in enumerate(("task-a", "task-b")):
        for split, count in (("train", 12), ("dev", 3), ("test", 3)):
            for index in range(count):
                ordinal += 1
                better = f"{split}-{task_index}-{index}-better"
                worse = f"{split}-{task_index}-{index}-worse"
                component = hashlib.sha256(f"{split}-{task}".encode()).hexdigest() if split != "test" else None
                record = pair(task, f"parent-{split}-{task_index}-{index}", better, worse, split, component)
                rows[split].append(record)
                grouped[f"run-{better}"] = [make_card(better, task, True, ordinal)]
                grouped[f"run-{worse}"] = [make_card(worse, task, False, ordinal)]

    paths = {name: tmp_path / f"{name}.jsonl" for name in rows}
    for name, path in paths.items():
        write_jsonl(path, rows[name])
    cards_path = tmp_path / "cards.json"
    cards_path.write_text(json.dumps(grouped, sort_keys=True), encoding="utf-8")
    source_rows = [source_form(row) for split in ("train", "dev", "test") for row in rows[split]]
    draft_path, improve_path = tmp_path / "draft.jsonl", tmp_path / "improve.jsonl"
    write_jsonl(draft_path, source_rows[::2])
    write_jsonl(improve_path, source_rows[1::2])
    tfidf_path = tmp_path / "tfidf.jsonl"
    tfidf_rows = []
    for split in ("dev", "test"):
        for index, row in enumerate(rows[split]):
            tfidf_rows.append({
                "split": split, "index": index, "task": row["task"], "parent": row["parent"],
                "better": row["better"], "worse": row["worse"], "correct": False, "tie": False,
            })
    write_jsonl(tfidf_path, tfidf_rows)
    inputs = {
        "cards": cards_path, "train": paths["train"], "dev": paths["dev"], "test": paths["test"],
        "draft": draft_path, "improve": improve_path,
    }
    expected = {name: (sha(path), path.stat().st_size) for name, path in inputs.items()}
    return inputs, tfidf_path, expected


def patch_fixture(monkeypatch, expected: dict, tfidf_path: Path) -> None:
    monkeypatch.setattr(producer, "EXPECTED", expected)
    monkeypatch.setattr(verifier, "EXPECTED", expected)
    monkeypatch.setattr(producer, "TFIDF_PAIR_SHA256", sha(tfidf_path))
    monkeypatch.setattr(verifier, "TFIDF_SHA256", sha(tfidf_path))
    monkeypatch.setattr(producer, "BOOTSTRAP_REPS", 50)
    monkeypatch.setattr(verifier, "REPS", 50)


def test_feature_contract_uses_exact_34_decision_time_fields():
    card = make_card("x", "task", True, 2)
    card["obs"] = object()
    card["label"] = object()
    observed = producer.feature_dict(card)
    assert tuple(sorted(observed)) == producer.FEATURE_NAMES
    assert len(observed) == 34
    assert not ({"obs", "label", "runtime", "stdout", "parent_val"} & set(observed))
    assert observed["n_cv"] > 0
    assert observed["m_xgboost"] == 1.0


def test_lr_is_zero_intercept_and_explicitly_antisymmetric():
    values = np.asarray([[1., 2.], [3., -1.], [-2., 4.], [5., 3.]])
    scaler, model, receipt = producer.lr_fit(values)
    forward = producer.lr_margin(values, scaler, model)
    reverse = producer.lr_margin(-values, scaler, model)
    assert receipt["fit_intercept"] is False
    assert model.fit_intercept is False
    assert np.max(np.abs(forward + reverse)) <= 1e-12


def test_gbm_scores_both_orientations_before_antisymmetrizing():
    base = np.arange(24, dtype=np.float64).reshape(-1, 1) + 1
    values = np.hstack((base, base % 5, np.ones_like(base)))
    model, _ = producer.gbm_fit(values)
    forward = producer.gbm_margin(values, -values, model)
    reverse = producer.gbm_margin(-values, values, model)
    assert np.max(np.abs(forward + reverse)) <= 1e-12


def test_task_routing_marks_unknown_without_fallback():
    rows = [{"task": "known"}, {"task": "unknown"}]
    values = np.ones((2, 34))
    interactions, known_lr = producer.task_interactions(values, rows, {"known": 0})
    conditioned, known_gbm = producer.task_conditioned(values, rows, {"known": 0})
    assert known_lr.tolist() == [True, False]
    assert known_gbm.tolist() == [True, False]
    assert np.all(interactions[1, 34:] == 0)
    assert np.all(conditioned[1, 34:] == 0)


def test_champion_tie_break_is_frozen_order():
    scores = {name: .6 for name in producer.LEARNED_MODELS}
    assert producer.select_champion(scores) == "static_lr_pooled"
    scores["static_lr_task"] = .6000000000005
    assert producer.select_champion(scores) == "static_lr_pooled"
    scores["static_lr_task"] = .600000000002
    assert producer.select_champion(scores) == "static_lr_task"


def test_paired_bootstrap_is_deterministic(monkeypatch):
    monkeypatch.setattr(producer, "BOOTSTRAP_REPS", 50)
    rows = [
        {"task": "a", "parent": "p1"}, {"task": "a", "parent": "p2"},
        {"task": "b", "parent": "p3"}, {"task": "b", "parent": "p4"},
    ]
    delta = np.asarray([1., 0., -1., 1.])
    assert producer.paired_delta_ci(rows, delta, "task") == producer.paired_delta_ci(rows, delta, "task")
    assert producer.paired_delta_ci(rows, delta, "parent") == producer.paired_delta_ci(rows, delta, "parent")


def test_producer_and_independent_full_refit_agree(tmp_path, monkeypatch):
    inputs, tfidf_path, expected = build_fixture(tmp_path)
    patch_fixture(monkeypatch, expected, tfidf_path)
    summary, pairs, tasks, parents = producer.analyze(
        inputs["cards"], inputs["train"], inputs["dev"], inputs["test"],
        inputs["draft"], inputs["improve"], tfidf_path,
    )
    output = tmp_path / "output"
    producer.write_outputs(output, summary, pairs, tasks, parents)
    receipt = verifier.verify(
        inputs["cards"], inputs["train"], inputs["dev"], inputs["test"],
        inputs["draft"], inputs["improve"], tfidf_path, output,
    )
    assert receipt["full_refit"] is True
    assert receipt["producer_imported"] is False
    assert receipt["max_abs_summary_difference"] == 0.0
    assert receipt["max_abs_pair_difference"] == 0.0


def test_hash_gate_and_tamper_detection(tmp_path, monkeypatch):
    inputs, tfidf_path, expected = build_fixture(tmp_path)
    patch_fixture(monkeypatch, expected, tfidf_path)
    summary, pairs, tasks, parents = producer.analyze(
        inputs["cards"], inputs["train"], inputs["dev"], inputs["test"],
        inputs["draft"], inputs["improve"], tfidf_path,
    )
    output = tmp_path / "output"
    producer.write_outputs(output, summary, pairs, tasks, parents)
    pair_rows = verifier.read_artifact_jsonl(output / "per_pair.jsonl")
    pair_rows[0]["margin"] += .1
    write_jsonl(output / "per_pair.jsonl", pair_rows)
    with pytest.raises(verifier.VerificationError):
        verifier.verify(
            inputs["cards"], inputs["train"], inputs["dev"], inputs["test"],
            inputs["draft"], inputs["improve"], tfidf_path, output,
        )
    inputs["train"].write_text(inputs["train"].read_text() + "\n")
    with pytest.raises(Exception, match="identity mismatch"):
        producer.analyze(
            inputs["cards"], inputs["train"], inputs["dev"], inputs["test"],
            inputs["draft"], inputs["improve"], tfidf_path,
        )


def test_verifier_source_does_not_import_producer():
    source = inspect.getsource(verifier)
    assert "critic_component_static_suite" not in source
    assert "from phase1" not in source
