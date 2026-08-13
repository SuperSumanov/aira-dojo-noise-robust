"""Structural comparison of the pinned alignment grid and HF auto parquet."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import pyarrow.parquet as pq


def task_from_path(path: str) -> str:
    marker = "solutions_subset_50/"
    if marker not in path:
        raise RuntimeError(f"unrecognized path: {path}")
    return path.split(marker, 1)[1].split("/", 1)[0]


def released_short_name(path: str) -> str:
    value = Path(path)
    return value.stem[-4:] + value.suffix


def winner(score_by_path: dict[str, float], lower: bool) -> str | None:
    if not all(math.isfinite(value) for value in score_by_path.values()):
        return None
    ordered = sorted(score_by_path.items(), key=lambda item: item[1], reverse=not lower)
    if ordered[0][1] == ordered[1][1]:
        return None
    return ordered[0][0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--master", type=Path, required=True)
    parser.add_argument("--parquet", type=Path, required=True)
    args = parser.parse_args()
    sources = json.loads(args.manifest.read_text(encoding="utf-8"))["files"]
    primary_indices = {
        index
        for index, source in enumerate(sources)
        if source["model_family"] == "deepseek" and source["release_run"] == 1
    }
    alignment: dict[tuple[str, str, str], dict[str, object]] = {}
    with args.master.open(encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            if row["source_index"] not in primary_indices:
                continue
            raw_short_paths = [released_short_name(str(value)) for value in row["solution_paths"]]
            paths = tuple(sorted(raw_short_paths))
            key = (str(row["task"]), paths[0], paths[1])
            if key in alignment:
                raise RuntimeError("duplicate primary pair across tasks")
            scores = [float(value) for value in row["scores"]]
            status = (
                "nonfinite"
                if not all(math.isfinite(value) for value in scores)
                else "tie"
                if scores[0] == scores[1]
                else "finite_nontie"
            )
            alignment[key] = {
                "task": row["task"],
                "scores": scores,
                "score_by_path": dict(zip(raw_short_paths, scores, strict=True)),
                "status": status,
                "groundtruth": row["groundtruth_best_index"],
                "is_lower_better": row["is_lower_better"],
            }

    table = pq.read_table(args.parquet, columns=["paths", "scores", "is_lower_better"])
    parquet: dict[tuple[str, str, str], dict[str, object]] = {}
    full_paths_by_short: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in table.to_pylist():
        raw_paths = [str(value) for value in row["paths"]]
        tasks = {task_from_path(path) for path in raw_paths}
        if len(tasks) != 1:
            raise RuntimeError("cross-task parquet pair")
        task = next(iter(tasks))
        paths = tuple(sorted(released_short_name(value) for value in raw_paths))
        for raw_path, short_path in zip(raw_paths, [released_short_name(value) for value in raw_paths], strict=True):
            full_paths_by_short[(task, short_path)].add(raw_path)
        key = (task, paths[0], paths[1])
        if key in parquet:
            raise RuntimeError("duplicate parquet pair")
        raw_scores = [float(value) for value in row["scores"]]
        parquet[key] = {
            "score_by_path": {
                released_short_name(raw_path): score
                for raw_path, score in zip(raw_paths, raw_scores, strict=True)
            },
            "is_lower_better": bool(row["is_lower_better"]),
        }
    collisions = {key: values for key, values in full_paths_by_short.items() if len(values) > 1}
    if collisions:
        raise RuntimeError(f"released short-name collision count={len(collisions)}")

    alignment_keys = set(alignment)
    parquet_keys = set(parquet)
    missing = alignment_keys - parquet_keys
    extra = parquet_keys - alignment_keys
    statuses = Counter(str(alignment[key]["status"]) for key in missing)
    tasks = Counter(str(alignment[key]["task"]) for key in missing)
    print(
        "PARQUET_GRID_COMPARE",
        f"alignment={len(alignment_keys)}",
        f"parquet={len(parquet_keys)}",
        f"common={len(alignment_keys & parquet_keys)}",
        f"missing={len(missing)}",
        f"extra={len(extra)}",
        f"missing_status={dict(sorted(statuses.items()))}",
    )
    print("PARQUET_MISSING_TASKS", json.dumps(dict(sorted(tasks.items())), sort_keys=True))
    finite_missing = [key for key in sorted(missing) if alignment[key]["status"] == "finite_nontie"]
    endpoint_counts: Counter[tuple[str, str]] = Counter(
        (key[0], path) for key in finite_missing for path in key[1:]
    )
    print(
        "PARQUET_FINITE_MISSING_ENDPOINT_REUSE",
        f"pairs={len(finite_missing)}",
        f"unique_endpoints={len(endpoint_counts)}",
        f"max_reuse={max(endpoint_counts.values(), default=0)}",
    )
    print(
        "PARQUET_EXTRA_TASKS",
        json.dumps(dict(sorted(Counter(key[0] for key in extra).items())), sort_keys=True),
    )
    score_mismatch = Counter()
    direction_mismatch = Counter()
    winner_mismatch = Counter()
    common_comparable = Counter()
    for key in alignment_keys & parquet_keys:
        left = alignment[key]
        right = parquet[key]
        if left["score_by_path"] != right["score_by_path"]:
            score_mismatch[key[0]] += 1
        if left["is_lower_better"] != right["is_lower_better"]:
            direction_mismatch[key[0]] += 1
        left_winner = winner(left["score_by_path"], bool(left["is_lower_better"]))
        right_winner = winner(right["score_by_path"], bool(right["is_lower_better"]))
        if left_winner is not None and right_winner is not None:
            common_comparable[key[0]] += 1
            if left_winner != right_winner:
                winner_mismatch[key[0]] += 1
    print(
        "PARQUET_COMMON_TRUTH",
        f"common={len(alignment_keys & parquet_keys)}",
        f"score_mismatch={sum(score_mismatch.values())}",
        f"direction_mismatch={sum(direction_mismatch.values())}",
        f"winner_comparable={sum(common_comparable.values())}",
        f"winner_mismatch={sum(winner_mismatch.values())}",
        f"score_mismatch_tasks={json.dumps(dict(sorted(score_mismatch.items())), sort_keys=True)}",
        f"winner_mismatch_tasks={json.dumps(dict(sorted(winner_mismatch.items())), sort_keys=True)}",
    )
    for key in sorted(alignment_keys & parquet_keys)[:3]:
        print(
            "PARQUET_COMMON_SAMPLE",
            json.dumps(key),
            f"alignment={json.dumps(alignment[key]['score_by_path'], sort_keys=True)}",
            f"parquet={json.dumps(parquet[key]['score_by_path'], sort_keys=True)}",
        )


if __name__ == "__main__":
    main()
