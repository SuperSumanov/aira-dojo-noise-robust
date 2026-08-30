from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import pytest

from phase1 import analyze_foreagent_ust_outcome_sensitivity as producer
from phase1 import verify_foreagent_ust_outcome_sensitivity as verifier


TASKS = ("synthetic-task-a", "synthetic-task-b")
GRAPHS = {
    "synthetic-task-a": (("a", "b"), ("a", "c"), ("b", "c"), ("c", "d")),
    "synthetic-task-b": (("e", "f"), ("f", "g")),
}
UTILITY = {"a": 0.1, "b": 0.2, "c": 0.3, "d": 0.4, "e": 0.5, "f": 0.6, "g": 0.7}


def path(task: str, node: str) -> str:
    return f"solutions_subset_50/{task}/code/solution_{node}.py"


def fixture() -> tuple[dict, list[dict]]:
    files: list[dict] = []
    rows: list[dict] = []
    for task in TASKS:
        for model in ("deepseek", "gpt"):
            for release_run in (1, 2, 3):
                source_index = len(files)
                files.append(
                    {
                        "task": task,
                        "model_family": model,
                        "release_run": release_run,
                        "path": f"{task}/{model}/{release_run}.json",
                    }
                )
                for edge_index, (left_node, right_node) in enumerate(GRAPHS[task]):
                    left, right = path(task, left_node), path(task, right_node)
                    scores = [UTILITY[left_node], UTILITY[right_node]]
                    if (source_index + edge_index) % 2:
                        left, right = right, left
                        scores.reverse()
                    paths = [left, right]
                    true_index = 0 if scores[0] > scores[1] else 1
                    if model == "deepseek":
                        correct = (edge_index + release_run) % 3 != 0
                    else:
                        correct = (edge_index + 2 * release_run) % 4 == 0
                    prediction_index = true_index if correct else 1 - true_index
                    rows.append(
                        {
                            "source_index": source_index,
                            "task": task,
                            "model_family": model,
                            "release_run": release_run,
                            "solution_paths": paths,
                            "scores": scores,
                            "is_lower_better": False,
                            "groundtruth_best_index": true_index,
                            "prediction_best_index": prediction_index,
                            "confidence": {"must_not_be_read": True},
                        }
                    )
    return {"files": files}, rows


def test_clique_and_tree_weights_match_independent_grounded_inverse() -> None:
    clique_nodes = ["a", "b", "c", "d"]
    clique_edges = [
        (clique_nodes[i], clique_nodes[j])
        for i in range(len(clique_nodes))
        for j in range(i + 1, len(clique_nodes))
    ]
    producer_values = producer.component_weights(clique_nodes, clique_edges)
    verifier_values = verifier.grounded_weights(clique_nodes, clique_edges)
    assert producer_values == pytest.approx([0.5] * 6)
    assert verifier_values == pytest.approx([0.5] * 6)
    tree_edges = [("a", "b"), ("b", "c"), ("c", "d")]
    assert producer.component_weights(clique_nodes, tree_edges) == pytest.approx([1.0] * 3)
    assert verifier.grounded_weights(clique_nodes, tree_edges) == pytest.approx([1.0] * 3)
    assert producer.linear_quantile([0.5, 0.5, 1.0, 1.0], 0.5) == pytest.approx(0.75)
    assert verifier.linear_quantile([0.5, 0.5, 1.0, 1.0], 0.5) == pytest.approx(0.75)


