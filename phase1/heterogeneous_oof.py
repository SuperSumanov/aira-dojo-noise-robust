#!/usr/bin/env python3
"""Run-clean OOF audit of heterogeneous decision-time predictors.

The program has no frozen/test/held pair argument.  It inherits the locked
physical-run folds from the prior train-only frozen-head OOF artifact and fits
four preregistered code/action predictors without updating any LLM weights.
"""

from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import math
import os
import platform
import re
import subprocess
import sys
import time
import warnings
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np

from phase1 import frozen_embed_rank as baseline_module
from phase1 import task_topcenter_rank as metric_module


SEED = 887
PROTOCOL = "heterogeneous_oof_v11_discovery_v1"
OUTER_FOLDS = 5
BOOTSTRAP_REPS = 10_000
EPSILON = 1e-12
EXPECTED = {
    "pairs": 4_263,
    "runs": 333,
    "tasks": 23,
    "parents": 2_293,
    "complete_parents": 2_259,
    "endpoints": 5_499,
}
BASELINE_ARM = "fixed_frozen_global"
PRIMARY_ARM = "char_tfidf_lr"
BASE_ARMS = ("op_only_lr", "static_lr", "static_gbm", PRIMARY_ARM)
EQUAL_ARM = "equal_rank_frozen_tfidf"
ARMS = (BASELINE_ARM, *BASE_ARMS, EQUAL_ARM)
METRIC_SEED_OFFSETS = {
    BASELINE_ARM: 10,
    "op_only_lr": 300,
    "static_lr": 320,
    "static_gbm": 340,
    PRIMARY_ARM: 360,
    EQUAL_ARM: 380,
}

