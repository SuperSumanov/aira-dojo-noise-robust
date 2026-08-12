"""Offline test of artifact-verified, coverage-aware multi-fidelity selection.

The frozen fidelity experiment ran every candidate in 100 real sibling sets for 120 s.
Some candidates emitted a schema-valid submission that the pristine external grader could
score; others were silent.  This script evaluates the deployable policy:

  1. run every sibling for 120 s;
  2. retain the external score for candidates with a valid artifact;
  3. escalate every silent candidate to full external evaluation;
  4. select by the resulting mixed (partial/full) external scores.

The endpoint is each candidate's already-collected external ``graded`` score.  No model is
trained and no frozen split is modified.  Random tie breaking is integrated analytically.
Inference is clustered by physical run (primary) and parent (secondary), because multiple
sampled decisions can come from one run.

Cost accounting uses the observed capped-run wall times plus every sampled candidate's
historical full runtime exported from the SHA-verified v9 corpus.  The restart policy is
deployable with the current worker; the continuation figure assumes a resumable executor.
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


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", default="phase1/fidelity_manifest.jsonl")
    p.add_argument("--results", default="phase1/fidelity_results.jsonl")
    p.add_argument("--run-map", default="phase1/card_run_map.json")
    p.add_argument("--runtime-map", default="phase1/fidelity_runtime_v9.jsonl")
    p.add_argument("--orientation", default="phase1/task_orientation.json")
    p.add_argument("--cap", type=int, default=120)
    p.add_argument("--bootstrap", type=int, default=10000)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--out-dir", default="phase1/coverage_escalation_v9")
    return p.parse_args()


def read_jsonl(path: Path) -> list[dict]:
    out = []
    with path.open(encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSON at {path}:{lineno}") from exc
    return out


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def finite(value: object) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def utility(value: float, task: str, lower_is_better: dict[str, bool]) -> float:
    return -value if lower_is_better.get(task, False) else value


def tied_best(
    signals: dict[str, float], task: str, lower_is_better: dict[str, bool]
) -> list[str]:
    assert signals
    best = max(utility(v, task, lower_is_better) for v in signals.values())
    return sorted(
        c
        for c, value in signals.items()
        if math.isclose(
            utility(value, task, lower_is_better), best, rel_tol=0.0, abs_tol=1e-12
        )
    )


def evaluate_choice(
    children: list[str],
    signals: dict[str, float] | None,
    truth: dict[str, float],
    task: str,
    lower_is_better: dict[str, bool],
) -> dict[str, object]:
    # No signal means an explicit uniform-random fallback over the complete sibling set.
    picked = children if not signals else tied_best(signals, task, lower_is_better)
    true_utils = {c: utility(truth[c], task, lower_is_better) for c in children}
    best_u = max(true_utils.values())
    true_best = {
        c for c, value in true_utils.items() if math.isclose(value, best_u, abs_tol=1e-12)
    }
    top1 = len(set(picked) & true_best) / len(picked)
    picked_u = statistics.mean(true_utils[c] for c in picked)

    ranked_values = sorted(set(true_utils.values()), reverse=True)
    ranks = {value: 1 + ranked_values.index(value) for value in ranked_values}
    expected_rank = statistics.mean(ranks[true_utils[c]] for c in picked)
    return {
        "picked": "|".join(picked),
        "picked_pool_n": len(picked),
        "top1_expected": top1,
        "raw_regret": best_u - picked_u,
        "rank_expected": expected_rank,
    }


def percentile(values: list[float], q: float) -> float:
    values = sorted(values)
    if not values:
        return float("nan")
    return values[min(len(values) - 1, max(0, int(q * len(values))))]


def cluster_boot(
    by_cluster: dict[str, list[float]], nb: int, seed: int
) -> tuple[float, float]:
    keys = sorted(by_cluster)
    if not keys:
        return float("nan"), float("nan")
    rng = random.Random(seed)
    draws = []
    for _ in range(nb):
        vals = [
            value
            for key in (rng.choice(keys) for _ in keys)
            for value in by_cluster[key]
        ]
        draws.append(statistics.mean(vals))
    return percentile(draws, 0.025), percentile(draws, 0.975)


def interval(
    rows: list[dict], field: str, cluster_field: str, nb: int, seed: int
) -> tuple[float, float]:
    grouped: dict[str, list[float]] = collections.defaultdict(list)
    for row in rows:
        grouped[str(row[cluster_field])].append(float(row[field]))
    return cluster_boot(grouped, nb, seed)


def summarize_rows(rows: list[dict], nb: int, seed: int) -> dict[str, object]:
    top = [float(r["top1_expected"]) for r in rows]
    rank = [float(r["rank_expected"]) for r in rows]
    regret = [float(r["raw_regret"]) for r in rows]
    run_lo, run_hi = interval(rows, "top1_expected", "run_id", nb, seed)
    par_lo, par_hi = interval(rows, "top1_expected", "parent", nb, seed)
    return {
        "sets": len(rows),
        "runs": len({r["run_id"] for r in rows}),
        "top1": statistics.mean(top),
        "top1_run_cluster_ci95": [run_lo, run_hi],
        "top1_parent_cluster_ci95": [par_lo, par_hi],
        "median_raw_regret": statistics.median(regret),
        "mean_rank": statistics.mean(rank),
        "mean_artifact_coverage": statistics.mean(float(r["artifact_coverage"]) for r in rows),
        "mean_full_eval_count": statistics.mean(float(r["full_eval_count"]) for r in rows),
        "mean_cost_ratio_restart_exact": statistics.mean(
            float(r["cost_ratio_restart_exact"]) for r in rows
        ),
        "mean_cost_ratio_continue_exact": statistics.mean(
            float(r["cost_ratio_continue_exact"]) for r in rows
        ),
    }


def paired_difference(
    rows: list[dict], a_name: str, b_name: str, nb: int, seed: int
) -> dict[str, object]:
    index = {(r["policy"], r["parent"]): r for r in rows}
    parents = sorted(
        {r["parent"] for r in rows if r["policy"] == a_name}
        & {r["parent"] for r in rows if r["policy"] == b_name}
    )
    diff_rows = []
    for parent in parents:
        a = index[(a_name, parent)]
        b = index[(b_name, parent)]
        assert a["run_id"] == b["run_id"]
        diff_rows.append(
            {
                "parent": parent,
                "run_id": a["run_id"],
                "delta": float(a["top1_expected"]) - float(b["top1_expected"]),
            }
        )
    run_groups: dict[str, list[float]] = collections.defaultdict(list)
    par_groups: dict[str, list[float]] = collections.defaultdict(list)
    for row in diff_rows:
        run_groups[row["run_id"]].append(row["delta"])
        par_groups[row["parent"]].append(row["delta"])
    rlo, rhi = cluster_boot(run_groups, nb, seed)
    plo, phi = cluster_boot(par_groups, nb, seed)
    return {
        "a": a_name,
        "b": b_name,
        "sets": len(diff_rows),
        "runs": len(run_groups),
        "delta_top1": statistics.mean(r["delta"] for r in diff_rows),
        "run_cluster_ci95": [rlo, rhi],
        "parent_cluster_ci95": [plo, phi],
    }


def main() -> None:
    args = parse_args()
    manifest_path = Path(args.manifest)
    results_path = Path(args.results)
    run_map_path = Path(args.run_map)
    runtime_map_path = Path(args.runtime_map)
    orientation_path = Path(args.orientation)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest = read_jsonl(manifest_path)
    results_all = read_jsonl(results_path)
    run_map = json.loads(run_map_path.read_text(encoding="utf-8"))
    runtime_rows = read_jsonl(runtime_map_path)
    runtime = {}
    runtime_cards_hashes = set()
    for row in runtime_rows:
        cid = row["card_id"]
        assert cid not in runtime, f"duplicate runtime card: {cid}"
        assert finite(row.get("runtime_s")) and float(row["runtime_s"]) >= 0
        runtime[cid] = float(row["runtime_s"])
        runtime_cards_hashes.add(row.get("cards_sha256"))
    assert len(runtime_cards_hashes) == 1 and None not in runtime_cards_hashes
    lower_is_better = json.loads(orientation_path.read_text(encoding="utf-8"))

    # Pre-flight invariants: frozen population, one endpoint, one cap result, and one
    # physical run/task/stratum per decision.  Any violation aborts instead of degrading.
    by_parent: dict[str, list[dict]] = collections.defaultdict(list)
    manifest_ids = set()
    for row in manifest:
        cid = row["card_id"]
        assert cid not in manifest_ids, f"duplicate manifest card: {cid}"
        manifest_ids.add(cid)
        assert finite(row.get("graded")), f"missing/nonfinite truth: {cid}"
        by_parent[row["parent"]].append(row)

    cap_rows = [r for r in results_all if int(r["cap"]) == args.cap]
    cap_index = {}
    for row in cap_rows:
        cid = row["card_id"]
        assert cid not in cap_index, f"duplicate cap result: {cid}, cap={args.cap}"
        cap_index[cid] = row
    assert set(cap_index) == manifest_ids, (
        f"cap coverage mismatch: missing={len(manifest_ids-set(cap_index))}, "
        f"extra={len(set(cap_index)-manifest_ids)}"
    )
    assert set(runtime) == manifest_ids, (
        f"runtime coverage mismatch: missing={len(manifest_ids-set(runtime))}, "
        f"extra={len(set(runtime)-manifest_ids)}"
    )

    set_rows: list[dict] = []
    policies = (
        "random",
        "full_external",
        "full_self_report_available",
        "full_self_report_complete",
        "sub120_available",
        "artifact120_escalate_silent",
    )
    for parent, members in sorted(by_parent.items()):
        children = sorted(r["card_id"] for r in members)
        assert len(children) >= 2
        tasks = {r["competition"] for r in members}
        strata = {r["stratum"] for r in members}
        runs = {run_map.get(c) for c in children}
        assert len(tasks) == len(strata) == len(runs) == 1
        task, stratum, run_id = next(iter(tasks)), next(iter(strata)), next(iter(runs))
        assert run_id is not None, f"run missing for parent {parent}"

        truth = {r["card_id"]: float(r["graded"]) for r in members}
        self_report = {
            r["card_id"]: float(r["val_at_low"])
            for r in members
            if finite(r.get("val_at_low"))
        }
        artifact = {
            c: float(cap_index[c]["sub_score"])
            for c in children
            if finite(cap_index[c].get("sub_score"))
        }
        silent = set(children) - set(artifact)
        escalated = dict(artifact)
        escalated.update({c: truth[c] for c in silent})
        assert set(escalated) == set(children)

        low_wall = sum(float(cap_index[c]["wall_s"]) for c in children)
        full_baseline = sum(runtime[c] for c in children)
        restart_cost = low_wall + sum(runtime[c] for c in silent)
        continuation_cost = low_wall + sum(
            max(0.0, runtime[c] - args.cap) for c in silent
        )
        signals = {
            "random": None,
            "full_external": truth,
            "full_self_report_available": self_report or None,
            "full_self_report_complete": self_report,
            "sub120_available": artifact or None,
            "artifact120_escalate_silent": escalated,
        }
        costs = {
            "random": (0, 0.0, 0.0),
            "full_external": (len(children), full_baseline, full_baseline),
            "full_self_report_available": (len(children), full_baseline, full_baseline),
            "full_self_report_complete": (len(children), full_baseline, full_baseline),
            "sub120_available": (0, low_wall, low_wall),
            "artifact120_escalate_silent": (
                len(silent),
                restart_cost,
                continuation_cost,
            ),
        }
        for policy in policies:
            if policy == "full_self_report_complete" and len(self_report) != len(children):
                continue
            chosen = evaluate_choice(
                children, signals[policy], truth, task, lower_is_better
            )
            full_evals, restart_s, continuation_s = costs[policy]
            set_rows.append(
                {
                    "parent": parent,
                    "run_id": run_id,
                    "task": task,
                    "stratum": stratum,
                    "n_children": len(children),
                    "n_artifacts": len(artifact),
                    "n_silent": len(silent),
                    "artifact_coverage": len(artifact) / len(children),
                    "policy": policy,
                    **chosen,
                    "observed_low_stage_wall_s": low_wall,
                    "full_eval_count": full_evals,
                    "historical_all_full_runtime_s": full_baseline,
                    "cost_restart_exact_s": restart_s,
                    "cost_continue_exact_s": continuation_s,
                    "cost_ratio_restart_exact": restart_s / full_baseline,
                    "cost_ratio_continue_exact": continuation_s / full_baseline,
                }
            )

    # Positive control and accounting assertions catch orientation or policy bugs.
    full_rows = [r for r in set_rows if r["policy"] == "full_external"]
    assert all(math.isclose(float(r["top1_expected"]), 1.0) for r in full_rows)
    assert all(math.isclose(float(r["raw_regret"]), 0.0, abs_tol=1e-12) for r in full_rows)
    assert len(full_rows) == 100, f"expected frozen 100-set sample, got {len(full_rows)}"

    fields = list(set_rows[0])
    with (out_dir / "per_set_policy.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(set_rows)

    summary: dict[str, object] = {
        "provenance": {
            "manifest": str(manifest_path),
            "manifest_sha256": sha256(manifest_path),
            "results": str(results_path),
            "results_sha256": sha256(results_path),
            "run_map": str(run_map_path),
            "run_map_sha256": sha256(run_map_path),
            "runtime_map": str(runtime_map_path),
            "runtime_map_sha256": sha256(runtime_map_path),
            "runtime_source_cards_sha256": next(iter(runtime_cards_hashes)),
            "orientation": str(orientation_path),
            "orientation_sha256": sha256(orientation_path),
            "git_commit": subprocess.run(
                ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
            ).stdout.strip(),
            "python": platform.python_version(),
            "command": (
                f"python phase1/coverage_escalation.py --cap {args.cap} "
                f"--runtime-map {runtime_map_path} --bootstrap {args.bootstrap} --seed {args.seed}"
            ),
        },
        "design": {
            "cap_s": args.cap,
            "bootstrap_draws": args.bootstrap,
            "bootstrap_seed": args.seed,
            "primary_cluster": "physical run",
            "secondary_cluster": "parent decision",
            "cost_warning": (
                "Restart cost combines observed cap-run wall time with historical per-card "
                "full runtime. Continuation cost additionally assumes execution can resume."
            ),
            "population_warning": (
                "The manifest is deliberately 50 hard + 50 easy sets; ALL is balanced, "
                "not an estimate reweighted to the natural corpus difficulty prevalence."
            ),
        },
        "counts": {
            "sets": len(by_parent),
            "physical_runs": len({r["run_id"] for r in full_rows}),
            "children": len(manifest_ids),
            "tasks": len({r["task"] for r in full_rows}),
            "hard_sets": sum(r["stratum"] == "hard" for r in full_rows),
            "easy_sets": sum(r["stratum"] == "easy" for r in full_rows),
            "artifact_children": sum(
                finite(cap_index[c].get("sub_score")) for c in manifest_ids
            ),
            "silent_children": sum(
                not finite(cap_index[c].get("sub_score")) for c in manifest_ids
            ),
            "self_report_children": sum(
                finite(r.get("val_at_low")) for r in manifest
            ),
            "complete_self_report_sets": sum(
                all(finite(r.get("val_at_low")) for r in members)
                for members in by_parent.values()
            ),
        },
        "policy_summary": {},
        "paired_top1_differences": [],
    }
    for stratum in ("ALL_BALANCED", "hard", "easy"):
        summary["policy_summary"][stratum] = {}
        for policy in policies:
            rows = [r for r in set_rows if r["policy"] == policy]
            if stratum != "ALL_BALANCED":
                rows = [r for r in rows if r["stratum"] == stratum]
            summary["policy_summary"][stratum][policy] = summarize_rows(
                rows, args.bootstrap, args.seed
            )

    for stratum in ("ALL_BALANCED", "hard", "easy"):
        subset = set_rows if stratum == "ALL_BALANCED" else [
            r for r in set_rows if r["stratum"] == stratum
        ]
        for baseline in (
            "random",
            "sub120_available",
            "full_self_report_available",
            "full_self_report_complete",
            "full_external",
        ):
            d = paired_difference(
                subset,
                "artifact120_escalate_silent",
                baseline,
                args.bootstrap,
                args.seed,
            )
            d["stratum"] = stratum
            summary["paired_top1_differences"].append(d)

    # Task breakdown is descriptive; task-level n is intentionally visible so isolated
    # wins cannot masquerade as broad consistency.
    task_rows = []
    for task in sorted({r["task"] for r in full_rows}):
        for policy in policies:
            rows = [
                r for r in set_rows if r["task"] == task and r["policy"] == policy
            ]
            if not rows:
                continue
            task_rows.append(
                {
                    "task": task,
                    "policy": policy,
                    "sets": len(rows),
                    "runs": len({r["run_id"] for r in rows}),
                    "top1": statistics.mean(float(r["top1_expected"]) for r in rows),
                    "artifact_coverage": statistics.mean(
                        float(r["artifact_coverage"]) for r in rows
                    ),
                }
            )
    with (out_dir / "task_summary.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(task_rows[0]))
        writer.writeheader()
        writer.writerows(task_rows)

    escalate_rows = [
        r for r in set_rows if r["policy"] == "artifact120_escalate_silent"
    ]
    baseline_s = sum(float(r["historical_all_full_runtime_s"]) for r in escalate_rows)
    restart_ratio = sum(
        float(r["cost_restart_exact_s"]) for r in escalate_rows
    ) / baseline_s
    continue_ratio = sum(
        float(r["cost_continue_exact_s"]) for r in escalate_rows
    ) / baseline_s
    summary["aggregate_cost_accounting"] = {
        "observed_low_stage_wall_s": sum(
            float(r["observed_low_stage_wall_s"]) for r in escalate_rows
        ),
        "full_eval_count": sum(int(r["full_eval_count"]) for r in escalate_rows),
        "all_full_eval_count": sum(int(r["n_children"]) for r in escalate_rows),
        "historical_all_full_runtime_s": baseline_s,
        "restart_exact_ratio_to_all_full": restart_ratio,
        "continuation_exact_ratio_to_all_full": continue_ratio,
    }

    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(
        f"VERIFIED sets={summary['counts']['sets']} runs={summary['counts']['physical_runs']} "
        f"children={summary['counts']['children']} tasks={summary['counts']['tasks']} "
        f"artifacts={summary['counts']['artifact_children']} "
        f"silent={summary['counts']['silent_children']}"
    )
    print(
        f"AGGREGATE_COST low_stage_wall_s="
        f"{sum(float(r['observed_low_stage_wall_s']) for r in escalate_rows):.1f} "
        f"full_evals={sum(int(r['full_eval_count']) for r in escalate_rows)} "
        f"restart_ratio={restart_ratio:.4f} continue_ratio={continue_ratio:.4f}"
    )
    print("policy                         top1      run-cluster 95% CI   restart-cost/full")
    for policy in policies:
        s = summary["policy_summary"]["ALL_BALANCED"][policy]
        lo, hi = s["top1_run_cluster_ci95"]
        print(
            f"{policy:30s} {s['top1']:.4f}   [{lo:.4f},{hi:.4f}]"
            f"       {s['mean_cost_ratio_restart_exact']:.3f}"
        )
    for d in summary["paired_top1_differences"]:
        if d["stratum"] == "ALL_BALANCED":
            lo, hi = d["run_cluster_ci95"]
            print(
                f"paired escalate - {d['b']}: {d['delta_top1']:+.4f} "
                f"[{lo:+.4f},{hi:+.4f}] (run clustered)"
            )
    print(f"WROTE {out_dir}")


if __name__ == "__main__":
    main()
