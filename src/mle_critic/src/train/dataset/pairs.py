"""Data loading, rendering, tokenization, and collation for RM pair training."""

from __future__ import annotations

import json
import random
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
import torch


def read_cards(path: str) -> tuple[dict[str, str], dict[str, str]]:
    """Read lookup tables from the current ``run_id -> list[Card]`` JSON format."""
    with open(path, encoding="utf-8") as input_file:
        cards_by_run_id = json.load(input_file)
    if not isinstance(cards_by_run_id, dict):
        raise ValueError(
            f"Expected a JSON object mapping run IDs to Card lists: {path}"
        )

    code: dict[str, str] = {}
    tasks: dict[str, str] = {}
    run_id_by_card_id: dict[str, str] = {}
    for run_id, run_cards in cards_by_run_id.items():
        if not isinstance(run_id, str) or not run_id:
            raise ValueError(f"Invalid run ID in {path}: {run_id!r}")
        if not isinstance(run_cards, list):
            raise ValueError(f"Run {run_id!r} does not contain a Card list")

        for card in run_cards:
            if not isinstance(card, dict):
                raise ValueError(f"Run {run_id!r} contains a non-object Card")
            card_id = card["id"]
            if not isinstance(card_id, str) or not card_id:
                raise ValueError(f"Run {run_id!r} contains an invalid Card ID")
            if card_id in code:
                raise ValueError(
                    f"Duplicate Card ID {card_id!r} in runs "
                    f"{run_id_by_card_id[card_id]!r} and {run_id!r}"
                )

            card_code = card["code"]
            task_name = card["task"]["name"]
            if not isinstance(card_code, str):
                raise ValueError(f"Card {card_id!r} has a non-string code field")
            if not isinstance(task_name, str) or not task_name:
                raise ValueError(f"Card {card_id!r} has an invalid task.name field")

            code[card_id] = card_code
            tasks[card_id] = task_name
            run_id_by_card_id[card_id] = run_id
    return code, tasks


def read_pairs(path: str, code: dict[str, str]) -> list[dict[str, Any]]:
    """Read pair records whose two card IDs are present in the cards file."""
    return [
        pair
        for line in open(path)
        for pair in [json.loads(line)]
        if pair["better"] in code and pair["worse"] in code
    ]


def load_training_pool(
    pairs: Sequence[dict[str, Any]],
    *,
    loto: str = "",
    seed: int = 7,
) -> tuple[list[dict[str, Any]], str]:
    """Select and deterministically shuffle the records used for training."""
    if loto:
        pool = [pair for pair in pairs if pair["task"] != loto]
        split_name = "loto:" + loto
    else:
        pool = [pair for pair in pairs if pair["intask_split"] == "train"]
        split_name = "in-task"
    random.Random(seed).shuffle(pool)
    return pool, split_name


def load_testing_pool(
    pairs: Sequence[dict[str, Any]],
    *,
    loto: str = "",
    seed: int = 7,
) -> tuple[list[dict[str, Any]], str]:
    """Select the records used for testing."""
    if loto:
        pool = [pair for pair in pairs if pair["task"] == loto]
        split_name = "loto:" + loto
    else:
        pool = [pair for pair in pairs if pair["intask_split"] == "test"]
        split_name = "in-task"
    random.Random(seed).shuffle(pool)
    return pool, split_name


@dataclass
class CardEncoder:
    """Reproduce bradley_terry.py's task/budget rendering and truncation."""

    code: dict[str, str]
    tasks: dict[str, str]
    tokenizer: Any
    max_len: int = 8192
    head_frac: float = 0.25
    task_cond: bool = True
    budget_cond: bool = False
    budget_pos: str = "head"

    @staticmethod
    def _budget_line(budget: int | None) -> str:
        return (
            "# remaining budget: unlimited\n"
            if budget == 0
            else f"# remaining budget: {budget} steps\n"
        )

    def render(self, card_id: str, budget: int | None = None) -> str:
        prefix = ""
        if self.task_cond:
            prefix += f"# MLE-bench task: {self.tasks.get(card_id, '')}\n"
        if budget is not None and self.budget_pos == "head":
            prefix += self._budget_line(budget)
        return prefix + self.code[card_id]

    def encode(self, card_id: str, budget: int | None = None) -> list[int]:
        conditioned_budget = budget if self.budget_cond else None
        suffix = (
            self.tokenizer(
                "\n" + self._budget_line(conditioned_budget),
                add_special_tokens=False,
            )["input_ids"]
            if conditioned_budget is not None and self.budget_pos == "tail"
            else None
        )
        token_ids = self.tokenizer(
            self.render(card_id, conditioned_budget), add_special_tokens=False
        )["input_ids"]
        room = self.max_len - len(suffix or [])
        if len(token_ids) > room:
            head = int(room * self.head_frac)
            token_ids = token_ids[:head] + token_ids[-(room - head):]
        return token_ids + (suffix or [])

    def __call__(self, card_id: str, budget: int | None = None) -> list[int]:
        return self.encode(card_id, budget)


class PairDataset:
    """Dataset returning tokenized better/worse sequences for one pair."""

    def __init__(self, pairs: Sequence[dict[str, Any]], encoder: CardEncoder):
        self.pairs = pairs
        self.encoder = encoder

    def __len__(self) -> int:
        return len(self.pairs)

    def __getitem__(self, index: int) -> dict[str, list[int]]:
        pair = self.pairs[index]
        return {
            "b": self.encoder(pair["better"], pair.get("budget")),
            "w": self.encoder(pair["worse"], pair.get("budget")),
        }


def pair_collate(batch: Sequence[dict[str, list[int]]], pad_token_id: int) -> dict[str, torch.Tensor]:
    """Pack all better sequences followed by all worse sequences."""

    sequences = [item["b"] for item in batch] + [item["w"] for item in batch]
    width = max(len(sequence) for sequence in sequences)
    input_ids = torch.tensor(
        [sequence + [pad_token_id] * (width - len(sequence)) for sequence in sequences]
    )
    attention_mask = torch.tensor(
        [[1] * len(sequence) + [0] * (width - len(sequence)) for sequence in sequences]
    )
    return {"input_ids": input_ids, "attention_mask": attention_mask}
