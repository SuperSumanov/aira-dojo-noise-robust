"""Keep rows with a finite, strictly positive computed advantage."""

import argparse
import json
import math
from pathlib import Path


def filter_positive(source: Path, destination: Path) -> dict:
    """Export rows with finite, strictly positive advantage and write filtering statistics."""
    source, destination = source.resolve(), destination.resolve()
    if source == destination:
        raise ValueError("Filter output must differ from input")
    destination.parent.mkdir(parents=True, exist_ok=True)
    counts = {"input_rows": 0, "positive_rows": 0, "nonpositive_rows": 0}
    with source.open(encoding="utf-8") as inputs, destination.open("w", encoding="utf-8") as outputs:
        for line_number, line in enumerate(inputs, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            advantage = row.get("advantage")
            if (
                isinstance(advantage, bool)
                or not isinstance(advantage, (int, float))
                or not math.isfinite(advantage)
            ):
                raise ValueError(f"{source}:{line_number}: expected a finite computed advantage")
            counts["input_rows"] += 1
            if advantage > 0:
                json.dump(row, outputs, ensure_ascii=False)
                outputs.write("\n")
                counts["positive_rows"] += 1
            else:
                counts["nonpositive_rows"] += 1
    report = {"input": str(source), "output": str(destination), **counts}
    with destination.with_suffix(".report.json").open("w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return report


def main():
    """Parse input and output paths, filter positive advantages, and print the report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(filter_positive(args.input, args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
