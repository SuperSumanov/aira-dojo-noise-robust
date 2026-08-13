"""Locked structural audit of FOREAGENT's released pair graph.

The audit is descriptive. It does not import our predictor code and does not
contain official model predictions.
"""

from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import math
import statistics
from pathlib import Path, PurePosixPath
from typing import Iterable

import pyarrow.parquet as pq


LOCKS = {
    "official_parquet": "79363b7ef0b6154061f18e81f6c6fdf380e71ae3f1d7b9a262cc79acb08f0b5f",
    "our_b0": "33df48f8c9b54f60e6e3f100b9269e5e3950c506c8ff98601a61848e197ede50",
}
EDGES = [0.0, 1e-4, 3e-4, 1e-3, 3e-3, 1e-2, 3e-2, 1e-1, 3e-1, math.inf]


def cli() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--official-parquet", default="/tmp/pbe_predict_before_execute.parquet")
    parser.add_argument("--our-b0", default="phase1/decision_clean_b0.jsonl")
    parser.add_argument("--out-json", default="phase1/pbe_external_pair_audit.json")
    parser.add_argument("--out-csv", default="phase1/pbe_external_pair_audit_per_task.csv")
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def quantile(values: Iterable[float], fraction: float) -> float:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return math.nan
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def task_from_path(path: str) -> str:
    pieces = PurePosixPath(path).parts
    try:
        index = pieces.index("solutions_subset_50")
    except ValueError as error:
        raise ValueError(f"missing solutions_subset_50 in {path}") from error
    if index + 1 >= len(pieces):
        raise ValueError(path)
    return pieces[index + 1]


def trajectory(path: str) -> str | None:
    stem = PurePosixPath(path).stem
    if "_run_" not in stem:
        return None
    return stem.rsplit("_run_", 1)[0]


