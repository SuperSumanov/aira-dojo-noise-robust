from __future__ import annotations

from phase1 import audit_yield_guarded_breadth_exact_budget_development_v1 as producer
from phase1 import falsify_historical_run_split_breadth_pareto as source
from phase1 import verify_yield_guarded_breadth_exact_budget_development_v1 as verifier


def graph_with_disjoint_contexts():
    engine = source.engine
    return source.graph_from_edges(
        [
            engine.Edge("a", "b", "p0", "t0", "r0"),
            engine.Edge("c", "d", "p1", "t1", "r1"),
            engine.Edge("e", "f", "p2", "t2", "r2"),
            engine.Edge("g", "h", "p3", "t3", "r3"),
        ]
    )


def test_exact_uniform_edge_uses_every_checkpoint_endpoint() -> None:
    graph = graph_with_disjoint_contexts()
    checkpoints = [1, 2, 3, 5]
    rows, _old_underfilled = producer.baseline_rows(graph, checkpoints)
    assert len(rows) == 256 * len(checkpoints)
    assert all(row["selected_endpoints"] == row["budget"] for row in rows)


def test_producer_and_independent_baseline_implementations_agree() -> None:
    graph = graph_with_disjoint_contexts()
    checkpoints = [1, 2, 3, 5]
    rows, old_underfilled_a = producer.baseline_rows(graph, checkpoints)
    by_budget_a, integrated_a = producer.summarize_baseline(rows, checkpoints)
    by_budget_b, integrated_b, old_underfilled_b = verifier.rebuild_baseline(
        graph, checkpoints
    )
    assert {str(key): value for key, value in by_budget_a.items()} == by_budget_b
    assert integrated_a == integrated_b
    assert old_underfilled_a == old_underfilled_b
    assert old_underfilled_a > 0


def test_exact_order_is_nested_and_seed_reproducible() -> None:
    graph = graph_with_disjoint_contexts()
    first = verifier.exact_order(graph, seed=19, maximum=7)
    second = verifier.exact_order(graph, seed=19, maximum=7)
    assert first == second
    assert len(first) == len(set(first)) == 7
    assert set(first[:3]) < set(first[:7])
