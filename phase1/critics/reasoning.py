"""Critic (c): REASONING-first value critic — the hypothesis under test. Same base as (b)
(Qwen2.5-Coder-7B) so any difference is attributable to the *reasoning-then-value* format, not the
backbone.

Real backend (step 2): QLoRA SFT so the model emits a short natural-language ANALYSIS of the card
(what the code does, whether the cheap signal is trustworthy, lineage cues) and THEN a final line
`predicted_final_score: x.xx`. Prediction = ONE forward pass; parse the number (no multi-sample
voting — hard constraint). Training targets come from HINDSIGHT DISTILLATION: a frozen 14B writes the
analysis for a card whose TRUE graded score is known, with the number stripped from its text, and the
真值 y_norm is appended as the supervised target — so the model learns to reason toward the real label,
not to imitate the teacher's guess. The research claim: under FEW + EXPENSIVE labels, forcing explicit
reasoning is more sample-efficient / better-calibrated than a bare scalar head.

Mock backend: RESIDUAL ridge. It first anchors on the cheap signal (prior = val_at_low, the
"analysis reads the obvious number") and then learns only the CORRECTION from features (the op/depth
structure the number misses). A lower-variance regression target converges in fewer labels -> in the
smoke this arm tends to lead at small N and the harness can DETECT that. It is a stand-in inductive
bias for the smoke, NOT evidence about the real model.
"""
from __future__ import annotations

from typing import List

import numpy as np

from ..cards import Card, features_matrix
from .base import Critic, Ridge, orient


class ReasoningCritic(Critic):
    name = "reasoning"
    uses_labels = True

    def __init__(self, backend: str = "mock", lam: float = 5.0,
                 model_path: str = "/research/d7/spc/yzyang4/models/Qwen2.5-Coder-7B-Instruct",
                 quant: str = "4bit", model: str = "Qwen/Qwen2.5-Coder-7B-Instruct",
                 teacher_path: str = "/research/d7/spc/yzyang4/models/Qwen2.5-Coder-14B-Instruct"):
        self.backend = backend
        self.lam = lam
        self.model_path = model_path
        self.quant = quant
        self.model = model
        self.teacher_path = teacher_path   # 14B teacher for hindsight distillation (stronger analysis than 7B self-distill)
        self._trainer = None
        self._ridge = None

    @staticmethod
    def _prior(cards: List[Card]) -> np.ndarray:
        hib = cards[0].task.higher_is_better if cards else True
        raw = np.array([(c.obs.val_at_low if c.obs.val_at_low is not None else 0.5) for c in cards])
        return np.clip(orient(raw, hib), 0.0, 1.0)

    def fit(self, train: List[Card]) -> "ReasoningCritic":
        if self.backend == "mock":
            train = [c for c in train if c.y is not None]
            if train:
                X = features_matrix(train)
                resid = np.array([c.y for c in train], float) - self._prior(train)
                self._ridge = Ridge(self.lam).fit(X, resid)
            return self
        return self._fit_qwen(train)

    def predict(self, cards: List[Card]) -> np.ndarray:
        if self.backend == "mock":
            prior = self._prior(cards)
            if self._ridge is None:
                return prior
            return prior + self._ridge.predict(features_matrix(cards))
        return self._predict_qwen(cards)

    # -- real backend: QLoRA SFT, hindsight distillation (see qwen_train.ReasoningTrainer) --
    def _fit_qwen(self, train: List[Card]) -> "ReasoningCritic":
        from .qwen_train import ReasoningTrainer
        train = [c for c in train if c.y is not None]
        if not train:
            return self
        self._trainer = ReasoningTrainer(self.model_path, teacher_path=self.teacher_path).fit(train)
        return self

    def _predict_qwen(self, cards: List[Card]) -> np.ndarray:
        if self._trainer is None:
            return np.full(len(cards), 0.5)
        return self._trainer.predict(cards)
