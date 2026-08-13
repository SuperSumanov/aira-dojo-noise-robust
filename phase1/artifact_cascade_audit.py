"""Adjudicate a coverage-complete 120-second artifact-first selection cascade.

This is a retrospective analysis of the frozen v9 fidelity discovery sample.  The
policy, comparisons, and gates were committed before this script was run; see the
dated preregistration.  It is exploratory and cannot replace prospective replication.
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
from typing import Any


EXPECTED = {
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
POLICIES = (
    "random",
    "stdout_only",
    "artifact_presence_then_stdout",
    "artifact_score_then_stdout",
    "artifact_score_then_random",
    "full_oracle",
    "stdout_only_keyed",
    "artifact_score_then_stdout_keyed",
)
COMPARISONS = (
    ("MAIN", "artifact_score_then_stdout", "stdout_only"),
    ("SECONDARY_SCORE_VALUE", "artifact_score_then_stdout", "artifact_presence_then_stdout"),
    ("SECONDARY_ARTIFACT_PRESENCE", "artifact_presence_then_stdout", "stdout_only"),
    ("ANCHOR_ARTIFACT_RANDOM", "artifact_score_then_random", "random"),
    ("ROBUST_KEYED_ONLY", "artifact_score_then_stdout_keyed", "stdout_only_keyed"),
)


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
    parser.add_argument("--out-dir", default="phase1/artifact_cascade_v9")
    return parser.parse_args()


def sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows = []
    with Path(path).open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as error:
                raise ValueError(f"invalid JSON at {path}:{line_number}") from error
    return rows


def finite(value: object) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def utility(value: float, task: str, lower_is_better: dict[str, bool]) -> float:
    return -float(value) if lower_is_better[task] else float(value)


def tied_best(signals: dict[str, float], task: str, lower: dict[str, bool]) -> list[str]:
    best = max(utility(value, task, lower) for value in signals.values())
    return sorted(
        card_id
        for card_id, value in signals.items()
        if math.isclose(utility(value, task, lower), best, rel_tol=0.0, abs_tol=1e-12)
    )


def evaluate(
    children: list[str],
    selected_signals: dict[str, float] | None,
    truth: dict[str, float],
    task: str,
    lower: dict[str, bool],
) -> dict[str, Any]:
    selected = children if not selected_signals else tied_best(selected_signals, task, lower)
    true_utility = {card_id: utility(truth[card_id], task, lower) for card_id in children}
    best = max(true_utility.values())
    best_ids = {
        card_id
        for card_id, value in true_utility.items()
        if math.isclose(value, best, rel_tol=0.0, abs_tol=1e-12)
    }
    ranks = {
        value: rank
        for rank, value in enumerate(sorted(set(true_utility.values()), reverse=True), 1)
    }
    return {
        "selected": "|".join(selected),
        "selected_n": len(selected),
        "top1": len(set(selected) & best_ids) / len(selected),
        "raw_regret": best - statistics.mean(true_utility[card_id] for card_id in selected),
        "rank": statistics.mean(ranks[true_utility[card_id]] for card_id in selected),
    }


def percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(quantile * len(ordered))))
    return ordered[index]


def cluster_interval(
    rows: list[dict[str, Any]], field: str, cluster: str, draws: int, seed: int,
) -> list[float]:
    grouped: dict[str, list[float]] = collections.defaultdict(list)
    for row in rows:
        grouped[str(row[cluster])].append(float(row[field]))
    keys = sorted(grouped)
    if not keys:
        raise ValueError("empty cluster population")
    rng = random.Random(seed)
    estimates = []
    for _ in range(draws):
        sampled = [rng.choice(keys) for _ in keys]
        values = [value for key in sampled for value in grouped[key]]
        estimates.append(statistics.mean(values))
    return [percentile(estimates, 0.025), percentile(estimates, 0.975)]


def exact_sign(rows: list[dict[str, Any]]) -> dict[str, int | float]:
    grouped: dict[str, list[float]] = collections.defaultdict(list)
    for row in rows:
        grouped[str(row["run_id"])].append(float(row["delta_top1"]))
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


def summarize_policy(rows: list[dict[str, Any]], draws: int, seed: int) -> dict[str, Any]:
    return {
        "sets": len(rows),
        "runs": len({row["run_id"] for row in rows}),
        "tasks": len({row["task"] for row in rows}),
        "top1": statistics.mean(float(row["top1"]) for row in rows),
        "top1_run_ci95": cluster_interval(rows, "top1", "run_id", draws, seed),
        "top1_task_ci95": cluster_interval(rows, "top1", "task", draws, seed),
        "mean_regret": statistics.mean(float(row["raw_regret"]) for row in rows),
        "median_regret": statistics.median(float(row["raw_regret"]) for row in rows),
        "mean_rank": statistics.mean(float(row["rank"]) for row in rows),
    }


def paired_comparison(
    rows: list[dict[str, Any]],
    label: str,
    a_name: str,
    b_name: str,
    draws: int,
    seed: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    indexed = {(row["parent"], row["policy"]): row for row in rows}
    parents_a = {row["parent"] for row in rows if row["policy"] == a_name}
    parents_b = {row["parent"] for row in rows if row["policy"] == b_name}
    parents = sorted(parents_a & parents_b)
    paired = []
    for parent in parents:
        a_row = indexed[(parent, a_name)]
        b_row = indexed[(parent, b_name)]
        if a_row["run_id"] != b_row["run_id"] or a_row["task"] != b_row["task"]:
            raise RuntimeError(f"pair metadata mismatch for {parent}")
        paired.append(
            {
                "parent": parent,
                "run_id": a_row["run_id"],
                "task": a_row["task"],
                "stratum": a_row["stratum"],
                "delta_top1": float(a_row["top1"]) - float(b_row["top1"]),
                "delta_regret": float(a_row["raw_regret"]) - float(b_row["raw_regret"]),
                "delta_rank": float(a_row["rank"]) - float(b_row["rank"]),
            }
        )
    tasks = sorted({row["task"] for row in paired})
    loto = {
        task: statistics.mean(row["delta_top1"] for row in paired if row["task"] != task)
        for task in tasks
    }
    result = {
        "label": label,
        "a": a_name,
        "b": b_name,
        "sets": len(paired),
        "runs": len({row["run_id"] for row in paired}),
        "tasks": len(tasks),
        "delta_top1": statistics.mean(row["delta_top1"] for row in paired),
        "run_ci95": cluster_interval(paired, "delta_top1", "run_id", draws, seed),
        "task_ci95": cluster_interval(paired, "delta_top1", "task", draws, seed),
        "run_sign": exact_sign(paired),
        "delta_mean_regret": statistics.mean(row["delta_regret"] for row in paired),
        "delta_mean_rank": statistics.mean(row["delta_rank"] for row in paired),
        "task_loto": loto,
        "task_loto_min": min(loto.values()),
        "task_loto_max": max(loto.values()),
    }
    return result, paired


def holm_adjust(raw: dict[str, float]) -> dict[str, float]:
    ordered = sorted(raw, key=raw.get)
    adjusted: dict[str, float] = {}
    running = 0.0
    total = len(ordered)
    for rank, label in enumerate(ordered):
        running = max(running, min(1.0, (total - rank) * raw[label]))
        adjusted[label] = running
    return adjusted


def git_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], text=True, capture_output=True, check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else "not-a-git-worktree"


def main() -> None:
    args = arguments()
    if args.cap != 120:
        raise ValueError("headline cap is frozen at 120 seconds")
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
    if observed_sha != EXPECTED:
        raise RuntimeError(f"input SHA mismatch: {observed_sha}")

    manifest = jsonl(paths["manifest"])
    all_results = jsonl(paths["results"])
    runtime_rows = jsonl(paths["runtime"])
    run_of = json.loads(paths["run_map"].read_text(encoding="utf-8"))
    lower = json.loads(paths["orientation"].read_text(encoding="utf-8"))

    by_parent: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    manifest_by_id: dict[str, dict[str, Any]] = {}
    manifest_ids: set[str] = set()
    for row in manifest:
        card_id = str(row["card_id"])
        if card_id in manifest_ids:
            raise RuntimeError(f"duplicate manifest card: {card_id}")
        if not finite(row.get("graded")):
            raise RuntimeError(f"nonfinite truth: {card_id}")
        manifest_ids.add(card_id)
        manifest_by_id[card_id] = row
        by_parent[str(row["parent"])].append(row)

    cap_index: dict[str, dict[str, Any]] = {}
    seen_result_keys: set[tuple[str, int]] = set()
    for row in all_results:
        key = (str(row["card_id"]), int(row["cap"]))
        if key in seen_result_keys:
            raise RuntimeError(f"duplicate result: {key}")
        seen_result_keys.add(key)
        if key[1] == args.cap:
            cap_index[key[0]] = row
    if set(cap_index) != manifest_ids:
        raise RuntimeError("120-second result coverage mismatch")
    if len(seen_result_keys) != 2 * len(manifest_ids):
        raise RuntimeError("expected exactly two cap results per card")
    expected_result_keys = {
        (card_id, cap) for card_id in manifest_ids for cap in (30, 120)
    }
    if seen_result_keys != expected_result_keys:
        raise RuntimeError("result keys differ from the frozen 30/120 grid")
    for card_id, row in cap_index.items():
        source = manifest_by_id[card_id]
        if (
            row.get("competition") != source.get("competition")
            or row.get("parent") != source.get("parent")
            or row.get("stratum") != source.get("stratum")
            or not math.isclose(float(row["graded"]), float(source["graded"]), abs_tol=1e-15)
        ):
            raise RuntimeError(f"result metadata mismatch: {card_id}")
        if finite(row.get("sub_score")) and not row.get("sub_exists"):
            raise RuntimeError(f"graded artifact marked absent: {card_id}")
        if finite(row.get("stdout_val")) != (row.get("val_how") in {"keyed", "bare"}):
            raise RuntimeError(f"stdout parser metadata mismatch: {card_id}")

    runtime: dict[str, float] = {}
    for row in runtime_rows:
        card_id = str(row["card_id"])
        if card_id in runtime or not finite(row.get("runtime_s")) or float(row["runtime_s"]) < 0:
            raise RuntimeError(f"bad runtime row: {card_id}")
        runtime[card_id] = float(row["runtime_s"])
    if set(runtime) != manifest_ids:
        raise RuntimeError("runtime coverage mismatch")

    set_rows: list[dict[str, Any]] = []
    for parent, members in sorted(by_parent.items()):
        children = sorted(str(member["card_id"]) for member in members)
        tasks = {str(member["competition"]) for member in members}
        strata = {str(member["stratum"]) for member in members}
        runs = {run_of.get(card_id) for card_id in children}
        if len(children) < 2 or len(tasks) != 1 or len(strata) != 1 or len(runs) != 1:
            raise RuntimeError(f"invalid sibling set: {parent}")
        task, stratum, run_id = next(iter(tasks)), next(iter(strata)), next(iter(runs))
        if run_id is None or task not in lower:
            raise RuntimeError(f"missing run/orientation for {parent}")

        truth = {str(member["card_id"]): float(member["graded"]) for member in members}
        artifact = {
            card_id: float(cap_index[card_id]["sub_score"])
            for card_id in children
            if finite(cap_index[card_id].get("sub_score"))
        }
        stdout = {
            card_id: float(cap_index[card_id]["stdout_val"])
            for card_id in children
            if finite(cap_index[card_id].get("stdout_val"))
        }
        stdout_keyed = {
            card_id: value
            for card_id, value in stdout.items()
            if cap_index[card_id].get("val_how") == "keyed"
        }
        presence = {card_id: 0.0 for card_id in artifact}
        policy_signals: dict[str, dict[str, float] | None] = {
            "random": None,
            "stdout_only": stdout or None,
            "artifact_presence_then_stdout": presence if artifact else (stdout or None),
            "artifact_score_then_stdout": artifact if artifact else (stdout or None),
            "artifact_score_then_random": artifact or None,
            "full_oracle": truth,
            "stdout_only_keyed": stdout_keyed or None,
            "artifact_score_then_stdout_keyed": artifact if artifact else (stdout_keyed or None),
        }
        low_wall = sum(float(cap_index[card_id]["wall_s"]) for card_id in children)
        full_runtime = sum(runtime[card_id] for card_id in children)
        for policy in POLICIES:
            measured = evaluate(children, policy_signals[policy], truth, task, lower)
            set_rows.append(
                {
                    "parent": parent,
                    "run_id": run_id,
                    "task": task,
                    "stratum": stratum,
                    "n_children": len(children),
                    "n_artifact": len(artifact),
                    "n_stdout": len(stdout),
                    "n_stdout_keyed": len(stdout_keyed),
                    "policy": policy,
                    "low_wall_s": low_wall,
                    "full_runtime_s": full_runtime,
                    "cost_ratio": low_wall / full_runtime,
                    **measured,
                }
            )

    oracle_rows = [row for row in set_rows if row["policy"] == "full_oracle"]
    random_rows = [row for row in set_rows if row["policy"] == "random"]
    artifact_random_rows = [
        row for row in set_rows if row["policy"] == "artifact_score_then_random"
    ]
    counts = {
        "sets": len(by_parent),
        "cards": len(manifest_ids),
        "runs": len({row["run_id"] for row in oracle_rows}),
        "tasks": len({row["task"] for row in oracle_rows}),
        "hard": sum(row["stratum"] == "hard" for row in oracle_rows),
        "easy": sum(row["stratum"] == "easy" for row in oracle_rows),
    }
    if counts != EXPECTED_COUNTS:
        raise RuntimeError(f"frozen population mismatch: {counts}")
    if not all(row["top1"] == 1.0 and abs(row["raw_regret"]) <= 1e-15 for row in oracle_rows):
        raise RuntimeError("oracle positive control failed")
    if not math.isclose(statistics.mean(row["top1"] for row in random_rows), 0.4598333333333333):
        raise RuntimeError("random anchor failed")
    if not math.isclose(
        statistics.mean(row["top1"] for row in artifact_random_rows), 0.5783333333333334,
    ):
        raise RuntimeError("artifact/random anchor failed")

    policy_summary = {}
    for stratum in ("ALL_BALANCED", "hard", "easy"):
        policy_summary[stratum] = {}
        for policy in POLICIES:
            rows = [row for row in set_rows if row["policy"] == policy]
            if stratum != "ALL_BALANCED":
                rows = [row for row in rows if row["stratum"] == stratum]
            policy_summary[stratum][policy] = summarize_policy(
                rows, args.bootstrap, args.seed,
            )

    comparisons = []
    paired_outputs = {}
    for label, a_name, b_name in COMPARISONS:
        comparison, paired = paired_comparison(
            set_rows, label, a_name, b_name, args.bootstrap, args.seed,
        )
        comparisons.append(comparison)
        paired_outputs[label] = paired
    indexed_comparisons = {item["label"]: item for item in comparisons}
    secondary_raw = {
        label: float(indexed_comparisons[label]["run_sign"]["p_two_sided"])
        for label in ("SECONDARY_SCORE_VALUE", "SECONDARY_ARTIFACT_PRESENCE")
    }
    secondary_holm = holm_adjust(secondary_raw)
    for label, adjusted in secondary_holm.items():
        indexed_comparisons[label]["run_sign_holm_p"] = adjusted

    all_policy_rows = [
        row for row in set_rows if row["policy"] == "artifact_score_then_stdout"
    ]
    aggregate_cost_ratio = (
        sum(float(row["low_wall_s"]) for row in all_policy_rows)
        / sum(float(row["full_runtime_s"]) for row in all_policy_rows)
    )
    main = indexed_comparisons["MAIN"]
    score_value = indexed_comparisons["SECONDARY_SCORE_VALUE"]
    cascade_go = bool(
        main["delta_top1"] >= 0.08
        and main["run_ci95"][0] > 0
        and main["task_ci95"][0] > 0
        and main["run_sign"]["p_two_sided"] < 0.05
        and main["task_loto_min"] > -0.10
        and aggregate_cost_ratio <= 0.35
    )
    channel_go = bool(
        cascade_go
        and score_value["delta_top1"] >= 0.03
        and score_value["run_ci95"][0] > 0
    )
    if cascade_go:
        decision = "CHANNEL-GO" if channel_go else "CASCADE-GO_ONLY"
    elif main["delta_top1"] <= 0 or main["run_ci95"][1] <= 0:
        decision = "KILL"
    else:
        decision = "BORDERLINE"

    out_dir = Path(args.out_dir)
    if out_dir.exists() and any(out_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite non-empty directory: {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "per_set_policy.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(set_rows[0]))
        writer.writeheader()
        writer.writerows(set_rows)
    with (out_dir / "main_paired.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(paired_outputs["MAIN"][0]))
        writer.writeheader()
        writer.writerows(paired_outputs["MAIN"])

    per_task = []
    for task in sorted({row["task"] for row in paired_outputs["MAIN"]}):
        task_rows = [row for row in paired_outputs["MAIN"] if row["task"] == task]
        per_task.append(
            {
                "task": task,
                "sets": len(task_rows),
                "runs": len({row["run_id"] for row in task_rows}),
                "delta_top1": statistics.mean(row["delta_top1"] for row in task_rows),
            }
        )
    with (out_dir / "per_task.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(per_task[0]))
        writer.writeheader()
        writer.writerows(per_task)

    provenance = {
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
    }
    summary = {
        "provenance": provenance,
        "status": "retrospective discovery-set adjudication; not confirmatory",
        "counts": counts,
        "signal_counts": {
            "artifact_cards": sum(
                finite(cap_index[card_id].get("sub_score")) for card_id in manifest_ids
            ),
            "stdout_cards": sum(
                finite(cap_index[card_id].get("stdout_val")) for card_id in manifest_ids
            ),
            "keyed_stdout_cards": sum(
                finite(cap_index[card_id].get("stdout_val"))
                and cap_index[card_id].get("val_how") == "keyed"
                for card_id in manifest_ids
            ),
            "artifact_sets": sum(row["n_artifact"] > 0 for row in all_policy_rows),
            "stdout_sets": sum(row["n_stdout"] > 0 for row in all_policy_rows),
        },
        "aggregate_120s_cost_ratio_to_historical_full": aggregate_cost_ratio,
        "policy_summary": policy_summary,
        "comparisons": comparisons,
        "gates": {
            "cascade_go": cascade_go,
            "channel_go": channel_go,
            "decision": decision,
        },
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
        f"SIGNALS artifact_cards={summary['signal_counts']['artifact_cards']} "
        f"stdout_cards={summary['signal_counts']['stdout_cards']} "
        f"artifact_sets={summary['signal_counts']['artifact_sets']} "
        f"cost_ratio={aggregate_cost_ratio:.4f}"
    )
    for comparison in comparisons:
        print(
            f"{comparison['label']:28s} delta={comparison['delta_top1']:+.4f} "
            f"runCI=[{comparison['run_ci95'][0]:+.4f},{comparison['run_ci95'][1]:+.4f}] "
            f"taskCI=[{comparison['task_ci95'][0]:+.4f},{comparison['task_ci95'][1]:+.4f}] "
            f"sign_p={comparison['run_sign']['p_two_sided']:.6f}"
        )
    print(f"DECISION {decision}")
    print(f"WROTE {out_dir}")


if __name__ == "__main__":
    main()
