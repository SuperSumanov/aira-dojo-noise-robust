from __future__ import annotations

import json

from phase1 import tree_node_label_yield as label_yield
from phase1 import verify_tree_node_label_yield as verifier


def graph() -> label_yield.Graph:
    edges = [
        label_yield.Edge("a", "b", "p1", "t1", "r1"),
        label_yield.Edge("a", "c", "p1", "t1", "r1"),
        label_yield.Edge("b", "c", "p1", "t1", "r1"),
        label_yield.Edge("d", "e", "p2", "t2", "r2"),
    ]
    incident = {node: [] for node in "abcde"}
    context = {}
    for index, edge in enumerate(edges):
        for node in edge.endpoints:
            incident[node].append(index)
            context[node] = (edge.task, edge.run)
    return label_yield.Graph(
        edges,
        tuple("abcde"),
        {key: tuple(value) for key, value in incident.items()},
        context,
    )


def verifier_topology() -> verifier.Topology:
    source = graph()
    return verifier.Topology(
        [
            verifier.Pair(edge.u, edge.v, edge.parent, edge.task, edge.run)
            for edge in source.edges
        ],
        source.nodes,
        source.incident,
        source.context,
    )


def test_one_full_execution_can_close_multiple_sibling_edges() -> None:
    state = label_yield.State(graph())
    state.add(("a", "b"))
    assert len(state.closed) == 1
    assert state.gain(("c",)) == 2
    state.add(("c",))
    assert len(state.closed) == 3
    assert state.closed_task == {"t1": 3}


def test_snapshots_never_charge_an_action_past_budget() -> None:
    rows = label_yield.snapshots_from_actions(
        graph(), 0, [1, 2, 3], iter([("a", "b"), ("c",)])
    )
    assert [row["selected_endpoints"] for row in rows] == [0, 2, 3]
    assert [row["closed_edges"] for row in rows] == [0, 1, 3]


def test_balanced_score_prefers_underrepresented_context() -> None:
    represented = (2, 1, 5, 5, "0", ("a",))
    underrepresented = (2, 1, 0, 0, "f", ("d",))
    assert label_yield.better_action(underrepresented, represented, balanced=True)
    assert label_yield.better_action(represented, underrepresented, balanced=False)


def test_graph_loader_canonicalizes_orientation_and_ignores_forbidden_values(tmp_path) -> None:
    rows = [
        {
            "better": "z",
            "worse": "a",
            "parent": "p",
            "task": "t",
            "run_id": "r",
            "intask_split": "train",
            "budget": 0,
            "gap_raw": 999,
            "clears_tau": True,
        }
    ]
    path = tmp_path / "pairs.jsonl"
    path.write_bytes(
        ("\r\n".join(json.dumps(row) for row in rows) + "\r\n").encode("utf-8")
    )
    digest, size = label_yield.normalized_sha256(path)
    protocol = {
        "immutable_inputs": {
            "pair_graph": {"sha256": digest, "git_blob_bytes": size, "rows": 1}
        },
        "known_before_freeze": {
            "pairs": 1,
            "endpoints": 2,
            "parents": 1,
            "tasks": 1,
            "physical_runs": 1,
        },
    }
    loaded, _ = label_yield.load_graph(path, protocol)
    assert loaded.edges[0].endpoints == ("a", "z")


def test_fraction_is_reduced_and_exactly_serializable() -> None:
    value = label_yield.fraction(6, 8)
    assert value == {"numerator": 3, "denominator": 4, "decimal_17g": "0.75"}
    label_yield.canonical(value)


def test_independent_planners_match_on_synthetic_topology() -> None:
    first, second = graph(), verifier_topology()
    for seed in range(3):
        assert list(label_yield.uniform_node_actions(first, seed)) == list(
            verifier.node_plan(second, seed)
        )
        assert list(label_yield.uniform_edge_actions(first, seed, 5)) == list(
            verifier.edge_plan(second, seed, 5)
        )
        for balanced in (False, True):
            assert list(label_yield.greedy_actions(first, seed, 5, balanced)) == list(
                verifier.greedy_plan(second, seed, 5, balanced)
            )


def test_independent_trajectory_metrics_match() -> None:
    first, second = graph(), verifier_topology()
    actions = [("a", "b"), ("c",), ("d", "e")]
    assert label_yield.snapshots_from_actions(first, 7, [1, 2, 3, 5], iter(actions)) == verifier.trajectory(
        second, 7, [1, 2, 3, 5], iter(actions)
    )
