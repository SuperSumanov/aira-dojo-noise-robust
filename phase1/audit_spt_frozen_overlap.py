#!/usr/bin/env python3
"""Identity-only overlap audit between an SPT manifest and frozen decision evaluation."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path: Path):
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            yield json.loads(line)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cards", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--frozen", type=Path, nargs="+", required=True)
    args = parser.parse_args()

    manifest_rows = list(rows(args.manifest))
    selected_cards = {row["card_id"] for row in manifest_rows}
    selected_parents = {row["parent_id"] for row in manifest_rows}
    selected_runs = {row["run_id"] for row in manifest_rows}
    if len(selected_cards) != 6 or len(selected_parents) != 3:
        raise RuntimeError("unexpected pilot identity grid")

    frozen_endpoints: set[str] = set()
    frozen_parents: set[str] = set()
    frozen_rows = 0
    split_values: set[str] = set()
    for path in args.frozen:
        for row in rows(path):
            frozen_rows += 1
            split_values.add(row.get("intask_split"))
            frozen_endpoints.update((row["better"], row["worse"]))
            frozen_parents.add(row["parent"])
    if split_values != {"test"}:
        raise RuntimeError(f"frozen files are not test-only: {sorted(split_values)}")

    relevant_ids = selected_cards | selected_parents | frozen_endpoints | frozen_parents
    id_to_run: dict[str, str] = {}
    for row in rows(args.cards):
        card_id = row.get("id")
        if card_id not in relevant_ids:
            continue
        run_id = row.get("run_id")
        if not isinstance(run_id, str) or not run_id:
            raise RuntimeError(f"missing run id for relevant card: {card_id}")
        if card_id in id_to_run and id_to_run[card_id] != run_id:
            raise RuntimeError(f"card maps to multiple runs: {card_id}")
        id_to_run[card_id] = run_id

    frozen_runs = {
        id_to_run[card_id]
        for card_id in frozen_endpoints | frozen_parents
        if card_id in id_to_run
    }
    result = {
        "schema_version": 1,
        "forbidden_fields_not_accessed": ["label", "obs", "gap_raw"],
        "manifest_sha256": file_sha256(args.manifest),
        "cards_sha256": file_sha256(args.cards),
        "frozen_sha256": {str(path): file_sha256(path) for path in args.frozen},
        "frozen_rows": frozen_rows,
        "frozen_endpoints": len(frozen_endpoints),
        "frozen_parents": len(frozen_parents),
        "frozen_runs": len(frozen_runs),
        "selected_cards": len(selected_cards),
        "selected_parents": len(selected_parents),
        "selected_runs": len(selected_runs),
        "selected_card_vs_frozen_endpoint": sorted(selected_cards & frozen_endpoints),
        "selected_card_vs_frozen_any_id": sorted(
            selected_cards & (frozen_endpoints | frozen_parents)
        ),
        "selected_parent_vs_frozen_parent": sorted(selected_parents & frozen_parents),
        "selected_run_vs_frozen_run": sorted(selected_runs & frozen_runs),
    }
    result["decision"] = (
        "PASS_ZERO_OVERLAP"
        if not any(
            result[name]
            for name in (
                "selected_card_vs_frozen_endpoint",
                "selected_card_vs_frozen_any_id",
                "selected_parent_vs_frozen_parent",
                "selected_run_vs_frozen_run",
            )
        )
        else "FAIL_FROZEN_OVERLAP"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    if result["decision"] != "PASS_ZERO_OVERLAP":
        raise SystemExit(3)


if __name__ == "__main__":
    main()
