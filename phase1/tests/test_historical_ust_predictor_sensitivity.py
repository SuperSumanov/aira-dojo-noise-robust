from __future__ import annotations

from itertools import combinations
import hashlib
import json
import os
from pathlib import Path
import subprocess

import pytest

from phase1 import analyze_historical_ust_predictor_sensitivity as producer
from phase1 import verify_historical_ust_predictor_sensitivity as verifier


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "phase1/scripts/run_historical_ust_predictor_sensitivity_formal_20260830.sh"
PROTOCOL = ROOT / "phase1/historical_ust_predictor_sensitivity_v2.json"


def graph_row(index: int, task: str, parent: str, left: str, right: str) -> tuple[tuple, dict]:
    row = {
        "index": index,
        "task": task,
        "parent": parent,
        "semantics": "Improve",
        "better": left,
        "worse": right,
        "better_run": f"run-{left}",
        "worse_run": f"run-{right}",
    }
    return producer.pair_key(row), row


def prediction_row(base: dict, *, correct: bool | None, tie: bool = False,
                   abstain: bool = False) -> dict:
    return {
        **base,
        "correct": correct,
        "margin": 0.0 if correct is None else (1.0 if correct else -1.0),
        "split": "test",
        "tie": tie,
        "abstain": abstain,
        "model": "code_len",
    }


def test_clique_and_tree_special_cases_match_independent_grounded_inverse() -> None:
    nodes = list("abcd")
    clique_edges = [((index,), left, right) for index, (left, right) in enumerate(combinations(nodes, 2))]
    producer_clique = producer.component_weights(nodes, clique_edges)
    verifier_clique = verifier.grounded_weights(nodes, clique_edges)
    assert producer_clique == pytest.approx(verifier_clique, abs=1e-12)
    assert all(weight == pytest.approx(0.5, abs=1e-12) for weight in producer_clique.values())
    assert sum(producer_clique.values()) == pytest.approx(3.0, abs=1e-12)

    tree_edges = [((index,), left, right) for index, (left, right) in enumerate(zip(nodes, nodes[1:]))]
    producer_tree = producer.component_weights(nodes, tree_edges)
    verifier_tree = verifier.grounded_weights(nodes, tree_edges)
    assert producer_tree == pytest.approx(verifier_tree, abs=1e-12)
    assert all(weight == pytest.approx(1.0, abs=1e-12) for weight in producer_tree.values())


def test_parent_graph_components_and_foster_accounting_are_independent() -> None:
    items = [
        graph_row(0, "task-a", "parent-a", "a", "b"),
        graph_row(1, "task-a", "parent-a", "b", "c"),
        graph_row(2, "task-a", "parent-a", "a", "c"),
        graph_row(3, "task-a", "parent-a", "d", "e"),
        graph_row(4, "task-b", "parent-b", "f", "g"),
    ]
    base = dict(items)
    producer_weights, producer_graph = producer.build_weights(base)
    verifier_weights, verifier_graph = verifier.graph_weights(base)
    assert producer_weights == pytest.approx(verifier_weights, abs=1e-12)
    assert producer_graph["tasks"] == verifier_graph["tasks"] == 2
    assert producer_graph["decision_parents"] == verifier_graph["decision_parents"] == 2
    assert producer_graph["connected_components"] == verifier_graph["connected_components"] == 3
    assert producer_graph["incidence_rank"] == verifier_graph["incidence_rank"] == 4
    assert float(producer_graph["weight_sum_decimal_17g"]) == pytest.approx(4.0)


def test_neutral_credit_and_weight_shift_match_independent_aggregation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(producer, "BOOTSTRAP_REPETITIONS", 200)
    monkeypatch.setattr(verifier, "REPETITIONS", 200)
    items = [
        graph_row(0, "task-a", "parent-a", "a", "b"),
        graph_row(1, "task-a", "parent-a", "a", "c"),
        graph_row(2, "task-a", "parent-a", "b", "c"),
        graph_row(3, "task-b", "parent-b", "d", "e"),
    ]
    base = dict(items)
    weights, _graph = producer.build_weights(base)
    rows = {
        key: prediction_row(row, correct=value, tie=(value is None))
        for (key, row), value in zip(items, (True, False, None, True))
    }
    (
        producer_metrics, producer_tasks, producer_task_parents, producer_parents
    ) = producer.model_metrics(rows, weights)
    (
        verifier_metrics, verifier_tasks, verifier_task_parents, verifier_parents
    ) = verifier.aggregate(rows, weights)
    assert producer.credit(rows[items[2][0]]) == 0.5
    assert float(producer_metrics["ust_task_macro_accuracy_decimal_17g"]) == pytest.approx(
        verifier_metrics["ust_task"]
    )
    assert float(producer_metrics["ust_minus_raw_task_macro_decimal_17g"]) == pytest.approx(
        verifier_metrics["task_shift"]
    )
    assert [float(value) for value in producer_metrics["ust_minus_raw_task_macro_clustered_ci95"]] \
        == pytest.approx(verifier_metrics["task_shift_ci"])
    assert producer_tasks == pytest.approx(verifier_tasks)
    assert producer_task_parents == pytest.approx(verifier_task_parents)
    assert producer_parents == pytest.approx(verifier_parents)


