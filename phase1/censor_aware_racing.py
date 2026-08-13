"""One-shot feasibility audit for censor-aware racing on frozen v9 discovery data.

This analysis is retrospective and exploratory. Its policy and gates are frozen in
the dated preregistration; it cannot replace prospective confirmation.
"""

from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import math
import os
import platform
import random
import statistics
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable


EXPECTED_SHA = {
    "manifest": "77f696828010e2d6ae10a9b9de2d9ec05d44975b1285ea763d9850a7f30ca4ef",
    "results": "b1266d04912596b1e37e13f79ce2387a962f5510cfa264aa1a97b7a1c443180d",
    "runtime": "dff8eb88a1db8d63bab17851c1dce2c1bd389a4744a811d65a5ce1fe5a1f55e7",
    "run_map": "3d774d8414e7b0553e4efdab9410b06aa67ed80cac48fff2d69cbe056baa0e30",
    "orientation": "e11111a3538c54eb91048b54380466b4dc0f041c2f511a78a85573cbc92b121a",
}
EXPECTED_COUNTS = {
    "sets": 100,
    "cards": 230,
    "runs": 52,
    "tasks": 19,
    "hard": 50,
    "easy": 50,
}
POLICIES = ("full_continue", "observed_only", "censor_aware")
ABS_TOL = 1e-12


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default="phase1/fidelity_manifest.jsonl")
    parser.add_argument("--results", default="phase1/fidelity_results.jsonl")
    parser.add_argument("--runtime", default="phase1/fidelity_runtime_v9.jsonl")
    parser.add_argument("--run-map", default="phase1/card_run_map.json")
    parser.add_argument("--orientation", default="phase1/task_orientation.json")
    parser.add_argument("--cap", type=int, default=120)
    parser.add_argument("--bootstrap", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=20260813)
    parser.add_argument("--out-dir", default="phase1/censor_aware_racing_v9")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"invalid JSON at {path}:{line_number}") from error
            if not isinstance(value, dict):
                raise TypeError(f"non-object JSON at {path}:{line_number}")
            rows.append(value)
    return rows


def finite(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def utility(value: float, task: str, lower: dict[str, bool]) -> float:
    return -float(value) if lower[task] else float(value)


def tied_best(values: dict[str, float], task: str, lower: dict[str, bool]) -> set[str]:
    if not values:
        raise ValueError("tied_best requires at least one value")
    best = max(utility(value, task, lower) for value in values.values())
    return {
        card_id
        for card_id, value in values.items()
        if math.isclose(utility(value, task, lower), best, rel_tol=0.0, abs_tol=ABS_TOL)
    }


def matched_random_any_winner(n: int, kept: int, winners: int) -> float:
    if not (1 <= winners <= n and 0 <= kept <= n):
        raise ValueError((n, kept, winners))
    if kept == 0:
        return 0.0
    if kept > n - winners:
        return 1.0
    return 1.0 - math.comb(n - winners, kept) / math.comb(n, kept)


def structured_random_expectation(
    children: set[str], observed: set[str], kept_observed: int, winners: set[str]
) -> tuple[float, float]:
    """Keep every missing candidate and randomize only the observed survivors."""
    if not observed:
        return 1.0, 1.0
    if not observed.issubset(children) or not winners.issubset(children):
        raise ValueError("sets are not nested")
    if not (1 <= kept_observed <= len(observed)):
        raise ValueError("invalid observed survivor count")
    missing = children - observed
    missing_winners = len(missing & winners)
    observed_winners = len(observed & winners)
    any_survival = (
        1.0
        if missing_winners
        else matched_random_any_winner(len(observed), kept_observed, observed_winners)
    )
    fraction_survival = (
        missing_winners + observed_winners * kept_observed / len(observed)
    ) / len(winners)
    return any_survival, fraction_survival


def policy_sets(
    children: Iterable[str], artifact: dict[str, float], task: str, lower: dict[str, bool]
) -> dict[str, set[str]]:
    all_children = set(children)
    if len(all_children) < 2:
        raise ValueError("sibling set must contain at least two candidates")
    if not set(artifact).issubset(all_children):
        raise ValueError("artifact candidate outside sibling set")
    if artifact:
        best_observed = tied_best(artifact, task, lower)
        missing = all_children - set(artifact)
        observed_only = best_observed
        censor_aware = missing | best_observed
    else:
        observed_only = all_children
        censor_aware = all_children
    return {
        "full_continue": all_children,
        "observed_only": observed_only,
        "censor_aware": censor_aware,
    }


def self_test() -> None:
    lower = {"high": False, "low": True}
    policies = policy_sets(["a", "b", "c"], {"a": 0.8, "b": 0.5}, "high", lower)
    assert policies["observed_only"] == {"a"}
    assert policies["censor_aware"] == {"a", "c"}
    truth = {"a": 0.7, "b": 0.6, "c": 0.9}
    winners = tied_best(truth, "high", lower)
    assert not (policies["observed_only"] & winners)
    assert policies["censor_aware"] & winners
    tied = policy_sets(["a", "b", "c"], {"a": 0.8, "b": 0.8}, "high", lower)
    assert tied["censor_aware"] == {"a", "b", "c"}
    low = policy_sets(["a", "b", "c"], {"a": 0.2, "b": 0.3}, "low", lower)
    assert low["censor_aware"] == {"a", "c"}
    assert math.isclose(matched_random_any_winner(3, 2, 1), 2 / 3)
    assert math.isclose(matched_random_any_winner(4, 2, 2), 5 / 6)
    assert matched_random_any_winner(4, 3, 2) == 1.0
    any_random, frac_random = structured_random_expectation(
        {"a", "b", "c"}, {"a", "b"}, 1, {"c"}
    )
    assert any_random == 1.0 and frac_random == 1.0
    any_random, frac_random = structured_random_expectation(
        {"a", "b", "c", "d"}, {"a", "b", "c"}, 1, {"a", "b"}
    )
    assert math.isclose(any_random, 2 / 3) and math.isclose(frac_random, 1 / 3)
    test_rows = [
        {"run_id": "r1", "task": "t1", "x": 1.0},
        {"run_id": "r1", "task": "t1", "x": 0.0},
        {"run_id": "r2", "task": "t2", "x": 1.0},
    ]
    test_summary = summarize(test_rows, "x", 200, 7)
    assert math.isclose(test_summary["set_mean"], 2 / 3)
    assert math.isclose(test_summary["run_macro_mean"], 0.75)
    assert exact_sign(test_rows, "x")["informative"] == 2
    print("CENSOR_AWARE_RACING_SELF_TEST_PASS")


def percentile(values: list[float], q: float) -> float:
    if not values:
        raise ValueError("empty percentile")
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(q * len(ordered))))
    return ordered[index]


