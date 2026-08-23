from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("scipy")
pytest.importorskip("sklearn")

from phase1 import critic_gap_aware_qualification as module


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "phase1" / "critic_gap_aware_qualification_v1.json"


def contract() -> dict:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def row(task: str, parent: str, better: str, worse: str, gap: float) -> dict:
    return {"task": task, "parent": parent, "better": better, "worse": worse, "gap_raw": gap}


def test_contract_hash_and_resource_boundary_are_frozen() -> None:
    assert hashlib.sha256(CONTRACT.read_bytes()).hexdigest() == module.CONTRACT_SHA256
    value = contract()
    assert value["resources"] == {
        "api_calls": 0,
        "base_llm_updates": 0,
        "gpu_jobs": 0,
        "maximum_unique_cpu_fits_per_implementation": 4,
        "threads_per_fit": 1,
    }
    assert value["claim_boundary"]["gap_ridge_may_rescue_primary"] is False


def test_task_scales_and_weights_are_train_only_and_task_mass_preserving() -> None:
    rows = [
        row("a", "p1", "a1", "a0", 1.0),
        row("a", "p2", "a2", "a0", 2.0),
        row("a", "p3", "a3", "a0", 3.0),
        row("a", "p4", "a4", "a0", 4.0),
        row("b", "q1", "b1", "b0", 10.0),
        row("b", "q2", "b2", "b0", 20.0),
        row("b", "q3", "b3", "b0", 30.0),
        row("b", "q4", "b4", "b0", 40.0),
    ]
    scales = module.task_scales(rows)
    assert scales == pytest.approx({"a": 3.25, "b": 32.5})
    relative = module.relative_gaps(rows, scales)
    weights = module.task_mass_preserving_weights(rows, relative)
    permuted = module.hash_cyclic_permuted_weights(rows, weights)
    for task in ("a", "b"):
        indices = [index for index, value in enumerate(rows) if value["task"] == task]
        assert float(np.mean(weights[indices])) == pytest.approx(1.0, abs=1e-12)
        assert np.array_equal(np.sort(permuted[indices]), np.sort(weights[indices]))
    with pytest.raises(module.QualificationError, match="dev-only task"):
        module.relative_gaps([row("c", "r", "c1", "c0", 1.0)], scales)


def test_parent_then_task_aggregation_is_not_pair_micro() -> None:
    rows = [
        row("a", "p1", "a1", "a0", 1.0),
        row("a", "p1", "a2", "a0", 1.0),
        row("a", "p2", "a3", "a0", 1.0),
        row("b", "q1", "b1", "b0", 1.0),
    ]
    margins = {
        "binary_bt": np.asarray([1.0, 1.0, -1.0, -1.0]),
        "gap_permuted_bt": np.asarray([1.0, 1.0, -1.0, -1.0]),
        "gap_weighted_bt": np.asarray([1.0, 1.0, 1.0, -1.0]),
        "gap_ridge": np.asarray([1.0, -1.0, 0.0, 1.0]),
    }
    metrics, task_rows, task_values = module.arm_metrics(rows, margins, np.ones(4))
    assert metrics["binary_bt"]["pair_micro_accuracy"] == pytest.approx(0.5)
    assert task_values["binary_bt"] == pytest.approx({"a": 0.5, "b": 0.0})
    assert metrics["binary_bt"]["task_macro_parent_macro_accuracy"] == pytest.approx(0.25)
    assert task_values["gap_weighted_bt"] == pytest.approx({"a": 1.0, "b": 0.0})
    assert len(task_rows) == 8


def test_primary_gate_uses_only_weighted_bt_and_paired_tasks() -> None:
    tasks = [f"task-{index:02d}" for index in range(20)]
    task_values = {
        "binary_bt": {task: 0.50 for task in tasks},
        "gap_permuted_bt": {task: 0.505 for task in tasks},
        "gap_weighted_bt": {task: 0.52 for task in tasks},
        "gap_ridge": {task: 0.99 for task in tasks},
    }
    result = module.primary_contrast(task_values, contract(), {task: 10 for task in tasks})
    assert result["support"]["all_pass"] is True
    assert result["all_pass"] is True
    assert result["gap_weighted_minus_binary"]["point_delta"] == pytest.approx(0.02)
    assert result["gap_weighted_minus_gap_permuted"]["point_delta"] == pytest.approx(0.015)

    task_values["gap_weighted_bt"] = {task: 0.50 for task in tasks}
    failed = module.primary_contrast(task_values, contract(), {task: 10 for task in tasks})
    assert failed["all_pass"] is False
    assert failed["gap_weighted_minus_binary"]["point_delta"] == 0.0
    assert task_values["gap_ridge"][tasks[0]] == 0.99


def test_pair_identity_is_orientation_invariant() -> None:
    left = row("task", "parent", "b", "a", 1.0)
    right = row("task", "parent", "a", "b", 1.0)
    assert module.pair_key(left) == module.pair_key(right)
    assert module.pair_id(left) == module.pair_id(right)
