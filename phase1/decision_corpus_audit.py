#!/usr/bin/env python3
"""Create a machine-readable audit card for decision-local search corpora.

The auditor intentionally consumes pair metadata and a card-to-physical-run map,
not card code or observations.  It checks the sampling unit, true-sibling choice
sets, effective support, gap composition, and same-budget split isolation.
Label-noise and deployment-time evidence remain separate attestations because
they require different raw inputs and estimands.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import os
import platform
import statistics
from pathlib import Path
from typing import Any, Iterable, Sequence


PROTOCOL = "decision_corpus_audit_v1"
PARTITIONS = {"train", "frozen", "extension", "prospective"}
EXPECTED_INTASK_SPLIT = {
    "train": "train",
    "frozen": "test",
    "extension": "test",
    "prospective": "test",
}
GAP_EDGES = (0.0, 1e-4, 3e-4, 1e-3, 3e-3, 1e-2, 3e-2, 1e-1, 3e-1, math.inf)
HARD_THRESHOLD = 1e-2
REQUIRED_FIELDS = {
    "better",
    "worse",
    "parent",
    "task",
    "budget",
    "intask_split",
    "gap_raw",
    "set_size",
}


class IntegrityError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def portable_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    atomic_text(
        path,
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n",
    )


def parse_pair_set(specification: str) -> tuple[str, int, Path]:
    pieces = specification.split(":", 2)
    if len(pieces) != 3:
        raise IntegrityError("--pair-set must be PARTITION:BUDGET:PATH")
    partition, budget_text, path_text = pieces
    if partition not in PARTITIONS:
        raise IntegrityError(f"unsupported partition: {partition}")
    try:
        budget = int(budget_text)
    except ValueError as exc:
        raise IntegrityError(f"non-integer budget: {budget_text}") from exc
    if budget < 0:
        raise IntegrityError("budget must be non-negative")
    return partition, budget, Path(path_text)


def finite_nonnegative(value: Any, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise IntegrityError(f"non-numeric {label}: {value!r}") from exc
    if not math.isfinite(number) or number < 0:
        raise IntegrityError(f"invalid {label}: {value!r}")
    return number


def load_run_map(path: Path) -> dict[str, str]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not raw:
        raise IntegrityError("run map must be a non-empty object")
    output: dict[str, str] = {}
    for card_id, run_id in raw.items():
        card, run = str(card_id), str(run_id)
        if not card or not run:
            raise IntegrityError("run map contains an empty card/run identifier")
        output[card] = run
    return output


def resolve_physical_run(
    row: dict[str, Any], run_map: dict[str, str], label: str
) -> tuple[str, bool]:
    endpoints = [str(row[key]) for key in ("better", "worse")]
    missing = [card_id for card_id in endpoints if card_id not in run_map]
    if missing:
        raise IntegrityError(f"{label} endpoints missing from run map: {missing}")
    runs = {run_map[card_id] for card_id in endpoints}
    if len(runs) != 1:
        raise IntegrityError(f"{label} is not a true physical-run sibling pair: {sorted(runs)}")
    resolved = next(iter(runs))
    parent = str(row["parent"])
    parent_mapped = parent in run_map
    if parent_mapped and run_map[parent] != resolved:
        raise IntegrityError(
            f"{label} mapped parent run {run_map[parent]!r} differs from endpoint run {resolved!r}"
        )
    declared = row.get("run_id")
    if declared is not None and str(declared) != resolved:
        raise IntegrityError(
            f"{label} declared run {declared!r} differs from reconstructed {resolved!r}"
        )
    return resolved, parent_mapped


def load_pair_set(
    partition: str, budget: int, path: Path, run_map: dict[str, str]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            raw = json.loads(line)
            missing = REQUIRED_FIELDS - set(raw)
            if missing:
                raise IntegrityError(
                    f"{path}:{line_number} missing required fields {sorted(missing)}"
                )
            label = f"{path}:{line_number}"
            if int(raw["budget"]) != budget:
                raise IntegrityError(f"{label} budget differs from pair-set specification")
            if str(raw["intask_split"]) != EXPECTED_INTASK_SPLIT[partition]:
                raise IntegrityError(f"{label} intask_split differs from partition contract")
            better, worse = str(raw["better"]), str(raw["worse"])
            parent, task = str(raw["parent"]), str(raw["task"])
            if not all((better, worse, parent, task)) or better == worse:
                raise IntegrityError(f"{label} contains empty/degenerate identifiers")
            unordered = tuple(sorted((better, worse)))
            if unordered in seen:
                raise IntegrityError(f"{label} duplicates or reverses an earlier pair")
            seen.add(unordered)
            gap = finite_nonnegative(raw["gap_raw"], f"{label} gap_raw")
            set_size = int(raw["set_size"])
            if set_size < 2:
                raise IntegrityError(f"{label} set_size must be at least two")
            run, parent_mapped = resolve_physical_run(raw, run_map, label)
            rows.append(
                {
                    "partition": partition,
                    "budget": budget,
                    "better": better,
                    "worse": worse,
                    "parent": parent,
                    "task": task,
                    "run": run,
                    "parent_run_mapped": parent_mapped,
                    "gap": gap,
                    "declared_set_size": set_size,
                }
            )
    if not rows:
        raise IntegrityError(f"empty pair set: {path}")
    return rows


def percentile(values: Sequence[int], probability: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower, upper = math.floor(position), math.ceil(position)
    if lower == upper:
        return float(ordered[lower])
    weight = position - lower
    return float(ordered[lower] * (1 - weight) + ordered[upper] * weight)


def gap_label(lower: float, upper: float) -> str:
    return f"[{lower:.12g},{'inf' if math.isinf(upper) else f'{upper:.12g}'})"


def gap_counts(rows: Sequence[dict[str, Any]]) -> dict[str, int]:
    counts = {gap_label(left, right): 0 for left, right in zip(GAP_EDGES, GAP_EDGES[1:])}
    for row in rows:
        gap = float(row["gap"])
        for left, right in zip(GAP_EDGES, GAP_EDGES[1:]):
            if left <= gap < right:
                counts[gap_label(left, right)] += 1
                break
        else:  # pragma: no cover - finite_nonnegative plus final inf makes this unreachable
            raise IntegrityError(f"gap did not enter a frozen bucket: {gap}")
    return counts


def choice_set_records(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, int, str], list[dict[str, Any]]] = collections.defaultdict(list)
    for row in rows:
        grouped[(row["partition"], row["budget"], row["parent"])].append(row)
    output: list[dict[str, Any]] = []
    for (partition, budget, parent), members in sorted(grouped.items()):
        contexts = {
            (
                row["task"],
                row["run"],
                row["declared_set_size"],
                row["parent_run_mapped"],
            )
            for row in members
        }
        if len(contexts) != 1:
            raise IntegrityError(f"inconsistent choice-set context: {partition}/{budget}/{parent}")
        task, run, declared_size, parent_mapped = next(iter(contexts))
        candidates = sorted(
            {row[key] for row in members for key in ("better", "worse")}
        )
        expected_edges = len(candidates) * (len(candidates) - 1) // 2
        wins = collections.Counter(row["better"] for row in members)
        degree_sequence = sorted(wins[candidate] for candidate in candidates)
        complete = len(members) == expected_edges
        strict_order = complete and degree_sequence == list(range(len(candidates)))
        output.append(
            {
                "partition": partition,
                "budget": budget,
                "parent": parent,
                "task": task,
                "run": run,
                "parent_run_mapped": parent_mapped,
                "pairs": len(members),
                "candidates": len(candidates),
                "declared_set_size": declared_size,
                "declared_size_matches": declared_size == len(candidates),
                "edge_complete": complete,
                "strict_total_order": strict_order,
            }
        )
    return output


def summarize_set(rows: Sequence[dict[str, Any]], choices: Sequence[dict[str, Any]]) -> dict[str, Any]:
    endpoints = [row[key] for row in rows for key in ("better", "worse")]
    endpoint_degree = collections.Counter(endpoints)
    task_pairs = collections.Counter(row["task"] for row in rows)
    task_parents = collections.Counter(choice["task"] for choice in choices)
    parent_sizes = collections.Counter(choice["candidates"] for choice in choices)
    hard = sum(float(row["gap"]) < HARD_THRESHOLD for row in rows)
    degrees = list(endpoint_degree.values())
    return {
        "pairs": len(rows),
        "parents": len(choices),
        "endpoints": len(endpoint_degree),
        "runs": len({row["run"] for row in rows}),
        "tasks": len(task_pairs),
        "complete_parents": sum(choice["edge_complete"] for choice in choices),
        "strict_total_order_parents": sum(choice["strict_total_order"] for choice in choices),
        "declared_size_match_parents": sum(
            choice["declared_size_matches"] for choice in choices
        ),
        "mapped_parent_choice_sets": sum(choice["parent_run_mapped"] for choice in choices),
        "orphan_parent_choice_sets": sum(not choice["parent_run_mapped"] for choice in choices),
        "candidate_count_histogram": dict(sorted(parent_sizes.items())),
        "hard_threshold": HARD_THRESHOLD,
        "hard_pairs": hard,
        "hard_pair_share": hard / len(rows),
        "gap_bucket_counts": gap_counts(rows),
        "endpoint_degree": {
            "median": float(statistics.median(degrees)),
            "p95": percentile(degrees, 0.95),
            "max": max(degrees),
            "degree_gt_one_endpoints": sum(value > 1 for value in degrees),
        },
        "dominant_task_pair_share": max(task_pairs.values()) / len(rows),
        "dominant_task_parent_share": max(task_parents.values()) / len(choices),
    }


def overlap(left: Sequence[dict[str, Any]], right: Sequence[dict[str, Any]]) -> dict[str, int]:
    def values(rows: Sequence[dict[str, Any]], field: str) -> set[str]:
        if field == "endpoints":
            return {row[key] for row in rows for key in ("better", "worse")}
        return {str(row[field]) for row in rows}

    return {
        "pairs": len(
            {tuple(sorted((row["better"], row["worse"]))) for row in left}
            & {tuple(sorted((row["better"], row["worse"]))) for row in right}
        ),
        "endpoints": len(values(left, "endpoints") & values(right, "endpoints")),
        "parents": len(values(left, "parent") & values(right, "parent")),
        "runs": len(values(left, "run") & values(right, "run")),
    }


def audit(
    specifications: Sequence[tuple[str, int, Path]], run_map_path: Path
) -> dict[str, Any]:
    if not specifications:
        raise IntegrityError("at least one --pair-set is required")
    keys = [(partition, budget) for partition, budget, _ in specifications]
    if len(keys) != len(set(keys)):
        raise IntegrityError("duplicate partition/budget pair-set specification")
    run_map = load_run_map(run_map_path)
    rows_by_key: dict[tuple[str, int], list[dict[str, Any]]] = {}
    inputs: dict[str, Any] = {
        "run_map": {"path": run_map_path.as_posix(), "sha256": sha256(run_map_path)}
    }
    for partition, budget, path in specifications:
        key = (partition, budget)
        rows_by_key[key] = load_pair_set(partition, budget, path, run_map)
        inputs[f"{partition}:b{budget}"] = {
            "path": path.as_posix(),
            "sha256": sha256(path),
        }

    all_rows = [row for rows in rows_by_key.values() for row in rows]
    choices = choice_set_records(all_rows)
    choices_by_key: dict[tuple[str, int], list[dict[str, Any]]] = collections.defaultdict(list)
    for choice in choices:
        choices_by_key[(choice["partition"], choice["budget"])].append(choice)

    sets = {
        f"{partition}:b{budget}": summarize_set(rows, choices_by_key[(partition, budget)])
        for (partition, budget), rows in sorted(rows_by_key.items())
    }
    same_budget_isolation: dict[str, Any] = {}
    isolation_ok = True
    budgets = sorted({budget for _, budget in rows_by_key})
    for budget in budgets:
        train = rows_by_key.get(("train", budget))
        frozen = rows_by_key.get(("frozen", budget))
        if train is None or frozen is None:
            continue
        measured = overlap(train, frozen)
        passed = measured == {"pairs": 0, "endpoints": 0, "parents": 0, "runs": 0}
        isolation_ok = isolation_ok and passed
        same_budget_isolation[f"b{budget}"] = {**measured, "passed": passed}

    isolation_evaluable = bool(same_budget_isolation)
    verified = isolation_evaluable and isolation_ok
    return {
        "protocol": PROTOCOL,
        "status": (
            "VERIFIED_DECISION_CORPUS_AUDIT"
            if verified
            else "FAILED_SPLIT_ISOLATION"
            if isolation_evaluable
            else "INSUFFICIENT_SPLIT_EVIDENCE"
        ),
        "provenance": {
            "producer_script": {
                "path": portable_path(Path(__file__)),
                "sha256": sha256(Path(__file__)),
            },
            "python": platform.python_version(),
        },
        "scope": {
            "reads_card_code": False,
            "reads_card_observations": False,
            "recomputes_label_noise": False,
            "recomputes_deployment_cost": False,
            "recomputes_prospective_protocol": False,
        },
        "inputs": inputs,
        "sets": sets,
        "same_budget_train_frozen_isolation": same_budget_isolation,
        "integrity": {
            "all_rows_true_physical_siblings": True,
            "all_choice_sets_context_consistent": True,
            "same_budget_train_frozen_isolation_evaluable": isolation_evaluable,
            "same_budget_train_frozen_isolated": isolation_ok,
        },
    }


def render_datasheet(result: dict[str, Any]) -> str:
    lines = [
        "# Decision-corpus audit card",
        "",
        f"- Protocol: `{result['protocol']}`",
        f"- Status: `{result['status']}`",
        "- Raw code/observations read: no",
        "",
        "| Pair set | pairs | parents | endpoints | runs | tasks | hard share | complete parents |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, item in sorted(result["sets"].items()):
        lines.append(
            f"| {name} | {item['pairs']} | {item['parents']} | {item['endpoints']} | "
            f"{item['runs']} | {item['tasks']} | {item['hard_pair_share']:.6f} | "
            f"{item['complete_parents']} |"
        )
    lines.extend(["", "## Same-budget train/frozen isolation", ""])
    if not result["same_budget_train_frozen_isolation"]:
        lines.append("No train/frozen pair with a common budget was supplied.")
    else:
        lines.extend(
            [
                "| budget | pair overlap | endpoint overlap | parent overlap | run overlap | pass |",
                "|---|---:|---:|---:|---:|---|",
            ]
        )
        for budget, item in sorted(result["same_budget_train_frozen_isolation"].items()):
            lines.append(
                f"| {budget} | {item['pairs']} | {item['endpoints']} | {item['parents']} | "
                f"{item['runs']} | {str(item['passed']).lower()} |"
            )
    lines.extend(
        [
            "",
            "Label-noise ceilings, deployment-time/cost semantics, and prospective activation "
            "are deliberately separate attestations; this card must not be cited as having "
            "recomputed them.",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--pair-set",
        action="append",
        required=True,
        help="repeatable PARTITION:BUDGET:PATH",
    )
    parser.add_argument("--run-map", required=True)
    parser.add_argument("--out-dir", required=True)
    return parser.parse_args()


def main() -> None:
    arguments = parse_args()
    specifications = [parse_pair_set(value) for value in arguments.pair_set]
    result = audit(specifications, Path(arguments.run_map))
    output = Path(arguments.out_dir)
    atomic_json(output / "audit_card.json", result)
    atomic_text(output / "DATASHEET.md", render_datasheet(result))
    print(result["status"])
    for name, item in sorted(result["sets"].items()):
        print(
            f"{name} pairs={item['pairs']} parents={item['parents']} runs={item['runs']} "
            f"tasks={item['tasks']} hard_share={item['hard_pair_share']:.12f}"
        )


if __name__ == "__main__":
    main()
