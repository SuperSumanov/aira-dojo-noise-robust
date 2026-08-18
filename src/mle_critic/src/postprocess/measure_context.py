"""Measure token lengths using the Bradley-Terry training data pipeline.

Example from the repository root:

    python -m src.mle_critic.src.postprocess.measure_context \
        --model Qwen/Qwen3-0.6B-Base \
        --pairs data/augmented_mle_critic/batch_value_pairs_filtered_runsplit.jsonl \
        --cards data/augmented_mle_critic/augmented_cards_current.json \
        --context-length 16384

The encoder receives a deliberately large temporary max length so its normal
head/tail truncation does not affect the measurements.
"""
from __future__ import annotations

import argparse
import random
from dataclasses import dataclass
from functools import partial
from pathlib import Path

from torch.utils.data import DataLoader
from transformers import AutoTokenizer

from src.mle_critic.src.train.dataset import (
    CardEncoder,
    PairDataset,
    load_testing_pool,
    load_training_pool,
    pair_collate,
    read_cards,
    read_pairs,
)


PROJECT_ROOT = Path(__file__).resolve().parents[4]
AUGMENTED_DATA_DIR = PROJECT_ROOT / "data" / "augmented_mle_critic"
DEFAULT_PAIRS = AUGMENTED_DATA_DIR / "batch_value_pairs_filtered_runsplit.jsonl"
DEFAULT_CARDS = AUGMENTED_DATA_DIR / "augmented_cards_current.json"


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def fraction(value: str) -> float:
    parsed = float(value)
    if not 0.0 <= parsed <= 1.0:
        raise argparse.ArgumentTypeError("must be between 0 and 1")
    return parsed


@dataclass
class LengthStats:
    """Streaming token-length statistics for model inputs and pairs."""

    pair_count: int = 0
    sequence_count: int = 0
    total_tokens: int = 0
    max_tokens: int = 0
    over_context_sequences: int = 0
    over_context_pairs: int = 0

    def update(self, lengths: list[int], context_length: int) -> None:
        if len(lengths) % 2:
            raise ValueError("pair_collate returned an odd number of sequences")

        pair_count = len(lengths) // 2
        better_lengths = lengths[:pair_count]
        worse_lengths = lengths[pair_count:]

        self.pair_count += pair_count
        self.sequence_count += len(lengths)
        self.total_tokens += sum(lengths)
        self.max_tokens = max(self.max_tokens, max(lengths, default=0))
        self.over_context_sequences += sum(
            length > context_length for length in lengths
        )
        self.over_context_pairs += sum(
            better > context_length or worse > context_length
            for better, worse in zip(better_lengths, worse_lengths)
        )

    def merge(self, other: "LengthStats") -> None:
        self.pair_count += other.pair_count
        self.sequence_count += other.sequence_count
        self.total_tokens += other.total_tokens
        self.max_tokens = max(self.max_tokens, other.max_tokens)
        self.over_context_sequences += other.over_context_sequences
        self.over_context_pairs += other.over_context_pairs


def measure_dataset(
    dataset: PairDataset,
    *,
    pad_token_id: int,
    context_length: int,
    batch_size: int,
    num_workers: int,
) -> LengthStats:
    """Traverse one PairDataset through the training collator."""
    loader = DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        collate_fn=partial(pair_collate, pad_token_id=pad_token_id),
    )
    stats = LengthStats()
    for batch in loader:
        lengths = batch["attention_mask"].sum(dim=1).tolist()
        stats.update(lengths, context_length)
    return stats


