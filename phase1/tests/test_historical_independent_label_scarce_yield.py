from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

from phase1 import confirm_historical_independent_label_scarce_yield as producer
from phase1 import verify_historical_independent_label_scarce_yield as verifier


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "phase1" / "historical_independent_label_scarce_yield_confirmation_v1.json"


def load_protocol() -> dict:
    return json.loads(PROTOCOL.read_text(encoding="utf-8"))


def row(seed: int, budget: int, closed: int, parents: int, tasks: int, runs: int) -> dict:
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
        "maximum_single_run_share": producer.engine.fraction(1, 10),
        "task_effective_count": producer.engine.fraction(4, 1),
        "run_effective_count": producer.engine.fraction(10, 1),
    }


def synthetic_rows(multiplier: int) -> dict[str, list[dict]]:
    protocol = load_protocol()
    budgets = producer.budgets(protocol)
    output: dict[str, list[dict]] = {
        "uniform_node": [],
        "uniform_edge": [],
        "closure_greedy": [],
        "balanced_closure_greedy": [],
    }
    for seed in range(256):
        for index, budget in enumerate(budgets, 1):
            value = 10 * index
            output["uniform_node"].append(row(seed, budget, value // 2, 5, 5, 5))
            output["uniform_edge"].append(row(seed, budget, value, 10, 10, 10))
    for seed in range(32):
        for index, budget in enumerate(budgets, 1):
            value = multiplier * index
            output["closure_greedy"].append(row(seed, budget, value + 1, 9, 9, 9))
            output["balanced_closure_greedy"].append(row(seed, budget, value, 8, 8, 8))
    return output


def test_budget_grid_is_six_equal_fraction_steps() -> None:
    protocol = load_protocol()
    assert producer.budgets(protocol) == [32, 64, 97, 129, 161, 194]
    assert verifier.budgets(protocol) == [32, 64, 97, 129, 161, 194]


def test_promotion_gate_passes_only_the_label_scarce_contract() -> None:
    protocol = load_protocol()
    rows = synthetic_rows(13)
    first, first_class = producer.evaluate_confirmation_gates(rows, protocol)
    second, second_class = verifier.gate_receipt(rows, protocol)
    assert first == second
    assert first["all_promotion_gates_pass"] is True
    assert first["pointwise_balanced_median_wins"] == 6
    assert first_class == second_class == protocol["promotion_gates"]["classification_if_all_pass"]


def test_integrated_gate_cannot_be_rescued_by_pointwise_wins() -> None:
    protocol = load_protocol()
    rows = synthetic_rows(11)
    receipt, classification = producer.evaluate_confirmation_gates(rows, protocol)
    assert receipt["pointwise_consistency_gate"] is True
    assert receipt["integrated_yield_gate"] is False
    assert receipt["all_promotion_gates_pass"] is False
    assert classification == protocol["promotion_gates"]["classification_otherwise"]


def test_terminal_anti_dominance_is_exact_integer_arithmetic() -> None:
    protocol = load_protocol()
    rows = synthetic_rows(13)
    terminal = protocol["acquisition"]["maximum_endpoint_budget"]
    target = next(
        item
        for item in rows["balanced_closure_greedy"]
        if item["seed"] == 0 and item["budget"] == terminal
    )
    target["maximum_single_run_share"] = producer.engine.fraction(2, 19)
    receipt, classification = producer.evaluate_confirmation_gates(rows, protocol)
    assert receipt["terminal_gates"]["run_anti_dominance_at_most_1_over_10"] is False
    assert classification == protocol["promotion_gates"]["classification_otherwise"]


def test_protocol_binds_both_independent_engines() -> None:
    protocol = load_protocol()
    for key in (
        "producer_graph_qualification_source",
        "independent_graph_qualification_source",
        "producer_acquisition_engine",
        "independent_acquisition_engine",
    ):
        binding = protocol["immutable_inputs"][key]
        observed = hashlib.sha256((ROOT / binding["path"]).read_bytes()).hexdigest()
        assert observed == binding["sha256"]


def test_verifier_does_not_import_confirmation_producer() -> None:
    source = (ROOT / "phase1" / "verify_historical_independent_label_scarce_yield.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
            imported.extend(alias.name for alias in node.names)
    assert not any("confirm_historical_independent_label_scarce_yield" in name for name in imported)


def test_exclusive_writers_refuse_overwrite(tmp_path: Path) -> None:
    first = tmp_path / "producer.json"
    producer.secure_write(first, {"ok": True})
    try:
        producer.secure_write(first, {"ok": False})
    except FileExistsError:
        pass
    else:
        raise AssertionError("producer overwrite was accepted")

    second = tmp_path / "verifier.json"
    verifier.write_exclusive(second, {"ok": True})
    try:
        verifier.write_exclusive(second, {"ok": False})
    except FileExistsError:
        pass
    else:
        raise AssertionError("verifier overwrite was accepted")
