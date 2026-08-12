"""Audit endpoint-identity accuracy versus actually deployable mixed-fidelity score."""

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


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", default="phase1/fidelity_manifest.jsonl")
    p.add_argument("--results", default="phase1/fidelity_results.jsonl")
    p.add_argument("--run-map", default="phase1/card_run_map.json")
    p.add_argument("--orientation", default="phase1/task_orientation.json")
    p.add_argument("--cap", type=int, default=120)
    p.add_argument("--bootstrap", type=int, default=10000)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--out-dir", default="phase1/deployment_semantics_v9")
    return p.parse_args()


def jsonl(path):
    with Path(path).open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def finite(x):
    return isinstance(x, (int, float)) and math.isfinite(float(x))


def utility(x, task, lower):
    return -float(x) if lower.get(task, False) else float(x)


def pct(values, q):
    values = sorted(values)
    return values[min(len(values) - 1, max(0, int(q * len(values))))]


def boot(rows, field, draws, seed):
    groups = collections.defaultdict(list)
    for row in rows:
        groups[row["run_id"]].append(float(row[field]))
    keys = sorted(groups)
    rng = random.Random(seed)
    estimates = []
    for _ in range(draws):
        vals = [v for k in (rng.choice(keys) for _ in keys) for v in groups[k]]
        estimates.append(statistics.mean(vals))
    return pct(estimates, .025), pct(estimates, .975)


def main():
    a = parse_args()
    paths = {name: Path(value) for name, value in {
        "manifest": a.manifest, "results": a.results,
        "run_map": a.run_map, "orientation": a.orientation,
    }.items()}
    manifest = jsonl(paths["manifest"])
    results = {r["card_id"]: r for r in jsonl(paths["results"]) if int(r["cap"]) == a.cap}
    run_of = json.loads(paths["run_map"].read_text(encoding="utf-8"))
    lower = json.loads(paths["orientation"].read_text(encoding="utf-8"))
    by_parent = collections.defaultdict(list)
    for row in manifest:
        by_parent[row["parent"]].append(row)
    ids = {row["card_id"] for row in manifest}
    if set(results) != ids:
        raise RuntimeError("cap result coverage mismatch")

    rows = []
    for parent, members in sorted(by_parent.items()):
        tasks = {m["competition"] for m in members}
        runs = {run_of.get(m["card_id"]) for m in members}
        if len(tasks) != 1 or len(runs) != 1 or None in runs:
            raise RuntimeError(f"mixed parent {parent}")
        task, run_id = next(iter(tasks)), next(iter(runs))
        truth = {m["card_id"]: utility(m["graded"], task, lower) for m in members}
        artifact = {
            m["card_id"]: utility(results[m["card_id"]]["sub_score"], task, lower)
            for m in members if finite(results[m["card_id"]].get("sub_score"))
        }
        silent = set(truth) - set(artifact)
        mixed = dict(artifact)
        mixed.update({card_id: truth[card_id] for card_id in silent})
        full_best = max(truth.values())
        deploy_best = max(mixed.values())
        selected = {card_id for card_id, value in mixed.items() if math.isclose(value, deploy_best, abs_tol=1e-12)}
        endpoint_best = {card_id for card_id, value in truth.items() if math.isclose(value, full_best, abs_tol=1e-12)}
        identity_hit = len(selected & endpoint_best) / len(selected)
        delta = deploy_best - full_best
        source_artifact = len(selected & set(artifact)) / len(selected)
        rows.append({
            "parent": parent, "run_id": run_id, "task": task,
            "n_children": len(truth), "n_artifact": len(artifact), "n_silent": len(silent),
            "endpoint_identity_top1": identity_hit,
            "selected_artifact_fraction": source_artifact,
            "deployed_utility": deploy_best, "full_final_best_utility": full_best,
            "deployed_delta_to_full_final": delta,
            "deployed_matches_or_beats_full": float(delta >= -1e-12),
            "deployed_strictly_beats_full": float(delta > 1e-12),
            "deployed_strictly_loses_full": float(delta < -1e-12),
        })

    summary = {
        "provenance": {
            "inputs": {k: {"path": str(v), "sha256": sha256(v)} for k, v in paths.items()},
            "script": {"path": __file__, "sha256": sha256(__file__)},
            "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip(),
            "python": platform.python_version(),
            "command": f"python {__file__} --cap {a.cap} --bootstrap {a.bootstrap} --seed {a.seed} --out-dir {a.out_dir}",
        },
        "counts": {"sets": len(rows), "runs": len({r['run_id'] for r in rows}), "tasks": len({r['task'] for r in rows})},
        "semantics": {
            "endpoint_identity_top1": "selected card ID's eventual full endpoint is best",
            "deployed_matches_or_beats_full": "best actually available partial-artifact/silent-full score >= best all-full endpoint score",
        },
        "all_escalate": {}, "by_task": {},
    }
    for field in (
        "endpoint_identity_top1", "selected_artifact_fraction",
        "deployed_matches_or_beats_full", "deployed_strictly_beats_full",
        "deployed_strictly_loses_full", "deployed_delta_to_full_final",
    ):
        vals = [float(r[field]) for r in rows]
        lo, hi = boot(rows, field, a.bootstrap, a.seed)
        summary["all_escalate"][field] = {"mean": statistics.mean(vals), "run_cluster_ci95": [lo, hi]}
    for task in sorted({r["task"] for r in rows}):
        task_rows = [r for r in rows if r["task"] == task]
        summary["by_task"][task] = {
            "sets": len(task_rows),
            "endpoint_identity_top1": statistics.mean(r["endpoint_identity_top1"] for r in task_rows),
            "deployed_matches_or_beats_full": statistics.mean(r["deployed_matches_or_beats_full"] for r in task_rows),
            "mean_delta": statistics.mean(r["deployed_delta_to_full_final"] for r in task_rows),
        }

    if not math.isclose(summary["all_escalate"]["endpoint_identity_top1"]["mean"], .96):
        raise RuntimeError("published endpoint identity anchor did not reproduce")
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "per_set.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)
    (out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"VERIFIED sets={len(rows)} runs={summary['counts']['runs']} tasks={summary['counts']['tasks']}")
    for field, value in summary["all_escalate"].items():
        lo, hi = value["run_cluster_ci95"]
        print(f"{field:36s} {value['mean']:+.6f} [{lo:+.6f},{hi:+.6f}]")
    print(f"WROTE {out}")


if __name__ == "__main__":
    main()
