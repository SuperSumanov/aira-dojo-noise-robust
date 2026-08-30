from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

from phase1 import falsify_historical_run_split_breadth_pareto as graph_source
from phase1 import freeze_vertex_cost_contrast_target522_selection as producer
from phase1.freeze_vertex_cost_contrast_target522_selection import (
    SelectionFreezeError,
    checkpoints,
    entries,
    graph_profile,
    parent_groups,
    partition_runs,
    public_has_no_identities,
    subgraph,
    support_gates,
    vccd_order,
)
from phase1 import verify_vertex_cost_contrast_target522_selection as independent


def synthetic_graph(parent_count: int = 16):
    edges = []
    payloads = {}
    for index in range(parent_count):
        left, right = f"endpoint-{index}-a", f"endpoint-{index}-b"
        task = f"task-{index % 8}"
        run = f"run-{index}"
        parent = f"parent-{index}"
        edges.append(graph_source.engine.Edge(left, right, parent, task, run))
        for endpoint in (left, right):
            code = f"def solution_{index}_{endpoint[-1]}():\n    return {index}\n"
            payloads[endpoint] = {
                "code": code,
                "code_sha256": hashlib.sha256(code.encode()).hexdigest(),
            }
    return graph_source.graph_from_edges(edges), payloads


def mini_protocol() -> dict:
    return {
        "selection": {
            "budget_fraction_denominator": 32,
            "trajectory_numerators": [3, 4, 5, 6, 7, 8],
            "fit_checkpoint_numerators": [4, 8],
            "vccd": {
                "dimension": 32,
                "character_ngram_range": [3, 5],
                "maximum_characters": 20000,
                "ridge": 1.0,
                "task_terminal_share_denominator": 5,
                "run_terminal_share_denominator": 10,
            },
        },
        "support_gates_before_selection": {
            "minimum_acquisition_pairs": 10,
            "minimum_acquisition_endpoints": 20,
            "minimum_acquisition_physical_runs": 10,
            "minimum_acquisition_tasks": 4,
            "minimum_evaluation_pairs": 4,
            "minimum_evaluation_endpoints": 8,
            "minimum_evaluation_physical_runs": 4,
            "minimum_evaluation_tasks": 2,
            "maximum_single_task_pair_share_numerator": 1,
            "maximum_single_task_pair_share_denominator": 2,
        },
    }


def test_partition_is_deterministic_disjoint_and_exhaustive() -> None:
    runs = {
        f"run-{task}-{index}": {"task": f"task-{task}"}
        for task in range(4)
        for index in range(5)
    }
    first = partition_runs(runs, "fixed-salt")
    second = partition_runs(dict(reversed(list(runs.items()))), "fixed-salt")
    assert first == second
    acquisition, evaluation = map(set, first)
    assert not acquisition & evaluation
    assert acquisition | evaluation == set(runs)
    assert len(acquisition) == 12
    assert len(evaluation) == 8


def test_partition_keeps_both_sides_for_each_multi_run_task() -> None:
    runs = {
        f"r-{task}-{index}": {"task": task}
        for task, count in (("a", 2), ("b", 3), ("c", 7))
        for index in range(count)
    }
    acquisition, evaluation = map(set, partition_runs(runs, "salt"))
    for task in ("a", "b", "c"):
        members = {run for run, row in runs.items() if row["task"] == task}
        assert members & acquisition
        assert members & evaluation


def test_checkpoint_contract_has_six_exact_distinct_values() -> None:
    graph, _ = synthetic_graph()
    assert checkpoints(graph, mini_protocol()) == [3, 4, 5, 6, 7, 8]


def test_parent_groups_reconstruct_exact_cliques() -> None:
    graph, _ = synthetic_graph(3)
    groups = parent_groups(graph)
    assert len(groups) == 3
    assert all(len(group.endpoints) == 2 for group in groups)


