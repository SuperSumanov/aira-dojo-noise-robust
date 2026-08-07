"""Standalone evaluation helpers for the pairwise reward model."""

from __future__ import annotations

import collections
import argparse
import json
import random
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import torch

EncodeCard = Callable[[str, int | None], list[int]]


class _RewardModel(torch.nn.Module):
    """Backbone plus the scalar head used by bradley_terry.py."""

    def __init__(self, backbone):
        super().__init__()
        self.backbone = backbone
        self.head = torch.nn.Linear(backbone.config.hidden_size, 1)

    def forward(self, input_ids=None, attention_mask=None, **kwargs):
        hidden = self.backbone(input_ids=input_ids, attention_mask=attention_mask).last_hidden_state
        indices = attention_mask.sum(1) - 1
        pooled = hidden[torch.arange(hidden.size(0), device=hidden.device), indices]
        return {"logits": self.head(pooled).squeeze(-1).float()}


def load_checkpoint(checkpoint: str, *, base_model: str | None = None):
    """Load a full-FT Trainer checkpoint or full backbone plus linear head."""
    from safetensors.torch import load_file
    from transformers import AutoModel, AutoTokenizer

    checkpoint_path = Path(checkpoint)
    weights_path = checkpoint_path / "model.safetensors"
    if not weights_path.is_file():
        raise FileNotFoundError(f"expected full backbone weights at {weights_path}")
    meta_path = checkpoint_path / "rm_meta.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    base_name = meta.get("base_model") or base_model
    if not base_name:
        raise ValueError("checkpoint has no rm_meta.json; pass --base-model")
    tokenizer = AutoTokenizer.from_pretrained(base_name)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32
    head_path = checkpoint_path / "head.pt"
    if head_path.is_file():
        # Full-FT export: model.safetensors is a normal HF backbone and head.pt
        # contains only the learned scalar projection. No adapter is involved.
        backbone = AutoModel.from_pretrained(str(checkpoint_path), torch_dtype=dtype)
        model = _RewardModel(backbone)
        model.head.to(dtype=dtype)
        try:
            head_state = torch.load(head_path, map_location="cpu", weights_only=True)
        except TypeError:
            head_state = torch.load(head_path, map_location="cpu")
        model.head.load_state_dict(head_state, strict=True)
    else:
        # Raw Trainer checkpoint: one state dict contains both backbone.* and head.*.
        state = load_file(str(weights_path), device="cpu")
        if "head.weight" not in state or not any(key.startswith("backbone.") for key in state):
            raise ValueError(
                "checkpoint must either include head.pt or contain backbone.* and head.* in model.safetensors"
            )
        backbone = AutoModel.from_pretrained(base_name, torch_dtype=dtype)
        model = _RewardModel(backbone)
        model.head.to(dtype=dtype)
        model.load_state_dict(state, strict=True)
    model.eval()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    return model.to(device), tokenizer, meta


def _make_encoder(cards_path: str, tokenizer, meta: dict[str, Any]):
    cards = {}
    tasks = {}
    for line in open(cards_path):
        card = json.loads(line)
        cards[card["id"]] = card.get("code") or ""
        tasks[card["id"]] = (card.get("task") or {}).get("name", "")
    max_len = int(meta.get("max_len", 8192))
    head_frac = float(meta.get("head_frac", 0.25))
    task_cond = bool(meta.get("task_cond", True))
    budget_cond = bool(meta.get("budget_cond", False))
    budget_pos = meta.get("budget_pos", "head")

    def budget_line(budget):
        return "# remaining budget: unlimited\n" if budget == 0 else f"# remaining budget: {budget} steps\n"

    def encode(card_id, budget=None):
        conditioned = budget if budget_cond else None
        prefix = f"# MLE-bench task: {tasks.get(card_id, '')}\n" if task_cond else ""
        suffix = None
        if conditioned is not None and budget_pos == "tail":
            suffix = tokenizer("\n" + budget_line(conditioned), add_special_tokens=False)["input_ids"]
        elif conditioned is not None:
            prefix += budget_line(conditioned)
        ids = tokenizer(prefix + cards[card_id], add_special_tokens=False)["input_ids"]
        room = max_len - len(suffix or [])
        if len(ids) > room:
            head = int(room * head_frac)
            ids = ids[:head] + ids[-(room - head):]
        return ids + (suffix or [])

    return cards, encode


def pair_accuracy_metrics(eval_prediction) -> dict[str, float]:
    """Convert validation score margins into pairwise accuracy."""
    predictions = eval_prediction.predictions
    if isinstance(predictions, tuple):
        predictions = predictions[0]
    margins = np.asarray(predictions).reshape(-1)
    return {"pair_accuracy": float((margins > 0).mean()) if len(margins) else 0.0}


