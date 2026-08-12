"""Audit whether an archived AIRA-dojo card corpus contains *usable* search trees.

This is the structural half of Prompt 0.5.  It deliberately does not implement a
TD return or claim a TD win: first establish that the logged graph has real,
closed parent--child subtrees deep enough for any backup comparison to be
meaningful.  In particular, a missing parent is treated as a fragment boundary,
not as a true search root.

Inputs are immutable corpus artifacts:
  * cards JSONL (v9 in the first run), and
  * the independently reconstructed card -> physical-run map.

Outputs are deterministic CSV/JSON audit records.  They include the input SHA256
and checkout commit so a later TD/MC simulation can cite precisely which trees
were eligible.

Example:
  python phase1/audit_tree_topology.py \
    --cards /path/cards_current_v9.jsonl \
    --run-map phase1/card_run_map.json \
    --out-dir phase1/td_topology_v9
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import math
import subprocess
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Set, Tuple


def finite_grade(card: Mapping[str, Any]) -> bool:
    try:
        return math.isfinite(float((card.get("label") or {}).get("graded")))
    except (TypeError, ValueError):
        return False


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def checkout_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "UNKNOWN"


def write_csv(path: Path, rows: Iterable[Mapping[str, Any]], fields: List[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cards", required=True, type=Path)
    ap.add_argument("--run-map", required=True, type=Path)
    ap.add_argument("--out-dir", required=True, type=Path)
    args = ap.parse_args()

    cards: Dict[str, Dict[str, Any]] = {}
    duplicate_ids = 0
    with args.cards.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            if not line.strip():
                continue
            card = json.loads(line)
            cid = card.get("id")
            if not isinstance(cid, str) or not cid:
                raise ValueError(f"missing card id at {args.cards}:{line_no}")
            if cid in cards:
                duplicate_ids += 1
            cards[cid] = card

    run_map: Dict[str, str] = json.loads(args.run_map.read_text(encoding="utf-8"))
    mapped = {cid: run_map[cid] for cid in cards if cid in run_map}
    unmapped = sorted(set(cards) - set(mapped))
    if unmapped:
        raise SystemExit(
            f"ABORT: {len(unmapped)}/{len(cards)} cards absent from run map; "
            "do not infer physical runs from fragments."
        )

    def task_of(cid: str) -> str:
        return str((cards[cid].get("task") or {}).get("name", "<missing-task>"))

    def parent_of(cid: str) -> str | None:
        p = (cards[cid].get("lineage") or {}).get("parent_id")
        return p if isinstance(p, str) and p else None

    def declared_children(cid: str) -> Set[str]:
        raw = (cards[cid].get("lineage") or {}).get("children_ids", [])
        if raw is None:
            return set()
        if not isinstance(raw, list) or not all(isinstance(x, str) and x for x in raw):
            raise ValueError(f"malformed children_ids for {cid}")
        return set(raw)

    # A direct edge is usable only when both endpoints occur in the independently
    # reconstructed physical run and task.  Cross-run parents would reintroduce the
    # fragment leakage already found in the old corpus.
    observed_by_parent: Dict[str, Set[str]] = collections.defaultdict(set)
    legal_edges: Set[Tuple[str, str]] = set()
    parent_missing = parent_cross_run = parent_cross_task = 0
    for child in cards:
        parent = parent_of(child)
        if parent is None:
            continue
        if parent not in cards:
            parent_missing += 1
            continue
        if mapped[parent] != mapped[child]:
            parent_cross_run += 1
            continue
        if task_of(parent) != task_of(child):
            parent_cross_task += 1
            continue
        legal_edges.add((parent, child))
        observed_by_parent[parent].add(child)

    # A downward subtree is closed only if the parent's declared children exactly
    # match the same-run observed children, and all descendants satisfy the same
    # condition.  This prevents silently treating pruned/ungraded children as leaves.
    local_complete: Dict[str, bool] = {}
    declaration_mismatch = declared_missing = 0
    for cid in cards:
        declared = declared_children(cid)
        observed = observed_by_parent.get(cid, set())
        missing = declared - set(cards)
        if missing:
            declared_missing += len(missing)
        complete = not missing and declared == observed
        if not complete:
            declaration_mismatch += 1
        local_complete[cid] = complete

    closed: Dict[str, bool] = {}
    depth_to_leaf: Dict[str, int] = {}
    visiting: Set[str] = set()
    cycles: Set[str] = set()

    def close_and_depth(cid: str) -> Tuple[bool, int]:
        if cid in closed:
            return closed[cid], depth_to_leaf[cid]
        if cid in visiting:
            cycles.update(visiting)
            return False, 0
        visiting.add(cid)
        kids = observed_by_parent.get(cid, set())
        ok = local_complete[cid] and finite_grade(cards[cid])
        child_depths: List[int] = []
        for child in kids:
            child_ok, child_depth = close_and_depth(child)
            ok = ok and child_ok
            child_depths.append(child_depth)
        visiting.remove(cid)
        closed[cid] = bool(ok)
        depth_to_leaf[cid] = 0 if not child_depths else 1 + max(child_depths)
        return closed[cid], depth_to_leaf[cid]

    for cid in cards:
        close_and_depth(cid)
    for cid in cycles:
        closed[cid] = False

    # Connected components of the *legal* direct-edge graph.  Their roots are merely
    # observed fragment roots; no result labels one a true original search root.
    undirected: Dict[str, Set[str]] = collections.defaultdict(set)
    for p, c in legal_edges:
        undirected[p].add(c)
        undirected[c].add(p)
    component_of: Dict[str, str] = {}
    component_nodes: Dict[str, List[str]] = {}
    for start in cards:
        if start in component_of:
            continue
        stack, nodes = [start], []
        component_of[start] = "PENDING"
        while stack:
            cur = stack.pop()
            nodes.append(cur)
            for nxt in undirected.get(cur, set()):
                if nxt not in component_of:
                    component_of[nxt] = "PENDING"
                    stack.append(nxt)
        runs = {mapped[x] for x in nodes}
        tasks = {task_of(x) for x in nodes}
        if len(runs) != 1 or len(tasks) != 1:
            raise AssertionError("legal edge construction produced mixed component")
        key = f"{next(iter(runs))}::component-{hashlib.sha1(min(nodes).encode()).hexdigest()[:12]}"
        for cid in nodes:
            component_of[cid] = key
        component_nodes[key] = nodes

    run_nodes: Dict[str, List[str]] = collections.defaultdict(list)
    for cid, rid in mapped.items():
        run_nodes[rid].append(cid)
    run_rows: List[Dict[str, Any]] = []
    for rid, nodes in sorted(run_nodes.items()):
        tasks = {task_of(x) for x in nodes}
        if len(tasks) != 1:
            raise AssertionError(f"run map mixes tasks: {rid}: {tasks}")
        comps = {component_of[x] for x in nodes}
        edges = sum(1 for p, _ in legal_edges if mapped[p] == rid)
        branch = [x for x in nodes if len(observed_by_parent.get(x, set())) >= 2]
        closed_branch = [x for x in branch if closed.get(x, False)]
        deep_branch = [
            x for x in closed_branch
            if any(depth_to_leaf.get(c, 0) >= 1 for c in observed_by_parent[x])
        ]
        run_rows.append({
            "run_id": rid,
            "task": next(iter(tasks)),
            "cards": len(nodes),
            "graded_cards": sum(finite_grade(cards[x]) for x in nodes),
            "legal_parent_child_edges": edges,
            "observed_components": len(comps),
            "closed_nodes": sum(closed.get(x, False) for x in nodes),
            "branch_points": len(branch),
            "closed_branch_points": len(closed_branch),
            "deep_closed_branch_points": len(deep_branch),
            "max_closed_depth_to_leaf": max((depth_to_leaf[x] for x in nodes if closed.get(x, False)), default=0),
        })

    task_rows: List[Dict[str, Any]] = []
    for task in sorted({r["task"] for r in run_rows}):
        rows = [r for r in run_rows if r["task"] == task]
        task_rows.append({
            "task": task,
            "runs": len(rows),
            "cards": sum(r["cards"] for r in rows),
            "legal_parent_child_edges": sum(r["legal_parent_child_edges"] for r in rows),
            "closed_nodes": sum(r["closed_nodes"] for r in rows),
            "branch_points": sum(r["branch_points"] for r in rows),
            "closed_branch_points": sum(r["closed_branch_points"] for r in rows),
            "deep_closed_branch_points": sum(r["deep_closed_branch_points"] for r in rows),
            "max_closed_depth_to_leaf": max(r["max_closed_depth_to_leaf"] for r in rows),
        })

    n_deep = sum(r["deep_closed_branch_points"] for r in run_rows)
    max_depth = max((r["max_closed_depth_to_leaf"] for r in run_rows), default=0)
    # This is a structure-only stop signal, not an outcome test.  A green signal means
    # that a TD/MC estimator can be specified next; it says nothing about TD winning.
    structural_signal = "CONTINUE_TO_ESTIMATOR_SPEC" if n_deep else "RED_NO_DEEP_CLOSED_BRANCH"
    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(
        args.out_dir / "run_topology.csv", run_rows,
        ["run_id", "task", "cards", "graded_cards", "legal_parent_child_edges",
         "observed_components", "closed_nodes", "branch_points", "closed_branch_points",
         "deep_closed_branch_points", "max_closed_depth_to_leaf"],
    )
    write_csv(
        args.out_dir / "task_topology.csv", task_rows,
        ["task", "runs", "cards", "legal_parent_child_edges", "closed_nodes",
         "branch_points", "closed_branch_points", "deep_closed_branch_points",
         "max_closed_depth_to_leaf"],
    )
    summary = {
        "script": "phase1/audit_tree_topology.py",
        "checkout_commit": checkout_commit(),
        "cards_filename": args.cards.name,
        "cards_sha256": sha256_file(args.cards),
        "run_map_filename": args.run_map.name,
        "run_map_sha256": sha256_file(args.run_map),
        "n_cards": len(cards),
        "n_duplicate_ids_overwritten": duplicate_ids,
        "n_runs": len(run_rows),
        "n_tasks": len(task_rows),
        "parent_missing": parent_missing,
        "parent_cross_run": parent_cross_run,
        "parent_cross_task": parent_cross_task,
        "declared_missing_children": declared_missing,
        "declaration_mismatch_nodes": declaration_mismatch,
        "cycle_nodes": len(cycles),
        "n_closed_nodes": sum(closed.values()),
        "n_closed_branch_points": sum(r["closed_branch_points"] for r in run_rows),
        "n_deep_closed_branch_points": n_deep,
        "max_closed_depth_to_leaf": max_depth,
        "structural_signal": structural_signal,
        "interpretation": (
            "Observed component roots are fragments, not true run roots.  The signal only "
            "determines whether a TD/MC estimator is worth specifying; it is not evidence "
            "that TD improves search."
        ),
    }
    (args.out_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
