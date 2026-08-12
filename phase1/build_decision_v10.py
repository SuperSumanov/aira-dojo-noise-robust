"""Build leakage-safe v10 decision-pair artifacts without moving the frozen test set.

The historical ``decision_clean_b*.jsonl`` files are immutable evaluation inputs.  This
builder separates each budget into three explicit roles:

* ``decision_train_v10_bK.jsonl``: training rows from non-held physical runs;
* ``decision_frozen_v10_bK.jsonl``: the finite, valid subset of the historical test;
* ``decision_extension_v10_bK.jsonl``: rows from newly held v10 runs, reported separately.

Old run assignments are read from ``runsplit_holdruns.json``.  Only runs outside its
recorded universe are assigned, deterministically with seed 7.  The builder fails closed
unless every valid historical frozen pair is reproduced with the same orientation and no
frozen-test node appears in training.

Usage:
    python phase1/build_decision_v10.py \
      --cards phase1/cards_current_v10.jsonl \
      --old-cards phase1/cards_current_v9.jsonl \
      --out-dir phase1/v10_decision
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import itertools
import json
import math
import os
import random
import tempfile
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cards", default="phase1/cards_current_v10.jsonl")
    parser.add_argument("--old-cards", default="phase1/cards_current_v9.jsonl")
    parser.add_argument("--run-map", default="phase1/card_run_map.json")
    parser.add_argument("--orientation", default="phase1/task_orientation.json")
    parser.add_argument("--prior-hold", default="phase1/runsplit_holdruns.json")
    parser.add_argument("--frozen-prefix", default="phase1/decision_clean_b")
    parser.add_argument("--out-dir", default="phase1/v10_decision")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--budgets", default="0,1,2")
    return parser.parse_args()


def load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def finite_label(card: dict) -> float | None:
    try:
        value = float((card.get("label") or {}).get("graded"))
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def has_nonfinite(value: object) -> bool:
    if isinstance(value, float):
        return not math.isfinite(value)
    if isinstance(value, dict):
        return any(has_nonfinite(child) for child in value.values())
    if isinstance(value, list):
        return any(has_nonfinite(child) for child in value)
    return False


def canonical_hash(rows: list[dict]) -> str:
    encoded = [
        json.dumps(row, sort_keys=True, separators=(",", ":"), allow_nan=False)
        for row in rows
    ]
    return hashlib.sha256("\n".join(sorted(encoded)).encode()).hexdigest()


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def atomic_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, allow_nan=False, sort_keys=True) + "\n")
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def main() -> None:
    args = parse_args()
    budgets = tuple(int(item) for item in args.budgets.split(","))
    cards_rows = load_jsonl(Path(args.cards))
    old_rows = load_jsonl(Path(args.old_cards))
    cards = {row["id"]: row for row in cards_rows}
    old_ids = {row["id"] for row in old_rows}
    if not old_ids <= cards.keys():
        raise RuntimeError(f"v10 lost {len(old_ids - cards.keys())} historical card ids")

    labels = {card_id: finite_label(card) for card_id, card in cards.items()}
    valid_ids = {card_id for card_id, value in labels.items() if value is not None}
    run_of = json.load(Path(args.run_map).open())
    orientation = json.load(Path(args.orientation).open())
    prior = json.load(Path(args.prior_hold).open())
    if not isinstance(prior, dict) or "hold" not in prior or "all" not in prior:
        raise RuntimeError("prior hold manifest must contain both 'hold' and 'all'")
    prior_hold = set(prior["hold"])
    prior_all = set(prior["all"])
    if not prior_hold <= prior_all:
        raise RuntimeError("prior held runs are not a subset of the prior universe")

    task_of_run: dict[str, str] = {}
    for card in cards_rows:
        card_id = card["id"]
        if card_id not in run_of:
            raise RuntimeError(f"card missing from run map: {card_id}")
        run_id = run_of[card_id]
        task = card["task"]["name"]
        previous = task_of_run.setdefault(run_id, task)
        if previous != task:
            raise RuntimeError(f"run mixes tasks: {run_id}")

    rng = random.Random(args.seed)
    new_by_task: dict[str, list[str]] = collections.defaultdict(list)
    for run_id, task in task_of_run.items():
        if run_id not in prior_all:
            new_by_task[task].append(run_id)
    hold = set(prior_hold)
    new_hold: set[str] = set()
    for task in sorted(new_by_task):
        run_ids = sorted(new_by_task[task])
        rng.shuffle(run_ids)
        selected = set(run_ids[int(0.8 * len(run_ids)):])
        hold.update(selected)
        new_hold.update(selected)

    children: dict[str, list[str]] = collections.defaultdict(list)
    for card_id, card in cards.items():
        parent = (card.get("lineage") or {}).get("parent_id")
        if parent:
            children[parent].append(card_id)

    def descendants_in_order(card_id: str) -> list[str]:
        output: list[str] = []
        stack = list(children.get(card_id, []))
        seen: set[str] = set()
        while stack:
            node = stack.pop()
            if node in seen or node not in cards:
                continue
            seen.add(node)
            if node in valid_ids:
                output.append(node)
            stack.extend(children.get(node, []))
        return sorted(
            output,
            key=lambda node: (
                ((cards[node].get("lineage") or {}).get("step") or 0),
                node,
            ),
        )

    descendants = {card_id: descendants_in_order(card_id) for card_id in valid_ids}

    def value(card_id: str, budget: int) -> float | None:
        if card_id not in valid_ids:
            return None
        if budget and len(descendants[card_id]) < budget:
            return None
        task = cards[card_id]["task"]["name"]
        choose = min if orientation.get(task, False) else max
        values = [labels[card_id]]
        if budget:
            values.extend(labels[node] for node in descendants[card_id][:budget])
        return choose(values)

    generated: list[dict] = []
    for parent, raw_children in children.items():
        candidates = [card_id for card_id in raw_children if card_id in valid_ids]
        if len(candidates) < 2:
            continue
        task = cards[candidates[0]]["task"]["name"]
        if task not in orientation:
            continue
        run_ids = {run_of[card_id] for card_id in candidates}
        if len(run_ids) != 1:
            raise RuntimeError(f"sibling set crosses physical runs: {parent}")
        run_id = next(iter(run_ids))
        split = "test" if run_id in hold else "train"
        lower = orientation[task]
        for budget in budgets:
            for left, right in itertools.combinations(candidates, 2):
                left_value = value(left, budget)
                right_value = value(right, budget)
                if left_value is None or right_value is None or left_value == right_value:
                    continue
                better, worse = (
                    (left, right)
                    if ((left_value < right_value) if lower else (left_value > right_value))
                    else (right, left)
                )
                generated.append(
                    {
                        "task": task,
                        "better": better,
                        "worse": worse,
                        "budget": budget,
                        "parent": parent,
                        "set_size": len(candidates),
                        "gap_raw": round(abs(left_value - right_value), 6),
                        "intask_split": split,
                        "loto_fold": task,
                        "clears_tau": None,
                        "src": "decision_v10",
                        "run_id": run_id,
                    }
                )

    out_dir = Path(args.out_dir)
    frozen_test_nodes: set[str] = set()
    audit: dict[str, object] = {
        "inputs": {
            "cards": args.cards,
            "cards_sha256": hashlib.sha256(Path(args.cards).read_bytes()).hexdigest(),
            "old_cards": args.old_cards,
            "old_cards_sha256": hashlib.sha256(Path(args.old_cards).read_bytes()).hexdigest(),
            "run_map": args.run_map,
            "run_map_sha256": hashlib.sha256(Path(args.run_map).read_bytes()).hexdigest(),
            "seed": args.seed,
        },
        "corpus": {
            "cards": len(cards),
            "valid_cards": len(valid_ids),
            "quarantined_cards": len(cards) - len(valid_ids),
            "old_cards": len(old_ids),
            "runs": len(task_of_run),
            "prior_runs": len(prior_all),
            "new_runs": sum(map(len, new_by_task.values())),
            "prior_hold_runs": len(prior_hold),
            "new_hold_runs": len(new_hold),
        },
        "new_runs_by_task": {task: len(run_ids) for task, run_ids in sorted(new_by_task.items())},
        "new_hold_by_task": dict(collections.Counter(task_of_run[run_id] for run_id in new_hold)),
        "budgets": {},
    }

    pending: dict[Path, list[dict]] = {}
    for budget in budgets:
        frozen_source = Path(f"{args.frozen_prefix}{budget}.jsonl")
        historical = load_jsonl(frozen_source)
        historical_test = [row for row in historical if row.get("intask_split") == "test"]
        frozen_valid = [
            row
            for row in historical_test
            if row.get("better") in valid_ids
            and row.get("worse") in valid_ids
            and not has_nonfinite(row)
        ]
        frozen_pairs = {(row["better"], row["worse"]) for row in frozen_valid}
        if len(frozen_pairs) != len(frozen_valid):
            raise RuntimeError(f"frozen b{budget} contains duplicate ordered pairs")
        frozen_test_nodes.update(
            row[key] for row in frozen_valid for key in ("better", "worse")
        )

        generated_old_test = [
            row
            for row in generated
            if row["budget"] == budget
            and row["intask_split"] == "test"
            and row["better"] in old_ids
            and row["worse"] in old_ids
        ]
        generated_old_pairs = {(row["better"], row["worse"]) for row in generated_old_test}
        reversed_frozen = {(worse, better) for better, worse in frozen_pairs}
        if frozen_pairs != generated_old_pairs:
            raise RuntimeError(
                f"frozen b{budget} drift: missing={len(frozen_pairs-generated_old_pairs)} "
                f"extra={len(generated_old_pairs-frozen_pairs)}"
            )
        if reversed_frozen & generated_old_pairs:
            raise RuntimeError(f"frozen b{budget} contains reversed labels")

        train = [
            row for row in generated
            if row["budget"] == budget and row["intask_split"] == "train"
        ]
        extension = [
            row for row in generated
            if row["budget"] == budget
            and row["intask_split"] == "test"
            and row["run_id"] not in prior_all
        ]
        if any(row["run_id"] not in new_hold for row in extension):
            raise RuntimeError(f"extension b{budget} contains a non-held run")
        if any(row["run_id"] in hold for row in train):
            raise RuntimeError(f"training b{budget} contains a held run")

        pending[out_dir / f"decision_train_v10_b{budget}.jsonl"] = train
        pending[out_dir / f"decision_frozen_v10_b{budget}.jsonl"] = frozen_valid
        pending[out_dir / f"decision_extension_v10_b{budget}.jsonl"] = extension
        audit["budgets"][str(budget)] = {
            "train": len(train),
            "train_old_only": sum(
                row["better"] in old_ids and row["worse"] in old_ids for row in train
            ),
            "train_new": sum(
                row["better"] not in old_ids or row["worse"] not in old_ids for row in train
            ),
            "frozen_source_rows": len(historical_test),
            "frozen_valid": len(frozen_valid),
            "frozen_quarantined": len(historical_test) - len(frozen_valid),
            "frozen_sha256": canonical_hash(frozen_valid),
            "extension": len(extension),
        }

    train_nodes = {
        row[key]
        for row in generated
        if row["intask_split"] == "train"
        for key in ("better", "worse")
    }
    overlap = train_nodes & frozen_test_nodes
    if overlap:
        raise RuntimeError(f"{len(overlap)} frozen-test nodes occur in training")
    audit["frozen_test_nodes_in_train"] = 0

    hold_manifest = {
        "seed": args.seed,
        "hold": sorted(hold),
        "all": sorted(prior_all | set(task_of_run)),
        "prior_hold": sorted(prior_hold),
        "prior_all": sorted(prior_all),
        "new_hold": sorted(new_hold),
    }
    for path, rows in pending.items():
        atomic_jsonl(path, rows)
    atomic_json(out_dir / "runsplit_holdruns_v10.json", hold_manifest)
    atomic_json(out_dir / "decision_v10_audit.json", audit)

    print(json.dumps(audit, indent=2, sort_keys=True))
    print(f"[build_decision_v10] wrote {len(pending) + 2} artifacts to {out_dir}")


if __name__ == "__main__":
    main()
