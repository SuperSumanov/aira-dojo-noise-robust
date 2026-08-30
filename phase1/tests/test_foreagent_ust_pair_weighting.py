from __future__ import annotations

import copy
from itertools import combinations
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

import pytest

from phase1 import audit_foreagent_ust_pair_weighting as producer
from phase1 import verify_foreagent_ust_pair_weighting as verifier


SOURCE_SHA = producer.SOURCE_SHA256
ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "phase1/scripts/run_foreagent_ust_pair_weighting_formal_20260830.sh"
PROTOCOL = ROOT / "phase1/foreagent_ust_pair_weighting_addendum_v1.json"


def path(task: str, name: str) -> str:
    return f"root/solutions_subset_50/{task}/{name}.py"


def clique(task: str, names: tuple[str, ...]) -> list[dict]:
    nodes = [path(task, name) for name in names]
    return [{"paths": [left, right]} for left, right in combinations(nodes, 2)]


def triangle_tail_rows() -> list[dict]:
    a, b, c, d = (path("task-a", name) for name in ("a", "b", "c", "d"))
    return [
        {"paths": [a, b]},
        {"paths": [a, c]},
        {"paths": [b, c]},
        {"paths": [c, d]},
    ]


def test_complete_clique_reduces_exactly_to_two_over_k() -> None:
    names = tuple("abcde")
    rows = clique("task-a", names)
    _, edges, _tasks, union = producer.graph_from_rows(rows)
    nodes = sorted(union.parent)
    weights = producer.component_leverages(nodes, edges)
    assert len(weights) == 10
    assert all(value == pytest.approx(2 / 5, abs=1e-12) for value in weights)
    assert sum(weights) == pytest.approx(4.0, abs=1e-12)


def test_tree_reduces_to_unweighted_edge_accuracy() -> None:
    a, b, c, d = (path("task-a", name) for name in ("a", "b", "c", "d"))
    rows = [{"paths": [a, b]}, {"paths": [b, c]}, {"paths": [c, d]}]
    _, edges, _tasks, union = producer.graph_from_rows(rows)
    weights = producer.component_leverages(sorted(union.parent), edges)
    assert weights == pytest.approx([1.0, 1.0, 1.0], abs=1e-12)


def test_triangle_plus_tail_matches_uniform_spanning_tree_inclusion() -> None:
    rows = triangle_tail_rows()
    _, edges, _tasks, union = producer.graph_from_rows(rows)
    nodes = sorted(union.parent)
    weights = producer.component_leverages(nodes, edges)
    counts = {edge: 0 for edge in edges}
    trees = 0
    for subset in combinations(edges, len(nodes) - 1):
        parent = {node: node for node in nodes}

        def find(node: str) -> str:
            while parent[node] != node:
                node = parent[node]
            return node

        valid = True
        for left, right in subset:
            left_root, right_root = find(left), find(right)
            if left_root == right_root:
                valid = False
                break
            parent[right_root] = left_root
        if valid and len({find(node) for node in nodes}) == 1:
            trees += 1
            for edge in subset:
                counts[edge] += 1
    assert trees == 3
    inclusion = [counts[edge] / trees for edge in edges]
    assert weights == pytest.approx(inclusion, abs=1e-12)
    assert sorted(weights) == pytest.approx([2 / 3, 2 / 3, 2 / 3, 1.0], abs=1e-12)


def test_task_rank_weighting_does_not_quadratically_reward_cliques() -> None:
    rows = clique("task-a", tuple("abcd")) + [{"paths": [path("task-b", "x"), path("task-b", "y")]}]
    result = producer.summarize(rows, SOURCE_SHA)
    weighting = result["task_weighting"]
    assert float(weighting["raw_pair_row_max_task_share_decimal_17g"]) == pytest.approx(6 / 7)
    assert float(weighting["incidence_rank_max_task_share_decimal_17g"]) == pytest.approx(3 / 4)
    assert float(weighting["total_variation_decimal_17g"]) == pytest.approx(3 / 28)
    assert result["endpoint_edge_incidence_rank"] == 4
    assert float(result["ust_edge_weight"]["sum_decimal_17g"]) == pytest.approx(4.0)


def test_independent_grounded_inverse_matches_eigendecomposition() -> None:
    rows = triangle_tail_rows() + clique("task-b", tuple("wxyz"))
    result = producer.summarize(rows, SOURCE_SHA)
    expected = verifier.reconstruct(rows)
    verifier.verify_claimed(result, expected)


def test_duplicate_cross_task_and_schema_drift_fail_closed() -> None:
    rows = triangle_tail_rows()
    with pytest.raises(ValueError, match="duplicate"):
        producer.summarize(rows + [copy.deepcopy(rows[0])], SOURCE_SHA)
    cross = copy.deepcopy(rows)
    cross[0] = {"paths": [path("task-a", "a"), path("task-b", "b")]}
    with pytest.raises(ValueError, match="cross-task"):
        producer.summarize(cross, SOURCE_SHA)
    changed = copy.deepcopy(rows)
    changed[0]["score"] = 1.0
    with pytest.raises(ValueError, match="schema"):
        producer.summarize(changed, SOURCE_SHA)


def test_source_sha_and_disconnected_component_accounting() -> None:
    rows = [
        {"paths": [path("task-a", "a"), path("task-a", "b")]},
        {"paths": [path("task-a", "c"), path("task-a", "d")]},
    ]
    result = producer.summarize(rows, SOURCE_SHA)
    assert result["tasks"] == 1
    assert result["connected_components"] == 2
    assert result["endpoint_edge_incidence_rank"] == 2
    with pytest.raises(ValueError, match="source SHA"):
        producer.summarize(rows, "x" * 64)


def test_public_result_emits_no_solution_or_task_identities() -> None:
    result = producer.summarize(triangle_tail_rows(), SOURCE_SHA)
    rendered = producer.canonical_bytes(result).decode()
    for forbidden in ("task-a", "/a.py", "/b.py", "/c.py", "/d.py"):
        assert forbidden not in rendered
    assert result["scope"]["scores_or_predictions_read"] is False
    assert result["task_weighting"]["task_identities_emitted"] is False


def test_runner_is_hash_bound_repeated_traced_and_cpu_only() -> None:
    source = RUNNER.read_text(encoding="utf-8")
    if os.name != "nt":
        subprocess.run(["bash", "-n", str(RUNNER)], check=True, capture_output=True)
    assert "if [[ $# -ne 7 ]]" in source
    assert len(re.findall(r"(?m)^(?:0[1-9]|1[0-3])_", source)) == 13
    assert "result_a.json" in source and "result_b.json" in source
    assert "verification_a.json" in source and "verification_b.json" in source
    assert 'cmp "$output/result_a.json" "$output/result_b.json"' in source
    assert 'cmp "$output/verification_a.json" "$output/verification_b.json"' in source
    assert 'timeout 1800s "$python_bin" -m pytest -q phase1/tests' in source
    assert "strace -ff -tt -yy -e trace=file,network" in source
    assert "gpu_paid_api_model_fit_base_update=0/0/0/0" in source
    assert "sbatch" not in source and "nvidia-smi" not in source


def test_protocol_binds_every_runtime_source() -> None:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    assert protocol["status"] == "FROZEN_BEFORE_EDGE_LEVERAGE_OR_TASK_WEIGHT_READOUT"
    for binding in protocol["source_bindings"].values():
        path = ROOT / binding["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == binding["sha256"]
