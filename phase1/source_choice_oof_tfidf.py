#!/usr/bin/env python3
"""Train-only task-LOTO and run-grouped OOF source-choice TF-IDF baseline."""

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
import sys
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import scipy
import sklearn
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression


PROTOCOL_NAME = "source-choice-oof-tfidf-v1"
MODEL_SCHEMA = "source-choice-decision-group-v2"
CLUSTER_SCHEMA = "source-choice-cluster-manifest-v1"
GROUP_FIELDS = {
    "schema_version", "group_id", "task", "source_size", "candidates",
    "winner_candidate_sha256",
}
CANDIDATE_FIELDS = {
    "candidate_id_sha256", "code", "code_sha256", "operator", "step", "depth",
}
CLUSTER_FIELDS = {
    "schema_version", "group_id", "role", "task", "run_id_sha256",
    "parent_id_sha256", "source_size",
}
ARMS = (
    "min_candidate_sha",
    "max_step_then_min_sha",
    "max_code_length_then_min_sha",
    "tfidf_pairwise_lr",
    "winner_oracle",
)
SPLITS = ("task_loto", "run_grouped_5fold")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


class OOFError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise OOFError(message)


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    require(not path.exists(), f"refusing to overwrite {path.name}")
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(json.dumps(value, indent=2, sort_keys=True, allow_nan=False).encode() + b"\n")
    os.replace(temporary, path)


