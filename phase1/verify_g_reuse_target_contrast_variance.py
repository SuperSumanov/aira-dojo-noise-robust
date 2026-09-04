"""Independent grounded-Laplacian verifier for target-local contrast variance."""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
import math
import os
from pathlib import Path
import sys

from phase1.verify_g_reuse_min_token_basis import FILES, Disjoint, checked_bytes
from phase1.verify_g_reuse_spectral_midpoint import GroundedState, IndependentTask, prepare


MATCHED = ("spectral50", "cheapest50", "hash50")
ALL_ARMS = ("basis",) + MATCHED + ("full",)
TOLERANCE = 1e-10
PROTOCOL_SHA256 = "203f7bc0a29a9d26fda82759f8bc5c7357d17c09e10729a03db62050baf336ab"


def independent_quantile(values, probability):
    if not values or not 0 <= probability <= 1:
        raise ValueError("invalid_quantile")
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower, upper = math.floor(position), math.ceil(position)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def independent_select_edges(local, full, basis, lengths, mode):
    if mode not in MATCHED:
        raise ValueError("unknown_selector")
    costs = {edge: lengths[edge[0]] + lengths[edge[1]] for edge in full}
    remaining = sorted(set(full) - set(basis))
    basis_tokens = sum(costs[edge] for edge in basis)
    full_tokens = sum(costs[edge] for edge in full)
    budget = (full_tokens - basis_tokens) // 2
    state = IndependentTask(local, full, basis)
    available, chosen, spent = list(remaining), [], 0
    selector = mode[:-2]
    if selector == "spectral":
        while True:
            fitting = [edge for edge in available if costs[edge] <= budget - spent]
            if not fitting:
                break
            candidates = []
            for edge in fitting:
                score = round(math.log1p(state.resistance(edge)) / costs[edge], 15)
                candidates.append((score, edge))
            best = max(score for score, _ in candidates)
            edge = min(edge for score, edge in candidates if score == best)
            available.remove(edge)
            chosen.append(edge)
            spent += costs[edge]
            state.add(edge)
    else:
        if selector == "cheapest":
            order = sorted(available, key=lambda edge: (costs[edge], edge))
        elif selector == "hash":
            order = sorted(
                available,
                key=lambda edge: (
                    hashlib.sha256((edge[0] + "\0" + edge[1]).encode()).hexdigest(),
                    edge,
                ),
            )
        else:
            raise ValueError("selector_parse")
        for edge in order:
            if costs[edge] <= budget - spent:
                chosen.append(edge)
                spent += costs[edge]
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
    }


def independent_target_variances(local, selected_g):
    nodes = {node for edge in local for node in edge}
    training = set(local) | set(selected_g)
    disjoint = Disjoint(nodes)
    for edge in training:
        disjoint.merge(*edge)
    groups = defaultdict(set)
    for node in nodes:
        groups[disjoint.root(node)].add(node)
    group_of = {node: root for root, group in groups.items() for node in group}
    training_by, target_by = defaultdict(list), defaultdict(list)
    for edge in training:
        if group_of[edge[0]] != group_of[edge[1]]:
            raise ValueError("training_partition")
        training_by[group_of[edge[0]]].append(edge)
    for edge in local:
        if group_of[edge[0]] != group_of[edge[1]]:
            raise ValueError("target_partition")
        target_by[group_of[edge[0]]].append(edge)
    values = []
    for root, targets in target_by.items():
        state = GroundedState(groups[root], training_by[root])
        for edge in targets:
            value = state.resistance(edge)
            if not math.isfinite(value) or value < -TOLERANCE:
                raise ValueError("invalid_variance")
            values.append(max(0.0, value))
    if len(values) != len(local):
        raise ValueError("variance_coverage")
    return values


