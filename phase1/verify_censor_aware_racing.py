"""Independent raw-input verifier for frozen censor-aware racing outputs.

Deliberately does not import censor_aware_racing.py.
"""

from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import math
import random
import statistics
from pathlib import Path
from typing import Any


LOCKS = {
    "manifest": "77f696828010e2d6ae10a9b9de2d9ec05d44975b1285ea763d9850a7f30ca4ef",
    "results": "b1266d04912596b1e37e13f79ce2387a962f5510cfa264aa1a97b7a1c443180d",
    "runtime": "dff8eb88a1db8d63bab17851c1dce2c1bd389a4744a811d65a5ce1fe5a1f55e7",
    "run_map": "3d774d8414e7b0553e4efdab9410b06aa67ed80cac48fff2d69cbe056baa0e30",
    "orientation": "e11111a3538c54eb91048b54380466b4dc0f041c2f511a78a85573cbc92b121a",
}
TOL = 1e-12


def cli() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", default="phase1/fidelity_manifest.jsonl")
    p.add_argument("--results", default="phase1/fidelity_results.jsonl")
    p.add_argument("--runtime", default="phase1/fidelity_runtime_v9.jsonl")
    p.add_argument("--run-map", default="phase1/card_run_map.json")
    p.add_argument("--orientation", default="phase1/task_orientation.json")
    p.add_argument("--out-dir", default="phase1/censor_aware_racing_v9")
    p.add_argument("--self-test", action="store_true")
    return p.parse_args()


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load_lines(path: Path) -> list[dict[str, Any]]:
    answer = []
    for number, text in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not text.strip():
            continue
        value = json.loads(text)
        if not isinstance(value, dict):
            raise AssertionError((path, number))
        answer.append(value)
    return answer


def is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def score_direction(value: float, task: str, minimize: dict[str, bool]) -> float:
    return -float(value) if minimize[task] else float(value)


def best_ids(values: dict[str, float], task: str, minimize: dict[str, bool]) -> set[str]:
    peak = max(score_direction(value, task, minimize) for value in values.values())
    return {
        key
        for key, value in values.items()
        if abs(score_direction(value, task, minimize) - peak) <= TOL
    }


def expected_random_survival(total: int, retained: int, optimal: int) -> float:
    if retained == 0:
        return 0.0
    misses = total - optimal
    return 1.0 if retained > misses else 1.0 - math.comb(misses, retained) / math.comb(total, retained)


def structured_random(
    children: set[str], observed: set[str], kept_observed: int, winners: set[str]
) -> tuple[float, float]:
    if not observed:
        return 1.0, 1.0
    missing = children - observed
    missing_optimal = len(missing & winners)
    observed_optimal = len(observed & winners)
    any_survival = (
        1.0
        if missing_optimal
        else expected_random_survival(len(observed), kept_observed, observed_optimal)
    )
    fraction = (
        missing_optimal + observed_optimal * kept_observed / len(observed)
    ) / len(winners)
    return any_survival, fraction


def close(a: object, b: float, tolerance: float = 1e-12) -> None:
    if not math.isclose(float(a), float(b), rel_tol=0.0, abs_tol=tolerance):
        raise AssertionError((a, b))


def macro_summary(
    records: list[dict[str, Any]], column: str, group: str
) -> tuple[float, list[float]]:
    buckets: dict[str, list[float]] = collections.defaultdict(list)
    for record in records:
        buckets[str(record[group])].append(float(record[column]))
    means = [statistics.fmean(buckets[name]) for name in sorted(buckets)]
    point = statistics.fmean(means)
    generator = random.Random(20260813)
    estimates = []
    for _ in range(10000):
        draw = [generator.choice(means) for __ in means]
        estimates.append(statistics.fmean(draw))
    estimates.sort()
    return point, [
        estimates[int(0.025 * len(estimates))],
        estimates[int(0.975 * len(estimates))],
    ]


