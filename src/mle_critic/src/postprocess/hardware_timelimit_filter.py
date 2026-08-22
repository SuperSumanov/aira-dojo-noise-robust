"""Filter value pairs so both cards use the same hardware/time buckets.

The input pair file contains Card IDs in its ``better`` and ``worse`` fields,
while the run-grouped card JSON contains the corresponding Card metadata.  A
pair is retained only when both cards fall in the same bucket for all three
physical settings: ``time_limit``, ``execution_timeout``, and ``hardware``.

Example::

    python -m src.mle_critic.src.postprocess.hardware_timelimit_filter
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ..preprocess.build_bt_pairs.build_subtree_pairs import flatten_runs
from ..preprocess.download_and_resolve.cards import Card, load_cards


PROJECT_ROOT = Path(__file__).resolve().parents[4]
AUGMENTED_DATA_DIR = PROJECT_ROOT / "data" / "augmented_mle_critic"
DEFAULT_VALUE_PAIRS = AUGMENTED_DATA_DIR / "raw_journal" / "value_pairs.jsonl"
DEFAULT_CARDS = AUGMENTED_DATA_DIR / "augmented_cards_current.json"
DEFAULT_OUTPUT = (
    AUGMENTED_DATA_DIR / "raw_journal" / "value_pairs_hardware_timelimit_filtered.jsonl"
)

# Intervals are lower-inclusive and upper-exclusive, except for the final
# interval.  This makes the otherwise overlapping execution-time endpoints
# (4800 and 10800) unambiguous.
TIME_LIMIT_BUCKETS = ((36000, 48000), (79200, 90000))
EXECUTION_TIMEOUT_BUCKETS = ((1800, 4800), (4800, 10800), (10800, 18000))
HARDWARE_KEYWORDS = ("2080", "3090", "4090", "cpu", "h200")


def _range_bucket(value: Any, ranges: tuple[tuple[float, float], ...]) -> int | None:
    """Return the index of the half-open range containing ``value``."""
    if isinstance(value, bool):
        return None
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return None
    for index, (lower, upper) in enumerate(ranges):
        is_last = index == len(ranges) - 1
        if lower <= numeric_value < upper or (is_last and numeric_value == upper):
            return index
    return None


def hardware_bucket(hardware: Any) -> int | None:
    """Return the bucket for the one expected hardware keyword, if present."""
    text = str(hardware).lower() if hardware is not None else ""
    matches = [index for index, keyword in enumerate(HARDWARE_KEYWORDS) if keyword in text]
    return matches[0] if len(matches) == 1 else None


def card_bucket(card: Card) -> tuple[int, int, int] | None:
    """Return all physical-setting buckets for a card, or ``None`` if invalid."""
    time_bucket = _range_bucket(card.time_limit, TIME_LIMIT_BUCKETS)
    timeout_bucket = _range_bucket(card.execution_timeout, EXECUTION_TIMEOUT_BUCKETS)
    hardware_bucket_id = hardware_bucket(card.hardware)
    if time_bucket is None or timeout_bucket is None or hardware_bucket_id is None:
        return None
    return time_bucket, timeout_bucket, hardware_bucket_id


def filter_pairs(
    value_pairs_path: Path,
    cards_path: Path,
    output_path: Path,
) -> tuple[int, int]:
    """Filter pairs and return ``(kept, dropped)`` counts."""
    cards_by_id, _ = flatten_runs(load_cards(str(cards_path)))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    kept = dropped = 0

    with value_pairs_path.open(encoding="utf-8") as input_file, output_path.open(
        "w", encoding="utf-8"
    ) as output_file:
        for line_number, line in enumerate(input_file, start=1):
            if not line.strip():
                continue
            record: dict[str, Any] = json.loads(line)
            try:
                better_id = record["better"]
                worse_id = record["worse"]
                better = cards_by_id[better_id]
                worse = cards_by_id[worse_id]
            except KeyError as error:
                raise ValueError(
                    f"Missing {error.args[0]!r} card ID at "
                    f"{value_pairs_path}, line {line_number}"
                ) from error

            better_bucket = card_bucket(better)
            worse_bucket = card_bucket(worse)
            if better_bucket is not None and better_bucket == worse_bucket:
                output_file.write(json.dumps(record, ensure_ascii=False) + "\n")
                kept += 1
            else:
                dropped += 1

    return kept, dropped


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--value-pairs", type=Path, default=DEFAULT_VALUE_PAIRS)
    parser.add_argument("--cards", type=Path, default=DEFAULT_CARDS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    arguments = parse_args()
    kept, dropped = filter_pairs(arguments.value_pairs, arguments.cards, arguments.output)
    print(f"[hardware_timelimit_filter] kept {kept} pairs, dropped {dropped} pairs -> {arguments.output}")


if __name__ == "__main__":
    main()
