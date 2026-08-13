"""Independent central-number verifier for the FOREAGENT alignment audit.

This file intentionally does not import audit_foreagent_alignments.py.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np


SEED = 20260813
B = 10_000


def close(actual: float, expected: float, name: str, tolerance: float = 1e-12) -> None:
    if not math.isclose(actual, expected, rel_tol=0.0, abs_tol=tolerance):
        raise RuntimeError(f"{name}: {actual} != {expected}")


def index(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value in (0, 1) else None


def rng(label: str) -> np.random.Generator:
    label_seed = int.from_bytes(hashlib.sha256(label.encode("utf-8")).digest()[:8], "big")
    return np.random.default_rng(label_seed ^ SEED)


def task_bootstrap_ci(task_values: list[float], label: str) -> list[float]:
    values = np.asarray(task_values, dtype=float)
    draws = rng(label).integers(0, len(values), size=(B, len(values)))
    boot = values[draws].mean(axis=1)
    return [float(value) for value in np.quantile(boot, [0.025, 0.975])]


def quartile_map(gaps: dict[tuple[str, str], float]) -> dict[tuple[str, str], int]:
    rows = sorted(gaps.items(), key=lambda item: (item[1], item[0]))
    result: dict[tuple[str, str], int] = {}
    start = 0
    while start < len(rows):
        end = start + 1
        while end < len(rows) and rows[end][1] == rows[start][1]:
            end += 1
        percentile = (start + end) / (2.0 * len(rows))
        bucket = min(3, int(percentile * 4.0))
        for offset in range(start, end):
            result[rows[offset][0]] = bucket
        start = end
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--master", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    summary = json.loads(args.summary.read_text(encoding="utf-8"))
    sources = manifest["files"]
    if len(sources) != 156:
        raise RuntimeError("expected 156 sources")

    # Source -> unordered pair -> minimal record.  This implementation derives
    # correctness directly from the compact primitive fields.
    records: dict[int, dict[tuple[str, str], dict[str, Any]]] = defaultdict(dict)
    with args.master.open("r", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            source_index = row["source_index"]
            source = sources[source_index]
            if (
                row["task"] != source["task"]
                or row["model_family"] != source["model_family"]
                or row["release_run"] != source["release_run"]
            ):
                raise RuntimeError("source metadata mismatch")
            paths = row["solution_paths"]
            scores = [float(value) for value in row["scores"]]
            key = tuple(sorted(paths))
            if key in records[source_index]:
                raise RuntimeError("duplicate pair")
            lower = row["is_lower_better"]
            if scores[0] == scores[1]:
                true_path = None
            elif lower:
                true_path = paths[0] if scores[0] < scores[1] else paths[1]
            else:
                true_path = paths[0] if scores[0] > scores[1] else paths[1]
            predicted_index = index(row["prediction_best_index"])
            predicted_path = paths[predicted_index] if predicted_index is not None else None
            confidence = row["confidence"]
            valid = (
                true_path is not None
                and predicted_path is not None
                and isinstance(confidence, (int, float))
                and not isinstance(confidence, bool)
                and math.isfinite(float(confidence))
                and 0.0 <= float(confidence) <= 1.0
            )
            records[source_index][key] = {
                "task": source["task"],
                "model": source["model_family"],
                "run": source["release_run"],
                "scores": tuple(sorted(((paths[0], scores[0]), (paths[1], scores[1])))),
                "lower": lower,
                "true": true_path,
                "gap": abs(scores[0] - scores[1]),
                "correct": float(predicted_path == true_path) if valid else None,
            }

    task_sources: dict[str, list[int]] = defaultdict(list)
    for source_index, source in enumerate(sources):
        task_sources[source["task"]].append(source_index)
    base_pairs = 0
    ties = 0
    references: dict[str, dict[tuple[str, str], dict[str, Any]]] = {}
    for task, indices in task_sources.items():
        if len(indices) != 6:
            raise RuntimeError("source count mismatch")
        reference = records[indices[0]]
        base_pairs += len(reference)
        ties += sum(row["true"] is None for row in reference.values())
        for source_index in indices[1:]:
            current = records[source_index]
            if set(current) != set(reference):
                raise RuntimeError("grid mismatch")
            for key in reference:
                for field in ("scores", "lower", "true", "gap"):
                    if current[key][field] != reference[key][field]:
                        raise RuntimeError("truth mismatch")
        references[task] = reference

    if base_pairs != summary["integrity"]["base_pairs"]:
        raise RuntimeError("base pair count mismatch")
    if ties != summary["integrity"]["exact_score_ties"]:
        raise RuntimeError("tie count mismatch")

    pair_accuracy: dict[tuple[str, str, tuple[str, str]], float] = {}
    quartiles: dict[str, dict[tuple[str, str], int]] = {}
    for task, reference in references.items():
        quartiles[task] = quartile_map(
            {key: row["gap"] for key, row in reference.items() if row["true"] is not None}
        )
        for model in ("deepseek", "gpt"):
            model_sources = [
                source_index
                for source_index in task_sources[task]
                if sources[source_index]["model_family"] == model
            ]
            for key, truth in reference.items():
                if truth["true"] is None:
                    continue
                correctness = [records[source_index][key]["correct"] for source_index in model_sources]
                valid = [value for value in correctness if value is not None]
                if valid:
                    pair_accuracy[(model, task, key)] = sum(valid) / len(valid)

    task_accuracy: dict[str, list[float]] = {"deepseek": [], "gpt": []}
    low_by_model: dict[str, dict[str, float]] = {"deepseek": {}, "gpt": {}}
    high_by_model: dict[str, dict[str, float]] = {"deepseek": {}, "gpt": {}}
    for model in ("deepseek", "gpt"):
        for task in sorted(references):
            values = [
                value
                for (row_model, row_task, _), value in pair_accuracy.items()
                if row_model == model and row_task == task
            ]
            task_accuracy[model].append(sum(values) / len(values))
            low = [
                value
                for (row_model, row_task, key), value in pair_accuracy.items()
                if row_model == model and row_task == task and quartiles[task][key] == 0
            ]
            high = [
                value
                for (row_model, row_task, key), value in pair_accuracy.items()
                if row_model == model and row_task == task and quartiles[task][key] == 3
            ]
            low_by_model[model][task] = sum(low) / len(low)
            high_by_model[model][task] = sum(high) / len(high)

    for model in ("deepseek", "gpt"):
        overall = sum(task_accuracy[model]) / len(task_accuracy[model])
        close(overall, summary["overall"][model]["task_macro"], f"{model} overall")
        low_values = [low_by_model[model][task] for task in sorted(low_by_model[model])]
        low_point = sum(low_values) / len(low_values)
        low_summary = (
            summary["primary_gate"]["lowest_quartile"]
            if model == "deepseek"
            else summary["gpt_replication"]["lowest_quartile"]
        )
        close(low_point, low_summary["task_macro"], f"{model} q1")
        expected_low_ci = task_bootstrap_ci(low_values, f"quartile:{model}:0")
        for index_value in (0, 1):
            close(expected_low_ci[index_value], low_summary["task_macro_ci"][index_value], f"{model} q1 ci")

        differences = [
            high_by_model[model][task] - low_by_model[model][task]
            for task in sorted(low_by_model[model])
        ]
        difference_point = sum(differences) / len(differences)
        difference_summary = summary["highest_minus_lowest_quartile"][model]
        close(difference_point, difference_summary["mean"], f"{model} q4-q1")
        expected_difference_ci = task_bootstrap_ci(differences, f"paired-difference:{model}")
        for index_value in (0, 1):
            close(
                expected_difference_ci[index_value],
                difference_summary["ci"][index_value],
                f"{model} q4-q1 ci",
            )

    print(
        "FOREAGENT_ALIGNMENT_INDEPENDENT_VERIFY_PASS",
        f"sources={len(sources)}",
        f"tasks={len(references)}",
        f"pairs={base_pairs}",
        f"ties={ties}",
        f"deepseek={summary['overall']['deepseek']['task_macro']:.6f}",
        f"deepseek_q1={summary['primary_gate']['lowest_quartile']['task_macro']:.6f}",
        f"deepseek_q4_minus_q1={summary['primary_gate']['highest_minus_lowest']['mean']:.6f}",
        f"decision={summary['primary_gate']['decision']}",
    )


if __name__ == "__main__":
    main()
