"""Fixed decision-time static baselines on the component-preserving critic split."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import zlib
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from phase1.critic_component_tfidf_baseline import (
    EXPECTED,
    canonical,
    compact,
    pair_key,
    quantiles,
    read_rows,
    semantics_map,
    sha256_file,
    validate_splits,
)


PROTOCOL = "critic-component-static-suite-v1"
TFIDF_PAIR_SHA256 = "021f8b3c74db89c6b770714edb879731799b145744af7b765005eed72f9ecde6"
TASK_SEED = 20260821
PARENT_SEED = 20260822
BOOTSTRAP_REPS = 20_000
LEARNED_MODELS = (
    "static_lr_pooled",
    "static_gbm_pooled",
    "static_lr_task",
    "static_gbm_task",
)
MODEL_ORDER = LEARNED_MODELS
SINGLE_FEATURES = ("code_len", "n_lines", "depth", "step", "n_cv", "n_ensemble")
SUBSETS = ("merged", "Draft", "Improve")

IMPORT_RX = re.compile(r"^\s*(?:from|import)\s+([\w.]+)", re.MULTILINE)
MODEL_WORDS = (
    "lightgbm", "xgboost", "catboost", "randomforest", "logisticregression",
    "ridge", "svc", "torch", "transformers", "bert", "resnet", "efficientnet",
    "timm", "keras", "sklearn",
)
CV_WORDS = ("kfold", "stratifiedkfold", "groupkfold", "cross_val", "train_test_split")
RISK_WORDS = (
    "fit_transform(test", "fit(test", ".append(test", "concat([train, test",
    "pd.concat([train,test",
)


class SuiteError(RuntimeError):
    """Raised when a frozen suite contract is violated."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SuiteError(message)


def array_sha(value: np.ndarray) -> str:
    return hashlib.sha256(np.asarray(value, dtype="<f8").tobytes()).hexdigest()


def verify_input_identity(path: Path, role: str) -> None:
    expected_hash, expected_bytes = EXPECTED[role]
    require(
        path.stat().st_size == expected_bytes and sha256_file(path) == expected_hash,
        f"{role} input identity mismatch",
    )


def feature_dict(card: dict[str, Any]) -> dict[str, float]:
    code = card.get("code")
    lineage = card.get("lineage")
    require(isinstance(code, str) and isinstance(lineage, dict), "needed card lacks code/lineage")
    low = code.lower()
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
            low.count("optuna") + low.count("gridsearch")
            + low.count("param_grid") + low.count("hyperopt")
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
    require(len(features) == 34, "feature inventory is not 34")
    return features


FEATURE_NAMES = tuple(sorted(feature_dict({"code": "", "lineage": {}})))


def load_cards(
    path: Path, needed: set[str]
) -> tuple[dict[str, np.ndarray], dict[str, str], dict[str, tuple[Any, ...]], dict[str, str], dict[str, int]]:
    grouped = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(grouped, dict), "cards root is not grouped")
    features: dict[str, np.ndarray] = {}
    runs: dict[str, str] = {}
    configs: dict[str, tuple[Any, ...]] = {}
    tasks: dict[str, str] = {}
    seen: set[str] = set()
    total = 0
    for run_id, cards in grouped.items():
        require(isinstance(run_id, str) and isinstance(cards, list), "invalid card group")
        for card in cards:
            total += 1
            require(
                isinstance(card, dict) and isinstance(card.get("id"), str) and card["id"] not in seen,
                "invalid or duplicate card",
            )
            card_id = card["id"]
            seen.add(card_id)
            if card_id not in needed:
                continue
            task_object = card.get("task")
            task = task_object.get("name") if isinstance(task_object, dict) else None
            config = (
                task,
                card.get("client"),
                card.get("hardware"),
                card.get("time_limit"),
                card.get("execution_timeout"),
            )
            require(
                all(isinstance(value, str) and value for value in config[:3])
                and all(isinstance(value, int) for value in config[3:]),
                "needed card lacks provenance",
            )
            values = feature_dict(card)
            vector = np.asarray([values[name] for name in FEATURE_NAMES], dtype=np.float64)
            require(np.isfinite(vector).all(), "non-finite static feature")
            features[card_id] = vector
            runs[card_id] = run_id
            configs[card_id] = config
            tasks[card_id] = task
    require(set(features) == needed, "pair endpoint missing from cards")
    return features, runs, configs, tasks, {
        "cards": total,
        "run_groups": len(grouped),
        "needed_cards": len(needed),
    }


