from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

import pytest

from phase1 import falsify_historical_run_split_breadth_pareto as producer
from phase1 import verify_historical_run_split_breadth_pareto as verifier


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "phase1" / "historical_run_split_breadth_pareto_falsification_v1.json"


def protocol() -> dict:
    return json.loads(PROTOCOL.read_text(encoding="utf-8"))


def metric_row(seed: int, budget: int, closed: int, tasks: int, runs: int, parents: int) -> dict:
    return {
        "seed": seed,
        "budget": budget,
        "selected_endpoints": budget,
        "closed_edges": closed,
        "closed_edges_per_endpoint": producer.engine.fraction(closed, budget),
        "parents": parents,
        "tasks": tasks,
        "physical_runs": runs,
        "maximum_single_task_share": producer.engine.fraction(1, 4),
        "maximum_single_run_share": producer.engine.fraction(1, 20),
        "task_effective_count": producer.engine.fraction(4, 1),
        "run_effective_count": producer.engine.fraction(20, 1),
    }


def synthetic_rows(task_multiplier: int = 6) -> tuple[dict[str, list[dict]], list[int]]:
    checkpoints = [10, 20, 30, 40, 50, 60]
    rows = {"uniform_edge": [], "balanced_closure_greedy": []}
    for seed in range(256):
        for index, budget in enumerate(checkpoints, 1):
            rows["uniform_edge"].append(metric_row(seed, budget, 10 * index, 5 * index, 10 * index, 10 * index))
    for seed in range(32):
        for index, budget in enumerate(checkpoints, 1):
            rows["balanced_closure_greedy"].append(
                metric_row(seed, budget, 10 * index, task_multiplier * index, 11 * index, 9 * index)
            )
    return rows, checkpoints


def test_fold_hash_is_identical_between_implementations() -> None:
    for run in ("r0", "r1", "run-long-123", "unicode-run-测试"):
        assert producer.fold_for_run(run) == verifier.fold_for_run(run)
        assert producer.fold_for_run(run) in (0, 1)


def test_physical_run_split_keeps_endpoints_disjoint() -> None:
    runs = {0: None, 1: None}
    index = 0
    while None in runs.values():
        run = f"run-{index}"
        runs[producer.fold_for_run(run)] = run
        index += 1
    edges = [
        producer.engine.Edge("a", "b", "p0", "t", runs[0]),
        producer.engine.Edge("c", "d", "p1", "t", runs[1]),
    ]
    graphs = {
        fold: producer.graph_from_edges([edge for edge in edges if producer.fold_for_run(edge.run) == fold])
        for fold in (0, 1)
    }
    assert producer.cross_fold_overlap(graphs[0], graphs[1]) == {
        "pairs": 0,
        "endpoints": 0,
        "parents": 0,
        "physical_runs": 0,
    }


def test_pareto_gate_passes_exact_boundary() -> None:
    rows, checkpoints = synthetic_rows()
    first = producer.evaluate_fold(rows, checkpoints)
    second = verifier.evaluate_fold(rows, checkpoints)
    assert first == second
    assert first["all_pareto_gates_pass"] is True
    assert first["pointwise_yield_noninferior_checkpoints"] == 6


def test_task_breadth_failure_cannot_be_rescued_by_yield() -> None:
    rows, checkpoints = synthetic_rows(task_multiplier=5)
    receipt = producer.evaluate_fold(rows, checkpoints)
    assert receipt["gates"]["integrated_yield_noninferiority"] is True
    assert receipt["gates"]["integrated_task_breadth_at_least_6_over_5"] is False
    assert receipt["all_pareto_gates_pass"] is False


def test_support_gate_fails_closed() -> None:
    value = {
        "pairs": 199,
        "endpoints": 400,
        "parents": 190,
        "physical_runs": 80,
        "tasks": 20,
        "maximum_single_task_pair_share": producer.engine.fraction(1, 4),
        "maximum_single_run_pair_share": producer.engine.fraction(1, 20),
    }
    gates = producer.support_gates(value, protocol())
    assert gates["minimum_pairs"] is False
    assert not all(gates.values())


def test_protocol_binds_prior_result_and_two_sources() -> None:
    value = protocol()
    for key in ("prior_protocol", "prior_result", "prior_verification", "prior_package_manifest", "prior_producer_source", "prior_independent_source"):
        binding = value["immutable_inputs"][key]
        observed = hashlib.sha256((ROOT / binding["path"]).read_bytes()).hexdigest()
        assert observed == binding["sha256"]


def test_profile_and_identity_fingerprints_are_bound_to_their_own_schemas() -> None:
    prior_result = {
        "graph_census": {"orientation_free_identity_fingerprint_sha256": "profile-fingerprint"}
    }
    qualification_result = {
        "strict_residual_profile": {
            "orientation_free_identity_fingerprint_sha256": "profile-fingerprint"
        },
        "identity_fingerprints": {"strict_residual": "identity-fingerprint"},
    }
    producer.verify_full_graph_fingerprints("identity-fingerprint", prior_result, qualification_result)
    verifier.verify_full_graph_fingerprints("identity-fingerprint", prior_result, qualification_result)
    with pytest.raises(producer.ParetoFalsificationError, match="full graph identity fingerprint"):
        producer.verify_full_graph_fingerprints("profile-fingerprint", prior_result, qualification_result)
    with pytest.raises(verifier.IndependentParetoError, match="full graph identity fingerprint"):
        verifier.verify_full_graph_fingerprints("profile-fingerprint", prior_result, qualification_result)


def test_verifier_does_not_import_falsification_producer() -> None:
    source = (ROOT / "phase1" / "verify_historical_run_split_breadth_pareto.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
            imported.extend(alias.name for alias in node.names)
    assert not any("falsify_historical_run_split_breadth_pareto" in name for name in imported)
