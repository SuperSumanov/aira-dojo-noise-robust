"""Two label-free baselines. They ignore the training labels, so their metrics are FLAT in the
label budget N — the floor any learned critic must clear to justify its cost.

  * OneEpochBaseline: "just trust the cheap self-reported number." score = val_at_low (oriented).
    This is the ArchPilot-style 1-epoch / 10%-data proxy — rank candidates by their low-fidelity
    validation as-is.
  * AshaBaseline: learning-curve extrapolation. Projects the val_curve forward (last rung + slope)
    so steadily-improving runs are rewarded over ones that plateaued early — an ASHA/curve-fit proxy.
    Falls back to val_at_low when no curve is recorded.
"""
from __future__ import annotations

from typing import List

import numpy as np

from ..cards import Card
from .base import Critic, orient


class OneEpochBaseline(Critic):
    name = "one_epoch"
    uses_labels = False

    def fit(self, train: List[Card]) -> "OneEpochBaseline":
        return self

    def predict(self, cards: List[Card]) -> np.ndarray:
        raw = np.array([(c.obs.val_at_low if c.obs.val_at_low is not None else 0.0) for c in cards])
        hib = cards[0].task.higher_is_better if cards else True
        return orient(raw, hib)


class AshaBaseline(Critic):
    name = "asha"
    uses_labels = False
    #: how many rungs beyond the observed curve to extrapolate the trend
    horizon: float = 2.0

    def fit(self, train: List[Card]) -> "AshaBaseline":
        return self

    def _extrapolate(self, c: Card) -> float:
        curve = [v for v in (c.obs.val_curve or []) if v is not None]
        if len(curve) >= 2:
            slope = (curve[-1] - curve[0]) / (len(curve) - 1)
            return curve[-1] + slope * self.horizon
        return c.obs.val_at_low if c.obs.val_at_low is not None else 0.0

    def predict(self, cards: List[Card]) -> np.ndarray:
        raw = np.array([self._extrapolate(c) for c in cards])
        hib = cards[0].task.higher_is_better if cards else True
        return orient(raw, hib)
