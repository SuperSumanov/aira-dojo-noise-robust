from __future__ import annotations

import argparse
import csv
import hashlib
from pathlib import Path

import phase1.balanced_continuation_e2a_split as split


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_task(root: Path, task: str, mode: str, rows: int) -> dict:
    public = root / task / "prepared" / "public"
    public.mkdir(parents=True)
    train = public / "train.csv"
    description = public / "description.md"
    if mode == "exact_target":
        header = ["id", "feature", "target"]
        with train.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, lineterminator="\n"); writer.writerow(header)
            for index in range(rows):
                writer.writerow([f"{task}-{index}", index, str(index % 2)])
        spec = {
            "id_column": "id", "target_columns": ["target"],
            "submission_columns": ["target"], "sample_defaults": ["0.5"],
            "metric": "roc_auc", "orientation": 1, "split": mode,
            "allowed": {"0", "1"}, "source_rows": rows,
        }
    else:
        header = ["id", "feature", "formation", "bandgap"]
        with train.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, lineterminator="\n"); writer.writerow(header)
            for index in range(rows):
                writer.writerow([f"{task}-{index}", index, index / rows, (rows - index) / rows])
        spec = {
            "id_column": "id", "target_columns": ["formation", "bandgap"],
            "submission_columns": ["formation", "bandgap"],
            "sample_defaults": ["0.1", "1.0"], "metric": "mean_columnwise_rmsle",
            "orientation": -1, "split": mode, "source_rows": rows,
        }
    description.write_text(f"description {task}\n", encoding="utf-8")
    spec["train_sha256"] = sha(train); spec["description_sha256"] = sha(description)
    # Forbidden conventional inputs exist but must not influence the build.
    (public / "test.csv").write_text("forbidden\n", encoding="utf-8")
    (public / "sample_submission.csv").write_text("forbidden\n", encoding="utf-8")
    return spec


def configure(tmp_path: Path, monkeypatch) -> Path:
    source = tmp_path / "source"
    specs = {
        "categorical": write_task(source, "categorical", "exact_target", 40),
        "regression": write_task(source, "regression", "formation_energy_rank_decile", 200),
    }
    monkeypatch.setattr(split, "TASK_SPECS", specs)
    monkeypatch.setattr(split, "TASK_ORDER", tuple(specs))
    return source


def test_e2a_split_is_deterministic_and_never_opens_official_test(tmp_path: Path, monkeypatch) -> None:
    source = configure(tmp_path, monkeypatch)
    first = (tmp_path / "first").resolve(); second = (tmp_path / "second").resolve()
    a = split.build(argparse.Namespace(source_root=str(source), output=str(first)))
    b = split.build(argparse.Namespace(source_root=str(source), output=str(second)))
    assert a["dtest_rows_read"] == b["dtest_rows_read"] == 0
    assert a["official_sample_submission_read"] is b["official_sample_submission_read"] is False
    first_hashes = {path.relative_to(first).as_posix(): sha(path) for path in first.rglob("*") if path.is_file()}
    second_hashes = {path.relative_to(second).as_posix(): sha(path) for path in second.rglob("*") if path.is_file()}
    assert first_hashes == second_hashes
    assert a["counts"]["categorical"] == {
        "source": 40, "train": 32, "dsearch": 4, "dval": 4,
        "strata": {
            "0": {"source": 20, "train": 16, "dsearch": 2, "dval": 2},
            "1": {"source": 20, "train": 16, "dsearch": 2, "dval": 2},
        },
    }
    regression_counts = a["counts"]["regression"]
    assert regression_counts["source"] == 200
    assert regression_counts["train"] == 160
    assert regression_counts["dsearch"] == regression_counts["dval"] == 20
    assert len(regression_counts["strata"]) == 10


def test_source_hash_tamper_fails_before_promotion(tmp_path: Path, monkeypatch) -> None:
    source = configure(tmp_path, monkeypatch)
    train = source / "categorical" / "prepared" / "public" / "train.csv"
    train.write_bytes(train.read_bytes() + b"tamper\n")
    try:
        split.build(argparse.Namespace(source_root=str(source), output=str((tmp_path / "out").resolve())))
    except split.SplitError as exc:
        assert "SHA differs" in str(exc)
    else:
        raise AssertionError("tampered source unexpectedly passed")
