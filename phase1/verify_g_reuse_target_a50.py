"""Independent grounded-inverse verifier for target-A50 development."""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
import math
import os
from pathlib import Path
import sys

import numpy as np

from phase1.verify_g_reuse_min_token_basis import FILES, Disjoint, checked_bytes
from phase1.verify_g_reuse_spectral_midpoint import GroundedState, prepare
from phase1.verify_g_reuse_target_contrast_variance import (
    independent_quantile,
    independent_select_edges,
    independent_target_variances,
    manifest_hash,
)


PROTOCOL_SHA256 = "ffd04c96b0433cdf917798e6169d79b0341c19a9846025311c1d3038b237f448"
MATCHED = ("targetA50", "spectral50", "cheapest50", "hash50")
CONTROLS = ("spectral50", "cheapest50", "hash50")
ALL_ARMS = ("basis",) + MATCHED + ("full",)
TOLERANCE = 1e-10


class IndependentTargetState:
    def __init__(self, local, full, basis):
        nodes = {node for edge in local for node in edge}
        disjoint = Disjoint(nodes)
        for edge in set(local) | set(full):
            disjoint.merge(*edge)
        groups = defaultdict(set)
        for node in nodes:
            groups[disjoint.root(node)].add(node)
        self.states, self.targets, self.node_group = [], [], {}
        for group in groups.values():
            group_full = [edge for edge in full if edge[0] in group and edge[1] in group]
            if not group_full:
                continue
            initial = [edge for edge in local + basis if edge[0] in group and edge[1] in group]
            state = GroundedState(group, initial)
            position = len(self.states)
            self.states.append(state)
            self.targets.append([edge for edge in local if edge[0] in group and edge[1] in group])
            for node in group:
                self.node_group[node] = position
        if not self.states or not all(edge[0] in self.node_group for edge in full):
            raise ValueError("target_state_coverage")

    def reduction(self, edge):
        position = self.node_group[edge[0]]
        if self.node_group[edge[1]] != position:
            raise ValueError("cross_component")
        state = self.states[position]
        vector = state.vector(edge)
        transformed = state.inverse @ vector
        resistance = float(vector @ transformed)
        if resistance < -1e-8:
            raise ValueError("negative_resistance")
        target_matrix = np.vstack([state.vector(target) for target in self.targets[position]])
        differences = target_matrix @ transformed
        reduction = float(differences @ differences) / (1.0 + max(0.0, resistance))
        if not math.isfinite(reduction) or reduction < -1e-8:
            raise ValueError("invalid_reduction")
        return max(0.0, reduction)

    def add(self, edge):
        position = self.node_group[edge[0]]
        if self.node_group[edge[1]] != position:
            raise ValueError("update_cross_component")
        self.states[position].add(edge)


def independent_target_select(local, full, basis, lengths):
    costs = {edge: lengths[edge[0]] + lengths[edge[1]] for edge in full}
    remaining = sorted(set(full) - set(basis))
    basis_tokens = sum(costs[edge] for edge in basis)
    full_tokens = sum(costs[edge] for edge in full)
    budget = (full_tokens - basis_tokens) // 2
    state = IndependentTargetState(local, full, basis)
    available, chosen, spent, predicted = list(remaining), [], 0, 0.0
    while True:
        fitting = [edge for edge in available if costs[edge] <= budget - spent]
        if not fitting:
            break
        candidates = [(round(state.reduction(edge) / costs[edge], 15), edge) for edge in fitting]
        maximum = max(value for value, _ in candidates)
        edge = min(edge for value, edge in candidates if value == maximum)
        gain = state.reduction(edge)
        available.remove(edge)
        chosen.append(edge)
        spent += costs[edge]
        predicted += gain
        state.add(edge)
    if spent > budget:
        raise ValueError("budget_exceeded")
    return {
        "edges": tuple(sorted(set(basis) | set(chosen))),
        "basis_tokens": basis_tokens,
        "full_tokens": full_tokens,
        "additional_token_budget": budget,
        "additional_tokens": spent,
        "additional_edges": len(chosen),
        "predicted_target_variance_reduction": predicted,
    }


