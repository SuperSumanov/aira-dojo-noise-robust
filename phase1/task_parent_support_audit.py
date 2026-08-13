#!/usr/bin/env python3
"""Audit train-only support for task-conditioned, parent-level ranking.

The audit consumes only the v11 training-pair file and the already locked
training OOF fold assignment.  It deliberately has no frozen/test input and
does not fit a model.  Its purpose is to decide, from support rather than
outcomes, which task-conditioning designs are statistically feasible.
"""

from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import math
import os
import statistics
from pathlib import Path
from typing import Any, Iterable


class IntegrityError(RuntimeError):
    pass


REQUIRED_FIELDS = {
    "better",
    "worse",
    "parent",
    "task",
    "run_id",
    "budget",
    "intask_split",
    "gap_raw",
    "set_size",
}
FORBIDDEN_PATH_TOKENS = ("frozen", "test", "held")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalized_lf_sha256(path: Path) -> str:
    """Hash UTF-8 text after canonical LF conversion and one final newline."""
    normalized = "\n".join(path.read_text(encoding="utf-8").splitlines()) + "\n"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def reject_forbidden_path(path: Path, label: str) -> None:
    lowered = path.name.lower()
    found = [token for token in FORBIDDEN_PATH_TOKENS if token in lowered]
    if found:
        raise IntegrityError(f"{label} path contains forbidden token(s): {found}")


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def atomic_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    fieldnames = list(rows[0]) if rows else ["task"]
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def load_pairs(path: Path) -> list[dict[str, Any]]:
    reject_forbidden_path(path, "training-pair")
    rows: list[dict[str, Any]] = []
    unordered_seen: set[tuple[str, str]] = set()
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line:
            continue
        raw = json.loads(line)
        missing = REQUIRED_FIELDS - set(raw)
        if missing:
            raise IntegrityError(f"pair line {line_number} missing {sorted(missing)}")
        if str(raw["intask_split"]) != "train" or int(raw["budget"]) != 0:
            raise IntegrityError(f"pair line {line_number} is not train/budget-zero")
        better, worse = str(raw["better"]), str(raw["worse"])
        if not better or not worse or better == worse:
            raise IntegrityError(f"degenerate pair at line {line_number}")
        unordered = tuple(sorted((better, worse)))
        if unordered in unordered_seen:
            raise IntegrityError(f"duplicate/reverse pair at line {line_number}")
        unordered_seen.add(unordered)
        gap = float(raw["gap_raw"])
        set_size = int(raw["set_size"])
        if not math.isfinite(gap) or gap < 0 or set_size < 2:
            raise IntegrityError(f"invalid gap/set_size at line {line_number}")
        rows.append(
            {
                "row_index": len(rows),
                "better": better,
                "worse": worse,
                "parent": str(raw["parent"]),
                "task": str(raw["task"]),
                "run": str(raw["run_id"]),
                "gap_raw": gap,
                "declared_set_size": set_size,
            }
        )
    if not rows:
        raise IntegrityError("empty training-pair file")
    return rows


def load_locked_folds(path: Path, rows: list[dict[str, Any]]) -> tuple[list[int], int]:
    reject_forbidden_path(path, "baseline-OOF")
    with path.open("r", encoding="utf-8", newline="") as handle:
        emitted = list(csv.DictReader(handle))
    if len(emitted) != len(rows):
        raise IntegrityError("baseline OOF row count differs from training pairs")
    folds: list[int] = []
    run_fold: dict[str, int] = {}
    required = {"row_index", "task", "run", "parent", "better", "worse", "fold"}
    for index, (row, output) in enumerate(zip(rows, emitted)):
        missing = required - set(output)
        if missing:
            raise IntegrityError(f"baseline OOF missing {sorted(missing)}")
        if int(output["row_index"]) != index:
            raise IntegrityError(f"baseline OOF row index mismatch at {index}")
        for key in ("task", "run", "parent", "better", "worse"):
            if str(output[key]) != str(row[key]):
                raise IntegrityError(f"baseline OOF {key} mismatch at {index}")
        fold = int(output["fold"])
        if fold < 0:
            raise IntegrityError(f"negative fold at {index}")
        previous = run_fold.setdefault(row["run"], fold)
        if previous != fold:
            raise IntegrityError(f"physical run spans folds: {row['run']}")
        folds.append(fold)
    fold_count = max(folds) + 1
    if set(folds) != set(range(fold_count)):
        raise IntegrityError("fold IDs are not contiguous")
    return folds, fold_count


