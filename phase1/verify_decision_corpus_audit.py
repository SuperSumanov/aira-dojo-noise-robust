#!/usr/bin/env python3
"""Independent verifier for ``decision_corpus_audit_v1`` cards.

This file deliberately does not import the producer.  It reparses every pair
file, reconstructs physical-run membership from endpoint IDs, recomputes all
published support fields, and checks input hashes plus train/frozen isolation.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import os
import statistics
from pathlib import Path
from typing import Any, Sequence


PROTOCOL = "decision_corpus_audit_v1"
EDGES = (0.0, 1e-4, 3e-4, 1e-3, 3e-3, 1e-2, 3e-2, 1e-1, 3e-1, math.inf)
HARD = 1e-2


class VerificationError(RuntimeError):
    pass


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def portable_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def locate(root: Path, published: str) -> Path:
    candidate = Path(published)
    return candidate if candidate.is_absolute() else root / candidate


def quantile(values: Sequence[int], probability: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    low, high = math.floor(position), math.ceil(position)
    if low == high:
        return float(ordered[low])
    fraction = position - low
    return float(ordered[low] * (1.0 - fraction) + ordered[high] * fraction)


def bucket_name(left: float, right: float) -> str:
    right_text = "inf" if math.isinf(right) else f"{right:.12g}"
    return f"[{left:.12g},{right_text})"


def read_set(path: Path, partition: str, budget: int, run_of: dict[str, str]) -> list[dict[str, Any]]:
    expected_split = "train" if partition == "train" else "test"
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    required = {
        "better", "worse", "parent", "task", "budget", "intask_split", "gap_raw", "set_size"
    }
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            raw = json.loads(line)
            if not required <= set(raw):
                raise VerificationError(f"missing pair fields at {path}:{line_number}")
            if int(raw["budget"]) != budget or str(raw["intask_split"]) != expected_split:
                raise VerificationError(f"partition/budget mismatch at {path}:{line_number}")
            better, worse, parent = str(raw["better"]), str(raw["worse"]), str(raw["parent"])
            if better == worse or not better or not worse or not parent:
                raise VerificationError(f"degenerate pair at {path}:{line_number}")
            unordered = tuple(sorted((better, worse)))
            if unordered in seen:
                raise VerificationError(f"duplicate/reverse pair at {path}:{line_number}")
            seen.add(unordered)
            if better not in run_of or worse not in run_of:
                raise VerificationError(f"endpoint absent from run map at {path}:{line_number}")
            if run_of[better] != run_of[worse]:
                raise VerificationError(f"cross-run pair at {path}:{line_number}")
            run = run_of[better]
            parent_mapped = parent in run_of
            if parent_mapped and run_of[parent] != run:
                raise VerificationError(f"mapped parent crosses runs at {path}:{line_number}")
            if raw.get("run_id") is not None and str(raw["run_id"]) != run:
                raise VerificationError(f"declared run mismatch at {path}:{line_number}")
            try:
                gap = float(raw["gap_raw"])
            except (TypeError, ValueError) as exc:
                raise VerificationError(f"non-numeric gap at {path}:{line_number}") from exc
            if not math.isfinite(gap) or gap < 0 or int(raw["set_size"]) < 2:
                raise VerificationError(f"invalid gap/set_size at {path}:{line_number}")
            rows.append(
                {
                    "better": better,
                    "worse": worse,
                    "parent": parent,
                    "task": str(raw["task"]),
                    "run": run,
                    "gap": gap,
                    "size": int(raw["set_size"]),
                    "parent_mapped": parent_mapped,
                }
            )
    if not rows:
        raise VerificationError(f"empty pair file: {path}")
    return rows


def recompute(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    by_parent: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in rows:
        by_parent[row["parent"]].append(row)
    choices: list[dict[str, Any]] = []
    for parent, members in sorted(by_parent.items()):
        context = {(row["task"], row["run"], row["size"], row["parent_mapped"]) for row in members}
        if len(context) != 1:
            raise VerificationError(f"mixed choice-set context for {parent}")
        task, run, declared, parent_mapped = next(iter(context))
        candidates = sorted({row[key] for row in members for key in ("better", "worse")})
        wins = collections.Counter(row["better"] for row in members)
        expected = len(candidates) * (len(candidates) - 1) // 2
        complete = len(members) == expected
        strict = complete and sorted(wins[item] for item in candidates) == list(range(len(candidates)))
        choices.append(
            {
                "task": task,
                "run": run,
                "candidate_count": len(candidates),
                "declared": declared,
                "complete": complete,
                "strict": strict,
                "parent_mapped": parent_mapped,
            }
        )

    endpoint_occurrences = [row[key] for row in rows for key in ("better", "worse")]
    degree = collections.Counter(endpoint_occurrences)
    degree_values = list(degree.values())
    tasks = collections.Counter(row["task"] for row in rows)
    parent_tasks = collections.Counter(item["task"] for item in choices)
    size_histogram = collections.Counter(item["candidate_count"] for item in choices)
    gaps = {bucket_name(left, right): 0 for left, right in zip(EDGES, EDGES[1:])}
    for row in rows:
        for left, right in zip(EDGES, EDGES[1:]):
            if left <= row["gap"] < right:
                gaps[bucket_name(left, right)] += 1
                break
    hard_count = sum(row["gap"] < HARD for row in rows)
    return {
        "pairs": len(rows),
        "parents": len(choices),
        "endpoints": len(degree),
        "runs": len({row["run"] for row in rows}),
        "tasks": len(tasks),
        "complete_parents": sum(item["complete"] for item in choices),
        "strict_total_order_parents": sum(item["strict"] for item in choices),
        "declared_size_match_parents": sum(
            item["declared"] == item["candidate_count"] for item in choices
        ),
        "mapped_parent_choice_sets": sum(item["parent_mapped"] for item in choices),
        "orphan_parent_choice_sets": sum(not item["parent_mapped"] for item in choices),
        "candidate_count_histogram": {
            str(key): value for key, value in sorted(size_histogram.items())
        },
        "hard_threshold": HARD,
        "hard_pairs": hard_count,
        "hard_pair_share": hard_count / len(rows),
        "gap_bucket_counts": gaps,
        "endpoint_degree": {
            "median": float(statistics.median(degree_values)),
            "p95": quantile(degree_values, 0.95),
            "max": max(degree_values),
            "degree_gt_one_endpoints": sum(value > 1 for value in degree_values),
        },
        "dominant_task_pair_share": max(tasks.values()) / len(rows),
        "dominant_task_parent_share": max(parent_tasks.values()) / len(choices),
    }


def set_overlap(left: Sequence[dict[str, Any]], right: Sequence[dict[str, Any]]) -> dict[str, int]:
    left_pairs = {tuple(sorted((row["better"], row["worse"]))) for row in left}
    right_pairs = {tuple(sorted((row["better"], row["worse"]))) for row in right}
    left_endpoints = {row[key] for row in left for key in ("better", "worse")}
    right_endpoints = {row[key] for row in right for key in ("better", "worse")}
    return {
        "pairs": len(left_pairs & right_pairs),
        "endpoints": len(left_endpoints & right_endpoints),
        "parents": len({row["parent"] for row in left} & {row["parent"] for row in right}),
        "runs": len({row["run"] for row in left} & {row["run"] for row in right}),
    }


def verify(card_path: Path, root: Path) -> dict[str, Any]:
    card = json.loads(card_path.read_text(encoding="utf-8"))
    if card.get("protocol") != PROTOCOL:
        raise VerificationError("unexpected audit protocol")
    if card.get("status") != "VERIFIED_DECISION_CORPUS_AUDIT":
        raise VerificationError("producer card is not verified")
    expected_scope = {
        "reads_card_code": False,
        "reads_card_observations": False,
        "recomputes_label_noise": False,
        "recomputes_deployment_cost": False,
        "recomputes_prospective_protocol": False,
    }
    if card.get("scope") != expected_scope:
        raise VerificationError("scope declaration is missing or altered")
    producer = card.get("provenance", {}).get("producer_script", {})
    producer_path = locate(root, str(producer.get("path", "")))
    if not producer_path.is_file() or digest(producer_path) != producer.get("sha256"):
        raise VerificationError("producer script provenance mismatch")
    inputs = card.get("inputs")
    if not isinstance(inputs, dict) or "run_map" not in inputs:
        raise VerificationError("missing input manifest")
    resolved: dict[str, Path] = {}
    for name, record in inputs.items():
        path = locate(root, str(record["path"]))
        if digest(path) != str(record["sha256"]):
            raise VerificationError(f"input hash mismatch: {name}")
        resolved[name] = path
    run_of_raw = json.loads(resolved["run_map"].read_text(encoding="utf-8"))
    run_of = {str(key): str(value) for key, value in run_of_raw.items()}

    rows_by_name: dict[str, list[dict[str, Any]]] = {}
    recomputed_sets: dict[str, Any] = {}
    for name, path in sorted(resolved.items()):
        if name == "run_map":
            continue
        try:
            partition, budget_text = name.split(":b", 1)
            budget = int(budget_text)
        except (ValueError, TypeError) as exc:
            raise VerificationError(f"malformed pair-set name: {name}") from exc
        rows = read_set(path, partition, budget, run_of)
        rows_by_name[name] = rows
        recomputed_sets[name] = recompute(rows)
    if recomputed_sets != card.get("sets"):
        raise VerificationError("published set metrics differ from independent recomputation")

    isolation: dict[str, Any] = {}
    budgets = sorted(
        {int(name.split(":b", 1)[1]) for name in rows_by_name if name.startswith("train:b")}
    )
    for budget in budgets:
        train_name, frozen_name = f"train:b{budget}", f"frozen:b{budget}"
        if train_name not in rows_by_name or frozen_name not in rows_by_name:
            continue
        counts = set_overlap(rows_by_name[train_name], rows_by_name[frozen_name])
        isolation[f"b{budget}"] = {
            **counts,
            "passed": counts == {"pairs": 0, "endpoints": 0, "parents": 0, "runs": 0},
        }
    if isolation != card.get("same_budget_train_frozen_isolation"):
        raise VerificationError("published split isolation differs from recomputation")
    if not all(item["passed"] for item in isolation.values()):
        raise VerificationError("same-budget train/frozen isolation failed")
    expected_integrity = {
        "all_rows_true_physical_siblings": True,
        "all_choice_sets_context_consistent": True,
        "same_budget_train_frozen_isolation_evaluable": bool(isolation),
        "same_budget_train_frozen_isolated": True,
    }
    if card.get("integrity") != expected_integrity:
        raise VerificationError("integrity declaration differs from recomputation")
    return {
        "protocol": "independent_decision_corpus_audit_verifier_v1",
        "status": "INDEPENDENTLY_VERIFIED_DECISION_CORPUS_AUDIT",
        "source_card": {"path": card_path.as_posix(), "sha256": digest(card_path)},
        "verifier_script": {
            "path": portable_path(Path(__file__)),
            "sha256": digest(Path(__file__)),
        },
        "verified_pair_sets": len(recomputed_sets),
        "verified_input_hashes": len(resolved),
        "verified_same_budget_isolation": isolation,
        "imports_producer": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit-card", required=True)
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> None:
    arguments = parse_args()
    result = verify(Path(arguments.audit_card), Path(arguments.root))
    atomic_json(Path(arguments.output), result)
    print(result["status"])
    print(
        f"pair_sets={result['verified_pair_sets']} input_hashes={result['verified_input_hashes']}"
    )


if __name__ == "__main__":
    main()
