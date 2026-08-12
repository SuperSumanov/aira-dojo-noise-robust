"""Sample and merge decision pairs with train-split value pairs.

The default paths are rooted at the repository so the command can be run from
any working directory:

    python -m src.mle_critic.src.postprocess.build_decision_augment_pairs \
      --n_decision 1000 --n_augment 5000

``n_decision`` intentionally keeps the spelling used by the experiment
configuration.  ``--n-decision`` is available as a correctly-spelled alias.
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any, Callable


PROJECT_ROOT = Path(__file__).resolve().parents[4]
DATA_DIR = PROJECT_ROOT / "data" / "mle_critic"


def read_jsonl_sample(
    path: Path,
    count: int,
    rng: random.Random,
    include: Callable[[dict[str, Any]], bool] | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """Return a uniform sample without replacement and its eligible count."""
    sample: list[dict[str, Any]] = []
    eligible_count = 0

    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in {path} at line {line_number}") from exc
            if include is not None and not include(record):
                continue

            eligible_count += 1
            if len(sample) < count:
                sample.append(record)
            else:
                replacement_index = rng.randrange(eligible_count)
                if replacement_index < count:
                    sample[replacement_index] = record

    return sample, eligible_count


def nonnegative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be non-negative")
    return parsed


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Randomly sample decision pairs and train-split value pairs, then "
            "write their concatenation as JSONL."
        )
    )
    parser.add_argument(
        "--n_decision",
        "--n-decision",
        dest="n_decision",
        type=nonnegative_int,
        required=True,
        help="number of records to sample from decision pairs",
    )
    parser.add_argument(
        "--n_augment",
        "--n-augment",
        dest="n_augment",
        type=nonnegative_int,
        required=True,
        help="number of intask_split=train records to sample from value pairs",
    )
    parser.add_argument(
        "--decision-path",
        type=Path,
        default=DATA_DIR / "decision_pairs_runsplit.jsonl",
    )
    parser.add_argument(
        "--value-path",
        type=Path,
        default=DATA_DIR / "value_pairs_runsplit.jsonl",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=DATA_DIR / "decision_value_merged.jsonl",
        help="merged JSONL path (default: data/mle_critic/decision_value_merged.jsonl)",
    )
    parser.add_argument(
        "--decision-split",
        choices=("train", "test"),
        default=None,
        help="optionally only sample decision records in this intask_split",
    )
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    decision_filter = (
        None
        if args.decision_split is None
        else lambda record: record.get("intask_split") == args.decision_split
    )
    decision_pairs, eligible_decisions = read_jsonl_sample(
        args.decision_path, args.n_decision, rng, decision_filter
    )
    value_pairs, eligible_values = read_jsonl_sample(
        args.value_path,
        args.n_augment,
        rng,
        lambda record: record.get("intask_split") == "train",
    )

    if eligible_decisions < args.n_decision:
        split_description = (
            f" with intask_split={args.decision_split!r}"
            if args.decision_split is not None
            else ""
        )
        raise SystemExit(
            f"Requested {args.n_decision} decision pairs{split_description}, but "
            f"only {eligible_decisions} are available."
        )
    if eligible_values < args.n_augment:
        raise SystemExit(
            f"Requested {args.n_augment} train-split value pairs, but only "
            f"{eligible_values} are available."
        )

    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    with args.output_path.open("w", encoding="utf-8") as output:
        for record in decision_pairs + value_pairs:
            output.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")

    print(
        f"Wrote {len(decision_pairs)} decision pairs and {len(value_pairs)} "
        f"train-split value pairs to {args.output_path} "
        f"(seed={args.seed})."
    )


if __name__ == "__main__":
    main()
