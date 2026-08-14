"""Post-hoc, zero-execution diagnosis of the completed E1 evaluator adapter.

This tool never starts a candidate or calls an operator.  It re-scores immutable
submission snapshots only after the E1 coverage gate has opened all sealed D_val
receipts.  Its output is diagnostic evidence, not an E1 method result.
"""

from __future__ import annotations

import argparse
import collections
import csv
import pathlib
from typing import Any

from phase1.balanced_continuation_e1_scoring import (
    CREDENTIAL,
    TASK_SPECS,
    ScoreError,
    atomic_json,
    canonical_json,
    checked_json,
    file_sha256,
    load_labels,
    load_public_ids,
    score_submission,
    sha256_bytes,
)


SCHEMA = "balanced-continuation-e1-adapter-diagnostic-v1"


class DiagnosticError(RuntimeError):
    pass


def csv_row_count(path: pathlib.Path) -> int | None:
    if not path.is_file():
        return None
    raw = path.read_bytes()
    if CREDENTIAL.search(raw):
        raise DiagnosticError(f"credential-shaped bytes refused: {path.name}")
    try:
        text = raw.decode("utf-8-sig")
        reader = csv.reader(text.splitlines())
        rows = list(reader)
    except (UnicodeDecodeError, csv.Error) as exc:
        raise DiagnosticError(f"CSV parse failed: {path}") from exc
    return max(len(rows) - 1, 0)


def failure_class(execution: dict[str, Any]) -> str:
    status = execution.get("execution_status")
    if status in {"ok", "timeout", "invalid_format"}:
        return str(status)
    terminal = execution.get("terminal_output")
    if not isinstance(terminal, str):
        return "execution_error_unclassified"
    if "SyntaxError" in terminal:
        return "python_syntax_error"
    if "NameError" in terminal:
        return "python_name_error"
    return "execution_error_other"


def split_proof(split_root: pathlib.Path, task: str) -> dict[str, Any]:
    public_sample = split_root / "public" / task / "sample_submission.csv"
    dsearch_labels = split_root / "private" / "dsearch" / f"{task}.csv"
    dval_labels = split_root / "private" / "dval" / f"{task}.csv"
    public_ids = load_public_ids(public_sample, task)
    dsearch_ids, _ = load_labels(dsearch_labels, task)
    dval_ids, _ = load_labels(dval_labels, task)
    public_set = set(public_ids)
    dsearch_set = set(dsearch_ids)
    dval_set = set(dval_ids)
    disjoint = dsearch_set.isdisjoint(dval_set)
    union_exact = dsearch_set | dval_set == public_set
    if not disjoint or not union_exact:
        raise DiagnosticError(f"private split membership differs for {task}")
    return {
        "task": task,
        "public_submission_rows": len(public_ids),
        "dsearch_rows": len(dsearch_ids),
        "dval_rows": len(dval_ids),
        "dsearch_dval_disjoint": disjoint,
        "private_union_equals_public": union_exact,
        "public_equals_dsearch_plus_dval": len(public_ids) == len(dsearch_ids) + len(dval_ids),
        "public_sample_sha256": file_sha256(public_sample),
        "dsearch_labels_sha256": file_sha256(dsearch_labels),
        "dval_labels_sha256": file_sha256(dval_labels),
    }


