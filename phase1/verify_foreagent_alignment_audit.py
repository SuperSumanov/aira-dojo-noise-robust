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
            scores_finite = all(math.isfinite(value) for value in scores)
            if not scores_finite:
                true_path = None
                label_status = "nonfinite_score"
            elif scores[0] == scores[1]:
                true_path = None
                label_status = "exact_tie"
            elif lower:
                true_path = paths[0] if scores[0] < scores[1] else paths[1]
                label_status = "finite_nontie"
            else:
                true_path = paths[0] if scores[0] > scores[1] else paths[1]
                label_status = "finite_nontie"
            predicted_index = index(row["prediction_best_index"])
            predicted_path = paths[predicted_index] if predicted_index is not None else None
            def canonical_score(value: float) -> Any:
                if math.isnan(value):
                    return "nan"
                if value == math.inf:
                    return "+inf"
                if value == -math.inf:
                    return "-inf"
                return value

            records[source_index][key] = {
                "task": source["task"],
                "model": source["model_family"],
                "run": source["release_run"],
                "scores": tuple(
                    sorted(
                        (
                            (paths[0], canonical_score(scores[0])),
                            (paths[1], canonical_score(scores[1])),
                        )
                    )
                ),
                "lower": lower,
                "true": true_path,
                "gap": abs(scores[0] - scores[1]) if scores_finite else None,
                "label_status": label_status,
                "correct": float(predicted_path == true_path) if true_path is not None else None,
            }

    task_sources: dict[str, list[int]] = defaultdict(list)
    for source_index, source in enumerate(sources):
        task_sources[source["task"]].append(source_index)
    references: dict[tuple[str, str], dict[tuple[str, str], dict[str, Any]]] = {}
    model_sources_by_task: dict[tuple[str, str], list[int]] = {}
    grid_totals = {
        "deepseek": {"union_pairs": 0, "intersection_pairs": 0, "excluded_incomplete_triplicate_pairs": 0},
        "gpt": {"union_pairs": 0, "intersection_pairs": 0, "excluded_incomplete_triplicate_pairs": 0},
    }
    for task, indices in task_sources.items():
        if len(indices) != 6:
            raise RuntimeError("source count mismatch")
        for model in ("deepseek", "gpt"):
            model_sources = sorted(
                [index_value for index_value in indices if sources[index_value]["model_family"] == model],
                key=lambda index_value: sources[index_value]["release_run"],
            )
            if len(model_sources) != 3:
                raise RuntimeError("model source count mismatch")
            model_sources_by_task[(model, task)] = model_sources
            key_sets = [set(records[index_value]) for index_value in model_sources]
            union_keys = set().union(*key_sets)
            intersection_keys = set.intersection(*key_sets)
            ratio = len(intersection_keys) / len(union_keys) if union_keys else 0.0
            if model == "deepseek" and any(keys != key_sets[0] for keys in key_sets[1:]):
                raise RuntimeError("primary grid mismatch")
            if model == "gpt" and ratio < 0.99:
                raise RuntimeError("GPT intersection support failure")
            grid_totals[model]["union_pairs"] += len(union_keys)
            grid_totals[model]["intersection_pairs"] += len(intersection_keys)
            grid_totals[model]["excluded_incomplete_triplicate_pairs"] += len(
                union_keys - intersection_keys
            )
            reference: dict[tuple[str, str], dict[str, Any]] = {}
            for key in intersection_keys:
                truth = records[model_sources[0]][key]
                for source_index in model_sources[1:]:
                    current = records[source_index][key]
                    for field in ("scores", "lower", "true", "gap", "label_status"):
                        if current[field] != truth[field]:
                            raise RuntimeError("within-model truth mismatch")
                reference[key] = truth
            references[(model, task)] = reference

        for key in set(references[("deepseek", task)]) & set(references[("gpt", task)]):
            deepseek_truth = references[("deepseek", task)][key]
            gpt_truth = references[("gpt", task)][key]
            for field in ("scores", "lower", "true", "gap", "label_status"):
                if deepseek_truth[field] != gpt_truth[field]:
                    raise RuntimeError("cross-model truth mismatch")

    primary_rows = [
        row
        for task in task_sources
        for row in references[("deepseek", task)].values()
    ]
    base_pairs = len(primary_rows)
    ties = sum(row["label_status"] == "exact_tie" for row in primary_rows)
    nonfinite = sum(row["label_status"] == "nonfinite_score" for row in primary_rows)
    cross_model_common_pairs = sum(
        len(set(references[("deepseek", task)]) & set(references[("gpt", task)]))
        for task in task_sources
    )
    integrity = summary["integrity"]
    if summary.get("schema_version") != 2:
        raise RuntimeError("unexpected summary schema")
    if base_pairs != integrity["primary_base_pairs"] or base_pairs != integrity["base_pairs"]:
        raise RuntimeError("base pair count mismatch")
    if ties != integrity["exact_score_ties"]:
        raise RuntimeError("tie count mismatch")
    if nonfinite != integrity["nonfinite_score_pairs"]:
        raise RuntimeError("nonfinite count mismatch")
    if grid_totals != integrity["model_grid_totals"]:
        raise RuntimeError("model grid totals mismatch")
    if cross_model_common_pairs != integrity["cross_model_common_pairs"]:
        raise RuntimeError("cross-model common count mismatch")
    for model in ("deepseek", "gpt"):
        model_rows = [
            row
            for task in task_sources
            for row in references[(model, task)].values()
        ]
        expected_counts = {
            "exact_ties": sum(row["label_status"] == "exact_tie" for row in model_rows),
            "nonfinite_score_pairs": sum(
                row["label_status"] == "nonfinite_score" for row in model_rows
            ),
            "finite_directional_pairs": sum(
                row["label_status"] == "finite_nontie" for row in model_rows
            ),
        }
        if expected_counts != integrity["label_counts_by_model"][model]:
            raise RuntimeError(f"{model} label counts mismatch")

    pair_accuracy: dict[tuple[str, str, tuple[str, str]], float] = {}
    quartiles: dict[tuple[str, str], dict[tuple[str, str], int]] = {}
    for model in ("deepseek", "gpt"):
        for task in task_sources:
            reference = references[(model, task)]
            quartiles[(model, task)] = quartile_map(
                {
                    key: row["gap"]
                    for key, row in reference.items()
                    if row["label_status"] == "finite_nontie"
                }
            )
            model_sources = model_sources_by_task[(model, task)]
            for key, truth in reference.items():
                if truth["label_status"] != "finite_nontie":
                    continue
                correctness = [records[source_index][key]["correct"] for source_index in model_sources]
                if any(value is None for value in correctness):
                    raise RuntimeError("missing directional correctness")
                pair_accuracy[(model, task, key)] = sum(correctness) / 3.0

    task_accuracy: dict[str, list[float]] = {"deepseek": [], "gpt": []}
    low_by_model: dict[str, dict[str, float]] = {"deepseek": {}, "gpt": {}}
    high_by_model: dict[str, dict[str, float]] = {"deepseek": {}, "gpt": {}}
    for model in ("deepseek", "gpt"):
        for task in sorted(task_sources):
            values = [
                value
                for (row_model, row_task, _), value in pair_accuracy.items()
                if row_model == model and row_task == task
            ]
            task_accuracy[model].append(sum(values) / len(values))
            low = [
                value
                for (row_model, row_task, key), value in pair_accuracy.items()
                if row_model == model and row_task == task and quartiles[(model, task)][key] == 0
            ]
            high = [
                value
                for (row_model, row_task, key), value in pair_accuracy.items()
                if row_model == model and row_task == task and quartiles[(model, task)][key] == 3
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
        f"tasks={len(task_sources)}",
        f"primary_pairs={base_pairs}",
        f"ties={ties}",
        f"nonfinite={nonfinite}",
        f"gpt_intersection={grid_totals['gpt']['intersection_pairs']}",
        f"gpt_excluded={grid_totals['gpt']['excluded_incomplete_triplicate_pairs']}",
        f"deepseek={summary['overall']['deepseek']['task_macro']:.6f}",
        f"deepseek_q1={summary['primary_gate']['lowest_quartile']['task_macro']:.6f}",
        f"deepseek_q4_minus_q1={summary['primary_gate']['highest_minus_lowest']['mean']:.6f}",
        f"decision={summary['primary_gate']['decision']}",
    )


if __name__ == "__main__":
    main()