def manifest_hash(arm_edges):
    payload = {
        arm: [left + "\0" + right for left, right in sorted(edges)]
        for arm, edges in sorted(arm_edges.items())
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


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
        task_local = sorted(by_local[task])
        task_full = sorted(by_full[task])
        task_basis = sorted(by_basis[task])
        selected = {
            arm: independent_select_edges(task_local, task_full, task_basis, lengths, arm)
            for arm in MATCHED
        }
        if len({result["additional_token_budget"] for result in selected.values()}) != 1:
            raise ValueError("budget_drift")
        arm_edges = {
            "basis": tuple(task_basis),
            **{arm: selected[arm]["edges"] for arm in MATCHED},
            "full": tuple(task_full),
        }
        for arm, edges in arm_edges.items():
            global_edges[arm].extend(edges)
        variances = {
            arm: independent_target_variances(task_local, edges)
            for arm, edges in arm_edges.items()
        }
        task_values.append(variances)
        rows.append(
            {
                "local_pairs": len(task_local),
                "full_g_pairs": len(task_full),
                "basis_g_pairs": len(task_basis),
                "arm_g_pairs": {arm: len(edges) for arm, edges in arm_edges.items()},
                "arm_mean_target_variance": {
                    arm: sum(values) / len(values) for arm, values in variances.items()
                },
                "matched_additional_token_budget": selected["spectral50"]["additional_token_budget"],
                "basis_g_tokens": selected["spectral50"]["basis_tokens"],
                "matched_additional_tokens": {
                    arm: selected[arm]["additional_tokens"] for arm in MATCHED
                },
            }
        )

    pooled = {arm: [] for arm in ALL_ARMS}
    task_means = {arm: [] for arm in ALL_ARMS}
    for variances in task_values:
        for arm, values in variances.items():
            pooled[arm].extend(values)
            task_means[arm].append(sum(values) / len(values))
    aggregates = {
        arm: {
            "pair_weighted_mean": sum(pooled[arm]) / len(pooled[arm]),
            "task_macro_mean": sum(task_means[arm]) / len(task_means[arm]),
            "pooled_p90": independent_quantile(pooled[arm], 0.9),
        }
        for arm in ALL_ARMS
    }
    comparisons = {}
    for baseline in ("cheapest50", "hash50"):
        differences = [
            baseline_value - spectral_value
            for baseline_value, spectral_value in zip(task_means[baseline], task_means["spectral50"])
        ]
        positive = [max(0.0, value) for value in differences]
        comparisons[baseline] = {
            "pair_weighted_relative_reduction": 1.0
            - aggregates["spectral50"]["pair_weighted_mean"]
            / aggregates[baseline]["pair_weighted_mean"],
            "nonworse_tasks": sum(value >= -TOLERANCE for value in differences),
            "strictly_better_tasks": sum(value > TOLERANCE for value in differences),
            "maximum_single_task_positive_reduction_share": max(positive) / sum(positive)
            if sum(positive) > 0
            else 1.0,
        }
    finite = all(
        math.isfinite(value) and value >= -TOLERANCE
        for values in pooled.values()
        for value in values
    )
    gates = {
        "fixed_population_and_finite_variances": len(local) == 4689
        and len(full) == 2745
        and len(basis) == 790
        and len(rows) == 28
        and finite,
        "spectral_pair_weighted_strictly_lower_and_reduction_at_least_0_03": all(
            aggregates["spectral50"]["pair_weighted_mean"]
            < aggregates[baseline]["pair_weighted_mean"]
            and comparisons[baseline]["pair_weighted_relative_reduction"] >= 0.03
            for baseline in ("cheapest50", "hash50")
        ),
        "spectral_task_macro_strictly_lower_than_both": all(
            aggregates["spectral50"]["task_macro_mean"]
            < aggregates[baseline]["task_macro_mean"]
            for baseline in ("cheapest50", "hash50")
        ),
        "spectral_pooled_p90_strictly_lower_than_both": all(
            aggregates["spectral50"]["pooled_p90"] < aggregates[baseline]["pooled_p90"]
            for baseline in ("cheapest50", "hash50")
        ),
        "spectral_task_breadth_vs_both": all(
            comparisons[baseline]["nonworse_tasks"] >= 20
            and comparisons[baseline]["strictly_better_tasks"] >= 15
            for baseline in ("cheapest50", "hash50")
        ),
        "spectral_gain_not_task_concentrated": all(
            comparisons[baseline]["maximum_single_task_positive_reduction_share"] <= 0.20
            for baseline in ("cheapest50", "hash50")
        ),
        "full_strictly_below_basis_pair_and_task_macro":
            aggregates["full"]["pair_weighted_mean"] < aggregates["basis"]["pair_weighted_mean"]
            and aggregates["full"]["task_macro_mean"] < aggregates["basis"]["task_macro_mean"],
        "matched_task_budgets_and_spectral_known_token_total": all(
            all(row["matched_additional_tokens"][arm] <= row["matched_additional_token_budget"]
                for arm in MATCHED)
            for row in rows
        ) and sum(row["matched_additional_tokens"]["spectral50"] + row["basis_g_tokens"]
                  for row in rows) == 12610283,
    }
    rows.sort(key=lambda row: json.dumps(row, sort_keys=True, separators=(",", ":")))
    return {
        "local_pairs": len(local),
        "full_g_pairs": len(full),
        "basis_g_pairs": len(basis),
        "tasks": len(rows),
        "selected_manifest_sha256": manifest_hash(global_edges),
        "aggregates": aggregates,
        "comparisons": comparisons,
        "anonymous_task_rows": rows,
        "gates": gates,
        "all_gates_pass": all(gates.values()),
    }


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
        write |= isinstance(flags, int) and bool(
            flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)
        )
        if write:
            raise PermissionError("read_only")
        if path in allowed:
            opened[str(path)] += 1
        elif path.suffix.lower() not in (".py", ".pyc"):
            raise PermissionError("unlisted_data")

    sys.addaudithook(guard)
    raw = {name: checked_bytes(path, digest) for name, (path, digest) in FILES.items()}
    receipt_raw = checked_bytes(args.receipt, args.sha256, 4 * 1024 * 1024)
    metrics = reconstruct(raw)
    payload = json.loads(receipt_raw)
    if not close(payload["metrics"], metrics):
        raise ValueError("independent_metric_mismatch")
    expected = (
        "G_REUSE_SPECTRAL50_TARGET_CONTRAST_VARIANCE_SUPPORTED"
        if metrics["all_gates_pass"]
        else "G_REUSE_SPECTRAL50_TARGET_CONTRAST_VARIANCE_NOT_SUPPORTED"
    )
    if payload["status"] != expected:
        raise ValueError("status_mismatch")
    if payload.get("protocol_sha256") != PROTOCOL_SHA256:
        raise ValueError("protocol_binding_mismatch")
    for path, digest in [*FILES.values(), (args.receipt, args.sha256)]:
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("post_hash_drift")
    return {
        "status": "INDEPENDENT_G_REUSE_TARGET_CONTRAST_VARIANCE_CLOSE",
        "protocol_sha256": PROTOCOL_SHA256,
        "receipt_sha256": args.sha256,
        "metrics": metrics,
        "data_open_counts": dict(opened),
        "real_pair_orientation_used": False,
        "selected_edge_identities_emitted": False,
        "protected_cohort_files_opened": 0,
        "gpu_jobs": 0,
        "paid_api_calls": 0,
        "neural_model_loads": 0,
        "neural_model_fits": 0,
    }


if __name__ == "__main__":
    try:
        print(json.dumps(main(), sort_keys=True))
    except Exception as exc:
        print(json.dumps({"status": "FAILED_CLOSED", "exception_type": type(exc).__name__}, sort_keys=True))
        raise SystemExit(1)
