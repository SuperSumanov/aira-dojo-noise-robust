#!/usr/bin/env python3
"""Confirm label-scarce endpoint-execution yield on an independent sibling graph.

The acquisition simulation consumes only unoriented graph topology.  It reconstructs
the exact senior-0819 train residual certified by the prior qualification gate and
emits aggregate trajectories without identities, labels, code, or prospective data.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
import math
import os
from pathlib import Path
from typing import Any

try:
    from phase1 import audit_historical_independent_sibling_graph_gate as qualification
    from phase1 import tree_node_label_yield as engine
except ImportError:  # direct execution from phase1/
    import audit_historical_independent_sibling_graph_gate as qualification
    import tree_node_label_yield as engine


PROTOCOL = "historical-independent-label-scarce-yield-confirmation-v1"
STATUS = (
    "FROZEN_AFTER_INDEPENDENT_GRAPH_QUALIFICATION_"
    "BEFORE_ANY_RESIDUAL_ACQUISITION_CURVE"
)
RESULT = "historical-independent-label-scarce-yield-confirmation-result-v1"


class ConfirmationError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ConfirmationError(message)


def read_object(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"unsafe JSON: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def load_protocol(path: Path, expected_sha: str) -> tuple[dict[str, Any], str]:
    observed = engine.raw_sha256(path)
    require(observed == expected_sha, "protocol SHA")
    value = read_object(path)
    require(value.get("protocol") == PROTOCOL, "protocol name")
    require(value.get("status") == STATUS, "protocol status")
    disclosure = value["discovery_disclosure"]
    require(disclosure["v11_b0_curve_was_seen_before_this_confirmation"] is True, "discovery disclosure")
    require(disclosure["independent_residual_acquisition_curve_seen"] is False, "residual curve already seen")
    require(disclosure["hypothesis_is_explicitly_refined_to_label_scarce_regime"] is True, "estimand drift")
    require(value["population_reconstruction"]["senior_test_rows_forbidden"] is True, "test prohibition")
    require(value["analysis"]["no_gate_threshold_budget_population_or_primary_method_changes_after_readout"] is True, "rescue drift")
    require(value["promotion_gates"]["all_gates_required_no_rescue"] is True, "gate rescue")
    return value, observed


def verify_package_manifest(path: Path) -> None:
    require(path.is_file() and not path.is_symlink(), "unsafe package manifest")
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        pieces = line.split("  ", 1)
        require(len(pieces) == 2 and len(pieces[0]) == 64, f"manifest row {number}")
        expected, name = pieces
        require(engine.raw_sha256(path.parent / name) == expected, f"manifest member {name}")


def verify_qualification(args: argparse.Namespace, protocol: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    immutable = protocol["immutable_inputs"]
    paths = {
        "qualification_protocol": Path(args.qualification_protocol).resolve(),
        "qualification_result": Path(args.qualification_result).resolve(),
        "qualification_verification": Path(args.qualification_verification).resolve(),
        "qualification_package_manifest": Path(args.qualification_package_manifest).resolve(),
        "producer_graph_qualification_source": Path(qualification.__file__).resolve(),
        "independent_graph_qualification_source": Path(args.independent_graph_qualification_source).resolve(),
        "producer_acquisition_engine": Path(engine.__file__).resolve(),
        "independent_acquisition_engine": Path(args.independent_acquisition_engine).resolve(),
    }
    for key, path in paths.items():
        require(engine.raw_sha256(path) == immutable[key]["sha256"], f"{key} SHA")
    verify_package_manifest(paths["qualification_package_manifest"])
    result = read_object(paths["qualification_result"])
    verification = read_object(paths["qualification_verification"])
    result_binding = immutable["qualification_result"]
    require(result["classification"] == result_binding["required_classification"], "qualification class")
    require(result["identity_fingerprints"]["strict_residual"] == result_binding["required_residual_fingerprint"], "residual fingerprint binding")
    require(all(result["integrity_gates"].values()) and all(result["support_gates"].values()), "qualification gates")
    verify_binding = immutable["qualification_verification"]
    require(verification["status"] == verify_binding["required_status"], "qualification verifier status")
    require(verification["all_aggregate_fields_equal"] is True, "qualification verifier fields")
    require(verification["producer_result_sha256"] == result_binding["sha256"], "qualification verifier closure")
    return result, {key: engine.raw_sha256(path) for key, path in paths.items()}


def reconstruct_graph(
    args: argparse.Namespace,
    protocol: dict[str, Any],
    qualification_result: dict[str, Any],
) -> tuple[engine.Graph, dict[str, str]]:
    old_protocol_path = Path(args.qualification_protocol).resolve()
    old_protocol_sha = protocol["immutable_inputs"]["qualification_protocol"]["sha256"]
    old_protocol = qualification.load_protocol(old_protocol_path, old_protocol_sha)
    qualification.verify_published_dependencies(args, old_protocol)
    qualification.verify_security_receipt(Path(args.senior_security_receipt).resolve(), old_protocol)

    immutable = old_protocol["immutable_inputs"]
    raw_paths = {
        "senior_safe_cards": Path(args.senior_cards).resolve(),
        "senior_run_split": Path(args.senior_run_split).resolve(),
        "senior_decision": Path(args.senior_decision).resolve(),
    }
    for key, path in raw_paths.items():
        require(qualification.sha256(path) == immutable[key]["sha256"], f"{key} SHA")

    senior_protocol_path = Path(args.senior_quarantine_protocol).resolve()
    senior_binding = immutable["senior_0819_quarantine_protocol"]
    require(qualification.sha256(senior_protocol_path) == senior_binding["sha256"], "senior protocol SHA")
    senior_protocol = qualification.quarantine.load_protocol(senior_protocol_path, senior_binding["sha256"])
    all_runs, held_runs = qualification.relation.base.load_run_split(raw_paths["senior_run_split"], senior_protocol)
    cards, _ = qualification.relation.base.load_cards(raw_paths["senior_safe_cards"], all_runs)
    rows, diagnostics = qualification.relation.read_rows(
        raw_paths["senior_decision"], cards, held_runs, senior_protocol["immutable_inputs"]["decision"]
    )
    core = [row for row in rows if qualification.quarantine.is_core(row, held_runs)]
    train_core = [row for row in core if row.split == "train"]
    require(len(core) == 1270 and len(train_core) == 952 and diagnostics["rows"] == 7644, "senior core")

    v11 = qualification.load_v11_graph(Path(args.v11_pairs).resolve(), old_protocol)
    v11_identities = set(v11["endpoints"]) | set(v11["parents"])
    residual, _ = qualification.strict_residual(train_core, v11_identities, set(v11["runs"]))
    require(qualification.fingerprint(residual) == qualification_result["identity_fingerprints"]["strict_residual"], "residual fingerprint")

    edges: list[engine.Edge] = []
    seen: set[tuple[str, str]] = set()
    context: dict[str, tuple[str, str]] = {}
    parent_context: dict[str, tuple[str, str]] = {}
    for row in residual:
        u, v = row.unordered
        require(u != v and (u, v) not in seen, "residual edge uniqueness")
        require(row.first_run == row.second_run == row.parent_run, "residual run context")
        seen.add((u, v))
        pair_context = (row.task, row.first_run)
        for node in (u, v):
            require(context.setdefault(node, pair_context) == pair_context, "endpoint context")
        require(parent_context.setdefault(row.parent, pair_context) == pair_context, "parent context")
        edges.append(engine.Edge(u, v, row.parent, row.task, row.first_run))
    incident_mutable: dict[str, list[int]] = defaultdict(list)
    for index, edge in enumerate(edges):
        incident_mutable[edge.u].append(index)
        incident_mutable[edge.v].append(index)
    graph = engine.Graph(
        edges=edges,
        nodes=tuple(sorted(context)),
        incident={node: tuple(indices) for node, indices in incident_mutable.items()},
        context=context,
    )
    expected = protocol["population_reconstruction"]["require_exact_residual_profile"]
    observed = {
        "pairs": len(graph.edges),
        "endpoints": len(graph.nodes),
        "parents": len({edge.parent for edge in graph.edges}),
        "physical_runs": len({edge.run for edge in graph.edges}),
        "tasks": len({edge.task for edge in graph.edges}),
    }
    for key, value in observed.items():
        require(value == expected[key] == qualification_result["strict_residual_profile"][key], f"residual {key}")
    return graph, {key: qualification.sha256(path) for key, path in raw_paths.items()}


def budgets(protocol: dict[str, Any]) -> list[int]:
    acquisition = protocol["acquisition"]
    total = int(acquisition["endpoint_population"])
    denominator = int(acquisition["budget_fraction_denominator"])
    values = [math.floor(total * int(numerator) / denominator) for numerator in acquisition["budget_fraction_numerators"]]
    require(values == acquisition["derived_report_budgets"], "derived budgets")
    require(values == sorted(set(values)) and values[-1] == acquisition["maximum_endpoint_budget"], "budget order")
    return values


def _share_at_most(row: dict[str, Any], field: str, numerator: int, denominator: int) -> bool:
    value = row[field]
    return value["numerator"] * denominator <= numerator * value["denominator"]


def evaluate_confirmation_gates(
    rows: dict[str, list[dict[str, Any]]], protocol: dict[str, Any]
) -> tuple[dict[str, Any], str]:
    checkpoints = budgets(protocol)
    by_budget: dict[str, Any] = {}
    pointwise_wins = 0
    uniform_per_seed_integral: dict[int, int] = defaultdict(int)
    for budget in checkpoints:
        uniform = [row for row in rows["uniform_edge"] if row["budget"] == budget]
        balanced = [row for row in rows["balanced_closure_greedy"] if row["budget"] == budget]
        require(len(uniform) == 256 and len(balanced) == 32, "seed rows")
        uniform_edges = engine.nearest_rank([row["closed_edges"] for row in uniform], 0.5)
        balanced_edges = [row["closed_edges"] for row in balanced]
        balanced_median = engine.nearest_rank(balanced_edges, 0.5)
        for row in uniform:
            uniform_per_seed_integral[int(row["seed"])] += int(row["closed_edges"])
        pointwise_wins += int(balanced_median > uniform_edges)
        by_budget[str(budget)] = {
            "uniform_edge_median_closed_edges": uniform_edges,
            "balanced_greedy_minimum_closed_edges": min(balanced_edges),
            "balanced_greedy_median_closed_edges": balanced_median,
            "balanced_median_strictly_better": balanced_median > uniform_edges,
        }

    per_seed_integral: dict[int, int] = defaultdict(int)
    for row in rows["balanced_closure_greedy"]:
        per_seed_integral[int(row["seed"])] += int(row["closed_edges"])
    require(sorted(per_seed_integral) == list(range(32)), "greedy seed closure")
    require(sorted(uniform_per_seed_integral) == list(range(256)), "uniform seed closure")
    uniform_integrals = list(uniform_per_seed_integral.values())
    uniform_integral_median = engine.nearest_rank(uniform_integrals, 0.5)
    worst_integral = min(per_seed_integral.values())
    integrated_gate = worst_integral * 5 >= uniform_integral_median * 6
    pointwise_gate = pointwise_wins >= 5

    terminal = checkpoints[-1]
    uniform_terminal = [row for row in rows["uniform_edge"] if row["budget"] == terminal]
    balanced_terminal = [row for row in rows["balanced_closure_greedy"] if row["budget"] == terminal]
    uniform_summary = {
        field: engine.nearest_rank([int(row[field]) for row in uniform_terminal], 0.5)
        for field in ("closed_edges", "parents", "tasks", "physical_runs")
    }
    balanced_minimum = {
        field: min(int(row[field]) for row in balanced_terminal)
        for field in ("closed_edges", "parents", "tasks", "physical_runs")
    }
    terminal_gates = {
        "yield_at_least_11_over_10": balanced_minimum["closed_edges"] * 10 >= uniform_summary["closed_edges"] * 11,
        "parent_breadth_at_least_2_over_3": balanced_minimum["parents"] * 3 >= uniform_summary["parents"] * 2,
        "task_breadth_at_least_3_over_4": balanced_minimum["tasks"] * 4 >= uniform_summary["tasks"] * 3,
        "run_breadth_at_least_3_over_4": balanced_minimum["physical_runs"] * 4 >= uniform_summary["physical_runs"] * 3,
        "task_anti_dominance_at_most_1_over_3": all(
            _share_at_most(row, "maximum_single_task_share", 1, 3) for row in balanced_terminal
        ),
        "run_anti_dominance_at_most_1_over_10": all(
            _share_at_most(row, "maximum_single_run_share", 1, 10) for row in balanced_terminal
        ),
    }
    all_pass = integrated_gate and pointwise_gate and all(terminal_gates.values())
    receipt = {
        "by_budget": by_budget,
        "integrated_uniform_edge_by_seed": {
            "minimum": min(uniform_integrals),
            "p05_nearest_rank": engine.nearest_rank(uniform_integrals, 0.05),
            "median_nearest_rank": uniform_integral_median,
            "p95_nearest_rank": engine.nearest_rank(uniform_integrals, 0.95),
            "maximum": max(uniform_integrals),
        },
        "integrated_balanced_greedy_by_tie_seed": {
            "minimum": min(per_seed_integral.values()),
            "median_nearest_rank": engine.nearest_rank(list(per_seed_integral.values()), 0.5),
            "maximum": max(per_seed_integral.values()),
        },
        "integrated_yield_gate": integrated_gate,
        "pointwise_balanced_median_wins": pointwise_wins,
        "pointwise_consistency_gate": pointwise_gate,
        "terminal_budget": terminal,
        "terminal_uniform_edge_medians": uniform_summary,
        "terminal_balanced_greedy_minima": balanced_minimum,
        "terminal_gates": terminal_gates,
        "all_promotion_gates_pass": all_pass,
    }
    key = "classification_if_all_pass" if all_pass else "classification_otherwise"
    return receipt, protocol["promotion_gates"][key]


def build(args: argparse.Namespace) -> dict[str, Any]:
    protocol, protocol_sha = load_protocol(Path(args.protocol).resolve(), args.protocol_sha256)
    qualification_result, qualification_hashes = verify_qualification(args, protocol)
    graph, raw_hashes = reconstruct_graph(args, protocol, qualification_result)
    checkpoints = budgets(protocol)
    maximum = checkpoints[-1]
    random_start, random_stop = protocol["acquisition"]["random_baseline_seeds"]["first_seed_in_half_open_range"]
    greedy_start, greedy_stop = protocol["acquisition"]["greedy_tie_seeds"]["first_seed_in_half_open_range"]

    method_rows: dict[str, list[dict[str, Any]]] = {}
    for method in ("uniform_node", "uniform_edge"):
        output: list[dict[str, Any]] = []
        for seed in range(int(random_start), int(random_stop)):
            actions = (
                engine.uniform_node_actions(graph, seed)
                if method == "uniform_node"
                else engine.uniform_edge_actions(graph, seed, maximum)
            )
            output.extend(engine.snapshots_from_actions(graph, seed, checkpoints, actions))
        method_rows[method] = output
    for method, balanced in (("closure_greedy", False), ("balanced_closure_greedy", True)):
        output = []
        for seed in range(int(greedy_start), int(greedy_stop)):
            output.extend(
                engine.snapshots_from_actions(
                    graph,
                    seed,
                    checkpoints,
                    engine.greedy_actions(graph, seed, maximum, balanced),
                )
            )
        method_rows[method] = output

    gates, classification = evaluate_confirmation_gates(method_rows, protocol)
    return {
        "protocol": RESULT,
        "status": "COMPLETE",
        "protocol_sha256": protocol_sha,
        "input_sha256": {**qualification_hashes, **raw_hashes},
        "graph_census": {
            "pairs": len(graph.edges),
            "endpoints": len(graph.nodes),
            "parents": len({edge.parent for edge in graph.edges}),
            "physical_runs": len({edge.run for edge in graph.edges}),
            "tasks": len({edge.task for edge in graph.edges}),
            "orientation_free_identity_fingerprint_sha256": qualification_result["strict_residual_profile"]["orientation_free_identity_fingerprint_sha256"],
        },
        "budget_fractions": [
            {"numerator": numerator, "denominator": 32, "endpoint_budget": budget}
            for numerator, budget in zip(range(1, 7), checkpoints)
        ],
        "methods": {
            method: {"rows": output, "summary_by_budget": engine.summarize(output, checkpoints)}
            for method, output in method_rows.items()
        },
        "primary_gates": gates,
        "classification": classification,
        "scope": {
            "aggregate_only": True,
            "row_endpoint_parent_task_run_identities_emitted": False,
            "pair_orientation_gap_grade_code_prediction_runtime_used": False,
            "senior_test_rows_used": False,
            "prospective_first960_target300_target522_values_read": False,
            "gpu_api_model_fit_base_update": "0/0/0/0",
        },
    }


def secure_write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(engine.canonical(value) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--protocol-sha256", required=True)
    parser.add_argument("--qualification-protocol", required=True)
    parser.add_argument("--qualification-result", required=True)
    parser.add_argument("--qualification-verification", required=True)
    parser.add_argument("--qualification-package-manifest", required=True)
    parser.add_argument("--independent-graph-qualification-source", required=True)
    parser.add_argument("--independent-acquisition-engine", required=True)
    parser.add_argument("--v11-pairs", required=True)
    parser.add_argument("--v11-lineage", required=True)
    parser.add_argument("--senior-quarantine-protocol", required=True)
    parser.add_argument("--senior-quarantine-result", required=True)
    parser.add_argument("--senior-quarantine-verification", required=True)
    parser.add_argument("--senior-quarantine-manifest", required=True)
    parser.add_argument("--senior-security-receipt", required=True)
    parser.add_argument("--senior-cards", required=True)
    parser.add_argument("--senior-run-split", required=True)
    parser.add_argument("--senior-decision", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = build(args)
    output = Path(args.output).resolve()
    secure_write(output, result)
    print(engine.canonical({
        "status": result["status"],
        "classification": result["classification"],
        "protocol_sha256": result["protocol_sha256"],
        "output_sha256": engine.raw_sha256(output),
        "scope": result["scope"],
    }))


if __name__ == "__main__":
    main()
