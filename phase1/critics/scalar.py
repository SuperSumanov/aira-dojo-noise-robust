"""Critic (b): SCALAR-head value critic. Base = Qwen2.5-Coder-7B (shared with the reasoning critic
for a fair comparison), trained to regress y_norm directly — NO natural-language reasoning.

Real backend (step 2): QLoRA 4-bit adapter on the 7B + a scalar regression head on the last hidden
state of the card prompt. Loss = MSE(y_norm) + a pairwise ranking hinge (so it orders candidates,
not just fits magnitudes). Small batch + grad-accum to fit a 3090. Single forward at predict time.

Mock backend: closed-form ridge on the numeric featurizer (cards.card_features), incl. op/type
one-hots. Because the mock label depends on op/depth (which val_at_low misses), ridge with enough
labels beats the baselines and IMPROVES with the budget N — the sample-efficiency signal the harness
must be able to measure. This is the "learn a direct value map from features" arm.
"""
from __future__ import annotations

from typing import List

import numpy as np

from ..cards import Card, features_matrix
from .base import Critic, Ridge


class ScalarCritic(Critic):
    name = "scalar"
    uses_labels = True

    def __init__(self, backend: str = "mock", lam: float = 5.0,
                 model: str = "Qwen/Qwen2.5-Coder-7B-Instruct"):
        self.backend = backend
        self.lam = lam
        self.model = model
        self._ridge = None

    def fit(self, train: List[Card]) -> "ScalarCritic":
        if self.backend == "mock":
            train = [c for c in train if c.y is not None]
            if train:
                X = features_matrix(train)
                y = np.array([c.y for c in train], float)
                self._ridge = Ridge(self.lam).fit(X, y)
            return self
        return self._fit_qwen(train)

    def predict(self, cards: List[Card]) -> np.ndarray:
        if self.backend == "mock":
            if self._ridge is None:
                return np.zeros(len(cards))
            return self._ridge.predict(features_matrix(cards))
        return self._predict_qwen(cards)

    # -- real backend (step 2) --------------------------------------------------
    def _fit_qwen(self, train: List[Card]) -> "ScalarCritic":
        raise NotImplementedError(
            "step-2 qwen backend: QLoRA 4-bit on Qwen2.5-Coder-7B + scalar head; loss = MSE(y_norm) "
            "+ pairwise ranking hinge; grad-accum for 3090. See README 'real backends'."
        )

    def _predict_qwen(self, cards: List[Card]) -> np.ndarray:
        raise NotImplementedError("step-2 qwen backend: single forward, read scalar head. See README.")
