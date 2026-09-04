"""Independent grounded-Laplacian verifier for decision-context reach."""
import argparse
from collections import defaultdict
import hashlib
import json
import math
import os
from pathlib import Path
import sys

from phase1.verify_g_reuse_min_token_basis import FILES, checked_bytes
from phase1.verify_g_reuse_spectral_midpoint import IndependentTask, prepare


class ContextDisjoint:
    def __init__(self, nodes):
        self.parent = {node: node for node in nodes}

    def root(self, node):
        trail = []
        while self.parent[node] != node:
            trail.append(node)
            node = self.parent[node]
        for item in trail:
            self.parent[item] = node
        return node

    def merge(self, left, right):
        left, right = self.root(left), self.root(right)
        if left == right:
            return False
        self.parent[max(left, right)] = min(left, right)
        return True


def contexts(raw_local, task_of):
    edge_context, memberships = {}, defaultdict(set)
    for line in raw_local.splitlines():
        row = json.loads(line)
        edge = tuple(sorted((row["better"], row["worse"])))
        context = (row["task"], row["parent"])
        if (
            row.get("intask_split") != "train"
            or edge in edge_context
            or edge[0] == edge[1]
            or not all(isinstance(value, str) and value for value in (*edge, *context))
            or task_of[edge[0]] != task_of[edge[1]]
            or task_of[edge[0]] != context[0]
        ):
            raise ValueError("independent_context_mapping")
        edge_context[edge] = context
        memberships[edge[0]].add(context)
        memberships[edge[1]].add(context)
    if not memberships or any(len(value) != 1 for value in memberships.values()):
        raise ValueError("independent_endpoint_multiple_contexts")
    return edge_context, {node: next(iter(value)) for node, value in memberships.items()}


def select_spectral50(local, full, basis, task_of, lengths):
    local_by, full_by, basis_by = defaultdict(list), defaultdict(list), defaultdict(list)
    for edge in local:
        local_by[task_of[edge[0]]].append(edge)
    for edge in full:
        full_by[task_of[edge[0]]].append(edge)
    for edge in basis:
        basis_by[task_of[edge[0]]].append(edge)
    selected = set(basis)
    for task in sorted(local_by):
        task_full, task_basis = full_by[task], basis_by[task]
        costs = {edge: lengths[edge[0]] + lengths[edge[1]] for edge in task_full}
        remaining = sorted(set(task_full) - set(task_basis))
        budget = (
            sum(costs[edge] for edge in task_full)
            - sum(costs[edge] for edge in task_basis)
        ) // 2
        spent = 0
        state = IndependentTask(local_by[task], task_full, task_basis)
        while True:
            fitting = [edge for edge in remaining if costs[edge] <= budget - spent]
            if not fitting:
                break
            scored = [
                (round(math.log1p(state.resistance(edge)) / costs[edge], 15), edge)
                for edge in fitting
            ]
            maximum = max(score for score, _ in scored)
            edge = min(edge for score, edge in scored if score == maximum)
            remaining.remove(edge)
            selected.add(edge)
            spent += costs[edge]
            state.add(edge)
    return sorted(selected)


def summarize_arm(name, selected, local, parent_of, task_of, lengths):
    all_contexts = set(parent_of.values())
    endpoints = {node for edge in selected for node in edge}
    touched = {parent_of[node] for node in endpoints}
    cross = [edge for edge in selected if parent_of[edge[0]] != parent_of[edge[1]]]
    context_by_task, cross_by_task = defaultdict(set), defaultdict(list)
    for context in all_contexts:
        context_by_task[context[0]].add(context)
    for edge in cross:
        cross_by_task[task_of[edge[0]]].append(edge)
    rows = []
    for task in sorted(context_by_task):
        disjoint = ContextDisjoint(context_by_task[task])
        gain = sum(
            disjoint.merge(parent_of[edge[0]], parent_of[edge[1]])
            for edge in cross_by_task[task]
        )
        task_selected = [edge for edge in selected if task_of[edge[0]] == task]
        task_endpoints = {node for edge in task_selected for node in edge}
        task_local = [edge for edge in local if task_of[edge[0]] == task]
        rows.append(
            {
                "local_contexts": len(context_by_task[task]),
                "local_pairs": len(task_local),
                "selected_g_edges": len(task_selected),
                "cross_context_edges": len(cross_by_task[task]),
                "parent_rank_gain": gain,
                "parents_touched": len({parent_of[node] for node in task_endpoints}),
                "local_pairs_any_endpoint_touched": sum(
                    bool(set(edge) & task_endpoints) for edge in task_local
                ),
                "local_pairs_both_endpoints_touched": sum(
                    set(edge) <= task_endpoints for edge in task_local
                ),
            }
        )
    total_gain = sum(row["parent_rank_gain"] for row in rows)
    rows.sort(key=lambda row: json.dumps(row, sort_keys=True, separators=(",", ":")))
    any_pairs = sum(bool(set(edge) & endpoints) for edge in local)
    both_pairs = sum(set(edge) <= endpoints for edge in local)
    return {
        "arm": name,
        "g_edges": len(selected),
        "g_tokens": sum(lengths[a] + lengths[b] for a, b in selected),
        "cross_context_edges": len(cross),
        "cross_context_edge_fraction": len(cross) / len(selected),
        "local_contexts": len(all_contexts),
        "contexts_touched": len(touched),
        "context_coverage": len(touched) / len(all_contexts),
        "local_pairs": len(local),
        "local_pairs_any_endpoint_touched": any_pairs,
        "local_pair_any_coverage": any_pairs / len(local),
        "local_pairs_both_endpoints_touched": both_pairs,
        "local_pair_both_coverage": both_pairs / len(local),
        "parent_rank_gain": total_gain,
        "tasks_with_positive_parent_rank_gain": sum(
            row["parent_rank_gain"] > 0 for row in rows
        ),
        "max_task_parent_rank_gain_share": (
            max(row["parent_rank_gain"] for row in rows) / total_gain if total_gain else None
        ),
        "anonymous_task_rows": rows,
    }


