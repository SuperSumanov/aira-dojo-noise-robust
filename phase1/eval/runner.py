"""Evaluation sweep: predictor x label-budget x seed x LOTO-fold -> per-run metrics.

Emits a per-run CSV (one row per run: predictor/budget/seed/task + every metric + n_train/n_test +
commit) — the canonical artifact per the project's reproducibility rules. `aggregate()` collapses the
runs into per-(predictor,budget) median + bootstrap CI for the sample-efficiency plot.

Label-hiding is enforced here: critics only ever see ``card.hidden()`` at predict time.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

import numpy as np

from ..cards import Card
from ..critics import ALL_PREDICTORS, build
from ..dataset import DEFAULT_BUDGETS, make_splits
from . import metrics as M


def _budget_label(b) -> str:
    return "all" if (b == "all" or b is None) else str(int(b))


@dataclass
class Row:
    predictor: str
    budget: str
    seed: int
    task: str
    n_train: int
    n_test: int
    metrics: Dict[str, float]
    commit: str = "mock"

    def flat(self) -> Dict[str, object]:
        d = {"predictor": self.predictor, "budget": self.budget, "seed": self.seed,
             "task": self.task, "n_train": self.n_train, "n_test": self.n_test, "commit": self.commit}
        d.update({m: self.metrics[m] for m in M.METRICS})
        return d


def evaluate_split(split, name: str, backend: str, commit: str) -> Optional[Row]:
    train = [c for c in split.train if c.y is not None]
    test = [c for c in split.test if c.y is not None]
    if not test:
        return None
    critic = build(name, backend=backend)
    critic.fit(train)
    preds = np.asarray(critic.predict([c.hidden() for c in test]), float)  # label-hidden inputs
    y = np.array([c.y for c in test], float)
    return Row(predictor=name, budget=_budget_label(split.budget), seed=split.seed, task=split.task,
               n_train=len(train), n_test=len(test), metrics=M.compute_all(y, preds), commit=commit)


def run_sweep(cards: List[Card], predictors: Sequence[str] = ALL_PREDICTORS, budgets=None,
              seeds=(0, 1, 2), backend: str = "mock", commit: str = "mock") -> List[Row]:
    budgets = budgets or DEFAULT_BUDGETS
    splits = list(make_splits(cards, budgets=budgets, seeds=seeds))
    rows: List[Row] = []
    for name in predictors:
        for sp in splits:
            r = evaluate_split(sp, name, backend, commit)
            if r is not None:
                rows.append(r)
    return rows


def write_csv(rows: List[Row], path: str) -> None:
    if not rows:
        return
    fields = list(rows[0].flat().keys())
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r.flat())


def aggregate(rows: List[Row], metric: str, n_boot: int = 1000, seed: int = 0):
    """-> {predictor: {"x":[budget labels], "median":[...], "lo":[...], "hi":[...]}} for one metric.
    Median + percentile bootstrap CI over the per-run values (across seeds x folds)."""
    order = ["25", "50", "100", "200", "all"]
    rng = np.random.default_rng(seed)
    out: Dict[str, Dict[str, list]] = {}
    preds = []
    for r in rows:
        if r.predictor not in preds:
            preds.append(r.predictor)
    for p in preds:
        xs, med, lo, hi = [], [], [], []
        for b in order:
            vals = np.array([r.metrics[metric] for r in rows
                             if r.predictor == p and r.budget == b and np.isfinite(r.metrics[metric])])
            if len(vals) == 0:
                continue
            xs.append(b)
            med.append(float(np.median(vals)))
            if len(vals) >= 2:
                boot = np.array([np.median(vals[rng.integers(0, len(vals), len(vals))]) for _ in range(n_boot)])
                lo.append(float(np.quantile(boot, 0.025)))
                hi.append(float(np.quantile(boot, 0.975)))
            else:
                lo.append(float(vals[0])); hi.append(float(vals[0]))
        out[p] = {"x": xs, "median": med, "lo": lo, "hi": hi}
    return out


def summary_table(rows: List[Row]) -> str:
    """Compact text table: rows = predictors, cols = budgets, cell = median Spearman (the headline)."""
    order = ["25", "50", "100", "200", "all"]
    preds = ALL_PREDICTORS
    lines = ["metric=spearman (median over seeds x LOTO folds)",
             "predictor  " + "".join(f"{b:>8}" for b in order)]
    for p in preds:
        cells = []
        for b in order:
            vals = [r.metrics["spearman"] for r in rows
                    if r.predictor == p and r.budget == b and np.isfinite(r.metrics["spearman"])]
            cells.append(f"{np.median(vals):>8.3f}" if vals else f"{'-':>8}")
        lines.append(f"{p:<11}" + "".join(cells))
    return "\n".join(lines)
