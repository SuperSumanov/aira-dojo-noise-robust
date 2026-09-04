"""Post-0L28 target-aware, cost-matched G-reuse selector development."""
from __future__ import annotations

from collections import defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path

import numpy as np

from phase1.g_reuse_cycle_information import components
from phase1.g_reuse_min_token_basis import LENGTHS, choose_basis, read_lengths
from phase1.g_reuse_record_consistent_sensitivity import EXTRA, record_consistent
from phase1.g_reuse_spectral_midpoint import ResistanceState
from phase1.g_reuse_target_contrast_variance import quantile, select_edges, selected_manifest, target_variances
from phase1.g_reuse_task_breadth import derive_reuse
from phase1.historical_global_local_source_gate import project_batches, project_cards
from phase1.historical_label_reuse_support import INPUTS, check, checked, install_guard, pairs, project


PROTOCOL_SHA256 = "ffd04c96b0433cdf917798e6169d79b0341c19a9846025311c1d3038b237f448"
MATCHED = ("targetA50", "spectral50", "cheapest50", "hash50")
CONTROLS = ("spectral50", "cheapest50", "hash50")
ALL_ARMS = ("basis",) + MATCHED + ("full",)
TOLERANCE = 1e-10


class TargetReductionState:
    """Shifted-inverse state with an exact local-contrast variance objective."""

    def __init__(self, local, full, basis):
        nodes = {node for edge in local for node in edge}
        groups = components(nodes, set(local) | set(full))
        self.states = []
        self.node_group = {}
        self.targets = []
        for group in groups:
            group_full = [edge for edge in full if edge[0] in group and edge[1] in group]
            if not group_full:
                continue
            initial = [edge for edge in local + basis if edge[0] in group and edge[1] in group]
            state = ResistanceState(group, initial)
            position = len(self.states)
            self.states.append(state)
            self.targets.append([edge for edge in local if edge[0] in group and edge[1] in group])
            for node in group:
                self.node_group[node] = position
        check(self.states and all(edge[0] in self.node_group for edge in full), "target_state_coverage")

    def reduction(self, edge):
        position = self.node_group[edge[0]]
        check(self.node_group[edge[1]] == position, "target_cross_component")
        state = self.states[position]
        i, j = state.index[edge[0]], state.index[edge[1]]
        direction = state.inverse[:, i] - state.inverse[:, j]
        resistance = float(direction[i] - direction[j])
        check(resistance >= -1e-8, "negative_candidate_resistance")
        differences = np.fromiter(
            (
                direction[state.index[left]] - direction[state.index[right]]
                for left, right in self.targets[position]
            ),
            dtype=np.float64,
        )
        value = float(differences @ differences) / (1.0 + max(0.0, resistance))
        check(math.isfinite(value) and value >= -1e-8, "invalid_target_reduction")
        return max(0.0, value)

    def add(self, edge):
        position = self.node_group[edge[0]]
        check(self.node_group[edge[1]] == position, "target_update_cross_component")
        self.states[position].add(edge)


def select_target_a50(local, full, basis, lengths):
    costs = {edge: lengths[edge[0]] + lengths[edge[1]] for edge in full}
    remaining = sorted(set(full) - set(basis))
    basis_tokens = sum(costs[edge] for edge in basis)
    full_tokens = sum(costs[edge] for edge in full)
    budget = (full_tokens - basis_tokens) // 2
    state = TargetReductionState(local, full, basis)
    available, chosen, spent, predicted_reduction = list(remaining), [], 0, 0.0
    while True:
        fitting = [edge for edge in available if costs[edge] <= budget - spent]
        if not fitting:
            break
        scored = [
            (round(state.reduction(edge) / costs[edge], 15), edge) for edge in fitting
        ]
        maximum = max(score for score, _ in scored)
        edge = min(edge for score, edge in scored if score == maximum)
        gain = state.reduction(edge)
        available.remove(edge)
        chosen.append(edge)
        spent += costs[edge]
        predicted_reduction += gain
        state.add(edge)
    check(spent <= budget, "target_budget_exceeded")
    return {
        "edges": tuple(sorted(set(basis) | set(chosen))),
        "basis_tokens": basis_tokens,
        "full_tokens": full_tokens,
        "additional_token_budget": budget,
        "additional_tokens": spent,
        "additional_edges": len(chosen),
        "predicted_target_variance_reduction": predicted_reduction,
    }


