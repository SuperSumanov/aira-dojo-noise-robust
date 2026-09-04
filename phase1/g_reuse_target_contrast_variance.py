"""Target-local contrast variance for fixed-cost historical G-reuse graph designs.

This is a deterministic, label-blind structural calculation.  It neither fits nor
loads a neural model.  Real pair directions are canonicalized away by ``pairs``.
"""
from __future__ import annotations

from collections import defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path

from phase1.g_reuse_cycle_information import components
from phase1.g_reuse_min_token_basis import LENGTHS, choose_basis, read_lengths
from phase1.g_reuse_record_consistent_sensitivity import EXTRA, record_consistent
from phase1.g_reuse_spectral_midpoint import ResistanceState, TaskGraph
from phase1.g_reuse_task_breadth import derive_reuse
from phase1.historical_global_local_source_gate import project_batches, project_cards
from phase1.historical_label_reuse_support import INPUTS, check, checked, install_guard, pairs, project


MATCHED = ("spectral50", "cheapest50", "hash50")
ALL_ARMS = ("basis",) + MATCHED + ("full",)
ROUND_DIGITS = 15
RELATIVE_REDUCTION_MINIMUM = 0.03
NONWORSE_TASKS_MINIMUM = 20
STRICT_TASKS_MINIMUM = 15
MAX_TASK_POSITIVE_SHARE = 0.20
FLOAT_TOLERANCE = 1e-10
PROTOCOL_SHA256 = "203f7bc0a29a9d26fda82759f8bc5c7357d17c09e10729a03db62050baf336ab"


def quantile(values: list[float], probability: float) -> float:
    check(values and 0.0 <= probability <= 1.0, "invalid_quantile")
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def select_edges(local, full, basis, lengths, mode):
    """Reproduce the frozen midpoint selector while retaining private edge IDs."""
    check(mode in MATCHED, "unknown_arm")
    costs = {edge: lengths[edge[0]] + lengths[edge[1]] for edge in full}
    remaining = sorted(set(full) - set(basis))
    basis_tokens = sum(costs[edge] for edge in basis)
    full_tokens = sum(costs[edge] for edge in full)
    budget = (full_tokens - basis_tokens) // 2
    state = TaskGraph(local, full, basis)
    available, chosen, spent = list(remaining), [], 0
    selector = mode.removesuffix("50")
    if selector == "spectral":
        while True:
            fitting = [edge for edge in available if costs[edge] <= budget - spent]
            if not fitting:
                break
            scored = [
                (round(math.log1p(state.resistance(edge)) / costs[edge], ROUND_DIGITS), edge)
                for edge in fitting
            ]
            maximum = max(score for score, _ in scored)
            edge = min(edge for score, edge in scored if score == maximum)
            available.remove(edge)
            chosen.append(edge)
            spent += costs[edge]
            state.add(edge)
    else:
        if selector == "cheapest":
            ordered = sorted(available, key=lambda edge: (costs[edge], edge))
        else:
            ordered = sorted(
                available,
                key=lambda edge: (
                    hashlib.sha256((edge[0] + "\0" + edge[1]).encode()).hexdigest(),
                    edge,
                ),
            )
        for edge in ordered:
            if costs[edge] <= budget - spent:
                chosen.append(edge)
                spent += costs[edge]
                state.add(edge)
    check(spent <= budget, "selection_budget_exceeded")
    return {
        "edges": tuple(sorted(set(basis) | set(chosen))),
        "basis_tokens": basis_tokens,
        "full_tokens": full_tokens,
        "additional_token_budget": budget,
        "additional_tokens": spent,
        "additional_edges": len(chosen),
    }


def target_variances(local, selected_g):
    """Return local-edge effective resistances from shifted-Laplacian inverses."""
    nodes = {node for edge in local for node in edge}
    training = set(local) | set(selected_g)
    groups = components(nodes, training)
    group_of = {node: index for index, group in enumerate(groups) for node in group}
    by_group_training, by_group_target = defaultdict(list), defaultdict(list)
    for edge in training:
        check(group_of[edge[0]] == group_of[edge[1]], "training_partition_error")
        by_group_training[group_of[edge[0]]].append(edge)
    for edge in local:
        check(group_of[edge[0]] == group_of[edge[1]], "target_partition_error")
        by_group_target[group_of[edge[0]]].append(edge)
    output = []
    for index, target in by_group_target.items():
        group = groups[index]
        state = ResistanceState(group, by_group_training[index])
        for edge in target:
            value = state.resistance(edge)
            check(math.isfinite(value) and value >= -FLOAT_TOLERANCE, "invalid_variance")
            output.append(max(0.0, value))
    check(len(output) == len(local), "target_variance_coverage")
    return output


