#!/usr/bin/env python3
"""Independent verifier for the v11 selective-execution audit.

This module deliberately does not import ``selective_execution_audit``.  It
reconstructs the exact-two pool, votes, confidence ranks, policies, bootstrap
intervals, gates, and output tables from the locked OOF CSV.
"""

from __future__ import annotations

import argparse
import bisect
import collections
import csv
import hashlib
import json
import math
import random
import statistics
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


PROTOCOL = "selective_execution_v11_retrospective_discovery_v1"
INPUT_SHA = "fc57c03a1c96ce7be19a4db764a539082258fe4c69a2ec8653b41ff85626cb45"
ARMS = ("char_tfidf_lr", "static_lr", "fixed_frozen_global")
FOLD_COUNTS = {0: 285, 1: 215, 2: 222, 3: 373, 4: 425}
Q_VALUES = (0.05, 0.10, 0.20, 0.40, 0.60, 0.80, 1.00)
TASK_SEED = 20_260_814
RUN_SEED = 20_260_815
N_BOOT = 10_000
TOL = 1e-12


class VerificationError(RuntimeError):
    pass


def digest(path: Path) -> str:
    state = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            state.update(chunk)
    return state.hexdigest()


def key(namespace: str, parent: str) -> str:
    return hashlib.sha256(f"{PROTOCOL}\x00{namespace}\x00{parent}".encode()).hexdigest()


