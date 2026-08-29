#!/usr/bin/env python3
"""Independent reconstruction of the label-scarce yield confirmation.

This verifier deliberately does not import the confirmation producer.  It uses the
previously independent senior/v11 decoder and the separately implemented acquisition
engine, then compares the full aggregate result exactly.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any

try:
    from phase1 import verify_historical_independent_sibling_graph_gate as graph_audit
    from phase1 import verify_tree_node_label_yield as engine
except ImportError:  # direct execution from phase1/
    import verify_historical_independent_sibling_graph_gate as graph_audit
    import verify_tree_node_label_yield as engine


PROTOCOL = "historical-independent-label-scarce-yield-confirmation-v1"
STATUS = (
    "FROZEN_AFTER_INDEPENDENT_GRAPH_QUALIFICATION_"
    "BEFORE_ANY_RESIDUAL_ACQUISITION_CURVE"
)
RESULT = "historical-independent-label-scarce-yield-confirmation-result-v1"


class IndependentConfirmationError(RuntimeError):
    pass


def check(condition: bool, message: str) -> None:
    if not condition:
        raise IndependentConfirmationError(message)


def digest(path: Path) -> str:
    check(path.is_file() and not path.is_symlink(), f"unsafe file: {path}")
    value = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(8 << 20):
            value.update(block)
    return value.hexdigest()


def read_object(path: Path) -> dict[str, Any]:
    check(path.is_file() and not path.is_symlink(), f"unsafe JSON: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    check(isinstance(value, dict), f"JSON object required: {path}")
    return value


def load_protocol(path: Path, expected_sha: str) -> tuple[dict[str, Any], str]:
    observed = digest(path)
    check(observed == expected_sha, "protocol SHA")
    value = read_object(path)
    check(value.get("protocol") == PROTOCOL, "protocol name")
    check(value.get("status") == STATUS, "protocol status")
    disclosure = value["discovery_disclosure"]
    check(disclosure["v11_b0_curve_was_seen_before_this_confirmation"] is True, "discovery disclosure")
    check(disclosure["independent_residual_acquisition_curve_seen"] is False, "residual curve already seen")
    check(disclosure["hypothesis_is_explicitly_refined_to_label_scarce_regime"] is True, "estimand drift")
    check(value["population_reconstruction"]["senior_test_rows_forbidden"] is True, "test prohibition")
    check(value["analysis"]["no_gate_threshold_budget_population_or_primary_method_changes_after_readout"] is True, "rescue drift")
    check(value["promotion_gates"]["all_gates_required_no_rescue"] is True, "gate rescue")
    return value, observed


def verify_package_manifest(path: Path) -> None:
    check(path.is_file() and not path.is_symlink(), "unsafe package manifest")
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        pieces = line.split("  ", 1)
        check(len(pieces) == 2 and len(pieces[0]) == 64, f"manifest row {number}")
        expected, name = pieces
        check(digest(path.parent / name) == expected, f"manifest member {name}")


def verify_qualification(args: argparse.Namespace, protocol: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    immutable = protocol["immutable_inputs"]
    paths = {
        "qualification_protocol": Path(args.qualification_protocol).resolve(),
        "qualification_result": Path(args.qualification_result).resolve(),
        "qualification_verification": Path(args.qualification_verification).resolve(),
        "qualification_package_manifest": Path(args.qualification_package_manifest).resolve(),
        "producer_graph_qualification_source": Path(args.producer_graph_qualification_source).resolve(),
        "independent_graph_qualification_source": Path(graph_audit.__file__).resolve(),
        "producer_acquisition_engine": Path(args.producer_acquisition_engine).resolve(),
        "independent_acquisition_engine": Path(engine.__file__).resolve(),
    }
    for key, path in paths.items():
        check(digest(path) == immutable[key]["sha256"], f"{key} SHA")
    verify_package_manifest(paths["qualification_package_manifest"])
    result = read_object(paths["qualification_result"])
    verification = read_object(paths["qualification_verification"])
    result_binding = immutable["qualification_result"]
    check(result["classification"] == result_binding["required_classification"], "qualification class")
    check(result["identity_fingerprints"]["strict_residual"] == result_binding["required_residual_fingerprint"], "residual fingerprint binding")
    check(all(result["integrity_gates"].values()) and all(result["support_gates"].values()), "qualification gates")
    verifier_binding = immutable["qualification_verification"]
    check(verification["status"] == verifier_binding["required_status"], "qualification verifier status")
    check(verification["all_aggregate_fields_equal"] is True, "qualification verifier fields")
    check(verification["producer_result_sha256"] == result_binding["sha256"], "qualification verifier closure")
    return result, {key: digest(path) for key, path in paths.items()}


def reconstruct_topology(
    args: argparse.Namespace,
    protocol: dict[str, Any],
    qualification_result: dict[str, Any],
) -> tuple[engine.Topology, dict[str, str]]:
    old_protocol_path = Path(args.qualification_protocol).resolve()
    old_protocol_sha = protocol["immutable_inputs"]["qualification_protocol"]["sha256"]
    old_protocol = graph_audit.load_protocol(old_protocol_path, old_protocol_sha)
    graph_audit.verify_parent_certificates(args, old_protocol)
    graph_audit.verify_security_receipt(Path(args.senior_security_receipt).resolve(), old_protocol)

    immutable = old_protocol["immutable_inputs"]
    raw_paths = {
        "senior_safe_cards": Path(args.senior_cards).resolve(),
        "senior_run_split": Path(args.senior_run_split).resolve(),
        "senior_decision": Path(args.senior_decision).resolve(),
    }
    for key, path in raw_paths.items():
        check(digest(path) == immutable[key]["sha256"], f"{key} SHA")

    senior_protocol_path = Path(args.senior_quarantine_protocol).resolve()
    senior_binding = immutable["senior_0819_quarantine_protocol"]
    check(digest(senior_protocol_path) == senior_binding["sha256"], "senior protocol SHA")
    senior_protocol = graph_audit.senior.frozen_protocol(senior_protocol_path, senior_binding["sha256"])
    all_runs, held_runs = graph_audit.senior.independent.prior.manifest(raw_paths["senior_run_split"], senior_protocol)
    nodes, _ = graph_audit.senior.independent.prior.card_index(raw_paths["senior_safe_cards"], all_runs)
    rows, diagnostics = graph_audit.senior.independent.parse_decisions(
        raw_paths["senior_decision"],
        nodes,
        held_runs,
        senior_protocol["immutable_inputs"]["decision"],
    )
    core = [row for row in rows if graph_audit.senior.selected_core(row, held_runs)]
    train_core = [row for row in core if row.split == "train"]
    check(len(core) == 1270 and len(train_core) == 952 and diagnostics["rows"] == 7644, "senior core")

    v11 = graph_audit.load_v11_graph(Path(args.v11_pairs).resolve(), old_protocol)
    v11_identities = set(v11["endpoints"]) | set(v11["parents"])
    residual, _ = graph_audit.strict_residual(train_core, v11_identities, set(v11["runs"]))
    check(graph_audit.identity_fingerprint(residual) == qualification_result["identity_fingerprints"]["strict_residual"], "residual fingerprint")

    pairs: list[engine.Pair] = []
    seen: set[tuple[str, str]] = set()
    context: dict[str, tuple[str, str]] = {}
    parent_context: dict[str, tuple[str, str]] = {}
    for row in residual:
        left, right = row.pair()
        check(left != right and (left, right) not in seen, "residual edge uniqueness")
        check(row.high_run == row.low_run == row.declared_run, "residual run context")
        seen.add((left, right))
        pair_context = (row.task, row.high_run)
        for vertex in (left, right):
            check(context.setdefault(vertex, pair_context) == pair_context, "endpoint context")
        check(parent_context.setdefault(row.declared, pair_context) == pair_context, "parent context")
        pairs.append(engine.Pair(left, right, row.declared, row.task, row.high_run))
    mutable: dict[str, list[int]] = defaultdict(list)
    for index, pair in enumerate(pairs):
        mutable[pair.left].append(index)
        mutable[pair.right].append(index)
    topology = engine.Topology(
        pairs=pairs,
        vertices=tuple(sorted(context)),
        adjacency={vertex: tuple(indices) for vertex, indices in mutable.items()},
        vertex_context=context,
    )
    expected = protocol["population_reconstruction"]["require_exact_residual_profile"]
    observed = {
        "pairs": len(topology.pairs),
        "endpoints": len(topology.vertices),
        "parents": len({pair.parent for pair in topology.pairs}),
        "physical_runs": len({pair.run for pair in topology.pairs}),
        "tasks": len({pair.task for pair in topology.pairs}),
    }
    for key, value in observed.items():
        check(value == expected[key] == qualification_result["strict_residual_profile"][key], f"residual {key}")
    return topology, {key: digest(path) for key, path in raw_paths.items()}


def budgets(protocol: dict[str, Any]) -> list[int]:
    acquisition = protocol["acquisition"]
    total = int(acquisition["endpoint_population"])
    denominator = int(acquisition["budget_fraction_denominator"])
    values = [math.floor(total * int(numerator) / denominator) for numerator in acquisition["budget_fraction_numerators"]]
    check(values == acquisition["derived_report_budgets"], "derived budgets")
    check(values == sorted(set(values)) and values[-1] == acquisition["maximum_endpoint_budget"], "budget order")
    return values


def share_at_most(row: dict[str, Any], field: str, numerator: int, denominator: int) -> bool:
    value = row[field]
    return value["numerator"] * denominator <= numerator * value["denominator"]


def gate_receipt(
    rows: dict[str, list[dict[str, Any]]], protocol: dict[str, Any]
) -> tuple[dict[str, Any], str]:
    checkpoints = budgets(protocol)
    by_budget: dict[str, Any] = {}
    pointwise_wins = 0
    uniform_per_seed_integral: dict[int, int] = defaultdict(int)
    for budget in checkpoints:
        uniform = [row for row in rows["uniform_edge"] if row["budget"] == budget]
        balanced = [row for row in rows["balanced_closure_greedy"] if row["budget"] == budget]
        check(len(uniform) == 256 and len(balanced) == 32, "seed rows")
        uniform_edges = engine.rank_statistic([row["closed_edges"] for row in uniform], 0.5)
        balanced_edges = [row["closed_edges"] for row in balanced]
        balanced_median = engine.rank_statistic(balanced_edges, 0.5)
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
    check(sorted(per_seed_integral) == list(range(32)), "greedy seed closure")
    check(sorted(uniform_per_seed_integral) == list(range(256)), "uniform seed closure")
    uniform_integrals = list(uniform_per_seed_integral.values())
    uniform_integral_median = engine.rank_statistic(uniform_integrals, 0.5)
    integrated_gate = min(per_seed_integral.values()) * 5 >= uniform_integral_median * 6
    pointwise_gate = pointwise_wins >= 5

    terminal = checkpoints[-1]
    uniform_terminal = [row for row in rows["uniform_edge"] if row["budget"] == terminal]
    balanced_terminal = [row for row in rows["balanced_closure_greedy"] if row["budget"] == terminal]
    uniform_summary = {
        field: engine.rank_statistic([int(row[field]) for row in uniform_terminal], 0.5)
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
            share_at_most(row, "maximum_single_task_share", 1, 3) for row in balanced_terminal
        ),
        "run_anti_dominance_at_most_1_over_10": all(
            share_at_most(row, "maximum_single_run_share", 1, 10) for row in balanced_terminal
        ),
    }
    all_pass = integrated_gate and pointwise_gate and all(terminal_gates.values())
    receipt = {
        "by_budget": by_budget,
        "integrated_uniform_edge_by_seed": {
            "minimum": min(uniform_integrals),
            "p05_nearest_rank": engine.rank_statistic(uniform_integrals, 0.05),
            "median_nearest_rank": uniform_integral_median,
            "p95_nearest_rank": engine.rank_statistic(uniform_integrals, 0.95),
            "maximum": max(uniform_integrals),
        },
        "integrated_balanced_greedy_by_tie_seed": {
            "minimum": min(per_seed_integral.values()),
            "median_nearest_rank": engine.rank_statistic(list(per_seed_integral.values()), 0.5),
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


def reconstruct(args: argparse.Namespace) -> dict[str, Any]:
    protocol, protocol_sha = load_protocol(Path(args.protocol).resolve(), args.protocol_sha256)
    qualification_result, qualification_hashes = verify_qualification(args, protocol)
    topology, raw_hashes = reconstruct_topology(args, protocol, qualification_result)
    checkpoints = budgets(protocol)
    maximum = checkpoints[-1]
    random_start, random_stop = protocol["acquisition"]["random_baseline_seeds"]["first_seed_in_half_open_range"]
    greedy_start, greedy_stop = protocol["acquisition"]["greedy_tie_seeds"]["first_seed_in_half_open_range"]

    method_rows: dict[str, list[dict[str, Any]]] = {}
    for method in ("uniform_node", "uniform_edge"):
        output: list[dict[str, Any]] = []
        for seed in range(int(random_start), int(random_stop)):
            actions = engine.node_plan(topology, seed) if method == "uniform_node" else engine.edge_plan(topology, seed, maximum)
            output.extend(engine.trajectory(topology, seed, checkpoints, actions))
        method_rows[method] = output
    for method, balanced in (("closure_greedy", False), ("balanced_closure_greedy", True)):
        output = []
        for seed in range(int(greedy_start), int(greedy_stop)):
            output.extend(engine.trajectory(topology, seed, checkpoints, engine.greedy_plan(topology, seed, maximum, balanced)))
        method_rows[method] = output

    gates, classification = gate_receipt(method_rows, protocol)
    return {
        "protocol": RESULT,
        "status": "COMPLETE",
        "protocol_sha256": protocol_sha,
        "input_sha256": {**qualification_hashes, **raw_hashes},
        "graph_census": {
            "pairs": len(topology.pairs),
            "endpoints": len(topology.vertices),
            "parents": len({pair.parent for pair in topology.pairs}),
            "physical_runs": len({pair.run for pair in topology.pairs}),
            "tasks": len({pair.task for pair in topology.pairs}),
            "orientation_free_identity_fingerprint_sha256": qualification_result["strict_residual_profile"]["orientation_free_identity_fingerprint_sha256"],
        },
        "budget_fractions": [
            {"numerator": numerator, "denominator": 32, "endpoint_budget": budget}
            for numerator, budget in zip(range(1, 7), checkpoints)
        ],
        "methods": {
            method: {"rows": output, "summary_by_budget": engine.method_summary(output, checkpoints)}
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


def verify(args: argparse.Namespace) -> dict[str, Any]:
    result_path = Path(args.result).resolve()
    result_hash = digest(result_path)
    check(result_hash == args.result_sha256, "result SHA")
    observed = read_object(result_path)
    expected = reconstruct(args)
    check(observed == expected, "producer and independent reconstruction differ")
    return {
        "protocol": "historical-independent-label-scarce-yield-independent-verification-v1",
        "status": "INDEPENDENT_RECONSTRUCTION_EXACT",
        "protocol_sha256": args.protocol_sha256,
        "source_result_sha256": result_hash,
        "classification": expected["classification"],
        "all_aggregate_fields_equal": True,
        "producer_imported": False,
        "scope": expected["scope"],
    }


def write_exclusive(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
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
    parser.add_argument("--producer-graph-qualification-source", required=True)
    parser.add_argument("--producer-acquisition-engine", required=True)
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
    parser.add_argument("--result", required=True)
    parser.add_argument("--result-sha256", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    receipt = verify(args)
    write_exclusive(Path(args.output).resolve(), receipt)
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False))


if __name__ == "__main__":
    main()
