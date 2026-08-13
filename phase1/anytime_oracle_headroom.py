"""Locked descriptive oracle headroom for current selective-feedback bottleneck.

This is a hindsight upper bound on the frozen v9 discovery set, not a method result.
"""

from __future__ import annotations

import argparse
import collections
import json
import math
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


def cli() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", default="phase1/fidelity_manifest.jsonl")
    p.add_argument("--results", default="phase1/fidelity_results.jsonl")
    p.add_argument("--runtime", default="phase1/fidelity_runtime_v9.jsonl")
    p.add_argument("--run-map", default="phase1/card_run_map.json")
    p.add_argument("--orientation", default="phase1/task_orientation.json")
    p.add_argument("--out", default="phase1/anytime_oracle_headroom_v9.json")
    return p.parse_args()


def digest(path: Path) -> str:
    import hashlib

    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def lines(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def finite(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def util(value: float, task: str, lower: dict[str, bool]) -> float:
    return -float(value) if lower[task] else float(value)


def best(values: dict[str, float], task: str, lower: dict[str, bool]) -> set[str]:
    peak = max(util(value, task, lower) for value in values.values())
    return {
        key for key, value in values.items()
        if math.isclose(util(value, task, lower), peak, rel_tol=0.0, abs_tol=1e-12)
    }


def quantile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(q * len(ordered)))]


