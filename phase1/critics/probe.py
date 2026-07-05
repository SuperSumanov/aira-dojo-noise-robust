"""Critic (d): linear/MLP PROBE on FROZEN representations. No fine-tuning of the backbone at all —
only a cheap readout is trained. This tests "how much value signal is already linearly decodable
from a frozen model's activations + token-level uncertainty," which is the cheapest possible critic
to train and a strong baseline against the QLoRA critics.

Real backend (step 2): run a frozen Qwen2.5-Coder (7B or 14B) over the card prompt, extract features =
[mean/last hidden state of chosen layers, mean token entropy / logprob of the code region], fit a
linear (or tiny MLP) probe to y_norm. Frozen backbone -> features can be CACHED once per card, so the
label-budget sweep is nearly free.

Mock backend: a FIXED (seeded, un-trained) random projection + tanh over the numeric featurizer stands
in for "frozen representation"; only the linear readout (ridge) is fit on labels. Because the
projection is random-but-frozen it loses some information -> learns with N but typically trails the
scalar critic. Distinct 6th predictor for the smoke.
"""
from __future__ import annotations

from typing import List, Optional

import numpy as np

from ..cards import Card, features_matrix
from .base import Critic, Ridge


class ProbeCritic(Critic):
    name = "probe"
    uses_labels = True

    def __init__(self, backend: str = "mock", lam: float = 2.0, proj_dim: int = 48, seed: int = 0,
                 model_path: str = "/research/d7/spc/yzyang4/models/Qwen2.5-Coder-7B-Instruct",
                 quant: str = "4bit", model: str = "Qwen/Qwen2.5-Coder-7B-Instruct"):
        self.backend = backend
        self.lam = lam
        self.proj_dim = proj_dim
        self.seed = seed
        self.model_path = model_path
        self.quant = quant
        self.model = model
        self._P = None            # frozen projection (mock "representation")
        self._mu = self._sd = None
        self._ridge = None

    def _frozen_repr(self, cards: List[Card]) -> np.ndarray:
        X = features_matrix(cards)
        Xs = (X - self._mu) / self._sd
        return np.tanh(Xs @ self._P)

    def fit(self, train: List[Card]) -> "ProbeCritic":
        if self.backend == "mock":
            train = [c for c in train if c.y is not None]
            if not train:
                return self
            X = features_matrix(train)
            self._mu = X.mean(0)
            self._sd = X.std(0); self._sd[self._sd < 1e-8] = 1.0
            rng = np.random.default_rng(self.seed)          # FROZEN projection: fixed, not trained
            self._P = rng.normal(0, 1.0, size=(X.shape[1], self.proj_dim)) / np.sqrt(X.shape[1])
            H = self._frozen_repr(train)
            y = np.array([c.y for c in train], float)
            self._ridge = Ridge(self.lam).fit(H, y)
            return self
        return self._fit_qwen(train)

    def predict(self, cards: List[Card]) -> np.ndarray:
        if self.backend == "mock":
            if self._ridge is None:
                return np.zeros(len(cards))
            return self._ridge.predict(self._frozen_repr(cards))
        return self._predict_qwen(cards)

    # -- real backend: frozen Qwen hidden-state + token-entropy features -> ridge probe --
    def _fit_qwen(self, train: List[Card]) -> "ProbeCritic":
        from .qwen_backend import extract_features
        train = [c for c in train if c.y is not None]
        if not train:
            return self
        X = extract_features(train, path=self.model_path, quant=self.quant)
        self._mu = X.mean(0); self._sd = X.std(0); self._sd[self._sd < 1e-8] = 1.0
        y = np.array([c.y for c in train], float)
        self._ridge = Ridge(self.lam).fit((X - self._mu) / self._sd, y)
        return self

    def _predict_qwen(self, cards: List[Card]) -> np.ndarray:
        from .qwen_backend import extract_features
        if self._ridge is None:
            return np.zeros(len(cards))
        X = extract_features(cards, path=self.model_path, quant=self.quant)
        return self._ridge.predict((X - self._mu) / self._sd)
