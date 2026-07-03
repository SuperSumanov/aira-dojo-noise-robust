"""Critic (a): ZERO-SHOT frozen model. No training labels consumed -> flat in the label budget N.

Real backend (step 2): a frozen Qwen2.5-Coder-14B (8-bit / AWQ) is prompted with the card view
(task desc, code, self-reported val, lineage) and asked for a single scalar in [0,1] in ONE forward
pass (no multi-sample voting — hard constraint). The number is parsed from a constrained output
(e.g. a `SCORE: 0.xx` line). This isolates "what does a strong frozen model already know" with zero
label cost — the reference the trained 7B critics must beat.

Mock backend: a FIXED hand-specified heuristic over verifiable card fields (no label access). It knows
the *sign* of the op prior (Improve>Draft>Debug) and rewards an upward curve, but not the true
coefficients -> better than raw val_at_low, still capped and flat in N. This makes the smoke's 6
predictors behave distinctly; it does NOT stand in for the real model's quality.
"""
from __future__ import annotations

from typing import List

import numpy as np

from ..cards import Card
from .base import Critic, orient

_OP_PRIOR = {"Draft": 0.0, "Debug": -1.0, "Improve": 1.0}


class ZeroShotCritic(Critic):
    name = "zeroshot"
    uses_labels = False

    def __init__(self, backend: str = "mock", model: str = "Qwen/Qwen2.5-Coder-14B-Instruct"):
        self.backend = backend
        self.model = model
        self._qwen = None

    def fit(self, train: List[Card]) -> "ZeroShotCritic":
        return self  # zero-shot: nothing to fit

    def predict(self, cards: List[Card]) -> np.ndarray:
        if self.backend == "mock":
            return self._predict_mock(cards)
        return self._predict_qwen(cards)

    def _predict_mock(self, cards: List[Card]) -> np.ndarray:
        out = []
        for c in cards:
            v = c.obs.val_at_low if c.obs.val_at_low is not None else 0.0
            curve = [x for x in (c.obs.val_curve or []) if x is not None]
            slope = (curve[-1] - curve[0]) / max(1, len(curve) - 1) if len(curve) >= 2 else 0.0
            s = v + 0.1 * _OP_PRIOR.get(c.lineage.op, 0.0) + 0.5 * slope - (0.2 if c.obs.error else 0.0)
            out.append(s)
        hib = cards[0].task.higher_is_better if cards else True
        return orient(np.array(out), hib)

    # -- real backend (step 2) --------------------------------------------------
    def _predict_qwen(self, cards: List[Card]) -> np.ndarray:
        raise NotImplementedError(
            "step-2 qwen backend: load frozen Qwen2.5-Coder-14B (8-bit/AWQ), for each card build a "
            "value prompt from Card.view(), single forward pass, parse `SCORE: x.xx`. See README "
            "'real backends'. Deferred so the mock smoke needs no torch/transformers."
        )
