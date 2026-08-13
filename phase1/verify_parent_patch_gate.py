#!/usr/bin/env python3
"""Independent stdlib-only verifier for parent_patch_gate.py outputs.

This file deliberately does not import the experiment implementation.
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
from pathlib import Path
from typing import Any, Sequence


SEED = 887
REPS = 4_000
EPSILON = 1e-12


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def close(left: float, right: float, tolerance: float = 1e-10) -> None:
    if not math.isclose(float(left), float(right), rel_tol=tolerance, abs_tol=tolerance):
        raise AssertionError(f"{left} != {right}")


def read_predictions(path: Path, expected_split: str) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise AssertionError(f"empty predictions: {path}")
    for row in rows:
        if row["split"] != expected_split:
            raise AssertionError(f"unexpected split {row['split']} in {path}")
        for key in (
            "absolute_better_score",
            "absolute_worse_score",
            "absolute_margin",
            "absolute_hit",
            "patch_better_score",
            "patch_worse_score",
            "patch_margin",
            "patch_hit",
        ):
            row[key] = float(row[key])
            if not math.isfinite(row[key]):
                raise AssertionError(f"non-finite {key}")
        for arm in ("absolute", "patch"):
            close(
                row[f"{arm}_margin"],
                row[f"{arm}_better_score"] - row[f"{arm}_worse_score"],
                tolerance=1e-5,
            )
            expected_hit = (
                1.0
                if row[f"{arm}_margin"] > EPSILON
                else 0.0
                if row[f"{arm}_margin"] < -EPSILON
                else 0.5
            )
            close(row[f"{arm}_hit"], expected_hit)
    return rows


def macro_means(
    rows: Sequence[dict[str, Any]], values: Sequence[float], key: str
) -> dict[str, float]:
    grouped: dict[str, list[float]] = collections.defaultdict(list)
    for row, value in zip(rows, values):
        grouped[str(row[key])].append(float(value))
    return {
        cluster: sum(items) / len(items) for cluster, items in sorted(grouped.items())
    }


def bootstrap(means: dict[str, float], seed: int) -> list[float]:
    values = list(means.values())
    rng = random.Random(seed)
    draws = [sum(rng.choice(values) for _ in values) / len(values) for _ in range(REPS)]
    draws.sort()
    return [draws[int(0.025 * REPS)], draws[int(0.975 * REPS)]]


def summarize(
    rows: Sequence[dict[str, Any]], values: Sequence[float], seed_offset: int
) -> dict[str, Any]:
    runs = macro_means(rows, values, "run")
    tasks = macro_means(rows, values, "task")
    return {
        "overall": sum(values) / len(values),
        "run_macro": sum(runs.values()) / len(runs),
        "task_macro": sum(tasks.values()) / len(tasks),
        "run_macro_ci95": bootstrap(runs, SEED + seed_offset),
        "task_macro_ci95": bootstrap(tasks, SEED + seed_offset + 1),
        "per_task": tasks,
    }


def parent_records(rows: Sequence[dict[str, Any]], arm: str) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    scores: dict[str, float] = {}
    for row in rows:
        grouped[str(row["parent"])].append(row)
        for endpoint in ("better", "worse"):
            card_id = str(row[endpoint])
            score = float(row[f"{arm}_{endpoint}_score"])
            if card_id in scores:
                close(scores[card_id], score)
            scores[card_id] = score
    output: dict[str, dict[str, Any]] = {}
    for parent, parent_rows in grouped.items():
        candidates = {
            str(row[key]) for row in parent_rows for key in ("better", "worse")
        }
        if len(parent_rows) != len(candidates) * (len(candidates) - 1) // 2:
            continue
        losses = collections.Counter({candidate: 0 for candidate in candidates})
        for row in parent_rows:
            losses[str(row["worse"])] += 1
        minimum = min(losses.values())
        true_top = {candidate for candidate, count in losses.items() if count == minimum}
        maximum = max(scores[candidate] for candidate in candidates)
        predicted_top = {
            candidate for candidate in candidates if abs(scores[candidate] - maximum) <= EPSILON
        }
        output[parent] = {
            "value": len(predicted_top & true_top) / len(predicted_top),
            "run": str(parent_rows[0]["run"]),
            "task": str(parent_rows[0]["task"]),
        }
    return output


def parent_summary(records: dict[str, dict[str, Any]], seed_offset: int) -> dict[str, Any]:
    rows = [{"run": row["run"], "task": row["task"]} for row in records.values()]
    values = [float(row["value"]) for row in records.values()]
    result = summarize(rows, values, seed_offset)
    result["parents"] = len(records)
    return result


def task_consistency(
    rows: Sequence[dict[str, Any]], differences: Sequence[float], minimum: int
) -> dict[str, Any]:
    grouped: dict[str, list[float]] = collections.defaultdict(list)
    for row, difference in zip(rows, differences):
        grouped[str(row["task"])].append(float(difference))
    supported = {
        task: {"n": len(values), "difference": sum(values) / len(values)}
        for task, values in sorted(grouped.items())
        if len(values) >= minimum
    }
    nonnegative = sum(item["difference"] >= 0.0 for item in supported.values())
    return {
        "minimum_rows": minimum,
        "supported_tasks": len(supported),
        "nonnegative_tasks": nonnegative,
        "nonnegative_share": nonnegative / len(supported) if supported else 0.0,
        "details": supported,
    }


def reconstruct(rows: Sequence[dict[str, Any]], supported_minimum: int) -> dict[str, Any]:
    output: dict[str, Any] = {}
    parent_tables: dict[str, dict[str, dict[str, Any]]] = {}
    for index, arm in enumerate(("absolute", "patch")):
        hits = [float(row[f"{arm}_hit"]) for row in rows]
        parent_tables[arm] = parent_records(rows, arm)
        output[arm] = {
            "pair_accuracy": summarize(rows, hits, 20 + index * 10),
            "parent_top1": parent_summary(parent_tables[arm], 40 + index * 10),
        }
    pair_differences = [
        float(row["patch_hit"]) - float(row["absolute_hit"]) for row in rows
    ]
    parent_differences = {
        parent: {
            **parent_tables["patch"][parent],
            "value": float(parent_tables["patch"][parent]["value"])
            - float(parent_tables["absolute"][parent]["value"]),
        }
        for parent in parent_tables["absolute"]
    }
    output["pair_difference"] = summarize(rows, pair_differences, 100)
    output["parent_top1_difference"] = parent_summary(parent_differences, 110)
    output["task_consistency"] = task_consistency(rows, pair_differences, supported_minimum)
    output["oracle_pair_accuracy"] = 1.0
    return output


def check_summary(observed: dict[str, Any], expected: dict[str, Any]) -> None:
    for arm in ("absolute", "patch"):
        for metric in ("pair_accuracy", "parent_top1"):
            for key in ("overall", "run_macro", "task_macro"):
                close(observed[arm][metric][key], expected[arm][metric][key])
            close(observed[arm][metric]["run_macro_ci95"][0], expected[arm][metric]["run_macro_ci95"][0])
            close(observed[arm][metric]["run_macro_ci95"][1], expected[arm][metric]["run_macro_ci95"][1])
            close(observed[arm][metric]["task_macro_ci95"][0], expected[arm][metric]["task_macro_ci95"][0])
            close(observed[arm][metric]["task_macro_ci95"][1], expected[arm][metric]["task_macro_ci95"][1])
    for metric in ("pair_difference", "parent_top1_difference"):
        for key in ("overall", "run_macro", "task_macro"):
            close(observed[metric][key], expected[metric][key])
        for ci in ("run_macro_ci95", "task_macro_ci95"):
            close(observed[metric][ci][0], expected[metric][ci][0])
            close(observed[metric][ci][1], expected[metric][ci][1])
    assert observed["task_consistency"] == expected["task_consistency"]
    close(observed["oracle_pair_accuracy"], 1.0)


def discovery_checks(
    audit: dict[str, Any], comparison: dict[str, Any], runtime: float
) -> dict[str, bool]:
    difference = comparison["pair_difference"]
    parent = comparison["parent_top1_difference"]
    consistency = comparison["task_consistency"]
    checks = {
        "parent_coverage_ge_090": audit["parent_coverage"] >= 0.90,
        "runs_ge_300": audit["runs"] >= 300,
        "tasks_ge_20": audit["tasks"] >= 20,
        "dominant_task_le_025": audit["dominant_task_share"] <= 0.25,
        "patch_pair_accuracy_ge_054": comparison["patch"]["pair_accuracy"]["overall"] >= 0.54,
        "pair_gain_ge_002": difference["overall"] >= 0.020,
        "parent_top1_gain_ge_003": parent["overall"] >= 0.030,
        "run_ci_low_gt_0": difference["run_macro_ci95"][0] > 0.0,
        "task_ci_low_gt_0": difference["task_macro_ci95"][0] > 0.0,
        "supported_tasks_ge_10": consistency["supported_tasks"] >= 10,
        "task_nonnegative_share_ge_060": consistency["nonnegative_share"] >= 0.60,
        "finite": True,
        "oracle_eq_1": comparison["oracle_pair_accuracy"] == 1.0,
        "within_wall_cap": runtime <= 900.0,
    }
    checks["all"] = all(checks.values())
    return checks


def frozen_checks(audit: dict[str, Any], comparison: dict[str, Any]) -> dict[str, bool]:
    difference = comparison["pair_difference"]
    parent = comparison["parent_top1_difference"]
    consistency = comparison["task_consistency"]
    checks = {
        "parent_coverage_ge_090": audit["parent_coverage"] >= 0.90,
        "run_overlap_eq_0": audit["train_frozen_run_overlap"] == 0,
        "endpoint_overlap_eq_0": audit["train_frozen_endpoint_overlap"] == 0,
        "patch_pair_accuracy_ge_056": comparison["patch"]["pair_accuracy"]["overall"] >= 0.56,
        "pair_gain_ge_003": difference["overall"] >= 0.030,
        "parent_top1_gain_ge_004": parent["overall"] >= 0.040,
        "run_ci_low_gt_0": difference["run_macro_ci95"][0] > 0.0,
        "task_ci_low_gt_0": difference["task_macro_ci95"][0] > 0.0,
        "task_nonnegative_share_ge_060": consistency["nonnegative_share"] >= 0.60,
    }
    checks["all"] = all(checks.values())
    return checks


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", required=True, type=Path)
    parser.add_argument("--oof", required=True, type=Path)
    parser.add_argument("--frozen", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    summary = json.loads(args.summary.read_text(encoding="utf-8"))
    assert summary["protocol"] == "parent_patch_sparse_v3"
    assert summary["seed"] == SEED
    assert summary["outputs"]["oof_predictions_sha256"] == sha256(args.oof)
    oof_rows = read_predictions(args.oof, "discovery")
    assert len(oof_rows) == summary["train_audit"]["eligible_rows"]
    discovery = reconstruct(oof_rows, supported_minimum=20)
    check_summary(summary["discovery"], discovery)
    discovery_runtime = float(summary["stage_times_s"]["oof_fold_4"])
    expected_discovery_gate = discovery_checks(
        summary["train_audit"], discovery, discovery_runtime
    )
    assert summary["discovery_gate"] == expected_discovery_gate

    result: dict[str, Any] = {
        "verified": True,
        "status": summary["status"],
        "oof_rows": len(oof_rows),
        "discovery_gate": expected_discovery_gate,
        "frozen_verified": False,
    }
    if expected_discovery_gate["all"]:
        if not summary["frozen_read"] or args.frozen is None:
            raise AssertionError("discovery unlocked but frozen artifact is absent")
        assert summary["outputs"]["frozen_predictions_sha256"] == sha256(args.frozen)
        frozen_rows = read_predictions(args.frozen, "frozen")
        assert len(frozen_rows) == summary["frozen_audit"]["eligible_rows"]
        frozen = reconstruct(frozen_rows, supported_minimum=10)
        check_summary(summary["frozen"], frozen)
        expected_frozen_gate = frozen_checks(summary["frozen_audit"], frozen)
        assert summary["frozen_gate"] == expected_frozen_gate
        expected_status = (
            "SPARSE_PATCH_GREEN" if expected_frozen_gate["all"] else "SPARSE_PATCH_NOT_GREEN"
        )
        assert summary["status"] == expected_status
        result.update(
            {
                "frozen_verified": True,
                "frozen_rows": len(frozen_rows),
                "frozen_gate": expected_frozen_gate,
            }
        )
    else:
        assert summary["status"] == "DISCOVERY_NO_UNLOCK"
        assert summary["frozen_read"] is False
        if args.frozen is not None and args.frozen.exists():
            raise AssertionError("frozen output exists despite a closed discovery gate")

    atomic_json(args.out, result)
    print(
        "PARENT_PATCH_INDEPENDENT_VERIFY_PASS",
        summary["status"],
        f"oof_rows={len(oof_rows)}",
        f"frozen_verified={result['frozen_verified']}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
