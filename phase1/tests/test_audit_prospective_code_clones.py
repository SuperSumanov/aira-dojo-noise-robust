from __future__ import annotations

from phase1.audit_prospective_code_clones import fingerprints, summarize_fingerprint


def test_normalizations_separate_literal_and_identifier_changes() -> None:
    first = fingerprints("x = 1\nprint(x)\n")
    literal_change = fingerprints("x = 2\nprint(x)\n")
    identifier_change = fingerprints("y = 1\nprint(y)\n")

    assert first["raw_exact"] != literal_change["raw_exact"]
    assert first["token_literal_norm"] == literal_change["token_literal_norm"]
    assert first["ast_literal_norm"] == literal_change["ast_literal_norm"]
    assert first["ast_literal_norm"] != identifier_change["ast_literal_norm"]
    assert first["ast_skeleton"] == identifier_change["ast_skeleton"]


def test_summary_reports_cross_run_and_cross_task_groups() -> None:
    records = [
        {
            "run_id": "run-a",
            "task": "task-a",
            "parent": "parent-a",
            "ast_literal_norm": "same",
        },
        {
            "run_id": "run-b",
            "task": "task-b",
            "parent": "parent-b",
            "ast_literal_norm": "same",
        },
        {
            "run_id": "run-c",
            "task": "task-c",
            "parent": "parent-c",
            "ast_literal_norm": "different",
        },
    ]

    summary = summarize_fingerprint(records, "ast_literal_norm")

    assert summary["fingerprinted_endpoints"] == 3
    assert summary["duplicate_groups"] == 1
    assert summary["cross_run_duplicate_groups"] == 1
    assert summary["cross_run_duplicate_endpoints"] == 2
    assert summary["cross_task_duplicate_groups"] == 1
    assert summary["large_multitask_duplicate_groups"] == 0