def test_nested_task_parent_macro_does_not_weight_tasks_by_parent_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(producer, "BOOTSTRAP_REPETITIONS", 200)
    monkeypatch.setattr(verifier, "REPETITIONS", 200)
    items = [
        graph_row(0, "task-a", "parent-a1", "a", "b"),
        graph_row(1, "task-a", "parent-a2", "c", "d"),
        graph_row(2, "task-b", "parent-b1", "e", "f"),
    ]
    base = dict(items)
    weights, _graph = producer.build_weights(base)
    rows = {
        key: prediction_row(row, correct=value)
        for (key, row), value in zip(items, (True, True, False))
    }
    metrics, _task, task_parent, _parent = producer.model_metrics(rows, weights)
    rebuilt, _task_v, task_parent_v, _parent_v = verifier.aggregate(rows, weights)
    assert float(metrics["raw_parent_macro_accuracy_decimal_17g"]) == pytest.approx(2 / 3)
    assert float(metrics["raw_task_parent_macro_accuracy_decimal_17g"]) == pytest.approx(0.5)
    assert float(metrics["ust_task_parent_macro_accuracy_decimal_17g"]) == pytest.approx(0.5)
    assert task_parent == pytest.approx({"task-a": 1.0, "task-b": 0.0})
    assert task_parent == pytest.approx(task_parent_v)
    assert rebuilt["ust_task_parent"] == pytest.approx(0.5)


def test_bootstrap_is_deterministic_and_uses_repetition_relative_order_statistics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(producer, "BOOTSTRAP_REPETITIONS", 200)
    monkeypatch.setattr(verifier, "REPETITIONS", 200)
    values = {"a": 0.0, "b": 0.25, "c": 0.75, "d": 1.0}
    first = producer.bootstrap_ci(values, 7)
    assert first == producer.bootstrap_ci(values, 7)
    assert first == pytest.approx(verifier.ci(values, 7))


def test_rank_discordance_count_is_reconstructed() -> None:
    left = ["a", "b", "c", "d"]
    right = ["b", "a", "d", "c"]
    assert producer.discordant_pairs(left, right) == 2
    assert verifier.discordance(left, right) == 2


def test_schema_drift_duplicate_edge_and_bad_neutral_rows_fail_closed() -> None:
    _key, base = graph_row(0, "task-a", "parent-a", "a", "b")
    valid = prediction_row(base, correct=True)
    producer.validate_common_row(valid, static=True)
    verifier.validate_input_row(valid, static=True)

    changed = dict(valid, unexpected=1)
    with pytest.raises(ValueError, match="schema"):
        producer.validate_common_row(changed, static=True)
    with pytest.raises(ValueError, match="schema"):
        verifier.validate_input_row(changed, static=True)

    invalid_neutral = dict(valid, tie=True, correct=True)
    with pytest.raises(ValueError, match="correctness"):
        producer.validate_common_row(invalid_neutral, static=True)
    with pytest.raises(ValueError, match="correctness"):
        verifier.validate_input_row(invalid_neutral, static=True)

    duplicate = {
        graph_row(0, "task-a", "parent-a", "a", "b")[0]: base,
        graph_row(1, "task-a", "parent-a", "b", "a")[0]: {
            **base, "index": 1, "better": "b", "worse": "a",
        },
    }
    with pytest.raises(ValueError, match="duplicate unordered"):
        producer.build_weights(duplicate)
    with pytest.raises(ValueError, match="duplicate edge"):
        verifier.graph_weights(duplicate)


def test_identity_emission_guard_detects_task_parent_endpoint_or_run() -> None:
    claimed = {"safe": ["aggregate", 931], "leak": {"value": "parent-secret"}}
    assert "parent-secret" in verifier.all_strings(claimed)
    claimed = {"safe": ["aggregate", 931]}
    assert "parent-secret" not in verifier.all_strings(claimed)


