"""Measure whether G-reuse connects local parent decision contexts."""
from collections import defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path

from phase1.g_reuse_min_token_basis import LENGTHS, choose_basis, read_lengths
from phase1.g_reuse_record_consistent_sensitivity import EXTRA, record_consistent
from phase1.g_reuse_spectral_midpoint import TaskGraph
from phase1.g_reuse_task_breadth import derive_reuse
from phase1.historical_global_local_source_gate import project_batches, project_cards
from phase1.historical_label_reuse_support import INPUTS, check, checked, install_guard, pairs, project


def parent_projection(local_rows, task_of):
    edge_parent = {}
    parents = defaultdict(set)
    for row in local_rows:
        check(row.get("intask_split") == "train", "non_train_local")
        edge = tuple(sorted((row["better"], row["worse"])))
        context = (row["task"], row["parent"])
        check(
            all(isinstance(value, str) and value for value in (*edge, *context)),
            "invalid_context",
        )
        check(edge not in edge_parent, "duplicate_local_edge")
        check(task_of[edge[0]] == task_of[edge[1]] == context[0], "task_context_mismatch")
        edge_parent[edge] = context
        parents[edge[0]].add(context)
        parents[edge[1]].add(context)
    check(all(len(value) == 1 for value in parents.values()), "endpoint_multiple_contexts")
    return edge_parent, {node: next(iter(value)) for node, value in parents.items()}


class Disjoint:
    def __init__(self, nodes):
        self.parent = {node: node for node in nodes}

    def root(self, node):
        while self.parent[node] != node:
            self.parent[node] = self.parent[self.parent[node]]
            node = self.parent[node]
        return node

    def merge(self, left, right):
        left, right = self.root(left), self.root(right)
        if left == right:
            return False
        self.parent[max(left, right)] = min(left, right)
        return True


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
        basis_tokens = sum(costs[edge] for edge in task_basis)
        full_tokens = sum(costs[edge] for edge in task_full)
        budget, spent = (full_tokens - basis_tokens) // 2, 0
        state = TaskGraph(local_by[task], task_full, task_basis)
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
            spent += costs[edge]
            selected.add(edge)
            state.add(edge)
    return sorted(selected)


def arm_summary(name, selected, local, edge_parent, parent_of, task_of, lengths):
    all_contexts = set(parent_of.values())
    selected_endpoints = {node for edge in selected for node in edge}
    touched = {parent_of[node] for node in selected_endpoints}
    cross = [edge for edge in selected if parent_of[edge[0]] != parent_of[edge[1]]]
    any_pairs = sum(bool(set(edge) & selected_endpoints) for edge in local)
    both_pairs = sum(set(edge) <= selected_endpoints for edge in local)
    contexts_by_task, edges_by_task = defaultdict(set), defaultdict(list)
    for context in all_contexts:
        contexts_by_task[context[0]].add(context)
    for edge in cross:
        edges_by_task[task_of[edge[0]]].append(edge)
    rows = []
    for task in sorted(contexts_by_task):
        contexts = contexts_by_task[task]
        disjoint = Disjoint(contexts)
        task_edges = edges_by_task[task]
        gain = 0
        for edge in task_edges:
            gain += disjoint.merge(parent_of[edge[0]], parent_of[edge[1]])
        task_selected = [edge for edge in selected if task_of[edge[0]] == task]
        task_endpoints = {node for edge in task_selected for node in edge}
        task_local = [edge for edge in local if task_of[edge[0]] == task]
        rows.append(
            {
                "local_contexts": len(contexts),
                "local_pairs": len(task_local),
                "selected_g_edges": len(task_selected),
                "cross_context_edges": len(task_edges),
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


def evaluate(local, full, basis, spectral, edge_parent, parent_of, task_of, lengths):
    arms = {
        name: arm_summary(name, edges, local, edge_parent, parent_of, task_of, lengths)
        for name, edges in (("basis", basis), ("spectral50", spectral), ("full", full))
    }
    full_metrics, spectral_metrics = arms["full"], arms["spectral50"]
    rank_retention = spectral_metrics["parent_rank_gain"] / full_metrics["parent_rank_gain"]
    context_retention = spectral_metrics["context_coverage"] / full_metrics["context_coverage"]
    pair_retention = (
        spectral_metrics["local_pair_both_coverage"] / full_metrics["local_pair_both_coverage"]
    )
    token_reduction = 1.0 - spectral_metrics["g_tokens"] / full_metrics["g_tokens"]
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
        "spectral_parent_rank_retention_at_least_0_75": rank_retention >= 0.75,
        "spectral_context_coverage_retention_at_least_0_80": context_retention >= 0.80,
        "spectral_local_pair_both_coverage_retention_at_least_0_75": pair_retention >= 0.75,
        "spectral_g_token_reduction_at_least_0_25": token_reduction >= 0.25,
    }
    return {
        "tasks": len({context[0] for context in parent_of.values()}),
        "arms": arms,
        "spectral50_retention": {
            "parent_rank_gain": rank_retention,
            "context_coverage": context_retention,
            "local_pair_both_coverage": pair_retention,
            "g_token_reduction": token_reduction,
        },
        "gates": gates,
        "all_gates_pass": all(gates.values()),
    }


def main():
    extras = [path for path, _ in EXTRA.values()] + [LENGTHS[0]]
    opened = install_guard(extras)
    for path, digest in [*INPUTS.values(), *EXTRA.values(), LENGTHS]:
        checked(path, digest)
    local_rows = [json.loads(line) for line in INPUTS["local"][0].read_text().splitlines()]
    local = pairs(local_rows)
    global_all = pairs(
        [json.loads(line) for line in INPUTS["global"][0].read_text().splitlines()]
    )
    grouped = json.loads(INPUTS["cards"][0].read_text())
    run_of, task_of = project(grouped)
    cards = project_cards(grouped)
    batches = project_batches(
        [json.loads(line) for line in EXTRA["batches"][0].read_text().splitlines()]
    )
    check(set(batches) == set(grouped), "batch_inventory")
    full = record_consistent(derive_reuse(local, global_all, run_of, task_of), cards, batches)
    local_ids = {node for edge in local for node in edge}
    with LENGTHS[0].open(newline="") as handle:
        lengths = read_lengths(local_ids, list(csv.DictReader(handle)))
    basis = choose_basis(local, full, lengths)
    spectral = select_spectral50(local, full, basis, task_of, lengths)
    edge_parent, parent_of = parent_projection(local_rows, task_of)
    metrics = evaluate(local, full, basis, spectral, edge_parent, parent_of, task_of, lengths)
    for path, digest in [*INPUTS.values(), *EXTRA.values(), LENGTHS]:
        checked(path, digest, scan=False)
    status = (
        "G_REUSE_DECISION_CONTEXT_REACH_STRUCTURALLY_SUPPORTED"
        if metrics["all_gates_pass"]
        else "G_REUSE_DECISION_CONTEXT_REACH_NOT_SUPPORTED"
    )
    return {
        "status": status,
        "metrics": metrics,
        "input_sha256": {
            **{key: digest for key, (_, digest) in INPUTS.items()},
            **{key: digest for key, (_, digest) in EXTRA.items()},
            "lengths": LENGTHS[1],
        },
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "selected_edge_identities_emitted": False,
        "parent_or_task_identities_emitted": False,
        "pool_written": False,
        "protected_cohort_files_opened": 0,
        "data_open_counts": dict(opened),
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
