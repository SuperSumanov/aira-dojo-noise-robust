"""Reward-model evaluation and serving utilities."""

from importlib import import_module

__all__ = ["evaluate_budget_flips", "evaluate_pairs", "load_checkpoint", "pair_accuracy_metrics"]


def __getattr__(name):
    if name not in __all__:
        raise AttributeError(name)
    return getattr(import_module(".bradley_terry_evaluation", __name__), name)