def test_synthetic_931_pair_end_to_end_claim_is_independently_verified(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    static_path = tmp_path / "static.jsonl"
    tfidf_path = tmp_path / "tfidf.jsonl"
    static_rows = []
    tfidf_rows = []
    for index in range(931):
        _item_key, base = graph_row(
            index, f"task-{index % 28}", f"parent-{index}", f"left-{index}", f"right-{index}"
        )
        common = {
            **base,
            "correct": index % 3 != 0,
            "margin": 1.0 if index % 3 != 0 else -1.0,
            "split": "test",
            "tie": False,
        }
        tfidf_rows.append(common)
        for model in producer.STATIC_MODELS:
            static_rows.append({**common, "abstain": False, "model": model})
    static_path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in static_rows),
                           encoding="utf-8")
    tfidf_path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in tfidf_rows),
                          encoding="utf-8")
    static_sha = hashlib.sha256(static_path.read_bytes()).hexdigest()
    tfidf_sha = hashlib.sha256(tfidf_path.read_bytes()).hexdigest()
    monkeypatch.setattr(producer, "STATIC_PAIR_SHA256", static_sha)
    monkeypatch.setattr(producer, "TFIDF_PAIR_SHA256", tfidf_sha)
    monkeypatch.setattr(producer, "BOOTSTRAP_REPETITIONS", 200)
    monkeypatch.setattr(verifier, "STATIC_SHA", static_sha)
    monkeypatch.setattr(verifier, "TFIDF_SHA", tfidf_sha)
    monkeypatch.setattr(verifier, "REPETITIONS", 200)
    claimed = producer.analyze(static_path, tfidf_path)
    receipt = verifier.verify(claimed, static_path, tfidf_path)
    assert claimed["models"][producer.FROZEN_CHAMPION][
        "ust_task_parent_macro_accuracy_decimal_17g"
    ] == claimed["models"][producer.FROZEN_CHAMPION][
        "raw_task_parent_macro_accuracy_decimal_17g"
    ]
    assert receipt["status"] == "INDEPENDENT_GROUNDED_RECONSTRUCTION_EXACT_WITHIN_TOLERANCE"
    assert receipt["pairs"] == 931 and receipt["models"] == 12
    assert receipt["raw_pair_task_parent_endpoint_identities_emitted"] is False


def test_exclusive_output_refuses_overwrite(tmp_path: Path) -> None:
    output = tmp_path / "result.json"
    producer.write_exclusive(output, {"status": "ok"})
    if os.name != "nt":
        assert (output.stat().st_mode & 0o777) == 0o600
    with pytest.raises(FileExistsError):
        producer.write_exclusive(output, {"status": "changed"})


def test_runner_is_hash_bound_repeated_traced_and_cpu_only() -> None:
    source = RUNNER.read_text(encoding="utf-8")
    if os.name != "nt":
        subprocess.run(["bash", "-n", str(RUNNER)], check=True, capture_output=True)
    assert "if [[ $# -ne 7 ]]" in source
    assert len(__import__("re").findall(r"(?m)^(?:0[1-9]|1[0-3])_", source)) == 13
    assert "result_a.json" in source and "result_b.json" in source
    assert "verification_a.json" in source and "verification_b.json" in source
    assert 'cmp "$output/result_a.json" "$output/result_b.json"' in source
    assert 'cmp "$output/verification_a.json" "$output/verification_b.json"' in source
    assert 'cmp "$static_a" "$static_b"' in source
    assert 'timeout 1800s "$python_bin" -m pytest -q phase1/tests' in source
    assert "strace -ff -tt -yy -e trace=file,network" in source
    assert "gpu_paid_api_model_fit_base_update=0/0/0/0" in source
    assert "sbatch" not in source and "nvidia-smi" not in source


def test_protocol_binds_every_runtime_source_and_freezes_disclosure() -> None:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    assert protocol["status"] == (
        "FROZEN_AFTER_V1_INVALIDATED_BEFORE_OUTCOME_AGGREGATION_WITH_NESTED_TASK_PARENT_HEADLINE"
    )
    assert protocol["v1_invalid_attempt"]["result_a_created"] is False
    assert protocol["v1_invalid_attempt"]["result_b_created"] is False
    assert protocol["disclosure"]["historical_prediction_outcomes_already_revealed"] is True
    assert protocol["resources"] == {
        "gpu": 0,
        "paid_api_calls": 0,
        "model_fits": 0,
        "base_updates": 0,
        "expected_single_cpu_minutes_excluding_full_tests": "3--20",
    }
    for binding in protocol["source_bindings"].values():
        path = ROOT / binding["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == binding["sha256"]


def test_producer_and_verifier_do_not_import_each_other() -> None:
    producer_source = (ROOT / "phase1/analyze_historical_ust_predictor_sensitivity.py").read_text(
        encoding="utf-8"
    )
    verifier_source = (ROOT / "phase1/verify_historical_ust_predictor_sensitivity.py").read_text(
        encoding="utf-8"
    )
    assert "verify_historical_ust_predictor_sensitivity" not in producer_source
    assert "analyze_historical_ust_predictor_sensitivity" not in verifier_source
