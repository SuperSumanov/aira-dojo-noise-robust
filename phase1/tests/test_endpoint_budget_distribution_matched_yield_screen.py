import ast
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from phase1 import endpoint_budget_label_efficiency_smoke as smoke
from phase1 import screen_endpoint_budget_distribution_matched_yield as producer
from phase1 import verify_endpoint_budget_distribution_matched_yield_screen as verifier


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "phase1" / "endpoint_budget_distribution_matched_yield_screen_v1.json"


def test_protocol_freezes_post_audit_scope_and_exact_pair_matching() -> None:
    value = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    assert value["status"] == "FROZEN_AFTER_TASK_HETEROGENEITY_AUDIT_BEFORE_NEW_SELECTION_OR_PREDICTION"
    assert value["selection"]["checkpoints"] == [72, 96, 120, 144, 168, 192]
    assert value["selection"]["exact_induced_pair_count"] == [36, 49, 61, 73, 85, 99]
    assert value["selection"]["task_anti_dominance_every_checkpoint"].startswith("5 *")
    assert value["selection"]["run_anti_dominance_every_checkpoint"].startswith("10 *")
    assert value["fit"]["model_fits"] == 2
    assert value["scope"]["scientific_confirmation"] is False
    assert value["scope"]["prospective_first960_target300_target522_values_forbidden"] is True
    assert all(value["known_before_freeze"][key] is False for key in (
        "new_selection_seen", "new_distribution_objective_seen", "new_prediction_or_task_metric_seen"
    ))


def test_solver_matches_small_exhaustive_objective_and_is_deterministic() -> None:
    pytest.importorskip("scipy.optimize")
    edges = [
        smoke.graph_source.engine.Edge(f"u{i}", f"v{i}", f"p{i}", f"t{i}", f"r{i}")
        for i in range(20)
    ]
    graph = smoke.graph_source.graph_from_edges(edges)
    protocol = {
        "selection": {
            "checkpoints": [20, 40],
            "exact_induced_pair_count": [10, 20],
            "integrated_closed_run_floor": 30,
            "terminal_parent_floor": 20,
        }
    }
    first, first_private = producer.solve_distribution_matched(graph, protocol, 30)
    second, second_private = producer.solve_distribution_matched(graph, protocol, 30)
    assert first["status"] == second["status"] == "OPTIMAL_WITNESS"
    assert first["primary_integer_objective"] == 200
    assert first["primary_integer_objective"] == second["primary_integer_objective"]
    assert first["private_selection_fingerprint_sha256"] == second["private_selection_fingerprint_sha256"]
    assert first_private == second_private
    assert [row["induced_pairs"] for row in first["metrics"]] == [10, 20]
    assert [row["selected_endpoints"] for row in first["metrics"]] == [20, 40]
    assert first_private[0] <= first_private[1]


def test_time_limited_primary_incumbent_is_not_called_optimal(monkeypatch: pytest.MonkeyPatch) -> None:
    edges = [smoke.graph_source.engine.Edge("u", "v", "p", "t", "r")]
    graph = smoke.graph_source.graph_from_edges(edges)
    protocol = {
        "selection": {
            "checkpoints": [2],
            "exact_induced_pair_count": [1],
            "integrated_closed_run_floor": 1,
            "terminal_parent_floor": 1,
        }
    }
    monkeypatch.setattr(
        producer,
        "milp_once",
        lambda *_args, **_kwargs: SimpleNamespace(
            x=[1.0] * 5,
            fun=0.0,
            status=1,
            message="time limit reached with incumbent",
            mip_gap=0.25,
        ),
    )
    result, witness = producer.solve_distribution_matched(graph, protocol, 1)
    assert result["status"] == "PRIMARY_OPTIMUM_NOT_RESOLVED"
    assert result["solver_status"] == 1
    assert result["solver_mip_gap"] == 0.25
    assert witness is None


def test_independent_verifier_does_not_import_or_execute_producer() -> None:
    path = ROOT / "phase1" / "verify_endpoint_budget_distribution_matched_yield_screen.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert "phase1.screen_endpoint_budget_distribution_matched_yield" not in imported
    assert "subprocess" not in imported
    assert "screen_endpoint_budget_distribution_matched_yield" not in source


def test_selection_metric_reconstruction_agrees_between_modules() -> None:
    edges = [
        smoke.graph_source.engine.Edge(f"u{i}", f"v{i}", f"p{i}", f"t{i % 10}", f"r{i}")
        for i in range(20)
    ]
    graph = smoke.graph_source.graph_from_edges(edges)
    selections = {
        20: {endpoint for edge in edges[:10] for endpoint in (edge.u, edge.v)},
        40: {endpoint for edge in edges for endpoint in (edge.u, edge.v)},
    }
    protocol = {
        "selection": {
            "checkpoints": [20, 40],
            "exact_induced_pair_count": [10, 20],
            "integrated_closed_run_floor": 30,
            "terminal_parent_floor": 20,
        }
    }
    producer_rows = [
        dict(row, endpoint_budget=budget)
        for row, budget in zip(producer.trajectory_metrics(graph, [selections[20], selections[40]], [10, 20]), [20, 40])
    ]
    assert producer_rows == verifier.direct_metrics(graph, selections, protocol)


def test_fixed_gates_forbid_task_dropping_and_posthoc_rescue() -> None:
    value = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    gates = value["frozen_screen_gates"]
    assert len(gates) == 7
    assert gates["terminal_new_minus_uniform_drop_dominant_accuracy_nonnegative"] is True
    assert "dropping/reweighting tasks" in value["interpretation"]["no_rescue"]
