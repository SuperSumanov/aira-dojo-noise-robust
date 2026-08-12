"""Offline Pareto test: let zero-cost critics gate expensive silent candidates.

At 120 seconds, some candidates have a schema-valid artifact and a pristine external
score; the rest are silent.  Escalating every silent candidate preserves quality but the
exact historical runtimes show almost no saving.  This script tests a fixed, tuning-free
alternative on the same frozen 100 sibling sets:

1. use the best partial artifact as the incumbent;
2. prune a silent candidate only when a pre-execution pairwise predictor says the
   incumbent is better;
3. externally evaluate every remaining silent candidate, then select on the common
   external-score scale.

The consistency gate is conservative: it prunes only when code_len, static_lr and
tfidf_lr unanimously agree.  A majority gate, tfidf-only gate, random negative control,
and truth-oracle positive control are reported without tuning.  If a set has no artifact,
all silent candidates are evaluated, so the probe isolates gating rather than inventing a
fallback.  Costs use each sampled candidate's exact historical runtime.

No model is fitted here. ``perpair_decision.json`` contains out-of-sample predictions
from predictors fitted only on the run-clean training side.
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
import zlib
from pathlib import Path


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default="phase1/fidelity_manifest.jsonl")
    parser.add_argument("--results", default="phase1/fidelity_results.jsonl")
    parser.add_argument("--runtime-map", default="phase1/fidelity_runtime_v9.jsonl")
    parser.add_argument("--run-map", default="phase1/card_run_map.json")
    parser.add_argument("--orientation", default="phase1/task_orientation.json")
    parser.add_argument("--frozen-pairs", default="phase1/v10_decision/decision_frozen_v10_b0.jsonl")
    parser.add_argument("--predictions", default="phase1/perpair_decision.json")
    parser.add_argument("--cap", type=int, default=120)
    parser.add_argument("--bootstrap", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--out-dir", default="phase1/critic_gated_escalation_v9")
    return parser.parse_args()


def jsonl(path: Path) -> list[dict]:
    output = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                output.append(json.loads(line))
            except json.JSONDecodeError as error:
                raise ValueError(f"invalid JSON: {path}:{line_number}") from error
    return output


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def finite(value: object) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def utility(score: float, task: str, lower: dict[str, bool]) -> float:
    return -score if lower.get(task, False) else score


def tied_best(scores: dict[str, float], task: str, lower: dict[str, bool]) -> list[str]:
    best = max(utility(score, task, lower) for score in scores.values())
    return sorted(
        card_id
        for card_id, score in scores.items()
        if math.isclose(utility(score, task, lower), best, abs_tol=1e-12)
    )


def expected_top1(selected: list[str], truth: dict[str, float], task: str,
                  lower: dict[str, bool]) -> tuple[float, float]:
    best = max(utility(score, task, lower) for score in truth.values())
    true_best = {
        card_id for card_id, score in truth.items()
        if math.isclose(utility(score, task, lower), best, abs_tol=1e-12)
    }
    hit = len(set(selected) & true_best) / len(selected)
    picked_utility = statistics.mean(utility(truth[card_id], task, lower)
                                     for card_id in selected)
    return hit, best - picked_utility


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, int(fraction * len(ordered))))]


def run_bootstrap(rows: list[dict], field: str, draws: int, seed: int) -> tuple[float, float]:
    groups: dict[str, list[float]] = collections.defaultdict(list)
    for row in rows:
        groups[row["run_id"]].append(float(row[field]))
    keys = sorted(groups)
    rng = random.Random(seed)
    estimates = []
    for _ in range(draws):
        values = [value for key in (rng.choice(keys) for _ in keys) for value in groups[key]]
        estimates.append(statistics.mean(values))
    return percentile(estimates, 0.025), percentile(estimates, 0.975)


def main() -> None:
    args = arguments()
    paths = {
        "manifest": Path(args.manifest),
        "results": Path(args.results),
        "runtime_map": Path(args.runtime_map),
        "run_map": Path(args.run_map),
        "orientation": Path(args.orientation),
        "frozen_pairs": Path(args.frozen_pairs),
        "predictions": Path(args.predictions),
    }
    manifest = jsonl(paths["manifest"])
    results = jsonl(paths["results"])
    runtime_rows = jsonl(paths["runtime_map"])
    run_of = json.loads(paths["run_map"].read_text(encoding="utf-8"))
    lower = json.loads(paths["orientation"].read_text(encoding="utf-8"))
    pair_rows = jsonl(paths["frozen_pairs"])
    predictions = json.loads(paths["predictions"].read_text(encoding="utf-8"))

    required_predictors = ("random", "code_len", "static_lr", "tfidf_lr")
    missing_predictors = set(required_predictors) - predictions.keys()
    if missing_predictors:
        raise RuntimeError(f"missing predictors: {sorted(missing_predictors)}")

    truth_pair: dict[frozenset[str], tuple[str, str]] = {}
    for row in pair_rows:
        key = frozenset((row["better"], row["worse"]))
        if key in truth_pair:
            raise RuntimeError("duplicate/reversed frozen pair")
        truth_pair[key] = (row["better"], row["worse"])

    def preference(predictor: str, left: str, right: str) -> str | None:
        pair = truth_pair.get(frozenset((left, right)))
        if pair is None:
            return None
        better, worse = pair
        value = predictions[predictor].get(f"{better}|{worse}")
        if value is None:
            return None
        if value not in (0, 1):
            raise RuntimeError(f"non-binary prediction: {predictor}, {better}, {worse}")
        return better if value == 1 else worse

    runtime = {row["card_id"]: float(row["runtime_s"]) for row in runtime_rows}
    cap_results = {row["card_id"]: row for row in results if int(row["cap"]) == args.cap}
    by_parent: dict[str, list[dict]] = collections.defaultdict(list)
    for row in manifest:
        by_parent[row["parent"]].append(row)
    manifest_ids = {row["card_id"] for row in manifest}
    if set(runtime) != manifest_ids or set(cap_results) != manifest_ids:
        raise RuntimeError("runtime/cap result coverage differs from frozen manifest")

    policy_names = (
        "artifact_only",
        "all_escalate",
        "random_gate",
        "tfidf_gate",
        "majority3_gate",
        "unanimous3_gate",
        "top1_random",
        "top1_tfidf",
        "top1_majority3",
        "top1_stdout",
        "top1_progress",
        "top1_stdout_tfidf",
        "top1_oracle",
        "top2_random",
        "top2_tfidf",
        "top2_oracle",
        "oracle_gate",
        "full_external",
    )
    gate_predictors = ("code_len", "static_lr", "tfidf_lr")
    per_set: list[dict] = []

    for parent, members in sorted(by_parent.items()):
        children = sorted(row["card_id"] for row in members)
        tasks = {row["competition"] for row in members}
        runs = {run_of.get(card_id) for card_id in children}
        strata = {row["stratum"] for row in members}
        if len(tasks) != 1 or len(runs) != 1 or len(strata) != 1 or None in runs:
            raise RuntimeError(f"mixed parent set: {parent}")
        task, run_id, stratum = next(iter(tasks)), next(iter(runs)), next(iter(strata))
        truth = {row["card_id"]: float(row["graded"]) for row in members}
        artifact = {
            card_id: float(cap_results[card_id]["sub_score"])
            for card_id in children if finite(cap_results[card_id].get("sub_score"))
        }
        silent = sorted(set(children) - artifact.keys())
        low_wall = sum(float(cap_results[card_id]["wall_s"]) for card_id in children)
        full_baseline = sum(runtime[card_id] for card_id in children)
        incumbent = tied_best(artifact, task, lower)[0] if artifact else None

        for policy in policy_names:
            if policy == "full_external":
                selected_silent = set(children)
                signals = dict(truth)
                restart_cost = full_baseline
                continuation_cost = full_baseline
                pruned = set()
            elif policy == "artifact_only":
                selected_silent = set()
                signals = dict(artifact)
                restart_cost = low_wall
                continuation_cost = low_wall
                pruned = set(silent)
            else:
                if policy.startswith(("top1_", "top2_")):
                    top_k = 1 if policy.startswith("top1_") else 2
                    if not silent:
                        selected_silent = set()
                    elif policy.endswith("_oracle"):
                        ordered = sorted(
                            silent,
                            key=lambda candidate: (
                                -utility(truth[candidate], task, lower),
                                zlib.crc32(f"{args.seed}|{parent}|{candidate}".encode()),
                            ),
                        )
                        selected_silent = set(ordered[:top_k])
                    elif policy in ("top1_stdout", "top1_stdout_tfidf"):
                        stdout_scores = {
                            candidate: float(cap_results[candidate]["stdout_val"])
                            for candidate in silent
                            if finite(cap_results[candidate].get("stdout_val"))
                        }
                        if stdout_scores:
                            tied = tied_best(stdout_scores, task, lower)
                            selected_silent = {min(tied, key=lambda candidate: zlib.crc32(
                                f"{args.seed}|{parent}|{candidate}".encode()))}
                        elif policy == "top1_stdout":
                            selected_silent = {min(silent, key=lambda candidate: zlib.crc32(
                                f"{args.seed}|{parent}|{candidate}".encode()))}
                        else:
                            wins = collections.Counter({candidate: 0.0 for candidate in silent})
                            for left_index, left in enumerate(silent):
                                for right in silent[left_index + 1:]:
                                    picked = preference("tfidf_lr", left, right)
                                    if picked is None:
                                        wins[left] += 0.5
                                        wins[right] += 0.5
                                    else:
                                        wins[picked] += 1.0
                            best_wins = max(wins.values())
                            tied = [candidate for candidate in silent
                                    if math.isclose(wins[candidate], best_wins)]
                            selected_silent = {min(tied, key=lambda candidate: zlib.crc32(
                                f"{args.seed}|{parent}|{candidate}".encode()))}
                    elif policy == "top1_progress":
                        progress = {
                            candidate: int(cap_results[candidate].get("stdout_bytes") or 0)
                            + int(cap_results[candidate].get("stderr_bytes") or 0)
                            for candidate in silent
                        }
                        best_progress = max(progress.values())
                        tied = [candidate for candidate in silent
                                if progress[candidate] == best_progress]
                        selected_silent = {min(tied, key=lambda candidate: zlib.crc32(
                            f"{args.seed}|{parent}|{candidate}".encode()))}
                    else:
                        wins = collections.Counter({candidate: 0.0 for candidate in silent})
                        for left_index, left in enumerate(silent):
                            for right in silent[left_index + 1:]:
                                if policy == "top1_majority3":
                                    votes = [preference(name, left, right)
                                             for name in gate_predictors]
                                    left_votes = sum(vote == left for vote in votes)
                                    right_votes = sum(vote == right for vote in votes)
                                    picked = left if left_votes > right_votes else (
                                        right if right_votes > left_votes else None
                                    )
                                else:
                                    predictor = ("random" if policy.endswith("_random")
                                                 else "tfidf_lr")
                                    picked = preference(predictor, left, right)
                                if picked is None:
                                    wins[left] += 0.5
                                    wins[right] += 0.5
                                else:
                                    wins[picked] += 1.0
                        ordered = sorted(
                            silent,
                            key=lambda candidate: (
                                -wins[candidate],
                                zlib.crc32(f"{args.seed}|{parent}|{candidate}".encode()),
                            ),
                        )
                        selected_silent = set(ordered[:top_k])
                elif policy == "all_escalate" or incumbent is None:
                    selected_silent = set(silent)
                else:
                    selected_silent = set()
                    for candidate in silent:
                        if policy == "oracle_gate":
                            prune = utility(truth[incumbent], task, lower) >= utility(
                                truth[candidate], task, lower
                            )
                        elif policy == "random_gate":
                            picked = preference("random", incumbent, candidate)
                            prune = picked == incumbent
                        elif policy == "tfidf_gate":
                            picked = preference("tfidf_lr", incumbent, candidate)
                            prune = picked == incumbent
                        else:
                            votes = [preference(name, incumbent, candidate)
                                     for name in gate_predictors]
                            incumbent_votes = sum(vote == incumbent for vote in votes)
                            complete = all(vote is not None for vote in votes)
                            if policy == "majority3_gate":
                                prune = complete and incumbent_votes >= 2
                            elif policy == "unanimous3_gate":
                                prune = complete and incumbent_votes == 3
                            else:
                                raise AssertionError(policy)
                        if not prune:
                            selected_silent.add(candidate)
                pruned = set(silent) - selected_silent
                signals = dict(artifact)
                signals.update({card_id: truth[card_id] for card_id in selected_silent})
                restart_cost = low_wall + sum(runtime[card_id] for card_id in selected_silent)
                continuation_cost = low_wall + sum(
                    max(0.0, runtime[card_id] - args.cap) for card_id in selected_silent
                )

            if not signals:
                chosen = children  # explicit uniform-random fallback
            else:
                chosen = tied_best(signals, task, lower)
            top1, regret = expected_top1(chosen, truth, task, lower)
            full_final_best = max(utility(value, task, lower) for value in truth.values())
            if signals:
                deployed_utility = statistics.mean(
                    utility(signals[card_id], task, lower) for card_id in chosen
                )
                deployed_available = 1
                deployed_delta = deployed_utility - full_final_best
                deployed_matches = float(deployed_delta >= -1e-12)
                deployed_strictly_beats = float(deployed_delta > 1e-12)
                deployed_strictly_loses = float(deployed_delta < -1e-12)
            else:
                # No artifact and no escalation means that the policy has no deployable output.
                deployed_utility = float("nan")
                deployed_available = 0
                deployed_delta = float("nan")
                deployed_matches = 0.0
                deployed_strictly_beats = 0.0
                deployed_strictly_loses = 1.0
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
                    "n_escalated": len(selected_silent),
                    "n_pruned": len(pruned),
                    # This is candidate-identity accuracy: the selected card's eventual
                    # full endpoint is best.  It is not the score of the output available
                    # when an artifact-producing run is stopped at ``cap``.
                    "top1_expected": top1,
                    "raw_regret": regret,
                    "deployed_available": deployed_available,
                    "deployed_utility": deployed_utility,
                    "full_final_best_utility": full_final_best,
                    "deployed_delta_to_full_final": deployed_delta,
                    "deployed_matches_or_beats_full": deployed_matches,
                    "deployed_strictly_beats_full": deployed_strictly_beats,
                    "deployed_strictly_loses_full": deployed_strictly_loses,
                    "low_wall_s": low_wall,
                    "all_full_runtime_s": full_baseline,
                    "restart_cost_s": restart_cost,
                    "continuation_cost_s": continuation_cost,
                }
            )

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
            "cap_s": args.cap,
            "bootstrap_draws": args.bootstrap,
            "seed": args.seed,
            "cluster": "physical run",
            "fixed_consensus_predictors": list(gate_predictors),
            "tuning": "none",
            "no_artifact_fallback": "escalate all silent candidates",
            "top1_semantics": (
                "selected card identity's eventual full endpoint is best; this is a "
                "routing diagnostic, not the actually deployed partial/full score"
            ),
            "deployment_semantics": (
                "artifact candidates contribute their cap-time sub_score; escalated "
                "candidates contribute their final external grade"
            ),
        },
        "counts": {
            "sets": len(by_parent),
            "runs": len({row["run_id"] for row in per_set}),
            "children": len(manifest_ids),
            "tasks": len({row["task"] for row in per_set}),
        },
        "policies": {},
        "paired_vs_all_escalate": {},
        "paired_policy_comparisons": {},
    }

    all_index = {
        row["parent"]: row for row in per_set if row["policy"] == "all_escalate"
    }
    for policy in policy_names:
        rows = [row for row in per_set if row["policy"] == policy]
        top1 = statistics.mean(row["top1_expected"] for row in rows)
        top_lo, top_hi = run_bootstrap(rows, "top1_expected", args.bootstrap, args.seed)
        restart = sum(row["restart_cost_s"] for row in rows) / sum(
            row["all_full_runtime_s"] for row in rows
        )
        continuation = sum(row["continuation_cost_s"] for row in rows) / sum(
            row["all_full_runtime_s"] for row in rows
        )
        summary["policies"][policy] = {
            "top1": top1,
            "top1_semantics": "endpoint_identity",
            "top1_run_cluster_ci95": [top_lo, top_hi],
            "mean_raw_regret": statistics.mean(row["raw_regret"] for row in rows),
            "full_evaluations": sum(row["n_escalated"] for row in rows),
            "pruned_silent": sum(row["n_pruned"] for row in rows),
            "restart_ratio_to_all_full": restart,
            "continuation_ratio_to_all_full": continuation,
        }
        available_rows = [row for row in rows if row["deployed_available"]]
        match_lo, match_hi = run_bootstrap(
            rows, "deployed_matches_or_beats_full", args.bootstrap, args.seed
        )
        summary["policies"][policy].update({
            "deployed_available_sets": len(available_rows),
            "deployed_matches_or_beats_full": statistics.mean(
                row["deployed_matches_or_beats_full"] for row in rows
            ),
            "deployed_matches_or_beats_full_run_cluster_ci95": [match_lo, match_hi],
            "deployed_strictly_beats_full": statistics.mean(
                row["deployed_strictly_beats_full"] for row in rows
            ),
            "deployed_strictly_loses_full": statistics.mean(
                row["deployed_strictly_loses_full"] for row in rows
            ),
            "mean_deployed_delta_to_full_final_available": (
                statistics.mean(row["deployed_delta_to_full_final"] for row in available_rows)
                if available_rows else None
            ),
        })
        difference_rows = []
        for row in rows:
            difference_rows.append(
                {
                    "run_id": row["run_id"],
                    "delta": row["top1_expected"] - all_index[row["parent"]]["top1_expected"],
                }
            )
        delta = statistics.mean(row["delta"] for row in difference_rows)
        delta_lo, delta_hi = run_bootstrap(
            difference_rows, "delta", args.bootstrap, args.seed
        )
        deployed_difference_rows = []
        for row in rows:
            deployed_difference_rows.append({
                "run_id": row["run_id"],
                "delta": row["deployed_matches_or_beats_full"]
                - all_index[row["parent"]]["deployed_matches_or_beats_full"],
            })
        deployed_delta = statistics.mean(
            row["delta"] for row in deployed_difference_rows
        )
        deployed_lo, deployed_hi = run_bootstrap(
            deployed_difference_rows, "delta", args.bootstrap, args.seed
        )
        summary["paired_vs_all_escalate"][policy] = {
            "delta_top1": delta,
            "run_cluster_ci95": [delta_lo, delta_hi],
            "delta_deployed_matches_or_beats_full": deployed_delta,
            "deployed_run_cluster_ci95": [deployed_lo, deployed_hi],
        }

    policy_index = {
        (row["policy"], row["parent"]): row for row in per_set
    }
    for left, right in (
        ("top1_tfidf", "top1_random"),
        ("top1_stdout_tfidf", "top1_random"),
        ("top2_tfidf", "top2_random"),
    ):
        difference_rows = []
        for parent in sorted(by_parent):
            left_row = policy_index[(left, parent)]
            right_row = policy_index[(right, parent)]
            difference_rows.append({
                "run_id": left_row["run_id"],
                "delta": left_row["top1_expected"] - right_row["top1_expected"],
            })
        delta = statistics.mean(row["delta"] for row in difference_rows)
        delta_lo, delta_hi = run_bootstrap(
            difference_rows, "delta", args.bootstrap, args.seed
        )
        deployed_difference_rows = []
        for parent in sorted(by_parent):
            left_row = policy_index[(left, parent)]
            right_row = policy_index[(right, parent)]
            deployed_difference_rows.append({
                "run_id": left_row["run_id"],
                "delta": left_row["deployed_matches_or_beats_full"]
                - right_row["deployed_matches_or_beats_full"],
            })
        deployed_delta = statistics.mean(
            row["delta"] for row in deployed_difference_rows
        )
        deployed_lo, deployed_hi = run_bootstrap(
            deployed_difference_rows, "delta", args.bootstrap, args.seed
        )
        summary["paired_policy_comparisons"][f"{left}_minus_{right}"] = {
            "delta_top1": delta,
            "run_cluster_ci95": [delta_lo, delta_hi],
            "delta_deployed_matches_or_beats_full": deployed_delta,
            "deployed_run_cluster_ci95": [deployed_lo, deployed_hi],
        }

    # Independent reproduction checks for the two already-published endpoints.
    if not math.isclose(summary["policies"]["artifact_only"]["top1"], 0.5783333333333334):
        raise RuntimeError("artifact-only endpoint did not reproduce 0.578333")
    if not math.isclose(summary["policies"]["all_escalate"]["top1"], 0.96):
        raise RuntimeError("all-escalate endpoint did not reproduce 0.9600")
    if not math.isclose(
        summary["policies"]["all_escalate"]["restart_ratio_to_all_full"],
        0.9849782859597027,
    ):
        raise RuntimeError("exact all-escalate cost did not reproduce 0.984978")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "per_set.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(per_set[0]), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(per_set)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    print(
        f"VERIFIED sets={summary['counts']['sets']} runs={summary['counts']['runs']} "
        f"children={summary['counts']['children']} tasks={summary['counts']['tasks']}"
    )
    print(
        "policy              endpoint-top1   deployed>=full   full-evals "
        "pruned restart/full continue/full"
    )
    for policy in policy_names:
        value = summary["policies"][policy]
        lo, hi = value["top1_run_cluster_ci95"]
        print(
            f"{policy:20s} {value['top1']:.4f} [{lo:.4f},{hi:.4f}] "
            f"{value['deployed_matches_or_beats_full']:.4f} "
            f"{value['full_evaluations']:10d} {value['pruned_silent']:6d} "
            f"{value['restart_ratio_to_all_full']:.4f} "
            f"{value['continuation_ratio_to_all_full']:.4f}"
        )
    print(f"WROTE {out_dir}")


if __name__ == "__main__":
    main()
