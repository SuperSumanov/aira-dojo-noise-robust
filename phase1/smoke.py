"""Phase-1a acceptance smoke: mock cards -> 6 predictors -> per-run CSV + summary table +
sample-efficiency plots, entirely on CPU in ~seconds with NO model downloads or real experiments.

Run:  python -m phase1.smoke            (writes to phase1/_smoke_out/)
      python -m phase1.smoke --quick    (tiny; used by the pytest gate)

The `run()` function returns (rows, paths) and asserts the pipeline's structural invariants so it can
double as the test body. It checks PLUMBING (all 6 predictors emit finite scores for every split; CSV
+ plot artifacts are written), and a couple of SANITY properties of the synthetic signal (a learned
critic beats a random-order floor; label-free baselines are flat across the budget). It does NOT
assert which critic wins — that is an empirical question for the real-data run.
"""
from __future__ import annotations

import argparse
import os
from typing import Dict, List, Tuple

import numpy as np

from .critics import ALL_PREDICTORS
from .eval import metrics as M
from .eval.plots import plot_all
from .eval.runner import Row, aggregate, run_sweep, summary_table, write_csv
from .mock import generate


def run(out_dir: str, quick: bool = False) -> Tuple[List[Row], Dict[str, str], str, List[str]]:
    if quick:
        cards = generate(n_tasks=4, n_per_task=40, seed=0)
        budgets, seeds = [25, 50, "all"], (0, 1)
    else:
        cards = generate(n_tasks=5, n_per_task=60, seed=0)
        budgets, seeds = [25, 50, 100, 200, "all"], (0, 1, 2)

    rows = run_sweep(cards, budgets=budgets, seeds=seeds, backend="mock", commit="mock")

    os.makedirs(out_dir, exist_ok=True)
    csv_path = os.path.join(out_dir, "runs.csv")
    write_csv(rows, csv_path)
    table = summary_table(rows)
    plot_msgs = plot_all(rows, out_dir)

    # ---- structural invariants (the actual gate) ----
    got = {r.predictor for r in rows}
    assert got == set(ALL_PREDICTORS), f"missing predictors: {set(ALL_PREDICTORS) - got}"
    for r in rows:
        for m in M.METRICS:
            assert np.isfinite(r.metrics[m]), f"non-finite {m} for {r.predictor}@{r.budget}"

    # ---- sanity of the synthetic signal (guards a broken featurizer/label round-trip) ----
    agg_sp = aggregate(rows, "spearman")
    # every learned critic clears a near-zero floor at the largest budget
    for name in ("scalar", "reasoning", "probe"):
        assert agg_sp[name]["median"][-1] > 0.2, f"{name} failed to learn on mock (spearman<=0.2)"
    # label-free baselines are flat: spearman barely moves from smallest to largest budget
    for name in ("one_epoch", "asha", "zeroshot"):
        med = agg_sp[name]["median"]
        assert abs(med[-1] - med[0]) < 0.05, f"{name} should be flat in N (label-free)"

    paths = {"csv": csv_path, "out_dir": out_dir}
    return rows, paths, table, plot_msgs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "_smoke_out"))
    args = ap.parse_args()

    rows, paths, table, plot_msgs = run(args.out, quick=args.quick)
    print(table)
    print()
    for m in plot_msgs:
        print(m)
    print(f"\n[smoke] {len(rows)} runs -> {paths['csv']}")
    print("[smoke] PASS: 6 predictors x budgets x seeds x LOTO folds, all metrics finite.")


if __name__ == "__main__":
    main()
