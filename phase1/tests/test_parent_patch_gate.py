from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


MODULE_PATH = Path(__file__).parent.parent / "parent_patch_gate.py"
SPEC = importlib.util.spec_from_file_location("parent_patch_gate", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_line_delta_is_directional_and_drops_unchanged_context() -> None:
    delta = MODULE.line_delta("a = 1\nkeep = 2\n", "a = 3\nkeep = 2\nnew = 4\n", "Improve")
    assert delta.splitlines() == ["OP Improve", "DEL a = 1", "ADD a = 3", "ADD new = 4"]
    assert "keep = 2" not in delta


def test_tie_hit() -> None:
    assert MODULE.tie_hit(1.0) == 1.0
    assert MODULE.tie_hit(-1.0) == 0.0
    assert MODULE.tie_hit(0.0) == 0.5


def test_parent_top1_uses_pair_graph_and_tie_aware_prediction() -> None:
    rows = [
        {"parent": "p", "better": "a", "worse": "b", "run": "r", "task": "t"},
        {"parent": "p", "better": "a", "worse": "c", "run": "r", "task": "t"},
        {"parent": "p", "better": "b", "worse": "c", "run": "r", "task": "t"},
    ]
    records = MODULE.parent_top1_records(rows, {"a": 0.2, "b": 0.2, "c": 0.1})
    assert records["p"]["value"] == 0.5
    assert records["p"]["true_ties"] == 1
    assert records["p"]["predicted_ties"] == 2


def test_discovery_gate_fails_closed_on_one_missing_condition() -> None:
    audit = {
        "parent_coverage": 0.95,
        "runs": 280,
        "tasks": 23,
        "dominant_task_share": 0.21,
    }
    comparison = {
        "patch": {"pair_accuracy": {"overall": 0.56}},
        "pair_difference": {
            "overall": 0.03,
            "run_macro_ci95": [0.01, 0.05],
            "task_macro_ci95": [0.01, 0.06],
        },
        "parent_top1_difference": {"overall": 0.04},
        "task_consistency": {"supported_tasks": 12, "nonnegative_share": 0.75},
        "oracle_pair_accuracy": 1.0,
    }
    passing_gate = MODULE.discovery_gate(audit, comparison, 400.0, True)
    assert passing_gate["runs_ge_250"] is True
    assert passing_gate["all"] is True
    audit["runs"] = 249
    low_support_gate = MODULE.discovery_gate(audit, comparison, 400.0, True)
    assert low_support_gate["runs_ge_250"] is False
    assert low_support_gate["all"] is False
    audit["runs"] = 280
    comparison["pair_difference"]["overall"] = 0.019
    gate = MODULE.discovery_gate(audit, comparison, 400.0, True)
    assert gate["pair_gain_ge_002"] is False
    assert gate["all"] is False
