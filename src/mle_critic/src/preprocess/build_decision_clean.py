"""Split run-clean decision pairs by lookahead budget and audit conflicts.

For each budget this writes a full train/test file named
``decision_clean_b<K>_runsplit.jsonl``.  With ``--write-frozen-test`` it also
writes the student-compatible test-only ``decision_clean_b<K>.jsonl`` files.
"""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pairs", type=Path)
    parser.add_argument("out_dir", type=Path)
    parser.add_argument("--budgets", default="0,1,2")
    parser.add_argument("--write-frozen-test", action="store_true")
    args = parser.parse_args()
    budgets = [int(value) for value in args.budgets.split(",")]

    rows_by_budget = {budget: [] for budget in budgets}
    with args.pairs.open(encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            if row.get("budget") in rows_by_budget:
                rows_by_budget[row["budget"]].append(row)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    for budget, rows in rows_by_budget.items():
        seen = set()
        deduplicated = []
        duplicates = 0
        for row in rows:
            key = (row["better"], row["worse"], row["intask_split"])
            if key in seen:
                duplicates += 1
                continue
            seen.add(key)
            deduplicated.append(row)

        directions = collections.defaultdict(set)
        for row in deduplicated:
            key = (tuple(sorted((row["better"], row["worse"]))), row["intask_split"])
            directions[key].add((row["better"], row["worse"]))
        conflicts = [key for key, values in directions.items() if len(values) > 1]
        if conflicts:
            raise ValueError(
                f"budget {budget} has {len(conflicts)} reversed conflicts within a split"
            )

        full_path = args.out_dir / f"decision_clean_b{budget}_runsplit.jsonl"
        with full_path.open("w", encoding="utf-8") as output:
            for row in deduplicated:
                output.write(json.dumps(row, ensure_ascii=False) + "\n")

        split_counts = collections.Counter(
            row["intask_split"] for row in deduplicated
        )
        print(
            f"K={budget}: {dict(split_counts)}, duplicates={duplicates}, "
            f"conflicts=0 -> {full_path}"
        )
        if args.write_frozen_test:
            test_path = args.out_dir / f"decision_clean_b{budget}.jsonl"
            with test_path.open("w", encoding="utf-8") as output:
                for row in deduplicated:
                    if row["intask_split"] == "test":
                        output.write(json.dumps(row, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