def cluster_macro(
    rows: list[dict[str, Any]], field: str, cluster: str, draws: int, seed: int
) -> tuple[float, list[float]]:
    grouped: dict[str, list[float]] = collections.defaultdict(list)
    for row in rows:
        grouped[str(row[cluster])].append(float(row[field]))
    keys = sorted(grouped)
    if not keys:
        raise ValueError("empty cluster population")
    cluster_means = [statistics.mean(grouped[key]) for key in keys]
    point = statistics.mean(cluster_means)
    rng = random.Random(seed)
    estimates: list[float] = []
    for _ in range(draws):
        sampled = [rng.choice(cluster_means) for _ in cluster_means]
        estimates.append(statistics.mean(sampled))
    return point, [percentile(estimates, 0.025), percentile(estimates, 0.975)]


def exact_sign(rows: list[dict[str, Any]], field: str) -> dict[str, int | float]:
    grouped: dict[str, list[float]] = collections.defaultdict(list)
    for row in rows:
        grouped[str(row["run_id"])].append(float(row[field]))
    effects = [statistics.mean(values) for values in grouped.values()]
    positive = sum(value > 1e-15 for value in effects)
    negative = sum(value < -1e-15 for value in effects)
    tied = len(effects) - positive - negative
    informative = positive + negative
    smaller = min(positive, negative)
    tail = (
        sum(math.comb(informative, k) for k in range(smaller + 1)) / (2**informative)
        if informative
        else 0.5
    )
    return {
        "positive": positive,
        "negative": negative,
        "tied": tied,
        "informative": informative,
        "p_two_sided": min(1.0, 2.0 * tail),
    }


def summarize(rows: list[dict[str, Any]], field: str, draws: int, seed: int) -> dict[str, Any]:
    run_point, run_ci = cluster_macro(rows, field, "run_id", draws, seed)
    task_point, task_ci = cluster_macro(rows, field, "task", draws, seed)
    return {
        "set_mean": statistics.mean(float(row[field]) for row in rows),
        "run_macro_mean": run_point,
        "run_macro_ci95": run_ci,
        "task_macro_mean": task_point,
        "task_macro_ci95": task_ci,
    }