def reconstruct(raw):
    local, full, basis, task_of, lengths = prepare(raw)
    by_local, by_full, by_basis = defaultdict(list), defaultdict(list), defaultdict(list)
    for edge in local:
        by_local[task_of[edge[0]]].append(edge)
    for edge in full:
        by_full[task_of[edge[0]]].append(edge)
    for edge in basis:
        by_basis[task_of[edge[0]]].append(edge)
    rows, task_values = [], []
    global_edges = {arm: [] for arm in ALL_ARMS}
    for task in sorted(by_local):
        task_local, task_full, task_basis = (
            sorted(by_local[task]), sorted(by_full[task]), sorted(by_basis[task])
        )
        target = independent_target_select(task_local, task_full, task_basis, lengths)
        controls = {arm: independent_select_edges(task_local, task_full, task_basis, lengths, arm)
                    for arm in CONTROLS}
        selected = {"targetA50": target, **controls}
        if len({item["additional_token_budget"] for item in selected.values()}) != 1:
            raise ValueError("budget_drift")
        arm_edges = {"basis": tuple(task_basis),
                     **{arm: selected[arm]["edges"] for arm in MATCHED},
                     "full": tuple(task_full)}
        for arm, edges in arm_edges.items():
            global_edges[arm].extend(edges)
        variances = {arm: independent_target_variances(task_local, edges)
                     for arm, edges in arm_edges.items()}
        task_values.append(variances)
        rows.append({
            "local_pairs": len(task_local), "full_g_pairs": len(task_full),
            "basis_g_pairs": len(task_basis),
            "arm_g_pairs": {arm: len(edges) for arm, edges in arm_edges.items()},
            "arm_mean_target_variance": {arm: sum(values) / len(values)
                                         for arm, values in variances.items()},
            "additional_token_budget": target["additional_token_budget"],
            "basis_g_tokens": target["basis_tokens"],
            "additional_tokens": {arm: selected[arm]["additional_tokens"] for arm in MATCHED},
            "target_predicted_reduction": target["predicted_target_variance_reduction"],
        })
    pooled = {arm: [] for arm in ALL_ARMS}
    task_means = {arm: [] for arm in ALL_ARMS}
    for values_by_arm in task_values:
        for arm, values in values_by_arm.items():
            pooled[arm].extend(values)
            task_means[arm].append(sum(values) / len(values))
    aggregates = {arm: {
        "pair_weighted_mean": sum(pooled[arm]) / len(pooled[arm]),
        "task_macro_mean": sum(task_means[arm]) / len(task_means[arm]),
        "pooled_p90": independent_quantile(pooled[arm], 0.9),
    } for arm in ALL_ARMS}
    comparisons = {}
    for control in CONTROLS:
        differences = [old - new for old, new in zip(task_means[control], task_means["targetA50"])]
        positive = [max(0.0, value) for value in differences]
        comparisons[control] = {
            "pair_weighted_relative_reduction": 1.0 - aggregates["targetA50"]["pair_weighted_mean"] / aggregates[control]["pair_weighted_mean"],
            "task_macro_relative_reduction": 1.0 - aggregates["targetA50"]["task_macro_mean"] / aggregates[control]["task_macro_mean"],
            "nonworse_tasks": sum(value >= -TOLERANCE for value in differences),
            "strictly_better_tasks": sum(value > TOLERANCE for value in differences),
            "maximum_single_task_positive_reduction_share": max(positive) / sum(positive) if sum(positive) else 1.0,
        }
    target_spent = sum(row["additional_tokens"]["targetA50"] for row in rows)
    target_budget = sum(row["additional_token_budget"] for row in rows)
    finite = all(math.isfinite(value) and value >= -TOLERANCE
                 for values in pooled.values() for value in values)
    gates = {
        "fixed_population_budget_and_finite_variances": len(local) == 4689 and len(full) == 2745
        and len(basis) == 790 and len(rows) == 28 and finite
        and all(all(row["additional_tokens"][arm] <= row["additional_token_budget"] for arm in MATCHED) for row in rows)
        and target_spent / target_budget >= 0.95,
        "target_pair_mean_effect_sizes_pass": comparisons["spectral50"]["pair_weighted_relative_reduction"] >= 0.01
        and all(comparisons[arm]["pair_weighted_relative_reduction"] >= 0.03 for arm in ("cheapest50", "hash50"))
        and all(aggregates["targetA50"]["pair_weighted_mean"] < aggregates[arm]["pair_weighted_mean"] for arm in CONTROLS),
        "target_task_macro_strictly_lower_than_all_controls": all(
            aggregates["targetA50"]["task_macro_mean"] < aggregates[arm]["task_macro_mean"] for arm in CONTROLS),
        "target_p90_not_higher_than_all_controls": all(
            aggregates["targetA50"]["pooled_p90"] <= aggregates[arm]["pooled_p90"] + TOLERANCE for arm in CONTROLS),
        "target_task_breadth_vs_spectral": comparisons["spectral50"]["nonworse_tasks"] >= 20
        and comparisons["spectral50"]["strictly_better_tasks"] >= 15,
        "target_gain_not_task_concentrated_vs_spectral": comparisons["spectral50"]["maximum_single_task_positive_reduction_share"] <= 0.20,
        "full_strictly_below_basis_pair_and_task_macro": aggregates["full"]["pair_weighted_mean"] < aggregates["basis"]["pair_weighted_mean"]
        and aggregates["full"]["task_macro_mean"] < aggregates["basis"]["task_macro_mean"],
    }
    rows.sort(key=lambda row: json.dumps(row, sort_keys=True, separators=(",", ":")))
    return {"local_pairs": len(local), "full_g_pairs": len(full), "basis_g_pairs": len(basis),
            "tasks": len(rows), "target_budget_utilization": target_spent / target_budget,
            "selected_manifest_sha256": manifest_hash(global_edges), "aggregates": aggregates,
            "comparisons": comparisons, "anonymous_task_rows": rows, "gates": gates,
            "all_gates_pass": all(gates.values())}