def differences(rows: list[dict[str, Any]], features: dict[str, np.ndarray]) -> np.ndarray:
    return np.vstack([features[row["better"]] - features[row["worse"]] for row in rows])


def augmented(values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    return np.vstack((values, -values)), np.concatenate(
        (np.ones(len(values), dtype=np.int8), np.zeros(len(values), dtype=np.int8))
    )


def task_interactions(
    values: np.ndarray, rows: list[dict[str, Any]], task_index: dict[str, int]
) -> tuple[np.ndarray, np.ndarray]:
    width = values.shape[1]
    output = np.zeros((len(rows), width * (len(task_index) + 1)), dtype=np.float64)
    known = np.ones(len(rows), dtype=bool)
    output[:, :width] = values
    for index, row in enumerate(rows):
        position = task_index.get(row["task"])
        if position is None:
            known[index] = False
            continue
        start = width * (position + 1)
        output[index, start : start + width] = values[index]
    return output, known


def task_conditioned(
    values: np.ndarray, rows: list[dict[str, Any]], task_index: dict[str, int]
) -> tuple[np.ndarray, np.ndarray]:
    output = np.zeros((len(rows), values.shape[1] + len(task_index)), dtype=np.float64)
    known = np.ones(len(rows), dtype=bool)
    output[:, : values.shape[1]] = values
    for index, row in enumerate(rows):
        position = task_index.get(row["task"])
        if position is None:
            known[index] = False
        else:
            output[index, values.shape[1] + position] = 1.0
    return output, known


def lr_fit(values: np.ndarray) -> tuple[StandardScaler, LogisticRegression, dict[str, Any]]:
    fit_x, fit_y = augmented(values)
    scaler = StandardScaler(with_mean=False).fit(fit_x)
    transformed = scaler.transform(fit_x)
    model = LogisticRegression(
        C=1.0, max_iter=4000, solver="lbfgs", fit_intercept=False
    ).fit(transformed, fit_y)
    require(int(model.n_iter_[0]) < 4000, "static LR did not converge")
    require(np.isfinite(model.coef_).all(), "static LR coefficient is non-finite")
    return scaler, model, {
        "scaler_scale_sha256": array_sha(scaler.scale_),
        "coefficient_sha256": array_sha(model.coef_),
        "n_iter": int(model.n_iter_[0]),
        "fit_intercept": False,
    }


def lr_margin(values: np.ndarray, scaler: StandardScaler, model: LogisticRegression) -> np.ndarray:
    return np.asarray(scaler.transform(values).dot(model.coef_.reshape(-1)), dtype=np.float64)


def gbm_fit(values: np.ndarray) -> tuple[HistGradientBoostingClassifier, dict[str, Any]]:
    fit_x, fit_y = augmented(values)
    model = HistGradientBoostingClassifier(
        loss="log_loss",
        max_iter=300,
        learning_rate=0.08,
        max_leaf_nodes=31,
        max_depth=None,
        min_samples_leaf=20,
        l2_regularization=0.0,
        early_stopping=False,
        random_state=7,
    ).fit(fit_x, fit_y)
    require(model.n_iter_ == 300, "static GBM iteration mismatch")
    train_margin = 0.5 * (model.decision_function(values) - model.decision_function(-values))
    return model, {
        "n_iter": int(model.n_iter_),
        "train_margin_sha256": array_sha(train_margin),
        "parameters": {
            "loss": "log_loss", "max_iter": 300, "learning_rate": 0.08,
            "max_leaf_nodes": 31, "max_depth": None, "min_samples_leaf": 20,
            "l2_regularization": 0.0, "early_stopping": False, "random_state": 7,
        },
    }


def gbm_margin(values: np.ndarray, reverse: np.ndarray, model: HistGradientBoostingClassifier) -> np.ndarray:
    return 0.5 * (model.decision_function(values) - model.decision_function(reverse))


def task_accuracy_ci(rows: list[dict[str, Any]], values: np.ndarray) -> dict[str, Any] | None:
    tasks = sorted({row["task"] for row, value in zip(rows, values) if np.isfinite(value)})
    if not tasks:
        return None
    task_values = np.asarray(
        [np.mean([value for row, value in zip(rows, values) if row["task"] == task and np.isfinite(value)]) for task in tasks],
        dtype=np.float64,
    )
    rng = np.random.default_rng(TASK_SEED)
    sampled = rng.integers(0, len(tasks), size=(BOOTSTRAP_REPS, len(tasks)))
    estimates = np.mean(task_values[sampled], axis=1)
    low, high = np.quantile(estimates, [0.025, 0.975], method="linear")
    return {
        "point": float(np.mean(task_values)), "ci95": [float(low), float(high)],
        "clusters": len(tasks), "replicates": BOOTSTRAP_REPS, "seed": TASK_SEED,
    }


def parent_accuracy_ci(rows: list[dict[str, Any]], values: np.ndarray) -> dict[str, Any] | None:
    grouped: dict[tuple[str, str], list[float]] = defaultdict(list)
    for row, value in zip(rows, values):
        if np.isfinite(value):
            grouped[(row["task"], row["parent"])].append(float(value))
    if not grouped:
        return None
    clusters = sorted(grouped)
    arrays = [np.asarray(grouped[key], dtype=np.float64) for key in clusters]
    rng = np.random.default_rng(PARENT_SEED)
    estimates = np.empty(BOOTSTRAP_REPS, dtype=np.float64)
    for index in range(BOOTSTRAP_REPS):
        sampled = rng.integers(0, len(arrays), size=len(arrays))
        estimates[index] = sum(float(np.sum(arrays[item])) for item in sampled) / sum(
            len(arrays[item]) for item in sampled
        )
    low, high = np.quantile(estimates, [0.025, 0.975], method="linear")
    return {
        "point": float(np.mean(np.concatenate(arrays))), "ci95": [float(low), float(high)],
        "clusters": len(arrays), "replicates": BOOTSTRAP_REPS, "seed": PARENT_SEED,
    }


def model_metrics(
    rows: list[dict[str, Any]], margins: np.ndarray, semantic_values: list[str]
) -> tuple[
    dict[str, Any],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    output: dict[str, Any] = {}
    task_output = []
    parent_output = []
    for subset in SUBSETS:
        selected = np.asarray(
            [subset == "merged" or semantic == subset for semantic in semantic_values], dtype=bool
        )
        selected_rows = [row for row, keep in zip(rows, selected) if keep]
        selected_margins = margins[selected]
        evaluable = np.isfinite(selected_margins) & (selected_margins != 0)
        correctness = np.where(evaluable, (selected_margins > 0).astype(float), np.nan)
        task_ci = task_accuracy_ci(selected_rows, correctness)
        parent_ci = parent_accuracy_ci(selected_rows, correctness)
        output[subset] = {
            "pairs": len(selected_rows),
            "tasks": len({row["task"] for row in selected_rows}),
            "parents": len({(row["task"], row["parent"]) for row in selected_rows}),
            "evaluable_pairs": int(np.sum(evaluable)),
            "coverage": float(np.mean(evaluable)),
            "ties": int(np.sum(np.isfinite(selected_margins) & (selected_margins == 0))),
            "abstentions": int(np.sum(~np.isfinite(selected_margins))),
            "micro_accuracy": None if not np.any(evaluable) else float(np.nanmean(correctness)),
            "task_macro_accuracy": None if task_ci is None else task_ci["point"],
            "task_clustered": task_ci,
            "parent_clustered": parent_ci,
            "margin_quantiles": quantiles(selected_margins[evaluable]),
        }
        for task in sorted({row["task"] for row in selected_rows}):
            mask = np.asarray([row["task"] == task for row in selected_rows])
            task_values = correctness[mask]
            task_output.append({
                "subset": subset,
                "task": task,
                "pairs": int(np.sum(mask)),
                "evaluable_pairs": int(np.sum(np.isfinite(task_values))),
                "accuracy": None if not np.any(np.isfinite(task_values)) else float(np.nanmean(task_values)),
            })
        for task, parent in sorted({(row["task"], row["parent"]) for row in selected_rows}):
            mask = np.asarray([
                row["task"] == task and row["parent"] == parent for row in selected_rows
            ])
            parent_values = correctness[mask]
            parent_output.append({
                "subset": subset,
                "task": task,
                "parent": parent,
                "pairs": int(np.sum(mask)),
                "evaluable_pairs": int(np.sum(np.isfinite(parent_values))),
                "accuracy": None if not np.any(np.isfinite(parent_values)) else float(np.nanmean(parent_values)),
            })
    return output, task_output, parent_output


def paired_delta_ci(rows: list[dict[str, Any]], delta: np.ndarray, cluster: str) -> dict[str, Any]:
    if cluster == "task":
        keys = sorted({row["task"] for row in rows})
        arrays = [np.asarray([value for row, value in zip(rows, delta) if row["task"] == key]) for key in keys]
        point = float(np.mean([np.mean(values) for values in arrays]))
        rng = np.random.default_rng(TASK_SEED)
        sampled = rng.integers(0, len(arrays), size=(BOOTSTRAP_REPS, len(arrays)))
        means = np.asarray([np.mean(values) for values in arrays])
        estimates = np.mean(means[sampled], axis=1)
    else:
        grouped: dict[tuple[str, str], list[float]] = defaultdict(list)
        for row, value in zip(rows, delta):
            grouped[(row["task"], row["parent"])].append(float(value))
        keys = sorted(grouped)
        arrays = [np.asarray(grouped[key]) for key in keys]
        point = float(np.mean(delta))
        rng = np.random.default_rng(PARENT_SEED)
        estimates = np.empty(BOOTSTRAP_REPS)
        for index in range(BOOTSTRAP_REPS):
            sampled = rng.integers(0, len(arrays), size=len(arrays))
            estimates[index] = sum(float(np.sum(arrays[item])) for item in sampled) / sum(
                len(arrays[item]) for item in sampled
            )
    low, high = np.quantile(estimates, [0.025, 0.975], method="linear")
    return {
        "point": point, "ci95": [float(low), float(high)], "clusters": len(keys),
        "replicates": BOOTSTRAP_REPS,
        "seed": TASK_SEED if cluster == "task" else PARENT_SEED,
    }


def read_tfidf(path: Path, pools: dict[str, list[dict[str, Any]]]) -> dict[tuple[str, tuple[str, str, str, str]], bool]:
    require(sha256_file(path) == TFIDF_PAIR_SHA256, "TF-IDF pair receipt SHA mismatch")
    output = {}
    expected = {
        (split, pair_key(row)): (row["better"], row["worse"])
        for split in ("dev", "test") for row in pools[split]
    }
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            key = (row["split"], (row["task"], row["parent"], *sorted((row["better"], row["worse"]))))
            require(key in expected and expected[key] == (row["better"], row["worse"]), "TF-IDF row mismatch")
            require(isinstance(row.get("correct"), bool) and not row.get("tie"), "invalid TF-IDF decision")
            require(key not in output, "duplicate TF-IDF decision")
            output[key] = row["correct"]
    require(set(output) == set(expected), "TF-IDF decision coverage mismatch")
    return output


def select_champion(dev_scores: dict[str, float]) -> str:
    require(set(dev_scores) == set(MODEL_ORDER), "dev score inventory mismatch")
    require(all(np.isfinite(value) for value in dev_scores.values()), "dev score is non-finite")
    best_score = max(dev_scores.values())
    return next(name for name in MODEL_ORDER if abs(dev_scores[name] - best_score) <= 1e-12)


def analyze(
    cards_path: Path,
    train_path: Path,
    dev_path: Path,
    test_path: Path,
    draft_path: Path,
    improve_path: Path,
    tfidf_path: Path,
) -> tuple[
    dict[str, Any],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    paths = {
        "cards": cards_path, "train": train_path, "dev": dev_path, "test": test_path,
        "draft": draft_path, "improve": improve_path,
    }
    for role, path in paths.items():
        verify_input_identity(path, role)
    pools = {
        "train": read_rows(train_path, "train"),
        "dev": read_rows(dev_path, "dev"),
        "test": read_rows(test_path, "test"),
    }
    semantics = semantics_map(read_rows(draft_path), read_rows(improve_path))
    needed = {endpoint for rows in pools.values() for row in rows for endpoint in pair_key(row)[2:]}
    features, runs, configs, tasks, card_inventory = load_cards(cards_path, needed)
    integrity = validate_splits(pools, runs, configs, semantics)
    tfidf = read_tfidf(tfidf_path, pools)
    train_values = differences(pools["train"], features)
    train_tasks = sorted({row["task"] for row in pools["train"]})
    task_index = {task: index for index, task in enumerate(train_tasks)}

    predictors: dict[str, Callable[[np.ndarray, list[dict[str, Any]]], np.ndarray]] = {}
    receipts: dict[str, Any] = {}

    pooled_scaler, pooled_lr, receipt = lr_fit(train_values)
    predictors["static_lr_pooled"] = lambda values, rows: lr_margin(values, pooled_scaler, pooled_lr)
    receipts["static_lr_pooled"] = receipt

    pooled_gbm, receipt = gbm_fit(train_values)
    predictors["static_gbm_pooled"] = lambda values, rows: gbm_margin(values, -values, pooled_gbm)
    receipts["static_gbm_pooled"] = receipt

    train_task_values, known = task_interactions(train_values, pools["train"], task_index)
    require(known.all(), "train task interaction is unknown")
    task_scaler, task_lr, receipt = lr_fit(train_task_values)
    def predict_task_lr(values: np.ndarray, rows: list[dict[str, Any]]) -> np.ndarray:
        expanded, is_known = task_interactions(values, rows, task_index)
        margin = lr_margin(expanded, task_scaler, task_lr)
        margin[~is_known] = np.nan
        return margin
    predictors["static_lr_task"] = predict_task_lr
    receipts["static_lr_task"] = {**receipt, "train_tasks": train_tasks, "dimensions": train_task_values.shape[1]}

    train_conditioned, known = task_conditioned(train_values, pools["train"], task_index)
    require(known.all(), "train task conditioning is unknown")
    fit_x = np.vstack((train_conditioned, np.column_stack((-train_values, train_conditioned[:, len(FEATURE_NAMES):]))))
    fit_y = np.concatenate((np.ones(len(train_values), dtype=np.int8), np.zeros(len(train_values), dtype=np.int8)))
    task_gbm = HistGradientBoostingClassifier(
        loss="log_loss", max_iter=300, learning_rate=0.08, max_leaf_nodes=31,
        max_depth=None, min_samples_leaf=20, l2_regularization=0.0,
        early_stopping=False, random_state=7,
    ).fit(fit_x, fit_y)
    require(task_gbm.n_iter_ == 300, "task GBM iteration mismatch")
    def predict_task_gbm(values: np.ndarray, rows: list[dict[str, Any]]) -> np.ndarray:
        forward, is_known = task_conditioned(values, rows, task_index)
        reverse = forward.copy()
        reverse[:, : len(FEATURE_NAMES)] *= -1
        margin = 0.5 * (task_gbm.decision_function(forward) - task_gbm.decision_function(reverse))
        margin[~is_known] = np.nan
        return margin
    predictors["static_gbm_task"] = predict_task_gbm
    receipts["static_gbm_task"] = {
        "n_iter": int(task_gbm.n_iter_), "train_tasks": train_tasks,
        "dimensions": train_conditioned.shape[1],
        "train_margin_sha256": array_sha(predict_task_gbm(train_values, pools["train"])),
        "parameters": receipts["static_gbm_pooled"]["parameters"],
    }

    margins: dict[str, dict[str, np.ndarray]] = {name: {} for name in LEARNED_MODELS}
    anti_symmetry = {}
    unknown_task_counts: dict[str, dict[str, int]] = {name: {} for name in LEARNED_MODELS}
    for name, predictor in predictors.items():
        maximum = 0.0
        for split in ("dev", "test"):
            values = differences(pools[split], features)
            forward = predictor(values, pools[split])
            reverse = predictor(-values, pools[split])
            require(forward.shape == (len(pools[split]),), "learned margin shape mismatch")
            require(reverse.shape == forward.shape, "reverse learned margin shape mismatch")
            require(
                np.array_equal(np.isnan(forward), np.isnan(reverse)),
                "forward/reverse abstention masks differ",
            )
            finite = np.isfinite(forward) & np.isfinite(reverse)
            require(np.any(finite), "learned arm has no finite predictions")
            require(
                not np.any(np.isinf(forward)) and not np.any(np.isinf(reverse)),
                "learned arm produced infinite margin",
            )
            maximum = max(maximum, float(np.max(np.abs(forward[finite] + reverse[finite]))))
            unknown_task_counts[name][split] = int(np.sum(~finite))
            margins[name][split] = forward
        require(maximum <= 1e-12, "learned prediction is not antisymmetric")
        anti_symmetry[name] = maximum
        receipts[name]["anti_symmetry_max_abs"] = maximum

    controls: dict[str, dict[str, np.ndarray]] = {"random_hash": {}}
    for feature in SINGLE_FEATURES:
        controls[feature] = {}
    feature_positions = {name: index for index, name in enumerate(FEATURE_NAMES)}
    for split in ("dev", "test"):
        rows = pools[split]
        values = differences(rows, features)
        random_margin = []
        for row in rows:
            left, right = sorted((row["better"], row["worse"]))
            selected = (left, right)[zlib.crc32((left + "|" + right).encode()) & 1]
            random_margin.append(1.0 if selected == row["better"] else -1.0)
        controls["random_hash"][split] = np.asarray(random_margin)
        for feature in SINGLE_FEATURES:
            controls[feature][split] = values[:, feature_positions[feature]].copy()

    all_margins = {**controls, **margins}
    all_metrics: dict[str, Any] = {}
    all_pair_rows = []
    all_task_rows = []
    all_parent_rows = []
    for model_name in ("random_hash", *SINGLE_FEATURES, *LEARNED_MODELS):
        all_metrics[model_name] = {}
        for split in ("dev", "test"):
            rows = pools[split]
            semantic_values = [semantics[pair_key(row)] for row in rows]
            model_result, task_rows, parent_rows = model_metrics(
                rows, all_margins[model_name][split], semantic_values
            )
            all_metrics[model_name][split] = model_result
            all_task_rows.extend({"model": model_name, "split": split, **row} for row in task_rows)
            all_parent_rows.extend({"model": model_name, "split": split, **row} for row in parent_rows)
            for index, (row, semantic, margin) in enumerate(zip(rows, semantic_values, all_margins[model_name][split])):
                finite = bool(np.isfinite(margin))
                all_pair_rows.append({
                    "model": model_name, "split": split, "index": index,
                    "task": row["task"], "parent": row["parent"],
                    "better": row["better"], "worse": row["worse"],
                    "better_run": runs[row["better"]], "worse_run": runs[row["worse"]],
                    "semantics": semantic,
                    "margin": None if not finite else float(margin),
                    "correct": None if not finite or margin == 0 else bool(margin > 0),
                    "tie": bool(finite and margin == 0), "abstain": not finite,
                })

    dev_scores = {name: all_metrics[name]["dev"]["merged"]["task_macro_accuracy"] for name in LEARNED_MODELS}
    champion = select_champion(dev_scores)
    test_rows = pools["test"]
    champion_margin = margins[champion]["test"]
    champion_evaluable = np.isfinite(champion_margin) & (champion_margin != 0)
    require(np.any(champion_evaluable), "champion has no evaluable test predictions")
    champion_correct = np.where(champion_evaluable, (champion_margin > 0).astype(float), np.nan)
    tfidf_correct = np.asarray([float(tfidf[("test", pair_key(row))]) for row in test_rows])
    delta = champion_correct - tfidf_correct
    paired_eligible = bool(np.isfinite(delta).all())
    paired = {
        "eligible_exact_931_pairs": paired_eligible,
        "pairs": int(np.sum(np.isfinite(delta))),
        "task_clustered": paired_delta_ci(test_rows, delta, "task") if paired_eligible else None,
        "parent_clustered": paired_delta_ci(test_rows, delta, "parent") if paired_eligible else None,
        "semantic_point_delta": {},
        "leave_one_task_out": {},
    }
    test_semantics = [semantics[pair_key(row)] for row in test_rows]
    for semantic in ("Draft", "Improve"):
        mask = np.asarray([value == semantic for value in test_semantics])
        values = delta[mask]
        paired["semantic_point_delta"][semantic] = (
            float(np.mean(values)) if paired_eligible else None
        )
    for task in sorted({row["task"] for row in test_rows}):
        mask = np.asarray([row["task"] != task for row in test_rows])
        values = delta[mask]
        paired["leave_one_task_out"][task] = (
            float(np.mean(values)) if paired_eligible else None
        )

    champion_test = all_metrics[champion]["test"]["merged"]
    orientation_forward = np.ones(len(test_rows), dtype=np.float64)
    orientation_reverse = -orientation_forward
    orientation_oracle = {
        "pairs": len(test_rows),
        "accuracy": float(np.mean(orientation_forward > 0)),
        "anti_symmetry_max_abs": float(np.max(np.abs(orientation_forward + orientation_reverse))),
    }
    gates = {
        "champion_task_ci_above_half": champion_test["task_clustered"]["ci95"][0] > 0.5,
        "champion_parent_ci_above_half": champion_test["parent_clustered"]["ci95"][0] > 0.5,
        "paired_task_ci_above_zero": paired_eligible and paired["task_clustered"]["ci95"][0] > 0,
        "paired_parent_ci_above_zero": paired_eligible and paired["parent_clustered"]["ci95"][0] > 0,
        "semantic_deltas_at_least_minus_0.01": paired_eligible and min(paired["semantic_point_delta"].values()) >= -0.01,
        "loto_deltas_nonnegative": paired_eligible and min(paired["leave_one_task_out"].values()) >= 0,
        "champion_full_coverage_no_ties": champion_test["coverage"] == 1.0 and champion_test["ties"] == 0,
        "all_learned_predictions_finite": all(
            count == 0 for counts in unknown_task_counts.values() for count in counts.values()
        ),
        "all_antisymmetric": max(anti_symmetry.values()) <= 1e-12,
        "orientation_oracle_exact": orientation_oracle["accuracy"] == 1.0 and orientation_oracle["anti_symmetry_max_abs"] == 0.0,
    }
    producer_effect_gates_pass = all(gates.values())
    feature_matrix = np.vstack([features[card_id] for card_id in sorted(features)])
    summary = {
        "protocol": PROTOCOL,
        "status": (
            "STATIC_FEATURE_ADVANTAGE_CANDIDATE_PENDING_INDEPENDENT_VERIFICATION"
            if producer_effect_gates_pass
            else "STATIC_BASELINE_VALID_NO_STRONG_ADVANTAGE"
        ),
        "evidence_level": "retrospective_same_pool_baseline",
        "inputs": {
            role: {"sha256": EXPECTED[role][0], "bytes": EXPECTED[role][1]}
            for role in ("cards", "train", "dev", "test", "draft", "improve")
        } | {"tfidf_per_pair": {"sha256": TFIDF_PAIR_SHA256, "bytes": tfidf_path.stat().st_size}},
        "card_inventory": card_inventory,
        "integrity": integrity,
        "features": {
            "names": list(FEATURE_NAMES), "count": len(FEATURE_NAMES),
            "endpoint_order_sha256": hashlib.sha256(compact(sorted(features)).encode()).hexdigest(),
            "matrix_sha256": array_sha(feature_matrix),
            "forbidden_post_execution_fields_used": False,
        },
        "models": receipts,
        "unknown_task_abstentions": unknown_task_counts,
        "orientation_oracle": orientation_oracle,
        "selection": {
            "metric": "dev_task_macro_accuracy", "scores": dev_scores,
            "tie_tolerance": 1e-12, "tie_order": list(MODEL_ORDER), "champion": champion,
        },
        "metrics": all_metrics,
        "champion_tfidf_paired_delta": paired,
        "gates": gates,
        "producer_effect_gates_pass": producer_effect_gates_pass,
        "pending_independent_verification": True,
        "strong_positive_claim_allowed": False,
        "bootstrap": {"replicates": BOOTSTRAP_REPS, "task_seed": TASK_SEED, "parent_seed": PARENT_SEED},
    }
    return summary, all_pair_rows, all_task_rows, all_parent_rows


def write_outputs(
    output: Path,
    summary: dict[str, Any],
    pairs: list[dict[str, Any]],
    tasks: list[dict[str, Any]],
    parents: list[dict[str, Any]],
) -> None:
    require(not output.exists(), "output directory already exists")
    json.dumps(summary, allow_nan=False)
    for row in (*pairs, *tasks, *parents):
        json.dumps(row, allow_nan=False)
    output.mkdir(parents=True)
    (output / "summary.json").write_bytes(canonical(summary))
    with (output / "per_pair.jsonl").open("x", encoding="utf-8", newline="\n") as handle:
        for row in pairs:
            handle.write(compact(row) + "\n")
    fields = ("model", "split", "subset", "task", "pairs", "evaluable_pairs", "accuracy")
    with (output / "per_task.csv").open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(tasks)
    fields = ("model", "split", "subset", "task", "parent", "pairs", "evaluable_pairs", "accuracy")
    with (output / "per_parent.csv").open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(parents)
    manifest = {
        name: sha256_file(output / name)
        for name in ("summary.json", "per_pair.jsonl", "per_task.csv", "per_parent.csv")
    }
    (output / "artifact_manifest.json").write_bytes(canonical(manifest))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("cards", "train", "dev", "test", "draft", "improve", "tfidf_per_pair", "output"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    summary, pairs, tasks, parents = analyze(
        args.cards, args.train, args.dev, args.test, args.draft, args.improve,
        args.tfidf_per_pair,
    )
    write_outputs(args.output, summary, pairs, tasks, parents)
    print(json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    main()
