#!/usr/bin/env python3
"""Measure deployment cost for three decision-time MLE code predictors.

This is a timing-only attestation.  It trains on the released v11 b0 training
pairs and queries a canonical (orientation-free) manifest derived from the
released v11 b0 frozen pairs.  It never evaluates frozen accuracy.  Runtime
from the historical cards is reported separately as a post-execution reference.
"""

from __future__ import annotations

import os

# These must be set before NumPy/scikit-learn load their native thread pools.
for _variable in (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
):
    os.environ[_variable] = "1"

import argparse
import csv
import hashlib
import json
import math
import platform
import random
import re
import statistics
import subprocess
import sys
import time
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np
import scipy
from scipy import sparse
import sklearn
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.exceptions import ConvergenceWarning
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_info, threadpool_limits


PROTOCOL = "deployment_cost_attestation_v2"
MODELS = ("static_lr", "static_gbm", "tfidf_lr")
MEASUREMENT_FIELDS = (
    "model",
    "trial",
    "phase",
    "repeat",
    "item_index",
    "n_items",
    "elapsed_s",
    "per_pair_ms",
    "decision",
    "decision_sha256",
)
FORBIDDEN_PATH_FRAGMENTS = (
    "prospective_decision_v1/label",
    "prospective_decision_v1/outcome",
    "prospective_decision_v1/scorer",
    "label_vault",
    "outcome_vault",
)

IMPORT_RX = re.compile(r"^\s*(?:from|import)\s+([\w.]+)", re.M)
MODEL_WORDS = (
    "lightgbm",
    "xgboost",
    "catboost",
    "randomforest",
    "logisticregression",
    "ridge",
    "svc",
    "torch",
    "transformers",
    "bert",
    "resnet",
    "efficientnet",
    "timm",
    "keras",
    "sklearn",
)
CV_WORDS = ("kfold", "stratifiedkfold", "groupkfold", "cross_val", "train_test_split")
RISK_WORDS = (
    "fit_transform(test",
    "fit(test",
    ".append(test",
    "concat([train, test",
    "pd.concat([train,test",
)


class IntegrityError(RuntimeError):
    pass


@dataclass(frozen=True)
class Card:
    code: str
    lineage: dict[str, Any]
    runtime_s: float | None


