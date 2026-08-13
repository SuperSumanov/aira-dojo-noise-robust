"""Frozen gap- and task-aware audit of official FOREAGENT alignments."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np


BOOTSTRAP_SEED = 20260813
BOOTSTRAP_REPLICATES = 10_000
RAW_EDGES = [0.0, 1e-4, 3e-4, 1e-3, 3e-3, 1e-2, 3e-2, 1e-1, 3e-1, math.inf]
RAW_LABELS = [
    "[0,1e-4)",
    "[1e-4,3e-4)",
    "[3e-4,1e-3)",
    "[1e-3,3e-3)",
    "[3e-3,1e-2)",
    "[1e-2,3e-2)",
    "[3e-2,1e-1)",
    "[1e-1,3e-1)",
    "[3e-1,inf)",
]


@dataclass(frozen=True)
class ParsedRecord:
    source_index: int
    task: str
    model: str
    release_run: int
    pair_key: tuple[str, str]
    paths: tuple[str, str]
    score_by_path: tuple[tuple[str, float], tuple[str, float]]
    gap: float
    is_lower_better: bool
    true_path: str | None
    groundtruth_path: str
    prediction_path: str | None
    prediction_index: int | None
    confidence: float | None
    correct: float | None
    release_correct: Any


@dataclass(frozen=True)
class PairAverage:
    task: str
    model: str
    pair_key: tuple[str, str]
    gap: float
    accuracy: float
    confidence: float
    unanimous: bool


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_index(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value in (0, 1):
        return value
    return None


def parse_record(raw: dict[str, Any], source: dict[str, Any]) -> ParsedRecord:
    source_index = raw.get("source_index")
    if source_index != source["source_index"]:
        raise RuntimeError(f"source index mismatch: {source_index} != {source['source_index']}")
    task = raw.get("task")
    model = raw.get("model_family")
    release_run = raw.get("release_run")
    if (task, model, release_run) != (source["task"], source["model_family"], source["release_run"]):
        raise RuntimeError(f"source identity mismatch at {source_index}")

    paths_raw = raw.get("solution_paths")
    scores_raw = raw.get("scores")
    if (
        not isinstance(paths_raw, list)
        or len(paths_raw) != 2
        or not all(isinstance(path, str) and path for path in paths_raw)
        or paths_raw[0] == paths_raw[1]
    ):
        raise RuntimeError(f"invalid paths at source {source_index}")
    if not isinstance(scores_raw, list) or len(scores_raw) != 2:
        raise RuntimeError(f"invalid scores at source {source_index}")
    try:
        scores = (float(scores_raw[0]), float(scores_raw[1]))
    except (TypeError, ValueError) as error:
        raise RuntimeError(f"non-numeric scores at source {source_index}") from error
    if not all(math.isfinite(score) for score in scores):
        raise RuntimeError(f"non-finite scores at source {source_index}")
    is_lower_better = raw.get("is_lower_better")
    if not isinstance(is_lower_better, bool):
        raise RuntimeError(f"invalid is_lower_better at source {source_index}")

    paths = (paths_raw[0], paths_raw[1])
    gap = abs(scores[0] - scores[1])
    if scores[0] == scores[1]:
        true_path = None
    elif is_lower_better:
        true_path = paths[0] if scores[0] < scores[1] else paths[1]
    else:
        true_path = paths[0] if scores[0] > scores[1] else paths[1]

    groundtruth_index = parse_index(raw.get("groundtruth_best_index"))
    if groundtruth_index is None:
        raise RuntimeError(f"invalid groundtruth index at source {source_index}")
    groundtruth_path = paths[groundtruth_index]
    if true_path is not None and groundtruth_path != true_path:
        raise RuntimeError(f"groundtruth disagrees with score at source {source_index}")

    prediction_index = parse_index(raw.get("prediction_best_index"))
    prediction_path = paths[prediction_index] if prediction_index is not None else None
    confidence_raw = raw.get("confidence")
    try:
        confidence = float(confidence_raw)
    except (TypeError, ValueError):
        confidence = None
    if confidence is not None and (not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0):
        confidence = None
    valid = prediction_path is not None and confidence is not None and true_path is not None
    correct = float(prediction_path == true_path) if valid else None

    pair_key = tuple(sorted(paths))
    score_by_path = tuple(sorted(((paths[0], scores[0]), (paths[1], scores[1]))))
    return ParsedRecord(
        source_index=source_index,
        task=task,
        model=model,
        release_run=release_run,
        pair_key=pair_key,
        paths=paths,
        score_by_path=score_by_path,
        gap=gap,
        is_lower_better=is_lower_better,
        true_path=true_path,
        groundtruth_path=groundtruth_path,
        prediction_path=prediction_path,
        prediction_index=prediction_index,
        confidence=confidence,
        correct=correct,
        release_correct=raw.get("release_correct"),
    )


def raw_bin(gap: float) -> int:
    for index in range(len(RAW_EDGES) - 1):
        if RAW_EDGES[index] <= gap < RAW_EDGES[index + 1]:
            return index
    raise RuntimeError(f"gap outside frozen bins: {gap}")


def within_task_bins(gaps: dict[tuple[str, str], float], count: int) -> dict[tuple[str, str], int]:
    ordered = sorted(gaps.items(), key=lambda item: (item[1], item[0]))
    n = len(ordered)
    result: dict[tuple[str, str], int] = {}
    start = 0
    while start < n:
        end = start + 1
        while end < n and ordered[end][1] == ordered[start][1]:
            end += 1
        percentile = (start + end) / (2.0 * n)
        bucket = min(count - 1, int(percentile * count))
        for index in range(start, end):
            result[ordered[index][0]] = bucket
        start = end
    return result


def stable_rng(label: str) -> np.random.Generator:
    label_seed = int.from_bytes(hashlib.sha256(label.encode("utf-8")).digest()[:8], "big")
    return np.random.default_rng(label_seed ^ BOOTSTRAP_SEED)


def percentile_interval(values: np.ndarray) -> tuple[float, float]:
    lower, upper = np.quantile(values, [0.025, 0.975])
    return float(lower), float(upper)


def summarize_pairs(rows: Iterable[PairAverage], label: str) -> dict[str, Any]:
    by_task: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        by_task[row.task].append(row.accuracy)
    if not by_task:
        return {
            "n_tasks": 0,
            "n_pairs": 0,
            "task_macro": None,
            "task_macro_ci": [None, None],
            "pair_micro": None,
            "pair_micro_task_cluster_ci": [None, None],
        }
    tasks = sorted(by_task)
    sums = np.asarray([sum(by_task[task]) for task in tasks], dtype=float)
    counts = np.asarray([len(by_task[task]) for task in tasks], dtype=float)
    means = sums / counts
    rng = stable_rng(label)
    indices = rng.integers(0, len(tasks), size=(BOOTSTRAP_REPLICATES, len(tasks)))
    task_boot = means[indices].mean(axis=1)
    pair_boot = sums[indices].sum(axis=1) / counts[indices].sum(axis=1)
    return {
        "n_tasks": len(tasks),
        "n_pairs": int(counts.sum()),
        "task_macro": float(means.mean()),
        "task_macro_ci": list(percentile_interval(task_boot)),
        "pair_micro": float(sums.sum() / counts.sum()),
        "pair_micro_task_cluster_ci": list(percentile_interval(pair_boot)),
    }


def summarize_paired_differences(values: dict[str, float], label: str) -> dict[str, Any]:
    tasks = sorted(values)
    array = np.asarray([values[task] for task in tasks], dtype=float)
    if not len(array):
        return {"n_tasks": 0, "mean": None, "ci": [None, None]}
    rng = stable_rng(label)
    indices = rng.integers(0, len(array), size=(BOOTSTRAP_REPLICATES, len(array)))
    boot = array[indices].mean(axis=1)
    return {"n_tasks": len(array), "mean": float(array.mean()), "ci": list(percentile_interval(boot))}


def ece10(records: Iterable[ParsedRecord]) -> float | None:
    bins: list[list[tuple[float, float]]] = [[] for _ in range(10)]
    for record in records:
        if record.correct is None or record.confidence is None:
            continue
        index = min(9, int(record.confidence * 10.0))
        bins[index].append((record.confidence, record.correct))
    total = sum(len(bucket) for bucket in bins)
    if total == 0:
        return None
    value = 0.0
    for bucket in bins:
        if bucket:
            mean_confidence = sum(item[0] for item in bucket) / len(bucket)
            mean_correct = sum(item[1] for item in bucket) / len(bucket)
            value += len(bucket) / total * abs(mean_confidence - mean_correct)
    return value


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def self_test() -> None:
    gaps = {("a", str(index)): gap for index, gap in enumerate([0.1, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7])}
    quartiles = within_task_bins(gaps, 4)
    assert quartiles[("a", "0")] == quartiles[("a", "1")]
    assert min(quartiles.values()) == 0 and max(quartiles.values()) == 3
    assert raw_bin(0.0) == 0 and raw_bin(0.01) == 5 and raw_bin(0.3) == 8
    print("FOREAGENT_ALIGNMENT_AUDIT_SELF_TEST_PASS")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--download-log", type=Path)
    parser.add_argument("--master", type=Path)
    parser.add_argument("--out-dir", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    if not all((args.manifest, args.download_log, args.master, args.out_dir)):
        parser.error("--manifest, --download-log, --master, and --out-dir are required")

    out_dir: Path = args.out_dir
    expected_outputs = [
        out_dir / "summary.json",
        out_dir / "per_run.csv",
        out_dir / "per_task.csv",
        out_dir / "stratified.csv",
    ]
    if any(path.exists() for path in expected_outputs):
        raise RuntimeError("refusing to overwrite alignment audit outputs")
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest_raw = args.manifest.read_bytes()
    manifest = json.loads(manifest_raw)
    download_log = json.loads(args.download_log.read_text(encoding="utf-8"))
    if manifest.get("file_count") != 156 or len(manifest.get("files", [])) != 156:
        raise RuntimeError("manifest does not contain frozen 156 files")
    if download_log.get("manifest_sha256") != hashlib.sha256(manifest_raw).hexdigest():
        raise RuntimeError("manifest/download-log mismatch")
    if download_log.get("master", {}).get("sha256") != sha256_file(args.master):
        raise RuntimeError("master compact hash mismatch")

    sources: list[dict[str, Any]] = []
    for source_index, source in enumerate(manifest["files"]):
        enriched = dict(source)
        enriched["source_index"] = source_index
        sources.append(enriched)

    by_source: dict[int, dict[tuple[str, str], ParsedRecord]] = defaultdict(dict)
    ordinals: dict[int, set[Any]] = defaultdict(set)
    log_index_values: dict[int, list[Any]] = defaultdict(list)
    with args.master.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            raw = json.loads(line)
            source_index = raw.get("source_index")
            if not isinstance(source_index, int) or not 0 <= source_index < len(sources):
                raise RuntimeError(f"bad source index on master line {line_number}")
            parsed = parse_record(raw, sources[source_index])
            if parsed.pair_key in by_source[source_index]:
                raise RuntimeError(f"duplicate pair in source {source_index}")
            ordinal = raw.get("ordinal")
            if ordinal in ordinals[source_index]:
                raise RuntimeError(f"duplicate extraction ordinal in source {source_index}")
            by_source[source_index][parsed.pair_key] = parsed
            ordinals[source_index].add(ordinal)
            log_index_values[source_index].append(raw.get("log_index"))
    if set(by_source) != set(range(156)):
        raise RuntimeError("not all 156 source files appear in compact master")

    task_sources: dict[str, list[int]] = defaultdict(list)
    for source in sources:
        task_sources[source["task"]].append(source["source_index"])
    if len(task_sources) != 26 or any(len(indices) != 6 for indices in task_sources.values()):
        raise RuntimeError("expected 26 tasks with 6 source files each")

    reference_by_task: dict[str, dict[tuple[str, str], ParsedRecord]] = {}
    for task, indices in sorted(task_sources.items()):
        reference = by_source[indices[0]]
        reference_keys = set(reference)
        for source_index in indices[1:]:
            current = by_source[source_index]
            if set(current) != reference_keys:
                raise RuntimeError(f"GRID-MISMATCH task={task} source={source_index}")
            for pair_key, ref in reference.items():
                row = current[pair_key]
                if (
                    row.score_by_path != ref.score_by_path
                    or row.is_lower_better != ref.is_lower_better
                    or row.true_path != ref.true_path
                ):
                    raise RuntimeError(f"GROUNDTRUTH-MISMATCH task={task} pair={pair_key}")
        reference_by_task[task] = reference

    total_base_pairs = sum(len(rows) for rows in reference_by_task.values())
    total_ties = sum(
        1 for rows in reference_by_task.values() for record in rows.values() if record.true_path is None
    )
    log_index_all_null_sources = sum(
        all(value is None for value in log_index_values[source_index]) for source_index in range(156)
    )
    log_index_null_records = sum(
        value is None for source_index in range(156) for value in log_index_values[source_index]
    )
    log_index_duplicate_nonnull_sources = 0
    for source_index in range(156):
        nonnull = [repr(value) for value in log_index_values[source_index] if value is not None]
        if len(nonnull) != len(set(nonnull)):
            log_index_duplicate_nonnull_sources += 1

    per_run_rows: list[dict[str, Any]] = []
    min_valid_coverage = 1.0
    release_correct_mismatches = 0
    for source in sources:
        records = list(by_source[source["source_index"]].values())
        nonties = [record for record in records if record.true_path is not None]
        valid = [record for record in nonties if record.correct is not None]
        coverage = len(valid) / len(nonties) if nonties else 0.0
        min_valid_coverage = min(min_valid_coverage, coverage)
        for record in valid:
            normalized_release = str(record.release_correct).strip().lower()
            release_value = normalized_release in {"correct", "true", "1"}
            if release_value != bool(record.correct):
                release_correct_mismatches += 1
        per_run_rows.append(
            {
                "task": source["task"],
                "model_family": source["model_family"],
                "release_run": source["release_run"],
                "model_token": source["model_token"],
                "temperature_token": source["temperature_token"],
                "timestamp": source["timestamp"],
                "source_path": source["path"],
                "pairs": len(records),
                "exact_ties": len(records) - len(nonties),
                "valid_nontie_predictions": len(valid),
                "valid_coverage": coverage,
                "accuracy": sum(record.correct for record in valid) / len(valid) if valid else None,
                "pick_index0_rate": (
                    sum(record.prediction_index == 0 for record in valid) / len(valid) if valid else None
                ),
                "mean_confidence": (
                    sum(record.confidence for record in valid if record.confidence is not None) / len(valid)
                    if valid
                    else None
                ),
                "ece10": ece10(valid),
            }
        )

    pair_averages: list[PairAverage] = []
    per_task_pair_map: dict[tuple[str, str], list[PairAverage]] = defaultdict(list)
    for task, indices in sorted(task_sources.items()):
        for model in ("deepseek", "gpt"):
            model_indices = [index for index in indices if sources[index]["model_family"] == model]
            if len(model_indices) != 3:
                raise RuntimeError(f"expected 3 {model} files for {task}")
            for pair_key, reference in reference_by_task[task].items():
                if reference.true_path is None:
                    continue
                records = [by_source[index][pair_key] for index in model_indices]
                valid = [record for record in records if record.correct is not None]
                if not valid:
                    continue
                predictions = [record.prediction_path for record in valid]
                pair = PairAverage(
                    task=task,
                    model=model,
                    pair_key=pair_key,
                    gap=reference.gap,
                    accuracy=sum(record.correct for record in valid) / len(valid),
                    confidence=sum(record.confidence for record in valid if record.confidence is not None) / len(valid),
                    unanimous=len(valid) == 3 and len(set(predictions)) == 1,
                )
                pair_averages.append(pair)
                per_task_pair_map[(model, task)].append(pair)

    quartiles: dict[str, dict[tuple[str, str], int]] = {}
    deciles: dict[str, dict[tuple[str, str], int]] = {}
    support_tasks: list[str] = []
    for task, reference in sorted(reference_by_task.items()):
        gaps = {key: record.gap for key, record in reference.items() if record.true_path is not None}
        quartiles[task] = within_task_bins(gaps, 4)
        deciles[task] = within_task_bins(gaps, 10)
        low_count = sum(value == 0 for value in quartiles[task].values())
        high_count = sum(value == 3 for value in quartiles[task].values())
        if low_count >= 20 and high_count >= 20:
            support_tasks.append(task)

    overall: dict[str, Any] = {}
    stratified_rows: list[dict[str, Any]] = []
    stratified_lookup: dict[tuple[str, str, int], dict[str, Any]] = {}
    for model in ("deepseek", "gpt"):
        model_rows = [row for row in pair_averages if row.model == model]
        overall[model] = summarize_pairs(model_rows, f"overall:{model}")
        overall[model]["three_run_unanimous_rate"] = sum(row.unanimous for row in model_rows) / len(model_rows)

        for bin_index, bin_label in enumerate(RAW_LABELS):
            selected = [row for row in model_rows if raw_bin(row.gap) == bin_index]
            summary = summarize_pairs(selected, f"raw:{model}:{bin_index}")
            output = {"group_type": "raw_gap", "model_family": model, "bin_index": bin_index, "bin": bin_label, **summary}
            stratified_rows.append(output)
            stratified_lookup[(model, "raw_gap", bin_index)] = summary
        for bin_index in range(4):
            selected = [row for row in model_rows if quartiles[row.task][row.pair_key] == bin_index]
            summary = summarize_pairs(selected, f"quartile:{model}:{bin_index}")
            output = {"group_type": "within_task_quartile", "model_family": model, "bin_index": bin_index, "bin": f"Q{bin_index + 1}", **summary}
            stratified_rows.append(output)
            stratified_lookup[(model, "within_task_quartile", bin_index)] = summary
        for bin_index in range(10):
            selected = [row for row in model_rows if deciles[row.task][row.pair_key] == bin_index]
            summary = summarize_pairs(selected, f"decile:{model}:{bin_index}")
            output = {"group_type": "within_task_decile", "model_family": model, "bin_index": bin_index, "bin": f"D{bin_index + 1}", **summary}
            stratified_rows.append(output)
            stratified_lookup[(model, "within_task_decile", bin_index)] = summary

    per_task_rows: list[dict[str, Any]] = []
    paired_differences: dict[str, dict[str, float]] = {"deepseek": {}, "gpt": {}}
    for model in ("deepseek", "gpt"):
        for task in sorted(reference_by_task):
            rows = per_task_pair_map[(model, task)]
            low = [row.accuracy for row in rows if quartiles[task][row.pair_key] == 0]
            high = [row.accuracy for row in rows if quartiles[task][row.pair_key] == 3]
            low_acc = sum(low) / len(low) if low else None
            high_acc = sum(high) / len(high) if high else None
            if low_acc is not None and high_acc is not None:
                paired_differences[model][task] = high_acc - low_acc
            run_rows = sorted(
                [row for row in per_run_rows if row["model_family"] == model and row["task"] == task],
                key=lambda row: row["release_run"],
            )
            per_task_rows.append(
                {
                    "task": task,
                    "model_family": model,
                    "pairs": len(reference_by_task[task]),
                    "exact_ties": sum(
                        record.true_path is None for record in reference_by_task[task].values()
                    ),
                    "nontie_pair_averages": len(rows),
                    "task_accuracy": sum(row.accuracy for row in rows) / len(rows) if rows else None,
                    "raw_hard_lt_1e-2_share": sum(row.gap < 1e-2 for row in rows) / len(rows) if rows else None,
                    "lowest_quartile_pairs": len(low),
                    "lowest_quartile_accuracy": low_acc,
                    "highest_quartile_pairs": len(high),
                    "highest_quartile_accuracy": high_acc,
                    "highest_minus_lowest": high_acc - low_acc if low_acc is not None and high_acc is not None else None,
                    "three_run_unanimous_rate": sum(row.unanimous for row in rows) / len(rows) if rows else None,
                    "release_run_1_accuracy": run_rows[0]["accuracy"],
                    "release_run_2_accuracy": run_rows[1]["accuracy"],
                    "release_run_3_accuracy": run_rows[2]["accuracy"],
                }
            )

    difference_summary = {
        model: summarize_paired_differences(values, f"paired-difference:{model}")
        for model, values in paired_differences.items()
    }

    integrity_support = (
        min_valid_coverage >= 0.99
        and len(support_tasks) >= 24
        and all(
            len([index for index in indices if sources[index]["model_family"] == model]) == 3
            for indices in task_sources.values()
            for model in ("deepseek", "gpt")
        )
    )
    primary_low = stratified_lookup[("deepseek", "within_task_quartile", 0)]
    primary_difference = difference_summary["deepseek"]
    if not integrity_support:
        decision = "INSUFFICIENT-SUPPORT"
    elif (
        primary_low["task_macro"] <= 0.55
        and primary_low["task_macro_ci"][0] <= 0.5 <= primary_low["task_macro_ci"][1]
        and primary_difference["ci"][0] > 0.0
    ):
        decision = "LOCAL-DIFFICULTY-CONFIRMED"
    elif primary_low["task_macro_ci"][0] > 0.55:
        decision = "GAP-ALONE-WEAKENED"
    else:
        decision = "INCONCLUSIVE"

    summary = {
        "schema_version": 1,
        "source": {
            "repo_id": manifest["source"]["repo_id"],
            "revision": manifest["source"]["revision"],
            "manifest_sha256": hashlib.sha256(manifest_raw).hexdigest(),
            "master_sha256": sha256_file(args.master),
            "source_files": len(sources),
        },
        "frozen_inference": {
            "bootstrap_seed": BOOTSTRAP_SEED,
            "bootstrap_replicates": BOOTSTRAP_REPLICATES,
            "release_runs_averaged_within_pair": True,
            "primary_cluster": "task",
        },
        "integrity": {
            "grid_consistent": True,
            "groundtruth_consistent": True,
            "tasks": len(reference_by_task),
            "base_pairs": total_base_pairs,
            "exact_score_ties": total_ties,
            "nontie_pairs": total_base_pairs - total_ties,
            "paper_pair_count": 18438,
            "auto_parquet_pair_count": 18361,
            "paper_minus_parquet": 18438 - 18361,
            "difference_equals_exact_ties": total_ties == 18438 - 18361,
            "min_valid_prediction_coverage": min_valid_coverage,
            "tasks_with_quartile_support": len(support_tasks),
            "release_correct_mismatches": release_correct_mismatches,
            "log_index_all_null_sources": log_index_all_null_sources,
            "log_index_null_records": log_index_null_records,
            "log_index_duplicate_nonnull_sources": log_index_duplicate_nonnull_sources,
            "support_gate_pass": integrity_support,
        },
        "overall": overall,
        "highest_minus_lowest_quartile": difference_summary,
        "primary_gate": {
            "model_family": "deepseek",
            "lowest_quartile": primary_low,
            "highest_minus_lowest": primary_difference,
            "decision": decision,
        },
        "gpt_replication": {
            "lowest_quartile": stratified_lookup[("gpt", "within_task_quartile", 0)],
            "highest_minus_lowest": difference_summary["gpt"],
        },
    }

    write_csv(
        out_dir / "per_run.csv",
        per_run_rows,
        list(per_run_rows[0]),
    )
    write_csv(
        out_dir / "per_task.csv",
        per_task_rows,
        list(per_task_rows[0]),
    )
    write_csv(
        out_dir / "stratified.csv",
        stratified_rows,
        [
            "group_type",
            "model_family",
            "bin_index",
            "bin",
            "n_tasks",
            "n_pairs",
            "task_macro",
            "task_macro_ci",
            "pair_micro",
            "pair_micro_task_cluster_ci",
        ],
    )
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        "FOREAGENT_ALIGNMENT_AUDIT_PASS",
        f"files={len(sources)}",
        f"tasks={len(reference_by_task)}",
        f"pairs={total_base_pairs}",
        f"ties={total_ties}",
        f"deepseek={overall['deepseek']['task_macro']:.6f}",
        f"deepseek_q1={primary_low['task_macro']:.6f}",
        f"deepseek_q4_minus_q1={primary_difference['mean']:.6f}",
        f"decision={decision}",
    )


if __name__ == "__main__":
    main()
