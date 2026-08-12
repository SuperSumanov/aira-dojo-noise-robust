"""Task-conditional finite-sample certificate for low-fidelity early stopping.

This is the preregistered zero-GPU test in
``实验记录/2026-08-13/任务条件风险证书早停_预注册.md``.  Calibration uses
only non-hold physical runs from corpus v10.  The frozen fidelity manifest is used as
the test population.  Decisions depend only on task identity, cap-time external artifact
scores, and calibration thresholds; final test grades are used only after decisions are
fixed to evaluate deployment quality.
"""

from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import math
import platform
import random
import statistics
import subprocess
from pathlib import Path


ALPHAS = (0.05, 0.10, 0.20)


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cards", default="phase1/cards_current_v10.jsonl")
    parser.add_argument(
        "--split", default="phase1/v10_decision/runsplit_holdruns_v10.json"
    )
    parser.add_argument("--manifest", default="phase1/fidelity_manifest.jsonl")
    parser.add_argument("--results", default="phase1/fidelity_results.jsonl")
    parser.add_argument("--runtime-map", default="phase1/fidelity_runtime_v9.jsonl")
    parser.add_argument("--orientation", default="phase1/task_orientation.json")
    parser.add_argument("--cap", type=int, default=120)
    parser.add_argument("--bootstrap", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--out-dir", default="phase1/task_conformal_early_stop_v10")
    return parser.parse_args()


def jsonl(path: Path):
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"invalid JSON: {path}:{line_number}") from error


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def finite(value: object) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def utility(score: float, task: str, lower: dict[str, bool]) -> float:
    return -float(score) if lower.get(task, False) else float(score)


def percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(quantile * len(ordered))))
    return ordered[index]


def run_bootstrap(
    rows: list[dict], field: str, draws: int, seed: int
) -> tuple[float, float]:
    groups: dict[str, list[float]] = collections.defaultdict(list)
    for row in rows:
        groups[row["run_id"]].append(float(row[field]))
    keys = sorted(groups)
    if not keys:
        raise ValueError("empty bootstrap population")
    rng = random.Random(seed)
    estimates = []
    for _ in range(draws):
        sampled = [rng.choice(keys) for _ in keys]
        values = [value for key in sampled for value in groups[key]]
        estimates.append(statistics.mean(values))
    return percentile(estimates, 0.025), percentile(estimates, 0.975)


def tied_best(scores: dict[str, float]) -> list[str]:
    best = max(scores.values())
    return sorted(
        card_id
        for card_id, score in scores.items()
        if math.isclose(score, best, abs_tol=1e-12)
    )


def expected_endpoint_identity(chosen: list[str], truth: dict[str, float]) -> float:
    best = max(truth.values())
    best_ids = {
        card_id
        for card_id, score in truth.items()
        if math.isclose(score, best, abs_tol=1e-12)
    }
    return sum(card_id in best_ids for card_id in chosen) / len(chosen)


def calibration_threshold(values: list[float], alpha: float) -> tuple[float, int]:
    n_values = len(values)
    rank = math.ceil((n_values + 1) * (1.0 - alpha))
    if rank > n_values:
        return math.inf, rank
    return sorted(values)[rank - 1], rank


def card_label(row: dict) -> object:
    label = row.get("label")
    if isinstance(label, dict):
        return label.get("graded")
    return row.get("graded")


def card_task(row: dict) -> str:
    task = row.get("task")
    if isinstance(task, dict):
        return str(task.get("name"))
    return str(row.get("competition") or task)


