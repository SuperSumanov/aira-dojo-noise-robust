"""Independent verifier for the append-only exploratory v12 corpus and decisions.

This file intentionally does not import ``build_exploratory_v12`` or the decision builder.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path


BATCHES = (
    "gen2K2a",
    "gen2K2b",
    "gen2Q01",
    "gen2Q02",
    "gen2Q03",
    "gen2Q04",
    "gen2Q05",
    "gen2Q06",
    "gen2Q07",
    "gen2Q08",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--runs-root", type=Path, required=True)
    parser.add_argument("--combined", type=Path, required=True)
    parser.add_argument("--run-map", type=Path, required=True)
    return parser.parse_args()


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def id_run_index(path: Path) -> tuple[dict[str, str], int]:
    index: dict[str, str] = {}
    count = 0
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            count += 1
            card_id = row["id"]
            if card_id in index:
                raise AssertionError(f"duplicate card id: {card_id}")
            index[card_id] = row["run_id"]
    return index, count


def usable_journal_ids(path: Path, task: str) -> list[str]:
    output = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        node = json.loads(line)
        if node.get("step") == 0 and node.get("code", "") == "":
            continue
        metric = node.get("metric_info") or {}
        score = metric.get("score")
        thresholds = [metric.get(f"{name}_threshold") for name in ("gold", "silver", "bronze")]
        try:
            finite = score is not None and math.isfinite(float(score))
        except (TypeError, ValueError):
            finite = False
        if finite and all(value is not None for value in thresholds):
            output.append(f"{task}__{node.get('id', node.get('step'))}")
    return output


def starts_with(path: Path, prefix: Path) -> bool:
    remaining = prefix.stat().st_size
    with path.open("rb") as full, prefix.open("rb") as expected:
        while remaining:
            size = min(1024 * 1024, remaining)
            if full.read(size) != expected.read(size):
                return False
            remaining -= size
    return True


def main() -> None:
    args = parse_args()
    phase1 = args.repo / "phase1"
    base = phase1 / "cards_current_v11.jsonl"
    extension = phase1 / "cards_extension_exploratory_v12.jsonl"
    audit = json.loads((phase1 / "exploratory_v12_audit.json").read_text())
    base_index, base_count = id_run_index(base)
    extension_rows = rows(extension)
    run_map = json.loads(args.run_map.read_text())

    assert digest(base) == audit["base"]["sha256"]
    assert digest(extension) == audit["extension"]["sha256"]
    assert digest(args.combined) == audit["combined"]["sha256"]
    assert digest(args.run_map) == audit["run_map"]["sha256"]
    assert starts_with(args.combined, base)
    with args.combined.open("rb") as handle:
        handle.seek(base.stat().st_size)
        assert handle.read() == extension.read_bytes()
    assert base_count == audit["base"]["cards"]
    assert len(extension_rows) == audit["extension"]["cards"]
    assert audit["combined"]["cards"] == base_count + len(extension_rows)

    base_ids = set(base_index)
    extension_ids = {row["id"] for row in extension_rows}
    assert len(base_ids) == base_count
    assert len(extension_ids) == len(extension_rows)
    assert not (base_ids & extension_ids)
    assert set(run_map) == base_ids | extension_ids
    assert all(run_map[card_id] == run_id for card_id, run_id in base_index.items())
    assert all(run_map[row["id"]] == row["run_id"] for row in extension_rows)

    tasks_by_run: dict[str, set[str]] = defaultdict(set)
    for row in extension_rows:
        tasks_by_run[row["run_id"]].add(row["task"]["name"])
        assert row["provenance"]["label_status"] == "finite"
        parent = (row.get("lineage") or {}).get("parent_id")
        if parent in extension_ids:
            assert run_map[parent] == row["run_id"]
    assert all(len(tasks) == 1 for tasks in tasks_by_run.values())

    expected_ids_by_run: dict[str, set[str]] = {}
    expected_accepted: set[tuple[str, str]] = set()
    expected_rejected: set[tuple[str, str]] = set()
    for batch in BATCHES:
        root = args.runs_root / f"user_yzyang4_issue_mcts_data_{batch}"
        manifest_paths = list(root.glob("srun_pool/*/manifest.json"))
        assert len(manifest_paths) == 1
        manifest = json.loads(manifest_paths[0].read_text())
        for task_id, meta in manifest["tasks"].items():
            exp = Path(meta["experiment_dir"])
            journal = exp / "checkpoint/journal.jsonl"
            state_path = exp / "checkpoint/state.json"
            searches = list(exp.glob("*_MCTS_search_data.json"))
            integrity = (
                meta.get("status") == "completed"
                and meta.get("exit_code") == 0
                and journal.exists()
                and journal.stat().st_size > 0
                and state_path.exists()
                and state_path.stat().st_size > 0
                and len(searches) == 1
            )
            usable_ids: list[str] = []
            if integrity:
                state = json.loads(state_path.read_text())
                search = json.loads(searches[0].read_text())
                journal_count = sum(1 for line in journal.open() if line.strip())
                integrity = (
                    isinstance(search, dict)
                    and isinstance(search.get("nodes"), list)
                    and len(search["nodes"]) == journal_count
                    and state.get("current_step") == journal_count
                )
                if integrity:
                    usable_ids = usable_journal_ids(journal, meta["task_name"])
            key = (batch, task_id)
            if integrity and usable_ids:
                expected_accepted.add(key)
                run_id = f"exploratory-20260812:{batch}:{task_id}"
                expected_ids_by_run[run_id] = set(usable_ids)
            else:
                expected_rejected.add(key)

    actual_accepted = {(item["batch"], item["task_id"]) for item in audit["accepted_runs"]}
    actual_rejected = {(item["batch"], item["task_id"]) for item in audit["rejected_runs"]}
    assert expected_accepted == actual_accepted
    assert expected_rejected == actual_rejected
    assert actual_accepted.isdisjoint(actual_rejected)
    assert set(expected_ids_by_run) == set(tasks_by_run)
    actual_ids_by_run: dict[str, set[str]] = defaultdict(set)
    for row in extension_rows:
        actual_ids_by_run[row["run_id"]].add(row["id"])
    assert dict(actual_ids_by_run) == expected_ids_by_run

    decision_root = phase1 / "v12_exploratory_decision"
    frozen_nodes: set[str] = set()
    new_pair_counts = {}
    for budget in range(3):
        frozen = decision_root / f"decision_frozen_v12x_b{budget}.jsonl"
        base_frozen = phase1 / "v11_decision" / f"decision_frozen_v11_b{budget}.jsonl"
        train = decision_root / f"decision_train_v12x_b{budget}.jsonl"
        base_train = phase1 / "v11_decision" / f"decision_train_v11_b{budget}.jsonl"
        extra = decision_root / f"decision_extension_v12x_b{budget}.jsonl"
        base_extra = phase1 / "v11_decision" / f"decision_extension_v11_b{budget}.jsonl"
        assert frozen.read_bytes() == base_frozen.read_bytes()
        assert starts_with(train, base_train)
        assert starts_with(extra, base_extra)
        frozen_rows = rows(frozen)
        train_rows = rows(train)
        extra_rows = rows(extra)
        frozen_nodes |= {row[key] for row in frozen_rows for key in ("better", "worse")}
        keys = [(row["better"], row["worse"], row["budget"]) for row in train_rows]
        assert len(keys) == len(set(keys))
        keys = [(row["better"], row["worse"], row["budget"]) for row in extra_rows]
        assert len(keys) == len(set(keys))
        new_train = train_rows[len(rows(base_train)) :]
        new_extra = extra_rows[len(rows(base_extra)) :]
        assert all(row["better"] in extension_ids and row["worse"] in extension_ids for row in new_train + new_extra)
        new_pair_counts[str(budget)] = {"train": len(new_train), "extension": len(new_extra)}
    all_train_nodes = {
        row[key]
        for budget in range(3)
        for row in rows(decision_root / f"decision_train_v12x_b{budget}.jsonl")
        for key in ("better", "worse")
    }
    assert not (frozen_nodes & all_train_nodes)

    task_count = len({task for task_set in tasks_by_run.values() for task in task_set})

    print(
        "EXPLORATORY_V12_INDEPENDENT_VERIFY_PASS",
        f"base_cards={base_count}",
        f"extension_cards={len(extension_rows)}",
        f"accepted_runs={len(actual_accepted)}",
        f"rejected_runs={len(actual_rejected)}",
        f"runs={len(tasks_by_run)}",
        f"tasks={task_count}",
        f"new_pairs={json.dumps(new_pair_counts, sort_keys=True)}",
        f"frozen_train_overlap={len(frozen_nodes & all_train_nodes)}",
    )


if __name__ == "__main__":
    main()
