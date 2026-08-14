from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import pytest

import phase1.balanced_continuation_e1_split as producer
import phase1.verify_balanced_continuation_e1_split as verifier


TASKS = ("spaceship-titanic", "tabular-playground-series-may-2022")


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_source(root: Path, task: str, rows: int = 40) -> tuple[Path, Path]:
    public = root / task / "prepared" / "public"
    public.mkdir(parents=True)
    train = public / "train.csv"
    description = public / "description.md"
    id_column = "PassengerId" if task == TASKS[0] else "id"
    target = "Transported" if task == TASKS[0] else "target"
    labels = ("False", "True") if task == TASKS[0] else ("0", "1")
    with train.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=[id_column, "feature", target], lineterminator="\n"
        )
        writer.writeheader()
        for index in range(rows):
            writer.writerow({id_column: f"{task}-{index}", "feature": index, target: labels[index % 2]})
    description.write_text(f"public description for {task}\n", encoding="utf-8")
    # A deliberately malformed file with the forbidden conventional name must be ignored.
    (public / "test.csv").write_bytes(b"THIS FILE MUST NOT BE OPENED\n")
    return train, description


def configure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    source = tmp_path / "source"
    producer_specs = {}
    verifier_specs = {}
    for task in TASKS:
        train, description = write_source(source, task)
        if task == TASKS[0]:
            ident, target, labels, metric, default = (
                "PassengerId", "Transported", {"True", "False"}, "accuracy", "False"
            )
        else:
            ident, target, labels, metric, default = "id", "target", {"0", "1"}, "roc_auc", "0.5"
        producer_specs[task] = {
            "id_column": ident,
            "target_column": target,
            "metric": metric,
            "orientation": 1,
            "sample_default": default,
            "allowed_labels": labels,
            "source_rows": 40,
            "train_sha256": file_sha(train),
            "description_sha256": file_sha(description),
        }
        verifier_specs[task] = {
            "id": ident,
            "target": target,
            "metric": metric,
            "orientation": 1,
            "default": default,
            "labels": labels,
            "rows": 40,
            "train_sha": file_sha(train),
            "description_sha": file_sha(description),
        }
    monkeypatch.setattr(producer, "TASK_SPECS", producer_specs)
    monkeypatch.setattr(verifier, "SPECS", verifier_specs)
    return source


def test_split_and_independent_reconstruction(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = configure(tmp_path, monkeypatch)
    result = (tmp_path / "result").resolve()
    summary = producer.build(argparse.Namespace(source_root=str(source), output=str(result)))
    receipt = verifier.verify(argparse.Namespace(
        source_root=str(source), result=str(result), receipt=str(tmp_path / "receipt.json")
    ))
    assert summary["dtest_rows_read"] == 0
    assert receipt["status"] == "VERIFIED_E1_SPLIT_RECONSTRUCTION_NO_DTEST_READ"
    for task in TASKS:
        public = result / "public" / task
        target = "Transported" if task == TASKS[0] else "target"
        with (public / "test.csv").open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            assert target not in (reader.fieldnames or [])
            assert sum(1 for _ in reader) == 8
        with (public / "train.csv").open(encoding="utf-8", newline="") as handle:
            assert sum(1 for _ in csv.DictReader(handle)) == 32


def test_split_is_byte_deterministic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = configure(tmp_path, monkeypatch)
    first, second = (tmp_path / "first").resolve(), (tmp_path / "second").resolve()
    producer.build(argparse.Namespace(source_root=str(source), output=str(first)))
    producer.build(argparse.Namespace(source_root=str(source), output=str(second)))
    first_files = {p.relative_to(first).as_posix(): file_sha(p) for p in first.rglob("*") if p.is_file()}
    second_files = {p.relative_to(second).as_posix(): file_sha(p) for p in second.rglob("*") if p.is_file()}
    assert first_files == second_files


def test_private_label_tamper_is_detected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = configure(tmp_path, monkeypatch)
    result = (tmp_path / "result").resolve()
    producer.build(argparse.Namespace(source_root=str(source), output=str(result)))
    private = result / "private" / "dval" / f"{TASKS[0]}.csv"
    private.write_bytes(private.read_bytes() + b"tamper\n")
    with pytest.raises(verifier.VerifySplitError):
        verifier.verify(argparse.Namespace(
            source_root=str(source), result=str(result), receipt=str(tmp_path / "receipt.json")
        ))


def test_source_hash_change_fails_before_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = configure(tmp_path, monkeypatch)
    train = source / TASKS[0] / "prepared" / "public" / "train.csv"
    train.write_bytes(train.read_bytes() + b"\n")
    with pytest.raises(producer.SplitError, match="SHA differs"):
        producer.build(argparse.Namespace(source_root=str(source), output=str((tmp_path / "result").resolve())))
