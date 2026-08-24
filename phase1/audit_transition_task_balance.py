#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
from typing import Any


EXPECTED_FIELDS = {
    "pair_id",
    "task",
    "run_id",
    "parent",
    "left",
    "right",
    "generation_started_at_utc",
    "temporal_stratum",
    "parent_source_present",
    "left_code_sha256",
    "right_code_sha256",
    "parent_code_sha256",
    "training_endpoint_id_overlap",
    "training_run_id_overlap",
    "training_code_sha_overlap",
    "source_novel",
    "finite_all_arms",
    "nontie_all_arms",
    "strict_effect_eligible",
    "child_code",
    "transition_only",
    "child_plus_transition",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", type=Path, required=True)
    parser.add_argument("--expect-pairs-sha256", required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--expect-summary-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.output.exists() or args.pairs.is_symlink() or args.summary.is_symlink():
        raise SystemExit("fresh output and regular immutable inputs required")
    if sha256(args.pairs) != args.expect_pairs_sha256:
        raise SystemExit("pairs SHA mismatch")
    if sha256(args.summary) != args.expect_summary_sha256:
        raise SystemExit("summary SHA mismatch")
    summary: dict[str, Any] = json.loads(args.summary.read_text(encoding="utf-8"))
    if summary.get("outputs", {}).get("pairs_sha256") != args.expect_pairs_sha256:
        raise SystemExit("summary does not bind pairs")

    counts: Counter[str] = Counter()
    runs: set[str] = set()
    rows = eligible = 0
    with args.pairs.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            row = json.loads(line)
            if not isinstance(row, dict) or set(row) != EXPECTED_FIELDS:
                raise SystemExit(f"schema mismatch at line {line_number}")
            rows += 1
            if row["strict_effect_eligible"] is True:
                task, run = row["task"], row["run_id"]
                if not isinstance(task, str) or not task or not isinstance(run, str) or not run:
                    raise SystemExit(f"invalid identity at line {line_number}")
                counts[task] += 1
                runs.add(run)
                eligible += 1
            elif row["strict_effect_eligible"] is not False:
                raise SystemExit(f"non-boolean eligibility at line {line_number}")

    expected_inventory = summary["support"]["inventory"]
    if rows != expected_inventory["all_pairs"]:
        raise SystemExit("all-pair count mismatch")
    if eligible != expected_inventory["eligible_pairs"]:
        raise SystemExit("eligible-pair count mismatch")
    if len(runs) != expected_inventory["eligible_runs"]:
        raise SystemExit("eligible-run count mismatch")
    if len(counts) != expected_inventory["eligible_tasks"]:
        raise SystemExit("eligible-task count mismatch")

    canonical = "".join(f"{task}\t{counts[task]}\n" for task in sorted(counts))
    dominant_task, dominant_count = min(
        counts.items(), key=lambda item: (-item[1], item[0].encode("utf-8"))
    )
    dominant_share = dominant_count / eligible
    non_dominant_needed_if_dominant_fixed = max(0, 4 * dominant_count - eligible)
    result = {
        "canonical_task_counts_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "dominant_count": dominant_count,
        "dominant_share": dominant_share,
        "dominant_task": dominant_task,
        "eligible_pairs": eligible,
        "eligible_runs": len(runs),
        "eligible_tasks": len(counts),
        "effect_metrics_computed": [],
        "finite": math.isfinite(dominant_share),
        "non_dominant_pairs_needed_if_dominant_count_stays_fixed": non_dominant_needed_if_dominant_fixed,
        "outcomes_read": False,
        "pairs_sha256": args.expect_pairs_sha256,
        "protocol": "transition-task-balance-structure-only-audit-v1",
        "summary_sha256": args.expect_summary_sha256,
    }
    args.output.mkdir(parents=False)
    (args.output / "task_counts.tsv").write_text(canonical, encoding="utf-8", newline="\n")
    (args.output / "summary.json").write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