def number(value: str, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise VerificationError(f"invalid {label}") from error
    if not math.isfinite(result):
        raise VerificationError(f"nonfinite {label}")
    return result


def direction(delta: float) -> int:
    return 1 if delta > TOL else (-1 if delta < -TOL else 0)


def correctness(predicted: int, truth: int) -> float:
    return 0.5 if predicted == 0 else float(predicted == truth)


def read_pool(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if path.name != "oof_predictions.csv" or digest(path) != INPUT_SHA:
        raise VerificationError("locked input identity mismatch")
    with path.open("r", encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != 4_263:
        raise VerificationError("full row count mismatch")
    parents: dict[str, list[dict[str, str]]] = collections.defaultdict(list)
    for expected, row in enumerate(rows):
        if int(row["row_index"]) != expected:
            raise VerificationError("row index mismatch")
        parents[row["parent"]].append(row)
    if len(parents) != 2_293:
        raise VerificationError("parent support mismatch")
    for parent_rows in parents.values():
        if len({(r["task"], r["run"], r["fold"]) for r in parent_rows}) != 1:
            raise VerificationError("parent spans a structural cluster")

    pool = []
    for parent, parent_rows in parents.items():
        if len(parent_rows) != 1:
            continue
        raw = parent_rows[0]
        endpoint0, endpoint1 = sorted((raw["better"], raw["worse"]))
        if not endpoint0 or endpoint0 == endpoint1:
            raise VerificationError("invalid endpoints")
        truth = 1 if raw["better"] == endpoint1 else -1
        gap = number(raw["gap_raw"], "gap")
        if gap <= 0:
            raise VerificationError("nonpositive gap")
        votes = {}
        margins = {}
        for arm in ARMS:
            score = {
                raw["better"]: number(raw[f"{arm}_better_score"], "endpoint score"),
                raw["worse"]: number(raw[f"{arm}_worse_score"], "endpoint score"),
            }
            delta = score[endpoint1] - score[endpoint0]
            votes[arm] = direction(delta)
            margins[arm] = abs(delta)
            if abs(number(raw[f"{arm}_hit"], "published hit") - correctness(votes[arm], truth)) > TOL:
                raise VerificationError("published hit mismatch")
        pool.append(
            {
                "index": int(raw["row_index"]),
                "task": raw["task"],
                "run": raw["run"],
                "parent": parent,
                "fold": int(raw["fold"]),
                "truth": truth,
                "gap": gap,
                "votes": votes,
                "margins": margins,
            }
        )
    pool.sort(key=lambda row: row["index"])
    tasks = collections.Counter(row["task"] for row in pool)
    folds = collections.Counter(row["fold"] for row in pool)
    if len(pool) != 1_520 or len({r["run"] for r in pool}) != 294 or len(tasks) != 23:
        raise VerificationError("exact-two support mismatch")
    if dict(sorted(folds.items())) != FOLD_COUNTS or tasks.most_common(1)[0][1] != 336:
        raise VerificationError("fold/task balance mismatch")
    if sum(math.floor(0.2 * n) for n in tasks.values()) != 295:
        raise VerificationError("quota mismatch")

    # Independent empirical-CDF implementation of the producer's midrank.
    distributions: dict[tuple[str, int], list[float]] = {}
    for arm in ARMS:
        for fold in FOLD_COUNTS:
            distributions[(arm, fold)] = sorted(
                row["margins"][arm] for row in pool if row["fold"] == fold
            )
    for row in pool:
        percentiles = {}
        for arm in ARMS:
            values = distributions[(arm, row["fold"])]
            value = row["margins"][arm]
            left = bisect.bisect_left(values, value)
            right = bisect.bisect_right(values, value)
            percentiles[arm] = ((left + 1) + right) / (2.0 * len(values))
        row["percentiles"] = percentiles

    audit = {
        "input_sha256": INPUT_SHA,
        "rows": len(rows),
        "parents": len(parents),
        "exact_two_parents": len(pool),
        "exact_two_runs": len({row["run"] for row in pool}),
        "exact_two_tasks": len(tasks),
        "fold_counts": {str(k): v for k, v in sorted(folds.items())},
        "task_counts": dict(sorted(tasks.items())),
        "dominant_task": tasks.most_common(1)[0][0],
        "dominant_count": tasks.most_common(1)[0][1],
        "dominant_share": tasks.most_common(1)[0][1] / len(pool),
        "q20_quota": 295,
    }
    return pool, audit


def unanimity(row: Mapping[str, Any]) -> int:
    values = [row["votes"][arm] for arm in ARMS]
    return values[0] if values[0] and len(set(values)) == 1 else 0


def task_groups(pool: Sequence[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in pool:
        result[row["task"]].append(row)
    return dict(result)


def top(
    rows: Sequence[dict[str, Any]], count: int, score: Callable[[Mapping[str, Any]], float], namespace: str
) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda row: (-score(row), key(namespace, row["parent"]), row["parent"]))[:count]


def hashed(rows: Sequence[dict[str, Any]], count: int, namespace: str) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda row: (key(namespace, row["parent"]), row["parent"]))[:count]


def policies(pool: Sequence[dict[str, Any]]) -> tuple[dict[str, dict[str, int]], dict[str, int]]:
    grouped = task_groups(pool)
    primary = {}
    quota_by_task = {}
    eligible = {}
    for task, rows in grouped.items():
        quota_by_task[task] = math.floor(0.2 * len(rows))
        eligible[task] = [row for row in rows if unanimity(row)]
        chosen = top(
            eligible[task],
            quota_by_task[task],
            lambda row: min(row["percentiles"].values()),
            "tri_q0.20",
        )
        primary.update({row["parent"]: unanimity(row) for row in chosen})
    realized = collections.Counter(row["task"] for row in pool if row["parent"] in primary)

    char_margin = {}
    unanimous_crc = {}
    char_crc = {}
    for task, rows in grouped.items():
        count = realized[task]
        char_margin.update(
            {
                row["parent"]: row["votes"]["char_tfidf_lr"]
                for row in top(
                    rows,
                    count,
                    lambda item: item["percentiles"]["char_tfidf_lr"],
                    "char_margin_matched",
                )
            }
        )
        unanimous_crc.update(
            {row["parent"]: unanimity(row) for row in hashed(eligible[task], count, "unanimous_crc_matched")}
        )
        char_crc.update(
            {
                row["parent"]: row["votes"]["char_tfidf_lr"]
                for row in hashed(rows, count, "char_crc_matched")
            }
        )
    random_primary = {
        row["parent"]: (1 if int(key("random_on_primary", row["parent"]), 16) & 1 else -1)
        for row in pool
        if row["parent"] in primary
    }
    return (
        {
            "tri_unanimous_q20": primary,
            "char_margin_matched": char_margin,
            "unanimous_crc_matched": unanimous_crc,
            "char_crc_matched": char_crc,
            "random_on_primary": random_primary,
            "oracle_all": {row["parent"]: row["truth"] for row in pool},
            "random_all": {
                row["parent"]: (1 if int(key("random_all", row["parent"]), 16) & 1 else -1)
                for row in pool
            },
        },
        quota_by_task,
    )


def interval(draws: list[float]) -> list[float]:
    draws.sort()
    return [draws[int(0.025 * len(draws))], draws[int(0.975 * len(draws))]]


def bootstrap(values: Mapping[str, float], seed: int) -> list[float]:
    names = sorted(values)
    rng = random.Random(seed)
    return interval(
        [statistics.fmean(values[rng.choice(names)] for _ in names) for _ in range(N_BOOT)]
    )


def measure(pool: Sequence[dict[str, Any]], predictions: Mapping[str, int], offset: int) -> dict[str, Any]:
    chosen = [row for row in pool if row["parent"] in predictions]
    if not chosen:
        return {
            "selected": 0,
            "runs": 0,
            "tasks": 0,
            "coverage": 0.0,
            "candidate_executions": 2 * len(pool),
            "candidate_saving_fraction": 0.0,
            "micro_accuracy": None,
            "run_macro_accuracy": None,
            "task_macro_accuracy": None,
        }
    observed = {
        row["parent"]: correctness(predictions[row["parent"]], row["truth"]) for row in chosen
    }
    task_values: dict[str, list[float]] = collections.defaultdict(list)
    run_values: dict[str, list[float]] = collections.defaultdict(list)
    support = collections.Counter()
    for row in chosen:
        value = observed[row["parent"]]
        task_values[row["task"]].append(value)
        run_values[row["run"]].append(value)
        support[row["task"]] += 1
    task_accuracy = {name: statistics.fmean(vals) for name, vals in task_values.items()}
    run_accuracy = {name: statistics.fmean(vals) for name, vals in run_values.items()}
    total_gap = collections.defaultdict(float)
    loss_gap = collections.defaultdict(float)
    for row in pool:
        total_gap[row["task"]] += row["gap"]
    for row in chosen:
        loss_gap[row["task"]] += row["gap"] * (1.0 - observed[row["parent"]])
    ratios = {task: loss_gap[task] / amount for task, amount in total_gap.items()}
    chosen_gap = sum(row["gap"] for row in chosen)
    task_macro = statistics.fmean(task_accuracy.values())
    loto = [
        statistics.fmean(value for task, value in task_accuracy.items() if task != omitted)
        for omitted in task_accuracy
        if len(task_accuracy) > 1
    ]
    dominant, dominant_n = support.most_common(1)[0]
    return {
        "selected": len(chosen),
        "selected_parent_sha256": hashlib.sha256(
            "\n".join(sorted(row["parent"] for row in chosen)).encode()
        ).hexdigest(),
        "runs": len(run_values),
        "tasks": len(task_values),
        "dominant_task": dominant,
        "dominant_count": dominant_n,
        "dominant_share": dominant_n / len(chosen),
        "coverage": len(chosen) / len(pool),
        "candidate_executions": 2 * len(pool) - len(chosen),
        "candidate_saving_fraction": len(chosen) / (2.0 * len(pool)),
        "micro_accuracy": statistics.fmean(observed.values()),
        "run_macro_accuracy": statistics.fmean(run_accuracy.values()),
        "run_macro_ci95": bootstrap(run_accuracy, RUN_SEED + offset),
        "task_macro_accuracy": task_macro,
        "task_macro_ci95": bootstrap(task_accuracy, TASK_SEED + offset),
        "task_macro_loto_range": [min(loto), max(loto)] if loto else [task_macro, task_macro],
        "selected_gap_weighted_accuracy": sum(
            row["gap"] * observed[row["parent"]] for row in chosen
        )
        / chosen_gap,
        "task_macro_total_gap_loss_ratio": statistics.fmean(ratios.values()),
        "per_task_accuracy": dict(sorted(task_accuracy.items())),
        "per_task_selected": dict(sorted(support.items())),
        "per_task_total_gap_loss_ratio": dict(sorted(ratios.items())),
    }


def compare_tasks(left: Mapping[str, Any], right: Mapping[str, Any], offset: int) -> dict[str, Any]:
    common = sorted(set(left["per_task_accuracy"]) & set(right["per_task_accuracy"]))
    values = {
        task: left["per_task_accuracy"][task] - right["per_task_accuracy"][task]
        for task in common
    }
    return {
        "tasks": len(common),
        "task_macro_delta": statistics.fmean(values.values()),
        "task_macro_delta_ci95": bootstrap(values, TASK_SEED + offset),
        "per_task_delta": values,
    }


def curve_predictions(pool: Sequence[dict[str, Any]], q: float, committee: bool) -> dict[str, int]:
    result = {}
    for task, rows in task_groups(pool).items():
        count = math.floor(q * len(rows))
        if committee:
            valid = [row for row in rows if unanimity(row)]
            picked = top(valid, count, lambda row: min(row["percentiles"].values()), f"curve_tri_{q:.2f}")
            result.update({row["parent"]: unanimity(row) for row in picked})
        else:
            picked = top(
                rows,
                count,
                lambda row: row["percentiles"]["char_tfidf_lr"],
                f"curve_char_{q:.2f}",
            )
            result.update({row["parent"]: row["votes"]["char_tfidf_lr"] for row in picked})
    return result


def curve_numbers(pool: Sequence[dict[str, Any]], predictions: Mapping[str, int]) -> dict[str, Any]:
    chosen = [row for row in pool if row["parent"] in predictions]
    if not chosen:
        return {"selected": 0, "coverage": 0.0, "micro_accuracy": None, "task_macro_accuracy": None}
    by_task = collections.defaultdict(list)
    values = []
    for row in chosen:
        value = correctness(predictions[row["parent"]], row["truth"])
        values.append(value)
        by_task[row["task"]].append(value)
    return {
        "selected": len(chosen),
        "coverage": len(chosen) / len(pool),
        "candidate_saving_fraction": len(chosen) / (2.0 * len(pool)),
        "micro_accuracy": statistics.fmean(values),
        "task_macro_accuracy": statistics.fmean(statistics.fmean(v) for v in by_task.values()),
        "tasks": len(by_task),
    }


def gates(audit: Mapping[str, Any], metrics: Mapping[str, Any], comparisons: Mapping[str, Any]):
    primary = metrics["tri_unanimous_q20"]
    oracle = metrics["oracle_all"]
    random_all = metrics["random_all"]
    delta = comparisons["primary_minus_char_margin_matched"]
    crc = comparisons["primary_minus_unanimous_crc_matched"]
    integrity = {
        "input_sha_exact": audit["input_sha256"] == INPUT_SHA,
        "structure_exact": audit["rows"] == 4_263 and audit["parents"] == 2_293
        and audit["exact_two_parents"] == 1_520 and audit["exact_two_runs"] == 294
        and audit["exact_two_tasks"] == 23,
        "oracle_accuracy_eq_1": oracle["micro_accuracy"] == 1.0,
        "oracle_gap_loss_eq_0": oracle["task_macro_total_gap_loss_ratio"] == 0.0,
        "random_all_micro_in_047_053": 0.47 <= random_all["micro_accuracy"] <= 0.53,
        "frozen_or_first960_read_false": True,
    }
    scientific = {
        "selected_ge_228": primary["selected"] >= 228,
        "runs_ge_100": primary["runs"] >= 100,
        "tasks_ge_20": primary["tasks"] >= 20,
        "dominant_share_le_025": primary["dominant_share"] <= 0.25,
        "candidate_saving_ge_0075": primary["candidate_saving_fraction"] >= 0.075,
        "micro_accuracy_ge_058": primary["micro_accuracy"] >= 0.58,
        "run_macro_accuracy_ge_058": primary["run_macro_accuracy"] >= 0.58,
        "task_macro_accuracy_ge_058": primary["task_macro_accuracy"] >= 0.58,
        "run_ci_low_gt_050": primary["run_macro_ci95"][0] > 0.50,
        "task_ci_low_gt_050": primary["task_macro_ci95"][0] > 0.50,
        "char_delta_ge_002": delta["task_macro_delta"] >= 0.02,
        "char_delta_ci_low_gt_0": delta["task_macro_delta_ci95"][0] > 0.0,
        "selected_gap_weighted_accuracy_ge_060": primary["selected_gap_weighted_accuracy"] >= 0.60,
        "task_macro_gap_loss_le_008": primary["task_macro_total_gap_loss_ratio"] <= 0.08,
    }
    verdict = "SELECTIVE_EXECUTION_DISCOVERY_UNLOCK" if all(integrity.values()) and all(scientific.values()) else "SELECTIVE_EXECUTION_DISCOVERY_NO_UNLOCK"
    margin = "MARGIN_ENRICHMENT_SUPPORTED" if crc["task_macro_delta"] >= 0.02 and crc["task_macro_delta_ci95"][0] > 0 else "MARGIN_ENRICHMENT_NOT_SUPPORTED"
    return integrity, scientific, verdict, margin


def recursively_match(expected: Any, observed: Any, path: str = "root") -> None:
    if isinstance(expected, dict):
        if not isinstance(observed, dict) or set(expected) != set(observed):
            raise VerificationError(f"mapping keys differ at {path}")
        for key_name in expected:
            recursively_match(expected[key_name], observed[key_name], f"{path}.{key_name}")
    elif isinstance(expected, list):
        if not isinstance(observed, list) or len(expected) != len(observed):
            raise VerificationError(f"list shape differs at {path}")
        for index, (left, right) in enumerate(zip(expected, observed)):
            recursively_match(left, right, f"{path}[{index}]")
    elif isinstance(expected, (int, float)) and not isinstance(expected, bool):
        if not isinstance(observed, (int, float)) or abs(float(expected) - float(observed)) > TOL:
            raise VerificationError(f"numeric mismatch at {path}: {expected} != {observed}")
    elif expected != observed:
        raise VerificationError(f"value mismatch at {path}: {expected!r} != {observed!r}")


def verify_selected_table(path: Path, pool: Sequence[dict[str, Any]], policy_map: Mapping[str, Mapping[str, int]]) -> None:
    with path.open("r", encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != len(pool):
        raise VerificationError("selected table row count mismatch")
    by_parent = {row["parent"]: row for row in pool}
    if [row["parent"] for row in rows] != sorted(by_parent):
        raise VerificationError("selected table parent order mismatch")
    for row in rows:
        source = by_parent[row["parent"]]
        if (row["task"], row["run"], int(row["fold"])) != (source["task"], source["run"], source["fold"]):
            raise VerificationError("selected table structural mismatch")
        for policy_name, predictions in policy_map.items():
            expected = "" if row["parent"] not in predictions else str(predictions[row["parent"]])
            if row[f"{policy_name}_vote"] != expected:
                raise VerificationError("selected table vote mismatch")


def verify(input_csv: Path, result_dir: Path, receipt: Path) -> dict[str, Any]:
    if receipt.exists():
        raise VerificationError("refusing to overwrite verifier receipt")
    summary_path = result_dir / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    pool, audit = read_pool(input_csv)
    policy_map, quotas = policies(pool)
    metrics = {name: measure(pool, predictions, 100 * index) for index, (name, predictions) in enumerate(policy_map.items())}
    comparisons = {
        "primary_minus_char_margin_matched": compare_tasks(metrics["tri_unanimous_q20"], metrics["char_margin_matched"], 1_000),
        "primary_minus_unanimous_crc_matched": compare_tasks(metrics["tri_unanimous_q20"], metrics["unanimous_crc_matched"], 2_000),
        "primary_minus_char_crc_matched": compare_tasks(metrics["tri_unanimous_q20"], metrics["char_crc_matched"], 3_000),
    }
    curves = []
    for family, committee in (("char_margin", False), ("tri_unanimous", True)):
        for q in Q_VALUES:
            row = curve_numbers(pool, curve_predictions(pool, q, committee))
            row.update({"family": family, "q": q})
            curves.append(row)
    integrity, scientific, verdict, margin = gates(audit, metrics, comparisons)

    recursively_match(audit, summary["input_audit"], "input_audit")
    recursively_match(metrics, summary["policies"], "policies")
    recursively_match(comparisons, summary["comparisons"], "comparisons")
    recursively_match(curves, summary["risk_coverage"], "risk_coverage")
    recursively_match(integrity, summary["integrity_gates"], "integrity_gates")
    recursively_match(scientific, summary["scientific_gates"], "scientific_gates")
    recursively_match(dict(sorted(quotas.items())), summary["parameters"]["task_quotas"], "task_quotas")
    if summary["protocol"] != PROTOCOL or summary["verdict"] != verdict or summary["margin_enrichment_verdict"] != margin:
        raise VerificationError("top-level verdict mismatch")
    if summary.get("frozen_or_first960_read") is not False:
        raise VerificationError("forbidden read receipt mismatch")
    verify_selected_table(result_dir / "selected_parents.csv", pool, policy_map)

    result = {
        "protocol": PROTOCOL,
        "verification": "INDEPENDENT_SELECTIVE_EXECUTION_VERIFY_PASS",
        "producer_verdict": verdict,
        "margin_enrichment_verdict": margin,
        "selected": metrics["tri_unanimous_q20"]["selected"],
        "task_macro_accuracy": metrics["tri_unanimous_q20"]["task_macro_accuracy"],
        "candidate_saving_fraction": metrics["tri_unanimous_q20"]["candidate_saving_fraction"],
        "selected_parent_sha256": metrics["tri_unanimous_q20"]["selected_parent_sha256"],
        "input_sha256": digest(input_csv),
        "summary_sha256": digest(summary_path),
        "selected_table_sha256": digest(result_dir / "selected_parents.csv"),
        "per_task_sha256": digest(result_dir / "per_task.csv"),
        "risk_coverage_sha256": digest(result_dir / "risk_coverage.csv"),
        "frozen_or_first960_read": False,
    }
    receipt.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"{result['verification']} verdict={verdict} selected={result['selected']} "
        f"task_macro={result['task_macro_accuracy']:.6f}",
        flush=True,
    )
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--result-dir", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    verify(args.input, args.result_dir, args.receipt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
