"""Cards -> critic-ready splits.

Split protocol:
  * leave-one-task-out (LOTO): each task is the held-out test set once; train = all OTHER tasks.
    This measures generalization to an UNSEEN task (the realistic deployment for a value critic).
  * label-budget sub-sampling: from the train pool, keep only N labels, N in {25,50,100,200,all},
    seeded -> the sample-efficiency axis.
Per-task label normalization is handled upstream (y_norm via medal thresholds in cards.py); mock/
tabular critics additionally get a task-one-hot so a linear model learns per-task offsets.
Only cards WITH a label are usable (need y for fit + eval).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterator, List, Optional

import numpy as np

from .cards import Card

DEFAULT_BUDGETS = [25, 50, 100, 200, "all"]


def labeled(cards: List[Card]) -> List[Card]:
    return [c for c in cards if c.y is not None]


def tasks_of(cards: List[Card]) -> List[str]:
    seen = []
    for c in cards:
        if c.task.name not in seen:
            seen.append(c.task.name)
    return seen


def loto_folds(cards: List[Card]):
    """Yield (test_task, train_cards, test_cards) for each leave-one-task-out fold."""
    cards = labeled(cards)
    for t in tasks_of(cards):
        train = [c for c in cards if c.task.name != t]
        test = [c for c in cards if c.task.name == t]
        if train and test:
            yield t, train, test


def subsample(train: List[Card], n, seed: int) -> List[Card]:
    if n == "all" or n is None or n >= len(train):
        return list(train)
    rng = np.random.default_rng(seed)
    idx = rng.choice(len(train), size=int(n), replace=False)
    return [train[i] for i in idx]


@dataclass
class Split:
    task: str          # held-out test task (LOTO fold id)
    budget: object     # N (int) or "all"
    seed: int
    train: List[Card]
    test: List[Card]


def make_splits(cards: List[Card], budgets=None, seeds=(0, 1, 2)) -> Iterator[Split]:
    """Cartesian product LOTO-fold x budget x seed -> Split (train subsampled to the budget)."""
    budgets = budgets or DEFAULT_BUDGETS
    for task, train, test in loto_folds(cards):
        for n in budgets:
            for seed in seeds:
                yield Split(task=task, budget=n, seed=seed, train=subsample(train, n, seed), test=test)
