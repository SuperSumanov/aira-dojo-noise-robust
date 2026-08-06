"""Standalone evaluation helpers for the pairwise reward model."""

from __future__ import annotations

import collections
import json
from collections.abc import Callable, Iterable, Sequence
from typing import Any

import numpy as np
import torch

EncodeCard = Callable[[str, int | None], list[int]]


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
