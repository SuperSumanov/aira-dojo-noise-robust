"""Create pairwise RL-judger messages from cards and labeled pairs.

Each output record has the chat ``message`` (system and user messages) and the
correct ``solution`` (``A`` or ``B``). Code is copied verbatim from the card;
there is deliberately no tokenizer-length truncation or conditioning.
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[5]
AUGMENTED_DATA_DIR = PROJECT_ROOT / "data" / "augmented_mle_critic"
DEFAULT_PAIRS = AUGMENTED_DATA_DIR / "decision_global_local_value_mixed_filtered_pairs_runsplit.jsonl"
DEFAULT_CARDS = AUGMENTED_DATA_DIR / "augmented_cards_current.json"
DEFAULT_PROMPTS = AUGMENTED_DATA_DIR / "rl_judger_system_prompts.json"
DEFAULT_TRAIN_OUTPUT = AUGMENTED_DATA_DIR / "rl_judger_messages_train.jsonl"
DEFAULT_TEST_OUTPUT = AUGMENTED_DATA_DIR / "rl_judger_messages_test.jsonl"

FINAL_INSTRUCTION = (
    "now please reasoning step by step and output your final decision in \\boxed{A} or \\boxed{B}"
)


def read_cards(path: str) -> dict[str, dict[str, Any]]:
    """Build a card-id-to-card index, matching the training data layout."""
    with open(path, encoding="utf-8") as file:
        cards_by_run_id = json.load(file)
    if not isinstance(cards_by_run_id, dict):
        raise ValueError(f"Expected a JSON object mapping run IDs to Card lists: {path}")
    cards_by_id: dict[str, dict[str, Any]] = {}
    for run_id, cards in cards_by_run_id.items():
        if not isinstance(cards, list):
            raise ValueError(f"Cards for run {run_id!r} are not a list")
        for card in cards:
            card_id = card["id"]
            if card_id in cards_by_id:
                raise ValueError(f"Duplicate Card ID {card_id!r}")
            cards_by_id[card_id] = card
    return cards_by_id


def read_pairs(path: str, cards_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Read JSONL pairs, retaining pairs whose card IDs are both available."""
    pairs = []
    with open(path, encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue
            pair = json.loads(line)
            if pair["better"] in cards_by_id and pair["worse"] in cards_by_id:
                pairs.append(pair)
    return pairs


def build_messages(
    pairs_path: Path = DEFAULT_PAIRS,
    cards_path: Path = DEFAULT_CARDS,
    prompts_path: Path = DEFAULT_PROMPTS,
    train_output_path: Path = DEFAULT_TRAIN_OUTPUT,
    test_output_path: Path = DEFAULT_TEST_OUTPUT,
    *,
    seed: int = 7,
) -> int:
    """Write one randomly A/B-oriented judger example per train/test pair."""
    with prompts_path.open(encoding="utf-8") as file:
        prompts = json.load(file)
    if not isinstance(prompts, dict):
        raise ValueError(f"Expected task-to-prompt mapping in {prompts_path}")

    cards_by_id = read_cards(str(cards_path))
    pairs = read_pairs(str(pairs_path), cards_by_id)
    rng = random.Random(seed)
    train_output_path.parent.mkdir(parents=True, exist_ok=True)
    test_output_path.parent.mkdir(parents=True, exist_ok=True)

    written = {"train": 0, "test": 0}
    with (
        train_output_path.open("w", encoding="utf-8") as train_file,
        test_output_path.open("w", encoding="utf-8") as test_file,
    ):
        for pair in pairs:
            split = pair.get("intask_split")
            if split not in written:
                continue
            task_name = pair["task"]
            try:
                system_prompt = prompts[task_name]
                better_code = cards_by_id[pair["better"]]["code"]
                worse_code = cards_by_id[pair["worse"]]["code"]
            except KeyError as error:
                raise ValueError(f"Missing task/card data for pair {pair!r}") from error
            if not isinstance(system_prompt, str):
                raise ValueError(f"Prompt for task {task_name!r} is not a string")

            better_position = rng.choice(("A", "B"))
            if better_position == "A":
                submission_a, submission_b = better_code, worse_code
            else:
                submission_a, submission_b = worse_code, better_code
            user_prompt = (
                "Submission A:\n"
                f"{submission_a}\n\n"
                "Submission B:\n"
                f"{submission_b}\n\n"
                f"{FINAL_INSTRUCTION}"
            )
            record: dict[str, Any] = {
                "message": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "solution": better_position,
            }
            output_file = train_file if split == "train" else test_file
            output_file.write(json.dumps(record, ensure_ascii=False) + "\n")
            written[split] += 1
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pairs", type=Path, default=DEFAULT_PAIRS)
    parser.add_argument("--cards", type=Path, default=DEFAULT_CARDS)
    parser.add_argument("--prompts", type=Path, default=DEFAULT_PROMPTS)
    parser.add_argument("--train-output", type=Path, default=DEFAULT_TRAIN_OUTPUT)
    parser.add_argument("--test-output", type=Path, default=DEFAULT_TEST_OUTPUT)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    counts = build_messages(
        args.pairs,
        args.cards,
        args.prompts,
        args.train_output,
        args.test_output,
        seed=args.seed,
    )
    print(
        f"[build_judger_messages] wrote train={counts['train']} -> {args.train_output}; "
        f"test={counts['test']} -> {args.test_output}"
    )


if __name__ == "__main__":
    main()