def calculate(local, full, basis, task_of, lengths):
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
        target = select_target_a50(task_local, task_full, task_basis, lengths)
        controls = {
            arm: select_edges(task_local, task_full, task_basis, lengths, arm)
            for arm in CONTROLS
        }
        selected = {"targetA50": target, **controls}
        check(len({item["additional_token_budget"] for item in selected.values()}) == 1,
              "matched_budget_drift")
        arm_edges = {
            "basis": tuple(task_basis),
            **{arm: selected[arm]["edges"] for arm in MATCHED},
            "full": tuple(task_full),
        }
        for arm, edges in arm_edges.items():
            global_edges[arm].extend(edges)
        variances = {arm: target_variances(task_local, edges) for arm, edges in arm_edges.items()}
        task_values.append(variances)
        rows.append({
            "local_pairs": len(task_local),
            "full_g_pairs": len(task_full),
            "basis_g_pairs": len(task_basis),
            "arm_g_pairs": {arm: len(edges) for arm, edges in arm_edges.items()},
            "arm_mean_target_variance": {
                arm: sum(values) / len(values) for arm, values in variances.items()
            },
            "additional_token_budget": target["additional_token_budget"],
            "basis_g_tokens": target["basis_tokens"],
            "additional_tokens": {arm: selected[arm]["additional_tokens"] for arm in MATCHED},
            "target_predicted_reduction": target["predicted_target_variance_reduction"],
        })

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
            "pooled_p90": quantile(pooled[arm], 0.9),
        }
        for arm in ALL_ARMS
    }
    comparisons = {}
    for control in CONTROLS:
        differences = [
            old - new for old, new in zip(task_means[control], task_means["targetA50"])
        ]
        positive = [max(0.0, value) for value in differences]
        comparisons[control] = {
            "pair_weighted_relative_reduction": 1.0
            - aggregates["targetA50"]["pair_weighted_mean"]
            / aggregates[control]["pair_weighted_mean"],
            "task_macro_relative_reduction": 1.0
            - aggregates["targetA50"]["task_macro_mean"]
            / aggregates[control]["task_macro_mean"],
            "nonworse_tasks": sum(value >= -TOLERANCE for value in differences),
            "strictly_better_tasks": sum(value > TOLERANCE for value in differences),
            "maximum_single_task_positive_reduction_share": max(positive) / sum(positive)
            if sum(positive) > 0 else 1.0,
        }
    target_spent = sum(row["additional_tokens"]["targetA50"] for row in rows)
    target_budget = sum(row["additional_token_budget"] for row in rows)
    finite = all(math.isfinite(value) and value >= -TOLERANCE
                 for values in pooled.values() for value in values)
    gates = {
        "fixed_population_budget_and_finite_variances": len(local) == 4689
        and len(full) == 2745 and len(basis) == 790 and len(rows) == 28 and finite
        and all(all(row["additional_tokens"][arm] <= row["additional_token_budget"]
                    for arm in MATCHED) for row in rows)
        and target_spent / target_budget >= 0.95,
        "target_pair_mean_effect_sizes_pass":
            comparisons["spectral50"]["pair_weighted_relative_reduction"] >= 0.01
            and all(comparisons[arm]["pair_weighted_relative_reduction"] >= 0.03
                    for arm in ("cheapest50", "hash50"))
            and all(aggregates["targetA50"]["pair_weighted_mean"]
                    < aggregates[arm]["pair_weighted_mean"] for arm in CONTROLS),
        "target_task_macro_strictly_lower_than_all_controls": all(
            aggregates["targetA50"]["task_macro_mean"] < aggregates[arm]["task_macro_mean"]
            for arm in CONTROLS),
        "target_p90_not_higher_than_all_controls": all(
            aggregates["targetA50"]["pooled_p90"] <= aggregates[arm]["pooled_p90"] + TOLERANCE
            for arm in CONTROLS),
        "target_task_breadth_vs_spectral":
            comparisons["spectral50"]["nonworse_tasks"] >= 20
            and comparisons["spectral50"]["strictly_better_tasks"] >= 15,
        "target_gain_not_task_concentrated_vs_spectral":
            comparisons["spectral50"]["maximum_single_task_positive_reduction_share"] <= 0.20,
        "full_strictly_below_basis_pair_and_task_macro":
            aggregates["full"]["pair_weighted_mean"] < aggregates["basis"]["pair_weighted_mean"]
            and aggregates["full"]["task_macro_mean"] < aggregates["basis"]["task_macro_mean"],
    }
    rows.sort(key=lambda row: json.dumps(row, sort_keys=True, separators=(",", ":")))
    return {
        "local_pairs": len(local), "full_g_pairs": len(full), "basis_g_pairs": len(basis),
        "tasks": len(rows), "target_budget_utilization": target_spent / target_budget,
        "selected_manifest_sha256": selected_manifest(global_edges),
        "aggregates": aggregates, "comparisons": comparisons,
        "anonymous_task_rows": rows, "gates": gates, "all_gates_pass": all(gates.values()),
    }


