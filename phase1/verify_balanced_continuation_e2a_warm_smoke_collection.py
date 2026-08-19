"""Aggregate six independently verified E2-A warm-only smoke slots."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

from phase1.balanced_continuation_e2a_scoring import atomic_json, checked_json, file_sha256
from phase1.prepare_balanced_continuation_e2a import TASKS


class VerifyError(RuntimeError):
    pass


def verify(args: argparse.Namespace) -> dict:
    run_root = pathlib.Path(args.run_root).resolve()
    preparation = pathlib.Path(args.preparation).resolve()
    receipt_path = pathlib.Path(args.receipt).resolve()
    if not run_root.is_dir() or run_root.is_symlink():
        raise VerifyError("warm-smoke run root differs")
    plan = checked_json(preparation / "run_plan.json")
    indices = plan.get("warm_smoke_assignment_indices")
    if not isinstance(indices, list) or len(indices) != 6 or len(set(indices)) != 6:
        raise VerifyError("warm-smoke plan differs")
    tasks = []
    summaries = []
    for slot in range(6):
        job = checked_json(run_root / "job_rc" / f"{slot}.json")
        receipt = checked_json(run_root / "receipts" / f"{slot}.verify.json")
        if (
            job.get("slot") != slot
            or job.get("assignment_index") != indices[slot]
            or any(job.get(key) != 0 for key in (
                "capability_rc", "producer_rc", "verifier_rc", "safety_rc"
            ))
            or not isinstance(job.get("slurm_job_id"), str)
            or receipt.get("status") != "VERIFIED_E2A_PUBLIC_WARM_SMOKE_PASS"
            or receipt.get("producer_imported") is not False
            or receipt.get("slot") != slot
            or receipt.get("assignment_index") != indices[slot]
            or receipt.get("candidate_executions") != 1
            or receipt.get("api_calls") != 0
            or receipt.get("dsearch_rows_read") != 0
            or receipt.get("dval_rows_read") != 0
            or receipt.get("dtest_rows_read") != 0
            or receipt.get("labels_opened") is not False
            or receipt.get("outcomes_read") is not False
            or receipt.get("gate_pass") is not True
        ):
            raise VerifyError(f"warm-smoke slot receipt differs: {slot}")
        summary_path = run_root / "outputs" / f"slot_{slot}" / "summary.json"
        if receipt.get("summary_sha256") != file_sha256(summary_path):
            raise VerifyError(f"warm-smoke summary hash differs: {slot}")
        tasks.append(receipt["task"])
        summaries.append(receipt["summary_sha256"])
    if tasks != list(TASKS) or len(set(tasks)) != 6:
        raise VerifyError("warm-smoke task order/coverage differs")
    result = {
        "schema_version": "balanced-continuation-e2a-warm-smoke-collection-v1",
        "status": "VERIFIED_E2A_SIX_TASK_PUBLIC_WARM_SMOKE_PASS",
        "producer_imported": False,
        "tasks": tasks,
        "assignment_indices": indices,
        "candidate_executions": 6,
        "api_calls": 0,
        "dsearch_rows_read": 0,
        "dval_rows_read": 0,
        "dtest_rows_read": 0,
        "labels_opened": False,
        "outcomes_read": False,
        "all_gate_pass": True,
        "summary_sha256": summaries,
    }
    atomic_json(receipt_path, result, mode=0o600)
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--preparation", required=True)
    parser.add_argument("--receipt", required=True)
    try:
        verify(parser.parse_args())
    except (VerifyError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"VERIFY_E2A_WARM_COLLECTION_ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