def test_synthetic_end_to_end_matches_independent_verifier() -> None:
    manifest, rows = fixture()
    result = producer.analyze_data(
        manifest,
        rows,
        manifest_sha256="synthetic-manifest",
        master_sha256="synthetic-master",
        bootstrap_repetitions=200,
    )
    expected, task_identities, endpoint_identities = verifier.reconstruct(manifest, rows, 200)
    differences: list[float] = []
    for key in (
        "population",
        "source_grid_reproduction",
        "common_support_graph",
        "common_support_metrics",
        "paired_deepseek_minus_gpt",
    ):
        verifier.compare(result[key], expected[key], key, differences)
    assert max(differences, default=0.0) < 1e-12
    assert result["common_support_graph"]["pair_rows"] == 6
    assert result["common_support_graph"]["vertices"] == 7
    assert result["common_support_graph"]["connected_components"] == 2
    assert result["common_support_graph"]["endpoint_edge_incidence_rank"] == 5
    assert result["common_support_graph"]["cycle_rows"] == 1
    assert result["common_support_graph"]["complete_components"] == 0
    assert result["common_support_graph"]["incomplete_components"] == 2
    serialized = json.dumps(result, sort_keys=True)
    assert not any(identity in serialized for identity in task_identities)
    assert not any(identity in serialized for identity in endpoint_identities)


def test_confidence_is_not_read_and_invalid_prediction_receives_zero() -> None:
    manifest, rows = fixture()
    rows[0]["confidence"] = object()
    rows[0]["prediction_best_index"] = None
    sources, by_source, _ = producer.load_records(manifest, rows)
    first = by_source[0][tuple(sorted(rows[0]["solution_paths"]))]
    assert first["correct"] == 0.0
    support, _ = producer.build_model_support(sources, by_source)
    assert support["deepseek"][TASKS[0]]


def test_gpt_three_release_intersection_excludes_incomplete_pair() -> None:
    manifest, rows = fixture()
    target_source = next(
        index
        for index, source in enumerate(manifest["files"])
        if source["task"] == TASKS[0]
        and source["model_family"] == "gpt"
        and source["release_run"] == 1
    )
    rows = [
        row
        for row in rows
        if not (
            row["source_index"] == target_source
            and set(row["solution_paths"]) == {path(TASKS[0], "a"), path(TASKS[0], "b")}
        )
    ]
    sources, by_source, _ = producer.load_records(manifest, rows)
    model_support, grid = producer.build_model_support(sources, by_source)
    common = producer.common_finite_support(model_support)
    assert grid["excluded_incomplete_triplicate_pairs"]["gpt"] == 1
    assert grid["grid_counts"]["gpt"] == 5
    assert sum(len(value) for value in common.values()) == 5


def test_nonfinite_truth_is_removed_before_common_graph() -> None:
    manifest, rows = fixture()
    target = {path(TASKS[0], "a"), path(TASKS[0], "b")}
    for row in rows:
        if set(row["solution_paths"]) == target:
            row["scores"] = [
                math.nan if value == path(TASKS[0], "a") else 0.0
                for value in row["solution_paths"]
            ]
            row["groundtruth_best_index"] = 0
    sources, by_source, _ = producer.load_records(manifest, rows)
    model_support, _ = producer.build_model_support(sources, by_source)
    common = producer.common_finite_support(model_support)
    assert sum(len(value) for value in common.values()) == 5


def test_duplicate_score_drift_and_groundtruth_mismatch_fail_closed() -> None:
    manifest, rows = fixture()
    duplicate = dict(rows[0])
    with pytest.raises(ValueError, match="duplicate pair"):
        producer.load_records(manifest, rows + [duplicate])

    manifest, rows = fixture()
    same_pair = set(rows[0]["solution_paths"])
    target_source = next(
        index
        for index, source in enumerate(manifest["files"])
        if source["task"] == TASKS[0]
        and source["model_family"] == "deepseek"
        and source["release_run"] == 2
    )
    target_row = next(
        row
        for row in rows
        if row["source_index"] == target_source and set(row["solution_paths"]) == same_pair
    )
    target_row["scores"] = [value + 0.01 for value in target_row["scores"]]
    sources, by_source, _ = producer.load_records(manifest, rows)
    with pytest.raises(ValueError, match="score drift"):
        producer.build_model_support(sources, by_source)

    manifest, rows = fixture()
    rows[0]["groundtruth_best_index"] = 1 - rows[0]["groundtruth_best_index"]
    with pytest.raises(ValueError, match="groundtruth/score disagreement"):
        producer.load_records(manifest, rows)


