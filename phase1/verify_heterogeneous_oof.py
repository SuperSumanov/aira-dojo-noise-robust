#!/usr/bin/env python3
"""Independent refit verifier for heterogeneous_oof_v11_discovery_v1.

This module deliberately does not import the producer or its metric helpers.
It reopens train-only inputs, independently rebuilds all features and all five
outer-fold models, checks checkpoint/prediction scores, and recomputes metrics,
clustered intervals, complementarity, gates, and status.
"""

from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import math
import os
import random
import re
import warnings
from pathlib import Path
from typing import Any, Sequence

import numpy as np


SEED = 887
PROTOCOL = "heterogeneous_oof_v11_discovery_v1"
OUTER_FOLDS = 5
BOOTSTRAP_REPS = 10_000
EPSILON = 1e-12
EXPECTED = {"pairs": 4263, "runs": 333, "tasks": 23, "parents": 2293, "complete_parents": 2259, "endpoints": 5499}
BASELINE_ARM = "fixed_frozen_global"
PRIMARY_ARM = "char_tfidf_lr"
BASE_ARMS = ("op_only_lr", "static_lr", "static_gbm", PRIMARY_ARM)
EQUAL_ARM = "equal_rank_frozen_tfidf"
ARMS = (BASELINE_ARM, *BASE_ARMS, EQUAL_ARM)
METRIC_SEED_OFFSETS = {BASELINE_ARM: 10, "op_only_lr": 300, "static_lr": 320, "static_gbm": 340, PRIMARY_ARM: 360, EQUAL_ARM: 380}
OP_NAMES = ("draft", "debug", "improve", "other")
IMPORT_RX = re.compile(r"^\s*(?:from|import)\s+([\w.]+)", re.M)
MODEL_WORDS = ("lightgbm", "xgboost", "catboost", "randomforest", "logisticregression", "ridge", "svc", "torch", "transformers", "bert", "resnet", "efficientnet", "timm", "keras", "sklearn")
CV_WORDS = ("kfold", "stratifiedkfold", "groupkfold", "cross_val", "train_test_split")
RISK_WORDS = ("fit_transform(test", "fit(test", ".append(test", "concat([train, test", "pd.concat([train,test")


class VerificationError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def reject_forbidden_path(path: Path, label: str) -> None:
    found = [token for token in ("frozen", "test", "held") if token in path.name.lower()]
    if found:
        raise VerificationError(f"{label} path contains forbidden token(s): {found}")


def task_name(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("name") or value.get("desc") or "")
    return str(value or "")


def code_view(code: str) -> str:
    return code if len(code) <= 20_000 else code[:5_000] + "\n# <FIXED_HEAD_TAIL_TRUNCATION>\n" + code[-15_000:]


def normalized_op(value: Any) -> str:
    op = str(value or "").strip().lower()
    return op if op in OP_NAMES[:-1] else "other"


def static_feature_dict(card: dict[str, Any]) -> dict[str, float]:
    code = str(card["code"])
    low = code.lower()
    lineage = card["lineage"]
    imports = set(IMPORT_RX.findall(code))
    values = {
        "code_len": float(len(code)), "n_lines": float(code.count("\n")), "n_imports": float(len(imports)),
        "depth": float(lineage.get("depth") or 0), "step": float(lineage.get("step") or 0),
        "n_sibs": float(lineage.get("n_siblings") or 0),
        "n_cv": float(sum(low.count(word) for word in CV_WORDS)),
        "n_seed": float(low.count("seed") + low.count("random_state")),
        "n_ensemble": float(low.count("ensemble") + low.count("blend") + low.count("stack") + low.count("mean(")),
        "n_earlystop": float(low.count("early_stop")),
        "n_hpsearch": float(low.count("optuna") + low.count("gridsearch") + low.count("param_grid") + low.count("hyperopt")),
        "n_augment": float(low.count("augment") + low.count("transform")), "n_try": float(low.count("try:")),
        "n_print": float(code.count("print(")), "n_comment": float(code.count("#")),
        "n_fold_int": float(max([int(item) for item in re.findall(r"n_splits\s*=\s*(\d+)", code)] or [0])),
        "n_epoch_int": float(max([int(item) for item in re.findall(r"epochs?\s*=\s*(\d+)", code)] or [0])),
        "risk_leak": float(sum(low.count(word) for word in RISK_WORDS)), "has_gpu": float("cuda" in low),
    }
    for word in MODEL_WORDS:
        values[f"m_{word}"] = float(word in low)
    op = normalized_op(lineage.get("op"))
    for name in OP_NAMES:
        values[f"op_{name}"] = float(op == name)
    return values


