"""Load card code/metadata and run-clean pair splits."""

from __future__ import annotations

import json
import random
from collections.abc import Iterable
from pathlib import Path
from typing import Any


Card = dict[str, Any]
Pair = dict[str, Any]


def read_pair_splits(
    path: str | Path,
    *,
    seed: int = 7,
    train_cap: int | None = 24_000,
    test_cap: int | None = 6_000,
    loto: str = ""
) -> tuple[list[Pair], list[Pair]]:
    """Read, deterministically shuffle, and cap the in-task train/test splits."""
    train: list[Pair] = []
    test: list[Pair] = []
    with Path(path).open(encoding="utf-8") as input_file:
        for line_number, line in enumerate(input_file, start=1):
            if not line.strip():
                continue
            pair = json.loads(line)
            split = pair.get("intask_split")
            if loto:
                if pair.get("loto_fold") != loto:
                    train.append(pair)
                elif pair.get("loto_fold") == loto:
                    test.append(pair)
            else:
                if split == "train":
                    train.append(pair)
                elif split == "test":
                    test.append(pair)
                else:
                    raise ValueError(
                        f"Unsupported intask_split={split!r} at {path}:{line_number}"
                    )

    rng = random.Random(seed)
    rng.shuffle(train)
    rng.shuffle(test)
    if train_cap is not None:
        train = train[:train_cap]
    if test_cap is not None:
        test = test[:test_cap]
    return train, test


def required_card_ids(*pair_groups: Iterable[Pair]) -> set[str]:
    """Return all endpoint IDs referenced by one or more pair collections."""
    return {
        card_id
        for pairs in pair_groups
        for pair in pairs
        for card_id in (pair["better"], pair["worse"])
    }


def _validate_and_add(cards: dict[str, Card], card: Any, needed: set[str]) -> None:
    if not isinstance(card, dict):
        raise ValueError("Card input contains a non-object record")
    card_id = card.get("id")
    if card_id not in needed:
        return
    if card_id in cards:
        raise ValueError(f"Duplicate relevant card ID: {card_id!r}")
    if not isinstance(card.get("code"), str):
        raise ValueError(f"Card {card_id!r} has a non-string code field")
    cards[card_id] = card


def read_cards(path: str | Path, needed: set[str]) -> dict[str, Card]:
    """Load relevant cards from flat JSONL or a run-ID-to-card-list JSON object."""
    path = Path(path)
    cards: dict[str, Card] = {}

    try:
        with path.open(encoding="utf-8") as input_file:
            cards_by_run_id = json.load(input_file)
            for run_cards in cards_by_run_id.values():
                if not isinstance(run_cards, list):
                    raise ValueError("Grouped card JSON values must be card lists")
                for card in run_cards:
                    _validate_and_add(cards, card, needed)
    except json.JSONDecodeError:
        with path.open(encoding="utf-8") as input_file:
            for line in input_file:
                if line.strip():
                    _validate_and_add(cards, json.loads(line), needed)

    missing = needed - cards.keys()
    if missing:
        examples = ", ".join(sorted(missing)[:5])
        raise ValueError(f"Cards file is missing {len(missing)} pair endpoints: {examples}")
    return cards
