from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "phase1/scripts/run_foreagent_loeo_graph_denoising_formal_20260830.sh"
ADDENDUM_V2 = ROOT / "phase1/foreagent_loeo_graph_denoising_execution_addendum_v2.json"
ADDENDUM_V3 = ROOT / "phase1/foreagent_loeo_graph_denoising_execution_addendum_v3.json"
NUMERIC_ADDENDUM_V4 = ROOT / "phase1/foreagent_loeo_graph_denoising_numeric_addendum_v4.json"


def test_lfs_skip_smudge_is_scoped_to_fresh_worktree_checkout() -> None:
    text = RUNNER.read_text(encoding="utf-8")
    expected = (
        'GIT_LFS_SKIP_SMUDGE=1 git -C "$repo" worktree add --detach '
        '"$worktree" "$expected_commit"'
    )
    assert text.count(expected) == 1
    assert '\ngit -C "$repo" worktree add --detach' not in text


def test_execution_addendum_preserves_scientific_contract() -> None:
    value = json.loads(ADDENDUM_V2.read_text(encoding="utf-8"))
    assert value["protocol"] == "foreagent-loeo-graph-denoising-execution-addendum-v2"
    assert value["parent_protocol_sha256"] == (
        "bcd25033e2340a0b98c362ae1fffb29fe39c5222ceb531e5112d4675d7be033c"
    )
    assert value["failed_attempt"]["exit_code"] == 128
    assert value["failed_attempt"]["result_files_created"] == 0
    assert value["scientific_changes"] == []
    assert value["resource_changes"] == []


def test_full_suite_is_scoped_to_phase1_tests() -> None:
    text = RUNNER.read_text(encoding="utf-8")
    expected = 'env PYTHONHASHSEED=0 "$python" -m pytest phase1/tests -q'
    assert text.count(expected) == 1
    assert 'env PYTHONHASHSEED=0 "$python" -m pytest -q \\\n' not in text


def test_v3_addendum_records_result_free_collection_failure() -> None:
    value = json.loads(ADDENDUM_V3.read_text(encoding="utf-8"))
    assert value["protocol"] == "foreagent-loeo-graph-denoising-execution-addendum-v3"
    assert value["parent_protocol_sha256"] == (
        "bcd25033e2340a0b98c362ae1fffb29fe39c5222ceb531e5112d4675d7be033c"
    )
    assert value["failed_attempt"]["exit_code"] == 2
    assert value["failed_attempt"]["focused_tests_passed"] == 9
    assert value["failed_attempt"]["producer_started"] is False
    assert value["failed_attempt"]["result_files_created"] == 0
    assert value["scientific_changes"] == []
    assert value["resource_changes"] == []


def test_v4_numeric_addendum_records_exact_rational_diagnostic() -> None:
    value = json.loads(NUMERIC_ADDENDUM_V4.read_text(encoding="utf-8"))
    assert value["protocol"] == "foreagent-loeo-graph-denoising-numeric-addendum-v4"
    assert value["failed_attempt"]["focused_tests_passed"] == 11
    assert value["failed_attempt"]["full_phase1_tests_passed"] == 1784
    assert value["failed_attempt"]["result_files_created"] == 0
    assert value["exact_rational_diagnostic"]["deepseek"]["exact_fraction"] == "33925/55143"
    assert value["exact_rational_diagnostic"]["gpt"]["exact_fraction"] == "32477/55143"
    assert value["raw_reproduction_tolerance_formula"] == "64 * binary64_epsilon"
    assert value["scientific_changes"] == []
    assert value["resource_changes"] == []
