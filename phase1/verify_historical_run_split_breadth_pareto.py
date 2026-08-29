#!/usr/bin/env python3
"""Independent reconstruction of the run-split breadth/yield falsification."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any

try:
    from phase1 import verify_historical_independent_label_scarce_yield as prior
    from phase1 import verify_tree_node_label_yield as engine
except ImportError:  # direct execution from phase1/
    import verify_historical_independent_label_scarce_yield as prior
    import verify_tree_node_label_yield as engine


PROTOCOL = "historical-run-split-breadth-pareto-falsification-v1"
STATUS = "FROZEN_AFTER_FULL_GRAPH_READOUT_BEFORE_HASH_RUN_SPLIT_COUNTS_OR_CURVES"
RESULT = "historical-run-split-breadth-pareto-falsification-result-v1"
SPLIT_SALT = "PARETO-RUN-SPLIT-V1"


class IndependentParetoError(RuntimeError):
    pass


def check(condition: bool, message: str) -> None:
    if not condition:
        raise IndependentParetoError(message)


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
    check(value["role"]["post_readout_falsification_only"] is True, "role drift")
    check(value["role"]["not_an_independent_external_confirmation"] is True, "confirmation drift")
    known = value["known_after_full_graph_readout"]
    check(known["hash_run_split_counts_seen"] is False, "split counts already seen")
    check(known["hash_run_split_acquisition_curves_seen"] is False, "split curves already seen")
    check(value["analysis"]["no_threshold_split_budget_or_method_change_after_readout"] is True, "rescue drift")
    return value, observed


def verify_prior_artifacts(args: argparse.Namespace, protocol: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    immutable = protocol["immutable_inputs"]
    paths = {
        "prior_protocol": Path(args.prior_protocol).resolve(),
        "prior_result": Path(args.prior_result).resolve(),
        "prior_verification": Path(args.prior_verification).resolve(),
        "prior_package_manifest": Path(args.prior_package_manifest).resolve(),
        "prior_producer_source": Path(args.prior_producer_source).resolve(),
        "prior_independent_source": Path(prior.__file__).resolve(),
    }
    for key, path in paths.items():
        check(digest(path) == immutable[key]["sha256"], f"{key} SHA")
    prior.verify_package_manifest(paths["prior_package_manifest"])
    result = read_object(paths["prior_result"])
    verification = read_object(paths["prior_verification"])
    check(result["classification"] == immutable["prior_result"]["required_classification"], "prior class")
    check(result["graph_census"]["pairs"] == 539 and result["graph_census"]["endpoints"] == 1036, "prior graph")
    check(result["scope"]["row_endpoint_parent_task_run_identities_emitted"] is False, "prior identity release")
    check(verification["status"] == immutable["prior_verification"]["required_status"], "prior verifier status")
    check(verification["all_aggregate_fields_equal"] is True, "prior verifier fields")
    check(verification["source_result_sha256"] == immutable["prior_result"]["sha256"], "prior verifier closure")
    return result, {key: digest(path) for key, path in paths.items()}


def fold_for_run(run: str) -> int:
    payload = f"{SPLIT_SALT}\0{run}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big") & 1


def topology_from_pairs(pairs: list[engine.Pair]) -> engine.Topology:
    mutable: dict[str, list[int]] = defaultdict(list)
    context: dict[str, tuple[str, str]] = {}
    seen: set[tuple[str, str]] = set()
    for index, pair in enumerate(pairs):
        key = (pair.left, pair.right)
        check(key not in seen, "duplicate split edge")
        seen.add(key)
        pair_context = (pair.task, pair.run)
        for vertex in key:
            check(context.setdefault(vertex, pair_context) == pair_context, "split endpoint context")
            mutable[vertex].append(index)
    return engine.Topology(
        pairs=pairs,
        vertices=tuple(sorted(context)),
        adjacency={vertex: tuple(indices) for vertex, indices in mutable.items()},
        vertex_context=context,
    )


def topology_fingerprint(topology: engine.Topology) -> str:
    records = ["\0".join((pair.left, pair.right, pair.parent, pair.task, pair.run)) for pair in topology.pairs]
    return hashlib.sha256(("\n".join(sorted(records)) + "\n").encode()).hexdigest()


def profile(topology: engine.Topology) -> dict[str, Any]:
    by_task = Counter(pair.task for pair in topology.pairs)
    by_run = Counter(pair.run for pair in topology.pairs)
    pairs = len(topology.pairs)
    return {
        "pairs": pairs,
        "endpoints": len(topology.vertices),
        "parents": len({pair.parent for pair in topology.pairs}),
        "physical_runs": len(by_run),
        "tasks": len(by_task),
        "maximum_single_task_pair_share": engine.ratio(max(by_task.values(), default=0), max(1, pairs)),
        "maximum_single_run_pair_share": engine.ratio(max(by_run.values(), default=0), max(1, pairs)),
        "orientation_free_identity_fingerprint_sha256": topology_fingerprint(topology),
    }


def share_at_most(value: dict[str, Any], numerator: int, denominator: int) -> bool:
    return value["numerator"] * denominator <= numerator * value["denominator"]


def support_gates(profile_value: dict[str, Any], protocol: dict[str, Any]) -> dict[str, bool]:
    gate = protocol["support_gates_per_fold"]
    return {
        "minimum_pairs": profile_value["pairs"] >= gate["minimum_pairs"],
        "minimum_endpoints": profile_value["endpoints"] >= gate["minimum_endpoints"],
        "minimum_parents": profile_value["parents"] >= gate["minimum_parents"],
        "minimum_physical_runs": profile_value["physical_runs"] >= gate["minimum_physical_runs"],
        "minimum_tasks": profile_value["tasks"] >= gate["minimum_tasks"],
        "maximum_single_task_pair_share": share_at_most(profile_value["maximum_single_task_pair_share"], 1, 3),
        "maximum_single_run_pair_share": share_at_most(profile_value["maximum_single_run_pair_share"], 1, 10),
    }


def cross_fold_overlap(first: engine.Topology, second: engine.Topology) -> dict[str, int]:
    def sets(topology: engine.Topology) -> dict[str, set[Any]]:
        return {
            "pairs": {(pair.left, pair.right) for pair in topology.pairs},
            "endpoints": set(topology.vertices),
            "parents": {pair.parent for pair in topology.pairs},
            "physical_runs": {pair.run for pair in topology.pairs},
        }
    left, right = sets(first), sets(second)
    return {key: len(left[key] & right[key]) for key in left}


def budgets(topology: engine.Topology, protocol: dict[str, Any]) -> list[int]:
    acquisition = protocol["acquisition"]
    denominator = int(acquisition["budget_fraction_denominator"])
    values = [math.floor(len(topology.vertices) * int(top) / denominator) for top in acquisition["budget_fraction_numerators"]]
    check(values == sorted(set(values)) and values[0] >= 2, "split budgets")
    return values


def trajectory_integrals(rows: list[dict[str, Any]], field: str, expected_seeds: range) -> list[int]:
    grouped: dict[int, int] = defaultdict(int)
    for row in rows:
        grouped[int(row["seed"])] += int(row[field])
    check(sorted(grouped) == list(expected_seeds), f"{field} seed closure")
    return list(grouped.values())


def evaluate_fold(rows: dict[str, list[dict[str, Any]]], checkpoints: list[int]) -> dict[str, Any]:
    by_budget: dict[str, Any] = {}
    pointwise_noninferior = 0
    for budget in checkpoints:
        uniform = [row for row in rows["uniform_edge"] if row["budget"] == budget]
        balanced = [row for row in rows["balanced_closure_greedy"] if row["budget"] == budget]
        check(len(uniform) == 256 and len(balanced) == 32, "split seed rows")
        entry: dict[str, Any] = {}
        for field in ("closed_edges", "tasks", "physical_runs", "parents"):
            uniform_median = engine.rank_statistic([int(row[field]) for row in uniform], 0.5)
            balanced_values = [int(row[field]) for row in balanced]
            entry[field] = {
                "uniform_median": uniform_median,
                "balanced_minimum": min(balanced_values),
                "balanced_median": engine.rank_statistic(balanced_values, 0.5),
            }
        yield_noninferior = entry["closed_edges"]["balanced_minimum"] >= entry["closed_edges"]["uniform_median"]
        entry["yield_noninferior"] = yield_noninferior
        pointwise_noninferior += int(yield_noninferior)
        by_budget[str(budget)] = entry

    integrated: dict[str, Any] = {}
    for field in ("closed_edges", "tasks", "physical_runs"):
        uniform_values = trajectory_integrals(rows["uniform_edge"], field, range(256))
        balanced_values = trajectory_integrals(rows["balanced_closure_greedy"], field, range(32))
        integrated[field] = {
            "uniform_median": engine.rank_statistic(uniform_values, 0.5),
            "balanced_minimum": min(balanced_values),
            "balanced_median": engine.rank_statistic(balanced_values, 0.5),
            "uniform_p05": engine.rank_statistic(uniform_values, 0.05),
            "uniform_p95": engine.rank_statistic(uniform_values, 0.95),
        }

    terminal = checkpoints[-1]
    uniform_terminal = [row for row in rows["uniform_edge"] if row["budget"] == terminal]
    balanced_terminal = [row for row in rows["balanced_closure_greedy"] if row["budget"] == terminal]
    terminal_parent_uniform = engine.rank_statistic([int(row["parents"]) for row in uniform_terminal], 0.5)
    terminal_parent_balanced = min(int(row["parents"]) for row in balanced_terminal)
    gates = {
        "integrated_yield_noninferiority": integrated["closed_edges"]["balanced_minimum"] >= integrated["closed_edges"]["uniform_median"],
        "pointwise_yield_noninferiority_at_least_5_of_6": pointwise_noninferior >= 5,
        "integrated_task_breadth_at_least_6_over_5": integrated["tasks"]["balanced_minimum"] * 5 >= integrated["tasks"]["uniform_median"] * 6,
        "integrated_run_breadth_at_least_11_over_10": integrated["physical_runs"]["balanced_minimum"] * 10 >= integrated["physical_runs"]["uniform_median"] * 11,
        "terminal_parent_breadth_at_least_9_over_10": terminal_parent_balanced * 10 >= terminal_parent_uniform * 9,
        "terminal_task_anti_dominance_at_most_1_over_3": all(
            share_at_most(row["maximum_single_task_share"], 1, 3) for row in balanced_terminal
        ),
        "terminal_run_anti_dominance_at_most_1_over_10": all(
            share_at_most(row["maximum_single_run_share"], 1, 10) for row in balanced_terminal
        ),
    }
    return {
        "budgets": checkpoints,
        "by_budget": by_budget,
        "integrated": integrated,
        "pointwise_yield_noninferior_checkpoints": pointwise_noninferior,
        "terminal_parent_uniform_median": terminal_parent_uniform,
        "terminal_parent_balanced_minimum": terminal_parent_balanced,
        "gates": gates,
        "all_pareto_gates_pass": all(gates.values()),
    }


def reconstruct(args: argparse.Namespace) -> dict[str, Any]:
    protocol, protocol_sha = load_protocol(Path(args.protocol).resolve(), args.protocol_sha256)
    prior_result, prior_hashes = verify_prior_artifacts(args, protocol)
    prior_protocol, _ = prior.load_protocol(
        Path(args.prior_protocol).resolve(), protocol["immutable_inputs"]["prior_protocol"]["sha256"]
    )
    qualification_result, qualification_hashes = prior.verify_qualification(args, prior_protocol)
    full_topology, raw_hashes = prior.reconstruct_topology(args, prior_protocol, qualification_result)
    check(topology_fingerprint(full_topology) == prior_result["graph_census"]["orientation_free_identity_fingerprint_sha256"], "full graph fingerprint")

    fold_pairs = {0: [], 1: []}
    for pair in full_topology.pairs:
        fold_pairs[fold_for_run(pair.run)].append(pair)
    topologies = {index: topology_from_pairs(pairs) for index, pairs in fold_pairs.items()}
    profiles = {f"fold{index}": profile(topology) for index, topology in topologies.items()}
    support = {name: support_gates(profiles[name], protocol) for name in profiles}
    overlap = cross_fold_overlap(topologies[0], topologies[1])
    integrity = {
        "full_graph_exactly_partitioned": sum(item["pairs"] for item in profiles.values()) == len(full_topology.pairs),
        "pair_endpoint_parent_run_overlap_between_folds_zero": all(value == 0 for value in overlap.values()),
        "aggregate_only_no_identity_release": True,
    }
    support_pass = all(all(values.values()) for values in support.values())
    methods_by_fold: dict[str, Any] = {}
    gates_by_fold: dict[str, Any] = {}

    if all(integrity.values()) and support_pass:
        for index, topology in topologies.items():
            name = f"fold{index}"
            checkpoints = budgets(topology, protocol)
            maximum = checkpoints[-1]
            method_rows: dict[str, list[dict[str, Any]]] = {}
            uniform_rows: list[dict[str, Any]] = []
            for seed in range(256):
                uniform_rows.extend(engine.trajectory(topology, seed, checkpoints, engine.edge_plan(topology, seed, maximum)))
            method_rows["uniform_edge"] = uniform_rows
            balanced_rows: list[dict[str, Any]] = []
            for seed in range(32):
                balanced_rows.extend(engine.trajectory(topology, seed, checkpoints, engine.greedy_plan(topology, seed, maximum, True)))
            method_rows["balanced_closure_greedy"] = balanced_rows
            methods_by_fold[name] = {
                method: {"rows": rows, "summary_by_budget": engine.method_summary(rows, checkpoints)}
                for method, rows in method_rows.items()
            }
            gates_by_fold[name] = evaluate_fold(method_rows, checkpoints)

    if not all(integrity.values()):
        classification = "POSTREADOUT_RUN_SPLIT_BREADTH_PARETO_INTEGRITY_FAIL"
    elif not support_pass:
        classification = "POSTREADOUT_RUN_SPLIT_BREADTH_PARETO_LIMITED_SUPPORT"
    elif all(value["all_pareto_gates_pass"] for value in gates_by_fold.values()):
        classification = "POSTREADOUT_RUN_SPLIT_BREADTH_PARETO_FALSIFICATION_SURVIVES"
    else:
        classification = "POSTREADOUT_RUN_SPLIT_BREADTH_PARETO_DOES_NOT_SURVIVE"

    return {
        "protocol": RESULT,
        "status": "COMPLETE",
        "protocol_sha256": protocol_sha,
        "input_sha256": {**prior_hashes, **qualification_hashes, **raw_hashes},
        "full_graph_counts": {
            "pairs": len(full_topology.pairs),
            "endpoints": len(full_topology.vertices),
            "parents": len({pair.parent for pair in full_topology.pairs}),
            "physical_runs": len({pair.run for pair in full_topology.pairs}),
            "tasks": len({pair.task for pair in full_topology.pairs}),
        },
        "split_profiles": profiles,
        "cross_fold_overlap": overlap,
        "integrity_gates": integrity,
        "support_gates": support,
        "acquisition_computed": bool(methods_by_fold),
        "methods_by_fold": methods_by_fold,
        "gates_by_fold": gates_by_fold,
        "classification": classification,
        "scope": {
            "post_readout_falsification_only": True,
            "external_confirmation": False,
            "aggregate_only": True,
            "identities_emitted": False,
            "pair_orientation_gap_grade_code_prediction_runtime_used": False,
            "senior_test_rows_used": False,
            "prospective_first960_target300_target522_values_read": False,
            "gpu_api_model_fit_base_update": "0/0/0/0",
        },
    }


def verify(args: argparse.Namespace) -> dict[str, Any]:
    result_path = Path(args.result).resolve()
    result_sha = digest(result_path)
    check(result_sha == args.result_sha256, "result SHA")
    observed = read_object(result_path)
    expected = reconstruct(args)
    check(observed == expected, "producer and independent reconstruction differ")
    return {
        "protocol": "historical-run-split-breadth-pareto-independent-verification-v1",
        "status": "INDEPENDENT_RECONSTRUCTION_EXACT",
        "protocol_sha256": args.protocol_sha256,
        "source_result_sha256": result_sha,
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
    parser.add_argument("--prior-protocol", required=True)
    parser.add_argument("--prior-result", required=True)
    parser.add_argument("--prior-verification", required=True)
    parser.add_argument("--prior-package-manifest", required=True)
    parser.add_argument("--prior-producer-source", required=True)
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