@torch.no_grad()
def _score_sequences(model, sequences: Sequence[list[int]], pad_token_id: int) -> list[float]:
    if not sequences:
        return []
    device = next(model.parameters()).device
    width = max(len(sequence) for sequence in sequences)
    input_ids = torch.tensor(
        [sequence + [pad_token_id] * (width - len(sequence)) for sequence in sequences],
        device=device,
    )
    attention_mask = torch.tensor(
        [[1] * len(sequence) + [0] * (width - len(sequence)) for sequence in sequences],
        device=device,
    )
    return model(input_ids=input_ids, attention_mask=attention_mask)["logits"].tolist()


@torch.no_grad()
def evaluate_pairs(
    model,
    pairs: Sequence[dict[str, Any]],
    batch_size: int,
    encode_card: EncodeCard,
    pad_token_id: int,
    *,
    breakdown: bool = True,
) -> float:
    """Evaluate better-vs-worse pair accuracy after training."""
    model.eval()
    hits: list[bool] = []
    for start in range(0, len(pairs), batch_size):
        chunk = pairs[start : start + batch_size]
        sequences = [encode_card(pair["better"], pair.get("budget")) for pair in chunk]
        sequences += [encode_card(pair["worse"], pair.get("budget")) for pair in chunk]
        logits = _score_sequences(model, sequences, pad_token_id)
        count = len(chunk)
        hits.extend(better > worse for better, worse in zip(logits[:count], logits[count:]))

    if breakdown:
        aggregates = collections.defaultdict(lambda: [0, 0])
        for hit, pair in zip(hits, pairs):
            keys = [pair["task"]]
            if "budget" in pair:
                keys.append("BUDGET=" + str(pair["budget"]))
                if pair.get("flips_vs_b1"):
                    keys.append("FLIPS@B" + str(pair["budget"]))
            for key in keys:
                aggregates[key][0] += int(hit)
                aggregates[key][1] += 1
        for key, (correct, total) in sorted(aggregates.items()):
            print(f"[task-acc] {key[:40]:40s} {correct}/{total} = {correct / max(total, 1):.3f}", flush=True)

    return sum(hits) / max(len(hits), 1)


