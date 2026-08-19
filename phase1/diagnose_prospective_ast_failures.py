"""Outcome-blind post-hoc diagnostic for AST normalization failures.

This diagnostic is intentionally not a replacement for the preregistered clone
gate.  It emits only aggregate counts and never emits code, task, run, or card
identities.
"""

from __future__ import annotations

import argparse
import ast
import collections
import json
import platform
import subprocess
import sys
import textwrap
import tokenize
from pathlib import Path
from typing import Any, Callable

from phase1.audit_prospective_code_clones import (
    BLIND_KEYS,
    FROZEN_COHORT_RUN_TARGET,
    LINEAGE_KEYS,
    RUN_KEYS,
    CloneAuditError,
    read_json,
    read_jsonl,
    require_sha,
    sha256_file,
    sha256_text,
    summarize_fingerprint,
    token_literal_fingerprint,
)


PROTOCOL = "prospective_ast_failure_diagnostic_v1"


def classify_syntax_error(error: BaseException) -> str:
    if isinstance(error, TabError):
        return "tab_error"
    if isinstance(error, IndentationError):
        message = str(error).lower()
        if "expected an indented block" in message:
            return "expected_indented_block"
        if "unexpected indent" in message:
            return "unexpected_indent"
        return "other_indentation_error"
    if not isinstance(error, SyntaxError):
        return "non_syntax_parse_error"
    message = str(error).lower()
    fixed_patterns = (
        ("unterminated string", "unterminated_string"),
        ("was never closed", "unclosed_delimiter"),
        ("unmatched", "unmatched_delimiter"),
        ("invalid decimal literal", "invalid_numeric_literal"),
        ("invalid character", "invalid_character"),
        ("cannot assign", "invalid_assignment"),
        ("outside function", "statement_outside_function"),
        ("outside loop", "statement_outside_loop"),
    )
    for pattern, category in fixed_patterns:
        if pattern in message:
            return category
    if "invalid syntax" in message:
        return "generic_invalid_syntax"
    return "other_syntax_error"


def remove_markdown_fence_lines(code: str) -> str:
    return "\n".join(line for line in code.splitlines() if not line.strip().startswith("```"))


def remove_cell_command_lines(code: str) -> str:
    return "\n".join(
        line for line in code.splitlines() if not line.lstrip().startswith(("%", "!"))
    )


def combined_surface_cleanup(code: str) -> str:
    return textwrap.dedent(remove_cell_command_lines(remove_markdown_fence_lines(code)))


RECOVERY_TRANSFORMS: dict[str, Callable[[str], str]] = {
    "dedent_only": textwrap.dedent,
    "remove_markdown_fence_lines_only": remove_markdown_fence_lines,
    "remove_cell_command_lines_only": remove_cell_command_lines,
    "combined_fence_cell_dedent": combined_surface_cleanup,
}


def parses_as_python(code: str) -> bool:
    try:
        ast.parse(code)
    except (IndentationError, SyntaxError, ValueError, TypeError, MemoryError):
        return False
    return True


