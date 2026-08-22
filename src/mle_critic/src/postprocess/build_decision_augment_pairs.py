"""Mix JSONL datasets with weighted sampling.

With ``--use-test-split DATASET``, the requested number of records is sampled
from every dataset's ``train`` split, the named dataset's complete ``test``
split is appended unchanged, and other datasets' test records are discarded.
Without it, train and test records from every dataset participate in sampling.
"""
from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path
from typing import Any


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def positive_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed) or parsed <= 0:
        raise argparse.ArgumentTypeError("must be a finite positive number")
    return parsed


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in {path} at line {line_number}") from exc
            if not isinstance(record, dict):
                raise ValueError(f"Expected an object in {path} at line {line_number}")
            records.append(record)
    return records


def allocate_counts(total: int, weights: list[float]) -> list[int]:
    """Allocate ``total`` samples proportionally, summing exactly to total."""
    weight_sum = sum(weights)
    exact = [total * weight / weight_sum for weight in weights]
    counts = [int(value) for value in exact]
    remainder = total - sum(counts)
    for index in sorted(
        range(len(weights)),
        key=lambda index: exact[index] - counts[index],
        reverse=True,
    )[:remainder]:
        counts[index] += 1
    return counts


def deduplicate_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove duplicate pairs, preserving the first occurrence."""
    seen: set[tuple[Any, Any]] = set()
    unique_records = []
    for record in records:
        key = (record["better"], record["worse"])
        if key not in seen:
            seen.add(key)
            unique_records.append(record)
    return unique_records


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sample and mix JSONL datasets according to normalized weights."
    )
    parser.add_argument("--datasets", nargs="+", type=Path, required=True)
    parser.add_argument("--weights", nargs="+", type=positive_float, required=True)
    parser.add_argument(
        "--n-samples",
        type=positive_int,
        required=True,
        help="number of sampled records in the mixed pool",
    )
    parser.add_argument("--output-path", type=Path, required=True)
    parser.add_argument(
        "--use-test-split",
        type=Path,
        default=None,
        metavar="DATASET",
        help=(
            "sample train records and retain the complete test split from this "
            "dataset only"
        ),
    )
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    if len(args.datasets) != len(args.weights):
        parser.error("--datasets and --weights must contain the same number of items")
    dataset_paths = [path.resolve() for path in args.datasets]
    if args.use_test_split is not None and args.use_test_split.resolve() not in dataset_paths:
        parser.error("--use-test-split must name one of the --datasets")

    datasets = [read_jsonl(path) for path in args.datasets]
    if args.use_test_split is not None:
        sample_pools = [
            [record for record in records if record.get("intask_split") == "train"]
            for records in datasets
        ]
        test_records = [
            record
            for path, records in zip(dataset_paths, datasets)
            if path == args.use_test_split.resolve()
            for record in records
            if record.get("intask_split") == "test"
        ]
    else:
        sample_pools = datasets
        test_records = []

    counts = allocate_counts(args.n_samples, args.weights)
    rng = random.Random(args.seed)
    sampled_records = []

    for path, pool, count in zip(args.datasets, sample_pools, counts):
        if len(pool) < count:
            split = "train" if args.use_test_split else "all"
            raise SystemExit(
                f"Requested {count} {split} records from {path}, but only "
                f"{len(pool)} are available."
            )
        sampled_records.extend(rng.sample(pool, count))

    rng.shuffle(sampled_records)
    unique_test_records = deduplicate_records(test_records)
    test_keys = {(record["better"], record["worse"]) for record in unique_test_records}
    unique_sampled_records = [
        record
        for record in deduplicate_records(sampled_records)
        if (record["better"], record["worse"]) not in test_keys
    ]
    output_records = unique_sampled_records + unique_test_records
    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    with args.output_path.open("w", encoding="utf-8") as output:
        for record in output_records:
            output.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")

    print(
        f"Wrote {len(output_records)} unique records ({len(unique_sampled_records)} "
        f"sampled, {len(unique_test_records)} retained test) to "
        f"{args.output_path} (seed={args.seed})."
    )


if __name__ == "__main__":
    main()
