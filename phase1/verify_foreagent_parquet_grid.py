"""Independent release-grid verifier; does not import the comparison script."""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

import pyarrow.parquet as pq


SHORT_ID = re.compile(r"([0-9a-f]{4})\.py$")


def short_id(path: str) -> str:
    match = SHORT_ID.search(path)
    if match is None:
        raise RuntimeError(f"missing released id: {path}")
    return match.group(1)


def task(path: str) -> str:
    return path.split("solutions_subset_50/", 1)[1].split("/", 1)[0]


def best(scores: dict[str, float], lower: bool) -> str | None:
    values = list(scores.items())
    if len(values) != 2 or not all(math.isfinite(value) for _, value in values):
        return None
    values.sort(key=lambda item: item[1], reverse=not lower)
    return None if values[0][1] == values[1][1] else values[0][0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--master", type=Path, required=True)
    parser.add_argument("--parquet", type=Path, required=True)
    args = parser.parse_args()
    sources = json.loads(args.manifest.read_text(encoding="utf-8"))["files"]
    selected = {
        index
        for index, source in enumerate(sources)
        if source["model_family"] == "deepseek" and source["release_run"] == 2
    }
    left: dict[tuple[str, frozenset[str]], tuple[dict[str, float], bool]] = {}
    with args.master.open(encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            if row["source_index"] not in selected:
                continue
            identifiers = [short_id(str(value)) for value in row["solution_paths"]]
            key = (str(row["task"]), frozenset(identifiers))
            if key in left or len(key[1]) != 2:
                raise RuntimeError("duplicate/degenerate compact key")
            left[key] = (
                {
                    identifier: float(score)
                    for identifier, score in zip(identifiers, row["scores"], strict=True)
                },
                bool(row["is_lower_better"]),
            )

    right: dict[tuple[str, frozenset[str]], tuple[dict[str, float], bool]] = {}
    table = pq.read_table(args.parquet, columns=["paths", "scores", "is_lower_better"])
    for row in table.to_pylist():
        paths = [str(value) for value in row["paths"]]
        tasks = {task(value) for value in paths}
        if len(tasks) != 1:
            raise RuntimeError("cross-task parquet pair")
        identifiers = [short_id(value) for value in paths]
        key = (next(iter(tasks)), frozenset(identifiers))
        if key in right or len(key[1]) != 2:
            raise RuntimeError("duplicate/degenerate parquet key")
        right[key] = (
            {
                identifier: float(score)
                for identifier, score in zip(identifiers, row["scores"], strict=True)
            },
            bool(row["is_lower_better"]),
        )

    left_keys = set(left)
    right_keys = set(right)
    common = left_keys & right_keys
    comparable = 0
    winner_mismatch = 0
    for key in common:
        left_winner = best(*left[key])
        right_winner = best(*right[key])
        if left_winner is not None and right_winner is not None:
            comparable += 1
            winner_mismatch += int(left_winner != right_winner)
    print(
        "FOREAGENT_PARQUET_GRID_INDEPENDENT_VERIFY_PASS",
        f"alignment={len(left_keys)}",
        f"parquet={len(right_keys)}",
        f"common={len(common)}",
        f"alignment_only={len(left_keys - right_keys)}",
        f"parquet_only={len(right_keys - left_keys)}",
        f"winner_comparable={comparable}",
        f"winner_mismatch={winner_mismatch}",
    )


if __name__ == "__main__":
    main()
