#!/usr/bin/env python3
"""Run-clean OOF rank head over frozen endpoint embeddings.

This discovery program has no frozen/test-pair argument by design.  It fits one
pre-registered linear head on run-grouped training folds and emits enough
per-pair evidence for an independent verifier to reconstruct every gate.
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
import random
import subprocess
import sys
import time
import zlib
from pathlib import Path
from typing import Any, Sequence

import numpy as np


SEED = 887
N_SPLITS = 5
BOOTSTRAP_REPS = 10_000
EXPECTED_PAIRS = 4_263
EXPECTED_TASKS = 23
EXPECTED_DIMENSION = 1_792
EPSILON = 1e-12


class IntegrityError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def git_commit(repo_root: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"], text=True
    ).strip()


def load_manifest(
    path: Path, summary_path: Path
) -> tuple[list[dict[str, Any]], dict[str, Any], str]:
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    rows = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line]
    if not rows:
        raise IntegrityError("empty manifest")
    ids = [str(row["card_id"]) for row in rows]
    if ids != sorted(ids) or len(ids) != len(set(ids)):
        raise IntegrityError("manifest IDs are not sorted and unique")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if summary.get("status") != "MANIFEST_COMPLETE":
        raise IntegrityError("manifest summary is not complete")
    if summary.get("outputs", {}).get("manifest_sha256") != digest:
        raise IntegrityError("manifest summary hash mismatch")
    if int(summary.get("endpoints", -1)) != len(rows):
        raise IntegrityError("manifest endpoint count mismatch")
    return rows, summary, digest


def load_features(
    feature_root: Path,
    manifest: Sequence[dict[str, Any]],
    manifest_sha: str,
    commit: str,
    expected_model_sha: str,
) -> tuple[np.ndarray, dict[str, int], dict[str, Any]]:
    expected = {str(row["card_id"]): row for row in manifest}
    features: dict[str, np.ndarray] = {}
    token_counts: dict[str, int] = {}
    worker_sources: set[str] = set()
    model_hashes: set[str] = set()
    cards_hashes: set[str] = set()
    attention_backends: set[str] = set()
    shard_audit: list[dict[str, Any]] = []

    for shard in range(4):
        shard_dir = feature_root / f"shard_{shard}"
        metadata_path = shard_dir / "metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        config = metadata.get("config") or {}
        feature = metadata.get("feature") or {}
        inputs = metadata.get("inputs") or {}
        if metadata.get("status") != "COMPLETE":
            raise IntegrityError(f"shard {shard} is not COMPLETE")
        if metadata.get("protocol") != "frozen_embed_v11_discovery_v1":
            raise IntegrityError(f"shard {shard} protocol mismatch")
        if metadata.get("git_commit") != commit:
            raise IntegrityError(f"shard {shard} commit mismatch")
        expected_config = {
            "shard": shard,
            "num_shards": 4,
            "max_len": 8192,
            "head_fraction": 0.25,
            "batch_size": 2,
            "chunk_size": 32,
            "limit_cards": 0,
        }
        if config != expected_config:
            raise IntegrityError(f"shard {shard} config mismatch: {config}")
        if inputs.get("manifest_sha256") != manifest_sha:
            raise IntegrityError(f"shard {shard} manifest hash mismatch")
        if inputs.get("model_weights_sha256") != expected_model_sha:
            raise IntegrityError(f"shard {shard} model hash mismatch")
        if feature.get("definition") != "concat(masked_mean_last_hidden)":
            raise IntegrityError(f"shard {shard} feature definition mismatch")
        if feature.get("dtype") != "float16" or not feature.get("task_prefix"):
            raise IntegrityError(f"shard {shard} feature metadata mismatch")
        if int(feature.get("dimension", -1)) != EXPECTED_DIMENSION:
            raise IntegrityError(f"shard {shard} feature dimension mismatch")
        assigned = sorted(
            str(row["card_id"]) for row in manifest if int(row["shard"]) == shard
        )
        if int(metadata.get("completed_cards", -1)) != len(assigned):
            raise IntegrityError(f"shard {shard} completed-card count mismatch")

        chunk_records = metadata.get("chunks") or []
        recorded_files = [str(record["file"]) for record in chunk_records]
        actual_files = sorted(path.name for path in shard_dir.glob("chunk_*.npz"))
        if recorded_files != actual_files or len(recorded_files) != len(set(recorded_files)):
            raise IntegrityError(f"shard {shard} chunk inventory mismatch")
        seen_shard: list[str] = []
        for record in chunk_records:
            chunk_path = shard_dir / str(record["file"])
            if sha256(chunk_path) != str(record["sha256"]):
                raise IntegrityError(f"chunk hash mismatch: {chunk_path}")
            with np.load(chunk_path, allow_pickle=False) as data:
                ids = [str(value) for value in data["card_ids"].tolist()]
                matrix = np.asarray(data["features"], dtype=np.float32)
                tokens = np.asarray(data["token_counts"], dtype=np.int64)
                chars = np.asarray(data["code_chars"], dtype=np.int64)
            if matrix.shape != (len(ids), EXPECTED_DIMENSION):
                raise IntegrityError(f"chunk shape mismatch: {chunk_path}")
            if tokens.shape != (len(ids),) or chars.shape != (len(ids),):
                raise IntegrityError(f"chunk metadata shape mismatch: {chunk_path}")
            if not np.isfinite(matrix).all() or np.any(tokens <= 0) or np.any(tokens > 8192):
                raise IntegrityError(f"invalid feature/token values: {chunk_path}")
            for index, card_id in enumerate(ids):
                if card_id not in expected or card_id in features:
                    raise IntegrityError(f"unexpected or duplicate feature ID: {card_id}")
                if int(chars[index]) != int(expected[card_id]["code_chars"]):
                    raise IntegrityError(f"code length mismatch: {card_id}")
                features[card_id] = matrix[index]
                token_counts[card_id] = int(tokens[index])
            seen_shard.extend(ids)
        if seen_shard != assigned:
            raise IntegrityError(f"shard {shard} IDs are not a contiguous manifest projection")
        worker_sources.add(str(metadata.get("source_sha256")))
        model_hashes.add(str(inputs.get("model_weights_sha256")))
        cards_hashes.add(str(inputs.get("cards_sha256")))
        attention_backends.add(str(metadata.get("software", {}).get("attention_backend")))
        shard_audit.append(
            {
                "shard": shard,
                "cards": len(assigned),
                "chunks": len(chunk_records),
                "elapsed_s": float(metadata.get("elapsed_s", math.nan)),
                "metadata_sha256": sha256(metadata_path),
            }
        )

    if set(features) != set(expected):
        raise IntegrityError("feature coverage is not exactly the manifest endpoint set")
    if len(worker_sources) != 1 or len(model_hashes) != 1 or len(cards_hashes) != 1:
        raise IntegrityError("feature shards disagree on source/model/cards hashes")
    ordered_ids = [str(row["card_id"]) for row in manifest]
    matrix = np.vstack([features[card_id] for card_id in ordered_ids]).astype(np.float32)
    half = matrix.shape[1] // 2
    for start, end in ((0, half), (half, matrix.shape[1])):
        norms = np.linalg.norm(matrix[:, start:end], axis=1, keepdims=True)
        if not np.isfinite(norms).all() or np.any(norms <= 0):
            raise IntegrityError("zero or non-finite embedding-half norm")
        matrix[:, start:end] /= norms
    if not np.isfinite(matrix).all():
        raise IntegrityError("non-finite normalized feature matrix")
    position = {card_id: index for index, card_id in enumerate(ordered_ids)}
    audit = {
        "endpoints": len(ordered_ids),
        "dimension": int(matrix.shape[1]),
        "worker_source_sha256": next(iter(worker_sources)),
        "model_weights_sha256": next(iter(model_hashes)),
        "cards_sha256": next(iter(cards_hashes)),
        "attention_backends": sorted(attention_backends),
        "token_count": {
            "minimum": min(token_counts.values()),
            "median": float(np.median(list(token_counts.values()))),
            "maximum": max(token_counts.values()),
            "truncated_share": sum(value == 8192 for value in token_counts.values())
            / len(token_counts),
        },
        "shards": shard_audit,
    }
    return matrix, position, audit


def load_pairs(
    path: Path,
    manifest: Sequence[dict[str, Any]],
    run_map_path: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any], str]:
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    rows = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line]
    if not rows:
        raise IntegrityError("empty training-pair file")
    metadata = {str(row["card_id"]): row for row in manifest}
    run_map = json.loads(run_map_path.read_text(encoding="utf-8"))
    required = {
        "better",
        "worse",
        "parent",
        "task",
        "run_id",
        "budget",
        "gap_raw",
        "intask_split",
    }
    oriented: set[tuple[str, str]] = set()
    unordered: set[tuple[str, str]] = set()
    clean: list[dict[str, Any]] = []
    for line_number, source in enumerate(rows, 1):
        missing = required - set(source)
        if missing:
            raise IntegrityError(f"pair line {line_number} missing {sorted(missing)}")
        if str(source["intask_split"]) != "train" or int(source["budget"]) != 0:
            raise IntegrityError(f"pair line {line_number} is not train/budget-zero")
        better, worse = str(source["better"]), str(source["worse"])
        if better == worse or (better, worse) in oriented:
            raise IntegrityError(f"duplicate/degenerate pair at line {line_number}")
        canonical = tuple(sorted((better, worse)))
        if canonical in unordered:
            raise IntegrityError(f"reverse or duplicate unordered pair at line {line_number}")
        oriented.add((better, worse))
        unordered.add(canonical)
        if better not in metadata or worse not in metadata:
            raise IntegrityError(f"pair endpoint absent from manifest at line {line_number}")
        task, run = str(source["task"]), str(source["run_id"])
        if any(
            str(metadata[card_id]["task"]) != task
            or str(metadata[card_id]["run_id"]) != run
            or str(run_map.get(card_id)) != run
            for card_id in (better, worse)
        ):
            raise IntegrityError(f"task/run context mismatch at line {line_number}")
        gap = float(source["gap_raw"])
        if not math.isfinite(gap) or gap <= 0.0:
            raise IntegrityError(f"non-positive/non-finite gap at line {line_number}")
        clean.append(
            {
                "row_index": line_number - 1,
                "task": task,
                "run": run,
                "parent": str(source["parent"]),
                "better": better,
                "worse": worse,
                "gap_raw": gap,
            }
        )
    endpoint_set = {
        str(row[key]) for row in clean for key in ("better", "worse")
    }
    if endpoint_set != set(metadata):
        raise IntegrityError("pair endpoint set does not exactly equal manifest")
    task_counts = collections.Counter(row["task"] for row in clean)
    run_counts = collections.Counter(row["run"] for row in clean)
    parent_counts = collections.Counter(row["parent"] for row in clean)
    audit = {
        "pairs": len(clean),
        "endpoints": len(endpoint_set),
        "runs": len(run_counts),
        "tasks": len(task_counts),
        "parents": len(parent_counts),
        "dominant_task": task_counts.most_common(1)[0][0],
        "dominant_task_share": task_counts.most_common(1)[0][1] / len(clean),
        "per_task_pairs": dict(sorted(task_counts.items())),
        "duplicate_or_reverse_pairs": 0,
        "run_map_sha256": sha256(run_map_path),
    }
    return clean, audit, digest


def tie_hit(margin: float) -> float:
    if margin > EPSILON:
        return 1.0
    if margin < -EPSILON:
        return 0.0
    return 0.5


def deterministic_random_score(card_id: str) -> float:
    return (zlib.crc32(f"{SEED}:{card_id}".encode("utf-8")) & 0xFFFFFFFF) / 2**32


def cluster_summary(
    rows: Sequence[dict[str, Any]],
    values: Sequence[float],
    key: str,
    seed: int,
) -> tuple[float, list[float], dict[str, float]]:
    grouped: dict[str, list[float]] = collections.defaultdict(list)
    for row, value in zip(rows, values):
        grouped[str(row[key])].append(float(value))
    means = {name: sum(items) / len(items) for name, items in sorted(grouped.items())}
    population = list(means.values())
    rng = random.Random(seed)
    draws = [
        sum(rng.choice(population) for _ in population) / len(population)
        for _ in range(BOOTSTRAP_REPS)
    ]
    draws.sort()
    interval = [draws[int(0.025 * BOOTSTRAP_REPS)], draws[int(0.975 * BOOTSTRAP_REPS)]]
    return sum(population) / len(population), interval, means


def summarize_values(
    rows: Sequence[dict[str, Any]], values: Sequence[float], seed_offset: int
) -> dict[str, Any]:
    run_macro, run_ci, per_run = cluster_summary(rows, values, "run", SEED + seed_offset)
    task_macro, task_ci, per_task = cluster_summary(
        rows, values, "task", SEED + seed_offset + 1
    )
    return {
        "overall": sum(values) / len(values),
        "run_macro": run_macro,
        "run_macro_ci95": run_ci,
        "task_macro": task_macro,
        "task_macro_ci95": task_ci,
        "per_run": per_run,
        "per_task": per_task,
    }


def parent_top1(
    rows: Sequence[dict[str, Any]], scores: dict[str, float]
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in rows:
        grouped[str(row["parent"])].append(row)
    records: dict[str, dict[str, Any]] = {}
    incomplete = 0
    for parent, parent_rows in sorted(grouped.items()):
        candidates = {
            str(row[key]) for row in parent_rows for key in ("better", "worse")
        }
        if len(parent_rows) != len(candidates) * (len(candidates) - 1) // 2:
            incomplete += 1
            continue
        losses = collections.Counter({candidate: 0 for candidate in candidates})
        for row in parent_rows:
            losses[str(row["worse"])] += 1
        true_top = {candidate for candidate, value in losses.items() if value == min(losses.values())}
        maximum = max(scores[candidate] for candidate in candidates)
        predicted = {
            candidate for candidate in candidates if abs(scores[candidate] - maximum) <= EPSILON
        }
        records[parent] = {
            "value": len(predicted & true_top) / len(predicted),
            "run": parent_rows[0]["run"],
            "task": parent_rows[0]["task"],
            "candidates": len(candidates),
        }
    proxy_rows = [{"run": item["run"], "task": item["task"]} for item in records.values()]
    values = [float(item["value"]) for item in records.values()]
    summary = summarize_values(proxy_rows, values, 40)
    summary.update(
        {
            "complete_parents": len(records),
            "incomplete_parents": incomplete,
            "complete_share": len(records) / len(grouped),
        }
    )
    return summary, records


def parent_equal_gap_utility(
    rows: Sequence[dict[str, Any]], hits: Sequence[float]
) -> dict[str, Any]:
    grouped: dict[str, list[tuple[dict[str, Any], float]]] = collections.defaultdict(list)
    for row, hit in zip(rows, hits):
        grouped[str(row["parent"])].append((row, float(hit)))
    proxy_rows: list[dict[str, Any]] = []
    values: list[float] = []
    for items in grouped.values():
        denominator = sum(float(row["gap_raw"]) for row, _ in items)
        value = sum(float(row["gap_raw"]) * hit for row, hit in items) / denominator
        proxy_rows.append({"run": items[0][0]["run"], "task": items[0][0]["task"]})
        values.append(value)
    output = summarize_values(proxy_rows, values, 60)
    output["parents"] = len(values)
    output["definition"] = "mean_parent(sum(gap_raw*hit)/sum(gap_raw))"
    return output


def task_consistency(
    rows: Sequence[dict[str, Any]], hits: Sequence[float], minimum_pairs: int = 20
) -> dict[str, Any]:
    grouped: dict[str, list[float]] = collections.defaultdict(list)
    for row, hit in zip(rows, hits):
        grouped[str(row["task"])].append(float(hit))
    supported = {
        task: {"pairs": len(values), "accuracy": sum(values) / len(values)}
        for task, values in sorted(grouped.items())
        if len(values) >= minimum_pairs
    }
    nonchance = sum(item["accuracy"] >= 0.5 for item in supported.values())
    return {
        "minimum_pairs": minimum_pairs,
        "supported_tasks": len(supported),
        "nonchance_tasks": nonchance,
        "nonchance_share": nonchance / len(supported) if supported else 0.0,
        "details": supported,
    }


def write_predictions(
    path: Path,
    rows: Sequence[dict[str, Any]],
    fold_assignment: Sequence[int],
    scores: dict[str, float],
) -> tuple[list[float], list[float]]:
    fields = [
        "row_index",
        "task",
        "run",
        "parent",
        "better",
        "worse",
        "gap_raw",
        "fold",
        "better_score",
        "worse_score",
        "margin",
        "hit",
        "random_margin",
        "random_hit",
    ]
    hits: list[float] = []
    random_hits: list[float] = []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row, fold in zip(rows, fold_assignment):
            better_score = float(scores[str(row["better"])])
            worse_score = float(scores[str(row["worse"])])
            margin = better_score - worse_score
            hit = tie_hit(margin)
            random_margin = deterministic_random_score(str(row["better"])) - deterministic_random_score(
                str(row["worse"])
            )
            random_hit = tie_hit(random_margin)
            hits.append(hit)
            random_hits.append(random_hit)
            writer.writerow(
                {
                    **row,
                    "fold": fold,
                    "better_score": repr(better_score),
                    "worse_score": repr(worse_score),
                    "margin": repr(margin),
                    "hit": repr(hit),
                    "random_margin": repr(random_margin),
                    "random_hit": repr(random_hit),
                }
            )
    return hits, random_hits


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", required=True, type=Path)
    parser.add_argument("--run-map", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--manifest-summary", required=True, type=Path)
    parser.add_argument("--feature-root", required=True, type=Path)
    parser.add_argument("--model-sha256", required=True)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--expect-pairs-sha256")
    parser.add_argument("--expect-run-map-sha256")
    parser.add_argument("--expect-manifest-sha256")
    parser.add_argument("--expect-commit")
    parser.add_argument("--wall-cap-s", type=float, default=900.0)
    return parser.parse_args()


def main() -> int:
    args = arguments()
    if args.out_dir.exists() and any(args.out_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite non-empty output: {args.out_dir}")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    commit = git_commit(args.repo_root)
    if args.expect_commit and commit != args.expect_commit:
        raise IntegrityError("git commit mismatch")
    manifest, manifest_summary, manifest_sha = load_manifest(
        args.manifest, args.manifest_summary
    )
    if args.expect_manifest_sha256 and manifest_sha != args.expect_manifest_sha256.lower():
        raise IntegrityError("manifest SHA256 mismatch")
    if args.expect_run_map_sha256 and sha256(args.run_map) != args.expect_run_map_sha256.lower():
        raise IntegrityError("run-map SHA256 mismatch")
    rows, pair_audit, pairs_sha = load_pairs(args.pairs, manifest, args.run_map)
    if args.expect_pairs_sha256 and pairs_sha != args.expect_pairs_sha256.lower():
        raise IntegrityError("training-pair SHA256 mismatch")
    matrix, position, feature_audit = load_features(
        args.feature_root,
        manifest,
        manifest_sha,
        commit,
        args.model_sha256.lower(),
    )

    import sklearn
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import GroupKFold

    groups = np.asarray([row["run"] for row in rows])
    fold_assignment = [-1] * len(rows)
    scores: dict[str, float] = {}
    folds: list[dict[str, Any]] = []
    converged = True
    splitter = GroupKFold(n_splits=N_SPLITS)
    for fold, (fit_indices, valid_indices) in enumerate(
        splitter.split(np.zeros(len(rows)), groups=groups)
    ):
        fit_rows = [rows[int(index)] for index in fit_indices]
        valid_rows = [rows[int(index)] for index in valid_indices]
        fit_runs = {row["run"] for row in fit_rows}
        valid_runs = {row["run"] for row in valid_rows}
        if fit_runs & valid_runs:
            raise IntegrityError(f"physical-run leakage in fold {fold}")
        fit_better = np.asarray([position[row["better"]] for row in fit_rows])
        fit_worse = np.asarray([position[row["worse"]] for row in fit_rows])
        differences = matrix[fit_better] - matrix[fit_worse]
        x_train = np.vstack((differences, -differences))
        y_train = np.concatenate(
            (np.ones(len(fit_rows), dtype=np.int8), np.zeros(len(fit_rows), dtype=np.int8))
        )
        per_parent = collections.Counter(row["parent"] for row in fit_rows)
        parents = len(per_parent)
        base_weight = np.asarray(
            [len(fit_rows) / (parents * per_parent[row["parent"]]) for row in fit_rows],
            dtype=np.float64,
        )
        sample_weight = np.concatenate((base_weight, base_weight))
        classifier = LogisticRegression(
            C=0.05,
            penalty="l2",
            solver="liblinear",
            fit_intercept=False,
            max_iter=2_000,
            tol=1e-6,
            random_state=SEED,
        )
        classifier.fit(x_train, y_train, sample_weight=sample_weight)
        n_iter = int(classifier.n_iter_[0])
        converged &= n_iter < 2_000
        valid_ids = sorted(
            {str(row[key]) for row in valid_rows for key in ("better", "worse")}
        )
        valid_matrix = matrix[[position[card_id] for card_id in valid_ids]]
        valid_scores = np.asarray(classifier.decision_function(valid_matrix)).reshape(-1)
        if not np.isfinite(valid_scores).all():
            raise IntegrityError(f"non-finite OOF scores in fold {fold}")
        for card_id, score in zip(valid_ids, valid_scores.tolist()):
            if card_id in scores:
                raise IntegrityError(f"endpoint received multiple OOF scores: {card_id}")
            scores[card_id] = float(score)
        for index in valid_indices:
            fold_assignment[int(index)] = fold
        folds.append(
            {
                "fold": fold,
                "fit_pairs": len(fit_rows),
                "valid_pairs": len(valid_rows),
                "fit_runs": len(fit_runs),
                "valid_runs": len(valid_runs),
                "valid_endpoints": len(valid_ids),
                "run_overlap": 0,
                "n_iter": n_iter,
                "sample_weight_mean": float(sample_weight.mean()),
            }
        )
    if any(fold < 0 for fold in fold_assignment) or set(scores) != set(position):
        raise IntegrityError("OOF coverage is incomplete")

    predictions_path = args.out_dir / "oof_predictions.csv"
    hits, random_hits = write_predictions(
        predictions_path, rows, fold_assignment, scores
    )
    primary = summarize_values(rows, hits, 10)
    random_control = summarize_values(rows, random_hits, 20)
    top1_summary, _ = parent_top1(rows, scores)
    gap_utility = parent_equal_gap_utility(rows, hits)
    consistency = task_consistency(rows, hits)
    runtime_s = time.monotonic() - started
    finite = all(math.isfinite(value) for value in scores.values())
    checks = {
        "pairs_eq_4263": pair_audit["pairs"] == EXPECTED_PAIRS,
        "runs_ge_300": pair_audit["runs"] >= 300,
        "tasks_eq_23": pair_audit["tasks"] == EXPECTED_TASKS,
        "dominant_task_le_025": pair_audit["dominant_task_share"] <= 0.25,
        "feature_coverage_exact": feature_audit["endpoints"] == pair_audit["endpoints"],
        "fold_run_overlap_eq_0": all(item["run_overlap"] == 0 for item in folds),
        "pair_accuracy_ge_054": primary["overall"] >= 0.54,
        "run_macro_ci_low_gt_050": primary["run_macro_ci95"][0] > 0.50,
        "task_macro_ci_low_gt_050": primary["task_macro_ci95"][0] > 0.50,
        "complete_parent_top1_ge_050": top1_summary["overall"] >= 0.50,
        "complete_parent_share_ge_095": top1_summary["complete_share"] >= 0.95,
        "parent_equal_gap_utility_ge_055": gap_utility["overall"] >= 0.55,
        "supported_tasks_ge_15": consistency["supported_tasks"] >= 15,
        "task_nonchance_share_ge_060": consistency["nonchance_share"] >= 0.60,
        "random_pair_accuracy_in_047_053": 0.47 <= random_control["overall"] <= 0.53,
        "oracle_pair_accuracy_eq_1": 1.0 == 1.0,
        "finite": finite,
        "converged": converged,
        "within_wall_cap": runtime_s <= args.wall_cap_s,
    }
    checks["all"] = all(checks.values())
    result = {
        "status": "DISCOVERY_UNLOCK_RECOMMENDED" if checks["all"] else "DISCOVERY_NO_UNLOCK",
        "frozen_read": False,
        "protocol": "frozen_embed_v11_discovery_v1",
        "git_commit": commit,
        "source_sha256": sha256(Path(__file__)),
        "runtime_s": runtime_s,
        "software": {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
            "sklearn": sklearn.__version__,
        },
        "configuration": {
            "seed": SEED,
            "folds": N_SPLITS,
            "bootstrap_reps": BOOTSTRAP_REPS,
            "wall_cap_s": args.wall_cap_s,
            "feature_normalization": "independent_L2_for_mean_and_last_halves",
            "rank_head": {
                "type": "LogisticRegression",
                "C": 0.05,
                "penalty": "l2",
                "solver": "liblinear",
                "fit_intercept": False,
                "max_iter": 2000,
                "tol": 1e-6,
                "training_design": "mirrored_pair_differences",
                "weighting": "equal_total_weight_per_parent_mean_weight_one",
            },
        },
        "inputs": {
            "pairs": str(args.pairs),
            "pairs_sha256": pairs_sha,
            "run_map": str(args.run_map),
            "run_map_sha256": sha256(args.run_map),
            "manifest": str(args.manifest),
            "manifest_sha256": manifest_sha,
            "manifest_summary": str(args.manifest_summary),
            "manifest_summary_sha256": sha256(args.manifest_summary),
            "feature_root": str(args.feature_root),
        },
        "manifest_summary": manifest_summary,
        "pair_audit": pair_audit,
        "feature_audit": feature_audit,
        "folds": folds,
        "primary_pair_accuracy": primary,
        "complete_parent_top1": top1_summary,
        "parent_equal_gap_utility": gap_utility,
        "task_consistency": consistency,
        "random_control": random_control,
        "oracle_pair_accuracy": 1.0,
        "discovery_gate": checks,
        "outputs": {
            "oof_predictions": str(predictions_path),
            "oof_predictions_sha256": sha256(predictions_path),
        },
    }
    atomic_json(args.out_dir / "summary.json", result)
    print(
        result["status"],
        f"pair_accuracy={primary['overall']:.6f}",
        f"run_ci_low={primary['run_macro_ci95'][0]:.6f}",
        f"task_ci_low={primary['task_macro_ci95'][0]:.6f}",
        f"top1={top1_summary['overall']:.6f}",
        f"gap_utility={gap_utility['overall']:.6f}",
        f"runtime_s={runtime_s:.3f}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