def read_json(path: Path, where: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OOFError(f"invalid JSON: {where}") from exc
    require(isinstance(value, dict), f"non-object JSON: {where}")
    return value


def read_canonical_jsonl(path: Path, where: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("rb") as handle:
        for number, line in enumerate(handle, 1):
            require(line.endswith(b"\n"), f"unterminated row: {where}:{number}")
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise OOFError(f"invalid row: {where}:{number}") from exc
            require(
                isinstance(value, dict) and canonical(value) + b"\n" == line,
                f"non-canonical row: {where}:{number}",
            )
            rows.append(value)
    require(bool(rows), f"empty JSONL: {where}")
    return rows


def valid_hash(value: Any, where: str) -> str:
    require(isinstance(value, str) and HEX64.fullmatch(value) is not None, f"bad hash: {where}")
    return value


def valid_int(value: Any, where: str) -> int:
    require(not isinstance(value, bool) and isinstance(value, int), f"bad integer: {where}")
    return value


def load_protocol(path: Path) -> dict[str, Any]:
    value = read_json(path, "protocol")
    require(value.get("protocol") == PROTOCOL_NAME, "protocol name differs")
    require(
        set(value) == {
            "protocol", "inputs", "expected_train", "splits", "model", "controls",
            "metrics", "gate", "scope",
        },
        "protocol fields differ",
    )
    require(value["controls"] == list(ARMS[:3]) + [ARMS[4]], "control list differs")
    require(value["scope"].get("frozen_or_extension_model_read") is False, "scope differs")
    require(value["scope"].get("frozen_or_extension_label_vault_read") is False, "scope differs")
    return value


def bind_input(path: Path, receipt: dict[str, Any], where: str) -> None:
    require(path.is_file(), f"missing input: {where}")
    require(path.stat().st_size == receipt["bytes"], f"byte count differs: {where}")
    require(sha256_file(path) == receipt["sha256"], f"SHA differs: {where}")


def load_data(
    train_path: Path, cluster_path: Path, protocol: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, Any]]:
    bind_input(train_path, protocol["inputs"]["train_model"], "train model")
    bind_input(cluster_path, protocol["inputs"]["cluster_manifest"], "cluster manifest")
    train_rows = read_canonical_jsonl(train_path, "train model")
    cluster_rows = read_canonical_jsonl(cluster_path, "cluster manifest")
    require(len(train_rows) == protocol["inputs"]["train_model"]["rows"], "train rows differ")
    require(len(cluster_rows) == protocol["inputs"]["cluster_manifest"]["rows"], "cluster rows differ")

    clusters: dict[str, dict[str, Any]] = {}
    train_clusters: dict[str, dict[str, Any]] = {}
    for number, row in enumerate(cluster_rows, 1):
        require(set(row) == CLUSTER_FIELDS and row.get("schema_version") == CLUSTER_SCHEMA, f"cluster schema {number}")
        group_id = valid_hash(row.get("group_id"), "cluster group")
        require(group_id not in clusters, "duplicate cluster group")
        require(row.get("role") in {"train", "frozen", "extension"}, "bad cluster role")
        valid_hash(row.get("run_id_sha256"), "cluster run")
        valid_hash(row.get("parent_id_sha256"), "cluster parent")
        require(isinstance(row.get("task"), str) and row["task"], "bad cluster task")
        require(valid_int(row.get("source_size"), "cluster source size") >= 2, "bad source size")
        clusters[group_id] = row
        if row["role"] == "train":
            train_clusters[group_id] = row

    groups: list[dict[str, Any]] = []
    groups_by_id: dict[str, dict[str, Any]] = {}
    candidates: dict[str, dict[str, Any]] = {}
    source_sizes: collections.Counter[int] = collections.Counter()
    code_locations: dict[str, set[tuple[str, str]]] = collections.defaultdict(set)
    for number, row in enumerate(train_rows, 1):
        require(set(row) == GROUP_FIELDS and row.get("schema_version") == MODEL_SCHEMA, f"group schema {number}")
        group_id = valid_hash(row.get("group_id"), "group")
        require(group_id not in groups_by_id, "duplicate train group")
        cluster = train_clusters.get(group_id)
        require(cluster is not None, "train group lacks train cluster")
        task = row.get("task")
        source_size = valid_int(row.get("source_size"), "source size")
        values = row.get("candidates")
        require(
            isinstance(task, str) and task == cluster["task"]
            and source_size == cluster["source_size"]
            and isinstance(values, list) and len(values) == source_size,
            "group/cluster closure differs",
        )
        ids: list[str] = []
        for candidate_number, candidate in enumerate(values, 1):
            require(isinstance(candidate, dict) and set(candidate) == CANDIDATE_FIELDS, "candidate fields differ")
            candidate_id = valid_hash(candidate.get("candidate_id_sha256"), "candidate")
            code = candidate.get("code")
            code_hash = valid_hash(candidate.get("code_sha256"), "code")
            require(candidate_id not in candidates, "candidate ID repeats")
            require(isinstance(code, str) and code, "empty code")
            require(hashlib.sha256(code.encode("utf-8")).hexdigest() == code_hash, "code hash differs")
            require(candidate.get("operator") in {"Draft", "Improve"}, "operator outside v2 enum")
            valid_int(candidate.get("step"), "step")
            valid_int(candidate.get("depth"), "depth")
            candidates[candidate_id] = candidate
            ids.append(candidate_id)
            code_locations[code_hash].add((cluster["run_id_sha256"], task))
        require(ids == sorted(ids) and len(ids) == len(set(ids)), "candidate order differs")
        winner = valid_hash(row.get("winner_candidate_sha256"), "winner")
        require(winner in set(ids), "winner outside group")
        groups.append(row)
        groups_by_id[group_id] = row
        source_sizes[source_size] += 1

    expected = protocol["expected_train"]
    tasks = {row["task"] for row in groups}
    runs = {train_clusters[row["group_id"]]["run_id_sha256"] for row in groups}
    run_tasks: dict[str, set[str]] = collections.defaultdict(set)
    for row in groups:
        run_tasks[train_clusters[row["group_id"]]["run_id_sha256"]].add(row["task"])
    cross_run = sum(len({item[0] for item in locations}) > 1 for locations in code_locations.values())
    cross_task = sum(len({item[1] for item in locations}) > 1 for locations in code_locations.values())
    census = {
        "groups": len(groups),
        "candidate_slots": sum(len(row["candidates"]) for row in groups),
        "tasks": len(tasks),
        "runs": len(runs),
        "unique_candidate_ids": len(candidates),
        "cross_run_code_hashes": cross_run,
        "cross_task_code_hashes": cross_task,
        "source_size_counts": {str(key): source_sizes[key] for key in sorted(source_sizes)},
        "mixed_task_runs": sum(len(values) > 1 for values in run_tasks.values()),
    }
    for key in (
        "groups", "candidate_slots", "tasks", "runs", "unique_candidate_ids",
        "cross_run_code_hashes", "cross_task_code_hashes", "source_size_counts",
    ):
        require(census[key] == expected[key], f"train census differs: {key}")
    require(census["mixed_task_runs"] == 0, "physical run spans tasks")
    return groups, candidates, train_clusters, census


def sha_tie(seed: int, *values: Any) -> str:
    return hashlib.sha256((str(seed) + "|" + "|".join(map(str, values))).encode()).hexdigest()


def run_fold_assignment(
    groups: list[dict[str, Any]], clusters: dict[str, dict[str, Any]], folds: int, seed: int
) -> tuple[dict[str, int], dict[str, Any]]:
    groups_by_run: dict[str, list[str]] = collections.defaultdict(list)
    task_by_run: dict[str, str] = {}
    for row in groups:
        cluster = clusters[row["group_id"]]
        run = cluster["run_id_sha256"]
        groups_by_run[run].append(row["group_id"])
        previous = task_by_run.setdefault(run, row["task"])
        require(previous == row["task"], "run/task mismatch")
    runs_by_task: dict[str, list[str]] = collections.defaultdict(list)
    for run, task in task_by_run.items():
        runs_by_task[task].append(run)
    assignment: dict[str, int] = {}
    total_loads = [0] * folds
    task_loads: dict[str, list[int]] = {}
    for task in sorted(runs_by_task):
        loads = [0] * folds
        task_loads[task] = loads
        ordered = sorted(
            runs_by_task[task],
            key=lambda run: (-len(groups_by_run[run]), sha_tie(seed, task, run)),
        )
        for run in ordered:
            fold = min(
                range(folds),
                key=lambda item: (
                    loads[item], total_loads[item], sha_tie(seed, task, run, item)
                ),
            )
            assignment[run] = fold
            weight = len(groups_by_run[run])
            loads[fold] += weight
            total_loads[fold] += weight
    require(set(assignment) == set(groups_by_run), "run assignment coverage differs")
    group_fold = {
        row["group_id"]: assignment[clusters[row["group_id"]]["run_id_sha256"]]
        for row in groups
    }
    receipt = {
        "seed": seed,
        "fold_group_counts": {str(fold): list(group_fold.values()).count(fold) for fold in range(folds)},
        "fold_run_counts": {str(fold): list(assignment.values()).count(fold) for fold in range(folds)},
        "run_assignment_sha256": hashlib.sha256(canonical(sorted(assignment.items()))).hexdigest(),
    }
    return group_fold, receipt


def split_maps(
    groups: list[dict[str, Any]], clusters: dict[str, dict[str, Any]], protocol: dict[str, Any]
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    task_map = {row["group_id"]: row["task"] for row in groups}
    secondary = protocol["splits"]["secondary"]
    run_map, run_receipt = run_fold_assignment(
        groups, clusters, secondary["folds"], secondary["assignment_seed"]
    )
    maps = {"task_loto": task_map, "run_grouped_5fold": run_map}
    receipt = {
        "task_loto": {
            "folds": len(set(task_map.values())),
            "assignment_sha256": hashlib.sha256(canonical(sorted(task_map.items()))).hexdigest(),
        },
        "run_grouped_5fold": run_receipt,
    }
    return maps, receipt


def control_ranking(group: dict[str, Any], arm: str) -> list[str]:
    candidates = group["candidates"]
    if arm == "min_candidate_sha":
        return sorted(candidate["candidate_id_sha256"] for candidate in candidates)
    if arm == "max_step_then_min_sha":
        return [
            candidate["candidate_id_sha256"]
            for candidate in sorted(candidates, key=lambda item: (-item["step"], item["candidate_id_sha256"]))
        ]
    if arm == "max_code_length_then_min_sha":
        return [
            candidate["candidate_id_sha256"]
            for candidate in sorted(candidates, key=lambda item: (-len(item["code"]), item["candidate_id_sha256"]))
        ]
    if arm == "winner_oracle":
        winner = group["winner_candidate_sha256"]
        return [winner] + sorted(
            candidate["candidate_id_sha256"]
            for candidate in candidates if candidate["candidate_id_sha256"] != winner
        )
    raise OOFError(f"unknown control: {arm}")


def fit_fold(
    train_groups: list[dict[str, Any]],
    test_groups: list[dict[str, Any]],
    candidates: dict[str, dict[str, Any]],
    model_config: dict[str, Any],
) -> tuple[dict[str, list[str]], dict[str, Any]]:
    train_ids = sorted(
        candidate["candidate_id_sha256"] for row in train_groups for candidate in row["candidates"]
    )
    test_ids = sorted(
        candidate["candidate_id_sha256"] for row in test_groups for candidate in row["candidates"]
    )
    require(not (set(train_ids) & set(test_ids)), "candidate crosses OOF fold")
    all_ids = sorted(train_ids + test_ids)
    positions = {candidate_id: index for index, candidate_id in enumerate(all_ids)}
    vector = model_config["vectorizer"]
    prefix = model_config["code_prefix_chars"]
    tfidf = TfidfVectorizer(
        analyzer=vector["analyzer"],
        ngram_range=(vector["ngram_min"], vector["ngram_max"]),
        max_features=vector["max_features"],
        min_df=vector["min_df"],
        sublinear_tf=vector["sublinear_tf"],
        dtype=np.float64,
    )
    tfidf.fit((candidates[candidate_id]["code"][:prefix] for candidate_id in train_ids))
    matrix = tfidf.transform(
        (candidates[candidate_id]["code"][:prefix] for candidate_id in all_ids)
    ).tocsr()

    differences = []
    relation_weights = []
    relation_count = 0
    for row in train_groups:
        winner = row["winner_candidate_sha256"]
        losers = [
            candidate["candidate_id_sha256"]
            for candidate in row["candidates"]
            if candidate["candidate_id_sha256"] != winner
        ]
        require(len(losers) == row["source_size"] - 1, "loser count differs")
        weight = 1.0 / (2.0 * len(losers))
        for loser in losers:
            differences.append(matrix[positions[winner]] - matrix[positions[loser]])
            relation_weights.append(weight)
            relation_count += 1
    difference = sparse.vstack(differences, format="csr")
    fit_x = sparse.vstack((difference, -difference), format="csr")
    fit_y = np.concatenate(
        (np.ones(relation_count, dtype=np.int8), np.zeros(relation_count, dtype=np.int8))
    )
    fit_weight = np.asarray(relation_weights + relation_weights, dtype=np.float64)
    require(abs(float(fit_weight.sum()) - len(train_groups)) < 1e-9, "group weights differ")
    logistic = model_config["logistic_regression"]
    model = LogisticRegression(
        C=logistic["C"],
        solver=logistic["solver"],
        max_iter=logistic["max_iter"],
        random_state=logistic["random_state"],
    ).fit(fit_x, fit_y, sample_weight=fit_weight)
    require(int(model.n_iter_[0]) < logistic["max_iter"], "LR did not converge")
    require(np.isfinite(model.coef_).all() and np.isfinite(model.intercept_).all(), "non-finite model")

    rankings: dict[str, list[str]] = {}
    for row in test_groups:
        ids = [candidate["candidate_id_sha256"] for candidate in row["candidates"]]
        scores = model.decision_function(matrix[[positions[candidate_id] for candidate_id in ids]])
        require(np.isfinite(scores).all(), "non-finite held-out score")
        rankings[row["group_id"]] = [
            candidate_id
            for _, candidate_id in sorted(zip(scores.tolist(), ids), key=lambda item: (-item[0], item[1]))
        ]
    coefficient_bytes = np.asarray(model.coef_, dtype="<f8").tobytes() + np.asarray(
        model.intercept_, dtype="<f8"
    ).tobytes()
    receipt = {
        "train_groups": len(train_groups),
        "test_groups": len(test_groups),
        "train_candidates": len(train_ids),
        "test_candidates": len(test_ids),
        "winner_loser_relations": relation_count,
        "oriented_fit_rows": 2 * relation_count,
        "fit_weight_sum": float(fit_weight.sum()),
        "vocabulary_size": len(tfidf.vocabulary_),
        "lr_iterations": int(model.n_iter_[0]),
        "coefficient_sha256": hashlib.sha256(coefficient_bytes).hexdigest(),
    }
    return rankings, receipt


def one_sided_sign_p(values: Iterable[float]) -> dict[str, Any]:
    positive = sum(value > 0 for value in values)
    negative = sum(value < 0 for value in values)
    zero = sum(value == 0 for value in values)
    n = positive + negative
    p = 1.0 if n == 0 else sum(math.comb(n, k) for k in range(positive, n + 1)) / (2 ** n)
    return {"positive": positive, "negative": negative, "zero": zero, "one_sided_p": p}


def task_bootstrap(values: dict[str, list[float]], reps: int, seed: int) -> dict[str, Any]:
    task_points = np.asarray([np.mean(values[key]) for key in sorted(values)], dtype=np.float64)
    rng = np.random.default_rng(seed)
    sampled = rng.integers(0, len(task_points), size=(reps, len(task_points)))
    estimates = np.mean(task_points[sampled], axis=1)
    low, high = np.quantile(estimates, [0.025, 0.975], method="linear")
    return {
        "point": float(np.mean(task_points)),
        "ci95": [float(low), float(high)],
        "clusters": len(task_points),
        "replicates": reps,
        "seed": seed,
    }


def run_clustered_micro(values: dict[str, list[float]], reps: int, seed: int) -> dict[str, Any]:
    ordered = [np.asarray(values[key], dtype=np.float64) for key in sorted(values)]
    rng = np.random.default_rng(seed)
    estimates = np.empty(reps, dtype=np.float64)
    for index in range(reps):
        sampled = rng.integers(0, len(ordered), size=len(ordered))
        numerator = sum(float(np.sum(ordered[item])) for item in sampled)
        denominator = sum(len(ordered[item]) for item in sampled)
        estimates[index] = numerator / denominator
    low, high = np.quantile(estimates, [0.025, 0.975], method="linear")
    flat = np.concatenate(ordered)
    return {
        "point": float(np.mean(flat)),
        "ci95": [float(low), float(high)],
        "clusters": len(ordered),
        "replicates": reps,
        "seed": seed,
    }


def summarize_rows(
    rows: list[dict[str, Any]], protocol: dict[str, Any]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    task_delta: dict[str, list[float]] = collections.defaultdict(list)
    run_delta: dict[str, list[float]] = collections.defaultdict(list)
    task_hit: dict[str, list[float]] = collections.defaultdict(list)
    task_uniform: dict[str, list[float]] = collections.defaultdict(list)
    task_mrr: dict[str, list[float]] = collections.defaultdict(list)
    run_hit: dict[str, list[float]] = collections.defaultdict(list)
    arity: dict[int, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in rows:
        expected = 1.0 / row["source_size"]
        delta = row["hit"] - expected
        task_delta[row["task"]].append(delta)
        run_delta[row["run_id_sha256"]].append(delta)
        task_hit[row["task"]].append(float(row["hit"]))
        task_uniform[row["task"]].append(expected)
        task_mrr[row["task"]].append(1.0 / row["winner_rank"])
        run_hit[row["run_id_sha256"]].append(float(row["hit"]))
        arity[row["source_size"]].append(row)
    metrics = protocol["metrics"]
    task_ci = task_bootstrap(task_delta, metrics["bootstrap_replicates"], metrics["task_bootstrap_seed"])
    run_ci = run_clustered_micro(run_delta, metrics["bootstrap_replicates"], metrics["run_bootstrap_seed"])
    per_task = []
    for task in sorted(task_hit):
        per_task.append({
            "task": task,
            "groups": len(task_hit[task]),
            "runs": len({row["run_id_sha256"] for row in rows if row["task"] == task}),
            "accuracy": float(np.mean(task_hit[task])),
            "uniform_expected_accuracy": float(np.mean(task_uniform[task])),
            "delta": float(np.mean(task_delta[task])),
            "winner_mrr": float(np.mean(task_mrr[task])),
        })
    source_size = {}
    for size, selected in sorted(arity.items()):
        source_size[str(size)] = {
            "groups": len(selected),
            "accuracy": float(np.mean([row["hit"] for row in selected])),
            "uniform_expected_accuracy": 1.0 / size,
            "delta": float(np.mean([row["hit"] - 1.0 / size for row in selected])),
            "winner_mrr": float(np.mean([1.0 / row["winner_rank"] for row in selected])),
        }
    summary = {
        "groups": len(rows),
        "tasks": len(task_hit),
        "runs": len(run_hit),
        "micro_accuracy": float(np.mean([row["hit"] for row in rows])),
        "micro_uniform_expected_accuracy": float(np.mean([1.0 / row["source_size"] for row in rows])),
        "micro_delta": float(np.mean([row["hit"] - 1.0 / row["source_size"] for row in rows])),
        "task_macro_accuracy": float(np.mean([np.mean(values) for values in task_hit.values()])),
        "task_macro_uniform_expected_accuracy": float(
            np.mean([np.mean(values) for values in task_uniform.values()])
        ),
        "task_macro_delta": task_ci["point"],
        "task_clustered_delta": task_ci,
        "run_macro_accuracy": float(np.mean([np.mean(values) for values in run_hit.values()])),
        "run_clustered_micro_delta": run_ci,
        "task_sign": one_sided_sign_p([item["delta"] for item in per_task]),
        "winner_mrr": float(np.mean([1.0 / row["winner_rank"] for row in rows])),
        "source_size": source_size,
    }
    return summary, per_task


def analyze(
    protocol_path: Path, train_path: Path, cluster_path: Path, output: Path
) -> dict[str, Any]:
    require(not output.exists(), "output directory exists")
    protocol = load_protocol(protocol_path)
    groups, candidates, clusters, census = load_data(train_path, cluster_path, protocol)
    maps, split_receipt = split_maps(groups, clusters, protocol)
    output.mkdir(parents=True)

    prediction_rows: list[dict[str, Any]] = []
    model_receipts: list[dict[str, Any]] = []
    groups_by_id = {row["group_id"]: row for row in groups}
    for split_name in SPLITS:
        assignment = maps[split_name]
        folds = sorted(set(assignment.values()), key=str)
        tfidf_rankings: dict[str, list[str]] = {}
        for fold in folds:
            train_groups = [row for row in groups if assignment[row["group_id"]] != fold]
            test_groups = [row for row in groups if assignment[row["group_id"]] == fold]
            require(train_groups and test_groups, f"empty fold: {split_name}:{fold}")
            train_runs = {clusters[row["group_id"]]["run_id_sha256"] for row in train_groups}
            test_runs = {clusters[row["group_id"]]["run_id_sha256"] for row in test_groups}
            require(not (train_runs & test_runs), f"run overlap: {split_name}:{fold}")
            if split_name == "task_loto":
                require(
                    not ({row["task"] for row in train_groups} & {row["task"] for row in test_groups}),
                    f"task overlap: {fold}",
                )
            train_code = {
                candidate["code_sha256"] for row in train_groups for candidate in row["candidates"]
            }
            test_code = {
                candidate["code_sha256"] for row in test_groups for candidate in row["candidates"]
            }
            require(not (train_code & test_code), f"code hash overlap: {split_name}:{fold}")
            rankings, receipt = fit_fold(train_groups, test_groups, candidates, protocol["model"])
            require(not (set(tfidf_rankings) & set(rankings)), "OOF group predicted twice")
            tfidf_rankings.update(rankings)
            model_receipts.append({
                "split": split_name,
                "fold": str(fold),
                "train_tasks": len({row["task"] for row in train_groups}),
                "test_tasks": len({row["task"] for row in test_groups}),
                "train_runs": len(train_runs),
                "test_runs": len(test_runs),
                "run_overlap": 0,
                "task_overlap": 0 if split_name == "task_loto" else None,
                "candidate_overlap": 0,
                "code_hash_overlap": 0,
                **receipt,
            })
        require(set(tfidf_rankings) == set(groups_by_id), f"OOF coverage differs: {split_name}")
        for group_id in sorted(groups_by_id):
            group = groups_by_id[group_id]
            winner = group["winner_candidate_sha256"]
            run = clusters[group_id]["run_id_sha256"]
            for arm in ARMS:
                ranking = (
                    tfidf_rankings[group_id]
                    if arm == "tfidf_pairwise_lr"
                    else control_ranking(group, arm)
                )
                require(set(ranking) == {item["candidate_id_sha256"] for item in group["candidates"]}, "ranking closure")
                winner_rank = ranking.index(winner) + 1
                prediction_rows.append({
                    "split": split_name,
                    "fold": str(assignment[group_id]),
                    "arm": arm,
                    "group_id": group_id,
                    "task": group["task"],
                    "run_id_sha256": run,
                    "source_size": group["source_size"],
                    "selected_candidate_sha256": ranking[0],
                    "hit": int(ranking[0] == winner),
                    "winner_rank": winner_rank,
                })

    metrics_by_split: dict[str, dict[str, Any]] = {}
    per_task_rows: list[dict[str, Any]] = []
    for split_name in SPLITS:
        metrics_by_split[split_name] = {}
        for arm in ARMS:
            selected = [
                row for row in prediction_rows if row["split"] == split_name and row["arm"] == arm
            ]
            require(len(selected) == len(groups), "arm coverage differs")
            arm_metrics, task_rows = summarize_rows(selected, protocol)
            metrics_by_split[split_name][arm] = arm_metrics
            per_task_rows.extend(
                {"split": split_name, "arm": arm, **row} for row in task_rows
            )
    for split_name in SPLITS:
        require(metrics_by_split[split_name]["winner_oracle"]["micro_accuracy"] == 1.0, "oracle failed")

    gate = protocol["gate"]
    threshold = gate["minimum_absolute_task_macro_delta"]
    cross = metrics_by_split["task_loto"]["tfidf_pairwise_lr"]
    run = metrics_by_split["run_grouped_5fold"]["tfidf_pairwise_lr"]
    cross_pass = (
        cross["task_macro_delta"] >= threshold
        and cross["task_clustered_delta"]["ci95"][0] > 0
        and cross["task_sign"]["one_sided_p"] < gate["maximum_one_sided_task_sign_p"]
    )
    run_pass = (
        run["task_macro_delta"] >= threshold
        and run["task_clustered_delta"]["ci95"][0] > 0
        and run["run_clustered_micro_delta"]["ci95"][0] > 0
    )
    verdict = "GO_CROSS_TASK" if cross_pass else "GO_RUN_ONLY" if run_pass else "NO_NARROW_POSITIVE"

    predictions_path = output / "predictions.csv"
    with predictions_path.open("x", newline="", encoding="utf-8") as handle:
        fields = [
            "split", "fold", "arm", "group_id", "task", "run_id_sha256", "source_size",
            "selected_candidate_sha256", "hit", "winner_rank",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(prediction_rows)
    per_task_path = output / "per_task.csv"
    with per_task_path.open("x", newline="", encoding="utf-8") as handle:
        fields = [
            "split", "arm", "task", "groups", "runs", "accuracy",
            "uniform_expected_accuracy", "delta", "winner_mrr",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(per_task_rows)
    receipts_path = output / "fold_receipts.json"
    write_json(receipts_path, {"split_assignment": split_receipt, "model_fits": model_receipts})
    summary = {
        "protocol": PROTOCOL_NAME,
        "status": "SOURCE_CHOICE_OOF_TFIDF_COMPLETE",
        "verdict": verdict,
        "input_sha256": {
            "train_model": protocol["inputs"]["train_model"]["sha256"],
            "cluster_manifest": protocol["inputs"]["cluster_manifest"]["sha256"],
        },
        "census": census,
        "models_fitted": len(model_receipts),
        "metrics": metrics_by_split,
        "gate": gate,
        "gate_checks": {"cross_task_pass": cross_pass, "run_only_pass": run_pass},
        "versions": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "sklearn": sklearn.__version__,
        },
        "scope": protocol["scope"],
        "frozen_or_extension_model_read": False,
        "frozen_or_extension_label_vault_read": False,
        "outputs": {
            "predictions.csv": sha256_file(predictions_path),
            "per_task.csv": sha256_file(per_task_path),
            "fold_receipts.json": sha256_file(receipts_path),
        },
    }
    summary_path = output / "summary.json"
    write_json(summary_path, summary)
    manifest = {
        path.name: sha256_file(path)
        for path in (predictions_path, per_task_path, receipts_path, summary_path)
    }
    write_json(output / "sha256_manifest.json", manifest)
    return summary


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--protocol", required=True)
    value.add_argument("--train-model", required=True)
    value.add_argument("--cluster-manifest", required=True)
    value.add_argument("--output", required=True)
    return value


def main() -> int:
    arguments = parser().parse_args()
    try:
        result = analyze(
            Path(arguments.protocol).resolve(),
            Path(arguments.train_model).resolve(),
            Path(arguments.cluster_manifest).resolve(),
            Path(arguments.output).resolve(),
        )
        print(f"{result['status']} verdict={result['verdict']} fits={result['models_fitted']}")
        return 0
    except OOFError as exc:
        print(f"SOURCE_CHOICE_OOF_TFIDF_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
