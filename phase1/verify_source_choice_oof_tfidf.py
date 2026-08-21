#!/usr/bin/env python3
"""Independent split/control/metric verifier for source-choice OOF TF-IDF results.

This module deliberately does not import the producer. Producer A/B independently refit all 28 models;
this verifier rebuilds every non-model transformation and the final statistical verdict from source bytes.
"""

from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import math
import os
import re
import sys
from pathlib import Path
from typing import Any

import numpy as np


PROTOCOL = "source-choice-oof-tfidf-v1"
MODEL_SCHEMA = "source-choice-decision-group-v2"
CLUSTER_SCHEMA = "source-choice-cluster-manifest-v1"
ARMS = (
    "min_candidate_sha", "max_step_then_min_sha", "max_code_length_then_min_sha",
    "tfidf_pairwise_lr", "winner_oracle",
)
SPLITS = ("task_loto", "run_grouped_5fold")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


class VerificationError(RuntimeError):
    pass


def need(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def compact(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            value.update(chunk)
    return value.hexdigest()


def object_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    need(isinstance(value, dict), f"non-object JSON: {path.name}")
    return value


def rows_jsonl(path: Path) -> list[dict[str, Any]]:
    values = []
    with path.open("rb") as handle:
        for number, line in enumerate(handle, 1):
            need(line.endswith(b"\n"), f"unterminated JSONL: {path.name}:{number}")
            value = json.loads(line)
            need(isinstance(value, dict) and compact(value) + b"\n" == line, "non-canonical JSONL")
            values.append(value)
    return values


def valid_hash(value: Any) -> str:
    need(isinstance(value, str) and HEX64.fullmatch(value) is not None, "invalid SHA")
    return value


def tie(seed: int, *values: Any) -> str:
    return hashlib.sha256((str(seed) + "|" + "|".join(map(str, values))).encode()).hexdigest()


def run_assignment(
    groups: dict[str, dict[str, Any]],
    clusters: dict[str, dict[str, Any]],
    folds: int,
    seed: int,
) -> dict[str, int]:
    group_ids_by_run: dict[str, list[str]] = collections.defaultdict(list)
    task_by_run: dict[str, str] = {}
    for group_id, group in groups.items():
        run = clusters[group_id]["run_id_sha256"]
        group_ids_by_run[run].append(group_id)
        old = task_by_run.setdefault(run, group["task"])
        need(old == group["task"], "run spans tasks")
    runs_by_task: dict[str, list[str]] = collections.defaultdict(list)
    for run, task in task_by_run.items():
        runs_by_task[task].append(run)
    loads_all = [0] * folds
    by_run: dict[str, int] = {}
    for task in sorted(runs_by_task):
        loads_task = [0] * folds
        ordered = sorted(
            runs_by_task[task], key=lambda run: (-len(group_ids_by_run[run]), tie(seed, task, run))
        )
        for run in ordered:
            fold = min(
                range(folds),
                key=lambda item: (loads_task[item], loads_all[item], tie(seed, task, run, item)),
            )
            by_run[run] = fold
            size = len(group_ids_by_run[run])
            loads_task[fold] += size
            loads_all[fold] += size
    return {group_id: by_run[clusters[group_id]["run_id_sha256"]] for group_id in groups}


def control_rank(group: dict[str, Any], arm: str) -> list[str]:
    candidates = group["candidates"]
    if arm == "min_candidate_sha":
        return sorted(item["candidate_id_sha256"] for item in candidates)
    if arm == "max_step_then_min_sha":
        ordered = sorted(candidates, key=lambda item: (-item["step"], item["candidate_id_sha256"]))
        return [item["candidate_id_sha256"] for item in ordered]
    if arm == "max_code_length_then_min_sha":
        ordered = sorted(candidates, key=lambda item: (-len(item["code"]), item["candidate_id_sha256"]))
        return [item["candidate_id_sha256"] for item in ordered]
    if arm == "winner_oracle":
        winner = group["winner_candidate_sha256"]
        return [winner] + sorted(
            item["candidate_id_sha256"] for item in candidates if item["candidate_id_sha256"] != winner
        )
    raise VerificationError("unknown control")


def sign(values: list[float]) -> dict[str, Any]:
    positive = sum(value > 0 for value in values)
    negative = sum(value < 0 for value in values)
    zero = sum(value == 0 for value in values)
    n = positive + negative
    p = 1.0 if n == 0 else sum(math.comb(n, item) for item in range(positive, n + 1)) / 2 ** n
    return {"positive": positive, "negative": negative, "zero": zero, "one_sided_p": p}


def task_ci(values: dict[str, list[float]], reps: int, seed: int) -> dict[str, Any]:
    points = np.asarray([np.mean(values[key]) for key in sorted(values)], dtype=np.float64)
    rng = np.random.default_rng(seed)
    sampled = rng.integers(0, len(points), size=(reps, len(points)))
    estimates = np.mean(points[sampled], axis=1)
    low, high = np.quantile(estimates, [0.025, 0.975], method="linear")
    return {
        "point": float(np.mean(points)), "ci95": [float(low), float(high)],
        "clusters": len(points), "replicates": reps, "seed": seed,
    }


def run_ci(values: dict[str, list[float]], reps: int, seed: int) -> dict[str, Any]:
    arrays = [np.asarray(values[key], dtype=np.float64) for key in sorted(values)]
    rng = np.random.default_rng(seed)
    estimates = np.empty(reps, dtype=np.float64)
    for index in range(reps):
        chosen = rng.integers(0, len(arrays), size=len(arrays))
        estimates[index] = (
            sum(float(np.sum(arrays[item])) for item in chosen)
            / sum(len(arrays[item]) for item in chosen)
        )
    low, high = np.quantile(estimates, [0.025, 0.975], method="linear")
    return {
        "point": float(np.mean(np.concatenate(arrays))), "ci95": [float(low), float(high)],
        "clusters": len(arrays), "replicates": reps, "seed": seed,
    }


def metrics(rows: list[dict[str, Any]], config: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    task_delta: dict[str, list[float]] = collections.defaultdict(list)
    run_delta: dict[str, list[float]] = collections.defaultdict(list)
    task_hit: dict[str, list[float]] = collections.defaultdict(list)
    task_uniform: dict[str, list[float]] = collections.defaultdict(list)
    task_mrr: dict[str, list[float]] = collections.defaultdict(list)
    run_hit: dict[str, list[float]] = collections.defaultdict(list)
    arity: dict[int, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in rows:
        expected = 1 / row["source_size"]
        delta = row["hit"] - expected
        task_delta[row["task"]].append(delta)
        run_delta[row["run_id_sha256"]].append(delta)
        task_hit[row["task"]].append(row["hit"])
        task_uniform[row["task"]].append(expected)
        task_mrr[row["task"]].append(1 / row["winner_rank"])
        run_hit[row["run_id_sha256"]].append(row["hit"])
        arity[row["source_size"]].append(row)
    primary = task_ci(task_delta, config["bootstrap_replicates"], config["task_bootstrap_seed"])
    run_cluster = run_ci(run_delta, config["bootstrap_replicates"], config["run_bootstrap_seed"])
    per_task = []
    for task in sorted(task_hit):
        per_task.append({
            "task": task, "groups": len(task_hit[task]),
            "runs": len({row["run_id_sha256"] for row in rows if row["task"] == task}),
            "accuracy": float(np.mean(task_hit[task])),
            "uniform_expected_accuracy": float(np.mean(task_uniform[task])),
            "delta": float(np.mean(task_delta[task])),
            "winner_mrr": float(np.mean(task_mrr[task])),
        })
    by_size = {}
    for size, selected in sorted(arity.items()):
        by_size[str(size)] = {
            "groups": len(selected),
            "accuracy": float(np.mean([row["hit"] for row in selected])),
            "uniform_expected_accuracy": 1 / size,
            "delta": float(np.mean([row["hit"] - 1 / size for row in selected])),
            "winner_mrr": float(np.mean([1 / row["winner_rank"] for row in selected])),
        }
    return {
        "groups": len(rows), "tasks": len(task_hit), "runs": len(run_hit),
        "micro_accuracy": float(np.mean([row["hit"] for row in rows])),
        "micro_uniform_expected_accuracy": float(np.mean([1 / row["source_size"] for row in rows])),
        "micro_delta": float(np.mean([row["hit"] - 1 / row["source_size"] for row in rows])),
        "task_macro_accuracy": float(np.mean([np.mean(value) for value in task_hit.values()])),
        "task_macro_uniform_expected_accuracy": float(np.mean([np.mean(value) for value in task_uniform.values()])),
        "task_macro_delta": primary["point"], "task_clustered_delta": primary,
        "run_macro_accuracy": float(np.mean([np.mean(value) for value in run_hit.values()])),
        "run_clustered_micro_delta": run_cluster,
        "task_sign": sign([row["delta"] for row in per_task]),
        "winner_mrr": float(np.mean([1 / row["winner_rank"] for row in rows])),
        "source_size": by_size,
    }, per_task


def close(left: Any, right: Any, where: str) -> None:
    if isinstance(left, dict) and isinstance(right, dict):
        need(set(left) == set(right), f"key mismatch: {where}")
        for key in left:
            close(left[key], right[key], f"{where}.{key}")
    elif isinstance(left, list) and isinstance(right, list):
        need(len(left) == len(right), f"length mismatch: {where}")
        for index, (a, b) in enumerate(zip(left, right)):
            close(a, b, f"{where}[{index}]")
    elif isinstance(left, float) or isinstance(right, float):
        need(math.isclose(float(left), float(right), rel_tol=0, abs_tol=1e-12), f"float mismatch: {where}")
    else:
        need(left == right, f"value mismatch: {where}")


def verify(protocol_path: Path, train_path: Path, cluster_path: Path, result: Path) -> dict[str, Any]:
    protocol = object_json(protocol_path)
    need(protocol.get("protocol") == PROTOCOL, "protocol differs")
    for key, path in (("train_model", train_path), ("cluster_manifest", cluster_path)):
        receipt = protocol["inputs"][key]
        need(path.is_file() and path.stat().st_size == receipt["bytes"] and digest(path) == receipt["sha256"], "input binding")
    train_rows = rows_jsonl(train_path)
    cluster_rows = rows_jsonl(cluster_path)
    clusters = {row["group_id"]: row for row in cluster_rows if row.get("role") == "train"}
    need(len(clusters) == len(train_rows), "train cluster coverage")
    groups: dict[str, dict[str, Any]] = {}
    all_candidates = set()
    for row in train_rows:
        need(row.get("schema_version") == MODEL_SCHEMA, "model schema")
        group_id = valid_hash(row.get("group_id"))
        need(group_id not in groups and group_id in clusters, "group closure")
        cluster = clusters[group_id]
        need(row["task"] == cluster["task"] and row["source_size"] == cluster["source_size"], "cluster mismatch")
        ids = [valid_hash(item["candidate_id_sha256"]) for item in row["candidates"]]
        need(ids == sorted(ids) and not (set(ids) & all_candidates), "candidate closure")
        all_candidates.update(ids)
        need(row["winner_candidate_sha256"] in set(ids), "winner closure")
        groups[group_id] = row

    task_map = {group_id: row["task"] for group_id, row in groups.items()}
    secondary = protocol["splits"]["secondary"]
    run_map = run_assignment(groups, clusters, secondary["folds"], secondary["assignment_seed"])
    assignments = {"task_loto": task_map, "run_grouped_5fold": run_map}

    manifest = object_json(result / "sha256_manifest.json")
    expected_files = {"predictions.csv", "per_task.csv", "fold_receipts.json", "summary.json"}
    need(set(manifest) == expected_files, "result manifest names")
    for name, expected in manifest.items():
        need(digest(result / name) == expected, f"result hash: {name}")
    summary = object_json(result / "summary.json")
    need(summary.get("status") == "SOURCE_CHOICE_OOF_TFIDF_COMPLETE", "summary status")

    prediction_fields = {
        "split", "fold", "arm", "group_id", "task", "run_id_sha256", "source_size",
        "selected_candidate_sha256", "hit", "winner_rank",
    }
    predictions = []
    seen = set()
    with (result / "predictions.csv").open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        need(set(reader.fieldnames or []) == prediction_fields, "prediction fields")
        for raw in reader:
            split, arm, group_id = raw["split"], raw["arm"], raw["group_id"]
            need(split in SPLITS and arm in ARMS and group_id in groups, "prediction identity")
            key = split, arm, group_id
            need(key not in seen, "duplicate prediction")
            seen.add(key)
            group, cluster = groups[group_id], clusters[group_id]
            candidate_ids = {item["candidate_id_sha256"] for item in group["candidates"]}
            selected = raw["selected_candidate_sha256"]
            hit, rank = int(raw["hit"]), int(raw["winner_rank"])
            need(selected in candidate_ids and hit == int(selected == group["winner_candidate_sha256"]), "hit closure")
            need(1 <= rank <= group["source_size"], "rank range")
            need(raw["fold"] == str(assignments[split][group_id]), "fold assignment")
            need(raw["task"] == group["task"] and raw["run_id_sha256"] == cluster["run_id_sha256"], "metadata closure")
            need(int(raw["source_size"]) == group["source_size"], "source size closure")
            if arm != "tfidf_pairwise_lr":
                ranking = control_rank(group, arm)
                need(selected == ranking[0] and rank == ranking.index(group["winner_candidate_sha256"]) + 1, "control differs")
            predictions.append({
                "split": split, "arm": arm, "group_id": group_id, "task": group["task"],
                "run_id_sha256": cluster["run_id_sha256"], "source_size": group["source_size"],
                "hit": hit, "winner_rank": rank,
            })
    need(len(seen) == len(groups) * len(ARMS) * len(SPLITS), "prediction coverage")

    reconstructed: dict[str, dict[str, Any]] = {}
    per_task_expected = []
    for split in SPLITS:
        reconstructed[split] = {}
        for arm in ARMS:
            selected = [row for row in predictions if row["split"] == split and row["arm"] == arm]
            value, tasks = metrics(selected, protocol["metrics"])
            reconstructed[split][arm] = value
            per_task_expected.extend({"split": split, "arm": arm, **row} for row in tasks)
    close(summary["metrics"], reconstructed, "metrics")

    with (result / "per_task.csv").open(newline="", encoding="utf-8") as handle:
        observed = list(csv.DictReader(handle))
    need(len(observed) == len(per_task_expected), "per-task row count")
    for raw, expected in zip(observed, per_task_expected):
        for key in ("split", "arm", "task"):
            need(raw[key] == expected[key], "per-task identity")
        for key in ("groups", "runs"):
            need(int(raw[key]) == expected[key], "per-task integer")
        for key in ("accuracy", "uniform_expected_accuracy", "delta", "winner_mrr"):
            need(math.isclose(float(raw[key]), expected[key], rel_tol=0, abs_tol=1e-12), "per-task float")

    folds = object_json(result / "fold_receipts.json")["model_fits"]
    expected_fits = (
        protocol["splits"]["primary"]["folds"]
        + protocol["splits"]["secondary"]["folds"]
    )
    max_features = protocol["model"]["vectorizer"]["max_features"]
    max_iterations = protocol["model"]["logistic_regression"]["max_iter"]
    need(
        len(folds) == expected_fits and summary.get("models_fitted") == expected_fits,
        "model fit count",
    )
    need(all(item["run_overlap"] == 0 and item["candidate_overlap"] == 0 and item["code_hash_overlap"] == 0 for item in folds), "fold overlap")
    need(
        all(
            0 < item["vocabulary_size"] <= max_features
            and item["lr_iterations"] < max_iterations
            and HEX64.fullmatch(item["coefficient_sha256"])
            for item in folds
        ),
        "model receipt",
    )

    gate = protocol["gate"]
    cross = reconstructed["task_loto"]["tfidf_pairwise_lr"]
    run = reconstructed["run_grouped_5fold"]["tfidf_pairwise_lr"]
    threshold = gate["minimum_absolute_task_macro_delta"]
    cross_pass = cross["task_macro_delta"] >= threshold and cross["task_clustered_delta"]["ci95"][0] > 0 and cross["task_sign"]["one_sided_p"] < gate["maximum_one_sided_task_sign_p"]
    run_pass = run["task_macro_delta"] >= threshold and run["task_clustered_delta"]["ci95"][0] > 0 and run["run_clustered_micro_delta"]["ci95"][0] > 0
    verdict = "GO_CROSS_TASK" if cross_pass else "GO_RUN_ONLY" if run_pass else "NO_NARROW_POSITIVE"
    need(summary["verdict"] == verdict and summary["gate_checks"] == {"cross_task_pass": cross_pass, "run_only_pass": run_pass}, "verdict differs")
    need(all(reconstructed[split]["winner_oracle"]["micro_accuracy"] == 1 for split in SPLITS), "oracle fails")
    return {
        "protocol": "independent-source-choice-oof-tfidf-verifier-v1",
        "status": "INDEPENDENT_SOURCE_CHOICE_OOF_TFIDF_VERIFIED",
        "producer_imported": False,
        "model_refit_by_verifier": False,
        "producer_replicas_expected_for_model_refit": 2,
        "prediction_split_control_metric_and_gate_reconstructed": True,
        "groups": len(groups), "candidates": len(all_candidates),
        "prediction_rows": len(predictions), "model_fit_receipts": len(folds),
        "verdict": verdict, "summary_sha256": digest(result / "summary.json"),
        "frozen_or_extension_model_read": False,
        "frozen_or_extension_label_vault_read": False,
    }


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--protocol", required=True)
    value.add_argument("--train-model", required=True)
    value.add_argument("--cluster-manifest", required=True)
    value.add_argument("--result", required=True)
    value.add_argument("--output", required=True)
    return value


def main() -> int:
    args = parser().parse_args()
    try:
        result = verify(
            Path(args.protocol).resolve(), Path(args.train_model).resolve(),
            Path(args.cluster_manifest).resolve(), Path(args.result).resolve(),
        )
        output = Path(args.output).resolve()
        need(not output.exists(), "verification output exists")
        temporary = output.with_suffix(output.suffix + ".tmp")
        temporary.write_bytes(json.dumps(result, indent=2, sort_keys=True).encode() + b"\n")
        os.replace(temporary, output)
        print(result["status"])
        return 0
    except VerificationError as exc:
        print(f"SOURCE_CHOICE_OOF_VERIFICATION_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