def test_parent_groups_reject_incomplete_clique() -> None:
    edges = [
        graph_source.engine.Edge("a", "b", "p", "t", "r"),
        graph_source.engine.Edge("a", "c", "p", "t", "r"),
    ]
    try:
        parent_groups(graph_source.graph_from_edges(edges))
    except SelectionFreezeError as error:
        assert "not a clique" in str(error)
    else:
        raise AssertionError("incomplete sibling clique must fail closed")


def test_vccd_order_uses_only_bound_code_and_is_deterministic() -> None:
    graph, payloads = synthetic_graph()
    first, first_summary = vccd_order(graph, payloads, 8, mini_protocol())
    second, second_summary = vccd_order(graph, payloads, 8, mini_protocol())
    assert first == second
    assert len(first) == len(set(first)) == 8
    assert first_summary == second_summary
    assert first_summary["terminal_task_endpoint_cap"] == 2
    assert first_summary["terminal_run_endpoint_cap"] == 2


def test_subgraph_partitions_complete_run_edges() -> None:
    graph, _ = synthetic_graph(4)
    left = subgraph(graph, ["run-0", "run-2"])
    right = subgraph(graph, ["run-1", "run-3"])
    assert {edge.run for edge in left.edges} == {"run-0", "run-2"}
    assert {edge.run for edge in right.edges} == {"run-1", "run-3"}
    assert not set(left.nodes) & set(right.nodes)


def test_entries_are_exact_nested_prefixes() -> None:
    order = [f"endpoint-{index}" for index in range(10)]
    rows = entries(order, [3, 6, 10])
    assert [row["budget"] for row in rows] == [3, 6, 10]
    assert [len(row["endpoint_ids"]) for row in rows] == [3, 6, 10]
    assert set(rows[0]["endpoint_ids"]) < set(rows[1]["endpoint_ids"]) < set(rows[2]["endpoint_ids"])


def test_support_gates_and_public_identity_guard() -> None:
    graph, _ = synthetic_graph()
    profile = graph_profile(graph)
    gates = support_gates(profile, profile, mini_protocol())
    assert all(gates.values())
    assert public_has_no_identities({"aggregate": {"pairs": len(graph.edges)}}, graph)
    assert not public_has_no_identities({"leak": graph.nodes[0]}, graph)


def test_independent_partition_and_checkpoints_match_contract() -> None:
    runs = {f"run-{index}": {"task": f"task-{index % 5}"} for index in range(25)}
    assert independent.independent_partition(runs, "salt") == partition_runs(runs, "salt")
    graph, _ = synthetic_graph()
    assert independent.independent_checkpoints(graph, mini_protocol()) == checkpoints(
        graph, mini_protocol()
    )


def test_independent_group_and_vccd_reconstruction_matches() -> None:
    graph, payloads = synthetic_graph()
    direct_groups = parent_groups(graph)
    rebuilt_groups = independent.independent_groups(graph)
    assert direct_groups == rebuilt_groups
    direct, direct_summary = vccd_order(graph, payloads, 8, mini_protocol())
    rebuilt, rebuilt_summary = independent.independent_vccd(
        graph, payloads, 8, mini_protocol()
    )
    assert direct == rebuilt
    assert direct_summary == rebuilt_summary


def test_independent_verifier_does_not_import_selection_exporter() -> None:
    source = Path(independent.__file__).read_text(encoding="utf-8")
    assert "from phase1.freeze_vertex_cost_contrast_target522_selection" not in source
    assert "import phase1.freeze_vertex_cost_contrast_target522_selection" not in source


def test_frozen_protocol_loads_in_both_implementations() -> None:
    repo_root = Path(__file__).parents[2]
    path = repo_root / "phase1" / "vertex_cost_contrast_target522_effect_v1.json"
    expected = hashlib.sha256(path.read_bytes()).hexdigest()
    direct, direct_sha = producer.load_protocol(path, expected)
    rebuilt, rebuilt_sha = independent.load_protocol(path, expected)
    assert direct == rebuilt
    assert direct_sha == rebuilt_sha == expected
    producer.verify_runtime_sources(repo_root, direct)
    independent.verify_runtime_sources(repo_root, rebuilt)
    producer.verify_program_binding(repo_root, direct)
    independent.verify_program_binding(repo_root, rebuilt)
    assert set(direct["selection"]["fit_checkpoint_numerators"]) < set(
        direct["selection"]["trajectory_numerators"]
    )
    assert direct["release_gate"]["effect_stage_requires_first960_accrual_closure"] is True