@torch.no_grad()
def evaluate_budget_flips(
    model,
    path: str,
    batch_size: int,
    encode_card: EncodeCard,
    pad_token_id: int,
    valid_card_ids: Iterable[str],
    *,
    verbose: bool = True,
) -> dict[str, dict[str, Any]]:
    """Evaluate the same card pair under low/high budgets."""
    valid_card_ids = set(valid_card_ids)
    records = [json.loads(line) for line in open(path)]
    records = [record for record in records if record["x"] in valid_card_ids and record["y"] in valid_card_ids]
    if not records:
        return {}

    model.eval()
    wanted = sorted(
        {
            (record[card_key], record[budget_key])
            for record in records
            for card_key in ("x", "y")
            for budget_key in ("budget_lo", "budget_hi")
        }
    )
    scores: dict[tuple[str, int], float] = {}
    for start in range(0, len(wanted), batch_size):
        chunk = wanted[start : start + batch_size]
        values = _score_sequences(
            model,
            [encode_card(card_id, budget) for card_id, budget in chunk],
            pad_token_id,
        )
        scores.update(zip(chunk, values))

    aggregates: dict[str, dict[str, Any]] = {}
    high_budgets = sorted({record["budget_hi"] for record in records})
    for kind in ("flip", "control"):
        for high_budget in high_budgets:
            subset = [
                record
                for record in records
                if record["kind"] == kind and record["budget_hi"] == high_budget
            ]
            if not subset:
                continue
            low_correct = high_correct = switched = switched_correctly = 0
            per_task = collections.defaultdict(lambda: [0, 0])
            for record in subset:
                low_pick = (
                    record["x"]
                    if scores[(record["x"], record["budget_lo"])]
                    > scores[(record["y"], record["budget_lo"])]
                    else record["y"]
                )
                high_pick = (
                    record["x"]
                    if scores[(record["x"], record["budget_hi"])]
                    > scores[(record["y"], record["budget_hi"])]
                    else record["y"]
                )
                low_hit = low_pick == record["better_lo"]
                high_hit = high_pick == record["better_hi"]
                low_correct += low_hit
                high_correct += high_hit
                per_task[record["task"]][0] += low_hit + high_hit
                per_task[record["task"]][1] += 2
                if low_pick != high_pick:
                    switched += 1
                    switched_correctly += low_hit and high_hit

            count = len(subset)
            key = kind + str(high_budget)
            aggregates[key] = {
                "n": count,
                "acc_lo": low_correct / count,
                "acc_hi": high_correct / count,
                "acc_mean": (low_correct + high_correct) / (2 * count),
                "moved": switched / count,
                "n_switch": switched,
                "switch_acc": switched_correctly / switched if switched else None,
            }
            if verbose:
                for task, (correct, total) in sorted(per_task.items()):
                    print(
                        f"[flip-task] {kind} K{high_budget} {task[:40]} "
                        f"{correct}/{total} = {correct / max(total, 1):.3f}",
                        flush=True,
                    )
                print(
                    f"[flip-eval] {kind} K1->K{high_budget} n={count} "
                    f"acc@lo={low_correct / count:.4f} acc@hi={high_correct / count:.4f} "
                    f"mean={(low_correct + high_correct) / (2 * count):.4f} "
                    f"model_switched={switched / count:.4f}"
                    + (f" switch_acc={switched_correctly / switched:.3f} of {switched}" if switched else ""),
                    flush=True,
                )

    for high_budget in high_budgets:
        flip = aggregates.get("flip" + str(high_budget))
        control = aggregates.get("control" + str(high_budget))
        if flip and control and control["moved"] > 0:
            selectivity = flip["moved"] / control["moved"]
            flip["selectivity"] = selectivity
            if verbose:
                print(
                    f"[flip-sel] K1->K{high_budget} switches on flip pairs vs controls: "
                    f"{flip['n_switch']} vs {control['n_switch']} = {selectivity:.2f}x",
                    flush=True,
                )
    return aggregates


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate any Hugging Face reward-model checkpoint.")
    parser.add_argument("--checkpoint", required=True,
                        help="full-FT Trainer checkpoint or full HF backbone plus head.pt")
    parser.add_argument("--base-model", help="base model for a raw checkpoint without rm_meta.json")
    parser.add_argument("--pairs", required=True, help="pair JSONL used for evaluation")
    parser.add_argument("--cards", required=True, help="cards JSONL used to render model inputs")
    parser.add_argument("--split", choices=("all", "train", "test"), default="test")
    parser.add_argument("--eval-cap", type=int, default=0, help="maximum pairs; 0 means all")
    parser.add_argument("--seed", type=int, default=7, help="pair shuffle seed")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--flip-eval", default="", help="optional budget flip/control JSONL")
    parser.add_argument("--eval-len-control", type=float, default=0.0)
    parser.add_argument("--max-len", type=int, help="override rm_meta.json max_len")
    parser.add_argument("--head-frac", type=float, help="override rm_meta.json head_frac")
    parser.add_argument("--task-cond", action=argparse.BooleanOptionalAction, default=None,
                        help="override task conditioning from rm_meta.json")
    parser.add_argument("--budget-cond", action=argparse.BooleanOptionalAction, default=None,
                        help="override budget conditioning from rm_meta.json")
    parser.add_argument("--budget-pos", choices=("head", "tail"),
                        help="override budget position from rm_meta.json")
    parser.add_argument("--output", default="", help="optional JSON output path")
    args = parser.parse_args()
    if args.batch_size < 1:
        parser.error("--batch-size must be positive")

    model, tokenizer, meta = load_checkpoint(args.checkpoint, base_model=args.base_model)
    for key in ("max_len", "head_frac", "task_cond", "budget_cond", "budget_pos"):
        value = getattr(args, key)
        if value is not None:
            meta[key] = value
    cards, encode_card = _make_encoder(args.cards, tokenizer, meta)
    all_pairs = []
    for line in open(args.pairs):
        pair = json.loads(line)
        if pair["better"] not in cards or pair["worse"] not in cards:
            continue
        all_pairs.append(pair)
    rng = random.Random(args.seed)
    if args.split == "all":
        pairs = all_pairs
        rng.shuffle(pairs)
    else:
        train_pairs = [pair for pair in all_pairs if pair.get("intask_split") == "train"]
        test_pairs = [pair for pair in all_pairs if pair.get("intask_split") == "test"]
        # Match bradley_terry.py: both pools consume the same RNG in this order.
        rng.shuffle(train_pairs)
        rng.shuffle(test_pairs)
        pairs = train_pairs if args.split == "train" else test_pairs
    if args.split == "test":
        seen = set()
        unique_pairs = []
        for pair in pairs:
            key = (pair["better"], pair["worse"], pair.get("budget"))
            if key not in seen:
                seen.add(key)
                unique_pairs.append(pair)
        pairs = unique_pairs
    if args.eval_cap:
        pairs = pairs[:args.eval_cap]
    print(f"[rm-eval] checkpoint={args.checkpoint} split={args.split} n_pairs={len(pairs)}", flush=True)
    result: dict[str, Any] = {
        "checkpoint": args.checkpoint,
        "split": args.split,
        "n_pairs": len(pairs),
        "accuracy": evaluate_pairs(model, pairs, args.batch_size, encode_card, tokenizer.pad_token_id),
    }

    if args.eval_len_control > 0:
        def close_pair(pair):
            left = len(cards[pair["better"]])
            right = len(cards[pair["worse"]])
            width = max(left, right)
            return width > 0 and abs(left - right) / width <= args.eval_len_control
        controlled = [pair for pair in pairs if close_pair(pair)]
        result["length_control"] = {
            "n_pairs": len(controlled),
            "accuracy": evaluate_pairs(model, controlled, args.batch_size, encode_card,
                                        tokenizer.pad_token_id, breakdown=False),
        }

    if args.flip_eval:
        result["budget_flips"] = evaluate_budget_flips(
            model, args.flip_eval, args.batch_size, encode_card, tokenizer.pad_token_id, cards
        )
    print(json.dumps(result, indent=2, sort_keys=True))
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