def main():
    extras = [path for path, _ in EXTRA.values()] + [LENGTHS[0]]
    opened = install_guard(extras)
    for path, digest in [*INPUTS.values(), *EXTRA.values(), LENGTHS]:
        checked(path, digest)
    local = pairs([json.loads(line) for line in INPUTS["local"][0].read_text().splitlines()])
    global_all = pairs([json.loads(line) for line in INPUTS["global"][0].read_text().splitlines()])
    grouped = json.loads(INPUTS["cards"][0].read_text())
    run_of, task_of = project(grouped)
    cards = project_cards(grouped)
    batch_rows = [json.loads(line) for line in EXTRA["batches"][0].read_text().splitlines()]
    batches = project_batches(batch_rows)
    check(set(batches) == set(grouped), "batch_inventory")
    check(json.loads(EXTRA["manifest"][0].read_text()).get("run_batch_manifest.jsonl")
          == EXTRA["batches"][1], "manifest_binding")
    full = record_consistent(derive_reuse(local, global_all, run_of, task_of), cards, batches)
    local_ids = {node for edge in local for node in edge}
    with LENGTHS[0].open(newline="") as handle:
        lengths = read_lengths(local_ids, list(csv.DictReader(handle)))
    basis = choose_basis(local, full, lengths)
    result = calculate(local, full, basis, task_of, lengths)
    for path, digest in [*INPUTS.values(), *EXTRA.values(), LENGTHS]:
        checked(path, digest, scan=False)
    status = ("TARGET_A50_DEVELOPMENT_STRUCTURALLY_SUPPORTED" if result["all_gates_pass"]
              else "TARGET_A50_DEVELOPMENT_NOT_SUPPORTED")
    return {
        "status": status, "protocol_sha256": PROTOCOL_SHA256, "metrics": result,
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "input_sha256": {**{k: d for k, (_, d) in INPUTS.items()},
                         **{k: d for k, (_, d) in EXTRA.items()}, "lengths": LENGTHS[1]},
        "timing_classification": "post_0L28_development_not_independent_confirmation",
        "real_pair_orientation_used": False, "selected_edge_identities_emitted": False,
        "protected_cohort_files_opened": 0, "gpu_jobs": 0, "paid_api_calls": 0,
        "neural_model_loads": 0, "neural_model_fits": 0, "base_model_updates": 0,
        "data_open_counts": dict(opened),
    }


if __name__ == "__main__":
    try:
        print(json.dumps(main(), sort_keys=True))
    except Exception as exc:
        print(json.dumps({"status": "FAILED_CLOSED", "exception_type": type(exc).__name__}, sort_keys=True))
        raise SystemExit(1)
