"""Strict submission scoring shared by the isolated E1 evaluator sidecars."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import pathlib
import re
import tempfile
from typing import Any


TASK_SPECS = {
    "spaceship-titanic": {
        "id_column": "PassengerId",
        "target_column": "Transported",
        "metric": "accuracy",
        "orientation": 1,
    },
    "tabular-playground-series-may-2022": {
        "id_column": "id",
        "target_column": "target",
        "metric": "roc_auc",
        "orientation": 1,
    },
}
CREDENTIAL = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|"
    rb"gh[pousr]_[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|"
    rb"Bearer[ \t]+[A-Za-z0-9._-]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)


class ScoreError(RuntimeError):
    pass


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def file_sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def evaluator_bundle_sha256(wrapper_path: pathlib.Path) -> str:
    common = pathlib.Path(__file__).resolve()
    wrapper = wrapper_path.resolve()
    bundle = {
        "common": {"name": common.name, "sha256": file_sha256(common)},
        "wrapper": {"name": wrapper.name, "sha256": file_sha256(wrapper)},
    }
    return sha256_bytes(canonical_json(bundle))


def checked_json(path: pathlib.Path) -> dict[str, Any]:
    raw = path.read_bytes()
    if CREDENTIAL.search(raw):
        raise ScoreError(f"credential-shaped bytes refused: {path.name}")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ScoreError(f"expected JSON object: {path}")
    return value


def atomic_json(path: pathlib.Path, value: Any, mode: int | None = None) -> None:
    if path.exists() or path.is_symlink():
        raise ScoreError(f"refusing existing output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = pathlib.Path(name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(canonical_json(value) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        if mode is not None:
            os.chmod(temporary, mode)
        os.replace(temporary, path)
        if mode is not None:
            os.chmod(path, mode)
    finally:
        if temporary.exists():
            temporary.unlink()


def parse_boolean(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"true", "1"}:
        return True
    if normalized in {"false", "0"}:
        return False
    raise ValueError("not a strict boolean")


def load_labels(path: pathlib.Path, task: str) -> tuple[list[str], list[bool | int]]:
    spec = TASK_SPECS[task]
    ids: list[str] = []
    labels: list[bool | int] = []
    seen: set[str] = set()
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        expected_header = [spec["id_column"], spec["target_column"]]
        if list(reader.fieldnames or []) != expected_header:
            raise ScoreError("private label header differs")
        for row in reader:
            row_id = row[spec["id_column"]]
            if not row_id or row_id in seen:
                raise ScoreError("private labels contain empty/duplicate ids")
            seen.add(row_id)
            ids.append(row_id)
            if spec["metric"] == "accuracy":
                try:
                    labels.append(parse_boolean(row[spec["target_column"]]))
                except ValueError as exc:
                    raise ScoreError("private accuracy label is invalid") from exc
            else:
                raw = row[spec["target_column"]].strip()
                if raw not in {"0", "1"}:
                    raise ScoreError("private AUC label is invalid")
                labels.append(int(raw))
    if not ids:
        raise ScoreError("private label file is empty")
    return ids, labels


def load_predictions(
    path: pathlib.Path, task: str, expected_ids: list[str]
) -> tuple[list[bool | float] | None, str | None]:
    if not path.is_file():
        return None, "submission_missing"
    raw = path.read_bytes()
    if CREDENTIAL.search(raw):
        return None, "credential_shape_in_submission"
    spec = TASK_SPECS[task]
    expected_header = [spec["id_column"], spec["target_column"]]
    try:
        text = raw.decode("utf-8-sig")
        rows = list(csv.DictReader(text.splitlines()))
        reader = csv.DictReader(text.splitlines())
    except (UnicodeDecodeError, csv.Error):
        return None, "submission_csv_parse_error"
    if list(reader.fieldnames or []) != expected_header:
        return None, "submission_header_mismatch"
    if len(rows) != len(expected_ids):
        return None, "submission_row_count_mismatch"
    by_id: dict[str, str] = {}
    for row in rows:
        row_id = row.get(spec["id_column"], "")
        if not row_id or row_id in by_id or set(row) != set(expected_header):
            return None, "submission_id_or_schema_invalid"
        by_id[row_id] = row[spec["target_column"]]
    if set(by_id) != set(expected_ids):
        return None, "submission_id_set_mismatch"
    predictions: list[bool | float] = []
    try:
        for row_id in expected_ids:
            raw_value = by_id[row_id]
            if spec["metric"] == "accuracy":
                predictions.append(parse_boolean(raw_value))
            else:
                value = float(raw_value)
                if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                    raise ValueError("probability outside [0,1]")
                predictions.append(value)
    except (ValueError, TypeError):
        return None, "submission_prediction_invalid"
    return predictions, None


def rank_auc(labels: list[int], predictions: list[float]) -> float:
    positive = sum(labels)
    negative = len(labels) - positive
    if positive == 0 or negative == 0:
        raise ScoreError("AUC labels contain only one class")
    order = sorted(range(len(predictions)), key=lambda index: predictions[index])
    rank_sum_positive = 0.0
    cursor = 0
    while cursor < len(order):
        end = cursor + 1
        score = predictions[order[cursor]]
        while end < len(order) and predictions[order[end]] == score:
            end += 1
        average_rank = ((cursor + 1) + end) / 2.0
        rank_sum_positive += average_rank * sum(labels[index] for index in order[cursor:end])
        cursor = end
    return (rank_sum_positive - positive * (positive + 1) / 2.0) / (positive * negative)


def score_submission(artifact: pathlib.Path, labels_path: pathlib.Path, task: str) -> dict[str, Any]:
    if task not in TASK_SPECS:
        raise ScoreError("unsupported E1 task")
    ids, labels = load_labels(labels_path, task)
    predictions, failure = load_predictions(artifact, task, ids)
    if predictions is None:
        return {
            "submission_valid": False,
            "score": None,
            "row_count": len(ids),
            "failure_reason": failure,
        }
    spec = TASK_SPECS[task]
    if spec["metric"] == "accuracy":
        score = sum(bool(pred) == bool(label) for pred, label in zip(predictions, labels)) / len(labels)
    else:
        score = rank_auc([int(value) for value in labels], [float(value) for value in predictions])
    if not math.isfinite(score):
        raise ScoreError("scorer produced a non-finite score")
    return {
        "submission_valid": True,
        "score": float(score),
        "row_count": len(ids),
        "failure_reason": None,
    }