def parent_records(rows: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
    grouped: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in rows:
        grouped[row["parent"]].append(row)
    records: dict[str, dict[str, Any]] = {}
    candidate_histogram: collections.Counter[int] = collections.Counter()
    for parent, items in grouped.items():
        contexts = {(item["task"], item["run"], item["declared_set_size"]) for item in items}
        if len(contexts) != 1:
            raise IntegrityError(f"parent context is inconsistent: {parent}")
        task, run, declared_set_size = next(iter(contexts))
        candidates = sorted(
            {str(item[key]) for item in items for key in ("better", "worse")}
        )
        directed = {(item["better"], item["worse"]) for item in items}
        if len(directed) != len(items):
            raise IntegrityError(f"duplicate directed edge within parent: {parent}")
        expected_edges = len(candidates) * (len(candidates) - 1) // 2
        edge_complete = len(items) == expected_edges
        declared_size_matches = declared_set_size == len(candidates)
        wins = collections.Counter(item["better"] for item in items)
        losses = collections.Counter(item["worse"] for item in items)
        degree_sequence = sorted(wins[candidate] for candidate in candidates)
        strict_total_order = edge_complete and degree_sequence == list(range(len(candidates)))
        winners = [candidate for candidate in candidates if wins[candidate] == len(candidates) - 1]
        records[parent] = {
            "task": task,
            "run": run,
            "pairs": len(items),
            "candidates": len(candidates),
            "declared_set_size": declared_set_size,
            "edge_complete": edge_complete,
            "declared_size_matches": declared_size_matches,
            "strict_total_order": strict_total_order,
            "unique_winner": len(winners) == 1,
            "winner": winners[0] if len(winners) == 1 else None,
            "endpoints": candidates,
            "loss_edges": sum(losses.values()),
        }
        candidate_histogram[len(candidates)] += 1
    return records, dict(sorted(candidate_histogram.items()))


def median(values: Iterable[int]) -> float:
    materialized = list(values)
    return float(statistics.median(materialized)) if materialized else 0.0


def display_path(path: Path) -> str:
    """Keep result metadata portable while hashes retain exact identity."""
    return path.name if path.is_absolute() else path.as_posix()


def per_task_rows(
    rows: list[dict[str, Any]],
    folds: list[int],
    fold_count: int,
    parents: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    tasks = sorted({row["task"] for row in rows})
    output: list[dict[str, Any]] = []
    for task in tasks:
        indices = [index for index, row in enumerate(rows) if row["task"] == task]
        task_rows = [rows[index] for index in indices]
        task_parents = {row["parent"] for row in task_rows}
        task_runs = {row["run"] for row in task_rows}
        endpoints = {
            row[key] for row in task_rows for key in ("better", "worse")
        }
        complete = {parent for parent in task_parents if parents[parent]["edge_complete"]}
        strict = {parent for parent in task_parents if parents[parent]["strict_total_order"]}
        multiway = {parent for parent in task_parents if parents[parent]["candidates"] >= 3}
        pairs_by_run = collections.Counter(row["run"] for row in task_rows)
        fold_support: list[dict[str, int]] = []
        for fold in range(fold_count):
            valid_indices = [index for index in indices if folds[index] == fold]
            fit_indices = [index for index in indices if folds[index] != fold]
            valid_rows = [rows[index] for index in valid_indices]
            fit_rows = [rows[index] for index in fit_indices]
            fold_support.append(
                {
                    "fold": fold,
                    "valid_pairs": len(valid_rows),
                    "valid_runs": len({row["run"] for row in valid_rows}),
                    "valid_parents": len({row["parent"] for row in valid_rows}),
                    "fit_pairs": len(fit_rows),
                    "fit_runs": len({row["run"] for row in fit_rows}),
                    "fit_parents": len({row["parent"] for row in fit_rows}),
                }
            )
        active = [item for item in fold_support if item["valid_pairs"] > 0]
        output.append(
            {
                "task": task,
                "pairs": len(task_rows),
                "runs": len(task_runs),
                "parents": len(task_parents),
                "endpoints": len(endpoints),
                "complete_parents": len(complete),
                "strict_total_order_parents": len(strict),
                "multiway_parents": len(multiway),
                "multiway_parent_share": len(multiway) / len(task_parents),
                "pair_count_per_run_min": min(pairs_by_run.values()),
                "pair_count_per_run_median": median(pairs_by_run.values()),
                "pair_count_per_run_max": max(pairs_by_run.values()),
                "outer_active_folds": len(active),
                "outer_min_fit_runs_when_active": min(item["fit_runs"] for item in active),
                "outer_min_fit_parents_when_active": min(item["fit_parents"] for item in active),
                "outer_min_valid_runs_when_active": min(item["valid_runs"] for item in active),
                "inner_3fold_run_feasible_in_every_active_outer_fold": all(
                    item["fit_runs"] >= 3 for item in active
                ),
                "fold_support": fold_support,
            }
        )
    return output


def audit(train_pairs: Path, baseline_oof: Path) -> dict[str, Any]:
    rows = load_pairs(train_pairs)
    folds, fold_count = load_locked_folds(baseline_oof, rows)
    parents, candidate_histogram = parent_records(rows)
    tasks = per_task_rows(rows, folds, fold_count, parents)
    run_folds: dict[str, int] = {}
    for row, fold in zip(rows, folds):
        run_folds.setdefault(row["run"], fold)
    multiway_parents = {parent for parent, item in parents.items() if item["candidates"] >= 3}
    multiway_pairs = sum(parents[parent]["pairs"] for parent in multiway_parents)
    complete = sum(item["edge_complete"] for item in parents.values())
    strict = sum(item["strict_total_order"] for item in parents.values())
    size_match = sum(item["declared_size_matches"] for item in parents.values())
    unique_winner = sum(item["unique_winner"] for item in parents.values())
    return {
        "status": "AUDIT_COMPLETE",
        "protocol": "task_parent_support_audit_v1",
        "frozen_read": False,
        "inputs": {
            "train_pairs": display_path(train_pairs),
            "train_pairs_sha256": sha256(train_pairs),
            "train_pairs_normalized_lf_sha256": normalized_lf_sha256(train_pairs),
            "baseline_oof": display_path(baseline_oof),
            "baseline_oof_sha256": sha256(baseline_oof),
            "baseline_oof_normalized_lf_sha256": normalized_lf_sha256(baseline_oof),
        },
        "global": {
            "pairs": len(rows),
            "runs": len(run_folds),
            "tasks": len(tasks),
            "parents": len(parents),
            "endpoints": len({row[key] for row in rows for key in ("better", "worse")}),
            "outer_folds": fold_count,
            "physical_run_fold_overlap": 0,
            "complete_parents": complete,
            "complete_parent_share": complete / len(parents),
            "declared_size_match_parents": size_match,
            "strict_total_order_parents": strict,
            "unique_winner_parents": unique_winner,
            "candidate_count_histogram": candidate_histogram,
            "multiway_parents": len(multiway_parents),
            "multiway_parent_share": len(multiway_parents) / len(parents),
            "multiway_pairs": multiway_pairs,
            "multiway_pair_share": multiway_pairs / len(rows),
        },
        "per_fold": [
            {
                "fold": fold,
                "pairs": sum(item == fold for item in folds),
                "runs": sum(value == fold for value in run_folds.values()),
                "tasks": len({rows[index]["task"] for index, value in enumerate(folds) if value == fold}),
                "parents": len({rows[index]["parent"] for index, value in enumerate(folds) if value == fold}),
            }
            for fold in range(fold_count)
        ],
        "per_task": tasks,
    }


def csv_projection(payload: dict[str, Any]) -> list[dict[str, Any]]:
    excluded = {"fold_support"}
    return [
        {key: value for key, value in item.items() if key not in excluded}
        for item in payload["per_task"]
    ]


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train-pairs", required=True, type=Path)
    parser.add_argument("--baseline-oof", required=True, type=Path)
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-csv", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = arguments()
    payload = audit(args.train_pairs, args.baseline_oof)
    atomic_json(args.output_json, payload)
    atomic_csv(args.output_csv, csv_projection(payload))
    global_stats = payload["global"]
    print(
        payload["status"],
        f"pairs={global_stats['pairs']}",
        f"runs={global_stats['runs']}",
        f"parents={global_stats['parents']}",
        f"multiway_parent_share={global_stats['multiway_parent_share']:.6f}",
        f"strict_total_order={global_stats['strict_total_order_parents']}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