def main() -> None:
    args = arguments()
    paths = {
        name: Path(value)
        for name, value in {
            "cards": args.cards,
            "split": args.split,
            "manifest": args.manifest,
            "results": args.results,
            "runtime_map": args.runtime_map,
            "orientation": args.orientation,
        }.items()
    }
    for name, path in paths.items():
        if not path.is_file():
            raise FileNotFoundError(f"missing {name}: {path}")

    split = json.loads(paths["split"].read_text(encoding="utf-8"))
    all_runs = set(split["all"])
    hold_runs = set(split["hold"])
    if not hold_runs or not hold_runs < all_runs:
        raise RuntimeError("invalid frozen run split")
    if set(split.get("prior_hold", [])) - hold_runs:
        raise RuntimeError("v10 did not preserve prior hold runs")

    lower = json.loads(paths["orientation"].read_text(encoding="utf-8"))
    manifest = list(jsonl(paths["manifest"]))
    by_parent: dict[str, list[dict]] = collections.defaultdict(list)
    for row in manifest:
        by_parent[row["parent"]].append(row)
    manifest_ids = {row["card_id"] for row in manifest}
    if len(manifest_ids) != len(manifest):
        raise RuntimeError("duplicate card in fidelity manifest")

    cap_rows = [row for row in jsonl(paths["results"]) if int(row["cap"]) == args.cap]
    cap_results = {row["card_id"]: row for row in cap_rows}
    if len(cap_results) != len(cap_rows) or set(cap_results) != manifest_ids:
        raise RuntimeError("cap result coverage mismatch")

    runtime_rows = list(jsonl(paths["runtime_map"]))
    runtime = {row["card_id"]: float(row["runtime_s"]) for row in runtime_rows}
    if len(runtime) != len(runtime_rows) or set(runtime) != manifest_ids:
        raise RuntimeError("runtime coverage mismatch")

    test_parent_ids = set(by_parent)
    test_node_ids = manifest_ids | test_parent_ids
    test_pairs = {(row["parent"], row["card_id"]) for row in manifest}
    card_ids: set[str] = set()
    card_run: dict[str, str] = {}
    card_task_map: dict[str, str] = {}
    test_code_hashes: set[str] = set()
    calibration_code_hashes: set[str] = set()
    calibration_pairs: set[tuple[str, str]] = set()
    run_tasks: dict[str, set[str]] = collections.defaultdict(set)
    run_maxima: dict[tuple[str, str], float] = {}
    corpus_cards = 0
    finite_cards = 0
    nonfinite_cards = 0

    for row in jsonl(paths["cards"]):
        corpus_cards += 1
        card_id = str(row["id"])
        if card_id in card_ids:
            raise RuntimeError(f"duplicate corpus card id: {card_id}")
        card_ids.add(card_id)
        run_id = str(row["run_id"])
        task = card_task(row)
        if run_id not in all_runs:
            raise RuntimeError(f"run absent from frozen split: {run_id}")
        if task not in lower:
            raise RuntimeError(f"orientation missing for task: {task}")
        card_run[card_id] = run_id
        card_task_map[card_id] = task
        run_tasks[run_id].add(task)
        code_hash = hashlib.sha256((row.get("code") or "").encode("utf-8")).hexdigest()
        if card_id in test_node_ids:
            test_code_hashes.add(code_hash)
        if run_id not in hold_runs:
            calibration_code_hashes.add(code_hash)
            parent_id = (row.get("lineage") or {}).get("parent_id")
            if parent_id:
                calibration_pairs.add((str(parent_id), card_id))
        grade = card_label(row)
        if not finite(grade):
            nonfinite_cards += 1
            continue
        finite_cards += 1
        if run_id in hold_runs:
            continue
        key = (task, run_id)
        value = utility(float(grade), task, lower)
        run_maxima[key] = max(value, run_maxima.get(key, -math.inf))

    if any(len(tasks) != 1 for tasks in run_tasks.values()):
        raise RuntimeError("mixed-task physical run")
    if set(card_run) != card_ids or corpus_cards != len(card_ids):
        raise RuntimeError("card accounting mismatch")
    if not manifest_ids <= card_ids:
        raise RuntimeError("fidelity card absent from v10 corpus")

    manifest_runs = {card_run[card_id] for card_id in manifest_ids}
    manifest_tasks = {card_task_map[card_id] for card_id in manifest_ids}
    if not manifest_runs <= hold_runs:
        raise RuntimeError("fidelity test run entered calibration side")
    if any(card_run[node] not in hold_runs for node in test_node_ids if node in card_run):
        raise RuntimeError("fidelity test node entered calibration side")

    node_overlap = {
        card_id for card_id in test_node_ids if card_id in card_run and card_run[card_id] not in hold_runs
    }
    pair_overlap = test_pairs & calibration_pairs
    code_hash_overlap = test_code_hashes & calibration_code_hashes
    if node_overlap or pair_overlap or code_hash_overlap:
        raise RuntimeError(
            "train-test leakage: "
            f"nodes={len(node_overlap)} pairs={len(pair_overlap)} code_hash={len(code_hash_overlap)}"
        )

    maxima_by_task: dict[str, list[float]] = collections.defaultdict(list)
    for (task, _run_id), value in run_maxima.items():
        maxima_by_task[task].append(value)

    calibration_rows = []
    thresholds: dict[float, dict[str, float]] = {alpha: {} for alpha in ALPHAS}
    for task in sorted(manifest_tasks):
        values = maxima_by_task.get(task, [])
        for alpha in ALPHAS:
            threshold, rank = calibration_threshold(values, alpha)
            thresholds[alpha][task] = threshold
            calibration_rows.append(
                {
                    "task": task,
                    "alpha": alpha,
                    "calibration_runs": len(values),
                    "rank": rank,
                    "threshold_available": int(math.isfinite(threshold)),
                    "threshold_utility": threshold if math.isfinite(threshold) else "",
                }
            )

    policy_names = ["artifact_only", "all_escalate", "full_external"] + [
        f"conformal_a{int(alpha * 100):02d}" for alpha in ALPHAS
    ]
    per_set = []
    prospective_accepts: dict[str, int] = collections.Counter()

    for parent, members in sorted(by_parent.items()):
        children = sorted(row["card_id"] for row in members)
        tasks = {row["competition"] for row in members}
        runs = {card_run[card_id] for card_id in children}
        strata = {row["stratum"] for row in members}
        if len(tasks) != 1 or len(runs) != 1 or len(strata) != 1:
            raise RuntimeError(f"mixed fidelity set: {parent}")
        task, run_id, stratum = next(iter(tasks)), next(iter(runs)), next(iter(strata))
        if run_id not in hold_runs:
            raise RuntimeError(f"test set outside hold: {parent}")
        truth = {
            row["card_id"]: utility(float(row["graded"]), task, lower) for row in members
        }
        artifact = {
            card_id: utility(float(cap_results[card_id]["sub_score"]), task, lower)
            for card_id in children
            if finite(cap_results[card_id].get("sub_score"))
        }
        silent = set(children) - set(artifact)
        low_wall = sum(float(cap_results[card_id]["wall_s"]) for card_id in children)
        full_baseline = sum(runtime[card_id] for card_id in children)

        # Freeze all conformal decisions before consulting ``truth`` below.
        decisions = {}
        for alpha in ALPHAS:
            policy = f"conformal_a{int(alpha * 100):02d}"
            threshold = thresholds[alpha][task]
            # An "early accept" is actionable only when there is at least one silent
            # candidate whose full evaluation is actually skipped.
            decisions[policy] = (
                bool(artifact) and bool(silent) and max(artifact.values()) >= threshold
            )
            prospective_accepts[policy] += int(decisions[policy])

        for policy in policy_names:
            if policy == "full_external":
                signals = dict(truth)
                escalated = set(children)
                restart_cost = full_baseline
                continuation_cost = full_baseline
                accepted_early = False
            elif policy == "artifact_only":
                signals = dict(artifact)
                escalated = set()
                restart_cost = low_wall
                continuation_cost = low_wall
                accepted_early = bool(artifact)
            else:
                accepted_early = policy.startswith("conformal_") and decisions[policy]
                escalated = set() if accepted_early else set(silent)
                signals = dict(artifact)
                signals.update({card_id: truth[card_id] for card_id in escalated})
                restart_cost = low_wall + sum(runtime[card_id] for card_id in escalated)
                continuation_cost = low_wall + sum(
                    max(0.0, runtime[card_id] - args.cap) for card_id in escalated
                )

            if signals:
                chosen = tied_best(signals)
                deployed_utility = statistics.mean(signals[card_id] for card_id in chosen)
                deployed_available = 1
                endpoint_identity = expected_endpoint_identity(chosen, truth)
            else:
                chosen = children
                deployed_utility = float("nan")
                deployed_available = 0
                endpoint_identity = expected_endpoint_identity(chosen, truth)
            full_best = max(truth.values())
            deployed_delta = deployed_utility - full_best if signals else float("nan")
            per_set.append(
                {
                    "parent": parent,
                    "run_id": run_id,
                    "task": task,
                    "stratum": stratum,
                    "policy": policy,
                    "n_children": len(children),
                    "n_artifact": len(artifact),
                    "n_silent": len(silent),
                    "accepted_early": int(accepted_early),
                    "n_escalated": len(escalated),
                    "endpoint_identity": endpoint_identity,
                    "deployed_available": deployed_available,
                    "deployed_utility": deployed_utility,
                    "full_final_best_utility": full_best,
                    "deployed_delta_to_full_final": deployed_delta,
                    "deployed_matches_or_beats_full": float(
                        bool(signals) and deployed_delta >= -1e-12
                    ),
                    "deployed_strictly_beats_full": float(
                        bool(signals) and deployed_delta > 1e-12
                    ),
                    "deployed_strictly_loses_full": float(
                        not bool(signals) or deployed_delta < -1e-12
                    ),
                    "low_wall_s": low_wall,
                    "all_full_runtime_s": full_baseline,
                    "restart_cost_s": restart_cost,
                    "continuation_cost_s": continuation_cost,
                }
            )

    preflight = {
        "1_knob_from_artifact": "alpha and decisions recorded per set; no runtime config changed",
        "2_cheap_path_test": "CPU-only full frozen-population test",
        "3_test_dedup": {
            "pair_overlap": len(pair_overlap),
            "node_overlap": len(node_overlap),
            "raw_code_hash_overlap": len(code_hash_overlap),
        },
        "4_distribution": {
            "test_sets": len(by_parent),
            "test_runs": len(manifest_runs),
            "test_tasks": len(manifest_tasks),
            "calibration_runs": len({run_id for _task, run_id in run_maxima}),
        },
        "5_eval_balance": "task and stratum breakdown emitted; no learned predictor",
        "6_model_saved": "not applicable: no fitted model",
        "7_leakage_checks": "pair/node/raw-code-hash all zero",
        "8_rng": f"only bootstrap RNG; fixed seed={args.seed}",
        "9_secret_surface": "no environment or run artifact ingested",
        "10_wall_clock": "CPU-only; no Slurm allocation",
        "11_power": "100 sets / 52 run clusters; preregistered 5pp noninferiority bound",
        "12_rc_capture": "single fail-closed process; shell wrapper must preserve rc",
        "13_frozen_draws": {
            "split_seed": split["seed"],
            "prior_hold_preserved": len(set(split.get("prior_hold", [])) & hold_runs),
            "prior_hold_total": len(split.get("prior_hold", [])),
        },
    }

    summary: dict[str, object] = {
        "provenance": {
            "inputs": {
                name: {"path": str(path), "sha256": sha256(path)}
                for name, path in paths.items()
            },
            "script": {"path": __file__, "sha256": sha256(Path(__file__))},
            "git_commit": subprocess.run(
                ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
            ).stdout.strip(),
            "python": platform.python_version(),
            "command": (
                f"python {__file__} --cap {args.cap} --bootstrap {args.bootstrap} "
                f"--seed {args.seed} --out-dir {args.out_dir}"
            ),
        },
        "design": {
            "alphas": list(ALPHAS),
            "primary_alpha": 0.10,
            "calibration_unit": "non-hold physical-run maximum within task",
            "decision_inputs": ["task", "cap-time pristine artifact score", "calibration threshold"],
            "test_outcome_used_for_decision": False,
            "cluster": "physical run",
            "bootstrap_draws": args.bootstrap,
            "seed": args.seed,
        },
        "counts": {
            "corpus_cards": corpus_cards,
            "finite_cards": finite_cards,
            "nonfinite_cards": nonfinite_cards,
            "all_runs": len(all_runs),
            "hold_runs": len(hold_runs),
            "sets": len(by_parent),
            "test_runs": len(manifest_runs),
            "children": len(manifest_ids),
            "test_tasks": len(manifest_tasks),
        },
        "preflight": preflight,
        "prospective_early_accepts": dict(sorted(prospective_accepts.items())),
        "policies": {},
        "paired_vs_all_escalate": {},
        "by_task": {},
    }

    all_rows = [row for row in per_set if row["policy"] == "all_escalate"]
    all_index = {row["parent"]: row for row in all_rows}
    for policy in policy_names:
        rows = [row for row in per_set if row["policy"] == policy]
        endpoint_ci = run_bootstrap(rows, "endpoint_identity", args.bootstrap, args.seed)
        match_ci = run_bootstrap(
            rows, "deployed_matches_or_beats_full", args.bootstrap, args.seed
        )
        available = [row for row in rows if row["deployed_available"]]
        delta_ci = (
            run_bootstrap(available, "deployed_delta_to_full_final", args.bootstrap, args.seed)
            if available
            else [None, None]
        )
        summary["policies"][policy] = {
            "endpoint_identity": statistics.mean(row["endpoint_identity"] for row in rows),
            "endpoint_identity_run_cluster_ci95": list(endpoint_ci),
            "deployed_matches_or_beats_full": statistics.mean(
                row["deployed_matches_or_beats_full"] for row in rows
            ),
            "deployed_matches_or_beats_full_run_cluster_ci95": list(match_ci),
            "mean_deployed_delta_to_full_final_available": (
                statistics.mean(row["deployed_delta_to_full_final"] for row in available)
                if available
                else None
            ),
            "deployed_delta_run_cluster_ci95": list(delta_ci),
            "early_accepts": sum(row["accepted_early"] for row in rows),
            "full_evaluations": sum(row["n_escalated"] for row in rows),
            "restart_ratio_to_all_full": sum(row["restart_cost_s"] for row in rows)
            / sum(row["all_full_runtime_s"] for row in rows),
            "continuation_ratio_to_all_full": sum(
                row["continuation_cost_s"] for row in rows
            )
            / sum(row["all_full_runtime_s"] for row in rows),
        }

        paired = []
        for row in rows:
            baseline = all_index[row["parent"]]
            paired.append(
                {
                    "run_id": row["run_id"],
                    "match_delta": row["deployed_matches_or_beats_full"]
                    - baseline["deployed_matches_or_beats_full"],
                    "score_delta": (
                        row["deployed_delta_to_full_final"]
                        - baseline["deployed_delta_to_full_final"]
                        if row["deployed_available"] and baseline["deployed_available"]
                        else 0.0
                    ),
                }
            )
        summary["paired_vs_all_escalate"][policy] = {
            "deployed_match_delta": statistics.mean(row["match_delta"] for row in paired),
            "deployed_match_delta_run_cluster_ci95": list(
                run_bootstrap(paired, "match_delta", args.bootstrap, args.seed)
            ),
            "deployed_score_delta": statistics.mean(row["score_delta"] for row in paired),
            "deployed_score_delta_run_cluster_ci95": list(
                run_bootstrap(paired, "score_delta", args.bootstrap, args.seed)
            ),
        }

    for task in sorted(manifest_tasks):
        task_rows = [
            row for row in per_set if row["task"] == task and row["policy"] == "conformal_a10"
        ]
        summary["by_task"][task] = {
            "sets": len(task_rows),
            "runs": len({row["run_id"] for row in task_rows}),
            "calibration_runs": len(maxima_by_task.get(task, [])),
            "early_accepts_a10": sum(row["accepted_early"] for row in task_rows),
            "deployed_matches_or_beats_full_a10": statistics.mean(
                row["deployed_matches_or_beats_full"] for row in task_rows
            ),
        }

    # Independent reproduction anchors from the corrected deployment audit.
    all_summary = summary["policies"]["all_escalate"]
    if not math.isclose(all_summary["endpoint_identity"], 0.96):
        raise RuntimeError("all-escalate endpoint failed to reproduce 0.9600")
    if not math.isclose(all_summary["deployed_matches_or_beats_full"], 0.92):
        raise RuntimeError("all-escalate deployment failed to reproduce 0.9200")
    if not math.isclose(all_summary["restart_ratio_to_all_full"], 0.9849782859597027):
        raise RuntimeError("restart cost failed to reproduce")
    if not math.isclose(all_summary["continuation_ratio_to_all_full"], 0.9312411456030097):
        raise RuntimeError("continuation cost failed to reproduce")
    if summary["policies"]["full_external"]["deployed_matches_or_beats_full"] != 1.0:
        raise RuntimeError("full-external positive control failed")

    primary = summary["policies"]["conformal_a10"]
    primary_delta = summary["paired_vs_all_escalate"]["conformal_a10"]
    lower_bound = primary_delta["deployed_match_delta_run_cluster_ci95"][0]
    if lower_bound >= -0.05 and primary["restart_ratio_to_all_full"] <= 0.90:
        verdict = "GO"
    elif (
        primary_delta["deployed_match_delta"] >= 0.0
        and primary["restart_ratio_to_all_full"] < 0.95
    ):
        verdict = "BORDERLINE"
    else:
        verdict = "KILL"
    summary["preregistered_verdict"] = {
        "verdict": verdict,
        "primary_policy": "conformal_a10",
        "noninferiority_lower_bound": lower_bound,
        "restart_ratio_to_all_full": primary["restart_ratio_to_all_full"],
    }

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "per_set.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(per_set[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(per_set)
    with (out_dir / "task_calibration.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(calibration_rows[0]), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(calibration_rows)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )

    print(
        f"PREFLIGHT cards={corpus_cards} finite={finite_cards} runs={len(all_runs)} "
        f"hold={len(hold_runs)} test_sets={len(by_parent)} test_runs={len(manifest_runs)} "
        f"tasks={len(manifest_tasks)} leakage=0/0/0"
    )
    print("policy          accepts deployed>=full match-delta[CI] restart continuation")
    for policy in policy_names:
        result = summary["policies"][policy]
        paired = summary["paired_vs_all_escalate"][policy]
        lo, hi = paired["deployed_match_delta_run_cluster_ci95"]
        print(
            f"{policy:16s} {result['early_accepts']:3d} "
            f"{result['deployed_matches_or_beats_full']:.4f} "
            f"{paired['deployed_match_delta']:+.4f}[{lo:+.4f},{hi:+.4f}] "
            f"{result['restart_ratio_to_all_full']:.4f} "
            f"{result['continuation_ratio_to_all_full']:.4f}"
        )
    print(
        "VERDICT "
        f"{verdict} lower={lower_bound:+.6f} "
        f"restart={primary['restart_ratio_to_all_full']:.6f}"
    )
    print(f"WROTE {out_dir}")


if __name__ == "__main__":
    main()