def git_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], text=True, capture_output=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else "not-a-git-worktree"


def main() -> None:
    args = arguments()
    if args.self_test:
        self_test()
        return
    if args.cap != 120:
        raise ValueError("cap is frozen at 120 seconds")
    if args.bootstrap <= 0:
        raise ValueError("bootstrap must be positive")
    paths = {
        "manifest": Path(args.manifest),
        "results": Path(args.results),
        "runtime": Path(args.runtime),
        "run_map": Path(args.run_map),
        "orientation": Path(args.orientation),
    }
    observed_sha = {name: sha256(path) for name, path in paths.items()}
    if observed_sha != EXPECTED_SHA:
        raise RuntimeError(f"input SHA mismatch: {observed_sha}")

    manifest = jsonl(paths["manifest"])
    all_results = jsonl(paths["results"])
    runtime_rows = jsonl(paths["runtime"])
    run_of = json.loads(paths["run_map"].read_text(encoding="utf-8"))
    lower = json.loads(paths["orientation"].read_text(encoding="utf-8"))
    if not isinstance(run_of, dict) or not isinstance(lower, dict):
        raise TypeError("run map and orientation must be objects")

    by_parent: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    manifest_by_id: dict[str, dict[str, Any]] = {}
    for row in manifest:
        card_id = str(row["card_id"])
        if card_id in manifest_by_id:
            raise RuntimeError(f"duplicate manifest card: {card_id}")
        if not finite(row.get("graded")):
            raise RuntimeError(f"nonfinite final truth: {card_id}")
        manifest_by_id[card_id] = row
        by_parent[str(row["parent"])].append(row)
    manifest_ids = set(manifest_by_id)

    result_index: dict[tuple[str, int], dict[str, Any]] = {}
    for row in all_results:
        key = (str(row["card_id"]), int(row["cap"]))
        if key in result_index:
            raise RuntimeError(f"duplicate result: {key}")
        result_index[key] = row
    expected_keys = {(card_id, cap) for card_id in manifest_ids for cap in (30, 120)}
    if set(result_index) != expected_keys:
        raise RuntimeError("result keys differ from frozen 30/120 grid")
    cap_index = {card_id: result_index[(card_id, args.cap)] for card_id in manifest_ids}
    for card_id, row in cap_index.items():
        source = manifest_by_id[card_id]
        if (
            row.get("competition") != source.get("competition")
            or row.get("parent") != source.get("parent")
            or row.get("stratum") != source.get("stratum")
            or not math.isclose(float(row["graded"]), float(source["graded"]), rel_tol=0.0, abs_tol=1e-15)
        ):
            raise RuntimeError(f"result metadata mismatch: {card_id}")
        if finite(row.get("sub_score")) and row.get("sub_exists") is not True:
            raise RuntimeError(f"finite score without artifact: {card_id}")
        if not finite(row.get("wall_s")) or float(row["wall_s"]) < 0:
            raise RuntimeError(f"bad probe wall: {card_id}")

    runtime: dict[str, float] = {}
    for row in runtime_rows:
        card_id = str(row["card_id"])
        if card_id in runtime or not finite(row.get("runtime_s")) or float(row["runtime_s"]) < 0:
            raise RuntimeError(f"bad runtime row: {card_id}")
        runtime[card_id] = float(row["runtime_s"])
    if set(runtime) != manifest_ids:
        raise RuntimeError("historical runtime coverage mismatch")

    set_rows: list[dict[str, Any]] = []
    for parent, members in sorted(by_parent.items()):
        children = sorted(str(member["card_id"]) for member in members)
        tasks = {str(member["competition"]) for member in members}
        strata = {str(member["stratum"]) for member in members}
        runs = {run_of.get(card_id) for card_id in children}
        if len(children) < 2 or len(tasks) != 1 or len(strata) != 1 or len(runs) != 1:
            raise RuntimeError(f"invalid sibling set: {parent}")
        task, stratum, run_id = next(iter(tasks)), next(iter(strata)), next(iter(runs))
        if run_id is None or task not in lower or not isinstance(lower[task], bool):
            raise RuntimeError(f"missing run/orientation: {parent}")
        truth = {card_id: float(manifest_by_id[card_id]["graded"]) for card_id in children}
        winners = tied_best(truth, task, lower)
        artifact = {
            card_id: float(cap_index[card_id]["sub_score"])
            for card_id in children
            if finite(cap_index[card_id].get("sub_score"))
        }
        policies = policy_sets(children, artifact, task, lower)
        structured_random_any, structured_random_fraction = structured_random_expectation(
            set(children), set(artifact), len(tied_best(artifact, task, lower)) if artifact else len(children), winners
        )
        full_runtime = sum(runtime[card_id] for card_id in children)
        probe_wall = sum(float(cap_index[card_id]["wall_s"]) for card_id in children)
        if full_runtime <= 0:
            raise RuntimeError(f"nonpositive sibling runtime: {parent}")
        for policy in POLICIES:
            kept = policies[policy]
            pruned = set(children) - kept
            restart_cost = probe_wall + sum(runtime[card_id] for card_id in kept)
            resume_cost = sum(
                min(float(cap_index[card_id]["wall_s"]), runtime[card_id])
                + (max(runtime[card_id] - float(cap_index[card_id]["wall_s"]), 0.0) if card_id in kept else 0.0)
                for card_id in children
            )
            set_rows.append(
                {
                    "parent": parent,
                    "run_id": str(run_id),
                    "task": task,
                    "stratum": stratum,
                    "policy": policy,
                    "n_children": len(children),
                    "n_winners": len(winners),
                    "n_artifact_scored": len(artifact),
                    "n_artifact_exists": sum(cap_index[c].get("sub_exists") is True for c in children),
                    "kept_n": len(kept),
                    "pruned_n": len(pruned),
                    "kept_ids": "|".join(sorted(kept)),
                    "pruned_ids": "|".join(sorted(pruned)),
                    "any_winner_survival": float(bool(kept & winners)),
                    "winner_fraction_survival": len(kept & winners) / len(winners),
                    "structured_random_any_winner": (
                        structured_random_any if policy == "censor_aware" else None
                    ),
                    "structured_random_winner_fraction": (
                        structured_random_fraction if policy == "censor_aware" else None
                    ),
                    "kept_fraction": len(kept) / len(children),
                    "full_runtime_s": full_runtime,
                    "probe_wall_s": probe_wall,
                    "pruned_full_runtime_s": sum(runtime[c] for c in pruned),
                    "avoidable_tail_s": sum(
                        max(runtime[c] - float(cap_index[c]["wall_s"]), 0.0) for c in pruned
                    ),
                    "restart_cost_ratio": restart_cost / full_runtime,
                    "ideal_resume_cost_ratio": resume_cost / full_runtime,
                }
            )

    full_rows = [row for row in set_rows if row["policy"] == "full_continue"]
    observed_rows = [row for row in set_rows if row["policy"] == "observed_only"]
    censor_rows = [row for row in set_rows if row["policy"] == "censor_aware"]
    counts = {
        "sets": len(censor_rows),
        "cards": len(manifest_ids),
        "runs": len({row["run_id"] for row in censor_rows}),
        "tasks": len({row["task"] for row in censor_rows}),
        "hard": sum(row["stratum"] == "hard" for row in censor_rows),
        "easy": sum(row["stratum"] == "easy" for row in censor_rows),
    }
    if counts != EXPECTED_COUNTS:
        raise RuntimeError(f"frozen population mismatch: {counts}")
    if any(row["any_winner_survival"] != 1.0 or row["pruned_n"] != 0 for row in full_rows):
        raise RuntimeError("full-continue positive control failed")

    indexed = {(row["parent"], row["policy"]): row for row in set_rows}
    paired: list[dict[str, Any]] = []
    for row in censor_rows:
        observed = indexed[(row["parent"], "observed_only")]
        paired.append(
            {
                "parent": row["parent"],
                "run_id": row["run_id"],
                "task": row["task"],
                "stratum": row["stratum"],
                "censor_survival": row["any_winner_survival"],
                "observed_survival": observed["any_winner_survival"],
                "structured_random_survival": row["structured_random_any_winner"],
                "delta_vs_observed": row["any_winner_survival"] - observed["any_winner_survival"],
                "delta_vs_random": row["any_winner_survival"] - row["structured_random_any_winner"],
            }
        )

    censor_survival = summarize(paired, "censor_survival", args.bootstrap, args.seed)
    delta_observed = summarize(paired, "delta_vs_observed", args.bootstrap, args.seed)
    delta_random = summarize(paired, "delta_vs_random", args.bootstrap, args.seed)
    delta_observed["run_sign"] = exact_sign(paired, "delta_vs_observed")
    delta_random["run_sign"] = exact_sign(paired, "delta_vs_random")

    aggregate_pruned_fraction = sum(float(row["pruned_n"]) for row in censor_rows) / sum(
        float(row["n_children"]) for row in censor_rows
    )
    aggregate_pruned_runtime_fraction = sum(
        float(row["pruned_full_runtime_s"]) for row in censor_rows
    ) / sum(float(row["full_runtime_s"]) for row in censor_rows)
    aggregate_avoidable_tail_fraction = sum(float(row["avoidable_tail_s"]) for row in censor_rows) / sum(
        float(row["full_runtime_s"]) for row in censor_rows
    )
    aggregate_restart_ratio = (
        sum(float(row["probe_wall_s"]) for row in censor_rows)
        + sum(
            runtime[card_id]
            for row in censor_rows
            for card_id in str(row["kept_ids"]).split("|")
            if card_id
        )
    ) / sum(float(row["full_runtime_s"]) for row in censor_rows)
    aggregate_resume_ratio = 1.0 - aggregate_avoidable_tail_fraction

    per_task: list[dict[str, Any]] = []
    for task in sorted({row["task"] for row in paired}):
        task_rows = [row for row in paired if row["task"] == task]
        per_task.append(
            {
                "task": task,
                "sets": len(task_rows),
                "runs": len({row["run_id"] for row in task_rows}),
                "censor_survival": statistics.mean(row["censor_survival"] for row in task_rows),
                "observed_survival": statistics.mean(row["observed_survival"] for row in task_rows),
                "structured_random_survival": statistics.mean(
                    row["structured_random_survival"] for row in task_rows
                ),
                "delta_vs_observed": statistics.mean(row["delta_vs_observed"] for row in task_rows),
                "delta_vs_random": statistics.mean(row["delta_vs_random"] for row in task_rows),
            }
        )
    supported_min_survival = min(
        row["censor_survival"] for row in per_task if int(row["sets"]) >= 5
    )
    supported_min_delta_random = min(
        row["delta_vs_random"] for row in per_task if int(row["sets"]) >= 5
    )
    tasks = sorted({row["task"] for row in paired})
    loto_observed = {
        task: statistics.mean(row["delta_vs_observed"] for row in paired if row["task"] != task)
        for task in tasks
    }
    loto_random = {
        task: statistics.mean(row["delta_vs_random"] for row in paired if row["task"] != task)
        for task in tasks
    }

    gates = {
        "survival_point_ge_0p90": censor_survival["set_mean"] >= 0.90,
        "survival_run_ci_low_ge_0p80": censor_survival["run_macro_ci95"][0] >= 0.80,
        "survival_task_ci_low_ge_0p75": censor_survival["task_macro_ci95"][0] >= 0.75,
        "pruned_fraction_ge_0p10": aggregate_pruned_fraction >= 0.10,
        "delta_observed_point_ge_0p10": delta_observed["set_mean"] >= 0.10,
        "delta_observed_run_ci_positive": delta_observed["run_macro_ci95"][0] > 0.0,
        "delta_observed_task_ci_positive": delta_observed["task_macro_ci95"][0] > 0.0,
        "delta_observed_informative_runs_ge_10": delta_observed["run_sign"]["informative"] >= 10,
        "delta_observed_sign_p_lt_0p05": delta_observed["run_sign"]["p_two_sided"] < 0.05,
        "delta_random_point_ge_0p10": delta_random["set_mean"] >= 0.10,
        "delta_random_run_ci_positive": delta_random["run_macro_ci95"][0] > 0.0,
        "delta_random_task_ci_positive": delta_random["task_macro_ci95"][0] > 0.0,
        "avoidable_tail_fraction_ge_0p10": aggregate_avoidable_tail_fraction >= 0.10,
        "supported_task_min_survival_ge_0p60": supported_min_survival >= 0.60,
        "supported_task_min_delta_random_nonnegative": supported_min_delta_random >= 0.0,
        "loto_observed_min_nonnegative": min(loto_observed.values()) >= 0.0,
        "loto_random_min_nonnegative": min(loto_random.values()) >= 0.0,
    }
    if all(gates.values()):
        decision = "GO-FEASIBLE"
    elif censor_survival["set_mean"] <= statistics.mean(
        row["structured_random_survival"] for row in paired
    ) or aggregate_pruned_fraction < 0.05:
        decision = "KILL"
    else:
        decision = "BORDERLINE"

    out_dir = Path(args.out_dir)
    if out_dir.exists():
        raise FileExistsError(f"refusing to overwrite output path: {out_dir}")
    out_dir.mkdir(parents=True)
    with (out_dir / "per_set_policy.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(set_rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(set_rows)
    with (out_dir / "paired_survival.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(paired[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(paired)
    with (out_dir / "per_task.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(per_task[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(per_task)

    summary = {
        "status": "retrospective frozen-discovery feasibility; not confirmatory",
        "counts": counts,
        "provenance": {
            "git_commit": git_commit(),
            "script_sha256": sha256(__file__),
            "inputs": {
                name: {"path": str(path), "sha256": observed_sha[name]}
                for name, path in paths.items()
            },
            "command": [sys.executable, *sys.argv],
            "cwd": os.getcwd(),
            "python": platform.python_version(),
            "seed": args.seed,
            "bootstrap": args.bootstrap,
        },
        "signals": {
            "artifact_scored_cards": sum(finite(row.get("sub_score")) for row in cap_index.values()),
            "artifact_exists_cards": sum(row.get("sub_exists") is True for row in cap_index.values()),
            "artifact_scored_sets": sum(int(row["n_artifact_scored"]) > 0 for row in censor_rows),
        },
        "censor_survival": censor_survival,
        "delta_vs_observed": delta_observed,
        "delta_vs_structured_random": delta_random,
        "structured_random_survival_mean": statistics.mean(
            row["structured_random_survival"] for row in paired
        ),
        "resource_accounting": {
            "aggregate_pruned_card_fraction": aggregate_pruned_fraction,
            "aggregate_pruned_historical_full_runtime_fraction": aggregate_pruned_runtime_fraction,
            "aggregate_avoidable_tail_fraction": aggregate_avoidable_tail_fraction,
            "aggregate_pessimistic_restart_cost_ratio": aggregate_restart_ratio,
            "aggregate_optimistic_no_restart_cost_ratio": aggregate_resume_ratio,
            "grader_wall_unrecorded": True,
            "actual_speedup_claim_allowed": False,
        },
        "task_robustness": {
            "supported_task_min_survival": supported_min_survival,
            "supported_task_min_delta_random": supported_min_delta_random,
            "loto_delta_observed": loto_observed,
            "loto_delta_random": loto_random,
        },
        "gates": gates,
        "decision": decision,
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"VERIFIED sets={counts['sets']} cards={counts['cards']} runs={counts['runs']} "
        f"tasks={counts['tasks']} hard={counts['hard']} easy={counts['easy']}"
    )
    print(
        f"CENSOR set={censor_survival['set_mean']:.4f} "
        f"run={censor_survival['run_macro_mean']:.4f} "
        f"runCI=[{censor_survival['run_macro_ci95'][0]:.4f},{censor_survival['run_macro_ci95'][1]:.4f}] "
        f"task={censor_survival['task_macro_mean']:.4f} "
        f"taskCI=[{censor_survival['task_macro_ci95'][0]:.4f},{censor_survival['task_macro_ci95'][1]:.4f}]"
    )
    print(
        f"VS_OBSERVED set={delta_observed['set_mean']:+.4f} "
        f"run={delta_observed['run_macro_mean']:+.4f} "
        f"runCI=[{delta_observed['run_macro_ci95'][0]:+.4f},{delta_observed['run_macro_ci95'][1]:+.4f}] "
        f"task={delta_observed['task_macro_mean']:+.4f} "
        f"taskCI=[{delta_observed['task_macro_ci95'][0]:+.4f},{delta_observed['task_macro_ci95'][1]:+.4f}] "
        f"sign_p={delta_observed['run_sign']['p_two_sided']:.6f}"
    )
    print(
        f"VS_STRUCTURED_RANDOM set={delta_random['set_mean']:+.4f} "
        f"run={delta_random['run_macro_mean']:+.4f} "
        f"runCI=[{delta_random['run_macro_ci95'][0]:+.4f},{delta_random['run_macro_ci95'][1]:+.4f}] "
        f"task={delta_random['task_macro_mean']:+.4f} "
        f"taskCI=[{delta_random['task_macro_ci95'][0]:+.4f},{delta_random['task_macro_ci95'][1]:+.4f}]"
    )
    print(
        f"RESOURCE pruned_cards={aggregate_pruned_fraction:.4f} "
        f"pruned_full_runtime={aggregate_pruned_runtime_fraction:.4f} "
        f"avoidable_tail={aggregate_avoidable_tail_fraction:.4f} "
        f"restart_ratio={aggregate_restart_ratio:.4f} resume_ratio={aggregate_resume_ratio:.4f}"
    )
    print(f"DECISION {decision}")
    print(f"WROTE {out_dir}")


if __name__ == "__main__":
    main()