def reconstruct(raw):
    local, full, basis, task_of, lengths = prepare(raw)
    edge_context, parent_of = contexts(raw["local"], task_of)
    spectral = select_spectral50(local, full, basis, task_of, lengths)
    arms = {
        name: summarize_arm(name, selected, local, parent_of, task_of, lengths)
        for name, selected in (("basis", basis), ("spectral50", spectral), ("full", full))
    }
    full_metrics, spectral_metrics = arms["full"], arms["spectral50"]
    retention = {
        "parent_rank_gain": spectral_metrics["parent_rank_gain"]
        / full_metrics["parent_rank_gain"],
        "context_coverage": spectral_metrics["context_coverage"]
        / full_metrics["context_coverage"],
        "local_pair_both_coverage": spectral_metrics["local_pair_both_coverage"]
        / full_metrics["local_pair_both_coverage"],
        "g_token_reduction": 1.0
        - spectral_metrics["g_tokens"] / full_metrics["g_tokens"],
    }
    gates = {
        "fixed_counts_and_unique_endpoint_context": len(local) == 4689
        and len(full) == 2745
        and len(basis) == 790
        and len(spectral) == 1811
        and len(parent_of) == len({node for edge in local for node in edge}),
        "full_cross_context_edge_fraction_at_least_0_90": full_metrics[
            "cross_context_edge_fraction"
        ]
        >= 0.90,
        "full_context_coverage_at_least_0_60": full_metrics["context_coverage"] >= 0.60,
        "full_local_pair_both_coverage_at_least_0_20": full_metrics[
            "local_pair_both_coverage"
        ]
        >= 0.20,
        "full_positive_parent_rank_tasks_at_least_20": full_metrics[
            "tasks_with_positive_parent_rank_gain"
        ]
        >= 20,
        "full_max_task_parent_rank_share_at_most_0_20": full_metrics[
            "max_task_parent_rank_gain_share"
        ]
        <= 0.20,
        "spectral_parent_rank_retention_at_least_0_75": retention["parent_rank_gain"] >= 0.75,
        "spectral_context_coverage_retention_at_least_0_80": retention[
            "context_coverage"
        ]
        >= 0.80,
        "spectral_local_pair_both_coverage_retention_at_least_0_75": retention[
            "local_pair_both_coverage"
        ]
        >= 0.75,
        "spectral_g_token_reduction_at_least_0_25": retention["g_token_reduction"] >= 0.25,
    }
    return {
        "tasks": len({context[0] for context in parent_of.values()}),
        "arms": arms,
        "spectral50_retention": retention,
        "gates": gates,
        "all_gates_pass": all(gates.values()),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--sha256", required=True)
    args = parser.parse_args()
    allowed = {path.resolve() for path, _ in FILES.values()} | {args.receipt.resolve()}
    opened = defaultdict(int)

    def guard(event, params):
        if event in ("socket.connect", "socket.bind", "subprocess.Popen", "os.system"):
            raise PermissionError("offline")
        if event != "open" or not isinstance(params[0], (str, bytes, os.PathLike)):
            return
        path = Path(os.fsdecode(params[0])).resolve()
        mode, flags = params[1:3]
        if (
            isinstance(mode, str)
            and any(char in mode for char in "wax+")
            or isinstance(flags, int)
            and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)
        ):
            raise PermissionError("read_only")
        if path in allowed:
            opened[str(path)] += 1
        elif path.suffix.lower() not in (".py", ".pyc"):
            raise PermissionError("unlisted_data")

    sys.addaudithook(guard)
    raw = {name: checked_bytes(path, digest) for name, (path, digest) in FILES.items()}
    receipt = checked_bytes(args.receipt, args.sha256, 2 * 1024 * 1024)
    metrics = reconstruct(raw)
    payload = json.loads(receipt)
    if payload["metrics"] != metrics:
        raise ValueError("independent_metrics_mismatch")
    expected = (
        "G_REUSE_DECISION_CONTEXT_REACH_STRUCTURALLY_SUPPORTED"
        if metrics["all_gates_pass"]
        else "G_REUSE_DECISION_CONTEXT_REACH_NOT_SUPPORTED"
    )
    if payload["status"] != expected:
        raise ValueError("status_mismatch")
    for path, digest in [*FILES.values(), (args.receipt, args.sha256)]:
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("post_hash_drift")
    return {
        "status": "INDEPENDENT_G_REUSE_DECISION_CONTEXT_REACH_EXACT",
        "receipt_sha256": args.sha256,
        "metrics": metrics,
        "data_open_counts": dict(opened),
        "selected_edge_identities_emitted": False,
        "parent_or_task_identities_emitted": False,
        "protected_cohort_files_opened": 0,
        "gpu_jobs": 0,
        "api_calls": 0,
        "model_fits": 0,
    }


if __name__ == "__main__":
    try:
        print(json.dumps(main(), sort_keys=True))
    except Exception as exc:
        print(
            json.dumps(
                {"status": "FAILED_CLOSED", "exception_type": type(exc).__name__},
                sort_keys=True,
            )
        )
        raise SystemExit(1)