def test_outcome_blind_selection_and_independent_verification_end_to_end(
    tmp_path: Path, monkeypatch
) -> None:
    repo_root = Path(__file__).parents[2]
    protocol_path = repo_root / "phase1" / "vertex_cost_contrast_target522_effect_v1.json"
    protocol_sha = hashlib.sha256(protocol_path.read_bytes()).hexdigest()
    edges = []
    payloads = {}
    increment_runs = {}
    increment_cards = {}
    for task_index in range(20):
        task = f"future-task-{task_index}"
        for run_index in range(5):
            run = f"future-run-{task_index}-{run_index}"
            increment_runs[run] = {"task": task}
            for parent_index in range(2):
                parent = f"future-parent-{task_index}-{run_index}-{parent_index}"
                left, right = f"{parent}-a", f"{parent}-b"
                edges.append(graph_source.engine.Edge(left, right, parent, task, run))
                for endpoint in (left, right):
                    code = f"def {endpoint.replace('-', '_')}():\n    return {task_index + run_index}\n"
                    payloads[endpoint] = {
                        "code": code,
                        "code_sha256": hashlib.sha256(code.encode()).hexdigest(),
                    }
                    increment_cards[endpoint] = {"task": task, "run": run, "parent": parent}
    graph = graph_source.graph_from_edges(edges)
    selection = {
        "baseline_snapshot_sha256": "b" * 64,
        "candidate_snapshot_sha256": "a" * 64,
    }
    candidate = SimpleNamespace(card_payloads=payloads)
    append_only = {"increment_contains_only_complete_new_physical_runs": True}
    pair_bindings = {"structural_pair_files_equal_exact_observed_sibling_cliques": True}

    monkeypatch.setattr(
        producer.forward,
        "selection_and_increment",
        lambda *args, **kwargs: (
            selection,
            candidate,
            increment_cards,
            increment_runs,
            append_only,
        ),
    )
    monkeypatch.setattr(
        producer.forward,
        "structural_pair_graph",
        lambda *args, **kwargs: (graph, pair_bindings),
    )
    monkeypatch.setattr(
        producer.forward,
        "solve_private",
        lambda *args, **kwargs: (
            {"status": "FEASIBILITY_UNRESOLVED", "solver_status": 1},
            None,
        ),
    )
    common = {
        "protocol": protocol_path,
        "protocol_sha256": protocol_sha,
        "source_commit": "0" * 40,
        "state_root": tmp_path / "state",
        "selection_root": tmp_path / "selection",
        "repo_root": repo_root,
    }
    public, private = producer.build(
        SimpleNamespace(
            **common,
            public_output=tmp_path / "unused-public.json",
            private_output=tmp_path / "unused-private.json",
        )
    )
    assert public["classification"] == "VCCD_TARGET522_SELECTION_READY_YIELD_BASELINE_UNAVAILABLE"
    assert private is not None
    public_path = tmp_path / "public.json"
    private_path = tmp_path / "private.json"
    producer.write_exclusive(public_path, public)
    producer.write_exclusive(private_path, private)
    verification = independent.verify(
        SimpleNamespace(
            **common,
            public_result=public_path,
            private_selection=private_path,
            verification_output=tmp_path / "verification.json",
        )
    )
    assert verification["status"] == "VERIFIED"
    assert verification["run_partition_recomputed"] is True
    assert verification["uniform_order_recomputed"] is True
    assert verification["vccd_order_recomputed"] is True
    assert verification["prospective_values_read"] is False