def load_manifest(path: Path, summary_path: Path, expected_sha: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    reject_forbidden_path(path, "manifest")
    reject_forbidden_path(summary_path, "manifest summary")
    if sha256(path) != expected_sha.lower():
        raise VerificationError("manifest SHA mismatch")
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    ids = [str(row["card_id"]) for row in rows]
    if ids != sorted(ids) or len(ids) != len(set(ids)) or len(ids) != EXPECTED["endpoints"]:
        raise VerificationError("manifest inventory mismatch")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if summary.get("status") != "MANIFEST_COMPLETE" or summary.get("expected_split") != "train":
        raise VerificationError("manifest summary mismatch")
    if summary.get("outputs", {}).get("manifest_sha256") != sha256(path):
        raise VerificationError("manifest summary SHA mismatch")
    return rows, summary


def load_cards(path: Path, manifest: Sequence[dict[str, Any]], expected_sha: str) -> dict[str, dict[str, Any]]:
    reject_forbidden_path(path, "cards")
    expected = {str(row["card_id"]): row for row in manifest}
    found: dict[str, dict[str, Any]] = {}
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for raw_line in handle:
            digest.update(raw_line)
            row = json.loads(raw_line)
            card_id = str(row["id"])
            if card_id not in expected:
                continue
            if card_id in found:
                raise VerificationError(f"duplicate selected card: {card_id}")
            meta = expected[card_id]
            code = str(row.get("code") or "")
            if hashlib.sha256(code.encode()).hexdigest() != str(meta["code_sha256"]) or len(code) != int(meta["code_chars"]):
                raise VerificationError(f"code mismatch: {card_id}")
            if task_name(row.get("task")) != str(meta["task"]) or str(row.get("run_id")) != str(meta["run_id"]):
                raise VerificationError(f"context mismatch: {card_id}")
            lineage = dict(row.get("lineage") or {})
            found[card_id] = {"code": code, "lineage": {key: lineage.get(key) for key in ("depth", "step", "n_siblings", "op")}}
    if digest.hexdigest() != expected_sha.lower() or set(found) != set(expected):
        raise VerificationError("cards SHA/coverage mismatch")
    return found


def load_pairs(path: Path, run_map_path: Path, manifest: Sequence[dict[str, Any]], expected_sha: str, expected_run_sha: str) -> list[dict[str, Any]]:
    reject_forbidden_path(path, "training pairs")
    reject_forbidden_path(run_map_path, "run map")
    if sha256(path) != expected_sha.lower() or sha256(run_map_path) != expected_run_sha.lower():
        raise VerificationError("pair/run-map SHA mismatch")
    run_map = json.loads(run_map_path.read_text(encoding="utf-8"))
    metadata = {str(row["card_id"]): row for row in manifest}
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for index, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        if not line:
            continue
        raw = json.loads(line)
        if str(raw.get("intask_split")) != "train" or int(raw.get("budget", -1)) != 0:
            raise VerificationError(f"non-train pair: {index}")
        better, worse = str(raw["better"]), str(raw["worse"])
        canonical = tuple(sorted((better, worse)))
        if better == worse or canonical in seen:
            raise VerificationError(f"duplicate pair: {index}")
        seen.add(canonical)
        task, run = str(raw["task"]), str(raw["run_id"])
        for card_id in (better, worse):
            if card_id not in metadata or str(metadata[card_id]["task"]) != task or str(metadata[card_id]["run_id"]) != run or str(run_map.get(card_id)) != run:
                raise VerificationError(f"pair context mismatch: {index}")
        gap = float(raw["gap_raw"])
        if not math.isfinite(gap) or gap <= 0:
            raise VerificationError(f"invalid gap: {index}")
        rows.append({"row_index": index, "task": task, "run": run, "parent": str(raw["parent"]), "better": better, "worse": worse, "gap_raw": gap})
    endpoints = {str(row[key]) for row in rows for key in ("better", "worse")}
    if len(rows) != EXPECTED["pairs"] or endpoints != set(metadata):
        raise VerificationError("pair inventory mismatch")
    return rows


def load_baseline(path: Path, rows: Sequence[dict[str, Any]], expected_sha: str) -> tuple[list[int], dict[str, float]]:
    reject_forbidden_path(path, "baseline OOF")
    if sha256(path) != expected_sha.lower():
        raise VerificationError("baseline SHA mismatch")
    with path.open("r", encoding="utf-8", newline="") as handle:
        emitted = list(csv.DictReader(handle))
    if len(emitted) != len(rows):
        raise VerificationError("baseline row count mismatch")
    folds: list[int] = []
    scores: dict[str, float] = {}
    run_fold: dict[str, int] = {}
    for index, (row, output) in enumerate(zip(rows, emitted)):
        if int(output["row_index"]) != index or any(str(output[key]) != str(row[key]) for key in ("task", "run", "parent", "better", "worse")):
            raise VerificationError(f"baseline row mismatch: {index}")
        fold = int(output["fold"])
        if fold not in range(OUTER_FOLDS) or run_fold.setdefault(str(row["run"]), fold) != fold:
            raise VerificationError(f"baseline fold mismatch: {index}")
        folds.append(fold)
        for endpoint_key, score_key in (("better", "better_score"), ("worse", "worse_score")):
            card_id, score = str(row[endpoint_key]), float(output[score_key])
            if card_id in scores and not math.isclose(scores[card_id], score, abs_tol=1e-12):
                raise VerificationError(f"baseline score mismatch: {card_id}")
            scores[card_id] = score
    return folds, scores


def pair_differences(matrix: Any, position: dict[str, int], rows: Sequence[dict[str, Any]], indices: Sequence[int]) -> Any:
    better = np.asarray([position[str(rows[index]["better"])] for index in indices])
    worse = np.asarray([position[str(rows[index]["worse"])] for index in indices])
    return matrix[better] - matrix[worse]


def symmetric_design(differences: Any) -> tuple[Any, np.ndarray]:
    if hasattr(differences, "tocsr"):
        from scipy import sparse
        design = sparse.vstack([differences, -differences], format="csr")
    else:
        design = np.vstack([differences, -differences])
    return design, np.concatenate([np.ones(differences.shape[0], dtype=np.int8), np.zeros(differences.shape[0], dtype=np.int8)])


def fit_linear(matrix: np.ndarray, position: dict[str, int], rows: Sequence[dict[str, Any]], fit: Sequence[int], valid_ids: Sequence[str], columns: Sequence[int]) -> dict[str, float]:
    from sklearn.exceptions import ConvergenceWarning
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    subset = np.asarray(matrix[:, np.asarray(columns)], dtype=np.float64)
    design, labels = symmetric_design(pair_differences(subset, position, rows, fit))
    scaler = StandardScaler(with_mean=False).fit(design)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        model = LogisticRegression(C=1.0, fit_intercept=False, max_iter=2000, random_state=SEED, solver="liblinear", tol=1e-6).fit(scaler.transform(design), labels)
    if any(issubclass(item.category, ConvergenceWarning) for item in caught):
        raise VerificationError("linear convergence warning")
    values = model.decision_function(scaler.transform(subset[np.asarray([position[item] for item in valid_ids])]))
    return dict(zip(valid_ids, map(float, values)))


def aggregate(rows: Sequence[dict[str, Any]], valid: Sequence[int], logits: Sequence[float]) -> dict[str, float]:
    totals: dict[str, float] = collections.defaultdict(float)
    counts: dict[str, int] = collections.defaultdict(int)
    for index, logit in zip(valid, logits):
        better, worse = str(rows[index]["better"]), str(rows[index]["worse"])
        totals[better] += float(logit); totals[worse] -= float(logit)
        counts[better] += 1; counts[worse] += 1
    return {card_id: totals[card_id] / counts[card_id] for card_id in totals}


def fit_gbm(matrix: np.ndarray, position: dict[str, int], rows: Sequence[dict[str, Any]], fit: Sequence[int], valid: Sequence[int]) -> dict[str, float]:
    from sklearn.ensemble import HistGradientBoostingClassifier
    design, labels = symmetric_design(np.asarray(pair_differences(matrix, position, rows, fit), dtype=np.float64))
    model = HistGradientBoostingClassifier(early_stopping=False, learning_rate=0.08, max_iter=300, random_state=SEED).fit(design, labels)
    differences = np.asarray(pair_differences(matrix, position, rows, valid), dtype=np.float64)
    probability = np.clip(model.predict_proba(differences)[:, 1], 1e-6, 1 - 1e-6)
    return aggregate(rows, valid, np.log(probability / (1 - probability)))


def fit_tfidf(cards: dict[str, dict[str, Any]], rows: Sequence[dict[str, Any]], fit: Sequence[int], valid: Sequence[int]) -> dict[str, float]:
    from sklearn.exceptions import ConvergenceWarning
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    fit_ids = sorted({str(rows[index][key]) for index in fit for key in ("better", "worse")})
    valid_ids = sorted({str(rows[index][key]) for index in valid for key in ("better", "worse")})
    vectorizer = TfidfVectorizer(analyzer="char_wb", dtype=np.float64, max_features=30000, min_df=3, ngram_range=(3, 5), sublinear_tf=True)
    fit_matrix = vectorizer.fit_transform([code_view(cards[item]["code"]) for item in fit_ids])
    valid_matrix = vectorizer.transform([code_view(cards[item]["code"]) for item in valid_ids])
    design, labels = symmetric_design(pair_differences(fit_matrix, {item: i for i, item in enumerate(fit_ids)}, rows, fit))
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        model = LogisticRegression(C=0.5, fit_intercept=False, max_iter=2000, random_state=SEED, solver="liblinear", tol=1e-6).fit(design, labels)
    if any(issubclass(item.category, ConvergenceWarning) for item in caught):
        raise VerificationError("TF-IDF convergence warning")
    values = np.asarray(valid_matrix @ model.coef_.reshape(-1), dtype=np.float64).reshape(-1)
    return dict(zip(valid_ids, map(float, values)))


def average_ranks(values: Sequence[float]) -> np.ndarray:
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


def ensemble(rows: Sequence[dict[str, Any]], left: dict[str, float], right: dict[str, float]) -> dict[str, float]:
    grouped: dict[str, set[str]] = collections.defaultdict(set)
    endpoint_parent: dict[str, str] = {}
    for row in rows:
        parent = str(row["parent"])
        for key in ("better", "worse"):
            item = str(row[key])
            if endpoint_parent.setdefault(item, parent) != parent:
                raise VerificationError("endpoint has multiple parents")
            grouped[parent].add(item)
    output: dict[str, float] = {}
    for candidates in grouped.values():
        ids = sorted(candidates); denominator = max(len(ids) - 1, 1)
        lrank = (average_ranks([left[item] for item in ids]) - 1) / denominator
        rrank = (average_ranks([right[item] for item in ids]) - 1) / denominator
        output.update({item: float(value) for item, value in zip(ids, (lrank + rrank) / 2)})
    return output


def tie_hit(margin: float) -> float:
    return 1.0 if margin > EPSILON else 0.0 if margin < -EPSILON else 0.5


def random_score(card_id: str) -> float:
    import zlib
    return (zlib.crc32(f"{SEED}:{card_id}".encode()) & 0xFFFFFFFF) / 2**32


def cluster_summary(rows: Sequence[dict[str, Any]], values: Sequence[float], key: str, seed: int) -> tuple[float, list[float], dict[str, float]]:
    grouped: dict[str, list[float]] = collections.defaultdict(list)
    for row, value in zip(rows, values): grouped[str(row[key])].append(float(value))
    means = {name: sum(items) / len(items) for name, items in sorted(grouped.items())}
    population = list(means.values()); rng = random.Random(seed)
    draws = [sum(rng.choice(population) for _ in population) / len(population) for _ in range(BOOTSTRAP_REPS)]
    draws.sort()
    return sum(population) / len(population), [draws[250], draws[9750]], means


def summarize(rows: Sequence[dict[str, Any]], values: Sequence[float], offset: int) -> dict[str, Any]:
    run, run_ci, per_run = cluster_summary(rows, values, "run", SEED + offset)
    task, task_ci, per_task = cluster_summary(rows, values, "task", SEED + offset + 1)
    return {"overall": sum(values) / len(values), "run_macro": run, "run_macro_ci95": run_ci, "task_macro": task, "task_macro_ci95": task_ci, "per_run": per_run, "per_task": per_task}


def model_metrics(rows: Sequence[dict[str, Any]], scores: dict[str, float], offset: int) -> dict[str, Any]:
    hits = [tie_hit(scores[str(row["better"])] - scores[str(row["worse"])]) for row in rows]
    pair = summarize(rows, hits, offset)
    grouped: dict[str, list[tuple[dict[str, Any], float]]] = collections.defaultdict(list)
    for row, hit in zip(rows, hits): grouped[str(row["parent"])].append((row, hit))
    top_records: dict[str, dict[str, Any]] = {}; utility_records: dict[str, dict[str, Any]] = {}; incomplete = 0
    for parent, items in sorted(grouped.items()):
        parent_rows = [row for row, _ in items]
        candidates = {str(row[key]) for row in parent_rows for key in ("better", "worse")}
        if len(parent_rows) == len(candidates) * (len(candidates) - 1) // 2:
            losses = collections.Counter({item: 0 for item in candidates})
            for row in parent_rows: losses[str(row["worse"])] += 1
            true = {item for item, value in losses.items() if value == min(losses.values())}
            maximum = max(scores[item] for item in candidates)
            predicted = {item for item in candidates if abs(scores[item] - maximum) <= EPSILON}
            top_records[parent] = {"value": len(predicted & true) / len(predicted), "run": parent_rows[0]["run"], "task": parent_rows[0]["task"], "candidates": len(candidates)}
        else: incomplete += 1
        denominator = sum(float(row["gap_raw"]) for row, _ in items)
        utility_records[parent] = {"value": sum(float(row["gap_raw"]) * hit for row, hit in items) / denominator, "run": parent_rows[0]["run"], "task": parent_rows[0]["task"]}
    top_proxy = [{"run": item["run"], "task": item["task"]} for item in top_records.values()]
    top = summarize(top_proxy, [item["value"] for item in top_records.values()], 40)
    top.update({"complete_parents": len(top_records), "incomplete_parents": incomplete, "complete_share": len(top_records) / len(grouped)})
    utility_proxy = [{"run": item["run"], "task": item["task"]} for item in utility_records.values()]
    utility = summarize(utility_proxy, [item["value"] for item in utility_records.values()], 60)
    utility.update({"parents": len(utility_records), "definition": "mean_parent(sum(gap_raw*hit)/sum(gap_raw))"})
    per_task: dict[str, list[float]] = collections.defaultdict(list)
    for row, hit in zip(rows, hits): per_task[str(row["task"])].append(hit)
    supported = {task: {"pairs": len(values), "accuracy": sum(values) / len(values)} for task, values in sorted(per_task.items()) if len(values) >= 20}
    nonchance = sum(item["accuracy"] >= 0.5 for item in supported.values())
    consistency = {"minimum_pairs": 20, "supported_tasks": len(supported), "nonchance_tasks": nonchance, "nonchance_share": nonchance / len(supported), "details": supported}
    return {"pair": pair, "top1": top, "utility": utility, "task_consistency": consistency, "_hits": hits, "_top1_records": top_records, "_utility_records": utility_records}


def paired_records(left: dict[str, dict[str, Any]], right: dict[str, dict[str, Any]], offset: int) -> dict[str, Any]:
    if set(left) != set(right): raise VerificationError("paired support mismatch")
    names = sorted(left); proxy = [{"run": left[name]["run"], "task": left[name]["task"]} for name in names]
    values = [float(left[name]["value"]) - float(right[name]["value"]) for name in names]
    output = summarize(proxy, values, offset); output["records"] = len(values); return output


def paired(left: dict[str, Any], right: dict[str, Any], offset: int) -> dict[str, Any]:
    return {"top1": paired_records(left["_top1_records"], right["_top1_records"], offset), "utility": paired_records(left["_utility_records"], right["_utility_records"], offset + 10)}


def complement(candidate: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    left_hits, right_hits = candidate["_hits"], baseline["_hits"]
    x, y = np.asarray(left_hits), np.asarray(right_hits)
    phi = None if np.std(x) <= EPSILON or np.std(y) <= EPSILON else float(np.corrcoef(x, y)[0, 1])
    left, right = candidate["_top1_records"], baseline["_top1_records"]
    names = sorted(left); deltas = [left[name]["value"] - right[name]["value"] for name in names]
    oracle = sum(max(left[name]["value"], right[name]["value"]) for name in names) / len(names)
    best = max(candidate["top1"]["overall"], baseline["top1"]["overall"])
    return {"pair_disagreement": sum(abs(a - b) > EPSILON for a, b in zip(left_hits, right_hits)) / len(left_hits), "pair_correctness_phi": phi, "weighted_parent_rescue": sum(max(value, 0) for value in deltas) / len(deltas), "weighted_parent_harm": sum(max(-value, 0) for value in deltas) / len(deltas), "oracle_union_top1": oracle, "oracle_headroom_over_better_individual": oracle - best, "parents": len(names)}


def oracle_scores(rows: Sequence[dict[str, Any]]) -> dict[str, float]:
    grouped: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in rows: grouped[str(row["parent"])].append(row)
    output: dict[str, float] = {}
    for parent_rows in grouped.values():
        candidates = {str(row[key]) for row in parent_rows for key in ("better", "worse")}
        losses = collections.Counter({item: 0 for item in candidates})
        for row in parent_rows: losses[str(row["worse"])] += 1
        for item, value in losses.items():
            if item in output: raise VerificationError("oracle endpoint has multiple parents")
            output[item] = -float(value)
    return output


def unlock_gate(metrics: dict[str, Any], comparison: dict[str, Any], integrity: dict[str, bool]) -> dict[str, bool]:
    output = {
        "pair_ge_052": metrics["pair"]["overall"] >= 0.52, "top1_ge_050": metrics["top1"]["overall"] >= 0.50,
        "top1_delta_ge_003": comparison["top1"]["overall"] >= 0.03,
        "utility_ge_055": metrics["utility"]["overall"] >= 0.55,
        "utility_delta_ge_002": comparison["utility"]["overall"] >= 0.02,
        "top1_run_ci_low_gt_0": comparison["top1"]["run_macro_ci95"][0] > 0,
        "top1_task_ci_low_gt_0": comparison["top1"]["task_macro_ci95"][0] > 0,
        "utility_run_ci_low_gt_0": comparison["utility"]["run_macro_ci95"][0] > 0,
        "utility_task_ci_low_gt_0": comparison["utility"]["task_macro_ci95"][0] > 0,
        "supported_tasks_ge_15": metrics["task_consistency"]["supported_tasks"] >= 15,
        "task_nonchance_share_ge_060": metrics["task_consistency"]["nonchance_share"] >= 0.60,
        **integrity,
    }
    output["all"] = all(output.values()); return output


def nested_gate(metrics: dict[str, Any], comparison: dict[str, Any], complementarity: dict[str, Any], integrity: dict[str, bool]) -> dict[str, bool]:
    output = {
        "pair_ge_052": metrics["pair"]["overall"] >= 0.52, "top1_ge_046": metrics["top1"]["overall"] >= 0.46,
        "utility_ge_0525": metrics["utility"]["overall"] >= 0.525,
        "task_nonchance_share_ge_060": metrics["task_consistency"]["nonchance_share"] >= 0.60,
        "pair_disagreement_ge_015": complementarity["pair_disagreement"] >= 0.15,
        "weighted_parent_rescue_ge_008": complementarity["weighted_parent_rescue"] >= 0.08,
        "oracle_headroom_ge_005": complementarity["oracle_headroom_over_better_individual"] >= 0.05,
        "top1_run_ci_low_ge_minus002": comparison["top1"]["run_macro_ci95"][0] >= -0.02,
        "top1_task_ci_low_ge_minus002": comparison["top1"]["task_macro_ci95"][0] >= -0.02,
        "utility_run_ci_low_ge_minus002": comparison["utility"]["run_macro_ci95"][0] >= -0.02,
        "utility_task_ci_low_ge_minus002": comparison["utility"]["task_macro_ci95"][0] >= -0.02,
    }
    output["formal_runtime_le_cap"] = integrity["formal_runtime_le_cap"]
    output["all"] = all(output.values()) and all(integrity.values()); return output


def equal_gate(comparison: dict[str, Any], integrity: dict[str, bool]) -> dict[str, bool]:
    output = {
        "top1_delta_ge_0015": comparison["top1"]["overall"] >= 0.015,
        "utility_delta_ge_001": comparison["utility"]["overall"] >= 0.01,
        "top1_run_ci_low_ge_minus001": comparison["top1"]["run_macro_ci95"][0] >= -0.01,
        "top1_task_ci_low_ge_minus001": comparison["top1"]["task_macro_ci95"][0] >= -0.01,
        "utility_run_ci_low_ge_minus001": comparison["utility"]["run_macro_ci95"][0] >= -0.01,
        "utility_task_ci_low_ge_minus001": comparison["utility"]["task_macro_ci95"][0] >= -0.01,
    }
    output["formal_runtime_le_cap"] = integrity["formal_runtime_le_cap"]
    output["all"] = all(output.values()) and all(integrity.values()); return output


def strip(value: dict[str, Any]) -> dict[str, Any]: return {key: item for key, item in value.items() if not key.startswith("_")}


def assert_tree(actual: Any, expected: Any, label: str, tolerance: float = 1e-9) -> None:
    if isinstance(expected, dict):
        if set(actual) != set(expected): raise VerificationError(f"{label} keys differ")
        for key in expected: assert_tree(actual[key], expected[key], f"{label}.{key}", tolerance)
    elif isinstance(expected, list):
        if len(actual) != len(expected): raise VerificationError(f"{label} lengths differ")
        for index, item in enumerate(expected): assert_tree(actual[index], item, f"{label}[{index}]", tolerance)
    elif isinstance(expected, (float, int)) and not isinstance(expected, bool):
        if not math.isclose(float(actual), float(expected), abs_tol=tolerance, rel_tol=tolerance): raise VerificationError(f"{label}: {actual} != {expected}")
    elif actual != expected: raise VerificationError(f"{label}: {actual!r} != {expected!r}")


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", required=True, type=Path); parser.add_argument("--run-map", required=True, type=Path)
    parser.add_argument("--cards", required=True, type=Path); parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--manifest-summary", required=True, type=Path); parser.add_argument("--baseline-oof", required=True, type=Path)
    parser.add_argument("--result-dir", required=True, type=Path); parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--expect-pairs-sha256", required=True); parser.add_argument("--expect-run-map-sha256", required=True)
    parser.add_argument("--expect-cards-sha256", required=True); parser.add_argument("--expect-manifest-sha256", required=True)
    parser.add_argument("--expect-baseline-sha256", required=True)
    return parser.parse_args()


def main() -> int:
    args = arguments()
    for path, label in ((args.pairs, "pairs"), (args.run_map, "run map"), (args.cards, "cards"), (args.manifest, "manifest"), (args.manifest_summary, "manifest summary"), (args.baseline_oof, "baseline OOF")):
        reject_forbidden_path(path, label)
    producer_path = args.result_dir / "summary.json"; prediction_path = args.result_dir / "oof_predictions.csv"
    producer = json.loads(producer_path.read_text(encoding="utf-8"))
    if producer.get("protocol") != PROTOCOL or producer.get("frozen_read") is not False:
        raise VerificationError("producer protocol/frozen flag mismatch")
    manifest, _ = load_manifest(args.manifest, args.manifest_summary, args.expect_manifest_sha256)
    cards = load_cards(args.cards, manifest, args.expect_cards_sha256)
    rows = load_pairs(args.pairs, args.run_map, manifest, args.expect_pairs_sha256, args.expect_run_map_sha256)
    folds, baseline_scores = load_baseline(args.baseline_oof, rows, args.expect_baseline_sha256)
    ids = sorted(cards); position = {item: index for index, item in enumerate(ids)}
    names = sorted(static_feature_dict(cards[ids[0]])); op_indices = [names.index(f"op_{name}") for name in OP_NAMES]
    matrix = np.asarray([[static_feature_dict(cards[item])[name] for name in names] for item in ids], dtype=np.float64)
    scores: dict[str, dict[str, float]] = {arm: {} for arm in BASE_ARMS}
    checkpoint_audit: list[dict[str, Any]] = []
    for fold in range(OUTER_FOLDS):
        fit = [index for index, value in enumerate(folds) if value != fold]; valid = [index for index, value in enumerate(folds) if value == fold]
        fit_runs = {rows[index]["run"] for index in fit}; valid_runs = {rows[index]["run"] for index in valid}
        fit_ids = {str(rows[index][key]) for index in fit for key in ("better", "worse")}; valid_ids = sorted({str(rows[index][key]) for index in valid for key in ("better", "worse")})
        if fit_runs & valid_runs or fit_ids & set(valid_ids): raise VerificationError(f"fold overlap: {fold}")
        refit = {
            "op_only_lr": fit_linear(matrix, position, rows, fit, valid_ids, op_indices),
            "static_lr": fit_linear(matrix, position, rows, fit, valid_ids, list(range(matrix.shape[1]))),
            "static_gbm": fit_gbm(matrix, position, rows, fit, valid),
            PRIMARY_ARM: fit_tfidf(cards, rows, fit, valid),
        }
        fold_dir = args.result_dir / "checkpoints" / f"fold_{fold}"; score_path = fold_dir / "valid_scores.npz"
        fold_summary = json.loads((fold_dir / "fold_summary.json").read_text(encoding="utf-8"))
        if sha256(score_path) != fold_summary.get("valid_scores_sha256"): raise VerificationError(f"checkpoint SHA mismatch: {fold}")
        with np.load(score_path, allow_pickle=False) as data:
            stored_ids = [str(item) for item in data["card_ids"].tolist()]
            if stored_ids != valid_ids: raise VerificationError(f"checkpoint IDs mismatch: {fold}")
            for arm in BASE_ARMS:
                stored = np.asarray(data[arm], dtype=np.float64)
                expected = np.asarray([refit[arm][item] for item in valid_ids], dtype=np.float64)
                if not np.allclose(stored, expected, atol=1e-9, rtol=1e-9):
                    difference = float(np.max(np.abs(stored - expected)))
                    raise VerificationError(f"refit score mismatch fold={fold} arm={arm} max={difference}")
                scores[arm].update(refit[arm])
        checkpoint_audit.append({"fold": fold, "run_overlap": 0, "endpoint_overlap": 0, "valid_scores_sha256": sha256(score_path)})
    scores[BASELINE_ARM] = baseline_scores; scores[EQUAL_ARM] = ensemble(rows, baseline_scores, scores[PRIMARY_ARM])
    if any(set(scores[arm]) != set(ids) for arm in ARMS): raise VerificationError("global score coverage mismatch")
    with prediction_path.open("r", encoding="utf-8", newline="") as handle: predictions = list(csv.DictReader(handle))
    if len(predictions) != len(rows) or sha256(prediction_path) != producer["outputs"]["oof_predictions_sha256"]: raise VerificationError("prediction inventory/SHA mismatch")
    for index, (row, output) in enumerate(zip(rows, predictions)):
        if int(output["row_index"]) != index or int(output["fold"]) != folds[index]: raise VerificationError(f"prediction row mismatch: {index}")
        for arm in ARMS:
            better, worse = scores[arm][row["better"]], scores[arm][row["worse"]]
            for key, value in ((f"{arm}_better_score", better), (f"{arm}_worse_score", worse), (f"{arm}_margin", better - worse), (f"{arm}_hit", tie_hit(better - worse))):
                if not math.isclose(float(output[key]), float(value), abs_tol=1e-9, rel_tol=1e-9): raise VerificationError(f"prediction value mismatch: {index} {key}")
    metrics = {arm: model_metrics(rows, scores[arm], METRIC_SEED_OFFSETS[arm]) for arm in ARMS}
    comparisons = {arm: paired(metrics[arm], metrics[BASELINE_ARM], 600 + 20 * index) for index, arm in enumerate((*BASE_ARMS, EQUAL_ARM))}
    complements = {arm: complement(metrics[arm], metrics[BASELINE_ARM]) for arm in BASE_ARMS}
    oracle_metric = model_metrics(rows, oracle_scores(rows), 500)
    random_metric = model_metrics(rows, {item: random_score(item) for item in ids}, 520)
    tasks = {row["task"] for row in rows}; runs = {row["run"] for row in rows}; parents = {row["parent"] for row in rows}
    integrity = {
        "all_fits_accepted": True, "baseline_hash_exact": sha256(args.baseline_oof) == args.expect_baseline_sha256.lower(),
        "cards_hash_exact": sha256(args.cards) == args.expect_cards_sha256.lower(),
        "complete_parents_eq_2259": metrics[PRIMARY_ARM]["top1"]["complete_parents"] == EXPECTED["complete_parents"],
        "coverage_exact": all(set(scores[arm]) == set(ids) for arm in ARMS), "endpoints_eq_5499": len(ids) == EXPECTED["endpoints"],
        "frozen_read_false": True, "label_fields_retained_zero": True,
        "orientation_oracle_eq_1": oracle_metric["pair"]["overall"] == 1.0,
        "outer_endpoint_overlap_eq_0": all(item["endpoint_overlap"] == 0 for item in checkpoint_audit),
        "outer_run_overlap_eq_0": all(item["run_overlap"] == 0 for item in checkpoint_audit),
        "pairs_eq_4263": len(rows) == EXPECTED["pairs"], "parents_eq_2293": len(parents) == EXPECTED["parents"],
        "post_execution_fields_retained_zero": True,
        "random_pair_in_047_053": 0.47 <= random_metric["pair"]["overall"] <= 0.53,
        "runs_eq_333": len(runs) == EXPECTED["runs"], "tasks_eq_23": len(tasks) == EXPECTED["tasks"],
        "formal_runtime_le_cap": float(producer["runtime_s"]) <= float(producer["wall_cap_s"]),
    }
    primary_gate = unlock_gate(metrics[PRIMARY_ARM], comparisons[PRIMARY_ARM], integrity)
    nested_gates = {arm: nested_gate(metrics[arm], comparisons[arm], complements[arm], integrity) for arm in BASE_ARMS}
    rank_gate = equal_gate(comparisons[EQUAL_ARM], integrity)
    independent_status = "DISCOVERY_UNLOCK_RECOMMENDED" if primary_gate["all"] else "DISCOVERY_NO_UNLOCK_GO_NESTED_ENSEMBLE" if any(gate["all"] for gate in nested_gates.values()) else "DISCOVERY_NO_UNLOCK_NO_ENSEMBLE"
    for arm in ARMS: assert_tree(strip(metrics[arm]), producer["metrics"][arm], f"metrics.{arm}")
    assert_tree(comparisons, producer["paired_delta_vs_fixed_frozen"], "comparisons")
    assert_tree(complements, producer["complementarity_vs_fixed_frozen"], "complementarity")
    assert_tree(strip(oracle_metric), producer["orientation_oracle"], "orientation_oracle")
    assert_tree(strip(random_metric), producer["random_control"], "random_control")
    assert_tree(integrity, producer["integrity_gate"], "integrity_gate")
    assert_tree(primary_gate, producer["primary_unlock_gate"], "primary_unlock_gate")
    assert_tree(nested_gates, producer["nested_ensemble_gates"], "nested_ensemble_gates")
    assert_tree(rank_gate, producer["equal_rank_gate"], "equal_rank_gate")
    status = str(producer["status"])
    if independent_status != status: raise VerificationError(f"independent status mismatch: {independent_status} != {status}")
    verification = {
        "status": f"VERIFIED_{status}", "protocol": PROTOCOL, "frozen_read": False,
        "producer_summary_sha256": sha256(producer_path), "producer_predictions_sha256": sha256(prediction_path),
        "checkpoint_audit": checkpoint_audit, "metrics": {arm: strip(metrics[arm]) for arm in ARMS},
        "paired_delta_vs_fixed_frozen": comparisons, "complementarity_vs_fixed_frozen": complements,
        "integrity_gate": integrity, "primary_unlock_gate": primary_gate, "nested_ensemble_gates": nested_gates,
        "equal_rank_gate": rank_gate,
    }
    atomic_json(args.output, verification)
    print(f"VERIFIED_{status}", f"primary_top1={metrics[PRIMARY_ARM]['top1']['overall']:.6f}", f"primary_utility={metrics[PRIMARY_ARM]['utility']['overall']:.6f}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
