from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np


class SimulationError(RuntimeError):
    pass


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise SimulationError(reason)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def wilson(successes: int, trials: int) -> tuple[float, float]:
    z = 1.959963984540054
    p = successes / trials
    den = 1.0 + z * z / trials
    center = (p + z * z / (2.0 * trials)) / den
    half = z * math.sqrt(p * (1.0 - p) / trials + z * z / (4.0 * trials * trials)) / den
    return center - half, center + half


def simulate(counts: np.ndarray, delta: float, q: float, tau: float, rho: float, training_seeds: int,
             critical: float, trials: int, batch_size: int, seed: int) -> dict:
    require(counts.ndim == 1 and len(counts) >= 2 and np.all(counts > 0), "task_counts")
    require(0 < delta < q <= 1 and tau >= 0 and 0 <= rho <= 1, "scenario")
    require(trials > 0 and 0 < batch_size <= trials, "simulation_size")
    factor = (1.0 + (training_seeds - 1) * rho) / training_seeds
    task_sd = np.sqrt(tau * tau + (q - delta * delta) * factor / counts)
    rng = np.random.default_rng(seed)
    successes = 0
    completed = 0
    while completed < trials:
        size = min(batch_size, trials - completed)
        task_means = delta + rng.standard_normal((size, len(counts))) * task_sd
        estimates = task_means.mean(axis=1)
        standard_errors = task_means.std(axis=1, ddof=1) / math.sqrt(len(counts))
        successes += int(np.count_nonzero(estimates - critical * standard_errors > 0.0))
        completed += size
    low, high = wilson(successes, trials)
    return {"power": successes / trials, "successes": successes, "trials": trials,
            "wilson_95": [low, high], "wilson_95_half_width": (high - low) / 2.0}


def run(protocol_path: Path, input_path: Path) -> dict:
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    require(sha256(input_path) == protocol["input"]["sha256"], "input_sha")
    source = json.loads(input_path.read_text(encoding="utf-8"))
    rows = source["metrics"]["arms"]["full"]["anonymous_task_rows"]
    counts = np.asarray([row["local_pairs"] for row in rows], dtype=np.float64)
    require(len(counts) == 28 and int(counts.sum()) == 4689, "structure")
    fixed = protocol["fixed"]
    outputs = {}
    all_gates = True
    for name, scenario in protocol["scenarios"].items():
        replications = []
        for seed in fixed["simulation_seeds"]:
            replications.append(simulate(
                counts, fixed["delta"], scenario["paired_discordance"], scenario["between_task_sd"],
                scenario["seed_correlation"], fixed["training_seeds"], fixed["task_ci_t_critical_df27"],
                fixed["trials_per_replication"], fixed["batch_size"], seed,
            ))
        mean_power = sum(row["power"] for row in replications) / len(replications)
        gates = {
            "replication_difference": abs(replications[0]["power"] - replications[1]["power"])
                <= protocol["gates"]["maximum_replication_absolute_difference"],
            "analytic_difference": abs(mean_power - scenario["analytic_power"])
                <= protocol["gates"]["maximum_mean_mc_vs_analytic_absolute_difference"],
            "mc_half_width": all(row["wilson_95_half_width"]
                <= protocol["gates"]["maximum_wilson_95_half_width"] for row in replications),
        }
        all_gates = all_gates and all(gates.values())
        outputs[name] = {"analytic_power": scenario["analytic_power"], "mean_mc_power": mean_power,
                         "replications": replications, "gates": gates}
    return {
        "all_gates_pass": all_gates,
        "classification": protocol["classification"],
        "input_sha256": sha256(input_path),
        "protocol_sha256": sha256(protocol_path),
        "scenarios": outputs,
        "resources": {"gpu_jobs": 0, "model_fits": 0, "paid_api_calls": 0, "protected_values_read": 0},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.protocol, args.input)
    args.output.write_text(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