def diagnose(args: argparse.Namespace) -> dict[str, Any]:
    run_root = pathlib.Path(args.run_root).resolve()
    data_gate_root = pathlib.Path(args.data_gate_root).resolve()
    split_root = data_gate_root / "e1_split"
    if not run_root.is_dir() or not split_root.is_dir():
        raise DiagnosticError("run or split root is missing")
    source_inputs = checked_json(run_root / "preparation" / "source_inputs.json")
    if pathlib.Path(source_inputs.get("data_gate_root", "")).resolve() != data_gate_root:
        raise DiagnosticError("run source_inputs binds a different data gate root")
    if source_inputs.get("contains_outcomes") is not False:
        raise DiagnosticError("E1 source_inputs outcome-blind marker differs")
    final_status = checked_json(run_root / "final_status.json")
    collection_summary = checked_json(run_root / "collection" / "summary.json")
    if (
        final_status.get("status") != "VERIFIED_COMPLETE_REAL_E1_COLLECTION"
        or final_status.get("collection_rc") != 0
        or collection_summary.get("sealed_values_opened") is not True
        or collection_summary.get("sealed_values_opened_before_coverage_gate") is True
        or collection_summary.get("coverage_gate", {}).get(
            "sealed_values_opened_before_coverage_gate"
        ) is not False
    ):
        raise DiagnosticError("sealed D_val coverage gate is not proven open")

    worker_root = run_root / "worker_outputs"
    sealed_root = run_root / "sealed"
    result_paths = sorted(worker_root.glob("*/result.json"))
    if not result_paths:
        raise DiagnosticError("no completed worker results found")
    results = [checked_json(path) for path in result_paths]
    raw_tasks = {value.get("task") for value in results}
    if any(not isinstance(task, str) or task not in TASK_SPECS for task in raw_tasks):
        raise DiagnosticError("unsupported or malformed task in worker results")
    tasks = sorted(str(task) for task in raw_tasks)
    proofs = {task: split_proof(split_root, task) for task in tasks}

    records: list[dict[str, Any]] = []
    for result_path, result in zip(result_paths, results):
        rollout_id = result.get("rollout_id")
        task = result.get("task")
        horizon = result.get("continuation_horizon")
        if (
            not isinstance(rollout_id, str)
            or result_path.parent.name != rollout_id
            or not isinstance(task, str)
            or isinstance(horizon, bool)
            or not isinstance(horizon, int)
            or horizon < 0
        ):
            raise DiagnosticError("worker result identity is malformed")
        public_sample = split_root / "public" / task / "sample_submission.csv"
        dsearch_labels = split_root / "private" / "dsearch" / f"{task}.csv"
        dval_labels = split_root / "private" / "dval" / f"{task}.csv"
        for ordinal in range(horizon + 1):
            step = result_path.parent / "steps" / f"step_{ordinal:03d}"
            execution = checked_json(step / "execution.json")
            legacy_search = checked_json(step / "dsearch.json")
            legacy_val = checked_json(sealed_root / rollout_id / f"dval_{ordinal:03d}.json")
            artifact = step / "submission.csv"
            repaired_search = score_submission(artifact, dsearch_labels, public_sample, task)
            repaired_val = score_submission(artifact, dval_labels, public_sample, task)
            operator_extraction_status: str | None = None
            usage_path = step / "operator_usage.json"
            if usage_path.is_file():
                usage = checked_json(usage_path)
                raw_status = usage.get("extraction_status")
                if not isinstance(raw_status, str):
                    raise DiagnosticError("operator extraction status is malformed")
                operator_extraction_status = raw_status
            else:
                usage = {}
            code_path = step / "code.py"
            extracted_code_chars: int | None = None
            if ordinal > 0 and code_path.is_file():
                code_raw = code_path.read_bytes()
                if CREDENTIAL.search(code_raw):
                    raise DiagnosticError("credential-shaped bytes refused in extracted code")
                extracted_code_chars = len(code_raw.decode("utf-8"))
            artifact_rows = csv_row_count(artifact)
            records.append({
                "rollout_id": rollout_id,
                "task": task,
                "ordinal": ordinal,
                "stage": "warm_start" if ordinal == 0 else "continuation",
                "execution_status": execution.get("execution_status"),
                "process_started": execution.get("process_started"),
                "timed_out": execution.get("timed_out"),
                "exit_code": execution.get("exit_code"),
                "wall_time_seconds": execution.get("wall_time_seconds"),
                "failure_class": failure_class(execution),
                "artifact_present": artifact.is_file(),
                "artifact_bytes": artifact.stat().st_size if artifact.is_file() else None,
                "artifact_rows": artifact_rows,
                "artifact_sha256": file_sha256(artifact) if artifact.is_file() else None,
                "operator_extraction_status": operator_extraction_status,
                "operator_prompt_tokens": usage.get("prompt_tokens"),
                "operator_completion_tokens": usage.get("completion_tokens"),
                "operator_total_tokens": usage.get("total_tokens"),
                "operator_at_output_token_cap": usage.get("completion_tokens") == 8192,
                "operator_extracted_code_chars": extracted_code_chars,
                "legacy_dsearch_valid": legacy_search.get("submission_valid"),
                "legacy_dsearch_grade_return_code": legacy_search.get("grade_return_code"),
                "legacy_dval_valid": legacy_val.get("submission_valid"),
                "legacy_dval_grade_return_code": legacy_val.get("grade_return_code"),
                "replayed_dsearch_valid": repaired_search["submission_valid"],
                "replayed_dsearch_score": repaired_search["score"],
                "replayed_dsearch_failure_reason": repaired_search["failure_reason"],
                "replayed_dval_valid": repaired_val["submission_valid"],
                "replayed_dval_score": repaired_val["score"],
                "replayed_dval_failure_reason": repaired_val["failure_reason"],
                "artifact_matches_public_row_count": (
                    artifact_rows == proofs[task]["public_submission_rows"]
                    if artifact_rows is not None else False
                ),
            })

    paired_dval_gains: list[float] = []
    by_rollout: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        by_rollout.setdefault(record["rollout_id"], []).append(record)
    for rollout_records in by_rollout.values():
        ordered = sorted(rollout_records, key=lambda value: value["ordinal"])
        if (
            len(ordered) == 2
            and ordered[0]["replayed_dval_valid"] is True
            and ordered[1]["replayed_dval_valid"] is True
        ):
            paired_dval_gains.append(
                float(ordered[1]["replayed_dval_score"])
                - float(ordered[0]["replayed_dval_score"])
            )

    aggregate = {
        "rollouts": len(results),
        "steps": len(records),
        "candidate_processes_started": sum(record["process_started"] is True for record in records),
        "operator_invalid_format": sum(
            record["operator_extraction_status"] == "invalid_format" for record in records
        ),
        "operator_calls_at_output_token_cap": sum(
            record["operator_at_output_token_cap"] is True for record in records
        ),
        "continuation_failure_classes": dict(sorted(collections.Counter(
            record["failure_class"] for record in records if record["ordinal"] > 0
        ).items())),
        "artifacts_present": sum(record["artifact_present"] is True for record in records),
        "legacy_dsearch_valid": sum(record["legacy_dsearch_valid"] is True for record in records),
        "legacy_dval_valid": sum(record["legacy_dval_valid"] is True for record in records),
        "replayed_dsearch_valid": sum(record["replayed_dsearch_valid"] is True for record in records),
        "replayed_dval_valid": sum(record["replayed_dval_valid"] is True for record in records),
        "replayed_paired_rollouts": len(paired_dval_gains),
        "replayed_positive_dval_gains": sum(gain > 0 for gain in paired_dval_gains),
        "replayed_zero_dval_gains": sum(gain == 0 for gain in paired_dval_gains),
        "replayed_negative_dval_gains": sum(gain < 0 for gain in paired_dval_gains),
    }
    return {
        "schema_version": SCHEMA,
        "status": "DIAGNOSTIC_ONLY_POST_HOC_ADAPTER_REPLAY_NO_METHOD_CLAIM",
        "source_run_root": str(run_root),
        "source_data_gate_root": str(data_gate_root),
        "source_commit": source_inputs.get("source_commit"),
        "diagnostic_script_sha256": file_sha256(pathlib.Path(__file__).resolve()),
        "gpu_jobs_started": 0,
        "candidate_reexecutions": 0,
        "operator_api_calls": 0,
        "private_labels_read_post_coverage_gate": True,
        "raw_private_labels_emitted": False,
        "private_evaluation_scores_emitted_post_gate": True,
        "root_cause": (
            "public submission covers D_search union D_val, while the frozen v1 scorer "
            "incorrectly required exact equality with each private subset"
        ),
        "split_proofs": [proofs[task] for task in tasks],
        "aggregate": aggregate,
        "paired_dval_gains": paired_dval_gains,
        "records": records,
        "method_claim_allowed": False,
        "repair_rerun_required_for_e1_method_result": True,
        "e2_e3_unlocked": False,
    }


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-root", required=True)
    ap.add_argument("--data-gate-root", required=True)
    ap.add_argument("--output", required=True)
    return ap


def main() -> int:
    args = parser().parse_args()
    try:
        value = diagnose(args)
        raw = canonical_json(value) + b"\n"
        output = pathlib.Path(args.output).resolve()
        atomic_json(output, value)
    except (DiagnosticError, ScoreError, OSError, ValueError) as exc:
        print(f"E1_ADAPTER_DIAGNOSTIC_ERROR: {exc}")
        return 2
    print(
        "E1_ADAPTER_DIAGNOSTIC_DONE "
        f"sha256={sha256_bytes(raw)} "
        f"replayed_paired={value['aggregate']['replayed_paired_rollouts']} "
        "method_claim_allowed=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
