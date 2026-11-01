"""Merge GRPO rows with positive-advantage additions and consistent group splits."""

import argparse
from collections import Counter
import json
import math
from pathlib import Path


def merge(original: Path, hindsight: Path, destination: Path) -> dict:
    """Merge original rows and positive-advantage additions, enforcing unique samples and consistent group splits."""
    original, hindsight, destination = original.resolve(), hindsight.resolve(), destination.resolve()
    if destination in (original, hindsight) or original == hindsight:
        raise ValueError("Merge inputs and output must be distinct")
    destination.parent.mkdir(parents=True, exist_ok=True)
    counts = Counter()
    seen = set()
    splits = {}
    with destination.open("w", encoding="utf-8") as handle:
        for kind, source in (("original", original), ("added", hindsight)):
            with source.open(encoding="utf-8") as inputs:
                for line in inputs:
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    if kind == "added":
                        advantage = row.get("advantage")
                        if not (
                            not isinstance(advantage, bool)
                            and isinstance(advantage, (int, float))
                            and math.isfinite(advantage)
                            and advantage > 0
                        ):
                            raise ValueError("Merge additions require positive-advantage rows")
                    sample_id = row["sample_id"]
                    if sample_id in seen:
                        raise ValueError(f"Duplicate sample: {sample_id}")
                    seen.add(sample_id)
                    group_id, split = row["group_id"], row["split"]
                    if split not in ("train", "val") or splits.setdefault(group_id, split) != split:
                        raise ValueError(f"Inconsistent group split: {group_id}")
                    handle.write(line if line.endswith("\n") else line + "\n")
                    counts[kind + "_rows"] += 1
                    counts[kind + "_" + split] += 1

    report = {
        "original": str(original), "added": str(hindsight), "output": str(destination),
        "rows": sum(counts.get(kind + "_rows", 0) for kind in ("original", "added")),
        **dict(counts),
    }
    with destination.with_suffix(".report.json").open("w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return report


def main():
    """Parse dataset paths, merge training rows, and print the report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original", required=True, type=Path)
    parser.add_argument("--hindsight", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(merge(args.original, args.hindsight, args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
