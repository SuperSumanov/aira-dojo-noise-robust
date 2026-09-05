"""Evaluate a generative A/B MLE solution judger with vLLM.

Each JSONL record must contain a chat ``message`` list and the gold
``solution`` (``A`` or ``B``).  The checkpoint is expected to be a complete
Hugging Face checkpoint, including the tokenizer/chat template.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


BOXED_ANSWER = re.compile(r"\\boxed\s*\{\s*([AB])\s*\}", re.IGNORECASE)


def extract_answer(text: str) -> str | None:
    """Return the last boxed A/B answer, or None for an unparsable output."""
    matches = BOXED_ANSWER.findall(text)
    return matches[-1].upper() if matches else None


def _candidate_logprob(candidate: Any) -> float:
    """Sum token logprobs when available; otherwise return a neutral score."""
    logprobs = getattr(candidate, "logprobs", None)
    if not logprobs:
        return 0.0
    total = 0.0
    found = False
    for token_info in logprobs:
        # vLLM versions expose either a Logprob object or a one-entry dict
        # mapping token id/string to Logprob at each generated position.
        values = token_info.values() if isinstance(token_info, dict) else (token_info,)
        for item in values:
            value = getattr(item, "logprob", None)
            if value is None and isinstance(item, dict):
                value = item.get("logprob")
            if value is not None:
                total += float(value)
                found = True
                break
    return total if found else 0.0


def evaluate(
    checkpoint: str,
    messages_path: str,
    temperature: float,
    votes: int,
    *,
    max_tokens: int = 1024,
) -> dict[str, Any]:
    if votes < 1:
        raise ValueError("votes must be positive")
    if temperature < 0:
        raise ValueError("temperature must be non-negative")

    from vllm import LLM, SamplingParams

    with open(messages_path) as f:
        records = [json.loads(line) for line in f]
    llm = LLM(model=checkpoint)
    tokenizer = llm.get_tokenizer()
    prompts = [
        tokenizer.apply_chat_template(
            record["message"], tokenize=False, add_generation_prompt=True
        )
        for record in records
    ]
    sampling = SamplingParams(
        temperature=temperature,
        n=votes,
        max_tokens=max_tokens,
        # Needed only for tie-breaking; harmless when the installed vLLM does
        # not expose per-token logprobs on the returned objects.
        logprobs=1,
    )
    outputs = llm.generate(prompts, sampling)

    correct = 0
    parsed = 0
    predictions: list[dict[str, Any]] = []
    task_stats: dict[str, dict[str, int]] = defaultdict(
        lambda: {"total": 0, "correct": 0, "parsed": 0, "parsed_correct": 0}
    )
    for record, request_output in zip(records, outputs):
        candidates = list(request_output.outputs)
        by_answer: dict[str, list[float]] = defaultdict(list)
        raw_answers = []
        for candidate in candidates:
            answer = extract_answer(candidate.text)
            raw_answers.append(answer)
            if answer in ("A", "B"):
                by_answer[answer].append(_candidate_logprob(candidate))

        if by_answer:
            counts = Counter({answer: len(scores) for answer, scores in by_answer.items()})
            # Majority vote first. For a tie, choose the answer with the larger
            # summed candidate probability (equivalently, logprob sum here).
            best_count = max(counts.values())
            tied = [answer for answer, count in counts.items() if count == best_count]
            prediction = max(tied, key=lambda answer: sum(by_answer[answer]))
            parsed += 1
        else:
            prediction = None

        gold = str(record.get("solution", "")).strip().upper()
        hit = prediction == gold
        correct += int(hit)
        task = str(record.get("task", ""))
        stats = task_stats[task]
        stats["total"] += 1
        stats["correct"] += int(hit)
        stats["parsed"] += int(prediction is not None)
        stats["parsed_correct"] += int(prediction is not None and hit)
        predictions.append(
            {
                "task": task,
                "prediction": prediction,
                "gold": gold,
                "correct": hit,
                "answers": raw_answers,
            }
        )

    by_task = {
        task: {
            **stats,
            "accuracy": stats["correct"] / stats["total"] if stats["total"] else 0.0,
            "parsed_accuracy": (
                stats["parsed_correct"] / stats["parsed"] if stats["parsed"] else 0.0
            ),
        }
        for task, stats in sorted(task_stats.items())
    }

    return {
        "checkpoint": checkpoint,
        "messages": messages_path,
        "temperature": temperature,
        "votes": votes,
        "n_examples": len(records),
        "n_parsed": parsed,
        "accuracy": correct / len(records) if records else 0.0,
        "parsed_accuracy": (
            sum(item["correct"] for item in predictions if item["prediction"] is not None) / parsed
            if parsed
            else 0.0
        ),
        "by_task": by_task,
        "predictions": predictions,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--messages", required=True, help="test JSONL containing message and solution")
    parser.add_argument("--temperature", required=True, type=float)
    parser.add_argument("--m", type=int, default=1, help="number of generations per example")
    parser.add_argument("--max-tokens", type=int, default=16384)
    parser.add_argument("--output", default="", help="optional JSON output path")
    args = parser.parse_args()
    result = evaluate(
        args.checkpoint,
        args.messages,
        args.temperature,
        args.m,
        max_tokens=args.max_tokens,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
