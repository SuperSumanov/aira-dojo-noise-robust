from __future__ import annotations

import copy

import pytest

from phase1 import traceml_human_fork_s1_support as producer
from phase1 import verify_traceml_human_fork_s1_support as verifier


def synthetic_world(
    *, task_count: int = 20, parents_per_task: int = 5, children_per_parent: int = 4
):
    nodes = []
    kernels = []
    trees = []
    outcomes = {}
    public = {}
    edges = {}
    manifest = {
        f"task-{task:02d}": {"score_direction": "higher"} for task in range(task_count)
    }
    manifest["unused-release-entry"] = {"score_direction": "lower"}
    next_kernel = 1
    for task_number in range(task_count):
        task = f"task-{task_number:02d}"
        for parent_number in range(parents_per_task):
            tree = f"tree-{task_number:02d}-{parent_number:02d}"
            parent = f"parent-{task_number:02d}-{parent_number:02d}"
            parent_kernel = next_kernel
            next_kernel += 1
            trees.append({"tree_id": tree, "comp": task})
            kernels.append(
                {
                    "kernel_id": parent_kernel,
                    "comp": task,
                    "score_is_max": True,
                    "raw_dir": f"raw/{parent_kernel}",
                }
            )
            outcomes[parent_kernel] = 0.0
            nodes.append(
                {
                    "node_id": parent,
                    "tree_id": tree,
                    "comp": task,
                    "kernel_id": parent_kernel,
                    "version_id": 1,
                    "version_in_kernel": 1,
                    "depth": 0,
                    "parent_id": None,
                    "edge_kind": None,
                    "score_is_max": True,
                    "raw_code_path": f"raw/{parent_kernel}/1.ipynb",
                }
            )
            public[parent] = 0.0
            for child_number in range(children_per_parent):
                child = f"child-{task_number:02d}-{parent_number:02d}-{child_number:02d}"
                child_kernel = next_kernel
                next_kernel += 1
                kernels.append(
                    {
                        "kernel_id": child_kernel,
                        "comp": task,
                        "score_is_max": True,
                        "raw_dir": f"raw/{child_kernel}",
                    }
                )
                outcomes[child_kernel] = float(child_number + 1)
                public[child] = float(child_number + 1) / 10
                nodes.append(
                    {
                        "node_id": child,
                        "tree_id": tree,
                        "comp": task,
                        "kernel_id": child_kernel,
                        "version_id": child_number + 2,
                        "version_in_kernel": 1,
                        "depth": 1,
                        "parent_id": parent,
                        "edge_kind": "fork",
                        "score_is_max": True,
                        "raw_code_path": f"raw/{child_kernel}/1.ipynb",
                    }
                )
                edges[(parent, child, "fork")] = 1
    return {
        "nodes": nodes,
        "kernels": kernels,
        "trees": trees,
        "manifest": manifest,
        "edges": edges,
        "outcomes": outcomes,
        "public": public,
        "train_tasks": {"source-only-task"},
    }


def run_producer(world):
    return producer.summarize(
        world["nodes"],
        world["kernels"],
        world["trees"],
        world["manifest"],
        world["edges"],
        world["outcomes"],
        world["public"],
        world["train_tasks"],
    )


def outcome_rows(world):
    return [
        {"kernel_id": kernel_id, "best_private_score": value}
        for kernel_id, value in world["outcomes"].items()
    ]


def public_rows(world):
    return [
        {"node_id": node_id, "score_public": value}
        for node_id, value in world["public"].items()
    ]


def run_verifier(monkeypatch, world):
    monkeypatch.setattr(
        verifier,
        "edge_multiplicity",
        lambda _path, wanted: {edge: world["edges"].get(edge, 0) for edge in wanted},
    )
    return verifier.reconstruct(
        world["nodes"],
        world["kernels"],
        world["trees"],
        world["manifest"],
        None,
        outcome_rows(world),
        public_rows(world),
        world["train_tasks"],
    )


