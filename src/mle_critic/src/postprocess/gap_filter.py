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
    """Load and validate the task-to-minimum-gap mapping."""
    try:
        with path.open(encoding="utf-8") as input_file:
            raw_filters = json.load(input_file)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in gap-filter file {path}") from exc

    if not isinstance(raw_filters, dict):
        raise ValueError(f"Expected a JSON object in gap-filter file {path}")

    filters: dict[str, float] = {}
    for task_name, minimum_gap in raw_filters.items():
        if not isinstance(task_name, str) or not task_name:
            raise ValueError(f"Gap-filter task names must be non-empty strings: {task_name!r}")
        if (
            not isinstance(minimum_gap, (int, float))
            or isinstance(minimum_gap, bool)
            or not math.isfinite(minimum_gap)
            or minimum_gap < 0
        ):
            raise ValueError(
                f"Minimum gap for task {task_name!r} must be a finite non-negative number"
            )
        filters[task_name] = float(minimum_gap)
    return filters


def pair_gap(record: Any, line_number: int, path: Path) -> tuple[str, float]:
    """Extract and validate the task name and raw gap from one pair record."""
    if not isinstance(record, dict):
        raise ValueError(f"Expected a JSON object in {path} at line {line_number}")

    task_name = record.get("loto_fold")
    if not isinstance(task_name, str) or not task_name:
        raise ValueError(
            f"Missing non-empty string 'loto_fold' in {path} at line {line_number}"
        )

    gap_raw = record.get("gap_raw")
    if (
        not isinstance(gap_raw, (int, float))
        or isinstance(gap_raw, bool)
        or not math.isfinite(gap_raw)
    ):
        raise ValueError(
            f"Missing finite numeric 'gap_raw' in {path} at line {line_number}"
        )
    return task_name, float(gap_raw)


def filter_pairs(
    value_pairs_path: Path,
    gap_filter_path: Path,
    output_path: Path,
) -> tuple[int, int]:
    """Write pairs meeting their task threshold and return kept/dropped counts."""
    gap_filters = load_gap_filters(gap_filter_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    kept = 0
    dropped = 0
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output_path.parent,
            prefix=f".{output_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as output_file:
            temporary_path = Path(output_file.name)
            with value_pairs_path.open(encoding="utf-8") as input_file:
                for line_number, line in enumerate(input_file, start=1):
                    if not line.strip():
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise ValueError(
                            f"Invalid JSON in {value_pairs_path} at line {line_number}"
                        ) from exc

                    task_name, gap_raw = pair_gap(record, line_number, value_pairs_path)
                    if task_name not in gap_filters:
                        raise ValueError(
                            f"No minimum gap configured for task {task_name!r} "
                            f"({value_pairs_path}, line {line_number})"
                        )

                    if gap_raw < gap_filters[task_name]:
                        dropped += 1
                        continue
                    output_file.write(line if line.endswith("\n") else line + "\n")
                    kept += 1

        os.replace(temporary_path, output_path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)

    return kept, dropped


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--value-pairs-path",
        "--value-pairs",
        type=Path,
        default=DEFAULT_VALUE_PAIRS,
        help=f"input value-pair JSONL (default: {DEFAULT_VALUE_PAIRS})",
    )
    parser.add_argument(
        "--gap-filter-path",
        "--gap-filter",
        type=Path,
        default=DEFAULT_GAP_FILTER,
        help=f"task-to-minimum-gap JSON (default: {DEFAULT_GAP_FILTER})",
    )
    parser.add_argument(
        "--output-path",
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"filtered output JSONL (default: {DEFAULT_OUTPUT})",
    )
    return parser.parse_args()


def main() -> None:
    arguments = parse_args()
    kept, dropped = filter_pairs(
        arguments.value_pairs_path,
        arguments.gap_filter_path,
        arguments.output_path,
    )
    print(
        f"[gap_filter] kept {kept} pairs, dropped {dropped} pairs "
        f"-> {arguments.output_path}"
    )


if __name__ == "__main__":
    main()
