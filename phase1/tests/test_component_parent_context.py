from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from phase1 import audit_component_parent_context as producer
from phase1 import verify_component_parent_context as verifier


ROLES = ("cards", "train", "dev", "test", "draft", "improve")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def card(card_id: str, parent: str | None, code: str) -> dict:
    return {"id": card_id, "code": code, "lineage": {"parent_id": parent}}


def row(split: str, parent: str, better: str, worse: str, semantic: str) -> dict:
    return {
        "task": "task-a",
        "parent": parent,
        "better": better,
        "worse": worse,
        "src": "synthetic_" + semantic.lower(),
        "intask_split": split,
        "grade": 999.0,
        "gap": -999.0,
    }


def fixture(
    root: Path,
    *,
    reverse: bool = False,
    improve_overlap: bool = False,
    endpoint_code_overlap: bool = False,
) -> dict[str, Path]:
    root.mkdir(parents=True, exist_ok=True)
    train = [
        row("train", "p-shared", "train-a", "train-b", "Draft"),
        row("train", "p-improve-train", "improve-a", "improve-b", "Improve"),
    ]
    dev = [row("dev", "p-dev", "dev-a", "dev-b", "Draft")]
    test = [
        row("test", "p-shared", "test-a", "test-b", "Draft"),
        row(
            "test",
            "p-improve-train" if improve_overlap else "p-improve-test",
            "test-improve-a",
            "test-improve-b",
            "Improve",
        ),
    ]
    draft = [train[0], dev[0], test[0]]
    improve = [train[1], test[1]]
    groups = {
        "run-parent-shared": [card("p-shared", None, "parent shared")],
        "run-parent-improve-train": [card("p-improve-train", None, "parent improve train")],
        "run-parent-improve-test": [card("p-improve-test", None, "parent improve test")],
        "run-parent-dev": [card("p-dev", None, "parent dev")],
    }
    endpoint_specs = [
        ("train-a", "p-shared", "train code a"),
        ("train-b", "p-shared", "train code b"),
        ("improve-a", "p-improve-train", "improve code a"),
        ("improve-b", "p-improve-train", "improve code b"),
        ("dev-a", "p-dev", "dev code a"),
        ("dev-b", "p-dev", "dev code b"),
        ("test-a", "p-shared", "train code a" if endpoint_code_overlap else "test code a"),
        ("test-b", "p-shared", "test code b"),
        (
            "test-improve-a",
            "p-improve-train" if improve_overlap else "p-improve-test",
            "test improve code a",
        ),
        (
            "test-improve-b",
            "p-improve-train" if improve_overlap else "p-improve-test",
            "test improve code b",
        ),
    ]
    for card_id, parent, code_text in endpoint_specs:
        groups["run-" + card_id] = [card(card_id, parent, code_text)]
    if reverse:
        groups = dict(reversed(list(groups.items())))
        train.reverse()
        dev.reverse()
        test.reverse()
        draft.reverse()
        improve.reverse()

    paths = {role: root / f"{role}.jsonl" for role in ROLES}
    paths["cards"].write_text(json.dumps(groups, sort_keys=False), encoding="utf-8")
    for role, rows in (("train", train), ("dev", dev), ("test", test), ("draft", draft), ("improve", improve)):
        write_jsonl(paths[role], rows)
    return paths


def identities(paths: dict[str, Path]) -> dict[str, tuple[str, int]]:
    return {
        role: (hashlib.sha256(paths[role].read_bytes()).hexdigest(), paths[role].stat().st_size)
        for role in ROLES
    }


def configure(monkeypatch: pytest.MonkeyPatch, paths: dict[str, Path]) -> None:
    expected = identities(paths)
    monkeypatch.setattr(producer, "EXPECTED", expected)
    monkeypatch.setattr(verifier, "EXPECTED", expected)


def run_producer(paths: dict[str, Path]) -> dict:
    return producer.analyze(*(paths[name] for name in ROLES))


def test_independent_verifier_exactly_reconstructs_producer(tmp_path, monkeypatch):
    paths = fixture(tmp_path)
    configure(monkeypatch, paths)
    summary = run_producer(paths)
    artifact = tmp_path / "producer.json"
    producer.write_output(artifact, summary)
    receipt = verifier.verify(paths, artifact)
    assert receipt["all_fields_exact_match"] is True
    assert receipt["context_overlap_claim_allowed"] is True
    assert receipt["producer_imported"] is False


def test_structural_result_is_order_invariant_and_ignores_outcomes(tmp_path, monkeypatch):
    first_paths = fixture(tmp_path / "first")
    second_paths = fixture(tmp_path / "second", reverse=True)
    first_expected = identities(first_paths)
    second_expected = identities(second_paths)
    monkeypatch.setattr(producer, "EXPECTED", first_expected)
    first = run_producer(first_paths)
    monkeypatch.setattr(producer, "EXPECTED", second_expected)
    second = run_producer(second_paths)
    first.pop("inputs")
    second.pop("inputs")
    assert first == second
    assert first["outcome_fields_used"] is False


def test_verifier_rejects_tampered_producer_artifact(tmp_path, monkeypatch):
    paths = fixture(tmp_path)
    configure(monkeypatch, paths)
    summary = run_producer(paths)
    summary["parent_overlaps"]["outer_train_test"]["parents"] += 1
    artifact = tmp_path / "tampered.json"
    artifact.write_text(json.dumps(summary), encoding="utf-8")
    with pytest.raises(verifier.IndependentVerificationError, match="differs"):
        verifier.verify(paths, artifact)


@pytest.mark.parametrize(
    "variant",
    ("improve_overlap", "endpoint_code_overlap"),
)
def test_fixed_boundary_gates_reject_counterexamples(tmp_path, monkeypatch, variant):
    options = {variant: True}
    paths = fixture(tmp_path, **options)
    configure(monkeypatch, paths)
    with pytest.raises(producer.ParentAuditError, match="gates changed"):
        run_producer(paths)
