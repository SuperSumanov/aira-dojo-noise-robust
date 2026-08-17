#!/usr/bin/env python3
"""Audit whether v11 can support an evaluator-verified experience-memory study.

This is a support/leakage audit, not a method evaluation.  Every physical run
touching the frozen decision pairs is excluded from the candidate memory pool.
The released source-opportunity status summary is used only for aggregate
train-side failure counts; raw journals, exception text, stdout, and credentials
are never read.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable


PAIR_FILES = tuple(f"decision_clean_b{i}.jsonl" for i in range(3))


def _rows(path: Path) -> Iterable[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{line_number}: row is not an object")
            yield row


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _finite(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _task_name(card: dict[str, Any]) -> str:
    task = card.get("task")
    if isinstance(task, dict):
        name = task.get("name")
    else:
        name = task
    if not isinstance(name, str) or not name:
        raise ValueError(f"card {card.get('id')!r} lacks a canonical task name")
    return name


def _nontrivial_description(card: dict[str, Any]) -> bool:
    task = card.get("task")
    if not isinstance(task, dict):
        return False
    description = task.get("desc") or task.get("description")
    return isinstance(description, str) and bool(description.strip()) and description.strip() != _task_name(card)


def _static_artifact_writer_marker(card: dict[str, Any]) -> bool:
    code = str(card.get("code") or "").lower()
    return "to_csv" in code and ("submission" in code or "sample_submission" in code)


def _best_by_run(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_run: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for card in cards:
        y_norm = (card.get("label") or {}).get("y_norm")
        if _finite(y_norm):
            by_run[str(card["run_id"])].append(card)
    # y_norm is already direction-normalized, so larger is always better.
    return [
        max(group, key=lambda card: float(card["label"]["y_norm"]))
        for _, group in sorted(by_run.items())
    ]


def audit(repo_root: Path) -> dict[str, Any]:
    phase1 = repo_root / "phase1"
    cards_path = phase1 / "cards_current_v11.jsonl"
    pair_paths = [phase1 / name for name in PAIR_FILES]
    status_path = (
        phase1
        / "results"
        / "source_opportunity_journal_status_v11_20260815_42cb6b1"
        / "verification_summary.json"
    )

    cards = {str(row["id"]): row for row in _rows(cards_path)}
    pairs = [row for path in pair_paths for row in _rows(path)]
    split_counts = collections.Counter(str(row.get("intask_split")) for row in pairs)
    if set(split_counts) != {"test"}:
        raise ValueError(f"decision_clean inputs are not frozen-test-only: {dict(split_counts)}")

    endpoint_ids: set[str] = set()
    referenced_parent_ids: set[str] = set()
    frozen_runs: set[str] = set()
    frozen_tasks: set[str] = set()
    for row in pairs:
        better = str(row["better"])
        worse = str(row["worse"])
        if better not in cards or worse not in cards:
            raise ValueError("a frozen pair endpoint is absent from cards_current_v11")
        left, right = cards[better], cards[worse]
        if str(left["run_id"]) != str(right["run_id"]):
            raise ValueError("a frozen pair crosses physical runs")
        if _task_name(left) != _task_name(right):
            raise ValueError("a frozen pair crosses tasks")
        endpoint_ids.update((better, worse))
        frozen_runs.add(str(left["run_id"]))
        frozen_tasks.add(_task_name(left))
        if row.get("parent"):
            referenced_parent_ids.add(str(row["parent"]))

    memory_cards = [card for card in cards.values() if str(card["run_id"]) not in frozen_runs]
    memory_ids = {str(card["id"]) for card in memory_cards}
    memory_runs = {str(card["run_id"]) for card in memory_cards}
    if memory_ids & endpoint_ids:
        raise AssertionError("frozen endpoint leaked into the memory pool")
    if memory_runs & frozen_runs:
        raise AssertionError("frozen physical run leaked into the memory pool")

    finite_cards = [
        card for card in memory_cards if _finite((card.get("label") or {}).get("y_norm"))
    ]
    best_episodes = _best_by_run(memory_cards)
    writer_episodes = [card for card in best_episodes if _static_artifact_writer_marker(card)]
    episodes_per_task = collections.Counter(_task_name(card) for card in best_episodes)
    writer_per_task = collections.Counter(_task_name(card) for card in writer_episodes)
    memory_tasks = set(episodes_per_task)

    nonempty_memory_hashes = {
        hashlib.sha256(str(card.get("code") or "").encode()).hexdigest()
        for card in memory_cards
        if str(card.get("code") or "")
    }
    nonempty_frozen_hashes = {
        hashlib.sha256(str(cards[card_id].get("code") or "").encode()).hexdigest()
        for card_id in endpoint_ids
        if str(cards[card_id].get("code") or "")
    }

    status = json.loads(status_path.read_text(encoding="utf-8"))
    train_status = status["roles"]["train"]
    train_categories = train_status["categories"]
    train_targets = int(train_status["target_missing_identities"])
    train_recovered = int(train_status["unique_nodes_recovered"])
    if train_recovered != sum(int(value) for value in train_categories.values()):
        raise ValueError("train source-status category counts do not sum to recovered nodes")

    frozen_tasks_with_5 = sorted(task for task in frozen_tasks if episodes_per_task[task] >= 5)
    frozen_tasks_with_5_writers = sorted(task for task in frozen_tasks if writer_per_task[task] >= 5)
    parent_ids_present = referenced_parent_ids & set(cards)

    return {
        "protocol": "experience_memory_support_audit_v1",
        "inputs": {
            "cards": {"path": "phase1/cards_current_v11.jsonl", "sha256": _sha256(cards_path)},
            "pairs": [
                {"path": f"phase1/{path.name}", "sha256": _sha256(path)} for path in pair_paths
            ],
            "train_failure_status_summary": {
                "path": str(status_path.relative_to(repo_root)).replace("\\", "/"),
                "sha256": _sha256(status_path),
            },
        },
        "frozen_exclusion": {
            "pair_rows": len(pairs),
            "pair_split_rows": dict(sorted(split_counts.items())),
            "endpoint_cards": len(endpoint_ids),
            "referenced_parent_ids": len(referenced_parent_ids),
            "referenced_parent_ids_present_in_v11": len(parent_ids_present),
            "physical_runs": len(frozen_runs),
            "tasks": len(frozen_tasks),
            "memory_endpoint_card_overlap": len(memory_ids & endpoint_ids),
            "memory_physical_run_overlap": len(memory_runs & frozen_runs),
            "nonempty_exact_code_hash_overlap": len(nonempty_memory_hashes & nonempty_frozen_hashes),
        },
        "verified_success_memory": {
            "cards_after_run_exclusion": len(memory_cards),
            "physical_runs": len(memory_runs),
            "tasks": len(memory_tasks),
            "finite_y_norm_cards": len(finite_cards),
            "best_episode_per_physical_run": len(best_episodes),
            "best_episodes_with_static_artifact_writer_marker": len(writer_episodes),
            "static_marker_is_execution_verification": False,
            "tasks_with_at_least_5_best_episodes": sum(value >= 5 for value in episodes_per_task.values()),
            "tasks_with_at_least_5_writer_marked_best_episodes": sum(
                value >= 5 for value in writer_per_task.values()
            ),
        },
        "train_failure_status_memory": {
            "target_missing_sibling_identities": train_targets,
            "recovered_status_nodes": train_recovered,
            "unrecovered_status_nodes": train_targets - train_recovered,
            "categories": dict(sorted(train_categories.items())),
            "contains_actionable_diagnostics": False,
            "reads_raw_journals_or_exception_text": False,
        },
        "generalization_support": {
            "frozen_tasks": len(frozen_tasks),
            "frozen_tasks_with_any_same_task_success_memory": len(frozen_tasks & memory_tasks),
            "frozen_tasks_with_at_least_5_best_episodes": len(frozen_tasks_with_5),
            "frozen_tasks_with_at_least_5_writer_marked_best_episodes": len(
                frozen_tasks_with_5_writers
            ),
            "frozen_tasks_without_any_same_task_memory": sorted(frozen_tasks - memory_tasks),
            "cards_with_nontrivial_task_description": sum(
                _nontrivial_description(card) for card in memory_cards
            ),
            "supports_seen_task_memory_baseline": frozen_tasks <= memory_tasks,
            "supports_unseen_task_generalization_claim": False,
            "supports_causal_method_claim": False,
        },
        "per_task_best_episodes": dict(sorted(episodes_per_task.items())),
        "per_task_writer_marked_best_episodes": dict(sorted(writer_per_task.items())),
        "decision": {
            "support_audit_passed": True,
            "allowed_next_step": "train-only data-asset construction and preregistration",
            "paid_experiment_authorized": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("repo_root", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = audit(args.repo_root.resolve())
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