OP_NAMES = ("draft", "debug", "improve", "other")
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


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def json_digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def atomic_npz(path: Path, **arrays: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp.npz")
    np.savez_compressed(temporary, **arrays)
    os.replace(temporary, path)


def git_commit(repo_root: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"], text=True
    ).strip()


def reject_forbidden_path(path: Path, label: str) -> None:
    found = [token for token in ("frozen", "test", "held") if token in path.name.lower()]
    if found:
        raise IntegrityError(f"{label} path contains forbidden token(s): {found}")


def task_name(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("name") or value.get("desc") or "")
    return str(value or "")


def code_view(code: str) -> str:
    if len(code) <= 20_000:
        return code
    return code[:5_000] + "\n# <FIXED_HEAD_TAIL_TRUNCATION>\n" + code[-15_000:]


def normalized_op(value: Any) -> str:
    op = str(value or "").strip().lower()
    return op if op in OP_NAMES[:-1] else "other"


def static_feature_dict(card: dict[str, Any]) -> dict[str, float]:
    code = str(card["code"])
    low = code.lower()
    lineage = card["lineage"]
    imports = set(IMPORT_RX.findall(code))
    values = {
        "code_len": float(len(code)),
        "n_lines": float(code.count("\n")),
        "n_imports": float(len(imports)),
        "depth": float(lineage.get("depth") or 0),
        "step": float(lineage.get("step") or 0),
        "n_sibs": float(lineage.get("n_siblings") or 0),
        "n_cv": float(sum(low.count(word) for word in CV_WORDS)),
        "n_seed": float(low.count("seed") + low.count("random_state")),
        "n_ensemble": float(
            low.count("ensemble")
            + low.count("blend")
            + low.count("stack")
            + low.count("mean(")
        ),
        "n_earlystop": float(low.count("early_stop")),
        "n_hpsearch": float(
            low.count("optuna")
            + low.count("gridsearch")
            + low.count("param_grid")
            + low.count("hyperopt")
        ),
        "n_augment": float(low.count("augment") + low.count("transform")),
        "n_try": float(low.count("try:")),
        "n_print": float(code.count("print(")),
        "n_comment": float(code.count("#")),
        "n_fold_int": float(
            max([int(item) for item in re.findall(r"n_splits\s*=\s*(\d+)", code)] or [0])
        ),
        "n_epoch_int": float(
            max([int(item) for item in re.findall(r"epochs?\s*=\s*(\d+)", code)] or [0])
        ),
        "risk_leak": float(sum(low.count(word) for word in RISK_WORDS)),
        "has_gpu": float("cuda" in low),
    }
    for word in MODEL_WORDS:
        values[f"m_{word}"] = float(word in low)
    op = normalized_op(lineage.get("op"))
    for name in OP_NAMES:
        values[f"op_{name}"] = float(op == name)
    return values


def feature_names(example: dict[str, Any]) -> tuple[list[str], list[int]]:
    names = sorted(static_feature_dict(example))
    op_indices = [names.index(f"op_{name}") for name in OP_NAMES]
    return names, op_indices


def load_manifest(path: Path, summary_path: Path, expected_sha: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    reject_forbidden_path(path, "train endpoint manifest")
    reject_forbidden_path(summary_path, "train endpoint manifest summary")
    digest = sha256(path)
    if digest != expected_sha.lower():
        raise IntegrityError(f"manifest SHA mismatch: {digest}")
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    ids = [str(row["card_id"]) for row in rows]
    if ids != sorted(ids) or len(ids) != len(set(ids)) or len(ids) != EXPECTED["endpoints"]:
        raise IntegrityError("manifest IDs/count are invalid")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if summary.get("status") != "MANIFEST_COMPLETE":
        raise IntegrityError("manifest summary is incomplete")
    if summary.get("expected_split") != "train":
        raise IntegrityError("manifest is not train-only")
    if summary.get("outputs", {}).get("manifest_sha256") != digest:
        raise IntegrityError("manifest summary SHA mismatch")
    if int(summary.get("endpoints", -1)) != len(rows):
        raise IntegrityError("manifest summary endpoint count mismatch")
    return rows, summary


def load_train_cards(
    cards_path: Path,
    manifest: Sequence[dict[str, Any]],
    expected_cards_sha: str,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    reject_forbidden_path(cards_path, "source cards")
    expected = {str(row["card_id"]): row for row in manifest}
    found: dict[str, dict[str, Any]] = {}
    digest = hashlib.sha256()
    corpus_rows = 0
    with cards_path.open("rb") as handle:
        for raw_line in handle:
            digest.update(raw_line)
            corpus_rows += 1
            row = json.loads(raw_line)
            card_id = str(row["id"])
            if card_id not in expected:
                continue
            if card_id in found:
                raise IntegrityError(f"duplicate selected card: {card_id}")
            code = str(row.get("code") or "")
            lineage = dict(row.get("lineage") or {})
            if not code:
                raise IntegrityError(f"empty selected code: {card_id}")
            meta = expected[card_id]
            if hashlib.sha256(code.encode("utf-8")).hexdigest() != str(meta["code_sha256"]):
                raise IntegrityError(f"selected code SHA mismatch: {card_id}")
            if len(code) != int(meta["code_chars"]):
                raise IntegrityError(f"selected code length mismatch: {card_id}")
            if task_name(row.get("task")) != str(meta["task"]):
                raise IntegrityError(f"selected task mismatch: {card_id}")
            if str(row.get("run_id")) != str(meta["run_id"]):
                raise IntegrityError(f"selected run mismatch: {card_id}")
            # Deliberately retain no label, obs/stdout, runtime, or self-report field.
            found[card_id] = {
                "id": card_id,
                "task": str(meta["task"]),
                "run": str(meta["run_id"]),
                "code": code,
                "lineage": {
                    "depth": lineage.get("depth"),
                    "step": lineage.get("step"),
                    "n_siblings": lineage.get("n_siblings"),
                    "op": lineage.get("op"),
                },
            }
    actual_sha = digest.hexdigest()
    if actual_sha != expected_cards_sha.lower():
        raise IntegrityError(f"cards SHA mismatch: {actual_sha}")
    if set(found) != set(expected):
        missing = sorted(set(expected) - set(found))
        raise IntegrityError(f"selected card coverage mismatch: {missing[:8]}")
    retained_keys = sorted({key for card in found.values() for key in card})
    if retained_keys != ["code", "id", "lineage", "run", "task"]:
        raise IntegrityError(f"unexpected retained card keys: {retained_keys}")
    return found, {
        "cards_sha256": actual_sha,
        "corpus_rows_scanned": corpus_rows,
        "selected_endpoints": len(found),
        "retained_keys": retained_keys,
        "label_fields_retained": 0,
        "post_execution_fields_retained": 0,
    }


def pair_differences(
    matrix: Any,
    position: dict[str, int],
    rows: Sequence[dict[str, Any]],
    indices: Sequence[int],
) -> Any:
    better = np.asarray([position[str(rows[index]["better"])] for index in indices])
    worse = np.asarray([position[str(rows[index]["worse"])] for index in indices])
    return matrix[better] - matrix[worse]


def symmetric_design(differences: Any) -> tuple[Any, np.ndarray]:
    if hasattr(differences, "tocsr"):
        from scipy import sparse

        design = sparse.vstack([differences, -differences], format="csr")
    else:
        design = np.vstack([differences, -differences])
    labels = np.concatenate(
        [np.ones(differences.shape[0], dtype=np.int8), np.zeros(differences.shape[0], dtype=np.int8)]
    )
    return design, labels


def ensure_fit_valid_isolation(
    rows: Sequence[dict[str, Any]], fit_indices: Sequence[int], valid_indices: Sequence[int]
) -> dict[str, int]:
    fit_runs = {str(rows[index]["run"]) for index in fit_indices}
    valid_runs = {str(rows[index]["run"]) for index in valid_indices}
    fit_endpoints = {
        str(rows[index][key]) for index in fit_indices for key in ("better", "worse")
    }
    valid_endpoints = {
        str(rows[index][key]) for index in valid_indices for key in ("better", "worse")
    }
    if fit_runs & valid_runs:
        raise IntegrityError("outer physical-run overlap")
    if fit_endpoints & valid_endpoints:
        raise IntegrityError("outer endpoint overlap")
    return {
        "fit_runs": len(fit_runs),
        "valid_runs": len(valid_runs),
        "fit_endpoints": len(fit_endpoints),
        "valid_endpoints": len(valid_endpoints),
        "run_overlap": 0,
        "endpoint_overlap": 0,
    }


def fit_linear_scores(
    matrix: np.ndarray,
    position: dict[str, int],
    rows: Sequence[dict[str, Any]],
    fit_indices: Sequence[int],
    valid_ids: Sequence[str],
    columns: Sequence[int],
    c_value: float,
) -> tuple[dict[str, float], dict[str, Any]]:
    from sklearn.exceptions import ConvergenceWarning
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    start = time.perf_counter()
    selected = np.asarray(columns, dtype=np.int64)
    subset = np.asarray(matrix[:, selected], dtype=np.float64)
    diff = pair_differences(subset, position, rows, fit_indices)
    design, labels = symmetric_design(diff)
    scaler = StandardScaler(with_mean=False).fit(design)
    transformed = scaler.transform(design)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        model = LogisticRegression(
            C=c_value,
            fit_intercept=False,
            max_iter=2_000,
            random_state=SEED,
            solver="liblinear",
            tol=1e-6,
        ).fit(transformed, labels)
    convergence = [str(item.message) for item in caught if issubclass(item.category, ConvergenceWarning)]
    if convergence:
        raise IntegrityError(f"linear convergence warning: {convergence}")
    valid_pos = np.asarray([position[card_id] for card_id in valid_ids], dtype=np.int64)
    endpoint_scores = model.decision_function(scaler.transform(subset[valid_pos]))
    if not np.isfinite(endpoint_scores).all():
        raise IntegrityError("non-finite linear scores")
    return dict(zip(valid_ids, map(float, endpoint_scores))), {
        "accepted": True,
        "c": c_value,
        "features": len(columns),
        "iterations": int(model.n_iter_[0]),
        "training_rows_symmetric": int(design.shape[0]),
        "elapsed_s": time.perf_counter() - start,
        "coefficient_norm": float(np.linalg.norm(model.coef_)),
        "scaler_scale_min": float(np.min(scaler.scale_)),
        "scaler_scale_max": float(np.max(scaler.scale_)),
    }


def aggregate_pair_logits(
    rows: Sequence[dict[str, Any]],
    valid_indices: Sequence[int],
    logits: Sequence[float],
) -> dict[str, float]:
    totals: dict[str, float] = collections.defaultdict(float)
    counts: dict[str, int] = collections.defaultdict(int)
    for index, logit in zip(valid_indices, logits):
        better = str(rows[index]["better"])
        worse = str(rows[index]["worse"])
        totals[better] += float(logit)
        totals[worse] -= float(logit)
        counts[better] += 1
        counts[worse] += 1
    if not totals or set(totals) != set(counts) or any(value <= 0 for value in counts.values()):
        raise IntegrityError("invalid pair-logit aggregation")
    return {card_id: totals[card_id] / counts[card_id] for card_id in totals}


def fit_static_gbm_scores(
    matrix: np.ndarray,
    position: dict[str, int],
    rows: Sequence[dict[str, Any]],
    fit_indices: Sequence[int],
    valid_indices: Sequence[int],
) -> tuple[dict[str, float], dict[str, Any]]:
    from sklearn.ensemble import HistGradientBoostingClassifier

    start = time.perf_counter()
    diff = np.asarray(pair_differences(matrix, position, rows, fit_indices), dtype=np.float64)
    design, labels = symmetric_design(diff)
    model = HistGradientBoostingClassifier(
        early_stopping=False,
        learning_rate=0.08,
        max_iter=300,
        random_state=SEED,
    ).fit(design, labels)
    valid_diff = np.asarray(pair_differences(matrix, position, rows, valid_indices), dtype=np.float64)
    probability = np.clip(model.predict_proba(valid_diff)[:, 1], 1e-6, 1.0 - 1e-6)
    logits = np.log(probability / (1.0 - probability))
    if not np.isfinite(logits).all():
        raise IntegrityError("non-finite static GBM logits")
    scores = aggregate_pair_logits(rows, valid_indices, logits)
    return scores, {
        "accepted": True,
        "features": int(matrix.shape[1]),
        "iterations": int(model.n_iter_),
        "training_rows_symmetric": int(design.shape[0]),
        "elapsed_s": time.perf_counter() - start,
        "logit_min": float(np.min(logits)),
        "logit_max": float(np.max(logits)),
    }


def fit_tfidf_scores(
    cards: dict[str, dict[str, Any]],
    rows: Sequence[dict[str, Any]],
    fit_indices: Sequence[int],
    valid_indices: Sequence[int],
) -> tuple[dict[str, float], dict[str, Any]]:
    from scipy import sparse
    from sklearn.exceptions import ConvergenceWarning
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression

    start = time.perf_counter()
    fit_ids = sorted(
        {str(rows[index][key]) for index in fit_indices for key in ("better", "worse")}
    )
    valid_ids = sorted(
        {str(rows[index][key]) for index in valid_indices for key in ("better", "worse")}
    )
    if set(fit_ids) & set(valid_ids):
        raise IntegrityError("TF-IDF endpoint overlap")
    vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        dtype=np.float64,
        max_features=30_000,
        min_df=3,
        ngram_range=(3, 5),
        sublinear_tf=True,
    )
    fit_matrix = vectorizer.fit_transform([code_view(str(cards[card_id]["code"])) for card_id in fit_ids])
    valid_matrix = vectorizer.transform([code_view(str(cards[card_id]["code"])) for card_id in valid_ids])
    fit_position = {card_id: index for index, card_id in enumerate(fit_ids)}
    differences = pair_differences(fit_matrix, fit_position, rows, fit_indices)
    design, labels = symmetric_design(differences)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        model = LogisticRegression(
            C=0.5,
            fit_intercept=False,
            max_iter=2_000,
            random_state=SEED,
            solver="liblinear",
            tol=1e-6,
        ).fit(design, labels)
    convergence = [str(item.message) for item in caught if issubclass(item.category, ConvergenceWarning)]
    if convergence:
        raise IntegrityError(f"TF-IDF convergence warning: {convergence}")
    endpoint_scores = np.asarray(valid_matrix @ model.coef_.reshape(-1), dtype=np.float64).reshape(-1)
    if not np.isfinite(endpoint_scores).all():
        raise IntegrityError("non-finite TF-IDF scores")
    vocabulary_payload = sorted((term, int(index)) for term, index in vectorizer.vocabulary_.items())
    return dict(zip(valid_ids, map(float, endpoint_scores))), {
        "accepted": True,
        "fit_endpoints": len(fit_ids),
        "valid_endpoints": len(valid_ids),
        "vocabulary": len(vectorizer.vocabulary_),
        "vocabulary_sha256": json_digest(vocabulary_payload),
        "idf_sha256": hashlib.sha256(np.asarray(vectorizer.idf_, dtype="<f8").tobytes()).hexdigest(),
        "iterations": int(model.n_iter_[0]),
        "training_rows_symmetric": int(design.shape[0]),
        "training_matrix_nnz": int(sparse.csr_matrix(design).nnz),
        "truncated_fit_codes": sum(len(str(cards[card_id]["code"])) > 20_000 for card_id in fit_ids),
        "truncated_valid_codes": sum(len(str(cards[card_id]["code"])) > 20_000 for card_id in valid_ids),
        "coefficient_norm": float(np.linalg.norm(model.coef_)),
        "elapsed_s": time.perf_counter() - start,
    }


def run_fold(
    fold: int,
    rows: Sequence[dict[str, Any]],
    fold_assignment: Sequence[int],
    cards: dict[str, dict[str, Any]],
    static_matrix: np.ndarray,
    position: dict[str, int],
    op_indices: Sequence[int],
    output_root: Path | None,
    checkpoint_key: str,
) -> tuple[dict[str, dict[str, float]], dict[str, Any]]:
    if output_root is not None:
        final_dir = output_root / f"fold_{fold}"
        if final_dir.exists():
            previous = json.loads((final_dir / "fold_summary.json").read_text(encoding="utf-8"))
            if (
                previous.get("status") != "FOLD_COMPLETE"
                or int(previous.get("fold", -1)) != fold
                or str(previous.get("checkpoint_key")) != checkpoint_key
            ):
                raise IntegrityError(f"invalid existing fold checkpoint: {fold}")
            score_path = final_dir / "valid_scores.npz"
            if sha256(score_path) != str(previous.get("valid_scores_sha256")):
                raise IntegrityError(f"existing fold score SHA mismatch: {fold}")
            with np.load(score_path, allow_pickle=False) as data:
                ids = [str(item) for item in data["card_ids"].tolist()]
                restored = {
                    arm: dict(zip(ids, map(float, np.asarray(data[arm], dtype=np.float64))))
                    for arm in BASE_ARMS
                }
            return restored, previous
    fit_indices = [index for index, assigned in enumerate(fold_assignment) if assigned != fold]
    valid_indices = [index for index, assigned in enumerate(fold_assignment) if assigned == fold]
    isolation = ensure_fit_valid_isolation(rows, fit_indices, valid_indices)
    valid_ids = sorted(
        {str(rows[index][key]) for index in valid_indices for key in ("better", "worse")}
    )
    scores: dict[str, dict[str, float]] = {}
    diagnostics: dict[str, Any] = {}
    scores["op_only_lr"], diagnostics["op_only_lr"] = fit_linear_scores(
        static_matrix, position, rows, fit_indices, valid_ids, op_indices, 1.0
    )
    scores["static_lr"], diagnostics["static_lr"] = fit_linear_scores(
        static_matrix,
        position,
        rows,
        fit_indices,
        valid_ids,
        list(range(static_matrix.shape[1])),
        1.0,
    )
    scores["static_gbm"], diagnostics["static_gbm"] = fit_static_gbm_scores(
        static_matrix, position, rows, fit_indices, valid_indices
    )
    scores[PRIMARY_ARM], diagnostics[PRIMARY_ARM] = fit_tfidf_scores(
        cards, rows, fit_indices, valid_indices
    )
    expected_ids = set(valid_ids)
    for arm in BASE_ARMS:
        if set(scores[arm]) != expected_ids or not all(math.isfinite(value) for value in scores[arm].values()):
            raise IntegrityError(f"fold {fold} score coverage mismatch: {arm}")
    summary = {
        "status": "FOLD_COMPLETE",
        "protocol": PROTOCOL,
        "checkpoint_key": checkpoint_key,
        "fold": fold,
        "fit_pairs": len(fit_indices),
        "valid_pairs": len(valid_indices),
        **isolation,
        "diagnostics": diagnostics,
    }
    if output_root is not None:
        final_dir = output_root / f"fold_{fold}"
        temporary = output_root / f".fold_{fold}.tmp"
        if temporary.exists():
            raise FileExistsError(f"stale temporary fold checkpoint: {temporary}")
        temporary.mkdir(parents=True)
        atomic_npz(
            temporary / "valid_scores.npz",
            card_ids=np.asarray(valid_ids),
            **{arm: np.asarray([scores[arm][card_id] for card_id in valid_ids], dtype=np.float64) for arm in BASE_ARMS},
        )
        summary["valid_scores_sha256"] = sha256(temporary / "valid_scores.npz")
        atomic_json(temporary / "fold_summary.json", summary)
        os.replace(temporary, final_dir)
    return scores, summary


def parent_rank_ensemble(
    rows: Sequence[dict[str, Any]],
    left: dict[str, float],
    right: dict[str, float],
) -> dict[str, float]:
    grouped: dict[str, set[str]] = collections.defaultdict(set)
    endpoint_parent: dict[str, str] = {}
    for row in rows:
        parent = str(row["parent"])
        for key in ("better", "worse"):
            card_id = str(row[key])
            previous = endpoint_parent.setdefault(card_id, parent)
            if previous != parent:
                raise IntegrityError(f"endpoint appears under multiple parents: {card_id}")
            grouped[parent].add(card_id)
    output: dict[str, float] = {}
    for candidates in grouped.values():
        ids = sorted(candidates)
        denominator = max(len(ids) - 1, 1)
        left_rank = (average_ranks([left[card_id] for card_id in ids]) - 1.0) / denominator
        right_rank = (average_ranks([right[card_id] for card_id in ids]) - 1.0) / denominator
        for card_id, value in zip(ids, (left_rank + right_rank) / 2.0):
            output[card_id] = float(value)
    return output


def average_ranks(values: Sequence[float]) -> np.ndarray:
    """Equivalent to scipy.stats.rankdata(method='average'), without a SciPy import."""
    array = np.asarray(values, dtype=np.float64)
    order = np.argsort(array, kind="mergesort")
    ranks = np.empty(len(array), dtype=np.float64)
    start = 0
    while start < len(order):
        end = start + 1
        while end < len(order) and array[order[end]] == array[order[start]]:
            end += 1
        ranks[order[start:end]] = (start + 1 + end) / 2.0
        start = end
    return ranks


def orientation_oracle_scores(rows: Sequence[dict[str, Any]]) -> dict[str, float]:
    grouped: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in rows:
        grouped[str(row["parent"])].append(row)
    output: dict[str, float] = {}
    for parent_rows in grouped.values():
        candidates = {str(row[key]) for row in parent_rows for key in ("better", "worse")}
        losses = collections.Counter({card_id: 0 for card_id in candidates})
        for row in parent_rows:
            losses[str(row["worse"])] += 1
        for card_id, value in losses.items():
            if card_id in output:
                raise IntegrityError(f"oracle endpoint appears under multiple parents: {card_id}")
            output[card_id] = -float(value)
    return output


def stripped_metrics(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if not key.startswith("_")}


def correctness_phi(left: Sequence[float], right: Sequence[float]) -> float | None:
    x = np.asarray(left, dtype=np.float64)
    y = np.asarray(right, dtype=np.float64)
    if np.std(x) <= EPSILON or np.std(y) <= EPSILON:
        return None
    return float(np.corrcoef(x, y)[0, 1])


def complementarity(
    candidate: dict[str, Any], baseline: dict[str, Any]
) -> dict[str, Any]:
    left_hits = list(map(float, candidate["_hits"]))
    right_hits = list(map(float, baseline["_hits"]))
    if len(left_hits) != len(right_hits):
        raise IntegrityError("pair hit support mismatch")
    left_top = candidate["_top1_records"]
    right_top = baseline["_top1_records"]
    if set(left_top) != set(right_top):
        raise IntegrityError("parent top1 support mismatch")
    deltas = [float(left_top[key]["value"]) - float(right_top[key]["value"]) for key in sorted(left_top)]
    oracle = [
        max(float(left_top[key]["value"]), float(right_top[key]["value"]))
        for key in sorted(left_top)
    ]
    oracle_top1 = sum(oracle) / len(oracle)
    better_individual = max(
        float(candidate["top1"]["overall"]), float(baseline["top1"]["overall"])
    )
    return {
        "pair_disagreement": sum(abs(a - b) > EPSILON for a, b in zip(left_hits, right_hits)) / len(left_hits),
        "pair_correctness_phi": correctness_phi(left_hits, right_hits),
        "weighted_parent_rescue": sum(max(value, 0.0) for value in deltas) / len(deltas),
        "weighted_parent_harm": sum(max(-value, 0.0) for value in deltas) / len(deltas),
        "oracle_union_top1": oracle_top1,
        "oracle_headroom_over_better_individual": oracle_top1 - better_individual,
        "parents": len(deltas),
    }


def nested_ensemble_gate(
    metrics: dict[str, Any],
    comparison: dict[str, Any],
    complement: dict[str, Any],
) -> dict[str, bool]:
    return {
        "pair_ge_052": float(metrics["pair"]["overall"]) >= 0.52,
        "top1_ge_046": float(metrics["top1"]["overall"]) >= 0.46,
        "utility_ge_0525": float(metrics["utility"]["overall"]) >= 0.525,
        "task_nonchance_share_ge_060": float(metrics["task_consistency"]["nonchance_share"]) >= 0.60,
        "pair_disagreement_ge_015": float(complement["pair_disagreement"]) >= 0.15,
        "weighted_parent_rescue_ge_008": float(complement["weighted_parent_rescue"]) >= 0.08,
        "oracle_headroom_ge_005": float(complement["oracle_headroom_over_better_individual"]) >= 0.05,
        "top1_run_ci_low_ge_minus002": float(comparison["top1"]["run_macro_ci95"][0]) >= -0.02,
        "top1_task_ci_low_ge_minus002": float(comparison["top1"]["task_macro_ci95"][0]) >= -0.02,
        "utility_run_ci_low_ge_minus002": float(comparison["utility"]["run_macro_ci95"][0]) >= -0.02,
        "utility_task_ci_low_ge_minus002": float(comparison["utility"]["task_macro_ci95"][0]) >= -0.02,
    }


def unlock_gate(
    metrics: dict[str, Any], comparison: dict[str, Any], integrity: dict[str, bool]
) -> dict[str, bool]:
    output = {
        "pair_ge_052": float(metrics["pair"]["overall"]) >= 0.52,
        "top1_ge_050": float(metrics["top1"]["overall"]) >= 0.50,
        "top1_delta_ge_003": float(comparison["top1"]["overall"]) >= 0.03,
        "utility_ge_055": float(metrics["utility"]["overall"]) >= 0.55,
        "utility_delta_ge_002": float(comparison["utility"]["overall"]) >= 0.02,
        "top1_run_ci_low_gt_0": float(comparison["top1"]["run_macro_ci95"][0]) > 0.0,
        "top1_task_ci_low_gt_0": float(comparison["top1"]["task_macro_ci95"][0]) > 0.0,
        "utility_run_ci_low_gt_0": float(comparison["utility"]["run_macro_ci95"][0]) > 0.0,
        "utility_task_ci_low_gt_0": float(comparison["utility"]["task_macro_ci95"][0]) > 0.0,
        "supported_tasks_ge_15": int(metrics["task_consistency"]["supported_tasks"]) >= 15,
        "task_nonchance_share_ge_060": float(metrics["task_consistency"]["nonchance_share"]) >= 0.60,
        **integrity,
    }
    output["all"] = all(output.values())
    return output


def equal_rank_gate(comparison: dict[str, Any]) -> dict[str, bool]:
    output = {
        "top1_delta_ge_0015": float(comparison["top1"]["overall"]) >= 0.015,
        "utility_delta_ge_001": float(comparison["utility"]["overall"]) >= 0.01,
        "top1_run_ci_low_ge_minus001": float(comparison["top1"]["run_macro_ci95"][0]) >= -0.01,
        "top1_task_ci_low_ge_minus001": float(comparison["top1"]["task_macro_ci95"][0]) >= -0.01,
        "utility_run_ci_low_ge_minus001": float(comparison["utility"]["run_macro_ci95"][0]) >= -0.01,
        "utility_task_ci_low_ge_minus001": float(comparison["utility"]["task_macro_ci95"][0]) >= -0.01,
    }
    output["all"] = all(output.values())
    return output


def write_predictions(
    path: Path,
    rows: Sequence[dict[str, Any]],
    fold_assignment: Sequence[int],
    all_scores: dict[str, dict[str, float]],
) -> str:
    fields = ["row_index", "task", "run", "parent", "better", "worse", "gap_raw", "fold"]
    for arm in ARMS:
        fields.extend((f"{arm}_better_score", f"{arm}_worse_score", f"{arm}_margin", f"{arm}_hit"))
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row, fold in zip(rows, fold_assignment):
            output = {
                "row_index": row["row_index"],
                "task": row["task"],
                "run": row["run"],
                "parent": row["parent"],
                "better": row["better"],
                "worse": row["worse"],
                "gap_raw": format(float(row["gap_raw"]), ".17g"),
                "fold": fold,
            }
            for arm in ARMS:
                better = float(all_scores[arm][str(row["better"])])
                worse = float(all_scores[arm][str(row["worse"])])
                margin = better - worse
                output.update(
                    {
                        f"{arm}_better_score": format(better, ".17g"),
                        f"{arm}_worse_score": format(worse, ".17g"),
                        f"{arm}_margin": format(margin, ".17g"),
                        f"{arm}_hit": format(baseline_module.tie_hit(margin), ".17g"),
                    }
                )
            writer.writerow(output)
    os.replace(temporary, path)
    return sha256(path)


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--pairs", required=True, type=Path)
    parser.add_argument("--run-map", required=True, type=Path)
    parser.add_argument("--cards", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--manifest-summary", required=True, type=Path)
    parser.add_argument("--baseline-oof", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--expect-pairs-sha256", required=True)
    parser.add_argument("--expect-run-map-sha256", required=True)
    parser.add_argument("--expect-cards-sha256", required=True)
    parser.add_argument("--expect-manifest-sha256", required=True)
    parser.add_argument("--expect-baseline-sha256", required=True)
    parser.add_argument("--wall-cap-s", type=float, default=3_600.0)
    return parser.parse_args()


def main() -> int:
    args = arguments()
    started = time.perf_counter()
    for path, label in (
        (args.pairs, "training pairs"),
        (args.run_map, "run map"),
        (args.cards, "source cards"),
        (args.manifest, "train manifest"),
        (args.manifest_summary, "train manifest summary"),
        (args.baseline_oof, "baseline OOF"),
    ):
        reject_forbidden_path(path, label)
    if (args.out_dir / "summary.json").exists():
        raise FileExistsError(f"refusing to overwrite completed output: {args.out_dir}")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_root = args.out_dir / "checkpoints"
    checkpoint_root.mkdir(exist_ok=True)

    manifest, manifest_summary = load_manifest(
        args.manifest, args.manifest_summary, args.expect_manifest_sha256
    )
    cards, card_audit = load_train_cards(args.cards, manifest, args.expect_cards_sha256)
    rows, pair_audit, pairs_sha = baseline_module.load_pairs(args.pairs, manifest, args.run_map)
    if pairs_sha != args.expect_pairs_sha256.lower():
        raise IntegrityError("pairs SHA mismatch")
    if sha256(args.run_map) != args.expect_run_map_sha256.lower():
        raise IntegrityError("run-map SHA mismatch")
    folds, baseline_scores, baseline_audit = metric_module.load_locked_baseline(
        args.baseline_oof, rows, args.expect_baseline_sha256
    )
    for key in ("pairs", "runs", "tasks", "parents", "endpoints"):
        if int(pair_audit[key]) != EXPECTED[key]:
            raise IntegrityError(f"pair audit mismatch {key}: {pair_audit[key]}")

    ids = sorted(cards)
    position = {card_id: index for index, card_id in enumerate(ids)}
    names, op_indices = feature_names(cards[ids[0]])
    static_matrix = np.asarray(
        [[static_feature_dict(cards[card_id])[name] for name in names] for card_id in ids],
        dtype=np.float64,
    )
    if not np.isfinite(static_matrix).all():
        raise IntegrityError("non-finite static feature matrix")

    checkpoint_contract = {
        "protocol": PROTOCOL,
        "git_commit": git_commit(args.repo_root),
        "source_sha256": sha256(Path(__file__)),
        "pairs_sha256": pairs_sha,
        "run_map_sha256": sha256(args.run_map),
        "cards_sha256": card_audit["cards_sha256"],
        "manifest_sha256": sha256(args.manifest),
        "baseline_oof_sha256": baseline_audit["sha256"],
        "arms": list(ARMS),
        "seed": SEED,
    }
    checkpoint_key = json_digest(checkpoint_contract)
    contract_path = args.out_dir / "checkpoint_contract.json"
    if contract_path.exists():
        previous_contract = json.loads(contract_path.read_text(encoding="utf-8"))
        if previous_contract != {**checkpoint_contract, "checkpoint_key": checkpoint_key}:
            raise IntegrityError("checkpoint contract mismatch")
    else:
        atomic_json(contract_path, {**checkpoint_contract, "checkpoint_key": checkpoint_key})

    all_scores: dict[str, dict[str, float]] = {arm: {} for arm in BASE_ARMS}
    fold_summaries: list[dict[str, Any]] = []
    for fold in range(OUTER_FOLDS):
        scores, fold_summary = run_fold(
            fold,
            rows,
            folds,
            cards,
            static_matrix,
            position,
            op_indices,
            checkpoint_root,
            checkpoint_key,
        )
        for arm in BASE_ARMS:
            overlap = set(all_scores[arm]) & set(scores[arm])
            if overlap:
                raise IntegrityError(f"OOF endpoint overlap for {arm}: {sorted(overlap)[:4]}")
            all_scores[arm].update(scores[arm])
        fold_summaries.append(fold_summary)
        print(f"FOLD_COMPLETE {fold}", flush=True)
    expected_ids = set(ids)
    for arm in BASE_ARMS:
        if set(all_scores[arm]) != expected_ids:
            raise IntegrityError(f"global OOF score coverage mismatch: {arm}")
    all_scores[BASELINE_ARM] = baseline_scores
    all_scores[EQUAL_ARM] = parent_rank_ensemble(
        rows, baseline_scores, all_scores[PRIMARY_ARM]
    )

    oracle_scores = orientation_oracle_scores(rows)
    oracle_metrics = metric_module.model_metrics(rows, oracle_scores, 500)
    random_scores = {card_id: baseline_module.deterministic_random_score(card_id) for card_id in ids}
    random_metrics = metric_module.model_metrics(rows, random_scores, 520)
    metrics = {
        arm: metric_module.model_metrics(rows, all_scores[arm], METRIC_SEED_OFFSETS[arm])
        for arm in ARMS
    }
    comparisons = {
        arm: metric_module.paired_metric_comparison(metrics[arm], metrics[BASELINE_ARM], 600 + 20 * index)
        for index, arm in enumerate((*BASE_ARMS, EQUAL_ARM))
    }
    complements = {
        arm: complementarity(metrics[arm], metrics[BASELINE_ARM]) for arm in BASE_ARMS
    }
    integrity = {
        "all_fits_accepted": all(
            bool(fold["diagnostics"][arm]["accepted"])
            for fold in fold_summaries
            for arm in BASE_ARMS
        ),
        "baseline_hash_exact": baseline_audit["sha256"] == args.expect_baseline_sha256.lower(),
        "cards_hash_exact": card_audit["cards_sha256"] == args.expect_cards_sha256.lower(),
        "complete_parents_eq_2259": int(metrics[PRIMARY_ARM]["top1"]["complete_parents"]) == EXPECTED["complete_parents"],
        "coverage_exact": all(set(scores) == expected_ids for scores in all_scores.values()),
        "endpoints_eq_5499": len(ids) == EXPECTED["endpoints"],
        "frozen_read_false": True,
        "label_fields_retained_zero": int(card_audit["label_fields_retained"]) == 0,
        "orientation_oracle_eq_1": float(oracle_metrics["pair"]["overall"]) == 1.0,
        "outer_endpoint_overlap_eq_0": all(int(fold["endpoint_overlap"]) == 0 for fold in fold_summaries),
        "outer_run_overlap_eq_0": all(int(fold["run_overlap"]) == 0 for fold in fold_summaries),
        "pairs_eq_4263": len(rows) == EXPECTED["pairs"],
        "parents_eq_2293": int(pair_audit["parents"]) == EXPECTED["parents"],
        "post_execution_fields_retained_zero": int(card_audit["post_execution_fields_retained"]) == 0,
        "random_pair_in_047_053": 0.47 <= float(random_metrics["pair"]["overall"]) <= 0.53,
        "runs_eq_333": int(pair_audit["runs"]) == EXPECTED["runs"],
        "tasks_eq_23": int(pair_audit["tasks"]) == EXPECTED["tasks"],
    }
    primary_gate = unlock_gate(metrics[PRIMARY_ARM], comparisons[PRIMARY_ARM], integrity)
    nested_gates: dict[str, dict[str, bool]] = {}
    for arm in BASE_ARMS:
        gate = nested_ensemble_gate(metrics[arm], comparisons[arm], complements[arm])
        gate["all"] = all(gate.values()) and all(integrity.values())
        nested_gates[arm] = gate
    equal_gate = equal_rank_gate(comparisons[EQUAL_ARM])
    equal_gate["all"] = bool(equal_gate["all"] and all(integrity.values()))

    runtime = time.perf_counter() - started
    integrity["formal_runtime_le_cap"] = runtime <= args.wall_cap_s
    # Runtime is known only now, so fold it into every final gate.
    primary_gate["formal_runtime_le_cap"] = integrity["formal_runtime_le_cap"]
    primary_gate["all"] = all(value for key, value in primary_gate.items() if key != "all")
    for gate in nested_gates.values():
        gate["formal_runtime_le_cap"] = integrity["formal_runtime_le_cap"]
        gate["all"] = all(value for key, value in gate.items() if key != "all") and all(integrity.values())
    equal_gate["formal_runtime_le_cap"] = integrity["formal_runtime_le_cap"]
    equal_gate["all"] = all(value for key, value in equal_gate.items() if key != "all") and all(integrity.values())

    if primary_gate["all"]:
        status = "DISCOVERY_UNLOCK_RECOMMENDED"
    elif any(gate["all"] for gate in nested_gates.values()):
        status = "DISCOVERY_NO_UNLOCK_GO_NESTED_ENSEMBLE"
    else:
        status = "DISCOVERY_NO_UNLOCK_NO_ENSEMBLE"

    predictions_path = args.out_dir / "oof_predictions.csv"
    predictions_sha = write_predictions(predictions_path, rows, folds, all_scores)
    summary = {
        "status": status,
        "protocol": PROTOCOL,
        "checkpoint_key": checkpoint_key,
        "git_commit": git_commit(args.repo_root),
        "frozen_read": False,
        "configuration": {
            "seed": SEED,
            "outer_folds": OUTER_FOLDS,
            "arms": list(ARMS),
            "primary_arm": PRIMARY_ARM,
            "tfidf": {
                "analyzer": "char_wb",
                "ngram_range": [3, 5],
                "max_features": 30_000,
                "min_df": 3,
                "sublinear_tf": True,
                "code_view": "all_if_le_20000_else_head5000_tail15000",
                "lr_c": 0.5,
            },
            "static_lr_c": 1.0,
            "static_gbm": {"max_iter": 300, "learning_rate": 0.08, "early_stopping": False},
            "equal_rank": "parent_percentile_rank_mean(fixed_frozen_global,char_tfidf_lr)",
        },
        "inputs": {
            "pairs_sha256": pairs_sha,
            "run_map_sha256": sha256(args.run_map),
            "cards_sha256": card_audit["cards_sha256"],
            "manifest_sha256": sha256(args.manifest),
            "manifest_summary_sha256": sha256(args.manifest_summary),
            "baseline_oof_sha256": baseline_audit["sha256"],
        },
        "pair_audit": pair_audit,
        "card_audit": card_audit,
        "baseline_audit": baseline_audit,
        "manifest_summary": manifest_summary,
        "static_features": {"names": names, "op_indices": list(op_indices), "dimension": len(names)},
        "folds": fold_summaries,
        "metrics": {arm: stripped_metrics(metrics[arm]) for arm in ARMS},
        "paired_delta_vs_fixed_frozen": comparisons,
        "complementarity_vs_fixed_frozen": complements,
        "orientation_oracle": stripped_metrics(oracle_metrics),
        "random_control": stripped_metrics(random_metrics),
        "integrity_gate": integrity,
        "primary_unlock_gate": primary_gate,
        "nested_ensemble_gates": nested_gates,
        "equal_rank_gate": equal_gate,
        "runtime_s": runtime,
        "wall_cap_s": args.wall_cap_s,
        "outputs": {
            "oof_predictions": str(predictions_path),
            "oof_predictions_sha256": predictions_sha,
            "checkpoint_root": str(checkpoint_root),
        },
        "software": {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
        },
        "source_sha256": sha256(Path(__file__)),
    }
    atomic_json(args.out_dir / "summary.json", summary)
    print(
        status,
        f"primary_pair={metrics[PRIMARY_ARM]['pair']['overall']:.6f}",
        f"primary_top1={metrics[PRIMARY_ARM]['top1']['overall']:.6f}",
        f"primary_utility={metrics[PRIMARY_ARM]['utility']['overall']:.6f}",
        f"nested_go={','.join(arm for arm, gate in nested_gates.items() if gate['all']) or 'none'}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
