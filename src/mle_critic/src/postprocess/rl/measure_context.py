"""Measure tokenized context lengths of RL judger chat messages.

Example::

    python -m src.mle_critic.src.postprocess.rl.measure_context \
        --model Qwen/Qwen3-8B \
        --messages data/augmented_mle_critic/rl_judger_messages.jsonl \
        --expected-context-length 32768

The JSONL is processed line by line. Lengths include the system and user
messages, plus the chat-template generation prompt when the tokenizer provides
one. If no chat template exists, the script tokenizes a plain role/content
serialization instead.
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[5]
DEFAULT_MESSAGES = PROJECT_ROOT / "data" / "augmented_mle_critic" / "rl_judger_messages.jsonl"


def _token_count(tokenizer: Any, messages: list[dict[str, Any]]) -> int:
    """Count tokens using the model's chat template, if available."""
    apply_template = getattr(tokenizer, "apply_chat_template", None)
    if callable(apply_template) and getattr(tokenizer, "chat_template", None):
        token_ids = apply_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
        )
        if isinstance(token_ids, dict):
            token_ids = token_ids["input_ids"]
        return len(token_ids)

    # This fallback is deterministic and still accounts for all message text.
    serialized = "\n".join(
        f"<{message.get('role', '')}>\n{message.get('content', '')}"
        for message in messages
    )
    return len(tokenizer(serialized, add_special_tokens=True)["input_ids"])


def _bucket(length: int, expected: int) -> str:
    """Return a useful relative-to-budget context-length bucket."""
    if length <= expected * 0.25:
        return "0-25%"
    if length <= expected * 0.50:
        return "25-50%"
    if length <= expected * 0.75:
        return "50-75%"
    if length <= expected:
        return "75-100%"
    if length <= expected * 1.25:
        return "100-125%"
    return ">125%"


def measure_context(
    model: str,
    messages_path: Path = DEFAULT_MESSAGES,
    expected_context_length: int = 32768,
    *,
    max_context_length: int | None = None,
    filtered_messages_path: Path | None = None,
    trust_remote_code: bool = False,
) -> dict[str, Any]:
    """Measure all records and return JSON-serializable summary statistics."""
    if expected_context_length <= 0:
        raise ValueError("expected_context_length must be positive")
    if max_context_length is not None and max_context_length <= 0:
        raise ValueError("max_context_length must be positive")
    try:
        from transformers import AutoTokenizer
    except ImportError as error:
        raise RuntimeError(
            "transformers is required; run this script in the model/training environment"
        ) from error

    tokenizer = AutoTokenizer.from_pretrained(model, trust_remote_code=trust_remote_code)
    lengths: list[int] = []
    buckets: Counter[str] = Counter()
    malformed = 0
    removed = 0
    temp_path: str | None = None
    filtered_file = None
    if max_context_length is not None:
        if filtered_messages_path is None:
            # In-place filtering is requested; use a sibling temporary file and
            # replace the original only after the complete pass succeeds.
            fd, temp_path = tempfile.mkstemp(
                prefix=f".{messages_path.name}.", suffix=".tmp", dir=messages_path.parent
            )
            filtered_file = os.fdopen(fd, "w", encoding="utf-8")
        else:
            filtered_messages_path.parent.mkdir(parents=True, exist_ok=True)
            filtered_file = filtered_messages_path.open("w", encoding="utf-8")
    with messages_path.open(encoding="utf-8") as input_file:
        for line_number, line in enumerate(input_file, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                messages = record["message"]
                if not isinstance(messages, list):
                    raise TypeError("message is not a list")
                length = _token_count(tokenizer, messages)
            except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
                malformed += 1
                print(f"[measure_context] skipping line {line_number}: {error}")
                continue
            lengths.append(length)
            buckets[_bucket(length, expected_context_length)] += 1
            if filtered_file is not None:
                if length <= max_context_length:
                    filtered_file.write(line)
                else:
                    removed += 1

    if filtered_file is not None:
        filtered_file.close()
        if temp_path is not None:
            os.replace(temp_path, messages_path)

    sample_count = len(lengths)
    over_limit = sum(length > expected_context_length for length in lengths)
    summary: dict[str, Any] = {
        "model": model,
        "messages": str(messages_path),
        "expected_context_length": expected_context_length,
        "sample_count": sample_count,
        "retained_count": sample_count - removed,
        "removed_count": removed,
        "max_context_length": max_context_length,
        "malformed_count": malformed,
        "average_context_length": mean(lengths) if lengths else 0.0,
        "min_context_length": min(lengths) if lengths else 0,
        "maximum_observed_context_length": max(lengths) if lengths else 0,
        "over_expected_count": over_limit,
        "over_expected_fraction": over_limit / sample_count if sample_count else 0.0,
        "buckets": {
            label: {
                "count": buckets[label],
                "fraction": buckets[label] / sample_count if sample_count else 0.0,
            }
            for label in ("0-25%", "25-50%", "50-75%", "75-100%", "100-125%", ">125%")
        },
    }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, help="Hugging Face model/tokenizer name or path")
    parser.add_argument("--messages", type=Path, default=DEFAULT_MESSAGES)
    parser.add_argument(
        "--expected-context-length",
        type=int,
        required=True,
        help="Context length to use as the expected limit",
    )
    parser.add_argument(
        "--max-context-length",
        type=int,
        help=(
            "Drop records longer than this limit after measuring. Without "
            "--filtered-messages, the input JSONL is rewritten in place."
        ),
    )
    parser.add_argument("--trust-remote-code", action="store_true")
    parser.add_argument("--output", type=Path, help="Optional path for the JSON summary")
    parser.add_argument(
        "--filtered-messages",
        type=Path,
        help="Optional output JSONL for retained records; otherwise filter input in place",
    )
    args = parser.parse_args()

    summary = measure_context(
        args.model,
        args.messages,
        args.expected_context_length,
        max_context_length=args.max_context_length,
        filtered_messages_path=args.filtered_messages,
        trust_remote_code=args.trust_remote_code,
    )
    rendered = json.dumps(summary, ensure_ascii=False, indent=2)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
