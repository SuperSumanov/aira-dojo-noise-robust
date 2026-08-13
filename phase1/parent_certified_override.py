"""Adjudicate one frozen parent-certified artifact override policy.

This is a retrospective analysis of the frozen v9 fidelity discovery sample.
The policy, inputs, comparisons, and gates must be committed before execution.
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
    "cards": "daeb29fc07ad670b5ca7a10cd2d84f1fa9a27dfa9d22510533417f1a8ad9407f",
}
EXPECTED_COUNTS = {
    "sets": 100,
    "cards": 230,
    "runs": 52,
    "tasks": 19,
    "hard": 50,
    "easy": 50,
    "corpus_cards": 12383,
    "parent_available": 88,
    "parent_missing": 12,
}
POLICIES = (
    "random",
    "stdout_only",
    "artifact_score_then_stdout",
    "parent_certified_override",
    "full_oracle",
)
COMPARISONS = (
    ("MAIN_PARENT_VS_STDOUT", "parent_certified_override", "stdout_only"),
    (
        "SECONDARY_PARENT_VS_NAIVE",
        "parent_certified_override",
        "artifact_score_then_stdout",
    ),
)
EPSILON = 1e-12


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default="phase1/fidelity_manifest.jsonl")
    parser.add_argument("--results", default="phase1/fidelity_results.jsonl")
    parser.add_argument("--runtime", default="phase1/fidelity_runtime_v9.jsonl")
    parser.add_argument("--run-map", default="phase1/card_run_map.json")
    parser.add_argument("--orientation", default="phase1/task_orientation.json")
    parser.add_argument("--cards", default="phase1/cards_current_v9.jsonl")
    parser.add_argument("--cap", type=int, default=120)
    parser.add_argument("--bootstrap", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=20260813)
    parser.add_argument("--out-dir", default="phase1/parent_certified_v9")
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


def tied_best(
    candidates: list[str],
    signals: dict[str, float] | None,
    task: str,
    lower_is_better: dict[str, bool],
) -> list[str]:
    if not signals:
        return sorted(candidates)
    best = max(utility(value, task, lower_is_better) for value in signals.values())
    return sorted(
        card_id
        for card_id, value in signals.items()
        if math.isclose(
            utility(value, task, lower_is_better), best, rel_tol=0.0, abs_tol=EPSILON
        )
    )


def evaluate(
    candidates: list[str],
    signals: dict[str, float] | None,
    truth: dict[str, float],
    task: str,
    lower_is_better: dict[str, bool],
    parent_score: float | None,
) -> dict[str, Any]:
    selected = tied_best(candidates, signals, task, lower_is_better)
    truth_utility = {
        card_id: utility(value, task, lower_is_better) for card_id, value in truth.items()
    }
    best = max(truth_utility.values())
    worst = min(truth_utility.values())
    best_ids = {
        card_id
        for card_id, value in truth_utility.items()
        if math.isclose(value, best, rel_tol=0.0, abs_tol=EPSILON)
    }
    levels = sorted(set(truth_utility.values()), reverse=True)
    ranks = {value: rank + 1 for rank, value in enumerate(levels)}
    chosen_utility = statistics.mean(truth_utility[card_id] for card_id in selected)
    parent_improvement = ""
    if parent_score is not None:
        parent_utility = utility(parent_score, task, lower_is_better)
        parent_improvement = statistics.mean(
            truth_utility[card_id] > parent_utility + EPSILON for card_id in selected
        )
    raw_regret = best - chosen_utility
    return {
        "selected": "|".join(selected),
        "selected_n": len(selected),
        "top1": len(set(selected) & best_ids) / len(selected),
        "raw_regret": raw_regret,
        "normalized_regret": raw_regret / (best - worst) if best > worst else 0.0,
        "rank": statistics.mean(ranks[truth_utility[card_id]] for card_id in selected),
        "selected_final_improves_parent": parent_improvement,
    }


def percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(quantile * len(ordered))))
    return ordered[index]


def cluster_interval(
    rows: list[dict[str, Any]], field: str, cluster: str, draws: int, seed: int
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
    parent_rows = [row for row in rows if row["selected_final_improves_parent"] != ""]
    return {
        "sets": len(rows),
        "runs": len({row["run_id"] for row in rows}),
        "tasks": len({row["task"] for row in rows}),
        "top1": statistics.mean(float(row["top1"]) for row in rows),
        "top1_run_ci95": cluster_interval(rows, "top1", "run_id", draws, seed),
        "top1_task_ci95": cluster_interval(rows, "top1", "task", draws, seed),
        "median_raw_regret": statistics.median(float(row["raw_regret"]) for row in rows),
        "mean_normalized_regret": statistics.mean(
            float(row["normalized_regret"]) for row in rows
        ),
        "median_normalized_regret": statistics.median(
            float(row["normalized_regret"]) for row in rows
        ),
        "mean_rank": statistics.mean(float(row["rank"]) for row in rows),
        "parent_known_sets": len(parent_rows),
        "selected_final_improves_parent_rate": statistics.mean(
            float(row["selected_final_improves_parent"]) for row in parent_rows
        ),
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
                "override_active": a_row["override_active"],
                "delta_top1": float(a_row["top1"]) - float(b_row["top1"]),
                "delta_normalized_regret": (
                    float(a_row["normalized_regret"])
                    - float(b_row["normalized_regret"])
                ),
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
        "delta_mean_normalized_regret": statistics.mean(
            row["delta_normalized_regret"] for row in paired
        ),
        "delta_mean_rank": statistics.mean(row["delta_rank"] for row in paired),
        "task_loto": loto,
        "task_loto_min": min(loto.values()),
        "task_loto_max": max(loto.values()),
    }
    return result, paired


def git_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], text=True, capture_output=True, check=False
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
        "cards": Path(args.cards),
    }
    observed_sha = {name: sha256(path) for name, path in paths.items()}
    if observed_sha != EXPECTED:
        raise RuntimeError(f"input SHA mismatch: {observed_sha}")

    manifest = jsonl(paths["manifest"])
    all_results = jsonl(paths["results"])
    runtime_rows = jsonl(paths["runtime"])
    card_rows = jsonl(paths["cards"])
    run_of = json.loads(paths["run_map"].read_text(encoding="utf-8"))
    lower = json.loads(paths["orientation"].read_text(encoding="utf-8"))

    cards: dict[str, dict[str, Any]] = {}
    for row in card_rows:
        card_id = str(row["id"])
        if card_id in cards:
            raise RuntimeError(f"duplicate corpus card: {card_id}")
        cards[card_id] = row
    if len(cards) != EXPECTED_COUNTS["corpus_cards"]:
        raise RuntimeError(f"corpus card count mismatch: {len(cards)}")

    by_parent: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    manifest_by_id: dict[str, dict[str, Any]] = {}
    for row in manifest:
        card_id = str(row["card_id"])
        if card_id in manifest_by_id:
            raise RuntimeError(f"duplicate manifest card: {card_id}")
        if not finite(row.get("graded")):
            raise RuntimeError(f"nonfinite truth: {card_id}")
        manifest_by_id[card_id] = row
        by_parent[str(row["parent"])].append(row)
    manifest_ids = set(manifest_by_id)

    cap_index: dict[str, dict[str, Any]] = {}
    seen_result_keys: set[tuple[str, int]] = set()
    for row in all_results:
        key = (str(row["card_id"]), int(row["cap"]))
        if key in seen_result_keys:
            raise RuntimeError(f"duplicate result: {key}")
        seen_result_keys.add(key)
        if key[1] == args.cap:
            cap_index[key[0]] = row
    expected_result_keys = {
        (card_id, cap) for card_id in manifest_ids for cap in (30, 120)
    }
    if seen_result_keys != expected_result_keys or set(cap_index) != manifest_ids:
        raise RuntimeError("result grid or 120-second coverage mismatch")
    for card_id, row in cap_index.items():
        source = manifest_by_id[card_id]
        if (
            row.get("competition") != source.get("competition")
            or row.get("parent") != source.get("parent")
            or row.get("stratum") != source.get("stratum")
            or not math.isclose(
                float(row["graded"]), float(source["graded"]), abs_tol=1e-15
            )
        ):
            raise RuntimeError(f"result metadata mismatch: {card_id}")
        if finite(row.get("sub_score")) and not row.get("sub_exists"):
            raise RuntimeError(f"graded artifact marked absent: {card_id}")
        if finite(row.get("stdout_val")) != (
            row.get("val_how") in {"keyed", "bare"}
        ):
            raise RuntimeError(f"stdout parser metadata mismatch: {card_id}")

    runtime: dict[str, float] = {}
    for row in runtime_rows:
        card_id = str(row["card_id"])
        if card_id in runtime or not finite(row.get("runtime_s")):
            raise RuntimeError(f"bad runtime row: {card_id}")
        value = float(row["runtime_s"])
        if value < 0:
            raise RuntimeError(f"negative runtime: {card_id}")
        runtime[card_id] = value
    if set(runtime) != manifest_ids:
        raise RuntimeError("runtime coverage mismatch")
    if not manifest_ids.issubset(run_of):
        raise RuntimeError("run map does not cover every manifest card")

    parent_score: dict[str, float] = {}
    for parent, members in by_parent.items():
        if parent not in cards:
            continue
        card = cards[parent]
        card_task = card.get("task")
        if not isinstance(card_task, dict):
            raise RuntimeError(f"parent task schema mismatch: {parent}")
        tasks = {str(member["competition"]) for member in members}
        if len(tasks) != 1:
            raise RuntimeError(f"multi-task sibling set: {parent}")
        task = next(iter(tasks))
        if (
            card_task.get("name") != task
            or not isinstance(card_task.get("higher_is_better"), bool)
            or card_task["higher_is_better"] is not (not bool(lower[task]))
        ):
            raise RuntimeError(f"parent task/orientation mismatch: {parent}")
        value = (card.get("label") or {}).get("graded")
        if not finite(value):
            raise RuntimeError(f"present parent has nonfinite score: {parent}")
        children = [str(member["card_id"]) for member in members]
        child_cards = [cards.get(card_id) for card_id in children]
        if any(child is None for child in child_cards):
            raise RuntimeError(f"manifest child missing from corpus: {parent}")
        if any(
            (child.get("lineage") or {}).get("parent_id") != parent
            for child in child_cards
            if child is not None
        ):
            raise RuntimeError(f"child lineage does not point to parent: {parent}")
        if any(
            child.get("run_id") != card.get("run_id")
            for child in child_cards
            if child is not None
        ):
            raise RuntimeError(f"parent/child physical run mismatch: {parent}")
        if {run_of[card_id] for card_id in children} != {card.get("run_id")}:
            raise RuntimeError(f"run-map/corpus run mismatch: {parent}")
        parent_step = (card.get("lineage") or {}).get("step")
        child_steps = [
            (child.get("lineage") or {}).get("step")
            for child in child_cards
            if child is not None
        ]
        if (
            not isinstance(parent_step, int)
            or len(child_steps) != len(children)
            or any(not isinstance(step, int) or step <= parent_step for step in child_steps)
        ):
            raise RuntimeError(f"parent is not temporally prior to children: {parent}")
        parent_score[parent] = float(value)

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
        anchor = parent_score.get(parent)
        certified = {}
        if anchor is not None:
            anchor_utility = utility(anchor, task, lower)
            certified = {
                card_id: value
                for card_id, value in artifact.items()
                if utility(value, task, lower) > anchor_utility + EPSILON
            }
        policy_signals: dict[str, dict[str, float] | None] = {
            "random": None,
            "stdout_only": stdout or None,
            "artifact_score_then_stdout": artifact if artifact else (stdout or None),
            "parent_certified_override": certified if certified else (stdout or None),
            "full_oracle": truth,
        }
        low_wall = sum(float(cap_index[card_id]["wall_s"]) for card_id in children)
        full_runtime = sum(runtime[card_id] for card_id in children)
        for policy in POLICIES:
            measured = evaluate(
                children, policy_signals[policy], truth, task, lower, anchor
            )
            set_rows.append(
                {
                    "parent": parent,
                    "run_id": run_id,
                    "task": task,
                    "stratum": stratum,
                    "n_children": len(children),
                    "n_artifact": len(artifact),
                    "n_stdout": len(stdout),
                    "parent_available": anchor is not None,
                    "n_certified": len(certified),
                    "certificate_passed": bool(certified),
                    "override_active": bool(certified),
                    "policy": policy,
                    "low_wall_s": low_wall,
                    "full_runtime_s": full_runtime,
                    "cost_ratio": low_wall / full_runtime,
                    **measured,
                }
            )

    oracle_rows = [row for row in set_rows if row["policy"] == "full_oracle"]
    parent_policy_rows = [
        row for row in set_rows if row["policy"] == "parent_certified_override"
    ]
    counts = {
        "sets": len(by_parent),
        "cards": len(manifest_ids),
        "runs": len({row["run_id"] for row in oracle_rows}),
        "tasks": len({row["task"] for row in oracle_rows}),
        "hard": sum(row["stratum"] == "hard" for row in oracle_rows),
        "easy": sum(row["stratum"] == "easy" for row in oracle_rows),
        "corpus_cards": len(cards),
        "parent_available": len(parent_score),
        "parent_missing": len(by_parent) - len(parent_score),
    }
    if counts != EXPECTED_COUNTS:
        raise RuntimeError(f"frozen population mismatch: {counts}")
    if not all(
        row["top1"] == 1.0 and abs(float(row["raw_regret"])) <= EPSILON
        for row in oracle_rows
    ):
        raise RuntimeError("oracle positive control failed")

    anchors = {
        policy: statistics.mean(
            float(row["top1"]) for row in set_rows if row["policy"] == policy
        )
        for policy in ("random", "stdout_only", "artifact_score_then_stdout")
    }
    expected_anchors = {
        "random": 0.4598333333333333,
        "stdout_only": 0.5383333333333333,
        "artifact_score_then_stdout": 0.6083333333333333,
    }
    for policy, expected in expected_anchors.items():
        if not math.isclose(anchors[policy], expected, rel_tol=0.0, abs_tol=1e-15):
            raise RuntimeError(f"{policy} anchor failed: {anchors[policy]}")

    policy_summary = {}
    for stratum in ("ALL_BALANCED", "hard", "easy"):
        policy_summary[stratum] = {}
        for policy in POLICIES:
            rows = [row for row in set_rows if row["policy"] == policy]
            if stratum != "ALL_BALANCED":
                rows = [row for row in rows if row["stratum"] == stratum]
            policy_summary[stratum][policy] = summarize_policy(
                rows, args.bootstrap, args.seed
            )

    comparisons = []
    paired_outputs = {}
    for label, a_name, b_name in COMPARISONS:
        comparison, paired = paired_comparison(
            set_rows, label, a_name, b_name, args.bootstrap, args.seed
        )
        comparisons.append(comparison)
        paired_outputs[label] = paired
    indexed = {item["label"]: item for item in comparisons}
    main = indexed["MAIN_PARENT_VS_STDOUT"]

    support = {
        "sets": sum(bool(row["certificate_passed"]) for row in parent_policy_rows),
        "runs": len(
            {row["run_id"] for row in parent_policy_rows if row["certificate_passed"]}
        ),
        "tasks": len(
            {row["task"] for row in parent_policy_rows if row["certificate_passed"]}
        ),
    }
    macro_cost_ratio = statistics.mean(
        float(row["cost_ratio"]) for row in parent_policy_rows
    )
    aggregate_cost_ratio = sum(
        float(row["low_wall_s"]) for row in parent_policy_rows
    ) / sum(float(row["full_runtime_s"]) for row in parent_policy_rows)

    support_ok = support["sets"] >= 15 and support["runs"] >= 8
    go = bool(
        support_ok
        and main["delta_top1"] >= 0.08
        and main["run_ci95"][0] > 0
        and main["task_ci95"][0] > 0
        and main["run_sign"]["p_two_sided"] < 0.05
        and main["task_loto_min"] > -0.10
        and macro_cost_ratio <= 0.35
    )
    if not support_ok:
        decision = "KILL-UNDERSUPPORTED"
    elif go:
        decision = "PARENT-GO"
    elif main["delta_top1"] <= 0 or main["run_ci95"][1] <= 0:
        decision = "KILL"
    else:
        decision = "BORDERLINE"

    out_dir = Path(args.out_dir)
    if out_dir.exists():
        raise FileExistsError(f"refusing to reuse existing output path: {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=False)
    with (out_dir / "per_set_policy.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(set_rows[0]), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(set_rows)
    with (out_dir / "main_paired.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(paired_outputs["MAIN_PARENT_VS_STDOUT"][0]),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(paired_outputs["MAIN_PARENT_VS_STDOUT"])

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
        "epsilon": EPSILON,
    }
    summary = {
        "provenance": provenance,
        "status": "retrospective discovery-set adjudication; not confirmatory",
        "anchor_semantics": (
            "historical label.graded is a retrospective stand-in for a causally prior "
            "permitted D_search score; this run is not deployment-valid confirmation"
        ),
        "counts": counts,
        "anchors": anchors,
        "support": support,
        "cost": {
            "macro_mean_set_ratio_to_historical_full": macro_cost_ratio,
            "aggregate_ratio_to_historical_full": aggregate_cost_ratio,
            "gate_uses": "macro_mean_set_ratio_to_historical_full",
        },
        "policy_summary": policy_summary,
        "comparisons": comparisons,
        "gates": {"support_ok": support_ok, "go": go, "decision": decision},
    }
    (out_dir / "summary.json").write_text(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        f"VERIFIED sets={counts['sets']} cards={counts['cards']} runs={counts['runs']} "
        f"tasks={counts['tasks']} parents={counts['parent_available']}"
    )
    print(
        f"SUPPORT sets={support['sets']} runs={support['runs']} tasks={support['tasks']} "
        f"cost_macro={macro_cost_ratio:.4f} cost_aggregate={aggregate_cost_ratio:.4f}"
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