def run_sign(records: list[dict[str, Any]], column: str) -> dict[str, int | float]:
    buckets: dict[str, list[float]] = collections.defaultdict(list)
    for record in records:
        buckets[str(record["run_id"])].append(float(record[column]))
    effects = [statistics.fmean(values) for values in buckets.values()]
    plus = sum(value > 1e-15 for value in effects)
    minus = sum(value < -1e-15 for value in effects)
    tie = len(effects) - plus - minus
    n = plus + minus
    small = min(plus, minus)
    p = min(1.0, 2 * sum(math.comb(n, k) for k in range(small + 1)) / (2**n)) if n else 1.0
    return {"positive": plus, "negative": minus, "tied": tie, "informative": n, "p_two_sided": p}


def self_test() -> None:
    assert math.isclose(expected_random_survival(3, 2, 1), 2 / 3)
    assert math.isclose(expected_random_survival(4, 2, 2), 5 / 6)
    assert expected_random_survival(4, 3, 2) == 1.0
    low = {"x": True}
    assert best_ids({"a": 0.2, "b": 0.3}, "x", low) == {"a"}
    assert structured_random({"a", "b", "c"}, {"a", "b"}, 1, {"c"}) == (1.0, 1.0)
    any_value, fraction = structured_random(
        {"a", "b", "c", "d"}, {"a", "b", "c"}, 1, {"a", "b"}
    )
    assert math.isclose(any_value, 2 / 3) and math.isclose(fraction, 1 / 3)
    records = [
        {"run_id": "r1", "x": 1.0},
        {"run_id": "r1", "x": 0.0},
        {"run_id": "r2", "x": 1.0},
    ]
    point, ci = macro_summary(records, "x", "run_id")
    assert math.isclose(point, 0.75) and len(ci) == 2
    assert run_sign(records, "x")["informative"] == 2
    print("CENSOR_AWARE_INDEPENDENT_SELF_TEST_PASS")


