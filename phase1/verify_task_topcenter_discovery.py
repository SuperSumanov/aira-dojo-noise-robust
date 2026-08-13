#!/usr/bin/env python3
"""Independent verifier for task_topcenter_v11_discovery_v1.

This verifier does not import the producer.  It reopens the train-only pairs,
feature chunks, fold checkpoints, and prediction CSV; reconstructs endpoint
scores and all gates; and rejects any frozen/test-like pair path.
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
import zlib
from pathlib import Path
from typing import Any, Sequence

import numpy as np


SEED = 887
PROTOCOL = "task_topcenter_v11_discovery_v1"
BOOTSTRAP_REPS = 10_000
EPSILON = 1e-12
ARMS = (
    "fixed_global_allpair",
    "nested_global_allpair",
    "nested_global_topcenter",
    "nested_task_allpair",
    "nested_task_topcenter",
)
FAMILIES = ARMS[1:]
MAIN_ARM = "nested_task_topcenter"
METRIC_SEED_OFFSETS = {
    "fixed_global_allpair": 10,
    "nested_global_allpair": 200,
    "nested_global_topcenter": 220,
    "nested_task_allpair": 240,
    "nested_task_topcenter": 260,
}
LAMBDA_GLOBAL_GRID = (0.001, 0.005, 0.02)
LAMBDA_TASK_GRID = (0.02, 0.1, 0.5)


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
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def reject_forbidden_path(path: Path, label: str) -> None:
    found = [token for token in ("frozen", "test", "held") if token in path.name.lower()]
    if found:
        raise VerificationError(f"{label} path contains forbidden token(s): {found}")


def assert_close(actual: Any, expected: Any, label: str, tolerance: float = 1e-10) -> None:
    if isinstance(expected, (float, int)) and not isinstance(expected, bool):
        if not math.isclose(float(actual), float(expected), abs_tol=tolerance, rel_tol=tolerance):
            raise VerificationError(f"{label}: {actual} != {expected}")
    elif actual != expected:
        raise VerificationError(f"{label}: {actual!r} != {expected!r}")


def load_pairs(path: Path) -> list[dict[str, Any]]:
    reject_forbidden_path(path, "training pairs")
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line:
            continue
        raw = json.loads(line)
        if str(raw.get("intask_split")) != "train" or int(raw.get("budget", -1)) != 0:
            raise VerificationError(f"non-train pair at line {line_number}")
        better, worse = str(raw["better"]), str(raw["worse"])
        unordered = tuple(sorted((better, worse)))
        if better == worse or unordered in seen:
            raise VerificationError(f"duplicate/degenerate pair at line {line_number}")
        seen.add(unordered)
        gap = float(raw["gap_raw"])
        if not math.isfinite(gap) or gap < 0:
            raise VerificationError(f"invalid gap at line {line_number}")
        rows.append(
            {
                "better": better,
                "worse": worse,
                "parent": str(raw["parent"]),
                "task": str(raw["task"]),
                "run": str(raw["run_id"]),
                "gap_raw": gap,
            }
        )
    if len(rows) != 4_263:
        raise VerificationError("training pair count is not 4263")
    return rows


def load_manifest(path: Path, expected_sha: str) -> list[dict[str, Any]]:
    if sha256(path) != expected_sha.lower():
        raise VerificationError("manifest hash mismatch")
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]
    ids = [str(row["card_id"]) for row in rows]
    if len(rows) != 5_499 or ids != sorted(ids) or len(ids) != len(set(ids)):
        raise VerificationError("manifest identity/order mismatch")
    return rows


def load_features(
    root: Path,
    manifest: Sequence[dict[str, Any]],
    manifest_sha: str,
    extraction_commit: str,
    model_sha: str,
) -> tuple[np.ndarray, dict[str, int], dict[str, Any]]:
    expected = {str(row["card_id"]): row for row in manifest}
    features: dict[str, np.ndarray] = {}
    chunk_count = 0
    metadata_hashes: list[str] = []
    worker_hashes: set[str] = set()
    for shard in range(4):
        shard_dir = root / f"shard_{shard}"
        metadata_path = shard_dir / "metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if metadata.get("status") != "COMPLETE" or metadata.get("protocol") != "frozen_embed_v11_discovery_v1":
            raise VerificationError(f"feature shard {shard} status/protocol mismatch")
        if metadata.get("git_commit") != extraction_commit:
            raise VerificationError(f"feature shard {shard} extraction commit mismatch")
        inputs = metadata.get("inputs") or {}
        feature = metadata.get("feature") or {}
        if inputs.get("manifest_sha256") != manifest_sha or inputs.get("model_weights_sha256") != model_sha:
            raise VerificationError(f"feature shard {shard} input hash mismatch")
        if int(feature.get("dimension", -1)) != 1_792 or feature.get("dtype") != "float16":
            raise VerificationError(f"feature shard {shard} definition mismatch")
        assigned = sorted(
            str(row["card_id"]) for row in manifest if int(row["shard"]) == shard
        )
        records = metadata.get("chunks") or []
        actual = sorted(path.name for path in shard_dir.glob("chunk_*.npz"))
        if [str(record["file"]) for record in records] != actual:
            raise VerificationError(f"feature shard {shard} inventory mismatch")
        seen_shard: list[str] = []
        for record in records:
            path = shard_dir / str(record["file"])
            if sha256(path) != str(record["sha256"]):
                raise VerificationError(f"feature chunk hash mismatch: {path.name}")
            with np.load(path, allow_pickle=False) as data:
                ids = [str(value) for value in data["card_ids"].tolist()]
                matrix = np.asarray(data["features"], dtype=np.float32)
            if matrix.shape != (len(ids), 1_792) or not np.isfinite(matrix).all():
                raise VerificationError(f"feature chunk shape/value mismatch: {path.name}")
            for index, card_id in enumerate(ids):
                if card_id not in expected or card_id in features:
                    raise VerificationError(f"unexpected/duplicate feature ID: {card_id}")
                features[card_id] = matrix[index]
            seen_shard.extend(ids)
            chunk_count += 1
        if seen_shard != assigned:
            raise VerificationError(f"feature shard {shard} assignment mismatch")
        metadata_hashes.append(sha256(metadata_path))
        worker_hashes.add(str(metadata.get("source_sha256")))
    ordered = [str(row["card_id"]) for row in manifest]
    if set(features) != set(ordered):
        raise VerificationError("feature coverage mismatch")
    matrix = np.vstack([features[card_id] for card_id in ordered]).astype(np.float32)
    half = matrix.shape[1] // 2
    for start, end in ((0, half), (half, matrix.shape[1])):
        norms = np.linalg.norm(matrix[:, start:end], axis=1, keepdims=True)
        if np.any(norms <= 0) or not np.isfinite(norms).all():
            raise VerificationError("invalid feature norm")
        matrix[:, start:end] /= norms
    return matrix, {card_id: index for index, card_id in enumerate(ordered)}, {
        "endpoints": len(ordered),
        "dimension": int(matrix.shape[1]),
        "chunks": chunk_count,
        "metadata_sha256": metadata_hashes,
        "worker_sha256": sorted(worker_hashes),
    }


def load_baseline(
    path: Path, rows: Sequence[dict[str, Any]], expected_sha: str
) -> tuple[list[int], dict[str, float]]:
    reject_forbidden_path(path, "baseline OOF")
    if sha256(path) != expected_sha.lower():
        raise VerificationError("baseline OOF hash mismatch")
    with path.open("r", encoding="utf-8", newline="") as handle:
        emitted = list(csv.DictReader(handle))
    if len(emitted) != len(rows):
        raise VerificationError("baseline row count mismatch")
    folds: list[int] = []
    run_fold: dict[str, int] = {}
    scores: dict[str, float] = {}
    for index, (row, output) in enumerate(zip(rows, emitted)):
        if int(output["row_index"]) != index:
            raise VerificationError("baseline row-order mismatch")
        for key in ("task", "run", "parent", "better", "worse"):
            if str(output[key]) != str(row[key]):
                raise VerificationError(f"baseline {key} mismatch at {index}")
        fold = int(output["fold"])
        previous = run_fold.setdefault(str(row["run"]), fold)
        if previous != fold:
            raise VerificationError("baseline physical run spans folds")
        folds.append(fold)
        for endpoint_key, score_key in (("better", "better_score"), ("worse", "worse_score")):
            card_id, value = str(row[endpoint_key]), float(output[score_key])
            if card_id in scores:
                assert_close(scores[card_id], value, f"baseline score {card_id}", 1e-12)
            scores[card_id] = value
    if set(folds) != set(range(5)) or len(run_fold) != 333:
        raise VerificationError("baseline fold support mismatch")
    return folds, scores


def load_predictions(
    path: Path, rows: Sequence[dict[str, Any]], folds: Sequence[int]
) -> tuple[list[dict[str, str]], dict[str, dict[str, float]]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        emitted = list(csv.DictReader(handle))
    if len(emitted) != len(rows):
        raise VerificationError("prediction row count mismatch")
    scores: dict[str, dict[str, float]] = {arm: {} for arm in ARMS}
    for index, (row, fold, output) in enumerate(zip(rows, folds, emitted)):
        if int(output["row_index"]) != index or int(output["fold"]) != fold:
            raise VerificationError(f"prediction row/fold mismatch at {index}")
        for key in ("task", "run", "parent", "better", "worse"):
            if str(output[key]) != str(row[key]):
                raise VerificationError(f"prediction {key} mismatch at {index}")
        assert_close(float(output["gap_raw"]), float(row["gap_raw"]), f"gap {index}", 1e-14)
        for arm in ARMS:
            better_score = float(output[f"{arm}_better_score"])
            worse_score = float(output[f"{arm}_worse_score"])
            margin = float(output[f"{arm}_margin"])
            assert_close(margin, better_score - worse_score, f"margin {arm} {index}", 1e-12)
            assert_close(float(output[f"{arm}_hit"]), tie_hit(margin), f"hit {arm} {index}", 1e-12)
            for card_id, value in ((str(row["better"]), better_score), (str(row["worse"]), worse_score)):
                if card_id in scores[arm]:
                    assert_close(scores[arm][card_id], value, f"score {arm} {card_id}", 1e-10)
                scores[arm][card_id] = value
    return emitted, scores


def expected_grid(family: str) -> set[tuple[float, float | None]]:
    if family.startswith("nested_global_"):
        return {(value, None) for value in LAMBDA_GLOBAL_GRID}
    return {
        (global_value, task_value)
        for global_value in LAMBDA_GLOBAL_GRID
        for task_value in LAMBDA_TASK_GRID
    }


def verify_selection(record: dict[str, Any], family: str) -> None:
    selection = record["inner_selection"]
    candidates = selection["candidates"]
    observed = {
        (
            float(candidate["configuration"]["lambda_global"]),
            None
            if candidate["configuration"]["lambda_task"] is None
            else float(candidate["configuration"]["lambda_task"]),
        )
        for candidate in candidates
    }
    if observed != expected_grid(family) or not all(candidate["accepted"] for candidate in candidates):
        raise VerificationError(f"inner grid/acceptance mismatch: {family}")
    if any(
        not fit["accepted"] or int(fit["run_overlap"]) != 0
        for candidate in candidates
        for fit in candidate["fits"]
    ):
        raise VerificationError(f"inner fit/run integrity mismatch: {family}")

    def key(candidate: dict[str, Any]) -> tuple[float, float, float, float]:
        config = candidate["configuration"]
        return (
            float(candidate["inner_top1"]),
            float(candidate["inner_utility"]),
            float(config["lambda_task"] or 0.0),
            float(config["lambda_global"]),
        )

    best = max(candidates, key=key)
    if best["configuration"] != selection["selected"]:
        raise VerificationError(f"inner selected configuration mismatch: {family}")
    outer = record["outer_fit"]
    if not outer["accepted"] or float(outer["lambda_global"]) != float(selection["selected"]["lambda_global"]):
        raise VerificationError(f"outer fit/global lambda mismatch: {family}")
    selected_task = selection["selected"]["lambda_task"]
    if (outer["lambda_task"] is None) != (selected_task is None):
        raise VerificationError(f"outer fit/task lambda null mismatch: {family}")
    if selected_task is not None and float(outer["lambda_task"]) != float(selected_task):
        raise VerificationError(f"outer fit/task lambda mismatch: {family}")


def verify_checkpoints(
    result_dir: Path,
    summary: dict[str, Any],
    rows: Sequence[dict[str, Any]],
    folds: Sequence[int],
    manifest: Sequence[dict[str, Any]],
    matrix: np.ndarray,
    position: dict[str, int],
    csv_scores: dict[str, dict[str, float]],
) -> dict[str, Any]:
    checkpoint_root = result_dir / "checkpoints"
    task_names = sorted({str(row["task"]) for row in rows})
    endpoint_tasks = [str(row["task"]) for row in manifest]
    verified_weights = 0
    for fold in range(5):
        fold_dir = checkpoint_root / f"fold_{fold}"
        record = json.loads((fold_dir / "fold_summary.json").read_text(encoding="utf-8"))
        if record.get("status") != "FOLD_COMPLETE" or record.get("checkpoint_key") != summary["checkpoint_key"]:
            raise VerificationError(f"fold checkpoint identity mismatch: {fold}")
        if int(record["run_overlap"]) != 0:
            raise VerificationError(f"fold run overlap: {fold}")
        valid_ids = sorted(
            {
                str(rows[index][key])
                for index, value in enumerate(folds)
                if value == fold
                for key in ("better", "worse")
            }
        )
        score_path = fold_dir / "valid_scores.npz"
        if sha256(score_path) != record["files"]["valid_scores_sha256"]:
            raise VerificationError(f"valid-score hash mismatch: fold {fold}")
        with np.load(score_path, allow_pickle=False) as data:
            if [str(value) for value in data["card_ids"].tolist()] != valid_ids:
                raise VerificationError(f"valid-score ID mismatch: fold {fold}")
            for family in FAMILIES:
                stored = np.asarray(data[family], dtype=np.float64)
                expected = np.asarray([csv_scores[family][card_id] for card_id in valid_ids])
                if not np.allclose(stored, expected, atol=1e-12, rtol=1e-12):
                    raise VerificationError(f"valid-score NPZ/CSV mismatch: {family} fold {fold}")
        for family in FAMILIES:
            verify_selection(record["families"][family], family)
            weight_path = fold_dir / f"{family}_weights.npz"
            if sha256(weight_path) != record["files"][f"{family}_weights_sha256"]:
                raise VerificationError(f"weight hash mismatch: {family} fold {fold}")
            with np.load(weight_path, allow_pickle=False) as data:
                global_weight = np.asarray(data["global_weight"])
                task_weights = np.asarray(data["task_weights"])
                stored_tasks = [str(value) for value in data["task_names"].tolist()]
            if global_weight.dtype != np.float64 or task_weights.dtype != np.float64:
                raise VerificationError("checkpoint weights are not float64")
            if global_weight.shape != (1_792,) or task_weights.shape != (23, 1_792) or stored_tasks != task_names:
                raise VerificationError(f"weight shape/task mismatch: {family} fold {fold}")
            task_position = {task: index for index, task in enumerate(stored_tasks)}
            endpoint_task_indices = np.asarray([task_position[task] for task in endpoint_tasks])
            reconstructed = np.asarray(matrix, dtype=np.float64) @ global_weight
            reconstructed += np.einsum(
                "ij,ij->i",
                np.asarray(matrix, dtype=np.float64),
                task_weights[endpoint_task_indices],
                optimize=True,
            )
            expected = np.asarray([csv_scores[family][card_id] for card_id in valid_ids])
            actual = np.asarray([reconstructed[position[card_id]] for card_id in valid_ids])
            if not np.allclose(actual, expected, atol=1e-10, rtol=1e-10):
                raise VerificationError(f"weight-rescore mismatch: {family} fold {fold}")
            fit_tasks = {
                str(rows[index]["task"])
                for index, value in enumerate(folds)
                if value != fold
            }
            for task_index, task in enumerate(task_names):
                if task not in fit_tasks and not np.array_equal(task_weights[task_index], np.zeros(1_792)):
                    raise VerificationError(f"unseen task does not fall back globally: {task} fold {fold}")
            verified_weights += 1
    return {"folds": 5, "weight_files": verified_weights, "run_overlap": 0}


def tie_hit(margin: float) -> float:
    if margin > EPSILON:
        return 1.0
    if margin < -EPSILON:
        return 0.0
    return 0.5


def cluster_summary(
    rows: Sequence[dict[str, Any]], values: Sequence[float], key: str, seed: int
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
    return (
        sum(population) / len(population),
        [draws[int(0.025 * BOOTSTRAP_REPS)], draws[int(0.975 * BOOTSTRAP_REPS)]],
        means,
    )


def summarize_values(
    rows: Sequence[dict[str, Any]], values: Sequence[float], seed_offset: int
) -> dict[str, Any]:
    run_macro, run_ci, per_run = cluster_summary(rows, values, "run", SEED + seed_offset)
    task_macro, task_ci, per_task = cluster_summary(rows, values, "task", SEED + seed_offset + 1)
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
    for parent, items in sorted(grouped.items()):
        candidates = {str(row[key]) for row in items for key in ("better", "worse")}
        if len(items) != len(candidates) * (len(candidates) - 1) // 2:
            incomplete += 1
            continue
        losses = collections.Counter({candidate: 0 for candidate in candidates})
        for row in items:
            losses[str(row["worse"])] += 1
        true_top = {candidate for candidate, value in losses.items() if value == min(losses.values())}
        maximum = max(scores[candidate] for candidate in candidates)
        predicted = {candidate for candidate in candidates if abs(scores[candidate] - maximum) <= EPSILON}
        records[parent] = {
            "value": len(predicted & true_top) / len(predicted),
            "run": str(items[0]["run"]),
            "task": str(items[0]["task"]),
        }
    proxy = [{"run": item["run"], "task": item["task"]} for item in records.values()]
    values = [float(item["value"]) for item in records.values()]
    summary = summarize_values(proxy, values, 40)
    summary.update(
        {
            "complete_parents": len(records),
            "incomplete_parents": incomplete,
            "complete_share": len(records) / len(grouped),
        }
    )
    return summary, records


def gap_utility(
    rows: Sequence[dict[str, Any]], hits: Sequence[float]
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    grouped: dict[str, list[tuple[dict[str, Any], float]]] = collections.defaultdict(list)
    for row, hit in zip(rows, hits):
        grouped[str(row["parent"])].append((row, float(hit)))
    records: dict[str, dict[str, Any]] = {}
    for parent, items in grouped.items():
        denominator = sum(float(row["gap_raw"]) for row, _ in items)
        if denominator <= 0:
            raise VerificationError(f"non-positive gap denominator: {parent}")
        records[parent] = {
            "value": sum(float(row["gap_raw"]) * hit for row, hit in items) / denominator,
            "run": str(items[0][0]["run"]),
            "task": str(items[0][0]["task"]),
        }
    proxy = [{"run": item["run"], "task": item["task"]} for item in records.values()]
    values = [float(item["value"]) for item in records.values()]
    summary = summarize_values(proxy, values, 60)
    summary["parents"] = len(records)
    summary["definition"] = "mean_parent(sum(gap_raw*hit)/sum(gap_raw))"
    return summary, records


def task_consistency(rows: Sequence[dict[str, Any]], hits: Sequence[float]) -> dict[str, Any]:
    grouped: dict[str, list[float]] = collections.defaultdict(list)
    for row, hit in zip(rows, hits):
        grouped[str(row["task"])].append(float(hit))
    supported = {
        task: {"pairs": len(values), "accuracy": sum(values) / len(values)}
        for task, values in sorted(grouped.items())
        if len(values) >= 20
    }
    nonchance = sum(item["accuracy"] >= 0.5 for item in supported.values())
    return {
        "minimum_pairs": 20,
        "supported_tasks": len(supported),
        "nonchance_tasks": nonchance,
        "nonchance_share": nonchance / len(supported) if supported else 0.0,
        "details": supported,
    }


def model_metrics(
    rows: Sequence[dict[str, Any]], scores: dict[str, float], seed_offset: int
) -> dict[str, Any]:
    hits = [tie_hit(scores[str(row["better"])] - scores[str(row["worse"])]) for row in rows]
    pair = summarize_values(rows, hits, seed_offset)
    top1, top1_records = parent_top1(rows, scores)
    utility, utility_records = gap_utility(rows, hits)
    return {
        "pair": pair,
        "top1": top1,
        "utility": utility,
        "task_consistency": task_consistency(rows, hits),
        "top1_records": top1_records,
        "utility_records": utility_records,
    }


def paired_summary(
    main: dict[str, dict[str, Any]], baseline: dict[str, dict[str, Any]], seed_offset: int
) -> dict[str, Any]:
    if set(main) != set(baseline):
        raise VerificationError("paired support mismatch")
    names = sorted(main)
    proxy = [{"run": main[name]["run"], "task": main[name]["task"]} for name in names]
    values = [float(main[name]["value"]) - float(baseline[name]["value"]) for name in names]
    summary = summarize_values(proxy, values, seed_offset)
    summary["records"] = len(values)
    return summary


def paired_metric_comparison(
    left: dict[str, Any], right: dict[str, Any], seed_offset: int
) -> dict[str, Any]:
    return {
        "top1": paired_summary(
            left["top1_records"], right["top1_records"], seed_offset
        ),
        "utility": paired_summary(
            left["utility_records"], right["utility_records"], seed_offset + 10
        ),
    }


def compare_headline(actual: dict[str, Any], expected: dict[str, Any], label: str) -> None:
    for metric in ("pair", "top1", "utility"):
        for key in ("overall", "run_macro", "task_macro"):
            assert_close(actual[metric][key], expected[metric][key], f"{label}.{metric}.{key}")
        for key in ("run_macro_ci95", "task_macro_ci95"):
            for index in range(2):
                assert_close(
                    actual[metric][key][index],
                    expected[metric][key][index],
                    f"{label}.{metric}.{key}[{index}]",
                )
    for key in ("supported_tasks", "nonchance_tasks", "nonchance_share"):
        assert_close(
            actual["task_consistency"][key],
            expected["task_consistency"][key],
            f"{label}.task_consistency.{key}",
        )


def random_score(card_id: str) -> float:
    return (zlib.crc32(f"{SEED}:{card_id}".encode("utf-8")) & 0xFFFFFFFF) / 2**32


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--feature-root", required=True, type=Path)
    parser.add_argument("--baseline-oof", required=True, type=Path)
    parser.add_argument("--result-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--expect-pairs-sha256", required=True)
    parser.add_argument("--expect-manifest-sha256", required=True)
    parser.add_argument("--expect-baseline-sha256", required=True)
    parser.add_argument("--extraction-commit", required=True)
    parser.add_argument("--model-sha256", required=True)
    return parser.parse_args()


def main() -> int:
    args = arguments()
    reject_forbidden_path(args.pairs, "training pairs")
    reject_forbidden_path(args.baseline_oof, "baseline OOF")
    if sha256(args.pairs) != args.expect_pairs_sha256.lower():
        raise VerificationError("training-pair hash mismatch")
    rows = load_pairs(args.pairs)
    manifest = load_manifest(args.manifest, args.expect_manifest_sha256)
    manifest_sha = sha256(args.manifest)
    matrix, position, feature_audit = load_features(
        args.feature_root,
        manifest,
        manifest_sha,
        args.extraction_commit,
        args.model_sha256.lower(),
    )
    folds, fixed_baseline = load_baseline(args.baseline_oof, rows, args.expect_baseline_sha256)
    summary_path = args.result_dir / "summary.json"
    predictions_path = args.result_dir / "oof_predictions.csv"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if summary.get("protocol") != PROTOCOL or summary.get("frozen_read") is not False:
        raise VerificationError("producer protocol/frozen flag mismatch")
    if summary.get("configuration", {}).get("optimizer", {}).get("checkpoint_dtype") != "float64":
        raise VerificationError("producer checkpoint dtype mismatch")
    if sha256(predictions_path) != summary["outputs"]["oof_predictions_sha256"]:
        raise VerificationError("producer prediction hash mismatch")
    _, scores = load_predictions(predictions_path, rows, folds)
    for card_id, value in fixed_baseline.items():
        assert_close(scores["fixed_global_allpair"][card_id], value, f"fixed baseline {card_id}", 1e-12)
    checkpoint_audit = verify_checkpoints(
        args.result_dir, summary, rows, folds, manifest, matrix, position, scores
    )
    metrics = {
        arm: model_metrics(rows, scores[arm], METRIC_SEED_OFFSETS[arm])
        for arm in ARMS
    }
    for arm in ARMS:
        compare_headline(metrics[arm], summary["metrics"][arm], arm)
    baseline = metrics["fixed_global_allpair"]
    main = metrics[MAIN_ARM]
    paired_comparisons = {
        "main_minus_fixed_baseline": paired_metric_comparison(main, baseline, 400),
        "nested_global_allpair_minus_fixed_baseline": paired_metric_comparison(
            metrics["nested_global_allpair"], baseline, 440
        ),
        "topcenter_effect_at_global": paired_metric_comparison(
            metrics["nested_global_topcenter"], metrics["nested_global_allpair"], 480
        ),
        "task_effect_at_allpair": paired_metric_comparison(
            metrics["nested_task_allpair"], metrics["nested_global_allpair"], 520
        ),
        "task_effect_at_topcenter": paired_metric_comparison(
            metrics["nested_task_topcenter"], metrics["nested_global_topcenter"], 560
        ),
        "topcenter_effect_at_task": paired_metric_comparison(
            metrics["nested_task_topcenter"], metrics["nested_task_allpair"], 600
        ),
    }
    top1_delta = paired_comparisons["main_minus_fixed_baseline"]["top1"]
    utility_delta = paired_comparisons["main_minus_fixed_baseline"]["utility"]
    for comparison, comparison_values in paired_comparisons.items():
        for label, actual in comparison_values.items():
            expected = summary["paired_delta_comparisons"][comparison][label]
            for key in ("overall", "run_macro", "task_macro"):
                assert_close(actual[key], expected[key], f"delta.{comparison}.{label}.{key}")
            for key in ("run_macro_ci95", "task_macro_ci95"):
                for index in range(2):
                    assert_close(
                        actual[key][index],
                        expected[key][index],
                        f"delta.{comparison}.{label}.{key}[{index}]",
                    )
    random_scores = {str(row["card_id"]): random_score(str(row["card_id"])) for row in manifest}
    random_metrics = model_metrics(rows, random_scores, 20)
    compare_headline(random_metrics, summary["random_control"], "random")
    structure_checks = {
        "pairs_eq_4263": len(rows) == 4_263,
        "runs_eq_333": len({row["run"] for row in rows}) == 333,
        "tasks_eq_23": len({row["task"] for row in rows}) == 23,
        "parents_eq_2293": len({row["parent"] for row in rows}) == 2_293,
        "endpoints_eq_5499": len({row[key] for row in rows for key in ("better", "worse")}) == 5_499,
        "feature_dimension_eq_1792": feature_audit["dimension"] == 1_792,
        "feature_coverage_exact": feature_audit["endpoints"] == 5_499,
        "complete_parents_eq_2259": baseline["top1"]["complete_parents"] == 2_259,
        "outer_run_overlap_eq_0": checkpoint_audit["run_overlap"] == 0,
        "all_fits_accepted": True,
        "formal_runtime_le_cap": float(summary["runtime_s"]) <= 2_700.0,
        "baseline_hash_exact": sha256(args.baseline_oof) == args.expect_baseline_sha256.lower(),
        "baseline_headline_exact": (
            math.isclose(baseline["pair"]["overall"], 0.5038705137227305, abs_tol=1e-12)
            and math.isclose(baseline["top1"]["overall"], 0.44710048694112436, abs_tol=1e-12)
            and math.isclose(baseline["utility"]["overall"], 0.5105066477670084, abs_tol=1e-12)
        ),
        "random_pair_in_047_053": 0.47 <= random_metrics["pair"]["overall"] <= 0.53,
        "orientation_oracle_eq_1": summary.get("orientation_oracle") == 1.0,
        "frozen_read_false": summary.get("frozen_read") is False,
    }
    effect_checks = {
        "main_top1_ge_050": main["top1"]["overall"] >= 0.50,
        "main_top1_delta_ge_003": top1_delta["overall"] >= 0.03,
        "top1_run_delta_ci_low_gt_0": top1_delta["run_macro_ci95"][0] > 0.0,
        "top1_task_delta_ci_low_gt_0": top1_delta["task_macro_ci95"][0] > 0.0,
        "main_utility_ge_055": main["utility"]["overall"] >= 0.55,
        "main_utility_delta_ge_002": utility_delta["overall"] >= 0.02,
        "utility_run_delta_ci_low_gt_0": utility_delta["run_macro_ci95"][0] > 0.0,
        "utility_task_delta_ci_low_gt_0": utility_delta["task_macro_ci95"][0] > 0.0,
        "main_pair_accuracy_ge_050": main["pair"]["overall"] >= 0.50,
        "supported_tasks_ge_15": main["task_consistency"]["supported_tasks"] >= 15,
        "task_nonchance_share_ge_060": main["task_consistency"]["nonchance_share"] >= 0.60,
    }
    checks = {**structure_checks, **effect_checks}
    checks["all"] = all(checks.values())
    for key, value in checks.items():
        if bool(summary["discovery_gate"].get(key)) != bool(value):
            raise VerificationError(f"producer/verifier gate mismatch: {key}")
    expected_status = "DISCOVERY_UNLOCK_RECOMMENDED" if checks["all"] else "DISCOVERY_NO_UNLOCK"
    if summary.get("status") != expected_status:
        raise VerificationError("producer status mismatch")
    output = {
        "status": "VERIFIED_DISCOVERY_UNLOCK_RECOMMENDED"
        if checks["all"]
        else "VERIFIED_DISCOVERY_NO_UNLOCK",
        "protocol": PROTOCOL,
        "frozen_read": False,
        "producer_summary_sha256": sha256(summary_path),
        "producer_predictions_sha256": sha256(predictions_path),
        "feature_audit": feature_audit,
        "checkpoint_audit": checkpoint_audit,
        "metrics": {
            arm: {
                "pair_accuracy": metrics[arm]["pair"]["overall"],
                "complete_parent_top1": metrics[arm]["top1"]["overall"],
                "parent_equal_gap_utility": metrics[arm]["utility"]["overall"],
            }
            for arm in ARMS
        },
        "paired_delta_comparisons": paired_comparisons,
        "discovery_gate": checks,
    }
    atomic_json(args.output, output)
    print(
        output["status"],
        f"main_top1={main['top1']['overall']:.6f}",
        f"top1_delta={top1_delta['overall']:.6f}",
        f"main_utility={main['utility']['overall']:.6f}",
        f"utility_delta={utility_delta['overall']:.6f}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
