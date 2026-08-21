"""Independent full-refit verifier for the fixed component static suite."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import zlib
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler


REPS = 20_000
TASK_SEED = 20260821
PARENT_SEED = 20260822
TFIDF_SHA256 = "021f8b3c74db89c6b770714edb879731799b145744af7b765005eed72f9ecde6"
EXPECTED = {
    "cards": ("5fd24c8e545a67e1048f8a67b23bcb64605b9ad584a4fbaa44aa1b1f1b6e1afb", 604190866),
    "train": ("0ec49d76a896accf8e85a2556ca7ed12b9379b1867247d99c6be5e4c83bea98e", 3208089),
    "dev": ("3b3fb53f84277e935c66d3b3d1646d7a7d33624fb916e3f9bcc15f689904cfa4", 376635),
    "test": ("cb84d78d578e6a3f5378b3396a355fa83880739b4f9af8459d2b960c7ae005da", 381803),
    "draft": ("3ca77a18e224cacbb7f52121d6e8c2b66f17298c68dd06fbc42a14a238ad05b9", 1465008),
    "improve": ("7aca481afda5317fe78a0ad52fc7488fceff7fde6531c74ebb718df9e3b6926e", 1087821),
}
LEARNED = ("static_lr_pooled", "static_gbm_pooled", "static_lr_task", "static_gbm_task")
ORDER = LEARNED
SINGLES = ("code_len", "n_lines", "depth", "step", "n_cv", "n_ensemble")
SUBSETS = ("merged", "Draft", "Improve")
IMPORT_PATTERN = re.compile(r"^\s*(?:from|import)\s+([\w.]+)", re.MULTILINE)
MODEL_TOKENS = (
    "lightgbm", "xgboost", "catboost", "randomforest", "logisticregression",
    "ridge", "svc", "torch", "transformers", "bert", "resnet", "efficientnet",
    "timm", "keras", "sklearn",
)
CV_TOKENS = ("kfold", "stratifiedkfold", "groupkfold", "cross_val", "train_test_split")
RISK_TOKENS = (
    "fit_transform(test", "fit(test", ".append(test", "concat([train, test",
    "pd.concat([train,test",
)


class VerificationError(RuntimeError):
    """Raised on any independent-refit disagreement."""


def demand(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def compact(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def array_hash(value: np.ndarray) -> str:
    return hashlib.sha256(np.asarray(value, dtype="<f8").tobytes()).hexdigest()


def identify(path: Path, role: str) -> None:
    expected_hash, expected_size = EXPECTED[role]
    demand(path.stat().st_size == expected_size and file_hash(path) == expected_hash, f"{role} identity mismatch")


def read_jsonl(path: Path, split: str | None = None) -> list[dict[str, Any]]:
    records = []
    identities = set()
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            demand(bool(line.strip()), f"blank row {line_number}")
            record = json.loads(line)
            demand(isinstance(record, dict), "JSONL row is not an object")
            identity = pair_identity(record)
            demand(identity not in identities, "duplicate unordered pair")
            identities.add(identity)
            if split is not None:
                demand(record.get("intask_split") == split, "split row mismatch")
            records.append(record)
    return records


def read_artifact_jsonl(path: Path) -> list[dict[str, Any]]:
    records = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            demand(bool(line.strip()), f"blank artifact row {line_number}")
            record = json.loads(line)
            demand(isinstance(record, dict), "artifact row is not an object")
            records.append(record)
    return records


def pair_identity(record: dict[str, Any]) -> tuple[str, str, str, str]:
    try:
        left, right = sorted((record["better"], record["worse"]))
        output = record["task"], record["parent"], left, right
    except (KeyError, TypeError, ValueError) as error:
        raise VerificationError("bad pair identity") from error
    demand(all(isinstance(value, str) and value for value in output) and left != right, "bad pair identity")
    return output


def extract_features(card: dict[str, Any]) -> dict[str, float]:
    source = card.get("code")
    lineage = card.get("lineage")
    demand(isinstance(source, str) and isinstance(lineage, dict), "needed card lacks code/lineage")
    lower = source.lower()
    imports = set(IMPORT_PATTERN.findall(source))
    values = {
        "code_len": float(len(source)),
        "n_lines": float(source.count("\n")),
        "n_imports": float(len(imports)),
        "depth": float(lineage.get("depth") or 0),
        "step": float(lineage.get("step") or 0),
        "n_sibs": float(lineage.get("n_siblings") or 0),
        "n_cv": float(sum(lower.count(token) for token in CV_TOKENS)),
        "n_seed": float(lower.count("seed") + lower.count("random_state")),
        "n_ensemble": float(lower.count("ensemble") + lower.count("blend") + lower.count("stack") + lower.count("mean(")),
        "n_earlystop": float(lower.count("early_stop")),
        "n_hpsearch": float(lower.count("optuna") + lower.count("gridsearch") + lower.count("param_grid") + lower.count("hyperopt")),
        "n_augment": float(lower.count("augment") + lower.count("transform")),
        "n_try": float(lower.count("try:")),
        "n_print": float(lower.count("print(")),
        "n_comment": float(source.count("#")),
        "n_fold_int": float(max([int(item) for item in re.findall(r"n_splits\s*=\s*(\d+)", source)] or [0])),
        "n_epoch_int": float(max([int(item) for item in re.findall(r"epochs?\s*=\s*(\d+)", source)] or [0])),
        "risk_leak": float(sum(lower.count(token) for token in RISK_TOKENS)),
        "has_gpu": float("cuda" in lower),
    }
    for token in MODEL_TOKENS:
        values[f"m_{token}"] = float(token in lower)
    demand(len(values) == 34, "feature count mismatch")
    return values


FEATURES = tuple(sorted(extract_features({"code": "", "lineage": {}})))


def load_cards(path: Path, endpoints: set[str]):
    grouped = json.loads(path.read_text(encoding="utf-8"))
    demand(isinstance(grouped, dict), "cards root invalid")
    vectors: dict[str, np.ndarray] = {}
    runs: dict[str, str] = {}
    configs: dict[str, tuple[Any, ...]] = {}
    seen = set()
    total = 0
    for run_id, cards in grouped.items():
        demand(isinstance(run_id, str) and isinstance(cards, list), "cards group invalid")
        for card in cards:
            total += 1
            demand(isinstance(card, dict) and isinstance(card.get("id"), str) and card["id"] not in seen, "card identity invalid")
            card_id = card["id"]
            seen.add(card_id)
            if card_id not in endpoints:
                continue
            task_object = card.get("task")
            task = task_object.get("name") if isinstance(task_object, dict) else None
            config = task, card.get("client"), card.get("hardware"), card.get("time_limit"), card.get("execution_timeout")
            demand(all(isinstance(value, str) and value for value in config[:3]) and all(isinstance(value, int) for value in config[3:]), "needed provenance invalid")
            feature_map = extract_features(card)
            vector = np.asarray([feature_map[name] for name in FEATURES], dtype=np.float64)
            demand(np.isfinite(vector).all(), "non-finite feature")
            vectors[card_id], runs[card_id], configs[card_id] = vector, run_id, config
    demand(set(vectors) == endpoints, "needed endpoint missing")
    return vectors, runs, configs, {"cards": total, "run_groups": len(grouped), "needed_cards": len(endpoints)}


def check_integrity(
    pools: dict[str, list[dict[str, Any]]],
    runs: dict[str, str],
    configs: dict[str, tuple[Any, ...]],
    semantic_map: dict[tuple[str, str, str, str], str],
) -> dict[str, Any]:
    key_sets = {name: {pair_identity(row) for row in rows} for name, rows in pools.items()}
    endpoint_sets = {
        name: {endpoint for key in keys for endpoint in key[2:]}
        for name, keys in key_sets.items()
    }
    run_sets = {name: {runs[endpoint] for endpoint in values} for name, values in endpoint_sets.items()}
    overlap = {}
    for left, right in (("train", "dev"), ("train", "test"), ("dev", "test")):
        overlap[f"{left}_{right}_pairs"] = len(key_sets[left] & key_sets[right])
        overlap[f"{left}_{right}_endpoints"] = len(endpoint_sets[left] & endpoint_sets[right])
        overlap[f"{left}_{right}_runs"] = len(run_sets[left] & run_sets[right])
    demand(not any(overlap.values()), "split overlap")
    component_owner: dict[str, str] = {}
    for split in ("train", "dev"):
        for row in pools[split]:
            component = row.get("pair_component_id")
            demand(
                row.get("outer_intask_split") == "train"
                and row.get("train_dev_protocol") == "pair-graph-component-train-dev-split-v1"
                and row.get("train_dev_seed") == 20260821
                and row.get("train_dev_target_numerator") == 1
                and row.get("train_dev_target_denominator") == 10
                and isinstance(component, str)
                and re.fullmatch(r"[0-9a-f]{64}", component) is not None,
                "component receipt mismatch",
            )
            demand(component not in component_owner or component_owner[component] == split, "component crosses split")
            component_owner[component] = split
    for rows in pools.values():
        for row in rows:
            identity = pair_identity(row)
            demand(identity in semantic_map, "semantic identity missing")
            demand(configs[row["better"]] == configs[row["worse"]], "pair config differs")
            demand(configs[row["better"]][0] == row["task"], "pair task differs")
    return {
        "overlap": overlap,
        "pairs": {name: len(rows) for name, rows in pools.items()},
        "endpoints": {name: len(values) for name, values in endpoint_sets.items()},
        "runs": {name: len(values) for name, values in run_sets.items()},
        "components": len(component_owner),
    }


def feature_differences(rows: list[dict[str, Any]], vectors: dict[str, np.ndarray]) -> np.ndarray:
    return np.vstack([vectors[row["better"]] - vectors[row["worse"]] for row in rows])


def expand_task_interactions(values: np.ndarray, rows: list[dict[str, Any]], task_map: dict[str, int]):
    width = values.shape[1]
    expanded = np.zeros((len(rows), width * (len(task_map) + 1)), dtype=np.float64)
    expanded[:, :width] = values
    known = np.ones(len(rows), dtype=bool)
    for index, row in enumerate(rows):
        location = task_map.get(row["task"])
        if location is None:
            known[index] = False
        else:
            start = width * (location + 1)
            expanded[index, start : start + width] = values[index]
    return expanded, known


def append_task_onehot(values: np.ndarray, rows: list[dict[str, Any]], task_map: dict[str, int]):
    expanded = np.zeros((len(rows), values.shape[1] + len(task_map)), dtype=np.float64)
    expanded[:, : values.shape[1]] = values
    known = np.ones(len(rows), dtype=bool)
    for index, row in enumerate(rows):
        location = task_map.get(row["task"])
        if location is None:
            known[index] = False
        else:
            expanded[index, values.shape[1] + location] = 1.0
    return expanded, known


def fit_lr(values: np.ndarray):
    training = np.vstack((values, -values))
    labels = np.concatenate((np.ones(len(values), dtype=np.int8), np.zeros(len(values), dtype=np.int8)))
    scaler = StandardScaler(with_mean=False).fit(training)
    model = LogisticRegression(C=1.0, max_iter=4000, solver="lbfgs", fit_intercept=False).fit(
        scaler.transform(training), labels
    )
    demand(int(model.n_iter_[0]) < 4000 and np.isfinite(model.coef_).all(), "LR refit failure")
    receipt = {
        "scaler_scale_sha256": array_hash(scaler.scale_),
        "coefficient_sha256": array_hash(model.coef_),
        "n_iter": int(model.n_iter_[0]),
        "fit_intercept": False,
    }
    return scaler, model, receipt


def lr_scores(values: np.ndarray, scaler: StandardScaler, model: LogisticRegression) -> np.ndarray:
    return np.asarray(scaler.transform(values).dot(model.coef_.reshape(-1)), dtype=np.float64)


def new_gbm() -> HistGradientBoostingClassifier:
    return HistGradientBoostingClassifier(
        loss="log_loss", max_iter=300, learning_rate=0.08, max_leaf_nodes=31,
        max_depth=None, min_samples_leaf=20, l2_regularization=0.0,
        early_stopping=False, random_state=7,
    )


def gbm_parameters() -> dict[str, Any]:
    return {
        "loss": "log_loss", "max_iter": 300, "learning_rate": 0.08,
        "max_leaf_nodes": 31, "max_depth": None, "min_samples_leaf": 20,
        "l2_regularization": 0.0, "early_stopping": False, "random_state": 7,
    }


def distribution(values: np.ndarray) -> dict[str, float | None]:
    if not len(values):
        return {name: None for name in ("q00", "q10", "q25", "q50", "q75", "q90", "q100")}
    points = np.quantile(values, [0, .1, .25, .5, .75, .9, 1], method="linear")
    return {
        name: float(value)
        for name, value in zip(("q00", "q10", "q25", "q50", "q75", "q90", "q100"), points)
    }


def task_interval(rows: list[dict[str, Any]], values: np.ndarray) -> dict[str, Any] | None:
    tasks = sorted({row["task"] for row, value in zip(rows, values) if np.isfinite(value)})
    if not tasks:
        return None
    means = np.asarray([
        np.mean([value for row, value in zip(rows, values) if row["task"] == task and np.isfinite(value)])
        for task in tasks
    ])
    rng = np.random.default_rng(TASK_SEED)
    draws = rng.integers(0, len(means), size=(REPS, len(means)))
    estimates = np.mean(means[draws], axis=1)
    interval = np.quantile(estimates, [.025, .975], method="linear")
    return {
        "point": float(np.mean(means)), "ci95": [float(interval[0]), float(interval[1])],
        "clusters": len(means), "replicates": REPS, "seed": TASK_SEED,
    }


def parent_interval(rows: list[dict[str, Any]], values: np.ndarray) -> dict[str, Any] | None:
    grouped: dict[tuple[str, str], list[float]] = defaultdict(list)
    for row, value in zip(rows, values):
        if np.isfinite(value):
            grouped[(row["task"], row["parent"])].append(float(value))
    if not grouped:
        return None
    arrays = [np.asarray(grouped[key], dtype=np.float64) for key in sorted(grouped)]
    rng = np.random.default_rng(PARENT_SEED)
    estimates = np.empty(REPS, dtype=np.float64)
    for draw in range(REPS):
        sample = rng.integers(0, len(arrays), size=len(arrays))
        estimates[draw] = sum(float(np.sum(arrays[index])) for index in sample) / sum(
            len(arrays[index]) for index in sample
        )
    interval = np.quantile(estimates, [.025, .975], method="linear")
    return {
        "point": float(np.mean(np.concatenate(arrays))),
        "ci95": [float(interval[0]), float(interval[1])],
        "clusters": len(arrays), "replicates": REPS, "seed": PARENT_SEED,
    }


def pool_metrics(rows: list[dict[str, Any]], margins: np.ndarray, semantics: list[str]):
    metrics: dict[str, Any] = {}
    task_rows: list[dict[str, Any]] = []
    parent_rows: list[dict[str, Any]] = []
    for subset in SUBSETS:
        mask = np.asarray([subset == "merged" or value == subset for value in semantics], dtype=bool)
        chosen_rows = [row for row, keep in zip(rows, mask) if keep]
        chosen_margins = margins[mask]
        evaluable = np.isfinite(chosen_margins) & (chosen_margins != 0)
        correct = np.where(evaluable, (chosen_margins > 0).astype(float), np.nan)
        task_ci = task_interval(chosen_rows, correct)
        parent_ci = parent_interval(chosen_rows, correct)
        metrics[subset] = {
            "pairs": len(chosen_rows),
            "tasks": len({row["task"] for row in chosen_rows}),
            "parents": len({(row["task"], row["parent"]) for row in chosen_rows}),
            "evaluable_pairs": int(np.sum(evaluable)),
            "coverage": float(np.mean(evaluable)),
            "ties": int(np.sum(np.isfinite(chosen_margins) & (chosen_margins == 0))),
            "abstentions": int(np.sum(~np.isfinite(chosen_margins))),
            "micro_accuracy": None if not np.any(evaluable) else float(np.nanmean(correct)),
            "task_macro_accuracy": None if task_ci is None else task_ci["point"],
            "task_clustered": task_ci,
            "parent_clustered": parent_ci,
            "margin_quantiles": distribution(chosen_margins[evaluable]),
        }
        for task in sorted({row["task"] for row in chosen_rows}):
            task_mask = np.asarray([row["task"] == task for row in chosen_rows])
            values = correct[task_mask]
            task_rows.append({
                "subset": subset, "task": task, "pairs": int(np.sum(task_mask)),
                "evaluable_pairs": int(np.sum(np.isfinite(values))),
                "accuracy": None if not np.any(np.isfinite(values)) else float(np.nanmean(values)),
            })
        for task, parent in sorted({(row["task"], row["parent"]) for row in chosen_rows}):
            parent_mask = np.asarray([
                row["task"] == task and row["parent"] == parent for row in chosen_rows
            ])
            values = correct[parent_mask]
            parent_rows.append({
                "subset": subset, "task": task, "parent": parent,
                "pairs": int(np.sum(parent_mask)),
                "evaluable_pairs": int(np.sum(np.isfinite(values))),
                "accuracy": None if not np.any(np.isfinite(values)) else float(np.nanmean(values)),
            })
    return metrics, task_rows, parent_rows


def paired_interval(rows: list[dict[str, Any]], delta: np.ndarray, cluster: str) -> dict[str, Any]:
    if cluster == "task":
        keys = sorted({row["task"] for row in rows})
        arrays = [np.asarray([value for row, value in zip(rows, delta) if row["task"] == key]) for key in keys]
        means = np.asarray([np.mean(values) for values in arrays])
        point = float(np.mean(means))
        rng = np.random.default_rng(TASK_SEED)
        draws = rng.integers(0, len(arrays), size=(REPS, len(arrays)))
        estimates = np.mean(means[draws], axis=1)
        seed = TASK_SEED
    else:
        grouped: dict[tuple[str, str], list[float]] = defaultdict(list)
        for row, value in zip(rows, delta):
            grouped[(row["task"], row["parent"])].append(float(value))
        keys = sorted(grouped)
        arrays = [np.asarray(grouped[key]) for key in keys]
        point = float(np.mean(delta))
        rng = np.random.default_rng(PARENT_SEED)
        estimates = np.empty(REPS)
        for draw in range(REPS):
            sample = rng.integers(0, len(arrays), size=len(arrays))
            estimates[draw] = sum(float(np.sum(arrays[index])) for index in sample) / sum(
                len(arrays[index]) for index in sample
            )
        seed = PARENT_SEED
    interval = np.quantile(estimates, [.025, .975], method="linear")
    return {
        "point": point, "ci95": [float(interval[0]), float(interval[1])],
        "clusters": len(keys), "replicates": REPS, "seed": seed,
    }


def read_semantics(draft_path: Path, improve_path: Path) -> dict[tuple[str, str, str, str], str]:
    draft = {pair_identity(row) for row in read_jsonl(draft_path)}
    improve = {pair_identity(row) for row in read_jsonl(improve_path)}
    demand(not draft & improve, "semantic overlap")
    return {key: "Draft" for key in draft} | {key: "Improve" for key in improve}


def read_tfidf(path: Path, pools: dict[str, list[dict[str, Any]]]):
    demand(file_hash(path) == TFIDF_SHA256, "TF-IDF receipt identity mismatch")
    expected = {
        (split, pair_identity(row)): (row["better"], row["worse"])
        for split in ("dev", "test") for row in pools[split]
    }
    decisions = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            key = (row["split"], (row["task"], row["parent"], *sorted((row["better"], row["worse"]))))
            demand(key in expected and expected[key] == (row["better"], row["worse"]), "TF-IDF row mismatch")
            demand(isinstance(row.get("correct"), bool) and not row.get("tie"), "TF-IDF prediction invalid")
            demand(key not in decisions, "TF-IDF duplicate")
            decisions[key] = row["correct"]
    demand(set(decisions) == set(expected), "TF-IDF coverage mismatch")
    return decisions


def compare_values(expected: Any, observed: Any, path: str = "root") -> float:
    if isinstance(expected, dict):
        demand(isinstance(observed, dict) and set(expected) == set(observed), f"mapping mismatch at {path}")
        return max(
            (compare_values(value, observed[key], f"{path}.{key}") for key, value in expected.items()),
            default=0.0,
        )
    if isinstance(expected, list):
        demand(isinstance(observed, list) and len(expected) == len(observed), f"list mismatch at {path}")
        return max(
            (compare_values(left, right, f"{path}[{index}]") for index, (left, right) in enumerate(zip(expected, observed))),
            default=0.0,
        )
    if isinstance(expected, float):
        demand(isinstance(observed, (int, float)) and np.isfinite(observed), f"float mismatch at {path}")
        difference = abs(expected - float(observed))
        demand(difference <= 1e-12, f"numeric mismatch at {path}: {difference}")
        return difference
    demand(expected == observed, f"value mismatch at {path}")
    return 0.0


def recompute(
    cards_path: Path,
    train_path: Path,
    dev_path: Path,
    test_path: Path,
    draft_path: Path,
    improve_path: Path,
    tfidf_path: Path,
):
    paths = {
        "cards": cards_path, "train": train_path, "dev": dev_path, "test": test_path,
        "draft": draft_path, "improve": improve_path,
    }
    for role, path in paths.items():
        identify(path, role)
    pools = {
        "train": read_jsonl(train_path, "train"),
        "dev": read_jsonl(dev_path, "dev"),
        "test": read_jsonl(test_path, "test"),
    }
    semantic_map = read_semantics(draft_path, improve_path)
    endpoints = {
        endpoint for rows in pools.values() for row in rows for endpoint in pair_identity(row)[2:]
    }
    vectors, runs, configs, inventory = load_cards(cards_path, endpoints)
    integrity = check_integrity(pools, runs, configs, semantic_map)
    tfidf = read_tfidf(tfidf_path, pools)
    train_values = feature_differences(pools["train"], vectors)
    train_tasks = sorted({row["task"] for row in pools["train"]})
    task_map = {task: index for index, task in enumerate(train_tasks)}

    receipts: dict[str, Any] = {}
    predictors = {}

    pooled_scaler, pooled_lr, receipt = fit_lr(train_values)
    predictors["static_lr_pooled"] = lambda values, rows: lr_scores(values, pooled_scaler, pooled_lr)
    receipts["static_lr_pooled"] = receipt

    augmented_x = np.vstack((train_values, -train_values))
    augmented_y = np.concatenate((np.ones(len(train_values), dtype=np.int8), np.zeros(len(train_values), dtype=np.int8)))
    pooled_gbm = new_gbm().fit(augmented_x, augmented_y)
    demand(pooled_gbm.n_iter_ == 300, "pooled GBM refit failure")

    def predict_pooled_gbm(values: np.ndarray, rows: list[dict[str, Any]]) -> np.ndarray:
        return .5 * (pooled_gbm.decision_function(values) - pooled_gbm.decision_function(-values))

    receipts["static_gbm_pooled"] = {
        "n_iter": int(pooled_gbm.n_iter_),
        "train_margin_sha256": array_hash(predict_pooled_gbm(train_values, pools["train"])),
        "parameters": gbm_parameters(),
    }
    predictors["static_gbm_pooled"] = predict_pooled_gbm

    train_interactions, train_known = expand_task_interactions(train_values, pools["train"], task_map)
    demand(train_known.all(), "unknown training task for LR")
    task_scaler, task_lr, receipt = fit_lr(train_interactions)

    def predict_task_lr(values: np.ndarray, rows: list[dict[str, Any]]) -> np.ndarray:
        expanded, known = expand_task_interactions(values, rows, task_map)
        scores = lr_scores(expanded, task_scaler, task_lr)
        scores[~known] = np.nan
        return scores

    receipts["static_lr_task"] = {
        **receipt, "train_tasks": train_tasks, "dimensions": train_interactions.shape[1],
    }
    predictors["static_lr_task"] = predict_task_lr

    train_conditioned, train_known = append_task_onehot(train_values, pools["train"], task_map)
    demand(train_known.all(), "unknown training task for GBM")
    opposite_conditioned = train_conditioned.copy()
    opposite_conditioned[:, : len(FEATURES)] *= -1
    task_gbm_x = np.vstack((train_conditioned, opposite_conditioned))
    task_gbm_y = np.concatenate((np.ones(len(train_values), dtype=np.int8), np.zeros(len(train_values), dtype=np.int8)))
    task_gbm = new_gbm().fit(task_gbm_x, task_gbm_y)
    demand(task_gbm.n_iter_ == 300, "task GBM refit failure")

    def predict_task_gbm(values: np.ndarray, rows: list[dict[str, Any]]) -> np.ndarray:
        forward, known = append_task_onehot(values, rows, task_map)
        reverse = forward.copy()
        reverse[:, : len(FEATURES)] *= -1
        scores = .5 * (task_gbm.decision_function(forward) - task_gbm.decision_function(reverse))
        scores[~known] = np.nan
        return scores

    receipts["static_gbm_task"] = {
        "n_iter": int(task_gbm.n_iter_), "train_tasks": train_tasks,
        "dimensions": train_conditioned.shape[1],
        "train_margin_sha256": array_hash(predict_task_gbm(train_values, pools["train"])),
        "parameters": gbm_parameters(),
    }
    predictors["static_gbm_task"] = predict_task_gbm

    learned_margins: dict[str, dict[str, np.ndarray]] = {name: {} for name in LEARNED}
    anti_symmetry: dict[str, float] = {}
    unknown_counts: dict[str, dict[str, int]] = {name: {} for name in LEARNED}
    for name in LEARNED:
        maximum = 0.0
        for split in ("dev", "test"):
            values = feature_differences(pools[split], vectors)
            forward = predictors[name](values, pools[split])
            reverse = predictors[name](-values, pools[split])
            demand(forward.shape == (len(pools[split]),) and reverse.shape == forward.shape, "margin shape mismatch")
            demand(np.array_equal(np.isnan(forward), np.isnan(reverse)), "abstention mask mismatch")
            finite = np.isfinite(forward) & np.isfinite(reverse)
            demand(np.any(finite) and not np.any(np.isinf(forward)) and not np.any(np.isinf(reverse)), "invalid learned margins")
            maximum = max(maximum, float(np.max(np.abs(forward[finite] + reverse[finite]))))
            unknown_counts[name][split] = int(np.sum(~finite))
            learned_margins[name][split] = forward
        demand(maximum <= 1e-12, "antisymmetry failure")
        anti_symmetry[name] = maximum
        receipts[name]["anti_symmetry_max_abs"] = maximum

    controls: dict[str, dict[str, np.ndarray]] = {"random_hash": {}}
    controls.update({name: {} for name in SINGLES})
    positions = {name: index for index, name in enumerate(FEATURES)}
    for split in ("dev", "test"):
        rows = pools[split]
        values = feature_differences(rows, vectors)
        random_scores = []
        for row in rows:
            left, right = sorted((row["better"], row["worse"]))
            chosen = (left, right)[zlib.crc32(f"{left}|{right}".encode()) & 1]
            random_scores.append(1.0 if chosen == row["better"] else -1.0)
        controls["random_hash"][split] = np.asarray(random_scores)
        for name in SINGLES:
            controls[name][split] = values[:, positions[name]].copy()

    all_margins = {**controls, **learned_margins}
    metrics: dict[str, Any] = {}
    pair_rows: list[dict[str, Any]] = []
    task_rows: list[dict[str, Any]] = []
    parent_rows: list[dict[str, Any]] = []
    for model_name in ("random_hash", *SINGLES, *LEARNED):
        metrics[model_name] = {}
        for split in ("dev", "test"):
            rows = pools[split]
            semantic_values = [semantic_map[pair_identity(row)] for row in rows]
            split_metrics, split_task_rows, split_parent_rows = pool_metrics(
                rows, all_margins[model_name][split], semantic_values
            )
            metrics[model_name][split] = split_metrics
            task_rows.extend({"model": model_name, "split": split, **row} for row in split_task_rows)
            parent_rows.extend({"model": model_name, "split": split, **row} for row in split_parent_rows)
            for index, (row, semantic, margin) in enumerate(zip(rows, semantic_values, all_margins[model_name][split])):
                finite = bool(np.isfinite(margin))
                pair_rows.append({
                    "model": model_name, "split": split, "index": index,
                    "task": row["task"], "parent": row["parent"],
                    "better": row["better"], "worse": row["worse"],
                    "better_run": runs[row["better"]], "worse_run": runs[row["worse"]],
                    "semantics": semantic,
                    "margin": None if not finite else float(margin),
                    "correct": None if not finite or margin == 0 else bool(margin > 0),
                    "tie": bool(finite and margin == 0), "abstain": not finite,
                })

    dev_scores = {name: metrics[name]["dev"]["merged"]["task_macro_accuracy"] for name in LEARNED}
    best_score = max(dev_scores.values())
    champion = next(name for name in ORDER if abs(dev_scores[name] - best_score) <= 1e-12)
    test_rows = pools["test"]
    champion_margin = learned_margins[champion]["test"]
    evaluable = np.isfinite(champion_margin) & (champion_margin != 0)
    champion_correct = np.where(evaluable, (champion_margin > 0).astype(float), np.nan)
    tfidf_correct = np.asarray([float(tfidf[("test", pair_identity(row))]) for row in test_rows])
    delta = champion_correct - tfidf_correct
    paired_eligible = bool(np.isfinite(delta).all())
    paired = {
        "eligible_exact_931_pairs": paired_eligible,
        "pairs": int(np.sum(np.isfinite(delta))),
        "task_clustered": paired_interval(test_rows, delta, "task") if paired_eligible else None,
        "parent_clustered": paired_interval(test_rows, delta, "parent") if paired_eligible else None,
        "semantic_point_delta": {}, "leave_one_task_out": {},
    }
    test_semantics = [semantic_map[pair_identity(row)] for row in test_rows]
    for semantic in ("Draft", "Improve"):
        mask = np.asarray([value == semantic for value in test_semantics])
        paired["semantic_point_delta"][semantic] = float(np.mean(delta[mask])) if paired_eligible else None
    for task in sorted({row["task"] for row in test_rows}):
        mask = np.asarray([row["task"] != task for row in test_rows])
        paired["leave_one_task_out"][task] = float(np.mean(delta[mask])) if paired_eligible else None

    champion_test = metrics[champion]["test"]["merged"]
    orientation = {"pairs": len(test_rows), "accuracy": 1.0, "anti_symmetry_max_abs": 0.0}
    gates = {
        "champion_task_ci_above_half": champion_test["task_clustered"]["ci95"][0] > .5,
        "champion_parent_ci_above_half": champion_test["parent_clustered"]["ci95"][0] > .5,
        "paired_task_ci_above_zero": paired_eligible and paired["task_clustered"]["ci95"][0] > 0,
        "paired_parent_ci_above_zero": paired_eligible and paired["parent_clustered"]["ci95"][0] > 0,
        "semantic_deltas_at_least_minus_0.01": paired_eligible and min(paired["semantic_point_delta"].values()) >= -.01,
        "loto_deltas_nonnegative": paired_eligible and min(paired["leave_one_task_out"].values()) >= 0,
        "champion_full_coverage_no_ties": champion_test["coverage"] == 1.0 and champion_test["ties"] == 0,
        "all_learned_predictions_finite": all(count == 0 for counts in unknown_counts.values() for count in counts.values()),
        "all_antisymmetric": max(anti_symmetry.values()) <= 1e-12,
        "orientation_oracle_exact": True,
    }
    effect_pass = all(gates.values())
    feature_matrix = np.vstack([vectors[card_id] for card_id in sorted(vectors)])
    summary = {
        "protocol": "critic-component-static-suite-v1",
        "status": "STATIC_FEATURE_ADVANTAGE_CANDIDATE_PENDING_INDEPENDENT_VERIFICATION" if effect_pass else "STATIC_BASELINE_VALID_NO_STRONG_ADVANTAGE",
        "evidence_level": "retrospective_same_pool_baseline",
        "inputs": {
            role: {"sha256": EXPECTED[role][0], "bytes": EXPECTED[role][1]}
            for role in ("cards", "train", "dev", "test", "draft", "improve")
        } | {"tfidf_per_pair": {"sha256": TFIDF_SHA256, "bytes": tfidf_path.stat().st_size}},
        "card_inventory": inventory,
        "integrity": integrity,
        "features": {
            "names": list(FEATURES), "count": len(FEATURES),
            "endpoint_order_sha256": hashlib.sha256(compact(sorted(vectors)).encode()).hexdigest(),
            "matrix_sha256": array_hash(feature_matrix),
            "forbidden_post_execution_fields_used": False,
        },
        "models": receipts,
        "unknown_task_abstentions": unknown_counts,
        "orientation_oracle": orientation,
        "selection": {
            "metric": "dev_task_macro_accuracy", "scores": dev_scores,
            "tie_tolerance": 1e-12, "tie_order": list(ORDER), "champion": champion,
        },
        "metrics": metrics,
        "champion_tfidf_paired_delta": paired,
        "gates": gates,
        "producer_effect_gates_pass": effect_pass,
        "pending_independent_verification": True,
        "strong_positive_claim_allowed": False,
        "bootstrap": {"replicates": REPS, "task_seed": TASK_SEED, "parent_seed": PARENT_SEED},
    }
    return summary, pair_rows, task_rows, parent_rows


def compare_csv(path: Path, expected: list[dict[str, Any]], identity_fields: tuple[str, ...]) -> float:
    with path.open(encoding="utf-8", newline="") as handle:
        observed = list(csv.DictReader(handle))
    demand(len(observed) == len(expected), f"row count mismatch in {path.name}")
    maximum = 0.0
    for index, (left, right) in enumerate(zip(expected, observed)):
        for field in identity_fields:
            demand(right[field] == left[field], f"identity mismatch in {path.name}:{index}:{field}")
        for field in ("pairs", "evaluable_pairs"):
            demand(int(right[field]) == left[field], f"count mismatch in {path.name}:{index}:{field}")
        if left["accuracy"] is None:
            demand(right["accuracy"] == "", f"null accuracy mismatch in {path.name}:{index}")
        else:
            difference = abs(float(right["accuracy"]) - left["accuracy"])
            demand(difference <= 1e-12, f"accuracy mismatch in {path.name}:{index}")
            maximum = max(maximum, difference)
    return maximum


def verify(
    cards_path: Path,
    train_path: Path,
    dev_path: Path,
    test_path: Path,
    draft_path: Path,
    improve_path: Path,
    tfidf_path: Path,
    artifact_dir: Path,
) -> dict[str, Any]:
    expected_summary, expected_pairs, expected_tasks, expected_parents = recompute(
        cards_path, train_path, dev_path, test_path, draft_path, improve_path, tfidf_path
    )
    producer_summary = json.loads((artifact_dir / "summary.json").read_text(encoding="utf-8"))
    maximum_summary_difference = compare_values(expected_summary, producer_summary, "summary")

    observed_pairs = read_artifact_jsonl(artifact_dir / "per_pair.jsonl")
    demand(len(observed_pairs) == len(expected_pairs), "per-pair row count mismatch")
    maximum_margin_difference = 0.0
    for index, (expected, observed) in enumerate(zip(expected_pairs, observed_pairs)):
        difference = compare_values(expected, observed, f"per_pair[{index}]")
        maximum_margin_difference = max(maximum_margin_difference, difference)

    maximum_task_difference = compare_csv(
        artifact_dir / "per_task.csv", expected_tasks, ("model", "split", "subset", "task")
    )
    maximum_parent_difference = compare_csv(
        artifact_dir / "per_parent.csv", expected_parents,
        ("model", "split", "subset", "task", "parent"),
    )
    manifest = json.loads((artifact_dir / "artifact_manifest.json").read_text(encoding="utf-8"))
    expected_manifest = {
        name: file_hash(artifact_dir / name)
        for name in ("summary.json", "per_pair.jsonl", "per_task.csv", "per_parent.csv")
    }
    demand(manifest == expected_manifest, "artifact manifest mismatch")

    verification_gates = {
        "full_refit_summary_exact": maximum_summary_difference <= 1e-12,
        "all_pair_rows_exact": maximum_margin_difference <= 1e-12,
        "all_task_rows_exact": maximum_task_difference <= 1e-12,
        "all_parent_rows_exact": maximum_parent_difference <= 1e-12,
        "artifact_manifest_valid": True,
        "producer_not_imported": True,
    }
    verification_pass = all(verification_gates.values())
    strong = bool(expected_summary["producer_effect_gates_pass"] and verification_pass)
    return {
        "protocol": "independent-critic-component-static-suite-verifier-v1",
        "status": (
            "STATIC_FEATURE_ADVANTAGE_INDEPENDENTLY_VERIFIED"
            if strong else "STATIC_SUITE_INDEPENDENTLY_VERIFIED_NO_STRONG_ADVANTAGE"
        ),
        "full_refit": True,
        "producer_imported": False,
        "pairs": expected_summary["integrity"]["pairs"],
        "champion": expected_summary["selection"]["champion"],
        "producer_effect_gates_pass": expected_summary["producer_effect_gates_pass"],
        "verification_gates": verification_gates,
        "strong_positive_claim_allowed": strong,
        "max_abs_summary_difference": maximum_summary_difference,
        "max_abs_pair_difference": maximum_margin_difference,
        "max_abs_task_accuracy_difference": maximum_task_difference,
        "max_abs_parent_accuracy_difference": maximum_parent_difference,
        "producer_summary_sha256": file_hash(artifact_dir / "summary.json"),
        "producer_artifact_manifest_sha256": file_hash(artifact_dir / "artifact_manifest.json"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "cards", "train", "dev", "test", "draft", "improve", "tfidf_per_pair", "artifact_dir"
    ):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    receipt = verify(
        args.cards, args.train, args.dev, args.test, args.draft, args.improve,
        args.tfidf_per_pair, args.artifact_dir,
    )
    print(json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