def main() -> None:
    args = cli()
    if args.self_test:
        self_test()
        return
    files = {
        "manifest": Path(args.manifest),
        "results": Path(args.results),
        "runtime": Path(args.runtime),
        "run_map": Path(args.run_map),
        "orientation": Path(args.orientation),
    }
    actual_locks = {name: digest(path) for name, path in files.items()}
    if actual_locks != LOCKS:
        raise AssertionError(actual_locks)
    manifest = load_lines(files["manifest"])
    results = load_lines(files["results"])
    runtimes = load_lines(files["runtime"])
    run_map = json.loads(files["run_map"].read_text(encoding="utf-8"))
    minimize = json.loads(files["orientation"].read_text(encoding="utf-8"))
    out = Path(args.out_dir)
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    with (out / "per_set_policy.csv").open(newline="", encoding="utf-8") as f:
        exported = list(csv.DictReader(f))
    with (out / "paired_survival.csv").open(newline="", encoding="utf-8") as f:
        exported_pairs = list(csv.DictReader(f))
    with (out / "per_task.csv").open(newline="", encoding="utf-8") as f:
        exported_tasks = list(csv.DictReader(f))

    nodes = {str(row["card_id"]): row for row in manifest}
    if len(nodes) != len(manifest) or len(nodes) != 230:
        raise AssertionError("manifest uniqueness/count")
    groups: dict[str, list[str]] = collections.defaultdict(list)
    for card, row in nodes.items():
        groups[str(row["parent"])].append(card)
    if len(groups) != 100:
        raise AssertionError("parent count")
    cap120: dict[str, dict[str, Any]] = {}
    keys = set()
    for row in results:
        key = (str(row["card_id"]), int(row["cap"]))
        if key in keys:
            raise AssertionError(("duplicate result", key))
        keys.add(key)
        if key[1] == 120:
            cap120[key[0]] = row
    if keys != {(card, cap) for card in nodes for cap in (30, 120)}:
        raise AssertionError("result grid")
    fulltime = {str(row["card_id"]): float(row["runtime_s"]) for row in runtimes}
    if len(fulltime) != len(runtimes) or set(fulltime) != set(nodes):
        raise AssertionError("runtime coverage")

    table = {(row["parent"], row["policy"]): row for row in exported}
    if len(table) != 300 or len(exported) != 300:
        raise AssertionError("exported policy rows")
    reconstructed_pairs = []
    total_pruned = total_cards = 0
    total_pruned_runtime = total_runtime = total_tail = total_probe = total_kept_runtime = 0.0
    scored_cards = exists_cards = scored_sets = 0
    seen_scored: set[str] = set()
    seen_exists: set[str] = set()
    for parent, child_list in sorted(groups.items()):
        children = set(child_list)
        tasks = {str(nodes[c]["competition"]) for c in children}
        strata = {str(nodes[c]["stratum"]) for c in children}
        runs = {run_map[c] for c in children}
        if len(children) < 2 or len(tasks) != 1 or len(strata) != 1 or len(runs) != 1:
            raise AssertionError((parent, tasks, strata, runs))
        task, stratum, run_id = next(iter(tasks)), next(iter(strata)), next(iter(runs))
        truth = {c: float(nodes[c]["graded"]) for c in children}
        winners = best_ids(truth, task, minimize)
        observed = {c: float(cap120[c]["sub_score"]) for c in children if is_number(cap120[c].get("sub_score"))}
        for c in observed:
            if cap120[c].get("sub_exists") is not True:
                raise AssertionError(("score without artifact", c))
        seen_scored.update(observed)
        seen_exists.update(c for c in children if cap120[c].get("sub_exists") is True)
        if observed:
            scored_sets += 1
            top_observed = best_ids(observed, task, minimize)
            expected = {
                "full_continue": children,
                "observed_only": top_observed,
                "censor_aware": (children - set(observed)) | top_observed,
            }
        else:
            expected = {name: children for name in ("full_continue", "observed_only", "censor_aware")}
            top_observed = children
        random_any, random_fraction = structured_random(
            children, set(observed), len(top_observed), winners
        )
        set_runtime = sum(fulltime[c] for c in children)
        set_probe = sum(float(cap120[c]["wall_s"]) for c in children)
        for policy, kept in expected.items():
            row = table[(parent, policy)]
            pruned = children - kept
            if set(filter(None, row["kept_ids"].split("|"))) != kept:
                raise AssertionError((parent, policy, "kept"))
            if set(filter(None, row["pruned_ids"].split("|"))) != pruned:
                raise AssertionError((parent, policy, "pruned"))
            if row["run_id"] != str(run_id) or row["task"] != task or row["stratum"] != stratum:
                raise AssertionError((parent, policy, "metadata"))
            any_survive = float(bool(kept & winners))
            close(row["any_winner_survival"], any_survive)
            close(row["winner_fraction_survival"], len(kept & winners) / len(winners))
            if policy == "censor_aware":
                close(row["structured_random_any_winner"], random_any)
                close(row["structured_random_winner_fraction"], random_fraction)
            elif row["structured_random_any_winner"] or row["structured_random_winner_fraction"]:
                raise AssertionError((parent, policy, "unexpected random fields"))
            close(row["full_runtime_s"], set_runtime, 1e-9)
            close(row["probe_wall_s"], set_probe, 1e-9)
            close(row["pruned_full_runtime_s"], sum(fulltime[c] for c in pruned), 1e-9)
            tail = sum(max(fulltime[c] - float(cap120[c]["wall_s"]), 0.0) for c in pruned)
            close(row["avoidable_tail_s"], tail, 1e-9)
            restart = (set_probe + sum(fulltime[c] for c in kept)) / set_runtime
            resume = sum(
                min(float(cap120[c]["wall_s"]), fulltime[c])
                + (max(fulltime[c] - float(cap120[c]["wall_s"]), 0.0) if c in kept else 0.0)
                for c in children
            ) / set_runtime
            close(row["restart_cost_ratio"], restart, 1e-12)
            close(row["ideal_resume_cost_ratio"], resume, 1e-12)
        ca = table[(parent, "censor_aware")]
        oo = table[(parent, "observed_only")]
        reconstructed_pairs.append(
            {
                "parent": parent,
                "run_id": str(run_id),
                "task": task,
                "stratum": stratum,
                "censor_survival": float(ca["any_winner_survival"]),
                "observed_survival": float(oo["any_winner_survival"]),
                "structured_random_survival": float(ca["structured_random_any_winner"]),
                "delta_vs_observed": float(ca["any_winner_survival"]) - float(oo["any_winner_survival"]),
                "delta_vs_random": float(ca["any_winner_survival"]) - float(ca["structured_random_any_winner"]),
            }
        )
        kept = set(filter(None, ca["kept_ids"].split("|")))
        pruned = children - kept
        total_pruned += len(pruned)
        total_cards += len(children)
        total_pruned_runtime += sum(fulltime[c] for c in pruned)
        total_runtime += set_runtime
        total_tail += sum(max(fulltime[c] - float(cap120[c]["wall_s"]), 0.0) for c in pruned)
        total_probe += set_probe
        total_kept_runtime += sum(fulltime[c] for c in kept)

    paired_index = {row["parent"]: row for row in exported_pairs}
    if len(paired_index) != 100 or len(exported_pairs) != 100:
        raise AssertionError("paired rows")
    for expected in reconstructed_pairs:
        observed = paired_index[expected["parent"]]
        for key in ("run_id", "task", "stratum"):
            if observed[key] != expected[key]:
                raise AssertionError((expected["parent"], key))
        for key in (
            "censor_survival",
            "observed_survival",
            "structured_random_survival",
            "delta_vs_observed",
            "delta_vs_random",
        ):
            close(observed[key], expected[key])

    def checked_summary(column: str, block: dict[str, Any]) -> None:
        close(block["set_mean"], statistics.fmean(row[column] for row in reconstructed_pairs))
        run_point, expected_run = macro_summary(reconstructed_pairs, column, "run_id")
        task_point, expected_task = macro_summary(reconstructed_pairs, column, "task")
        close(block["run_macro_mean"], run_point)
        close(block["run_macro_ci95"][0], expected_run[0])
        close(block["run_macro_ci95"][1], expected_run[1])
        close(block["task_macro_mean"], task_point)
        close(block["task_macro_ci95"][0], expected_task[0])
        close(block["task_macro_ci95"][1], expected_task[1])

    checked_summary("censor_survival", summary["censor_survival"])
    checked_summary("delta_vs_observed", summary["delta_vs_observed"])
    checked_summary("delta_vs_random", summary["delta_vs_structured_random"])
    if summary["delta_vs_observed"]["run_sign"] != run_sign(reconstructed_pairs, "delta_vs_observed"):
        raise AssertionError("observed run sign")
    if summary["delta_vs_structured_random"]["run_sign"] != run_sign(reconstructed_pairs, "delta_vs_random"):
        raise AssertionError("random run sign")
    resources = summary["resource_accounting"]
    close(resources["aggregate_pruned_card_fraction"], total_pruned / total_cards)
    close(resources["aggregate_pruned_historical_full_runtime_fraction"], total_pruned_runtime / total_runtime)
    close(resources["aggregate_avoidable_tail_fraction"], total_tail / total_runtime)
    close(resources["aggregate_pessimistic_restart_cost_ratio"], (total_probe + total_kept_runtime) / total_runtime)
    close(resources["aggregate_optimistic_no_restart_cost_ratio"], 1 - total_tail / total_runtime)
    if resources["grader_wall_unrecorded"] is not True or resources["actual_speedup_claim_allowed"] is not False:
        raise AssertionError("cost caveat")
    if summary["signals"] != {
        "artifact_scored_cards": len(seen_scored),
        "artifact_exists_cards": len(seen_exists),
        "artifact_scored_sets": scored_sets,
    }:
        raise AssertionError("signals")

    per_task = []
    for task in sorted({row["task"] for row in reconstructed_pairs}):
        rows = [row for row in reconstructed_pairs if row["task"] == task]
        per_task.append(
            {
                "task": task,
                "sets": len(rows),
                "runs": len({row["run_id"] for row in rows}),
                "survival": statistics.fmean(row["censor_survival"] for row in rows),
                "structured_random_survival": statistics.fmean(
                    row["structured_random_survival"] for row in rows
                ),
                "delta_observed": statistics.fmean(row["delta_vs_observed"] for row in rows),
                "delta_random": statistics.fmean(row["delta_vs_random"] for row in rows),
            }
        )
    supported_min = min(row["survival"] for row in per_task if row["sets"] >= 5)
    supported_min_delta_random = min(
        row["delta_random"] for row in per_task if row["sets"] >= 5
    )
    loto_observed = {
        task: statistics.fmean(row["delta_vs_observed"] for row in reconstructed_pairs if row["task"] != task)
        for task in sorted({row["task"] for row in reconstructed_pairs})
    }
    loto_random = {
        task: statistics.fmean(row["delta_vs_random"] for row in reconstructed_pairs if row["task"] != task)
        for task in sorted({row["task"] for row in reconstructed_pairs})
    }
    close(summary["task_robustness"]["supported_task_min_survival"], supported_min)
    close(
        summary["task_robustness"]["supported_task_min_delta_random"],
        supported_min_delta_random,
    )
    for task, value in loto_observed.items():
        close(summary["task_robustness"]["loto_delta_observed"][task], value)
    for task, value in loto_random.items():
        close(summary["task_robustness"]["loto_delta_random"][task], value)

    exported_task_index = {row["task"]: row for row in exported_tasks}
    if len(exported_task_index) != len(per_task) or len(exported_tasks) != len(per_task):
        raise AssertionError("per-task row count")
    for expected in per_task:
        observed = exported_task_index[expected["task"]]
        if int(observed["sets"]) != expected["sets"] or int(observed["runs"]) != expected["runs"]:
            raise AssertionError((expected["task"], "counts"))
        close(observed["censor_survival"], expected["survival"])
        close(observed["structured_random_survival"], expected["structured_random_survival"])
        close(observed["delta_vs_observed"], expected["delta_observed"])
        close(observed["delta_vs_random"], expected["delta_random"])

    ca = summary["censor_survival"]
    do = summary["delta_vs_observed"]
    dr = summary["delta_vs_structured_random"]
    gates = {
        "survival_point_ge_0p90": ca["set_mean"] >= 0.90,
        "survival_run_ci_low_ge_0p80": ca["run_macro_ci95"][0] >= 0.80,
        "survival_task_ci_low_ge_0p75": ca["task_macro_ci95"][0] >= 0.75,
        "pruned_fraction_ge_0p10": total_pruned / total_cards >= 0.10,
        "delta_observed_point_ge_0p10": do["set_mean"] >= 0.10,
        "delta_observed_run_ci_positive": do["run_macro_ci95"][0] > 0,
        "delta_observed_task_ci_positive": do["task_macro_ci95"][0] > 0,
        "delta_observed_informative_runs_ge_10": do["run_sign"]["informative"] >= 10,
        "delta_observed_sign_p_lt_0p05": do["run_sign"]["p_two_sided"] < 0.05,
        "delta_random_point_ge_0p10": dr["set_mean"] >= 0.10,
        "delta_random_run_ci_positive": dr["run_macro_ci95"][0] > 0,
        "delta_random_task_ci_positive": dr["task_macro_ci95"][0] > 0,
        "avoidable_tail_fraction_ge_0p10": total_tail / total_runtime >= 0.10,
        "supported_task_min_survival_ge_0p60": supported_min >= 0.60,
        "supported_task_min_delta_random_nonnegative": supported_min_delta_random >= 0,
        "loto_observed_min_nonnegative": min(loto_observed.values()) >= 0,
        "loto_random_min_nonnegative": min(loto_random.values()) >= 0,
    }
    if gates != summary["gates"]:
        raise AssertionError((gates, summary["gates"]))
    random_mean = statistics.fmean(row["structured_random_survival"] for row in reconstructed_pairs)
    expected_decision = (
        "GO-FEASIBLE"
        if all(gates.values())
        else "KILL"
        if ca["set_mean"] <= random_mean or total_pruned / total_cards < 0.05
        else "BORDERLINE"
    )
    if summary["decision"] != expected_decision:
        raise AssertionError((expected_decision, summary["decision"]))
    print(
        "CENSOR_AWARE_INDEPENDENT_VERIFY_PASS",
        f"sets={len(groups)}",
        f"cards={len(nodes)}",
        f"decision={expected_decision}",
    )


if __name__ == "__main__":
    main()