def test_bootstrap_is_deterministic_and_loto_has_all_tasks() -> None:
    manifest, rows = fixture()
    first = producer.analyze_data(
        manifest,
        rows,
        manifest_sha256="synthetic-manifest",
        master_sha256="synthetic-master",
        bootstrap_repetitions=120,
    )
    second = producer.analyze_data(
        manifest,
        rows,
        manifest_sha256="synthetic-manifest",
        master_sha256="synthetic-master",
        bootstrap_repetitions=120,
    )
    assert producer.canonical_bytes(first) == producer.canonical_bytes(second)
    loto = first["common_support_metrics"]["deepseek"]["leave_one_task_out"]
    assert all(value["total"] == 2 for value in loto.values())


def test_exclusive_writers_refuse_overwrite(tmp_path: Path) -> None:
    producer_path = tmp_path / "producer.json"
    verifier_path = tmp_path / "verifier.json"
    producer.write_exclusive(producer_path, {"ok": True})
    verifier.write(verifier_path, {"ok": True})
    with pytest.raises(FileExistsError):
        producer.write_exclusive(producer_path, {"ok": True})
    with pytest.raises(FileExistsError):
        verifier.write(verifier_path, {"ok": True})


def test_producer_and_verifier_do_not_import_each_other() -> None:
    producer_source = Path(producer.__file__).read_text(encoding="utf-8")
    verifier_source = Path(verifier.__file__).read_text(encoding="utf-8")
    assert "verify_foreagent_ust_outcome_sensitivity" not in producer_source
    assert "analyze_foreagent_ust_outcome_sensitivity" not in verifier_source


def test_runner_is_exact_commit_repeated_traced_and_cpu_only() -> None:
    runner = Path("phase1/scripts/run_foreagent_ust_outcome_sensitivity_formal_20260830.sh")
    source = runner.read_text(encoding="utf-8")
    assert source.index("source /uac/y24/yzyang4/env_setup.sh") < source.index("set -u")
    assert source.count("; PASS\n") == 13
    for required in (
        "GIT_LFS_SKIP_SMUDGE=1",
        "worktree add --detach",
        "phase1/tests -q",
        "PYTHONHASHSEED=1",
        "PYTHONHASHSEED=2",
        "PYTHONHASHSEED=3",
        "PYTHONHASHSEED=4",
        "strace -ff",
        "cmp \"$output/result_a.json\" \"$output/result_b.json\"",
        "cmp \"$output/verification_a.json\" \"$output/verification_b.json\"",
        "chmod -R a-w",
    ):
        assert required in source
    for forbidden in ("sbatch", "srun ", "CUDA_VISIBLE_DEVICES", "OPENAI_API_KEY"):
        assert forbidden not in source


def test_protocol_binds_runtime_sources_and_discloses_postdisclosure_scope() -> None:
    protocol_path = Path("phase1/foreagent_ust_outcome_sensitivity_v1.json")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    assert protocol["status"] == (
        "FROZEN_AFTER_RAW_OUTCOMES_DISCLOSED_BEFORE_GRAPH_WEIGHTED_OUTCOME_COMPUTATION"
    )
    assert protocol["disclosure"]["historical_raw_outcomes_already_revealed"] is True
    assert protocol["disclosure"]["new_ust_outcomes_computed_before_freeze"] is False
    assert protocol["support"]["common_finite_directional_pairs"] == 18381
    assert protocol["inference"]["bootstrap_repetitions"] == 20000
    assert protocol["resources"] == {
        "gpu": 0,
        "paid_api_calls": 0,
        "model_fits": 0,
        "base_updates": 0,
        "expected_single_cpu_minutes_excluding_full_tests": "2--20",
    }
    for item in protocol["source_bindings"].values():
        path_value = Path(item["path"])
        digest = hashlib.sha256(path_value.read_bytes()).hexdigest()
        assert digest == item["sha256"]