def _load_cohort(
    state_root: Path, snapshot_root: Path, cohort_run_target: int
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    state_root = state_root.resolve()
    snapshot_root = snapshot_root.resolve()
    if snapshot_root.parent != state_root / "snapshots":
        raise CloneAuditError("snapshot is outside state root")
    if cohort_run_target != FROZEN_COHORT_RUN_TARGET:
        raise CloneAuditError("cohort target differs from frozen first-960 protocol")

    registry_path = snapshot_root / "intake_registry.jsonl"
    runs_path = snapshot_root / "accumulator" / "provisional_runs.jsonl"
    summary_path = snapshot_root / "accumulator" / "summary.json"
    registry = list(read_jsonl(registry_path))
    cards: dict[str, dict[str, str]] = {}
    intake_summary_shas: dict[str, str] = {}
    for entry in registry:
        if set(entry) != {"drop_id", "intake_dir", "summary_sha256"}:
            raise CloneAuditError("registry schema mismatch")
        drop_id = entry["drop_id"]
        intake_dir = Path(entry["intake_dir"]).resolve()
        if not isinstance(drop_id, str) or intake_dir.parent != state_root / "intakes":
            raise CloneAuditError("intake registry binding mismatch")
        if intake_dir.name != drop_id or drop_id in intake_summary_shas:
            raise CloneAuditError("duplicate or mismatched intake")
        intake_summary = intake_dir / "summary.json"
        require_sha(intake_summary, entry["summary_sha256"])
        summary = read_json(intake_summary)
        outputs = summary.get("outputs")
        security = summary.get("security")
        blindness = summary.get("blindness")
        if not isinstance(outputs, dict) or not isinstance(security, dict) or not isinstance(
            blindness, dict
        ):
            raise CloneAuditError("intake metadata missing")
        if (
            security.get("env_members_read") is not False
            or security.get("live_event_journal_members_read") is not False
            or blindness.get("labels_used_for_run_selection") is not False
            or blindness.get("labels_used_for_endpoint_selection") is not False
        ):
            raise CloneAuditError("intake blindness mismatch")
        intake_summary_shas[drop_id] = entry["summary_sha256"]
        manifest = intake_dir / "eligible_blind_manifest.jsonl"
        require_sha(manifest, outputs.get("eligible_blind_manifest_sha256"))
        for row in read_jsonl(manifest):
            if set(row) != BLIND_KEYS or not isinstance(row.get("lineage"), dict):
                raise CloneAuditError("blind manifest schema mismatch")
            if set(row["lineage"]) != LINEAGE_KEYS:
                raise CloneAuditError("blind lineage schema mismatch")
            card_id = row["card_id"]
            values = (card_id, row["run_id"], row["task"], row["code"], row["lineage"]["parent"])
            if not all(isinstance(value, str) for value in values):
                raise CloneAuditError("blind manifest type mismatch")
            if card_id in cards or sha256_text(row["code"]) != row["code_sha256"]:
                raise CloneAuditError("duplicate card or code SHA mismatch")
            cards[card_id] = {
                "run_id": row["run_id"],
                "task": row["task"],
                "parent": row["lineage"]["parent"],
                "code": row["code"],
            }

    runs = list(read_jsonl(runs_path))
    for row in runs:
        if set(row) != RUN_KEYS or row.get("flow_status") != "scoreable":
            raise CloneAuditError("provisional run schema mismatch")
    ordered_runs = sorted(
        runs,
        key=lambda row: (
            str(row["generation_started_at_utc"]),
            str(row["source_sha256"]),
            str(row["run_id"]),
        ),
    )
    cohort_run_ids = {str(row["run_id"]) for row in ordered_runs[:cohort_run_target]}
    cohort = [
        record
        for _card_id, record in sorted(cards.items())
        if record["run_id"] in cohort_run_ids
    ]
    accumulator = read_json(summary_path).get("inventory")
    if not isinstance(accumulator, dict):
        raise CloneAuditError("accumulator inventory missing")
    if (
        accumulator.get("provisional_first960_runs") != len(cohort_run_ids)
        or accumulator.get("provisional_first960_endpoints") != len(cohort)
    ):
        raise CloneAuditError("diagnostic cohort differs from accumulator")
    inputs = {
        "intake_registry_sha256": sha256_file(registry_path),
        "provisional_runs_sha256": sha256_file(runs_path),
        "accumulator_summary_sha256": sha256_file(summary_path),
        "intake_summary_sha256": dict(sorted(intake_summary_shas.items())),
    }
    return cohort, inputs


def diagnose(records: list[dict[str, str]]) -> dict[str, Any]:
    failures: list[tuple[dict[str, str], BaseException]] = []
    for record in records:
        try:
            ast.parse(record["code"])
        except (IndentationError, SyntaxError, ValueError, TypeError, MemoryError) as error:
            failures.append((record, error))

    exception_categories = collections.Counter(
        classify_syntax_error(error) for _record, error in failures
    )
    recovery_counts = {
        name: sum(parses_as_python(transform(record["code"])) for record, _error in failures)
        for name, transform in RECOVERY_TRANSFORMS.items()
    }
    recovered_by_any = sum(
        any(parses_as_python(transform(record["code"])) for transform in RECOVERY_TRANSFORMS.values())
        for record, _error in failures
    )
    token_records: list[dict[str, str]] = []
    for record, _error in failures:
        try:
            token_value = token_literal_fingerprint(record["code"])
        except (IndentationError, SyntaxError, tokenize.TokenError):
            token_value = ""
        token_records.append(
            {
                "run_id": record["run_id"],
                "task": record["task"],
                "parent": record["parent"],
                "token_literal_norm": token_value,
            }
        )
    token_summary = summarize_fingerprint(token_records, "token_literal_norm")
    failure_task_counts = collections.Counter(record["task"] for record, _error in failures)
    failure_run_counts = collections.Counter(record["run_id"] for record, _error in failures)
    n_failures = len(failures)
    recoveries = {
        name: {
            "recovered_endpoints": count,
            "fraction_of_direct_failures": count / n_failures if n_failures else None,
        }
        for name, count in sorted(recovery_counts.items())
    }
    recoveries["union_any_fixed_transform"] = {
        "recovered_endpoints": recovered_by_any,
        "fraction_of_direct_failures": recovered_by_any / n_failures if n_failures else None,
    }
    return {
        "direct_ast": {
            "input_endpoints": len(records),
            "parseable_endpoints": len(records) - n_failures,
            "failure_endpoints": n_failures,
            "failure_fraction": n_failures / len(records) if records else None,
            "failure_runs": len(failure_run_counts),
            "failure_tasks": len(failure_task_counts),
            "maximum_failures_in_one_run": max(failure_run_counts.values(), default=0),
            "maximum_failure_task_share": max(failure_task_counts.values(), default=0) / n_failures
            if n_failures
            else None,
            "anonymous_task_failure_counts_descending": sorted(
                failure_task_counts.values(), reverse=True
            ),
            "exception_categories": dict(sorted(exception_categories.items())),
        },
        "fixed_surface_recoveries": recoveries,
        "failed_subset_token_literal_norm": token_summary,
    }


def run(
    state_root: Path,
    snapshot_root: Path,
    cohort_run_target: int,
    source_commit: str,
) -> dict[str, Any]:
    cohort, inputs = _load_cohort(state_root, snapshot_root, cohort_run_target)
    return {
        "status": "POST_HOC_AST_FAILURE_DIAGNOSTIC_COMPLETE",
        "protocol": PROTOCOL,
        "source_commit": source_commit,
        "source_sha256": sha256_file(Path(__file__)),
        "snapshot_sha256": snapshot_root.resolve().name,
        "scope": {
            "name": "provisional_first960_prefix",
            "target_runs": cohort_run_target,
            "observed_endpoints": len(cohort),
            "confirmatory_outcomes_opened": False,
        },
        "inputs": inputs,
        "diagnostic": diagnose(cohort),
        "interpretation_contract": {
            "post_hoc_after_aggregate_ast_coverage_failure": True,
            "preregistered_clone_gate_changed": False,
            "preregistered_clone_gate_rescued": False,
            "may_replace_primary_ast_result": False,
            "semantic_or_fuzzy_clone_absence_proven": False,
        },
        "reproducibility": {
            "python_version": platform.python_version(),
            "python_executable": str(Path(sys.executable).resolve()),
            "randomness_used": False,
        },
        "security": {
            "code_values_emitted": False,
            "task_run_or_card_identities_emitted": False,
            "label_vault_opened": False,
            "outcome_files_opened": [],
            "scorer_prediction_files_opened": [],
        },
    }


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-root", required=True, type=Path)
    parser.add_argument("--snapshot-root", required=True, type=Path)
    parser.add_argument("--cohort-run-target", required=True, type=int)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = arguments()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite output: {args.output}")
    if len(args.source_commit) != 40 or any(c not in "0123456789abcdef" for c in args.source_commit):
        raise CloneAuditError("source commit is not a lowercase full Git SHA")
    repo_root = Path(__file__).resolve().parent.parent
    actual_commit = subprocess.check_output(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"], text=True
    ).strip()
    relative_source = Path(__file__).resolve().relative_to(repo_root).as_posix()
    committed_blob = subprocess.check_output(
        ["git", "-C", str(repo_root), "rev-parse", f"{actual_commit}:{relative_source}"],
        text=True,
    ).strip()
    worktree_blob = subprocess.check_output(
        ["git", "-C", str(repo_root), "hash-object", str(Path(__file__).resolve())], text=True
    ).strip()
    if actual_commit != args.source_commit or committed_blob != worktree_blob:
        raise CloneAuditError("source commit or Git blob binding failed")
    receipt = run(
        args.state_root,
        args.snapshot_root,
        args.cohort_run_target,
        args.source_commit,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        "PROSPECTIVE_AST_FAILURE_DIAGNOSTIC_COMPLETE",
        f"failures={receipt['diagnostic']['direct_ast']['failure_endpoints']}",
        "outcomes_read=false",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
