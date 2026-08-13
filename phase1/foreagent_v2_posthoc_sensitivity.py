"""Post-outcome sensitivity only; never upgrades the frozen v2 decision."""

from __future__ import annotations

import argparse
import csv
import hashlib
import math
from pathlib import Path

import numpy as np


SEED = 20260813
B = 10_000


def exact_two_sided_sign_p(positive: int, negative: int) -> float:
    n = positive + negative
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, k) for k in range(0, min(positive, negative) + 1)) / (2**n)
    return min(1.0, 2.0 * tail)


def summarize(rows: list[dict[str, str]], model: str, subset: str) -> None:
    deltas = np.asarray([float(row["highest_minus_lowest"]) for row in rows], dtype=float)
    lows = np.asarray([float(row["lowest_quartile_accuracy"]) for row in rows], dtype=float)
    label_seed = int.from_bytes(
        hashlib.sha256(f"posthoc:{model}:{subset}".encode()).digest()[:8], "big"
    )
    rng = np.random.default_rng(label_seed ^ SEED)
    indices = rng.integers(0, len(rows), size=(B, len(rows)))
    delta_ci = np.quantile(deltas[indices].mean(axis=1), [0.025, 0.975])
    low_ci = np.quantile(lows[indices].mean(axis=1), [0.025, 0.975])
    positives = int(np.sum(deltas > 0.0))
    negatives = int(np.sum(deltas < 0.0))
    zeros = int(np.sum(deltas == 0.0))
    leave_one_out = np.asarray(
        [np.delete(deltas, index).mean() for index in range(len(deltas))], dtype=float
    )
    print(
        "POSTHOC_SENSITIVITY",
        f"model={model}",
        f"subset={subset}",
        f"tasks={len(rows)}",
        f"q1={lows.mean():.12f}",
        f"q1_ci=[{low_ci[0]:.12f},{low_ci[1]:.12f}]",
        f"q4_minus_q1={deltas.mean():.12f}",
        f"delta_ci=[{delta_ci[0]:.12f},{delta_ci[1]:.12f}]",
        f"signs={positives}/{zeros}/{negatives}",
        f"sign_p={exact_two_sided_sign_p(positives, negatives):.12f}",
        f"loo_delta_range=[{leave_one_out.min():.12f},{leave_one_out.max():.12f}]",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-task", type=Path, required=True)
    args = parser.parse_args()
    with args.per_task.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for model in ("deepseek", "gpt"):
        model_rows = [row for row in rows if row["model_family"] == model]
        supported = [
            row
            for row in model_rows
            if int(row["lowest_quartile_pairs"]) >= 20
            and int(row["highest_quartile_pairs"]) >= 20
        ]
        summarize(model_rows, model, "all26")
        summarize(supported, model, "structural_support22")


if __name__ == "__main__":
    main()
