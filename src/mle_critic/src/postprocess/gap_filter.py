"""Filter value pairs using task-specific minimum raw gaps.

By default, this reads the aggregated augmented-data value pairs and writes a
filtered JSONL beside them:

    python -m src.mle_critic.src.postprocess.gap_filter
"""
from __future__ import annotations

import argparse
import json
import math
import os
import tempfile
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[4]
AUGMENTED_DATA_DIR = PROJECT_ROOT / "data" / "augmented_mle_critic"
DEFAULT_VALUE_PAIRS = AUGMENTED_DATA_DIR / "raw_journal" / "batch_value_pairs.jsonl"
DEFAULT_GAP_FILTER = AUGMENTED_DATA_DIR / "gap_filter.json"
DEFAULT_OUTPUT = (
    AUGMENTED_DATA_DIR / "raw_journal" / "batch_value_pairs_gap_filtered.jsonl"
)

def load_gap_filters(path: Path) -> dict[str, float]:
    """Load and validate the task-to-unit-gap mapping."""
    with path.open(encoding="utf-8") as input_file:
        raw_filters = json.load(input_file)

    filters: dict[str, float] = {}
    for task_name, unitgap in raw_filters.items():
        filters[task_name] = float(unitgap)
    return filters

def filter_pairs(
    value_pairs_path: Path,
    gap_filter_path: Path,
    min_gap: int,
    max_gap: int,
    output_path: Path,
) -> tuple[int, int]:
    """Write pairs meeting their task threshold and return kept/dropped counts."""
    gap_filters = load_gap_filters(gap_filter_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    kept = 0
    dropped = 0
    filtered_pairs: list[dict[str, Any]] = []
    with value_pairs_path.open(encoding="utf-8") as input_file:
        for line_number, line in enumerate(input_file, start=1):
            record = json.loads(line)

            task_name = record.get("loto_fold")
            gap_raw = record.get("gap_raw")
            if task_name not in gap_filters:
                raise ValueError(
                    f"No minimum gap configured for task {task_name!r} "
                    f"({value_pairs_path}, line {line_number})"
                )

            if gap_raw < min_gap * gap_filters[task_name] or gap_raw > max_gap * gap_filters[task_name]:
                dropped += 1
                continue
            filtered_pairs.append(record)
            kept += 1

    # Write the filtered pairs to the output file
    with output_path.open("w", encoding="utf-8") as output_file:
        for record in filtered_pairs:
            output_file.write(json.dumps(record) + "\n")

    return kept, dropped


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--value-pairs",
        type=Path,
        default=DEFAULT_VALUE_PAIRS,
        help=f"input value-pair JSONL (default: {DEFAULT_VALUE_PAIRS})",
    )
    parser.add_argument(
        "--gap-filter",
        type=Path,
        default=DEFAULT_GAP_FILTER,
        help=f"task-to-unit-gap JSON (default: {DEFAULT_GAP_FILTER})",
    )
    parser.add_argument(
        "--min-gap",
        type=int,
        default=1,
        help=f"minimum gap allowed (default: 1 * default gap filter)",
    )
    parser.add_argument(
        "--max-gap",
        type=int,
        default=9999,
        help=f"maximum gap allowed (default: 9999 * default gap filter)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"filtered output JSONL (default: {DEFAULT_OUTPUT})",
    )
    return parser.parse_args()


def main() -> None:
    arguments = parse_args()
    kept, dropped = filter_pairs(
        arguments.value_pairs,
        arguments.gap_filter,
        arguments.min_gap,
        arguments.max_gap,
        arguments.output,
    )
    print(
        f"[gap_filter] kept {kept} pairs, dropped {dropped} pairs "
        f"-> {arguments.output}"
    )


if __name__ == "__main__":
    main()
