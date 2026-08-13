"""Inspect released pair grids and score truth without prediction outcomes."""

from __future__ import annotations

import argparse
import collections
import json
import math
from pathlib import Path
from typing import Any


def canonical(value: Any) -> Any:
    numeric = float(value)
    if math.isnan(numeric):
        return "nan"
    if numeric == math.inf:
        return "+inf"
    if numeric == -math.inf:
        return "-inf"
    return numeric


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--master", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    sources = manifest["files"]
    grids: dict[int, dict[tuple[str, str], tuple[Any, Any, bool]]] = collections.defaultdict(dict)
    with args.master.open("r", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            source_index = row["source_index"]
            paths = row["solution_paths"]
            scores = row["scores"]
            score_by_path = tuple(
                sorted(((paths[0], canonical(scores[0])), (paths[1], canonical(scores[1]))))
            )
            numeric_scores = [float(scores[0]), float(scores[1])]
            finite = all(math.isfinite(value) for value in numeric_scores)
            if not finite or numeric_scores[0] == numeric_scores[1]:
                true_path = None
            elif row["is_lower_better"]:
                true_path = paths[0] if numeric_scores[0] < numeric_scores[1] else paths[1]
            else:
                true_path = paths[0] if numeric_scores[0] > numeric_scores[1] else paths[1]
            pair = tuple(sorted(paths))
            if pair in grids[source_index]:
                raise RuntimeError(f"duplicate pair source={source_index}")
            grids[source_index][pair] = (score_by_path, true_path, row["is_lower_better"])

    task_sources: dict[str, list[int]] = collections.defaultdict(list)
    for source_index, source in enumerate(sources):
        task_sources[source["task"]].append(source_index)
    affected = []
    for task, indices in sorted(task_sources.items()):
        family_indices = {
            family: [index for index in indices if sources[index]["model_family"] == family]
            for family in ("deepseek", "gpt")
        }
        family_equal = {
            family: all(set(grids[index]) == set(grids[family_indices[family][0]]) for index in family_indices[family])
            for family in family_indices
        }
        deepseek_grid = set(grids[family_indices["deepseek"][0]])
        gpt_grid = set(grids[family_indices["gpt"][0]])
        union = set().union(*(set(grids[index]) for index in indices))
        intersection = set(grids[indices[0]]).intersection(*(set(grids[index]) for index in indices[1:]))
        common_truth_mismatches = 0
        for pair in intersection:
            reference = grids[indices[0]][pair]
            if any(grids[index][pair] != reference for index in indices[1:]):
                common_truth_mismatches += 1
        if not all(family_equal.values()) or deepseek_grid != gpt_grid or common_truth_mismatches:
            affected.append(
                {
                    "task": task,
                    "source_sizes": {
                        str(index): {
                            "model": sources[index]["model_family"],
                            "run": sources[index]["release_run"],
                            "pairs": len(grids[index]),
                        }
                        for index in indices
                    },
                    "within_deepseek_equal": family_equal["deepseek"],
                    "within_gpt_equal": family_equal["gpt"],
                    "deepseek_only_count": len(deepseek_grid - gpt_grid),
                    "gpt_only_count": len(gpt_grid - deepseek_grid),
                    "deepseek_only_examples": [list(pair) for pair in sorted(deepseek_grid - gpt_grid)[:10]],
                    "gpt_only_examples": [list(pair) for pair in sorted(gpt_grid - deepseek_grid)[:10]],
                    "union_pairs": len(union),
                    "intersection_pairs": len(intersection),
                    "common_truth_mismatches": common_truth_mismatches,
                }
            )
    print(
        "FOREAGENT_PAIR_GRID_STRUCTURE",
        f"tasks={len(task_sources)}",
        f"affected_tasks={len(affected)}",
        f"within_deepseek_mismatch_tasks={sum(not row['within_deepseek_equal'] for row in affected)}",
        f"within_gpt_mismatch_tasks={sum(not row['within_gpt_equal'] for row in affected)}",
        f"cross_model_mismatch_tasks={sum(row['deepseek_only_count'] > 0 or row['gpt_only_count'] > 0 for row in affected)}",
        f"truth_mismatch_tasks={sum(row['common_truth_mismatches'] > 0 for row in affected)}",
    )
    for row in affected:
        print(json.dumps(row, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
