#!/usr/bin/env python3
"""Deterministic beta-binomial planning simulation for task-clustered SPT designs."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import statistics


T_CRIT_975 = {10: 2.262, 19: 2.101, 25: 2.064}
DESIGNS = {
    "old_100": [10] * 10,
    "v11_max_176": [15] * 9 + [12, 8, 4, 4, 4, 2, 2, 2, 2, 1],
    "future_375": [15] * 25,
}


def scenario_seed(base_seed: int, name: str, rho: float) -> int:
    payload = f"{base_seed}|{name}|{rho:.6f}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def power(*, sizes: list[int], p: float, rho: float, sims: int, seed: int) -> float:
    rng = random.Random(seed)
    concentration = 1.0 / rho - 1.0
    alpha = p * concentration
    beta = (1.0 - p) * concentration
    critical = T_CRIT_975[len(sizes)]
    rejected = 0
    for _ in range(sims):
        task_accuracy = []
        for size in sizes:
            task_p = rng.betavariate(alpha, beta)
            successes = sum(rng.random() < task_p for _ in range(size))
            task_accuracy.append(successes / size)
        mean = statistics.fmean(task_accuracy)
        standard_error = statistics.stdev(task_accuracy) / math.sqrt(len(task_accuracy))
        rejected += mean - critical * standard_error > 0.5
    return rejected / sims


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sims", type=int, default=50_000)
    parser.add_argument("--seed", type=int, default=20_260_813)
    parser.add_argument("--true-accuracy", type=float, default=0.65)
    args = parser.parse_args()
    if args.sims <= 0 or not 0.5 < args.true_accuracy < 1.0:
        raise RuntimeError("invalid planning arguments")

    output = {
        "schema_version": 1,
        "estimand": "unweighted task-macro accuracy",
        "test": "two-sided 95% task-level t lower bound strictly above 0.5",
        "model": "beta-binomial task random effect; rho is within-task Bernoulli ICC",
        "base_seed": args.seed,
        "simulations_per_cell": args.sims,
        "true_accuracy": args.true_accuracy,
        "designs": {},
    }
    for name, sizes in DESIGNS.items():
        row = {
            "tasks": len(sizes),
            "pairs": sum(sizes),
            "task_sizes": sizes,
            "power": {},
        }
        for rho in (0.1, 0.2):
            seed = scenario_seed(args.seed, name, rho)
            row["power"][f"rho_{rho:.1f}"] = {
                "seed": seed,
                "value": power(
                    sizes=sizes,
                    p=args.true_accuracy,
                    rho=rho,
                    sims=args.sims,
                    seed=seed,
                ),
            }
        output["designs"][name] = row
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
