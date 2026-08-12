"""Run-OOS probe of whether 120-second traces can rank silent candidates.

This script implements the fixed protocol in
``实验记录/2026-08-13/早期trace排序器_预注册.md``.  It never reads final
runtime or full self-report as model features.  Final external grades are labels only.
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

import numpy as np
import scipy.sparse as sp
import sklearn
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler


KEYWORD_GROUPS = (
    ("available", "download", "loading", "model"),
    ("prepar", "feature", "window", "token", "data"),
    ("train", "fit", "fold", "epoch", "iteration"),
    ("predict", "infer", "validation", "score"),
    ("submission", "saved", "wrote", "complete", "done"),
    ("error", "traceback", "failed", "exception", "oom"),
)
STATIC_PREDICTORS = ("code_len", "static_lr", "tfidf_lr")


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default="phase1/fidelity_manifest.jsonl")
    parser.add_argument("--results", default="phase1/fidelity_results.jsonl")
    parser.add_argument("--runtime-map", default="phase1/fidelity_runtime_v9.jsonl")
    parser.add_argument("--run-map", default="phase1/card_run_map.json")
    parser.add_argument("--orientation", default="phase1/task_orientation.json")
    parser.add_argument(
        "--frozen-pairs", default="phase1/v10_decision/decision_frozen_v10_b0.jsonl"
    )
    parser.add_argument("--predictions", default="phase1/perpair_decision.json")
    parser.add_argument("--cap", type=int, default=120)
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--bootstrap", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--out-dir", default="phase1/trace_rank_cv_v9")
    return parser.parse_args()


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as error:
                raise ValueError(f"invalid JSON: {path}:{line_number}") from error
    return rows


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def finite(value: object) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def utility(value: float, task: str, lower: dict[str, bool]) -> float:
    return -value if lower.get(task, False) else value


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, int(fraction * len(ordered))))]


def cluster_bootstrap(
    rows: list[dict], field: str, draws: int, seed: int
) -> tuple[float, float]:
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


def tied_best(
    scores: dict[str, float], task: str, lower: dict[str, bool]
) -> list[str]:
    best = max(utility(value, task, lower) for value in scores.values())
    return sorted(
        card_id
        for card_id, value in scores.items()
        if math.isclose(utility(value, task, lower), best, abs_tol=1e-12)
    )


def expected_outcome(
    selected: list[str], truth: dict[str, float], task: str, lower: dict[str, bool]
) -> tuple[float, float]:
    true_best_value = max(utility(value, task, lower) for value in truth.values())
    true_best = {
        card_id
        for card_id, value in truth.items()
        if math.isclose(utility(value, task, lower), true_best_value, abs_tol=1e-12)
    }
    hit = len(set(selected) & true_best) / len(selected)
    selected_value = statistics.mean(utility(truth[c], task, lower) for c in selected)
    return hit, true_best_value - selected_value


def deterministic_argmax(scores: dict[str, float], seed: int, parent: str) -> str:
    best = max(scores.values())
    tied = [card_id for card_id, value in scores.items() if math.isclose(value, best)]
    return min(tied, key=lambda card_id: zlib.crc32(f"{seed}|{parent}|{card_id}".encode()))


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
    manifest = read_jsonl(paths["manifest"])
    results = read_jsonl(paths["results"])
    runtimes = {row["card_id"]: float(row["runtime_s"]) for row in read_jsonl(paths["runtime_map"])}
    run_of = json.loads(paths["run_map"].read_text(encoding="utf-8"))
    lower = json.loads(paths["orientation"].read_text(encoding="utf-8"))
    frozen_pairs = read_jsonl(paths["frozen_pairs"])
    predictions = json.loads(paths["predictions"].read_text(encoding="utf-8"))

    for predictor in STATIC_PREDICTORS:
        if predictor not in predictions:
            raise RuntimeError(f"missing frozen predictor: {predictor}")

    result_at_cap = {row["card_id"]: row for row in results if int(row["cap"]) == args.cap}
    by_parent: dict[str, list[dict]] = collections.defaultdict(list)
    for row in manifest:
        by_parent[row["parent"]].append(row)
    all_ids = {row["card_id"] for row in manifest}
    if set(result_at_cap) != all_ids or set(runtimes) != all_ids:
        raise RuntimeError("manifest/results/runtime coverage mismatch")

    truth_pair: dict[frozenset[str], tuple[str, str]] = {}
    for row in frozen_pairs:
        key = frozenset((row["better"], row["worse"]))
        if key in truth_pair:
            raise RuntimeError("duplicate/reversed frozen pair")
        truth_pair[key] = row["better"], row["worse"]

    def frozen_preference(predictor: str, left: str, right: str) -> str | None:
        pair = truth_pair.get(frozenset((left, right)))
        if pair is None:
            return None
        better, worse = pair
        value = predictions[predictor].get(f"{better}|{worse}")
        if value not in (0, 1):
            return None
        return better if value == 1 else worse

    parent_meta = {}
    silent_ids = []
    for parent, members in sorted(by_parent.items()):
        tasks = {row["competition"] for row in members}
        runs = {run_of.get(row["card_id"]) for row in members}
        if len(tasks) != 1 or len(runs) != 1 or None in runs:
            raise RuntimeError(f"mixed parent: {parent}")
        children = sorted(row["card_id"] for row in members)
        task, run_id = next(iter(tasks)), next(iter(runs))
        artifact = {
            card_id: float(result_at_cap[card_id]["sub_score"])
            for card_id in children
            if finite(result_at_cap[card_id].get("sub_score"))
        }
        silent = sorted(set(children) - set(artifact))
        truth = {row["card_id"]: float(row["graded"]) for row in members}
        parent_meta[parent] = {
            "children": children,
            "task": task,
            "run_id": run_id,
            "artifact": artifact,
            "silent": silent,
            "truth": truth,
        }
        silent_ids.extend(silent)
    silent_ids = sorted(set(silent_ids))
    index = {card_id: idx for idx, card_id in enumerate(silent_ids)}

    # Static OOS Copeland features and within-set stdout percentile are computable at test time.
    copeland = {predictor: collections.defaultdict(lambda: 0.5) for predictor in STATIC_PREDICTORS}
    stdout_percentile = collections.defaultdict(float)
    for parent, meta in parent_meta.items():
        silent = meta["silent"]
        task = meta["task"]
        for predictor in STATIC_PREDICTORS:
            wins = collections.Counter({card_id: 0.0 for card_id in silent})
            games = collections.Counter({card_id: 0 for card_id in silent})
            for i, left in enumerate(silent):
                for right in silent[i + 1 :]:
                    picked = frozen_preference(predictor, left, right)
                    games[left] += 1
                    games[right] += 1
                    if picked is None:
                        wins[left] += 0.5
                        wins[right] += 0.5
                    else:
                        wins[picked] += 1.0
            for card_id in silent:
                copeland[predictor][card_id] = wins[card_id] / games[card_id] if games[card_id] else 0.5

        observed = {
            card_id: utility(float(result_at_cap[card_id]["stdout_val"]), task, lower)
            for card_id in silent
            if finite(result_at_cap[card_id].get("stdout_val"))
        }
        ordered = sorted(set(observed.values()))
        for card_id, value in observed.items():
            stdout_percentile[card_id] = (
                1.0 if len(ordered) == 1 else ordered.index(value) / (len(ordered) - 1)
            )

    scalar_rows = []
    trace_text = []
    for card_id in silent_ids:
        row = result_at_cap[card_id]
        text = f"{row.get('stdout_tail') or ''}\n{row.get('err_tail') or ''}".lower()
        features = [
            math.log1p(int(row.get("stdout_bytes") or 0)),
            math.log1p(int(row.get("stderr_bytes") or 0)),
            float(int(row.get("rc") or 0) == 0),
            float(finite(row.get("stdout_val"))),
            float(stdout_percentile[card_id]),
            float(row.get("val_how") == "keyed"),
        ]
        features.extend(math.log1p(sum(text.count(word) for word in words)) for words in KEYWORD_GROUPS)
        features.extend(float(copeland[predictor][card_id]) for predictor in STATIC_PREDICTORS)
        scalar_rows.append(features)
        trace_text.append(text)
    scalar = np.asarray(scalar_rows, dtype=float)

    pair_examples = []
    for parent, meta in parent_meta.items():
        silent, task, truth = meta["silent"], meta["task"], meta["truth"]
        for i, left in enumerate(silent):
            for right in silent[i + 1 :]:
                left_u = utility(truth[left], task, lower)
                right_u = utility(truth[right], task, lower)
                if math.isclose(left_u, right_u, abs_tol=1e-12):
                    continue
                pair_examples.append((left, right, int(left_u > right_u), meta["run_id"], task))
    if len(pair_examples) < 20:
        raise RuntimeError("too few non-tied silent pairs")

    def fit_scores(train_ids: set[str], test_ids: set[str], model_name: str) -> dict[str, float]:
        train_indices = np.asarray([index[card_id] for card_id in sorted(train_ids)])
        scaler = StandardScaler().fit(scalar[train_indices])
        scalar_all = sp.csr_matrix(scaler.transform(scalar))
        if model_name in ("text", "combined"):
            vectorizer = TfidfVectorizer(
                ngram_range=(1, 2), min_df=2, max_features=2048, sublinear_tf=True
            )
            try:
                vectorizer.fit([trace_text[idx] for idx in train_indices])
                text_all = vectorizer.transform(trace_text)
            except ValueError:
                text_all = sp.csr_matrix((len(silent_ids), 0))
        if model_name == "scalar":
            candidate_x = scalar_all
        elif model_name == "text":
            candidate_x = text_all
        elif model_name == "combined":
            candidate_x = sp.hstack((scalar_all, text_all), format="csr")
        else:
            raise AssertionError(model_name)

        diffs, labels = [], []
        for left, right, label, _run_id, _task in pair_examples:
            if left not in train_ids or right not in train_ids:
                continue
            diff = candidate_x[index[left]] - candidate_x[index[right]]
            diffs.extend((diff, -diff))
            labels.extend((label, 1 - label))
        if not diffs:
            raise RuntimeError(f"no training pairs for {model_name}")
        train_x = sp.vstack(diffs, format="csr")
        model = LogisticRegression(
            C=1.0, penalty="l2", fit_intercept=False, solver="liblinear",
            max_iter=1000, random_state=args.seed,
        )
        model.fit(train_x, np.asarray(labels))
        return {
            card_id: float(model.decision_function(candidate_x[index[card_id]])[0])
            for card_id in sorted(test_ids)
        }

    runs = np.asarray([run_of[card_id] for card_id in silent_ids])
    group_folds = GroupKFold(n_splits=args.folds)
    run_oof = {name: {} for name in ("scalar", "text", "combined")}
    fold_map = {}
    dummy = np.zeros(len(silent_ids))
    for fold, (train_idx, test_idx) in enumerate(group_folds.split(dummy, groups=runs)):
        train_ids = {silent_ids[idx] for idx in train_idx}
        test_ids = {silent_ids[idx] for idx in test_idx}
        test_runs = sorted({run_of[card_id] for card_id in test_ids})
        if {run_of[card_id] for card_id in train_ids} & set(test_runs):
            raise RuntimeError("physical run leaked across an outer fold")
        for run_id in test_runs:
            fold_map[run_id] = fold
        for name in run_oof:
            run_oof[name].update(fit_scores(train_ids, test_ids, name))

    tasks = sorted({meta["task"] for meta in parent_meta.values()})
    loto = {name: {} for name in ("scalar", "text", "combined")}
    for held_task in tasks:
        test_ids = {card_id for card_id in silent_ids if next(
            meta["task"] for meta in parent_meta.values() if card_id in meta["silent"]
        ) == held_task}
        train_ids = set(silent_ids) - test_ids
        if not test_ids:
            continue
        for name in loto:
            loto[name].update(fit_scores(train_ids, test_ids, name))

    for family in (run_oof, loto):
        for name, scores in family.items():
            if set(scores) != set(silent_ids):
                raise RuntimeError(f"incomplete predictions: {name}")

    def static_stdout_tfidf(parent: str, silent: list[str]) -> str | None:
        if not silent:
            return None
        meta = parent_meta[parent]
        observed = {
            card_id: float(result_at_cap[card_id]["stdout_val"])
            for card_id in silent
            if finite(result_at_cap[card_id].get("stdout_val"))
        }
        if observed:
            return tied_best(observed, meta["task"], lower)[0]
        return deterministic_argmax(
            {card_id: copeland["tfidf_lr"][card_id] for card_id in silent},
            args.seed, parent,
        )

    policy_scores = {
        "top1_scalar_run_oof": run_oof["scalar"],
        "top1_text_run_oof": run_oof["text"],
        "top1_combined_run_oof": run_oof["combined"],
        "top1_scalar_loto": loto["scalar"],
        "top1_text_loto": loto["text"],
        "top1_combined_loto": loto["combined"],
    }
    policy_names = (
        "random_expected", "stdout_tfidf", *policy_scores,
        "oracle_top1", "all_escalate", "full_external",
    )
    per_set = []
    for parent, meta in sorted(parent_meta.items()):
        children, silent = meta["children"], meta["silent"]
        artifact, truth = meta["artifact"], meta["truth"]
        task, run_id = meta["task"], meta["run_id"]
        low_wall = sum(float(result_at_cap[card_id]["wall_s"]) for card_id in children)
        full_cost = sum(runtimes[card_id] for card_id in children)
        for policy in policy_names:
            selections: list[tuple[str | None, float]]
            if policy == "random_expected":
                selections = ([(card_id, 1.0 / len(silent)) for card_id in silent]
                              if silent else [(None, 1.0)])
            elif policy == "stdout_tfidf":
                selections = [(static_stdout_tfidf(parent, silent), 1.0)]
            elif policy in policy_scores:
                selected = (deterministic_argmax(
                    {card_id: policy_scores[policy][card_id] for card_id in silent},
                    args.seed, parent,
                ) if silent else None)
                selections = [(selected, 1.0)]
            elif policy == "oracle_top1":
                selected = (max(silent, key=lambda card_id: utility(truth[card_id], task, lower))
                            if silent else None)
                selections = [(selected, 1.0)]
            elif policy == "all_escalate":
                selections = [("__ALL__", 1.0)]
            elif policy == "full_external":
                selections = [("__FULL__", 1.0)]
            else:
                raise AssertionError(policy)

            top1 = regret = restart = continuation = escalated_n = 0.0
            for selected, weight in selections:
                if selected == "__FULL__":
                    signals = dict(truth)
                    restart_cost = continuation_cost = full_cost
                    n_eval = len(children)
                elif selected == "__ALL__":
                    signals = dict(artifact)
                    signals.update({card_id: truth[card_id] for card_id in silent})
                    restart_cost = low_wall + sum(runtimes[c] for c in silent)
                    continuation_cost = low_wall + sum(max(0.0, runtimes[c] - args.cap) for c in silent)
                    n_eval = len(silent)
                else:
                    signals = dict(artifact)
                    if selected is not None:
                        signals[selected] = truth[selected]
                    restart_cost = low_wall + (runtimes[selected] if selected is not None else 0.0)
                    continuation_cost = low_wall + (
                        max(0.0, runtimes[selected] - args.cap) if selected is not None else 0.0
                    )
                    n_eval = int(selected is not None)
                chosen = tied_best(signals, task, lower) if signals else children
                hit, raw_regret = expected_outcome(chosen, truth, task, lower)
                top1 += weight * hit
                regret += weight * raw_regret
                restart += weight * restart_cost
                continuation += weight * continuation_cost
                escalated_n += weight * n_eval
            per_set.append({
                "parent": parent, "run_id": run_id, "task": task,
                "policy": policy, "n_children": len(children),
                "n_artifact": len(artifact), "n_silent": len(silent),
                "top1_expected": top1, "raw_regret": regret,
                "escalated_expected": escalated_n, "low_wall_s": low_wall,
                "all_full_runtime_s": full_cost, "restart_cost_s": restart,
                "continuation_cost_s": continuation,
            })

    summary = {
        "provenance": {
            "inputs": {name: {"path": str(path), "sha256": sha256(path)} for name, path in paths.items()},
            "script": {"path": __file__, "sha256": sha256(Path(__file__))},
            "git_commit": subprocess.run(
                ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
            ).stdout.strip(),
            "command": (
                f"python {__file__} --cap {args.cap} --folds {args.folds} "
                f"--bootstrap {args.bootstrap} --seed {args.seed} --out-dir {args.out_dir}"
            ),
            "python": platform.python_version(), "sklearn": sklearn.__version__,
        },
        "counts": {
            "sets": len(parent_meta), "children": len(all_ids), "silent": len(silent_ids),
            "runs": len(set(run_of.values()) & {meta["run_id"] for meta in parent_meta.values()}),
            "tasks": len(tasks), "non_tied_silent_pairs": len(pair_examples),
        },
        "design": {
            "outer": f"{args.folds}-fold physical-run OOF", "secondary": "leave-one-task-out",
            "primary_model": "combined", "tuning": "none", "cap_s": args.cap,
            "bootstrap_draws": args.bootstrap, "seed": args.seed,
        },
        "fold_map": fold_map,
        "policies": {}, "paired": {},
    }
    index_rows = {(row["policy"], row["parent"]): row for row in per_set}
    for policy in policy_names:
        rows = [row for row in per_set if row["policy"] == policy]
        lo, hi = cluster_bootstrap(rows, "top1_expected", args.bootstrap, args.seed)
        summary["policies"][policy] = {
            "top1": statistics.mean(row["top1_expected"] for row in rows),
            "top1_run_cluster_ci95": [lo, hi],
            "mean_raw_regret": statistics.mean(row["raw_regret"] for row in rows),
            "full_evaluations_expected": sum(row["escalated_expected"] for row in rows),
            "restart_ratio_to_all_full": sum(row["restart_cost_s"] for row in rows) / sum(row["all_full_runtime_s"] for row in rows),
            "continuation_ratio_to_all_full": sum(row["continuation_cost_s"] for row in rows) / sum(row["all_full_runtime_s"] for row in rows),
        }

    for left in ("top1_combined_run_oof", "top1_combined_loto", "stdout_tfidf"):
        difference = []
        for parent in sorted(parent_meta):
            a, b = index_rows[(left, parent)], index_rows[("random_expected", parent)]
            difference.append({"run_id": a["run_id"], "delta": a["top1_expected"] - b["top1_expected"]})
        lo, hi = cluster_bootstrap(difference, "delta", args.bootstrap, args.seed)
        summary["paired"][f"{left}_minus_random_expected"] = {
            "delta_top1": statistics.mean(row["delta"] for row in difference),
            "run_cluster_ci95": [lo, hi],
        }

    primary = summary["paired"]["top1_combined_run_oof_minus_random_expected"]
    loto_delta = summary["paired"]["top1_combined_loto_minus_random_expected"]["delta_top1"]
    if primary["run_cluster_ci95"][0] > 0 and loto_delta >= 0:
        verdict = "GO"
    elif primary["delta_top1"] > 0:
        verdict = "BORDERLINE"
    else:
        verdict = "KILL"
    summary["preregistered_verdict"] = verdict

    # Guard the two published anchors before writing a new claim.
    if not math.isclose(summary["policies"]["all_escalate"]["top1"], 0.96):
        raise RuntimeError("all-escalate anchor did not reproduce")
    if not math.isclose(summary["policies"]["full_external"]["top1"], 1.0):
        raise RuntimeError("full-external anchor did not reproduce")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "per_set.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(per_set[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(per_set)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    print(
        f"VERIFIED sets={summary['counts']['sets']} runs={summary['counts']['runs']} "
        f"children={summary['counts']['children']} silent={summary['counts']['silent']} "
        f"pairs={summary['counts']['non_tied_silent_pairs']}"
    )
    for policy in policy_names:
        row = summary["policies"][policy]
        lo, hi = row["top1_run_cluster_ci95"]
        print(
            f"{policy:28s} top1={row['top1']:.4f} [{lo:.4f},{hi:.4f}] "
            f"restart={row['restart_ratio_to_all_full']:.4f} "
            f"continue={row['continuation_ratio_to_all_full']:.4f}"
        )
    print(f"PREREGISTERED_VERDICT={verdict}")
    print(f"WROTE {out_dir}")


if __name__ == "__main__":
    main()