def close(left, right):
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(close(left[key], right[key]) for key in left)
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(close(a, b) for a, b in zip(left, right))
    if isinstance(left, float) or isinstance(right, float):
        return math.isclose(float(left), float(right), rel_tol=1e-8, abs_tol=1e-7)
    return left == right


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
        write = isinstance(mode, str) and any(char in mode for char in "wax+")
        write |= isinstance(flags, int) and bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
        if write:
            raise PermissionError("read_only")
        if path in allowed:
            opened[str(path)] += 1
        elif path.suffix.lower() not in (".py", ".pyc"):
            raise PermissionError("unlisted_data")
    sys.addaudithook(guard)
    raw = {name: checked_bytes(path, digest) for name, (path, digest) in FILES.items()}
    receipt_raw = checked_bytes(args.receipt, args.sha256, 5 * 1024 * 1024)
    metrics = reconstruct(raw)
    payload = json.loads(receipt_raw)
    if not close(payload["metrics"], metrics):
        raise ValueError("metric_mismatch")
    expected = "TARGET_A50_DEVELOPMENT_STRUCTURALLY_SUPPORTED" if metrics["all_gates_pass"] else "TARGET_A50_DEVELOPMENT_NOT_SUPPORTED"
    if payload["status"] != expected or payload.get("protocol_sha256") != PROTOCOL_SHA256:
        raise ValueError("status_or_protocol_mismatch")
    for path, digest in [*FILES.values(), (args.receipt, args.sha256)]:
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("post_hash_drift")
    return {"status": "INDEPENDENT_TARGET_A50_CLOSE", "protocol_sha256": PROTOCOL_SHA256,
            "receipt_sha256": args.sha256, "metrics": metrics, "data_open_counts": dict(opened),
            "real_pair_orientation_used": False, "selected_edge_identities_emitted": False,
            "protected_cohort_files_opened": 0, "gpu_jobs": 0, "paid_api_calls": 0,
            "neural_model_loads": 0, "neural_model_fits": 0}


if __name__ == "__main__":
    try:
        print(json.dumps(main(), sort_keys=True))
    except Exception as exc:
        print(json.dumps({"status": "FAILED_CLOSED", "exception_type": type(exc).__name__}, sort_keys=True))
        raise SystemExit(1)