def main() -> None:
    a = cli()
    paths = {name: Path(getattr(a, name.replace("run_map", "run_map"))) for name in LOCKS}
    observed_locks = {name: digest(path) for name, path in paths.items()}
    if observed_locks != LOCKS:
        raise RuntimeError(observed_locks)
    out = Path(a.out)
    if out.exists():
        raise FileExistsError(out)
    manifest = lines(paths["manifest"])
    nodes = {str(row["card_id"]): row for row in manifest}
    if len(nodes) != len(manifest) or len(nodes) != 230:
        raise RuntimeError("manifest count/uniqueness")
    result_rows = lines(paths["results"])
    keys = [(str(row["card_id"]), int(row["cap"])) for row in result_rows]
    if len(keys) != len(set(keys)) or set(keys) != {(card, cap) for card in nodes for cap in (30, 120)}:
        raise RuntimeError("result grid")
    at120 = {str(row["card_id"]): row for row in result_rows if int(row["cap"]) == 120}
    runtimes_raw = lines(paths["runtime"])
    runtimes = {str(row["card_id"]): float(row["runtime_s"]) for row in runtimes_raw}
    if len(runtimes) != len(runtimes_raw) or set(runtimes) != set(nodes):
        raise RuntimeError("runtime coverage")
    run_map = json.loads(paths["run_map"].read_text(encoding="utf-8"))
    lower = json.loads(paths["orientation"].read_text(encoding="utf-8"))

    groups: dict[str, list[str]] = collections.defaultdict(list)
    for card, row in nodes.items():
        groups[str(row["parent"])].append(card)
    if len(groups) != 100:
        raise RuntimeError("sibling-set count")
    observed_runtime: list[float] = []
    missing_runtime: list[float] = []
    set_rows = []
    total_runtime = total_probe = 0.0
    oracle_pruned_runtime = oracle_tail = 0.0
    current_pruned_runtime = current_tail = 0.0
    oracle_pruned_cards = current_pruned_cards = 0
    all_winners_missing_sets = any_winner_missing_sets = 0
    for parent, child_list in sorted(groups.items()):
        children = set(child_list)
        tasks = {str(nodes[c]["competition"]) for c in children}
        runs = {str(run_map[c]) for c in children}
        if len(tasks) != 1 or len(runs) != 1 or len(children) < 2:
            raise RuntimeError(parent)
        task, run_id = next(iter(tasks)), next(iter(runs))
        truth = {c: float(nodes[c]["graded"]) for c in children}
        winners = best(truth, task, lower)
        scored = {c: float(at120[c]["sub_score"]) for c in children if finite(at120[c].get("sub_score"))}
        missing = children - set(scored)
        observed_runtime.extend(runtimes[c] for c in scored)
        missing_runtime.extend(runtimes[c] for c in missing)
        any_winner_missing_sets += int(bool(winners & missing))
        all_winners_missing_sets += int(winners.issubset(missing))
        current_kept = missing | (best(scored, task, lower) if scored else children)
        oracle_kept = winners
        current_pruned = children - current_kept
        oracle_pruned = children - oracle_kept
        set_runtime = sum(runtimes[c] for c in children)
        set_probe = sum(float(at120[c]["wall_s"]) for c in children)
        current_set_tail = sum(max(runtimes[c] - float(at120[c]["wall_s"]), 0.0) for c in current_pruned)
        oracle_set_tail = sum(max(runtimes[c] - float(at120[c]["wall_s"]), 0.0) for c in oracle_pruned)
        total_runtime += set_runtime
        total_probe += set_probe
        current_pruned_runtime += sum(runtimes[c] for c in current_pruned)
        oracle_pruned_runtime += sum(runtimes[c] for c in oracle_pruned)
        current_tail += current_set_tail
        oracle_tail += oracle_set_tail
        current_pruned_cards += len(current_pruned)
        oracle_pruned_cards += len(oracle_pruned)
        set_rows.append({
            "parent": parent,
            "task": task,
            "run_id": run_id,
            "children": len(children),
            "scored": len(scored),
            "missing": len(missing),
            "winner_any_missing": bool(winners & missing),
            "winner_all_missing": winners.issubset(missing),
            "current_pruned": len(current_pruned),
            "oracle_pruned": len(oracle_pruned),
            "current_tail_fraction": current_set_tail / set_runtime,
            "oracle_tail_fraction": oracle_set_tail / set_runtime,
        })
    result = {
        "status": "hindsight descriptive upper bound on frozen v9 discovery set; not a method result",
        "inputs": observed_locks,
        "counts": {"sets": len(groups), "cards": len(nodes), "runs": len({x["run_id"] for x in set_rows}), "tasks": len({x["task"] for x in set_rows})},
        "selective_missingness": {
            "observed_cards": len(observed_runtime),
            "missing_cards": len(missing_runtime),
            "sets_any_final_winner_missing": any_winner_missing_sets,
            "sets_all_final_winners_missing": all_winners_missing_sets,
            "observed_runtime_median_s": statistics.median(observed_runtime),
            "missing_runtime_median_s": statistics.median(missing_runtime),
            "observed_runtime_q25_q75_s": [quantile(observed_runtime, 0.25), quantile(observed_runtime, 0.75)],
            "missing_runtime_q25_q75_s": [quantile(missing_runtime, 0.25), quantile(missing_runtime, 0.75)],
        },
        "current_censor_aware": {
            "pruned_cards": current_pruned_cards,
            "pruned_card_fraction": current_pruned_cards / len(nodes),
            "pruned_full_runtime_fraction": current_pruned_runtime / total_runtime,
            "optimistic_avoidable_tail_fraction": current_tail / total_runtime,
        },
        "perfect_score_at_120_hindsight_oracle": {
            "pruned_cards": oracle_pruned_cards,
            "pruned_card_fraction": oracle_pruned_cards / len(nodes),
            "pruned_full_runtime_fraction": oracle_pruned_runtime / total_runtime,
            "optimistic_avoidable_tail_fraction": oracle_tail / total_runtime,
            "optimistic_resume_cost_ratio": 1 - oracle_tail / total_runtime,
            "pessimistic_restart_cost_ratio": (total_probe + total_runtime - oracle_pruned_runtime) / total_runtime,
        },
        "interpretation_guard": {
            "uses_final_grade_for_oracle": True,
            "actual_speedup_claim_allowed": False,
            "purpose": "quantify whether improving early score coverage has enough theoretical cost leverage",
        },
    }
    out.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(
        "ANYTIME_ORACLE_HEADROOM",
        f"winner_all_missing_sets={all_winners_missing_sets}",
        f"observed_runtime_median_s={statistics.median(observed_runtime):.1f}",
        f"missing_runtime_median_s={statistics.median(missing_runtime):.1f}",
        f"current_tail={current_tail/total_runtime:.4f}",
        f"oracle_tail={oracle_tail/total_runtime:.4f}",
    )
    print(f"WROTE {out}")


if __name__ == "__main__":
    main()