def bucket_counts(gaps: Iterable[float]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for left, right in zip(EDGES, EDGES[1:]):
        label = f"[{left:g},{right:g})"
        counts[label] = 0
    for gap in gaps:
        for index, (left, right) in enumerate(zip(EDGES, EDGES[1:])):
            if left <= gap < right or (index == len(EDGES) - 2 and gap == right):
                counts[f"[{left:g},{right:g})"] += 1
                break
        else:
            raise AssertionError(f"unbucketed gap {gap}")
    return counts


def gap_summary(by_task: dict[str, list[float]]) -> dict:
    all_gaps = [gap for values in by_task.values() for gap in values]
    shares = [sum(gap < 1e-2 for gap in values) / len(values) for values in by_task.values()]
    return {
        "pairs": len(all_gaps),
        "tasks": len(by_task),
        "hard_lt_1e2_pairs": sum(gap < 1e-2 for gap in all_gaps),
        "hard_lt_1e2_pair_share": sum(gap < 1e-2 for gap in all_gaps) / len(all_gaps),
        "hard_lt_1e2_task_macro_share": statistics.mean(shares),
        "gap_quantiles": {
            f"q{int(fraction * 100):02d}": quantile(all_gaps, fraction)
            for fraction in (0.10, 0.25, 0.50, 0.75, 0.90)
        },
        "buckets": bucket_counts(all_gaps),
    }


def main() -> None:
    args = cli()
    official_path = Path(args.official_parquet)
    our_path = Path(args.our_b0)
    out_json = Path(args.out_json)
    out_csv = Path(args.out_csv)
    if out_json.exists() or out_csv.exists():
        raise FileExistsError("refusing to overwrite audit output")
    observed_locks = {
        "official_parquet": sha256(official_path),
        "our_b0": sha256(our_path),
    }
    if observed_locks != LOCKS:
        raise RuntimeError(f"input lock mismatch: {observed_locks}")

    table = pq.read_table(official_path)
    if table.column_names != ["paths", "scores", "best_index", "full_ranking", "is_lower_better"]:
        raise RuntimeError(f"official schema changed: {table.column_names}")
    official_rows = table.select(["paths", "scores"]).to_pylist()
    official_by_task: dict[str, list[float]] = collections.defaultdict(list)
    official_task_paths: dict[str, set[str]] = collections.defaultdict(set)
    official_task_pairs: collections.Counter[str] = collections.Counter()
    official_task_same: collections.Counter[str] = collections.Counter()
    official_task_parseable: collections.Counter[str] = collections.Counter()
    appearances: collections.Counter[str] = collections.Counter()
    pair_keys: list[tuple[str, str]] = []
    same_trajectory = 0
    trajectory_parseable = 0

    for index, row in enumerate(official_rows):
        paths = [str(value) for value in row["paths"]]
        scores = [float(value) for value in row["scores"]]
        if len(paths) != 2 or len(scores) != 2 or any(not math.isfinite(value) for value in scores):
            raise RuntimeError(f"invalid official row {index}")
        tasks = {task_from_path(path) for path in paths}
        if len(tasks) != 1:
            raise RuntimeError(f"cross-task pair {index}: {tasks}")
        task = next(iter(tasks))
        gap = abs(scores[0] - scores[1])
        official_by_task[task].append(gap)
        official_task_paths[task].update(paths)
        official_task_pairs[task] += 1
        pair_keys.append(tuple(sorted(paths)))
        appearances.update(paths)
        trajectory_keys = [trajectory(path) for path in paths]
        if all(key is not None for key in trajectory_keys):
            trajectory_parseable += 1
            official_task_parseable[task] += 1
            if trajectory_keys[0] == trajectory_keys[1]:
                same_trajectory += 1
                official_task_same[task] += 1

    our_rows = [
        json.loads(line)
        for line in our_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    our_by_task: dict[str, list[float]] = collections.defaultdict(list)
    our_pair_keys: list[tuple[str, str]] = []
    own_nonfinite_gap_rows: list[dict[str, object]] = []
    for index, row in enumerate(our_rows):
        gap = float(row["gap_raw"])
        if not math.isfinite(gap):
            own_nonfinite_gap_rows.append({
                "zero_based_row": index,
                "task": str(row["task"]),
                "better": str(row["better"]),
                "worse": str(row["worse"]),
            })
            continue
        if gap < 0:
            raise RuntimeError(f"negative own gap at row {index}")
        task = str(row["task"])
        our_by_task[task].append(gap)
        our_pair_keys.append(tuple(sorted((str(row["better"]), str(row["worse"])))))

    common_tasks = sorted(set(official_by_task) & set(our_by_task))
    official_common = {task: official_by_task[task] for task in common_tasks}
    our_common = {task: our_by_task[task] for task in common_tasks}

    per_task_rows = []
    for task in sorted(set(official_by_task) | set(our_by_task)):
        external_gaps = official_by_task.get(task, [])
        own_gaps = our_by_task.get(task, [])
        solutions = len(official_task_paths.get(task, set()))
        possible_pairs = solutions * (solutions - 1) // 2
        parseable = official_task_parseable[task]
        per_task_rows.append({
            "task": task,
            "official_solutions": solutions,
            "official_pairs": len(external_gaps),
            "official_possible_unordered_pairs": possible_pairs,
            "official_pair_graph_coverage": len(external_gaps) / possible_pairs if possible_pairs else math.nan,
            "official_hard_lt_1e2_share": sum(gap < 1e-2 for gap in external_gaps) / len(external_gaps) if external_gaps else math.nan,
            "official_median_gap": statistics.median(external_gaps) if external_gaps else math.nan,
            "official_trajectory_parseable_pairs": parseable,
            "official_same_trajectory_share": official_task_same[task] / parseable if parseable else math.nan,
            "our_pairs": len(own_gaps),
            "our_hard_lt_1e2_share": sum(gap < 1e-2 for gap in own_gaps) / len(own_gaps) if own_gaps else math.nan,
            "our_median_gap": statistics.median(own_gaps) if own_gaps else math.nan,
            "common_task": task in common_tasks,
        })

    coverage_values = [
        row["official_pair_graph_coverage"]
        for row in per_task_rows
        if row["official_solutions"] >= 2 and math.isfinite(row["official_pair_graph_coverage"])
    ]
    appearance_values = list(appearances.values())
    result = {
        "status": "descriptive external pair-graph audit; no official judge predictions",
        "input_locks": observed_locks,
        "official": {
            "rows": len(official_rows),
            "tasks": len(official_by_task),
            "unique_solution_paths": len(appearances),
            "unique_unordered_pairs": len(set(pair_keys)),
            "duplicate_unordered_pair_rows": len(pair_keys) - len(set(pair_keys)),
            "solution_appearance_median": statistics.median(appearance_values),
            "solution_appearance_mean": statistics.mean(appearance_values),
            "solution_appearance_max": max(appearance_values),
            "pair_graph_coverage_task_median": statistics.median(coverage_values),
            "pair_graph_coverage_task_min": min(coverage_values),
            "pair_graph_coverage_task_max": max(coverage_values),
            "trajectory_parseable_pairs": trajectory_parseable,
            "same_trajectory_pairs": same_trajectory,
            "same_trajectory_share_of_parseable": same_trajectory / trajectory_parseable,
            "gap": gap_summary(official_by_task),
        },
        "our_b0": {
            "rows_total": len(our_rows),
            "rows_finite_gap": sum(len(values) for values in our_by_task.values()),
            "rows_excluded_nonfinite_gap": len(own_nonfinite_gap_rows),
            "excluded_nonfinite_gap_rows": own_nonfinite_gap_rows,
            "tasks": len(our_by_task),
            "unique_unordered_pairs": len(set(our_pair_keys)),
            "duplicate_unordered_pair_rows": len(our_pair_keys) - len(set(our_pair_keys)),
            "gap": gap_summary(our_by_task),
        },
        "common_tasks": {
            "names": common_tasks,
            "official": gap_summary(official_common),
            "our_b0": gap_summary(our_common),
        },
        "interpretation_guard": {
            "contains_official_predictions": False,
            "causal_explanation_allowed": False,
            "cross_task_raw_gap_scale_warning": True,
            "purpose": "audit pairing distribution and dependence before any verified-report judge rerun",
        },
    }
    out_json.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    with out_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(per_task_rows[0]))
        writer.writeheader()
        writer.writerows(per_task_rows)
    print(
        "PBE_EXTERNAL_PAIR_AUDIT",
        f"official_rows={len(official_rows)}",
        f"solutions={len(appearances)}",
        f"same_trajectory_share={same_trajectory / trajectory_parseable:.6f}",
        f"official_hard={result['official']['gap']['hard_lt_1e2_pair_share']:.6f}",
        f"our_hard={result['our_b0']['gap']['hard_lt_1e2_pair_share']:.6f}",
        f"official_common_hard={result['common_tasks']['official']['hard_lt_1e2_pair_share']:.6f}",
        f"our_common_hard={result['common_tasks']['our_b0']['hard_lt_1e2_pair_share']:.6f}",
        f"our_nonfinite_excluded={len(own_nonfinite_gap_rows)}",
    )
    print(f"WROTE {out_json} {out_csv}")


if __name__ == "__main__":
    main()