def selected_manifest(arm_edges):
    payload = {
        arm: [left + "\0" + right for left, right in sorted(edges)]
        for arm, edges in sorted(arm_edges.items())
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def calculate(local, full, basis, task_of, lengths):
    by_local, by_full, by_basis = defaultdict(list), defaultdict(list), defaultdict(list)
    for edge in local:
        by_local[task_of[edge[0]]].append(edge)
    for edge in full:
        by_full[task_of[edge[0]]].append(edge)
    for edge in basis:
        by_basis[task_of[edge[0]]].append(edge)

    identified_rows = []
    per_task_variances = []
    global_arm_edges = {arm: [] for arm in ALL_ARMS}
    for task in sorted(by_local):
        task_local = sorted(by_local[task])
        task_full = sorted(by_full[task])
        task_basis = sorted(by_basis[task])
        selections = {
            arm: select_edges(task_local, task_full, task_basis, lengths, arm)
            for arm in MATCHED
        }
        arm_edges = {
            "basis": tuple(task_basis),
            **{arm: selections[arm]["edges"] for arm in MATCHED},
            "full": tuple(task_full),
        }
        for arm, edges in arm_edges.items():
            global_arm_edges[arm].extend(edges)
        variances = {arm: target_variances(task_local, edges) for arm, edges in arm_edges.items()}
        row = {
            "local_pairs": len(task_local),
            "full_g_pairs": len(task_full),
            "basis_g_pairs": len(task_basis),
            "arm_g_pairs": {arm: len(edges) for arm, edges in arm_edges.items()},
            "arm_mean_target_variance": {
                arm: sum(values) / len(values) for arm, values in variances.items()
            },
            "matched_additional_token_budget": selections["spectral50"]["additional_token_budget"],
            "basis_g_tokens": selections["spectral50"]["basis_tokens"],
            "matched_additional_tokens": {
                arm: selections[arm]["additional_tokens"] for arm in MATCHED
            },
        }
        check(
            len({item["additional_token_budget"] for item in selections.values()}) == 1,
            "matched_budget_drift",
        )
        identified_rows.append(row)
        per_task_variances.append(variances)

    all_variances = {arm: [] for arm in ALL_ARMS}
    task_means = {arm: [] for arm in ALL_ARMS}
    for variances in per_task_variances:
        for arm, values in variances.items():
            all_variances[arm].extend(values)
            task_means[arm].append(sum(values) / len(values))

    aggregates = {
        arm: {
            "pair_weighted_mean": sum(all_variances[arm]) / len(all_variances[arm]),
            "task_macro_mean": sum(task_means[arm]) / len(task_means[arm]),
            "pooled_p90": quantile(all_variances[arm], 0.90),
        }
        for arm in ALL_ARMS
    }
    comparisons = {}
    for baseline in ("cheapest50", "hash50"):
        deltas = [base - spectral for base, spectral in zip(task_means[baseline], task_means["spectral50"])]
        positive = [max(0.0, value) for value in deltas]
        comparisons[baseline] = {
            "pair_weighted_relative_reduction": 1.0
            - aggregates["spectral50"]["pair_weighted_mean"]
            / aggregates[baseline]["pair_weighted_mean"],
            "nonworse_tasks": sum(value >= -FLOAT_TOLERANCE for value in deltas),
            "strictly_better_tasks": sum(value > FLOAT_TOLERANCE for value in deltas),
            "maximum_single_task_positive_reduction_share": max(positive) / sum(positive)
            if sum(positive) > 0
            else 1.0,
        }

    finite = all(
        math.isfinite(value) and value >= -FLOAT_TOLERANCE
        for values in all_variances.values()
        for value in values
    )
    gates = {
        "fixed_population_and_finite_variances": len(local) == 4689
        and len(full) == 2745
        and len(basis) == 790
        and len(identified_rows) == 28
        and finite,
        "spectral_pair_weighted_strictly_lower_and_reduction_at_least_0_03": all(
            aggregates["spectral50"]["pair_weighted_mean"]
            < aggregates[baseline]["pair_weighted_mean"]
            and comparisons[baseline]["pair_weighted_relative_reduction"]
            >= RELATIVE_REDUCTION_MINIMUM
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
            comparisons[baseline]["nonworse_tasks"] >= NONWORSE_TASKS_MINIMUM
            and comparisons[baseline]["strictly_better_tasks"] >= STRICT_TASKS_MINIMUM
            for baseline in ("cheapest50", "hash50")
        ),
        "spectral_gain_not_task_concentrated": all(
            comparisons[baseline]["maximum_single_task_positive_reduction_share"]
            <= MAX_TASK_POSITIVE_SHARE
            for baseline in ("cheapest50", "hash50")
        ),
        "full_strictly_below_basis_pair_and_task_macro":
            aggregates["full"]["pair_weighted_mean"] < aggregates["basis"]["pair_weighted_mean"]
            and aggregates["full"]["task_macro_mean"] < aggregates["basis"]["task_macro_mean"],
        "matched_task_budgets_and_spectral_known_token_total": all(
            all(row["matched_additional_tokens"][arm] <= row["matched_additional_token_budget"]
                for arm in MATCHED)
            for row in identified_rows
        ) and sum(row["matched_additional_tokens"]["spectral50"] + row["basis_g_tokens"]
                  for row in identified_rows) == 12610283,
    }

    anonymous_rows = sorted(
        identified_rows, key=lambda row: json.dumps(row, sort_keys=True, separators=(",", ":"))
    )
    return {
        "local_pairs": len(local),
        "full_g_pairs": len(full),
        "basis_g_pairs": len(basis),
        "tasks": len(identified_rows),
        "selected_manifest_sha256": selected_manifest(global_arm_edges),
        "aggregates": aggregates,
        "comparisons": comparisons,
        "anonymous_task_rows": anonymous_rows,
        "gates": gates,
        "all_gates_pass": all(gates.values()),
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
    check(
        json.loads(EXTRA["manifest"][0].read_text()).get("run_batch_manifest.jsonl")
        == EXTRA["batches"][1],
        "manifest_binding",
    )
    full = record_consistent(derive_reuse(local, global_all, run_of, task_of), cards, batches)
    local_ids = {node for edge in local for node in edge}
    with LENGTHS[0].open(newline="") as handle:
        lengths = read_lengths(local_ids, list(csv.DictReader(handle)))
    basis = choose_basis(local, full, lengths)
    result = calculate(local, full, basis, task_of, lengths)
    for path, digest in [*INPUTS.values(), *EXTRA.values(), LENGTHS]:
        checked(path, digest, scan=False)
    status = (
        "G_REUSE_SPECTRAL50_TARGET_CONTRAST_VARIANCE_SUPPORTED"
        if result["all_gates_pass"]
        else "G_REUSE_SPECTRAL50_TARGET_CONTRAST_VARIANCE_NOT_SUPPORTED"
    )
    return {
        "status": status,
        "protocol_sha256": PROTOCOL_SHA256,
        "metrics": result,
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "input_sha256": {
            **{key: value for key, (_, value) in INPUTS.items()},
            **{key: value for key, (_, value) in EXTRA.items()},
            "lengths": LENGTHS[1],
        },
        "real_pair_orientation_used": False,
        "selected_edge_identities_emitted": False,
        "protected_cohort_files_opened": 0,
        "data_open_counts": dict(opened),
        "gpu_jobs": 0,
        "paid_api_calls": 0,
        "neural_model_loads": 0,
        "neural_model_fits": 0,
        "base_model_updates": 0,
    }


if __name__ == "__main__":
    try:
        print(json.dumps(main(), sort_keys=True))
    except Exception as exc:
        print(json.dumps({"status": "FAILED_CLOSED", "exception_type": type(exc).__name__}, sort_keys=True))
        raise SystemExit(1)