def print_stats(name: str, stats: LengthStats) -> None:
    average = (
        stats.total_tokens / stats.sequence_count if stats.sequence_count else 0.0
    )
    sequence_over_ratio = (
        stats.over_context_sequences / stats.sequence_count
        if stats.sequence_count
        else 0.0
    )
    pair_over_ratio = (
        stats.over_context_pairs / stats.pair_count if stats.pair_count else 0.0
    )
    print(
        f"[measure_context] {name}: pairs={stats.pair_count} "
        f"sequences={stats.sequence_count} avg_tokens={average:.2f} "
        f"max_tokens={stats.max_tokens} "
        f"sequences_over_context={stats.over_context_sequences}/"
        f"{stats.sequence_count} ({sequence_over_ratio:.2%}) "
        f"pairs_over_context={stats.over_context_pairs}/{stats.pair_count} "
        f"({pair_over_ratio:.2%})",
        flush=True,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="Qwen/Qwen3-0.6B-Base")
    parser.add_argument("--pairs", type=Path, default=DEFAULT_PAIRS)
    parser.add_argument("--cards", type=Path, default=DEFAULT_CARDS)
    parser.add_argument("--context-length", type=positive_int, default=16_384)
    parser.add_argument(
        "--measurement-max-len",
        type=positive_int,
        default=10_000_000,
        help="temporary CardEncoder max_len; must exceed every real input length",
    )
    parser.add_argument("--batch-size", type=positive_int, default=1)
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--loto", default="")
    parser.add_argument("--head-frac", type=fraction, default=0.25)
    parser.add_argument(
        "--task-cond",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="prepend the MLE-bench task name, as in training",
    )
    parser.add_argument("--budget-cond", action="store_true")
    parser.add_argument("--budget-pos", choices=("head", "tail"), default="head")
    arguments = parser.parse_args()
    if arguments.num_workers < 0:
        parser.error("--num-workers must be non-negative")
    if arguments.measurement_max_len <= arguments.context_length:
        parser.error("--measurement-max-len must be greater than --context-length")
    return arguments


def main() -> None:
    arguments = parse_args()

    card_codes, card_tasks = read_cards(str(arguments.cards))
    pair_records = read_pairs(str(arguments.pairs), card_codes)
    training_pool, split_name = load_training_pool(
        pair_records,
        loto=arguments.loto,
        seed=arguments.seed,
    )
    testing_pool, _ = load_testing_pool(
        pair_records,
        loto=arguments.loto,
        seed=arguments.seed,
    )

    # Match the additional shuffles in bradley_terry.py. They do not affect the
    # aggregate statistics, but keep traversal behavior aligned with training.
    rng = random.Random(arguments.seed)
    rng.shuffle(training_pool)
    rng.shuffle(testing_pool)

    print(
        f"[measure_context] split={split_name} input_pairs={len(pair_records)} "
        f"train={len(training_pool)} test={len(testing_pool)} "
        f"context_length={arguments.context_length}",
        flush=True,
    )

    tokenizer = AutoTokenizer.from_pretrained(arguments.model)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    if tokenizer.pad_token_id is None:
        raise ValueError(f"Tokenizer for {arguments.model!r} has no pad or EOS token")
    tokenizer.padding_side = "right"
    tokenizer.model_max_length = arguments.measurement_max_len

    card_encoder = CardEncoder(
        code=card_codes,
        tasks=card_tasks,
        tokenizer=tokenizer,
        max_len=arguments.measurement_max_len,
        head_frac=arguments.head_frac,
        task_cond=arguments.task_cond,
        budget_cond=arguments.budget_cond,
        budget_pos=arguments.budget_pos,
    )
    datasets = {
        "train": PairDataset(training_pool, card_encoder),
        "test": PairDataset(testing_pool, card_encoder),
    }

    combined_stats = LengthStats()
    for split, dataset in datasets.items():
        stats = measure_dataset(
            dataset,
            pad_token_id=tokenizer.pad_token_id,
            context_length=arguments.context_length,
            batch_size=arguments.batch_size,
            num_workers=arguments.num_workers,
        )
        print_stats(split, stats)
        combined_stats.merge(stats)
    print_stats("all", combined_stats)

    if combined_stats.max_tokens >= arguments.measurement_max_len:
        raise RuntimeError(
            "At least one input reached --measurement-max-len, so CardEncoder "
            "may have truncated it. Rerun with a larger measurement limit."
        )


if __name__ == "__main__":
    main()
