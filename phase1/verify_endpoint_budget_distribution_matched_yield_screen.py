#!/usr/bin/env python3
"""Independent primal/aggregate verifier for distribution-matched yield screen."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from phase1 import endpoint_budget_label_efficiency_smoke as smoke


PROTOCOL = "endpoint-budget-distribution-matched-yield-screen-v1"
SELECTION_PUBLIC = "endpoint-budget-distribution-matched-yield-selection-public-v1"
SELECTION_PRIVATE = "endpoint-budget-distribution-matched-yield-selection-private-v1"
FIT_CELL = "endpoint-budget-distribution-matched-yield-fit-cell-v1"
FIT_RESULT = "endpoint-budget-distribution-matched-yield-fit-result-v1"
FIT_PRIVATE = "endpoint-budget-distribution-matched-yield-private-pair-witness-v1"
VERIFY_RESULT = "endpoint-budget-distribution-matched-yield-independent-verification-v1"
OLD_UNIFORM = "exact_b_uniform_edge"
OLD_YIELD = "yield_guarded_breadth"
NEW_ARM = "distribution_matched_yield"


class VerificationError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def file_sha(path: Path) -> str:
    return smoke.file_sha(path)


def load(path: Path) -> dict[str, Any]:
    return smoke.object_file(path)


def private_mode(path: Path) -> bool:
    return os.name == "nt" or path.stat().st_mode & 0o077 == 0


def ratio(numerator: int, denominator: int) -> dict[str, Any]:
    return smoke.graph_source.engine.fraction(numerator, denominator)


def selected_by_budget(private: dict[str, Any]) -> dict[int, set[str]]:
    result: dict[int, set[str]] = {}
    previous: set[str] = set()
    for entry in private["selected_endpoint_ids_by_checkpoint"]:
        budget = int(entry["endpoint_budget"])
        identifiers = entry["endpoint_ids"]
        require(identifiers == sorted(set(identifiers)), "selection identifiers")
        selected = set(identifiers)
        require(len(selected) == budget and previous <= selected, "selection exact nested")
        require(budget not in result, "selection budget duplicate")
        result[budget] = selected
        previous = selected
    return result


def direct_metrics(graph: Any, selections: dict[int, set[str]], protocol: dict[str, Any]) -> list[dict[str, Any]]:
    checkpoints = [int(value) for value in protocol["selection"]["checkpoints"]]
    exact_pairs = [int(value) for value in protocol["selection"]["exact_induced_pair_count"]]
    available = Counter(edge.task for edge in graph.edges)
    total_available = len(graph.edges)
    require(sum(available.values()) == total_available and total_available > 0, "availability")
    output: list[dict[str, Any]] = []
    for budget, expected in zip(checkpoints, exact_pairs):
        selected = selections[budget]
        closed = [edge for edge in graph.edges if edge.u in selected and edge.v in selected]
        require(len(closed) == expected, "exact pair count")
        tasks = Counter(edge.task for edge in closed)
        runs = Counter(edge.run for edge in closed)
        task_share = ratio(max(tasks.values()), len(closed))
        run_share = ratio(max(runs.values()), len(closed))
        require(task_share["numerator"] * 5 <= task_share["denominator"], "task cap")
        require(run_share["numerator"] * 10 <= run_share["denominator"], "run cap")
        l1 = sum(abs(tasks.get(task, 0) / expected - count / total_available) for task, count in available.items())
        integer_objective = sum(abs(total_available * tasks.get(task, 0) - expected * count) for task, count in available.items())
        output.append({
            "selected_endpoints": len(selected),
            "induced_pairs": len(closed),
            "represented_tasks": len(tasks),
            "represented_runs": len(runs),
            "parents": len({edge.parent for edge in closed}),
            "maximum_single_task_share": task_share,
            "maximum_single_run_share": run_share,
            "task_distribution_l1": l1,
            "integer_distribution_objective": integer_objective,
            "endpoint_budget": budget,
        })
    require(sum(row["represented_runs"] for row in output) >= int(protocol["selection"]["integrated_closed_run_floor"]), "run floor")
    require(output[-1]["parents"] >= int(protocol["selection"]["terminal_parent_floor"]), "parent floor")
    return output


def old_yield_metrics(graph: Any, old_private: dict[str, Any], protocol: dict[str, Any]) -> list[dict[str, Any]]:
    old = smoke.entries_by_budget(old_private, OLD_YIELD)
    return direct_metrics(graph, old, protocol)


def fingerprint(selections: dict[int, set[str]], checkpoints: list[int]) -> str:
    return hashlib.sha256(
        "\n".join(
            hashlib.sha256((str(step) + "\0" + node).encode()).hexdigest()
            for step, budget in enumerate(checkpoints)
            for node in sorted(selections[budget])
        ).encode()
    ).hexdigest()


def witness_cells(value: dict[str, Any]) -> dict[tuple[str, int], dict[str, dict[str, Any]]]:
    result: dict[tuple[str, int], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in value["rows"]:
        cell = (row["arm"], int(row["endpoint_budget"]))
        pair = row["pair_identity_sha256"]
        require(pair not in result[cell], "witness duplicate")
        result[cell][pair] = row
    return result


def arrays(rows: list[dict[str, Any]]) -> dict[str, list[float]]:
    return smoke.arrays_from_pair_witness(rows)


def signs(values: list[float], tasks: list[str]) -> dict[str, int]:
    grouped: dict[str, float] = defaultdict(float)
    for value, task in zip(values, tasks):
        grouped[task] += value
    output = {"negative": 0, "zero": 0, "positive": 0}
    for value in grouped.values():
        output["negative" if value < 0 else "positive" if value > 0 else "zero"] += 1
    return output


def compare(
    left: dict[str, list[float]], right: dict[str, list[float]], tasks: list[str], runs: list[str], seed: int
) -> dict[str, Any]:
    deltas = {
        "accuracy": [a - b for a, b in zip(left["correct"], right["correct"])],
        "log_loss": [a - b for a, b in zip(left["log_loss"], right["log_loss"])],
        "brier": [a - b for a, b in zip(left["brier"], right["brier"])],
    }
    grouped: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for index, task in enumerate(tasks):
        for metric, values in deltas.items():
            grouped[task][metric].append(values[index])
    task_macro = {
        metric: statistics.fmean(statistics.fmean(grouped[task][metric]) for task in sorted(grouped))
        for metric in deltas
    }
    return {
        "pooled_metric_delta": {metric: statistics.fmean(values) for metric, values in deltas.items()},
        "task_macro_metric_delta": task_macro,
        "task_net_correct_sign_counts": signs(deltas["accuracy"], tasks),
        "accuracy_task_clustered_bootstrap": smoke.bootstrap_interval(deltas["accuracy"], tasks, 2000, seed),
        "accuracy_run_clustered_bootstrap": smoke.bootstrap_interval(deltas["accuracy"], runs, 2000, seed + 1),
        "_accuracy_values": deltas["accuracy"],
    }


def main_verify(args: argparse.Namespace) -> dict[str, Any]:
    protocol_path = args.protocol.resolve()
    require(file_sha(protocol_path) == args.protocol_sha256, "protocol SHA")
    protocol = load(protocol_path)
    require(protocol.get("protocol") == PROTOCOL, "protocol name")
    require(protocol.get("status") == "FROZEN_AFTER_TASK_HETEROGENEITY_AUDIT_BEFORE_NEW_SELECTION_OR_PREDICTION", "freeze status")
    bindings = protocol["input_bindings"]
    fixed = {
        "old_smoke_protocol": (args.old_protocol.resolve(), bindings["old_smoke_protocol_sha256"], False),
        "firewall_receipt": (args.firewall_receipt.resolve(), bindings["firewall_receipt_sha256"], True),
        "train_only_topology": (args.train_topology.resolve(), bindings["train_only_topology_sha256"], True),
        "train_only_labels": (args.train_labels.resolve(), bindings["train_only_labels_sha256"], True),
        "old_selection_public": (args.old_selection_public.resolve(), bindings["old_selection_public_sha256"], False),
        "old_selection_private": (args.old_selection_private.resolve(), bindings["old_selection_private_sha256"], True),
        "old_fit_summary": (args.old_fit_summary.resolve(), bindings["old_fit_summary_sha256"], False),
        "old_private_pair_witness": (args.old_private_pairs.resolve(), bindings["old_private_pair_witness_sha256"], True),
        "task_heterogeneity_public": (args.task_audit_public.resolve(), bindings["task_heterogeneity_public_sha256"], False),
        "safe_cards": (args.cards_root.resolve() / "cards.safe.json", bindings["safe_cards_sha256"], False),
        "safe_cards_security_receipt": (args.cards_root.resolve() / "security_scan.json", bindings["safe_cards_security_receipt_sha256"], False),
    }
    for name, (path, expected, private) in fixed.items():
        require(file_sha(path) == expected, f"fixed input SHA {name}")
        if private:
            require(private_mode(path), f"private mode {name}")

    old_protocol, old_sha = smoke.load_protocol(args.old_protocol.resolve(), bindings["old_smoke_protocol_sha256"])
    compatibility = SimpleNamespace(
        firewall_receipt=args.firewall_receipt,
        train_topology=args.train_topology,
        source_commit=bindings["artifact_source_commit"],
    )
    full, train, evaluation, _receipt = smoke.load_firewall_population(compatibility, old_sha)
    require((len(train.edges), len(evaluation.edges)) == (401, 138), "population")

    selection_public_path = args.selection_public.resolve()
    selection_private_path = args.selection_private.resolve()
    selection_public = load(selection_public_path)
    selection_private = load(selection_private_path)
    require(selection_public.get("protocol") == SELECTION_PUBLIC and selection_public.get("status") == "COMPLETE", "selection public")
    require(selection_private.get("protocol") == SELECTION_PRIVATE, "selection private")
    require(file_sha(selection_private_path) == selection_public["private_selection_sha256"], "selection SHA")
    require(private_mode(selection_private_path), "selection private mode")
    selections = selected_by_budget(selection_private)
    checkpoints = [int(value) for value in protocol["selection"]["checkpoints"]]
    require(set(selections) == set(checkpoints), "selection checkpoints")
    direct = direct_metrics(train, selections, protocol)
    require(selection_public["solver"]["metrics"] == direct, "direct selection metrics")
    require(selection_public["solver"]["primary_integer_objective"] == sum(row["integer_distribution_objective"] for row in direct), "primary objective")
    require(selection_public["solver"]["primary_solver_status"] == selection_public["solver"]["tie_solver_status"] == 0, "solver status")
    require(selection_public["solver"]["primary_solver_mip_gap"] == selection_public["solver"]["tie_solver_mip_gap"] == 0.0, "solver gaps")
    require(selection_public["solver"]["integrated_closed_runs"] == sum(row["represented_runs"] for row in direct), "integrated runs")
    observed_fingerprint = fingerprint(selections, checkpoints)
    require(observed_fingerprint == selection_private["selection_fingerprint_sha256"] == selection_public["solver"]["private_selection_fingerprint_sha256"], "selection fingerprint")
    old_direct = old_yield_metrics(train, load(args.old_selection_private.resolve()), protocol)
    expected_comparison = [
        {
            "endpoint_budget": new["endpoint_budget"],
            "new_task_distribution_l1": new["task_distribution_l1"],
            "old_yield_task_distribution_l1": old["task_distribution_l1"],
            "new_minus_old_l1": new["task_distribution_l1"] - old["task_distribution_l1"],
            "new_induced_pairs": new["induced_pairs"],
            "old_yield_induced_pairs": old["induced_pairs"],
        }
        for new, old in zip(direct, old_direct)
    ]
    require(selection_public["comparison_to_old_yield"] == expected_comparison, "old yield comparison")
    require(smoke.public_has_no_identities(selection_public, full), "selection identity leak")

    labels = load(args.train_labels.resolve())
    require(labels.get("senior_test_rows_emitted") == 0 and labels.get("all_source_rows_train") is True, "label firewall")
    eval_rows = []
    for item in labels["rows"]:
        if smoke.run_fold(item["physical_run"]) == 0:
            eval_rows.append(SimpleNamespace(
                first=item["better"], second=item["worse"], parent=item["parent"],
                task=item["task"], first_run=item["physical_run"],
            ))
    require(len(eval_rows) == 138, "eval label rows")
    pair_ids = [smoke.pair_identity_sha(row) for row in eval_rows]
    tasks = [smoke.identity_sha("task", row.task) for row in eval_rows]
    runs = [smoke.identity_sha("physical_run", row.first_run) for row in eval_rows]

    summary_path = args.fit_summary.resolve()
    private_path = args.new_private_pairs.resolve()
    summary = load(summary_path)
    private = load(private_path)
    require(summary.get("protocol") == FIT_RESULT and summary.get("status") == "COMPLETE", "fit summary")
    require(private.get("protocol") == FIT_PRIVATE, "fit private")
    require(file_sha(private_path) == summary["private_pair_witness_sha256"], "fit private SHA")
    require(private_mode(private_path), "fit private mode")
    new_cells = witness_cells(private)
    old_cells = witness_cells(load(args.old_private_pairs.resolve()))
    fit_budgets = [int(value) for value in protocol["fit"]["budgets"]]
    require(set(new_cells) == {(NEW_ARM, budget) for budget in fit_budgets}, "new witness cells")
    new_arrays: dict[int, dict[str, list[float]]] = {}
    model_rows = {int(row["endpoint_budget"]): row for row in summary["model_rows"]}
    require(set(model_rows) == set(fit_budgets), "model rows")
    for budget in fit_budgets:
        rows = [new_cells[(NEW_ARM, budget)][pair] for pair in pair_ids]
        require([row["pair_identity_sha256"] for row in rows] == pair_ids, "new pair set")
        require(all(row["task_sha256"] == task and row["physical_run_sha256"] == run for row, task, run in zip(rows, tasks, runs)), "new fingerprints")
        values = arrays(rows)
        new_arrays[budget] = values
        model = model_rows[budget]
        direct_metrics_fit = {
            "pairwise_accuracy": statistics.fmean(values["correct"]),
            "log_loss": statistics.fmean(values["log_loss"]),
            "brier_score": statistics.fmean(values["brier"]),
        }
        require(all(math.isclose(float(model[key]), value, rel_tol=1e-12, abs_tol=1e-12) for key, value in direct_metrics_fit.items()), "model metrics")
        require(model["selected_endpoints"] == budget, "model endpoint budget")
        closed = [edge for edge in train.edges if edge.u in selections[budget] and edge.v in selections[budget]]
        require(model["induced_unique_train_pairs"] == len(closed), "model train pairs")
        checkpoint = args.checkpoint_dir.resolve() / f"{NEW_ARM}__{budget}.json"
        require(file_sha(checkpoint) == summary["fit_checkpoints"][checkpoint.name], "checkpoint SHA")
        require(private_mode(checkpoint), "checkpoint mode")
        cell = load(checkpoint)
        require(cell.get("protocol") == FIT_CELL and cell["metrics"] == {key: model[key] for key in cell["metrics"]}, "checkpoint metrics")
        require(cell["pair_rows"] == rows, "checkpoint rows")

    expected_comparisons: dict[str, Any] = {}
    raw_accuracy: dict[tuple[int, str], list[float]] = {}
    for budget in fit_budgets:
        expected_comparisons[str(budget)] = {}
        for label, arm, seed in (
            ("new_minus_old_yield", OLD_YIELD, 20260830 + budget),
            ("new_minus_uniform", OLD_UNIFORM, 20261830 + budget),
        ):
            old_rows = [old_cells[(arm, budget)][pair] for pair in pair_ids]
            comparison = compare(new_arrays[budget], arrays(old_rows), tasks, runs, seed)
            raw_accuracy[(budget, label)] = comparison.pop("_accuracy_values")
            expected_comparisons[str(budget)][label] = comparison
    require(summary["comparisons"] == expected_comparisons, "paired comparisons")

    task_counts = Counter(tasks)
    dominant = sorted(task_counts, key=lambda key: (-task_counts[key], key))[0]
    terminal = fit_budgets[-1]
    retained = [index for index, task in enumerate(tasks) if task != dominant]
    drop_delta = statistics.fmean(raw_accuracy[(terminal, "new_minus_uniform")][index] for index in retained)
    require(math.isclose(summary["drop_dominant_task_terminal_new_minus_uniform_accuracy_delta"], drop_delta, rel_tol=0, abs_tol=1e-15), "drop dominant")
    l1_by_budget = {int(row["endpoint_budget"]): row for row in selection_public["comparison_to_old_yield"]}
    terminal_uniform = expected_comparisons[str(terminal)]["new_minus_uniform"]
    terminal_yield = expected_comparisons[str(terminal)]["new_minus_old_yield"]
    gates = {
        "new_task_distribution_l1_strictly_below_old_yield_at_both_budgets": all(l1_by_budget[b]["new_task_distribution_l1"] < l1_by_budget[b]["old_yield_task_distribution_l1"] for b in fit_budgets),
        "new_minus_old_yield_task_macro_accuracy_positive_at_both_budgets": all(expected_comparisons[str(b)]["new_minus_old_yield"]["task_macro_metric_delta"]["accuracy"] > 0 for b in fit_budgets),
        "terminal_new_minus_uniform_pooled_accuracy_positive": terminal_uniform["pooled_metric_delta"]["accuracy"] > 0,
        "terminal_new_minus_uniform_task_macro_accuracy_nonnegative": terminal_uniform["task_macro_metric_delta"]["accuracy"] >= 0,
        "terminal_new_minus_uniform_drop_dominant_accuracy_nonnegative": drop_delta >= 0,
        "terminal_new_minus_old_yield_log_loss_and_brier_nonworse": terminal_yield["pooled_metric_delta"]["log_loss"] <= 0 and terminal_yield["pooled_metric_delta"]["brier"] <= 0,
        "terminal_new_minus_old_yield_positive_task_count_at_least_negative": terminal_yield["task_net_correct_sign_counts"]["positive"] >= terminal_yield["task_net_correct_sign_counts"]["negative"],
    }
    require(summary["screen_gates"] == gates, "screen gates")
    expected_classification = protocol["interpretation"]["pass_classification"] if all(gates.values()) else protocol["interpretation"]["fail_classification"]
    require(summary["classification"] == expected_classification, "classification")
    require(smoke.public_has_no_identities(summary, full), "summary identity leak")

    with args.runs_csv.resolve().open("r", encoding="utf-8", newline="") as handle:
        csv_rows = list(csv.DictReader(handle))
    require(len(csv_rows) == len(summary["model_rows"]), "CSV rows")
    for observed, expected in zip(csv_rows, summary["model_rows"]):
        require(observed == {key: str(value) for key, value in expected.items()}, "CSV model row")

    return {
        "protocol": VERIFY_RESULT,
        "protocol_sha256": args.protocol_sha256,
        "analysis_source_commit": summary["analysis_source_commit"],
        "selection_public_sha256": file_sha(selection_public_path),
        "selection_private_sha256": file_sha(selection_private_path),
        "fit_summary_sha256": file_sha(summary_path),
        "runs_csv_sha256": file_sha(args.runs_csv.resolve()),
        "fit_private_witness_sha256": file_sha(private_path),
        "selection_primal_and_objective_reconstructed": True,
        "selection_optimality_source": "bound HiGHS status=0 and mip_gap=0; verifier independently checks primal constraints and objective value but does not rerun MILP",
        "evaluation_pair_set_and_40_new_task_budget_rows_reconstructed": True,
        "all_aggregate_fields_equal": True,
        "producer_module_imported": False,
        "model_refits": 0,
        "scope": {
            "historical_train_rows_only": True,
            "senior_test_rows_used": False,
            "prospective_values_used": False,
            "gpu_api_model_fit_base_update": "0/0/0/0",
        },
        "status": "INDEPENDENT_PRIMAL_AND_AGGREGATE_RECONSTRUCTION_EXACT",
    }


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    for name in (
        "protocol", "old-protocol", "firewall-receipt", "train-topology", "train-labels",
        "cards-root", "old-selection-public", "old-selection-private", "old-fit-summary",
        "old-private-pairs", "task-audit-public", "selection-public", "selection-private",
        "fit-summary", "runs-csv", "new-private-pairs", "checkpoint-dir", "output",
    ):
        value.add_argument(f"--{name}", type=Path, required=True)
    value.add_argument("--protocol-sha256", required=True)
    return value


def write_exclusive(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(smoke.canonical_bytes(value))


def main() -> None:
    args = parser().parse_args()
    result = main_verify(args)
    write_exclusive(args.output.resolve(), result)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