@dataclass
class FittedPredictor:
    name: str
    estimator: Any
    scaler: StandardScaler | None = None
    vectorizer: TfidfVectorizer | None = None


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalized_lf_sha256(path: Path) -> str:
    raw = path.read_bytes()
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise IntegrityError(f"expected UTF-8 input: {path}") from exc
    return hashlib.sha256(raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")).hexdigest()


def atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def atomic_json(path: Path, payload: Any) -> None:
    atomic_text(
        path,
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n",
    )


def quantile(values: Sequence[float], probability: float) -> float:
    if not values:
        raise IntegrityError("cannot summarize an empty measurement")
    ordered = sorted(float(value) for value in values)
    if any(not math.isfinite(value) or value < 0 for value in ordered):
        raise IntegrityError("measurement contains a non-finite or negative value")
    position = (len(ordered) - 1) * probability
    lower, upper = math.floor(position), math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def distribution(values: Sequence[float]) -> dict[str, float | int]:
    return {
        "n": len(values),
        "p25": quantile(values, 0.25),
        "p50": quantile(values, 0.50),
        "p75": quantile(values, 0.75),
        "p95": quantile(values, 0.95),
        "min": min(values),
        "max": max(values),
    }


def finite_positive(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number > 0 else None


def ensure_safe_path(path: Path) -> None:
    normalized = path.resolve().as_posix().lower()
    for fragment in FORBIDDEN_PATH_FRAGMENTS:
        if fragment in normalized:
            raise IntegrityError(f"forbidden prospective path: {path}")


def load_pairs(path: Path, expected_split: str, canonical: bool) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("intask_split") != expected_split or int(row.get("budget", -1)) != 0:
                raise IntegrityError(f"unexpected split/budget at {path}:{line_number}")
            better, worse = str(row.get("better", "")), str(row.get("worse", ""))
            if not better or not worse or better == worse:
                raise IntegrityError(f"degenerate pair at {path}:{line_number}")
            unordered = tuple(sorted((better, worse)))
            if unordered in seen:
                raise IntegrityError(f"duplicate/reversed pair at {path}:{line_number}")
            seen.add(unordered)
            pairs.append(unordered if canonical else (better, worse))
    if not pairs:
        raise IntegrityError(f"empty pair file: {path}")
    return pairs


def load_cards(path: Path, required: set[str]) -> dict[str, Card]:
    cards: dict[str, Card] = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            card_id = str(row.get("id", ""))
            if card_id not in required:
                continue
            obs = row.get("obs") or {}
            cards[card_id] = Card(
                code=str(row.get("code") or ""),
                lineage=dict(row.get("lineage") or {}),
                runtime_s=finite_positive(obs.get("runtime_s")),
            )
    missing = sorted(required - set(cards))
    if missing:
        raise IntegrityError(f"{len(missing)} required cards are missing; first={missing[:3]}")
    return cards


def feature_dict(card: Card) -> dict[str, float]:
    code = card.code
    low = code.lower()
    lineage = card.lineage
    imports = set(IMPORT_RX.findall(code))
    features = {
        "code_len": float(len(code)),
        "n_lines": float(code.count("\n")),
        "n_imports": float(len(imports)),
        "depth": float(lineage.get("depth") or 0),
        "step": float(lineage.get("step") or 0),
        "n_sibs": float(lineage.get("n_siblings") or 0),
        "n_cv": float(sum(low.count(word) for word in CV_WORDS)),
        "n_seed": float(low.count("seed") + low.count("random_state")),
        "n_ensemble": float(
            low.count("ensemble") + low.count("blend") + low.count("stack") + low.count("mean(")
        ),
        "n_earlystop": float(low.count("early_stop")),
        "n_hpsearch": float(
            low.count("optuna") + low.count("gridsearch") + low.count("param_grid") + low.count("hyperopt")
        ),
        "n_augment": float(low.count("augment") + low.count("transform")),
        "n_try": float(low.count("try:")),
        "n_print": float(low.count("print(")),
        "n_comment": float(code.count("#")),
        "n_fold_int": float(
            max([int(value) for value in re.findall(r"n_splits\s*=\s*(\d+)", code)] or [0])
        ),
        "n_epoch_int": float(
            max([int(value) for value in re.findall(r"epochs?\s*=\s*(\d+)", code)] or [0])
        ),
        "risk_leak": float(sum(low.count(word) for word in RISK_WORDS)),
        "has_gpu": float("cuda" in low),
    }
    for word in MODEL_WORDS:
        features["m_" + word] = float(word in low)
    return features


FEATURE_NAMES = tuple(sorted(feature_dict(Card("", {}, None))))


def static_pair_matrix(cards: dict[str, Card], pairs: Sequence[tuple[str, str]]) -> np.ndarray:
    identifiers = sorted({identifier for pair in pairs for identifier in pair})
    matrix = np.asarray(
        [[feature_dict(cards[identifier])[name] for name in FEATURE_NAMES] for identifier in identifiers],
        dtype=np.float64,
    )
    position = {identifier: index for index, identifier in enumerate(identifiers)}
    left = np.asarray([position[pair[0]] for pair in pairs], dtype=np.int64)
    right = np.asarray([position[pair[1]] for pair in pairs], dtype=np.int64)
    return matrix[left] - matrix[right]


def fit_predictor(
    name: str, cards: dict[str, Card], train_pairs: Sequence[tuple[str, str]], seed: int
) -> tuple[FittedPredictor, list[str]]:
    labels = np.concatenate(
        (np.ones(len(train_pairs), dtype=np.int8), np.zeros(len(train_pairs), dtype=np.int8))
    )
    captured: list[str] = []
    with warnings.catch_warnings(record=True) as records:
        warnings.simplefilter("always")
        if name in {"static_lr", "static_gbm"}:
            differences = static_pair_matrix(cards, train_pairs)
            design = np.vstack((differences, -differences))
            if name == "static_lr":
                scaler = StandardScaler(with_mean=False).fit(design)
                estimator = LogisticRegression(max_iter=4000, C=1.0, random_state=seed).fit(
                    scaler.transform(design), labels
                )
                fitted = FittedPredictor(name=name, estimator=estimator, scaler=scaler)
            else:
                estimator = HistGradientBoostingClassifier(
                    max_iter=300,
                    learning_rate=0.08,
                    random_state=seed,
                ).fit(design, labels)
                fitted = FittedPredictor(name=name, estimator=estimator)
        elif name == "tfidf_lr":
            identifiers = sorted({identifier for pair in train_pairs for identifier in pair})
            vectorizer = TfidfVectorizer(
                analyzer="char_wb",
                ngram_range=(3, 5),
                max_features=30000,
                min_df=3,
                sublinear_tf=True,
            )
            endpoint_matrix = vectorizer.fit_transform(
                [cards[identifier].code[:20000] for identifier in identifiers]
            )
            position = {identifier: index for index, identifier in enumerate(identifiers)}
            left = np.asarray([position[pair[0]] for pair in train_pairs], dtype=np.int64)
            right = np.asarray([position[pair[1]] for pair in train_pairs], dtype=np.int64)
            differences = endpoint_matrix[left] - endpoint_matrix[right]
            design = sparse.vstack((differences, -differences), format="csr")
            estimator = LogisticRegression(max_iter=1500, C=0.5, random_state=seed).fit(
                design, labels
            )
            fitted = FittedPredictor(name=name, estimator=estimator, vectorizer=vectorizer)
        else:  # pragma: no cover - guarded by CLI and tests
            raise IntegrityError(f"unknown model: {name}")
        # The integrity gate targets optimizer convergence, not version-level
        # deprecation notices emitted by SciPy internals.
        for record in records:
            if issubclass(record.category, ConvergenceWarning):
                captured.append(f"{record.category.__name__}: {record.message}")
    return fitted, captured


def raw_decision(estimator: Any, matrix: Any) -> np.ndarray:
    values = estimator.decision_function(matrix)
    return np.asarray(values, dtype=np.float64).reshape(-1)


def query_scores(
    fitted: FittedPredictor, cards: dict[str, Card], pairs: Sequence[tuple[str, str]]
) -> np.ndarray:
    if fitted.name in {"static_lr", "static_gbm"}:
        differences: Any = static_pair_matrix(cards, pairs)
        reverse = -differences
        if fitted.scaler is not None:
            differences = fitted.scaler.transform(differences)
            reverse = fitted.scaler.transform(reverse)
    elif fitted.name == "tfidf_lr":
        if fitted.vectorizer is None:  # pragma: no cover
            raise IntegrityError("TF-IDF predictor has no vectorizer")
        identifiers = sorted({identifier for pair in pairs for identifier in pair})
        endpoint_matrix = fitted.vectorizer.transform(
            [cards[identifier].code[:20000] for identifier in identifiers]
        )
        position = {identifier: index for index, identifier in enumerate(identifiers)}
        left = np.asarray([position[pair[0]] for pair in pairs], dtype=np.int64)
        right = np.asarray([position[pair[1]] for pair in pairs], dtype=np.int64)
        differences = endpoint_matrix[left] - endpoint_matrix[right]
        reverse = -differences
    else:  # pragma: no cover
        raise IntegrityError(f"unknown fitted model: {fitted.name}")
    # Explicit antisymmetrization makes the pair decision orientation invariant.
    return raw_decision(fitted.estimator, differences) - raw_decision(fitted.estimator, reverse)


def decisions(scores: np.ndarray) -> np.ndarray:
    if np.any(~np.isfinite(scores)):
        raise IntegrityError("non-finite query score")
    return np.sign(scores).astype(np.int8)


def decision_sha(values: np.ndarray) -> str:
    return hashlib.sha256((values.astype(np.int8) + 1).tobytes()).hexdigest()


def execution_reference(
    cards: dict[str, Card], pairs: Sequence[tuple[str, str]]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    unique_identifiers = sorted({identifier for pair in pairs for identifier in pair})
    endpoint_values = [cards[identifier].runtime_s for identifier in unique_identifiers]
    finite_endpoints = [value for value in endpoint_values if value is not None]
    serial_values: list[float] = []
    parallel_values: list[float] = []
    for index, (left, right) in enumerate(pairs):
        left_runtime, right_runtime = cards[left].runtime_s, cards[right].runtime_s
        complete = left_runtime is not None and right_runtime is not None
        serial = left_runtime + right_runtime if complete else None
        parallel = max(left_runtime, right_runtime) if complete else None
        if complete:
            serial_values.append(float(serial))
            parallel_values.append(float(parallel))
        rows.append(
            {
                "pair_index": index,
                "left_id": left,
                "right_id": right,
                "left_runtime_s": left_runtime,
                "right_runtime_s": right_runtime,
                "serial_runtime_s": serial,
                "ideal_parallel_runtime_s": parallel,
                "complete": int(complete),
            }
        )
    if not finite_endpoints or not parallel_values:
        raise IntegrityError("runtime reference has no finite support")
    summary = {
        "unique_endpoints": len(unique_identifiers),
        "finite_unique_endpoints": len(finite_endpoints),
        "endpoint_coverage": len(finite_endpoints) / len(unique_identifiers),
        "pairs": len(pairs),
        "complete_pairs": len(parallel_values),
        "pair_coverage": len(parallel_values) / len(pairs),
        "unique_endpoint_runtime_s": distribution(finite_endpoints),
        "pair_serial_runtime_s": distribution(serial_values),
        "pair_ideal_parallel_runtime_s": distribution(parallel_values),
    }
    return rows, summary


def write_csv(path: Path, fieldnames: Sequence[str], rows: Iterable[dict[str, Any]]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def completed_trials(receipts: Sequence[dict[str, Any]]) -> set[tuple[str, int]]:
    return {(str(row["model"]), int(row["trial"])) for row in receipts}


def summarize(
    config: dict[str, Any],
    measurements: Sequence[dict[str, str]],
    receipts: Sequence[dict[str, Any]],
    runtime: dict[str, Any],
) -> dict[str, Any]:
    models: dict[str, Any] = {}
    for model in MODELS:
        model_rows = [row for row in measurements if row["model"] == model]
        init_values = [float(row["elapsed_s"]) for row in model_rows if row["phase"] == "init"]
        single_values = [
            float(row["per_pair_ms"]) for row in model_rows if row["phase"] == "single_query"
        ]
        model_receipts = [row for row in receipts if row["model"] == model]
        if not init_values or not single_values:
            raise IntegrityError(f"incomplete measurements for {model}")
        trial_single_p50 = [
            quantile(
                [
                    float(row["per_pair_ms"])
                    for row in model_rows
                    if row["phase"] == "single_query" and int(row["trial"]) == trial
                ],
                0.5,
            )
            for trial in range(config["init_trials"])
        ]
        query_stability = max(trial_single_p50) / max(min(trial_single_p50), 1e-15)
        init_stability = max(init_values) / max(min(init_values), 1e-15)
        sample_digests = sorted({str(row["sample_decision_sha256"]) for row in model_receipts})
        warning_count = sum(len(row["fit_warnings"]) for row in model_receipts)
        init_stats = distribution(init_values)
        single_stats = distribution(single_values)
        execution_parallel_p50 = runtime["pair_ideal_parallel_runtime_s"]["p50"]
        execution_serial_p50 = runtime["pair_serial_runtime_s"]["p50"]
        single_p50_s = single_stats["p50"] / 1000.0
        single_p95_s = single_stats["p95"] / 1000.0
        denominator = max(execution_parallel_p50 - single_p50_s, 1e-15)
        models[model] = {
            "initialization_s": init_stats,
            "single_pair_query_ms": single_stats,
            "trial_single_query_p50_ms": trial_single_p50,
            "query_trial_max_min_ratio": query_stability,
            "init_trial_max_min_ratio": init_stability,
            "sample_decision_sha256_values": sample_digests,
            "fit_warning_count": warning_count,
            "tie_counts": sorted({int(row["tie_count"]) for row in model_receipts}),
            "antisymmetry_min": min(float(row["antisymmetry_fraction"]) for row in model_receipts),
            "execution_parallel_p50_over_query_p50": execution_parallel_p50 / single_p50_s,
            "execution_serial_p50_over_query_p50": execution_serial_p50 / single_p50_s,
            "query_p95_fraction_of_execution_parallel_p50": single_p95_s / execution_parallel_p50,
            "initialization_break_even_parallel_pairs": math.ceil(init_stats["p50"] / denominator),
        }
    integrity_checks = {
        "all_models_complete": len(receipts) == len(MODELS) * config["init_trials"],
        "runtime_pair_coverage_at_least_0_95": runtime["pair_coverage"] >= 0.95,
        "all_decision_digests_stable": all(
            len(models[model]["sample_decision_sha256_values"]) == 1 for model in MODELS
        ),
        "all_antisymmetry_exact": all(models[model]["antisymmetry_min"] == 1.0 for model in MODELS),
        "no_fit_warnings": all(models[model]["fit_warning_count"] == 0 for model in MODELS),
        "within_run_query_stability_at_most_2": all(
            models[model]["query_trial_max_min_ratio"] <= 2.0 for model in MODELS
        ),
        "within_run_init_stability_at_most_3": all(
            models[model]["init_trial_max_min_ratio"] <= 3.0 for model in MODELS
        ),
    }
    positive_checks = {
        "all_query_p95_below_1pct_parallel_execution_p50": all(
            models[model]["query_p95_fraction_of_execution_parallel_p50"] <= 0.01
            for model in MODELS
        ),
        "all_init_p50_below_10_parallel_execution_p50": all(
            models[model]["initialization_s"]["p50"]
            <= 10.0 * runtime["pair_ideal_parallel_runtime_s"]["p50"]
            for model in MODELS
        ),
    }
    integrity_pass = all(integrity_checks.values())
    positive_pass = integrity_pass and all(positive_checks.values())
    return {
        "protocol": PROTOCOL,
        "status": (
            "DEPLOYMENT_COST_ADVANTAGE_SUPPORTED"
            if positive_pass
            else "VERIFIED_DEPLOYMENT_COST_ATTESTATION"
            if integrity_pass
            else "FAILED_DEPLOYMENT_COST_INTEGRITY"
        ),
        "scope": {
            "accuracy_computed": False,
            "query_manifest_orientation_free": True,
            "prospective_vault_opened": False,
            "gpu_used": False,
            "api_used": False,
        },
        "runtime_reference": runtime,
        "models": models,
        "integrity_checks": integrity_checks,
        "positive_checks": positive_checks,
    }


def git_head(source_root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(source_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cards", required=True)
    parser.add_argument("--train-pairs", required=True)
    parser.add_argument("--query-pairs", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--expected-git-commit", required=True)
    parser.add_argument("--expected-cards-sha256-normalized-lf", required=True)
    parser.add_argument("--expected-train-sha256-normalized-lf", required=True)
    parser.add_argument("--expected-query-sha256-normalized-lf", required=True)
    parser.add_argument("--run-label", choices=("A", "B"), required=True)
    parser.add_argument("--seed", type=int, default=20260820)
    parser.add_argument("--init-trials", type=int, default=3)
    parser.add_argument("--single-query-warmup", type=int, default=10)
    parser.add_argument("--single-pair-sample", type=int, default=256)
    parser.add_argument("--resume", action="store_true")
    return parser.parse_args()


def main() -> None:
    arguments = parse_args()
    cards_path = Path(arguments.cards).resolve()
    train_path = Path(arguments.train_pairs).resolve()
    query_path = Path(arguments.query_pairs).resolve()
    source_root = Path(arguments.source_root).resolve()
    output = Path(arguments.out_dir).resolve()
    for path in (cards_path, train_path, query_path, source_root, output):
        ensure_safe_path(path)
    actual_commit = git_head(source_root)
    if actual_commit != arguments.expected_git_commit:
        raise IntegrityError(
            f"git commit mismatch: {actual_commit} != {arguments.expected_git_commit}"
        )
    input_manifest = {
        "cards": {
            "path": cards_path.as_posix(),
            "bytes": cards_path.stat().st_size,
            "sha256": sha256(cards_path),
            "sha256_normalized_lf": normalized_lf_sha256(cards_path),
            "expected_sha256_normalized_lf": arguments.expected_cards_sha256_normalized_lf,
        },
        "train_pairs": {
            "path": train_path.as_posix(),
            "bytes": train_path.stat().st_size,
            "sha256": sha256(train_path),
            "sha256_normalized_lf": normalized_lf_sha256(train_path),
            "expected_sha256_normalized_lf": arguments.expected_train_sha256_normalized_lf,
        },
        "query_pairs": {
            "path": query_path.as_posix(),
            "bytes": query_path.stat().st_size,
            "sha256": sha256(query_path),
            "sha256_normalized_lf": normalized_lf_sha256(query_path),
            "expected_sha256_normalized_lf": arguments.expected_query_sha256_normalized_lf,
        },
    }
    for name, item in input_manifest.items():
        if item["sha256_normalized_lf"] != item["expected_sha256_normalized_lf"]:
            raise IntegrityError(f"normalized input hash mismatch for {name}")
    train_pairs = load_pairs(train_path, "train", canonical=False)
    query_pairs = load_pairs(query_path, "test", canonical=True)
    if arguments.init_trials <= 0:
        raise IntegrityError("init-trials must be positive")
    if arguments.single_query_warmup < 0:
        raise IntegrityError("single-query-warmup must be non-negative")
    if arguments.single_pair_sample <= 0:
        raise IntegrityError("single-pair-sample must be positive")
    if arguments.single_pair_sample > len(query_pairs):
        raise IntegrityError(
            "single-pair-sample exceeds the frozen orientation-free query manifest"
        )
    train_endpoints = {identifier for pair in train_pairs for identifier in pair}
    query_endpoints = {identifier for pair in query_pairs for identifier in pair}
    overlap = train_endpoints & query_endpoints
    if overlap:
        raise IntegrityError(f"train/query endpoint overlap: {len(overlap)}")
    required = train_endpoints | query_endpoints
    cards = load_cards(cards_path, required)
    runtime_rows, runtime_summary = execution_reference(cards, query_pairs)
    if runtime_summary["pair_coverage"] < 0.95:
        raise IntegrityError("runtime pair coverage is below the preregistered 0.95 gate")

    script_path = Path(__file__).resolve()
    config = {
        "protocol": PROTOCOL,
        "run_label": arguments.run_label,
        "seed": arguments.seed,
        "models": list(MODELS),
        "init_trials": arguments.init_trials,
        "single_query_warmup": arguments.single_query_warmup,
        "single_pair_sample": arguments.single_pair_sample,
        "train_pairs": len(train_pairs),
        "query_pairs": len(query_pairs),
        "train_endpoints": len(train_endpoints),
        "query_endpoints": len(query_endpoints),
        "train_query_endpoint_overlap": len(overlap),
        "expected_git_commit": arguments.expected_git_commit,
        "actual_git_commit": actual_commit,
        "source_script": script_path.as_posix(),
        "source_script_sha256": sha256(script_path),
        "input_manifest": input_manifest,
        "thread_contract": {
            variable: os.environ[variable]
            for variable in (
                "OMP_NUM_THREADS",
                "OPENBLAS_NUM_THREADS",
                "MKL_NUM_THREADS",
                "NUMEXPR_NUM_THREADS",
            )
        },
    }
    if output.exists() and not arguments.resume:
        raise IntegrityError(f"output already exists (use --resume): {output}")
    output.mkdir(parents=True, exist_ok=True)
    config_path = output / "config.json"
    if config_path.exists():
        existing = json.loads(config_path.read_text(encoding="utf-8"))
        if existing != config:
            raise IntegrityError("resume config differs from existing config")
    else:
        atomic_json(config_path, config)
        atomic_json(output / "input_manifest.json", input_manifest)
        atomic_text(output / "command.txt", " ".join(sys.argv) + "\n")
        write_csv(
            output / "execution_reference.csv",
            (
                "pair_index",
                "left_id",
                "right_id",
                "left_runtime_s",
                "right_runtime_s",
                "serial_runtime_s",
                "ideal_parallel_runtime_s",
                "complete",
            ),
            runtime_rows,
        )
        atomic_json(output / "runtime_reference_summary.json", runtime_summary)

    measurements_path = output / "measurements.csv"
    receipts_path = output / "trial_receipts.jsonl"
    measurements = read_csv(measurements_path)
    receipts = read_jsonl(receipts_path)
    done = completed_trials(receipts)
    sample_size = arguments.single_pair_sample
    sample_rng = random.Random(arguments.seed)
    sample_indices = sorted(sample_rng.sample(range(len(query_pairs)), sample_size))
    single_pairs = [query_pairs[index] for index in sample_indices]
    atomic_json(
        output / "single_pair_sample.json",
        {
            "seed": arguments.seed,
            "indices": sample_indices,
            "pair_manifest_sha256": hashlib.sha256(
                "\n".join(f"{left}|{right}" for left, right in single_pairs).encode()
            ).hexdigest(),
        },
    )

    with threadpool_limits(limits=1):
        for model in MODELS:
            for trial in range(arguments.init_trials):
                if (model, trial) in done:
                    continue
                # Remove an interrupted partial trial before rerunning it.
                measurements = [
                    row
                    for row in measurements
                    if not (row["model"] == model and int(row["trial"]) == trial)
                ]
                started = time.perf_counter_ns()
                fitted, fit_warnings = fit_predictor(model, cards, train_pairs, arguments.seed)
                init_s = (time.perf_counter_ns() - started) / 1e9
                trial_rows: list[dict[str, Any]] = [
                    {
                        "model": model,
                        "trial": trial,
                        "phase": "init",
                        "repeat": 0,
                        "item_index": "",
                        "n_items": len(train_pairs),
                        "elapsed_s": f"{init_s:.12f}",
                        "per_pair_ms": "",
                        "decision": "",
                        "decision_sha256": "",
                    }
                ]
                for warm_index in range(arguments.single_query_warmup):
                    query_scores(fitted, cards, [single_pairs[warm_index % len(single_pairs)]])
                sample_decisions: list[int] = []
                for item_index, pair in enumerate(single_pairs):
                    started = time.perf_counter_ns()
                    score = query_scores(fitted, cards, [pair])
                    elapsed = (time.perf_counter_ns() - started) / 1e9
                    current = decisions(score)
                    sample_decisions.append(int(current[0]))
                    trial_rows.append(
                        {
                            "model": model,
                            "trial": trial,
                            "phase": "single_query",
                            "repeat": 0,
                            "item_index": item_index,
                            "n_items": 1,
                            "elapsed_s": f"{elapsed:.12f}",
                            "per_pair_ms": f"{elapsed * 1000.0:.12f}",
                            "decision": int(current[0]),
                            "decision_sha256": decision_sha(current),
                        }
                    )
                forward_scores = query_scores(fitted, cards, single_pairs)
                reverse_scores = query_scores(fitted, cards, [(right, left) for left, right in single_pairs])
                antisymmetry = float(
                    np.mean(np.isclose(reverse_scores, -forward_scores, rtol=0, atol=1e-12))
                )
                if antisymmetry != 1.0:
                    raise IntegrityError(f"antisymmetry failed for {model} trial {trial}")
                sample_array = np.asarray(sample_decisions, dtype=np.int8)
                if not np.array_equal(sample_array, decisions(forward_scores)):
                    raise IntegrityError(f"single/sample-batch decision mismatch for {model}")
                receipt = {
                    "model": model,
                    "trial": trial,
                    "fit_warnings": fit_warnings,
                    "sample_decision_sha256": decision_sha(sample_array),
                    "tie_count": int(np.sum(sample_array == 0)),
                    "antisymmetry_fraction": antisymmetry,
                    "init_s": init_s,
                    "single_measurements": len(single_pairs),
                }
                measurements.extend(trial_rows)
                receipts.append(receipt)
                write_csv(measurements_path, MEASUREMENT_FIELDS, measurements)
                atomic_text(
                    receipts_path,
                    "".join(
                        json.dumps(row, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"
                        for row in receipts
                    ),
                )
                print(
                    f"TRIAL_DONE model={model} trial={trial} init_s={init_s:.6f} "
                    f"decision_sha256={receipt['sample_decision_sha256']}",
                    flush=True,
                )

    summary = summarize(config, measurements, receipts, runtime_summary)
    hardware = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "sklearn": sklearn.__version__,
        "logical_cpu_count": os.cpu_count(),
        "cpu_affinity": sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
        "load_average_end": list(os.getloadavg()) if hasattr(os, "getloadavg") else None,
        "threadpools": threadpool_info(),
    }
    atomic_json(output / "hardware_environment.json", hardware)
    atomic_json(output / "summary.json", summary)
    print(summary["status"], flush=True)


if __name__ == "__main__":
    main()
