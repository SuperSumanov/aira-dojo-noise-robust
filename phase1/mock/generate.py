"""Synthetic card generator — lets the whole harness (dataset -> critics -> eval -> plots) run
end-to-end on CPU in minutes with NO real experiments or model downloads. This is the acceptance
gate for Phase 1a.

Design of the synthetic signal (so the smoke is meaningful, not just plumbing):
  * latent true quality q ~ U(0,1); the label y_norm depends on q AND on op/depth.
  * the cheap signal `val_at_low` is a NOISY, biased proxy that captures only PART of q ->
    the trivial baselines (rank by val_at_low) get decent-but-imperfect ranking, while a critic
    that learns from the full feature set can exceed them and improve with the label budget N.
Everything is seeded (reproducible).
"""
from __future__ import annotations

from typing import List

import numpy as np

from ..cards import Card, TaskInfo, Obs, Lineage, Label, OPS, TASK_TYPES, normalize_graded

_THR = {"bronze": 0.4, "silver": 0.6, "gold": 0.8}
_OP_BONUS = {"Draft": 0.0, "Debug": -0.05, "Improve": 0.05}


def generate(n_tasks: int = 5, n_per_task: int = 60, seed: int = 0) -> List[Card]:
    rng = np.random.default_rng(seed)
    cards: List[Card] = []
    for ti in range(n_tasks):
        ttype = TASK_TYPES[ti % len(TASK_TYPES)]
        tk = TaskInfo(name=f"mocktask{ti}", type=ttype, metric="auc", higher_is_better=True,
                      desc=f"synthetic {ttype} task {ti}", medal_thresholds=dict(_THR))
        task_bias = float(rng.normal(0, 0.10))
        for j in range(n_per_task):
            q = float(rng.uniform(0, 1))
            op = OPS[int(rng.integers(0, len(OPS)))]
            depth = int(rng.integers(0, 4))
            # cheap proxy: sees ~q but noisy + task-biased (misses the op/depth part of quality)
            val_at_low = float(np.clip(0.5 * q + 0.30 + task_bias + rng.normal(0, 0.12), 0, 1))
            curve = [float(v) for v in np.clip(np.cumsum(rng.normal(val_at_low / 3.0, 0.03, 3)), 0, 1)]
            parent_val = None if op == "Draft" else float(np.clip(q - 0.1 + rng.normal(0, 0.1), 0, 1))
            runtime = float(rng.uniform(30, 600))
            # true label uses q AND op/depth structure that val_at_low cannot fully capture.
            # Label noise is deliberately non-trivial (0.15) so labels genuinely matter: the learned
            # critics clear the label-free baselines, and the budget axis moves the *ceiling* and
            # calibration (ECE) most clearly. Note (honest): rank (Spearman) saturates fast here
            # because the cheap val_at_low already ranks well — a realistic shape, not a bug; the
            # harness reports it faithfully rather than the mock manufacturing a rising curve.
            y = float(np.clip(0.6 * q + 0.4 * (0.5 + _OP_BONUS[op] * 4 + (1 - depth / 4.0) * 0.5)
                              + rng.normal(0, 0.15), 0, 1))
            graded = 0.6 * y + 0.2  # inverse of normalize_graded so the round-trip recovers y
            y_norm, bucket = normalize_graded(graded, tk.medal_thresholds, True)
            cards.append(Card(
                id=f"{tk.name}__c{j}", task=tk,
                code=f"# mock solution {j}\n" + "x = 1\n" * int(rng.integers(3, 40)),
                obs=Obs(fidelity={"epochs": 1, "data_frac": 0.1}, val_curve=curve, val_at_low=val_at_low,
                        runtime_s=runtime, error=None, stdout_tail=f"FINAL_VALIDATION_SCORE: {val_at_low:.3f}"),
                lineage=Lineage(parent_val=parent_val, op=op, depth=depth),
                label=Label(graded=float(graded), y_norm=float(y_norm), medal_bucket=bucket),
            ))
    return cards
