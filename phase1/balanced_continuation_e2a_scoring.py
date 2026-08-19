"""Strict six-task scoring for balanced-continuation E2-A sidecars."""

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


TASK_SPECS: dict[str, dict[str, Any]] = {
    "spaceship-titanic": {
        "id_column": "PassengerId", "target_columns": ["Transported"],
        "submission_columns": ["Transported"], "metric": "accuracy", "orientation": 1,
    },
    "tabular-playground-series-may-2022": {
        "id_column": "id", "target_columns": ["target"],
        "submission_columns": ["target"], "metric": "roc_auc", "orientation": 1,
    },
    "spooky-author-identification": {
        "id_column": "id", "target_columns": ["author"],
        "submission_columns": ["EAP", "HPL", "MWS"],
        "metric": "multiclass_log_loss", "orientation": -1,
        "classes": ["EAP", "HPL", "MWS"],
    },
    "us-patent-phrase-to-phrase-matching": {
        "id_column": "id", "target_columns": ["score"],
        "submission_columns": ["score"], "metric": "pearson", "orientation": 1,
    },
    "nomad2018-predict-transparent-conductors": {
        "id_column": "id",
        "target_columns": ["formation_energy_ev_natom", "bandgap_energy_ev"],
        "submission_columns": ["formation_energy_ev_natom", "bandgap_energy_ev"],
        "metric": "mean_columnwise_rmsle", "orientation": -1,
    },
    "learning-agency-lab-automated-essay-scoring-2": {
        "id_column": "essay_id", "target_columns": ["score"],
        "submission_columns": ["score"], "metric": "quadratic_weighted_kappa",
        "orientation": 1, "classes": [1, 2, 3, 4, 5, 6],
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
    return sha256_bytes(canonical_json({
        "common": {"name": common.name, "sha256": file_sha256(common)},
        "wrapper": {"name": wrapper.name, "sha256": file_sha256(wrapper)},
    }))


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


def strict_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError("non-finite number")
    return parsed


def strict_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"true", "1"}:
        return True
    if normalized in {"false", "0"}:
        return False
    raise ValueError("not a strict boolean")


def strict_class_int(value: str) -> int:
    parsed = strict_float(value)
    if not parsed.is_integer() or not 1 <= parsed <= 6:
        raise ValueError("not an integer class in [1,6]")
    return int(parsed)


def parse_label(row: dict[str, str], task: str) -> Any:
    spec = TASK_SPECS[task]
    metric = spec["metric"]
    values = [row[column] for column in spec["target_columns"]]
    if metric == "accuracy":
        return strict_bool(values[0])
    if metric == "roc_auc":
        if values[0].strip() not in {"0", "1"}:
            raise ValueError("AUC label is not binary")
        return int(values[0])
    if metric == "multiclass_log_loss":
        if values[0] not in spec["classes"]:
            raise ValueError("unknown log-loss class")
        return values[0]
    if metric == "pearson":
        return strict_float(values[0])
    if metric == "mean_columnwise_rmsle":
        parsed = tuple(strict_float(value) for value in values)
        if any(value < 0 for value in parsed):
            raise ValueError("RMSLE label is negative")
        return parsed
    if metric == "quadratic_weighted_kappa":
        return strict_class_int(values[0])
    raise ScoreError("unsupported E2-A metric")


def load_labels(path: pathlib.Path, task: str) -> tuple[list[str], list[Any]]:
    spec = TASK_SPECS[task]
    expected_header = [spec["id_column"], *spec["target_columns"]]
    ids: list[str] = []
    labels: list[Any] = []
    seen: set[str] = set()
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if list(reader.fieldnames or []) != expected_header:
            raise ScoreError("private label header differs")
        for row in reader:
            row_id = row[spec["id_column"]]
            if not row_id or row_id in seen or set(row) != set(expected_header):
                raise ScoreError("private labels contain invalid/duplicate ids or schema")
            seen.add(row_id)
            ids.append(row_id)
            try:
                labels.append(parse_label(row, task))
            except (ValueError, TypeError) as exc:
                raise ScoreError("private label value is invalid") from exc
    if not ids:
        raise ScoreError("private label file is empty")
    return ids, labels


def load_public_ids(path: pathlib.Path, task: str) -> list[str]:
    if not path.is_file() or path.is_symlink():
        raise ScoreError("generated public sample submission is missing or symlinked")
    raw = path.read_bytes()
    if CREDENTIAL.search(raw):
        raise ScoreError("credential shape in generated public sample")
    spec = TASK_SPECS[task]
    expected_header = [spec["id_column"], *spec["submission_columns"]]
    try:
        reader = csv.DictReader(raw.decode("utf-8-sig").splitlines())
        rows = list(reader)
    except (UnicodeDecodeError, csv.Error) as exc:
        raise ScoreError("generated public sample is not valid CSV") from exc
    if list(reader.fieldnames or []) != expected_header:
        raise ScoreError("generated public sample header differs")
    ids: list[str] = []
    seen: set[str] = set()
    for row in rows:
        row_id = row.get(spec["id_column"], "")
        if not row_id or row_id in seen or set(row) != set(expected_header):
            raise ScoreError("generated public sample ids/schema are invalid")
        seen.add(row_id)
        ids.append(row_id)
    if not ids:
        raise ScoreError("generated public sample is empty")
    return ids


def parse_prediction(row: dict[str, str], task: str) -> Any:
    spec = TASK_SPECS[task]
    values = [row[column] for column in spec["submission_columns"]]
    metric = spec["metric"]
    if metric == "accuracy":
        return strict_bool(values[0])
    if metric == "roc_auc":
        value = strict_float(values[0])
        if not 0 <= value <= 1:
            raise ValueError("AUC prediction outside [0,1]")
        return value
    if metric == "multiclass_log_loss":
        parsed = tuple(strict_float(value) for value in values)
        if any(value < 0 for value in parsed) or sum(parsed) <= 0:
            raise ValueError("log-loss probabilities are negative or sum to zero")
        return parsed
    if metric == "pearson":
        return strict_float(values[0])
    if metric == "mean_columnwise_rmsle":
        parsed = tuple(strict_float(value) for value in values)
        if any(value < 0 for value in parsed):
            raise ValueError("RMSLE prediction is negative")
        return parsed
    if metric == "quadratic_weighted_kappa":
        return strict_class_int(values[0])
    raise ScoreError("unsupported E2-A metric")


def load_predictions(
    path: pathlib.Path, task: str, evaluation_ids: list[str], public_ids: list[str]
) -> tuple[list[Any] | None, str | None]:
    if not path.is_file() or path.is_symlink():
        return None, "submission_missing"
    raw = path.read_bytes()
    if CREDENTIAL.search(raw):
        return None, "credential_shape_in_submission"
    spec = TASK_SPECS[task]
    expected_header = [spec["id_column"], *spec["submission_columns"]]
    try:
        reader = csv.DictReader(raw.decode("utf-8-sig").splitlines())
        rows = list(reader)
    except (UnicodeDecodeError, csv.Error):
        return None, "submission_csv_parse_error"
    if list(reader.fieldnames or []) != expected_header:
        return None, "submission_header_mismatch"
    if len(rows) != len(public_ids):
        return None, "submission_row_count_mismatch"
    by_id: dict[str, dict[str, str]] = {}
    for row in rows:
        row_id = row.get(spec["id_column"], "")
        if not row_id or row_id in by_id or set(row) != set(expected_header):
            return None, "submission_id_or_schema_invalid"
        by_id[row_id] = row
    if set(by_id) != set(public_ids):
        return None, "submission_id_set_mismatch"
    if not set(evaluation_ids) <= set(by_id):
        raise ScoreError("private evaluation ids escape generated public universe")
    try:
        return [parse_prediction(by_id[row_id], task) for row_id in evaluation_ids], None
    except (ValueError, TypeError):
        return None, "submission_prediction_invalid"


def rank_auc(labels: list[int], predictions: list[float]) -> float:
    positives = sum(labels)
    negatives = len(labels) - positives
    if positives == 0 or negatives == 0:
        raise ScoreError("AUC labels contain only one class")
    order = sorted(range(len(predictions)), key=lambda index: predictions[index])
    positive_rank_sum = 0.0
    cursor = 0
    while cursor < len(order):
        end = cursor + 1
        score = predictions[order[cursor]]
        while end < len(order) and predictions[order[end]] == score:
            end += 1
        average_rank = ((cursor + 1) + end) / 2.0
        positive_rank_sum += average_rank * sum(labels[index] for index in order[cursor:end])
        cursor = end
    return (positive_rank_sum - positives * (positives + 1) / 2.0) / (positives * negatives)


def multiclass_log_loss(labels: list[str], predictions: list[tuple[float, ...]], classes: list[str]) -> float:
    index = {label: position for position, label in enumerate(classes)}
    total = 0.0
    for label, row in zip(labels, predictions):
        denominator = sum(row)
        probability = row[index[label]] / denominator
        probability = max(min(probability, 1.0 - 1e-15), 1e-15)
        total -= math.log(probability)
    return total / len(labels)


def pearson(labels: list[float], predictions: list[float]) -> float:
    label_mean = sum(labels) / len(labels)
    prediction_mean = sum(predictions) / len(predictions)
    numerator = sum(
        (label - label_mean) * (prediction - prediction_mean)
        for label, prediction in zip(labels, predictions)
    )
    label_ss = sum((label - label_mean) ** 2 for label in labels)
    prediction_ss = sum((prediction - prediction_mean) ** 2 for prediction in predictions)
    denominator = math.sqrt(label_ss * prediction_ss)
    if denominator == 0:
        raise ScoreError("Pearson input is constant")
    return numerator / denominator


def mean_rmsle(labels: list[tuple[float, ...]], predictions: list[tuple[float, ...]]) -> float:
    columns = len(labels[0])
    losses = []
    for column in range(columns):
        mse = sum(
            (math.log1p(prediction[column]) - math.log1p(label[column])) ** 2
            for label, prediction in zip(labels, predictions)
        ) / len(labels)
        losses.append(math.sqrt(mse))
    return sum(losses) / columns


def quadratic_weighted_kappa(labels: list[int], predictions: list[int], classes: list[int]) -> float:
    position = {value: index for index, value in enumerate(classes)}
    size = len(classes)
    observed = [[0.0] * size for _ in range(size)]
    actual_hist = [0.0] * size
    predicted_hist = [0.0] * size
    for actual, predicted in zip(labels, predictions):
        i, j = position[actual], position[predicted]
        observed[i][j] += 1.0
        actual_hist[i] += 1.0
        predicted_hist[j] += 1.0
    numerator = 0.0
    denominator = 0.0
    count = len(labels)
    for i in range(size):
        for j in range(size):
            weight = ((i - j) / (size - 1)) ** 2
            numerator += weight * observed[i][j]
            denominator += weight * actual_hist[i] * predicted_hist[j] / count
    if denominator == 0:
        raise ScoreError("QWK expected disagreement is zero")
    return 1.0 - numerator / denominator


def compute_score(task: str, labels: list[Any], predictions: list[Any]) -> float:
    spec = TASK_SPECS[task]
    metric = spec["metric"]
    if metric == "accuracy":
        return sum(prediction == label for label, prediction in zip(labels, predictions)) / len(labels)
    if metric == "roc_auc":
        return rank_auc(labels, predictions)
    if metric == "multiclass_log_loss":
        return multiclass_log_loss(labels, predictions, spec["classes"])
    if metric == "pearson":
        return pearson(labels, predictions)
    if metric == "mean_columnwise_rmsle":
        return mean_rmsle(labels, predictions)
    if metric == "quadratic_weighted_kappa":
        return quadratic_weighted_kappa(labels, predictions, spec["classes"])
    raise ScoreError("unsupported E2-A metric")


def analysis_utility(task: str, score: float | None, submission_valid: bool) -> float:
    if not submission_valid or score is None:
        return 0.0
    if not math.isfinite(score):
        raise ScoreError("analysis utility received non-finite score")
    metric = TASK_SPECS[task]["metric"]
    if metric in {"accuracy", "roc_auc"}:
        value = score
    elif metric == "multiclass_log_loss":
        value = math.exp(-score)
    elif metric in {"pearson", "quadratic_weighted_kappa"}:
        value = (score + 1.0) / 2.0
    elif metric == "mean_columnwise_rmsle":
        value = 1.0 / (1.0 + score)
    else:
        raise ScoreError("unsupported E2-A utility transform")
    if not math.isfinite(value) or not -1e-12 <= value <= 1.0 + 1e-12:
        raise ScoreError("analysis utility falls outside [0,1]")
    return min(max(float(value), 0.0), 1.0)


def score_submission(
    artifact: pathlib.Path, labels_path: pathlib.Path, public_sample_path: pathlib.Path, task: str
) -> dict[str, Any]:
    if task not in TASK_SPECS:
        raise ScoreError("unsupported E2-A task")
    ids, labels = load_labels(labels_path, task)
    public_ids = load_public_ids(public_sample_path, task)
    if not set(ids) <= set(public_ids):
        raise ScoreError("private labels escape generated public universe")
    predictions, failure = load_predictions(artifact, task, ids, public_ids)
    if predictions is None:
        return {
            "submission_valid": False, "score": None, "row_count": len(ids),
            "failure_reason": failure,
        }
    try:
        score = compute_score(task, labels, predictions)
    except ScoreError as exc:
        return {
            "submission_valid": False, "score": None, "row_count": len(ids),
            "failure_reason": f"metric_invalid:{exc}",
        }
    if not math.isfinite(score):
        raise ScoreError("scorer produced a non-finite score")
    return {
        "submission_valid": True, "score": float(score), "row_count": len(ids),
        "failure_reason": None,
    }
