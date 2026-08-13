#!/usr/bin/env python3
"""Label-blind static SPT sibling-pair capacity census."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from phase1.scoreable_prediction_tap import discover


SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9._-]{16,}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"(?i)(?:api[_-]?key|access[_-]?token)\s*=\s*['\"][^'\"]{12,}['\"]"),
)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cards", type=Path, required=True)
    parser.add_argument("--split", type=Path, required=True)
    args = parser.parse_args()

    split = json.loads(args.split.read_text(encoding="utf-8"))
    all_runs = set(split["all"])
    hold_runs = set(split["hold"])
    if not hold_runs < all_runs:
        raise RuntimeError("hold runs must be a strict subset of all runs")
    train_runs = all_runs - hold_runs

    counts: Counter[tuple[str, str]] = Counter()
    groups: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    forbidden_accesses: list[str] = []

    for line in args.cards.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        raw = json.loads(line)
        task_obj = raw.get("task") or {}
        task = task_obj.get("name")
        run_id = raw.get("run_id")
        parent_id = (raw.get("lineage") or {}).get("parent_id")
        code = raw.get("code")
        if not isinstance(task, str) or not task:
            counts[("<missing>", "missing_task")] += 1
            continue
        counts[(task, "cards_seen")] += 1
        if run_id not in train_runs:
            counts[(task, "excluded_hold_or_unknown_run")] += 1
            continue
        if not all(isinstance(value, str) and value for value in (run_id, parent_id, code)):
            counts[(task, "missing_required_field")] += 1
            continue
        if any(pattern.search(code) for pattern in SECRET_PATTERNS):
            counts[(task, "secret_pattern_rejected")] += 1
            continue
        try:
            _, sites = discover(code)
        except (RuntimeError, SyntaxError, ValueError):
            counts[(task, "not_instrumentable")] += 1
            continue
        if not sites:
            counts[(task, "not_instrumentable")] += 1
            continue
        counts[(task, "instrumentable_cards")] += 1
        groups[(task, run_id, parent_id)].add(sha256_text(code))

    raw_capacity: Counter[str] = Counter()
    eligible_groups: Counter[str] = Counter()
    run_capacity: Counter[tuple[str, str]] = Counter()
    for (task, run_id, _), code_hashes in groups.items():
        capacity = len(code_hashes) // 2
        if capacity <= 0:
            continue
        eligible_groups[task] += 1
        raw_capacity[task] += capacity
        run_capacity[(task, run_id)] += capacity

    capped_capacity: Counter[str] = Counter()
    eligible_runs: Counter[str] = Counter()
    for (task, _), capacity in run_capacity.items():
        eligible_runs[task] += 1
        capped_capacity[task] += min(2, capacity)

    tasks = sorted({task for task, _ in counts if task != "<missing>"})
    per_task = {}
    for task in tasks:
        per_task[task] = {
            name: counts[(task, name)]
            for name in (
                "cards_seen",
                "excluded_hold_or_unknown_run",
                "missing_required_field",
                "secret_pattern_rejected",
                "not_instrumentable",
                "instrumentable_cards",
            )
        }
        per_task[task].update(
            {
                "eligible_sibling_groups": eligible_groups[task],
                "eligible_runs": eligible_runs[task],
                "raw_disjoint_pair_capacity": raw_capacity[task],
                "e1_capacity_task15_run2": min(15, capped_capacity[task]),
            }
        )

    output = {
        "schema_version": 1,
        "selection_boundary": (
            "Non-hold runs; identity/topology/task/code only; precision-first static SPT; "
            "unique-code disjoint pairs; at most two pairs/run and fifteen pairs/task."
        ),
        "forbidden_fields_not_accessed": ["label", "obs"],
        "cards_sha256": hashlib.sha256(args.cards.read_bytes()).hexdigest(),
        "split_sha256": hashlib.sha256(args.split.read_bytes()).hexdigest(),
        "tasks_with_capacity": sum(value["e1_capacity_task15_run2"] > 0 for value in per_task.values()),
        "e1_total_capacity_task15_run2": sum(
            value["e1_capacity_task15_run2"] for value in per_task.values()
        ),
        "per_task": per_task,
    }
    if forbidden_accesses:
        raise RuntimeError(f"forbidden accesses: {forbidden_accesses}")
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
