"""Inspect only log_index structure in compact FOREAGENT release records."""

from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--master", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    values: dict[int, list[object]] = collections.defaultdict(list)
    ordinals: dict[int, list[object]] = collections.defaultdict(list)
    pair_keys: dict[int, list[tuple[str, str]]] = collections.defaultdict(list)
    with args.master.open("r", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            source_index = row["source_index"]
            values[source_index].append(row.get("log_index"))
            ordinals[source_index].append(row.get("ordinal"))
            pair_keys[source_index].append(tuple(sorted(row["solution_paths"])))
    affected = []
    for source_index in range(len(manifest["files"])):
        source = manifest["files"][source_index]
        row_values = values[source_index]
        duplicate_count = len(row_values) - len(set(map(repr, row_values)))
        null_count = sum(value is None for value in row_values)
        ordinal_duplicates = len(ordinals[source_index]) - len(set(ordinals[source_index]))
        pair_duplicates = len(pair_keys[source_index]) - len(set(pair_keys[source_index]))
        if duplicate_count or null_count or ordinal_duplicates or pair_duplicates:
            counter = collections.Counter(map(repr, row_values))
            examples = sorted(
                ((value, count) for value, count in counter.items() if count > 1),
                key=lambda item: (-item[1], item[0]),
            )[:5]
            affected.append(
                {
                    "source_index": source_index,
                    "task": source["task"],
                    "model": source["model_family"],
                    "release_run": source["release_run"],
                    "rows": len(row_values),
                    "log_index_duplicates": duplicate_count,
                    "log_index_nulls": null_count,
                    "ordinal_duplicates": ordinal_duplicates,
                    "pair_duplicates": pair_duplicates,
                    "duplicate_examples": examples,
                }
            )
    print(
        "FOREAGENT_LOG_INDEX_STRUCTURE",
        f"sources={len(manifest['files'])}",
        f"affected_sources={len(affected)}",
        f"pair_duplicate_sources={sum(row['pair_duplicates'] > 0 for row in affected)}",
        f"ordinal_duplicate_sources={sum(row['ordinal_duplicates'] > 0 for row in affected)}",
    )
    for row in affected:
        print(json.dumps(row, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
