"""Input construction and pair datasets for Bradley–Terry training."""

from .pairs import CardEncoder, PairDataset, load_training_pool, load_testing_pool, pair_collate, read_cards, read_pairs

__all__ = [
    "CardEncoder",
    "PairDataset",
    "load_training_pool",
    "load_testing_pool",
    "pair_collate",
    "read_cards",
    "read_pairs",
]