def test_positive_fixture_passes_all_fixed_gates(monkeypatch):
    world = synthetic_world()
    produced = run_producer(world)
    independently_rebuilt = run_verifier(monkeypatch, world)
    assert produced == independently_rebuilt
    assert produced["status"] == "TRACEML_HUMAN_FORK_S1_PASS_DOWNLOAD_ALLOWED"
    assert produced["support"]["task_unseen_competitions"] == 20
    assert produced["support"]["parent_groups"] == 100
    assert produced["support"]["totals"]["eventual_finite_nontie_pairs"] == 600
    assert produced["support"]["dominant_pair_task_share"] == pytest.approx(0.05)
    assert produced["identity"]["unused_manifest_entries"] == ["unused-release-entry"]

    provisional = verifier.reconstruct(
        world["nodes"],
        world["kernels"],
        world["trees"],
        world["manifest"],
        None,
        None,
        None,
        world["train_tasks"],
    )
    assert provisional["status"] == "IDENTITY_PASS_SCORE_ROWS_NOT_READ"
    assert provisional["support"] == {}


@pytest.mark.parametrize(
    ("mutation", "failure_name"),
    [
        (
            lambda world: world["nodes"].append(copy.deepcopy(world["nodes"][0])),
            "duplicate_node_id",
        ),
        (
            lambda world: world["nodes"].__setitem__(1, {**world["nodes"][1], "depth": 2}),
            "fork_depth_delta_mismatch",
        ),
        (
            lambda world: world["nodes"].__setitem__(1, {**world["nodes"][1], "version_in_kernel": 2}),
            "fork_not_first_kernel_version",
        ),
        (
            lambda world: world["kernels"].__setitem__(0, {**world["kernels"][0], "score_is_max": False}),
            "kernel_direction_mismatch",
        ),
    ],
)
def test_identity_faults_fail_closed(mutation, failure_name):
    world = synthetic_world()
    mutation(world)
    result = run_producer(world)
    assert result["status"] == "IDENTITY_OR_JOIN_AMBIGUOUS"
    assert result["identity"]["counts"][failure_name] > 0
    assert result["support"] == {}


def test_missing_edge_and_duplicate_child_kernel_fail_closed():
    world = synthetic_world()
    first_edge = next(iter(world["edges"]))
    world["edges"][first_edge] = 0
    result = run_producer(world)
    assert result["status"] == "IDENTITY_OR_JOIN_AMBIGUOUS"
    assert result["identity"]["counts"]["fork_edge_table_multiplicity_mismatch"] == 1

    world = synthetic_world()
    first_parent_children = [row for row in world["nodes"] if row.get("parent_id") == "parent-00-00"]
    first_parent_children[1]["kernel_id"] = first_parent_children[0]["kernel_id"]
    result = run_producer(world)
    assert result["status"] == "IDENTITY_OR_JOIN_AMBIGUOUS"
    assert result["identity"]["counts"]["fork_child_kernel_duplicate_within_parent"] == 1


def test_task_unseen_filter_and_dominance_gate_are_not_repaired_post_hoc():
    world = synthetic_world()
    world["train_tasks"].update(f"task-{index:02d}" for index in range(19))
    result = run_producer(world)
    assert result["status"] == "TRACEML_HUMAN_FORK_S1_SUPPORT_GATE_FAILED"
    assert result["support"]["task_unseen_competitions"] == 1
    assert result["support"]["totals"]["eventual_finite_nontie_pairs"] == 30
    assert result["support"]["dominant_pair_task_share"] == 1.0


def test_ties_nonfinite_and_missing_raw_paths_are_counted_before_gate():
    world = synthetic_world()
    children = [row for row in world["nodes"] if row.get("parent_id") == "parent-00-00"]
    world["outcomes"][children[1]["kernel_id"]] = world["outcomes"][children[0]["kernel_id"]]
    world["outcomes"][children[2]["kernel_id"]] = None
    children[3]["raw_code_path"] = None
    result = run_producer(world)
    assert result["support"]["totals"]["eventual_tie_pairs"] > 0
    assert result["support"]["totals"]["eventual_nonfinite_pairs"] > 0
    assert not result["gates"]["declared_raw_code_paths_complete"]
    assert result["status"] == "TRACEML_HUMAN_FORK_S1_SUPPORT_GATE_FAILED"


def test_credential_shaped_identity_is_rejected_without_echoing_value():
    world = synthetic_world()
    credential_shape = "sk-" + "abcdefghijklmnopqrstuvwxyz"
    world["nodes"][0]["raw_code_path"] = credential_shape
    with pytest.raises(producer.AuditError, match="credential-shaped identity value") as error:
        run_producer(world)
    assert "abcdefghijklmnopqrstuvwxyz" not in str(error.value)
