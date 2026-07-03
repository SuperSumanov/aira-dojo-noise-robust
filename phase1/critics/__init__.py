"""Predictor registry. Six predictors: 4 critics (a-d) + 2 label-free baselines.

    build(name, backend="mock", **kw) -> Critic
    ALL_PREDICTORS = ordered names for the eval sweep.
"""
from __future__ import annotations

from .base import Critic
from .baselines import AshaBaseline, OneEpochBaseline
from .probe import ProbeCritic
from .reasoning import ReasoningCritic
from .scalar import ScalarCritic
from .zeroshot import ZeroShotCritic

_REGISTRY = {
    "one_epoch": OneEpochBaseline,
    "asha": AshaBaseline,
    "zeroshot": ZeroShotCritic,
    "scalar": ScalarCritic,
    "reasoning": ReasoningCritic,
    "probe": ProbeCritic,
}

# baselines first, then the four critics (b/c share the 7B base; a is frozen 14B; d is a frozen probe)
ALL_PREDICTORS = ["one_epoch", "asha", "zeroshot", "scalar", "reasoning", "probe"]


def build(name: str, backend: str = "mock", **kw) -> Critic:
    if name not in _REGISTRY:
        raise KeyError(f"unknown predictor {name!r}; known = {list(_REGISTRY)}")
    cls = _REGISTRY[name]
    # baselines take no backend/model kwargs
    if name in ("one_epoch", "asha"):
        return cls()
    return cls(backend=backend, **kw)


__all__ = ["Critic", "build", "ALL_PREDICTORS"]
