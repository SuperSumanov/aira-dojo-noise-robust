"""Inspect non-finite official scores without reading prediction outcomes."""

from __future__ import annotations

import argparse
import collections
import json
import math
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--master", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    affected_rows = []
    pair_sources: dict[tuple[str, tuple[str, str]], set[int]] = collections.defaultdict(set)
    pair_score_repr: dict[tuple[str, tuple[str, str]], set[tuple[str, str]]] = collections.defaultdict(set)
    with args.master.open("r", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            scores = row["scores"]
            try:
                numeric = [float(scores[0]), float(scores[1])]
            except (TypeError, ValueError):
                numeric = [math.nan, math.nan]
            if all(math.isfinite(value) for value in numeric):
                continue
            source_index = row["source_index"]
            source = manifest["files"][source_index]
            pair_key = (row["task"], tuple(sorted(row["solution_paths"])))
            pair_sources[pair_key].add(source_index)
            pair_score_repr[pair_key].add((repr(scores[0]), repr(scores[1])))
            affected_rows.append(
                {
                    "source_index": source_index,
                    "task": source["task"],
                    "model": source["model_family"],
                    "release_run": source["release_run"],
                    "pair": list(pair_key[1]),
                    "scores_repr": [repr(scores[0]), repr(scores[1])],
                    "is_lower_better": row["is_lower_better"],
                    "groundtruth_best_index": row["groundtruth_best_index"],
                }
            )
    source_counts = collections.Counter(row["source_index"] for row in affected_rows)
    task_counts = collections.Counter(row["task"] for row in affected_rows)
    print(
        "FOREAGENT_NONFINITE_STRUCTURE",
        f"rows={len(affected_rows)}",
        f"unique_pairs={len(pair_sources)}",
        f"tasks={len(task_counts)}",
        f"sources={len(source_counts)}",
        f"pairs_in_all_6_sources={sum(len(value) == 6 for value in pair_sources.values())}",
    )
    for pair_key in sorted(pair_sources):
        print(
            json.dumps(
                {
                    "task": pair_key[0],
                    "pair": list(pair_key[1]),
                    "source_indices": sorted(pair_sources[pair_key]),
                    "score_reprs": sorted(pair_score_repr[pair_key]),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )


if __name__ == "__main__":
    main()
