"""Critic interface + a tiny closed-form ridge (no sklearn) shared by the *mock* backends.

Every predictor (4 critics + 2 baselines) implements:
    fit(train_cards: List[Card]) -> self        # baselines/zeroshot may ignore the labels
    predict(cards: List[Card])  -> np.ndarray    # one scalar per card, higher = better candidate

Scores only need to be ORDER-consistent with y_norm for ranking metrics; the scalar/reasoning/probe
critics additionally aim to be calibrated to y_norm in [0,1] (so ECE is meaningful).

Backends: `backend="mock"` uses the pure-numpy paths here (CPU, seconds) and is what the Phase-1a
smoke exercises. `backend="qwen"` is the real Qwen2.5-Coder path, imported lazily inside each critic
so the smoke never needs torch/transformers (see each critic file; step-2 work).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

import numpy as np

from ..cards import Card


def orient(x: np.ndarray, higher_is_better: bool) -> np.ndarray:
    """Flip a raw self-reported metric so that larger always means a better candidate."""
    return np.asarray(x, float) if higher_is_better else -np.asarray(x, float)


class Ridge:
    """Standardized closed-form ridge with intercept. Deterministic; no external deps."""

    def __init__(self, lam: float = 1.0):
        self.lam = lam
        self.mu = self.sd = self.w = None
        self.b = 0.0

    def fit(self, X: np.ndarray, y: np.ndarray) -> "Ridge":
        X = np.asarray(X, float); y = np.asarray(y, float)
        self.mu = X.mean(0)
        self.sd = X.std(0)
        self.sd[self.sd < 1e-8] = 1.0
        Xs = (X - self.mu) / self.sd
        n, d = Xs.shape
        A = Xs.T @ Xs + self.lam * np.eye(d)
        self.w = np.linalg.solve(A, Xs.T @ (y - y.mean()))
        self.b = float(y.mean())
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        Xs = (np.asarray(X, float) - self.mu) / self.sd
        return Xs @ self.w + self.b


class Critic(ABC):
    name: str = "critic"
    #: does this predictor consume training labels? (baselines/zeroshot = False -> flat in budget N)
    uses_labels: bool = True

    @abstractmethod
    def fit(self, train: List[Card]) -> "Critic":
        ...

    @abstractmethod
    def predict(self, cards: List[Card]) -> np.ndarray:
        ...
